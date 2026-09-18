#!/usr/bin/env python3
"""
batch_apply_workday.py - Autonomous Workday External Portal Application Engine
Automated application engine for early-career SWE and university internship positions.
Features:
1. Multi-layout Workday authentication (Layout A direct, Layout B SSO choice, existing account redirect).
2. Pointer event interception bypass via div[data-automation-id="click_filter"].
3. Silent 6-digit email OTP retrieval via email_verification_helper.py.
4. Hidden DOM file upload handling for tailored ATS resume attachment.
5. Dynamic multi-step form filler (My Information, My Experience, Application Questions, Voluntary Disclosures, Self Identify).
6. Truthful EEO ground truth (US Citizen, no sponsorship, Rutgers BS May 2024 / MS May 2028, Asian, Male, non-veteran, no disability).
7. Confirmation verification, permanent screenshot logging, and central Google Sheet synchronization.
"""

import os
import sys
import time
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

ENGINE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, os.path.expanduser("~/.agents/skills/resume-tailor-swe/scripts"))

from email_verification_helper import get_latest_verification_code
from fast_resume_selector import get_fast_tailored_resume

LOG_SCRIPT = os.path.expanduser("~/.agents/skills/resume-tailor-swe/scripts/log_application.py")
CONFIRMATIONS_DIR = os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/confirmations")
os.makedirs(CONFIRMATIONS_DIR, exist_ok=True)

try:
    from config_loader import load_config, get_candidate_dict
except ImportError:
    try:
        from application_engine.config_loader import load_config, get_candidate_dict
    except ImportError:
        def load_config(): return {}
        def get_candidate_dict(): return {}

_cfg = load_config()
_c = get_candidate_dict()

CANDIDATE = {
    "first_name": _c.get("first_name", "Jane"),
    "last_name": _c.get("last_name", "Doe"),
    "name": _c.get("name", "Jane Doe"),
    "email": _c.get("email", "jane.doe@example.com"),
    "password": _cfg.get("workday_password", "YourWorkdayPassword123!#"),
    "phone": _c.get("phone", "555-123-4567"),
    "address": _cfg.get("address", "123 Innovation Way"),
    "city": _c.get("city", "New York"),
    "state": _c.get("state", "New York"),
    "zip": _c.get("postal_code", "10001"),
    "country": _c.get("country", "United States of America"),
    "linkedin": _c.get("linkedin", "https://www.linkedin.com/in/janedoe/"),
    "github": _c.get("github", "https://github.com/janedoe"),
    "school": _c.get("school", "State University"),
    "degree": _c.get("degree_undergrad", "Bachelor of Science in Computer Science"),
    "degree_ms": _c.get("degree", "Master of Science in Computer Science"),
    "field": _c.get("field_of_study", "Computer Science"),
    "gpa": _c.get("gpa", "3.85")
}

def normalize_url(u):
    u = u.strip().lower().rstrip("/")
    u = re.sub(r"/en-[a-z]{2}/", "/", u)
    return u

def load_applied():
    applied_urls = set()
    applied_pairs = set()
    applied_reqs = set()
    import gspread
    keyfile = os.path.expanduser(_cfg.get("google_service_account_key") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY", ""))
    sheet_id = _cfg.get("google_sheet_id") or os.environ.get("GOOGLE_SPREADSHEET_ID", "")
    if not keyfile or not os.path.exists(keyfile) or not sheet_id:
        return set(), set()
    try:
        gc = gspread.service_account(keyfile)
        sh = gc.open_by_key(sheet_id)
        ws = sh.sheet1
        for r in ws.get_all_values()[1:]:
            c = r[0].strip().lower() if len(r) > 0 else ""
            role_val = r[2].strip().lower() if len(r) > 2 else ""
            u = r[5].strip() if len(r) > 5 else ""
            if c and role_val:
                applied_pairs.add(f"{c}:::{role_val}")
            if u:
                applied_urls.add(normalize_url(u))
                m = re.search(r'([A-Z]{1,3}-?\d{4,}|\b\d{5,}\b)', u)
                if m:
                    applied_reqs.add(m.group(1).replace('-', ''))
    except Exception as e:
        print(f"⚠️ Warning loading sheet records: {e}", flush=True)
    return applied_urls, applied_pairs, applied_reqs

def wait_for_workday_spinner(page, timeout_sec=8):
    """Waits for Workday bouncing dots / loading spinner to disappear."""
    try:
        page.wait_for_selector(
            '[data-automation-id="loadingSpinner"], .loading-dots, .css-1m1v4e8, [aria-label="Loading"]',
            state="hidden",
            timeout=timeout_sec * 1000
        )
    except Exception:
        pass
    time.sleep(1)

def is_authenticated(page):
    """Checks if session is truly inside the multi-step application form."""
    if page.locator('[data-automation-id="SignInWithEmailButton"], button:has-text("Sign in with email")').is_visible():
        return False
    if page.locator('input[data-automation-id="email"]').is_visible():
        return False
    title = page.title().lower()
    if "sign in" in title or "create account" in title:
        return False
    if page.locator('[data-automation-id="myInformationPage"], [data-automation-id="progressBarActiveStep"]:not(:has-text("Sign In")):not(:has-text("Create Account"))').is_visible():
        return True
    return False

def handle_workday_auth(page, company_name):
    """Handles Workday sign in or create account screens across all layouts."""
    print("  🔑 Checking Workday Authentication...", flush=True)
    time.sleep(3)
    
    if is_authenticated(page):
        print("  ✅ Already authenticated.", flush=True)
        return True

    # Check for Layout B: 'Sign in with email' button
    sso_email_btn = page.locator('[data-automation-id="SignInWithEmailButton"], button:has-text("Sign in with email")').first
    if sso_email_btn.is_visible(timeout=3000):
        print("  🔘 Detected Layout B (SSO Choice). Clicking 'Sign in with email'...", flush=True)
        sso_email_btn.click(force=True)
        time.sleep(3)

    for attempt in range(3):
        if is_authenticated(page):
            print("  ✅ Authenticated into application flow.", flush=True)
            return True

        email_inp = page.locator('input[data-automation-id="email"]').first
        pw_inp = page.locator('input[data-automation-id="password"]').first
        vpw_inp = page.locator('input[data-automation-id="verifyPassword"]').first

        if vpw_inp.is_visible(timeout=1500):
            # Create Account mode
            print("  📝 In Create Account mode. Filling verify password...", flush=True)
            if email_inp.is_visible():
                email_inp.fill(CANDIDATE["email"])
            if pw_inp.is_visible():
                pw_inp.fill(CANDIDATE["password"])
            vpw_inp.fill(CANDIDATE["password"])
            chk = page.locator('input[data-automation-id="createAccountCheckbox"], [data-automation-id="createAccountCheckbox"], label:has-text("consent"), label:has-text("Terms of use")').first
            if chk.is_visible(timeout=1500):
                try:
                    chk.check(force=True)
                except Exception:
                    chk.click(force=True)
            cf_create = page.locator('div[data-automation-id="click_filter"][aria-label="Create Account"]').first
            if cf_create.is_visible(timeout=2000):
                cf_create.click(force=True)
            else:
                create_btn = page.locator('[data-automation-id="createAccountSubmitButton"], button:has-text("Create Account")').first
                if create_btn.is_visible(timeout=2000):
                    create_btn.click(force=True)
            time.sleep(5)
        else:
            # Sign In mode
            print("  🔐 Submitting Sign In...", flush=True)
            if email_inp.is_visible():
                email_inp.fill(CANDIDATE["email"])
            if pw_inp.is_visible():
                pw_inp.fill(CANDIDATE["password"])
            cf_si = page.locator('div[data-automation-id="click_filter"][aria-label="Sign In"]').first
            if cf_si.is_visible(timeout=2000):
                cf_si.click(force=True)
            else:
                signin_btn = page.locator('[data-automation-id="signInSubmitButton"], button:has-text("Sign In")').first
                if signin_btn.is_visible(timeout=2000):
                    signin_btn.click(force=True)
            time.sleep(5)

        # Check for email verification OTP prompt
        body_text = page.locator("body").inner_text().lower()
        if any(k in body_text for k in ["verification code", "security code", "one-time passcode", "enter code"]):
            print(f"  🔔 Workday OTP requested for {company_name}! Fetching from Gmail...", flush=True)
            code = get_latest_verification_code(company=company_name, max_wait_sec=45)
            if code:
                code_inp = page.locator('input[data-automation-id*="code"], input[aria-label*="code" i], input[id*="code" i]').first
                if code_inp.is_visible():
                    code_inp.fill(code)
                    time.sleep(1)
                    page.locator('button:has-text("Verify"), button:has-text("Submit"), button:has-text("Continue")').first.click(force=True)
                    time.sleep(4)

        # If account not found or wrong password -> switch to Create Account
        if any(k in body_text for k in ["wrong email address or password", "account might be locked", "invalid user name", "cannot find your account"]):
            print("  ℹ️ Account does not exist on this tenant. Switching to Create Account...", flush=True)
            create_link = page.locator('[data-automation-id="createAccountLink"], a:has-text("Create Account")').first
            if create_link.is_visible(timeout=2000):
                create_link.click(force=True)
                time.sleep(3)
                continue

        # If redirected to Sign In or account already exists -> switch to Sign In
        if any(k in body_text for k in ["already exists", "account with this email already exists", "sign in"]) and "sign in" in page.title().lower():
            print("  ℹ️ On Sign In screen. Entering credentials and signing in...", flush=True)
            em = page.locator('input[data-automation-id="email"]').first
            pw = page.locator('input[data-automation-id="password"]').first
            if em.is_visible():
                em.fill(CANDIDATE["email"])
            if pw.is_visible():
                pw.fill(CANDIDATE["password"])
            cf_si2 = page.locator('div[data-automation-id="click_filter"][aria-label="Sign In"]').first
            if cf_si2.is_visible():
                cf_si2.click(force=True)
            else:
                sbtn = page.locator('[data-automation-id="signInSubmitButton"]').first
                if sbtn.is_visible():
                    sbtn.click(force=True)
            time.sleep(5)

        if is_authenticated(page):
            print("  ✅ Workday authentication successful.", flush=True)
            return True

    return is_authenticated(page)

def fill_all_workday_section_fields(page, today):
    """Dynamically identifies and answers all form controls present on current section."""
    # 1. Fill Contact & Address info
    fn = page.locator('input[id*="firstName" i], input[name*="firstName" i]').first
    if fn.is_visible() and not fn.input_value():
        fn.fill(CANDIDATE["first_name"])
    ln = page.locator('input[id*="lastName" i], input[name*="lastName" i]').first
    if ln.is_visible() and not ln.input_value():
        ln.fill(CANDIDATE["last_name"])
    addr = page.locator('input[id*="addressLine1" i], input[name*="addressLine1" i]').first
    if addr.is_visible() and not addr.input_value():
        addr.fill(CANDIDATE["address"])
    city = page.locator('input[id*="city" i], input[name*="city" i]').first
    if city.is_visible() and not city.input_value():
        city.fill(CANDIDATE["city"])
    postal = page.locator('input[id*="postalCode" i], input[name*="postalCode" i]').first
    if postal.is_visible() and not postal.input_value():
        postal.fill(CANDIDATE["zip"])

    # Email
    em = page.locator('input[id*="emailAddress" i], input[name*="emailAddress" i], input[type="email"]').first
    if em.is_visible() and not em.input_value():
        em.fill(CANDIDATE["email"])

    # Phone
    ph = page.locator('input[id*="phoneNumber--phoneNumber" i], input[name="phoneNumber"], input[id="phoneNumber--phoneNumber"]').first
    if not ph.is_visible():
        ph = page.locator('input[type="tel"], input[id*="phoneNumber" i]:not([id*="countryPhoneCode" i])').first
    if ph.is_visible() and not ph.input_value():
        ph.fill(CANDIDATE["phone"])

    # LinkedIn
    for li in page.locator('input[id*="linkedIn" i], input[name*="linkedIn" i], input[data-automation-id*="linkedIn" i]').all():
        try:
            val = li.input_value().strip()
            if not val or "www." not in val or not val.endswith("/"):
                li.fill(CANDIDATE["linkedin"])
        except Exception:
            pass

    # Country
    c_btn = page.locator('button[id*="addressSection_country" i]:not([id*="countryPhoneCode" i]):not([id*="countryRegion" i]), button[aria-label*="Country" i]:not([aria-label*="Phone" i])').first
    if c_btn.is_visible() and ("Select One" in (c_btn.get_attribute("aria-label") or "") or "Select One" in c_btn.inner_text()):
        c_btn.click(force=True)
        time.sleep(1)
        us = page.locator('[role="option"]:has-text("United States of America"), [data-automation-id*="promptOption"]:has-text("United States of America"), li:has-text("United States of America")').first
        if us.is_visible():
            us.click(force=True)
            time.sleep(1)
        else:
            page.keyboard.press("Escape")

    c_inp = page.locator('input[id*="addressSection_country" i]:not([id*="countryPhoneCode" i]):not([id*="countryRegion" i])').first
    if c_inp.is_visible() and not c_inp.input_value():
        c_inp.fill("United States of America")
        time.sleep(1)
        c_inp.press("Enter")
        time.sleep(1)
        us = page.locator('[role="option"]:has-text("United States of America"), [data-automation-id*="promptOption"]:has-text("United States")').first
        if us.is_visible():
            us.click(force=True)
            time.sleep(1)

    # State dropdown / input
    st_btn = page.locator('button[id*="countryRegion" i], button[name*="countryRegion" i], button[aria-label*="State " i]').first
    if st_btn.is_visible() and ("Select One" in (st_btn.get_attribute("aria-label") or "") or "Select One" in st_btn.inner_text()):
        st_btn.click(force=True)
        time.sleep(1)
        nj = page.locator('[role="option"]:has-text("New Jersey"), [data-automation-id*="promptOption"]:has-text("New Jersey"), li:has-text("New Jersey")').first
        if nj.is_visible():
            nj.click(force=True)
            time.sleep(1)
        else:
            page.keyboard.press("Escape")

    st_inp = page.locator('input[id*="countryRegion" i]').first
    if st_inp.is_visible() and not st_inp.input_value():
        st_inp.fill("New Jersey")
        time.sleep(1)
        st_inp.press("Enter")
        time.sleep(1)
        nj = page.locator('[role="option"]:has-text("New Jersey"), [data-automation-id*="promptOption"]:has-text("New Jersey"), li:has-text("New Jersey")').first
        if nj.is_visible():
            nj.click(force=True)
            time.sleep(1)

    # Phone device type
    pt_btn = page.locator('button[id*="phoneType" i], button[name*="phoneType" i], button[aria-label*="Phone Device Type" i]').first
    if pt_btn.is_visible() and ("Select One" in (pt_btn.get_attribute("aria-label") or "") or "Select One" in pt_btn.inner_text()):
        pt_btn.click(force=True)
        time.sleep(1)
        mob = page.locator('[role="option"]:has-text("Mobile"), [data-automation-id*="promptOption"]:has-text("Mobile"), li:has-text("Mobile")').first
        if mob.is_visible():
            mob.click(force=True)
            time.sleep(1)

    # Source
    src_inp = page.locator('input[id*="source" i], input[name*="source" i], input[data-automation-id*="source" i]').first
    if src_inp.is_visible() and not src_inp.input_value():
        src_inp.fill("LinkedIn")
        time.sleep(1)
        src_inp.press("Enter")
        time.sleep(1.5)
        lopt = page.locator('[role="option"]:has-text("LinkedIn"), [data-automation-id*="promptOption"]:has-text("LinkedIn")').first
        if lopt.is_visible():
            lopt.click(force=True)
            time.sleep(1)

    src_btn = page.locator('button[id*="source" i], button[name*="source" i], button[aria-label*="Hear" i]').first
    if src_btn.is_visible() and ("Select One" in (src_btn.get_attribute("aria-label") or "") or "Select One" in src_btn.inner_text()):
        src_btn.click(force=True)
        time.sleep(1)
        opt = page.locator('[data-automation-id="promptOption"]:has-text("LinkedIn"), [role="option"]:has-text("LinkedIn"), li:has-text("LinkedIn"), [role="option"]:has-text("Career Site")').first
        if opt.is_visible():
            opt.click(force=True)
            time.sleep(1)

    # 2. Education & Experience in My Experience
    for jt in page.locator('input[id*="jobTitle" i], input[name*="jobTitle" i]').all():
        try:
            if not jt.input_value().strip():
                jt.fill("Software Engineer")
        except Exception:
            pass

    for comp_inp in page.locator('input[id*="company" i], input[name*="company" i]').all():
        try:
            if not comp_inp.input_value().strip():
                comp_inp.fill("Rutgers University")
        except Exception:
            pass

    curr_chk = page.locator('input[id*="currentlyWorkHere" i], label:has-text("I currently work here")').first
    if curr_chk.is_visible():
        try:
            curr_chk.check(force=True)
        except Exception:
            curr_chk.click(force=True)

    sch = page.locator('input[id*="school" i]').first
    if sch.is_visible() and not sch.input_value():
        sch.fill("Rutgers University")
        time.sleep(1)
        sch.press("Enter")
        time.sleep(2)
        sopt = page.locator('[role="option"]:has-text("Rutgers"), [data-automation-id*="promptOption"]:has-text("Rutgers")').first
        if sopt.is_visible():
            sopt.click(force=True)
            time.sleep(1)

    deg_btn = page.locator('button[id*="degree" i], button[aria-label*="Degree " i]').first
    if deg_btn.is_visible() and ("Select One" in (deg_btn.get_attribute("aria-label") or "") or "Select One" in deg_btn.inner_text()):
        deg_btn.click(force=True)
        time.sleep(1)
        deg_opt = page.locator('[role="option"]:text-is("BS"), [role="option"]:text-is("Bachelor of Science"), [role="option"]:has-text("BS"), [role="option"]:has-text("Bachelor"), [role="option"]:text-is("MS")').first
        if deg_opt.is_visible():
            deg_opt.click(force=True)
            time.sleep(1.5)
        else:
            page.keyboard.press("Escape")

    fos = page.locator('input[id*="fieldOfStudy" i]').first
    if fos.is_visible() and not fos.input_value():
        fos.fill("Computer Science")
        time.sleep(1)
        fos.press("Enter")
        time.sleep(2)
        fopt = page.locator('[role="option"]:has-text("Computer Science"), [data-automation-id*="promptOption"]:has-text("Computer Science")').first
        if fopt.is_visible():
            fopt.click(force=True)
            time.sleep(1)

    gpa = page.locator('input[id*="gradeAverage" i]').first
    if gpa.is_visible() and not gpa.input_value():
        gpa.fill("3.85")

    y1 = page.locator('input[id*="firstYearAttended" i]').first
    if y1.is_visible() and not y1.input_value():
        y1.fill("2020")
    y2 = page.locator('input[id*="lastYearAttended" i]').first
    if y2.is_visible() and not y2.input_value():
        y2.fill("2024")

    # Language proficiency
    lang_btn = page.locator('button[id*="language-5--language" i], button[id*="language" i][id*="language"]').first
    if not lang_btn.is_visible():
        lang_btn = page.locator('button[id*="language" i], button[aria-label*="Language " i]').first
    if lang_btn.is_visible() and ("Select One" in (lang_btn.get_attribute("aria-label") or "") or "Select One" in lang_btn.inner_text()):
        lang_btn.click(force=True)
        time.sleep(1)
        lopt = page.locator('[role="option"]:has-text("English"), [data-automation-id*="promptOption"]:has-text("English"), li:has-text("English")').first
        if lopt.is_visible():
            lopt.click(force=True)
            time.sleep(1.5)
        else:
            page.keyboard.press("Escape")

    native = page.locator('input[id*="native" i]').first
    if native.is_visible():
        nid = native.get_attribute("id") or ""
        try:
            page.locator(f'label[for="{nid}"]').click(force=True)
        except Exception:
            pass

    for prof in page.locator('button[id*="language-"]:not([id*="language-5--language"]):not([id*="language-4--language"])').all():
        if prof.is_visible() and ("Select One" in (prof.get_attribute("aria-label") or "") or "Select One" in prof.inner_text()):
            prof.click(force=True)
            time.sleep(1.5)
            popt = page.locator('[role="option"]:has-text("Fluent"), [role="option"]:has-text("5 - Fluent"), [role="option"]:has-text("Native"), [role="option"]:has-text("Proficient")').first
            if popt.is_visible():
                popt.click(force=True)
                time.sleep(1.5)
            else:
                page.keyboard.press("Escape")
                time.sleep(0.5)

    # 3. Date pickers (Month, Day, Year inputs)
    for m_inp in page.locator('input[id*="dateSectionMonth-input" i], input[id*="Month-input" i]').all():
        if m_inp.is_visible() and not m_inp.input_value():
            lbl = m_inp.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, div') || el.parentElement).innerText").lower()
            if any(k in lbl for k in ["today", "signature", "disability"]):
                m_inp.fill(f"{today.month:02d}")
            else:
                m_inp.fill("05")

    for d_inp in page.locator('input[id*="dateSectionDay-input" i], input[id*="Day-input" i]').all():
        if d_inp.is_visible() and not d_inp.input_value():
            lbl = d_inp.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, div') || el.parentElement).innerText").lower()
            if any(k in lbl for k in ["today", "signature", "disability"]):
                d_inp.fill(f"{today.day:02d}")
            else:
                d_inp.fill(f"{today.day:02d}")

    for y_inp in page.locator('input[id*="dateSectionYear-input" i], input[id*="Year-input" i]').all():
        if y_inp.is_visible():
            val = y_inp.input_value()
            lbl = y_inp.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, div') || el.parentElement).innerText").lower()
            if any(k in lbl for k in ["today", "signature", "disability"]):
                y_inp.fill(f"{today.year}")
            elif any(k in lbl for k in ["graduat", "expected", "degree", "end", "completion"]):
                if not val or val == "2005":
                    y_inp.fill("2028")
            elif any(k in lbl for k in ["work", "job", "from", "experience"]):
                if not val or val == "2005":
                    y_inp.fill("2023")
            elif not val or val == "2005":
                y_inp.fill(f"{today.year}")

    # 4. Self Identify (Disability signature & Date)
    today_str = f"{today.month:02d}/{today.day:02d}/{today.year}"
    for n_inp in page.locator('input[id*="name" i], input[data-automation-id*="name" i], input[aria-label*="name" i]').all():
        try:
            if n_inp.is_visible() and not n_inp.input_value().strip():
                n_inp.fill(f"{CANDIDATE['first_name']} {CANDIDATE['last_name']}")
        except Exception:
            pass

    for d_inp in page.locator('input[id*="date" i], input[data-automation-id*="date" i], input[aria-label*="date" i], input[placeholder*="YYYY" i], input[placeholder*="yyyy" i]').all():
        try:
            if d_inp.is_visible():
                lbl = d_inp.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, div') || el.parentElement).innerText").lower()
                if any(k in lbl for k in ["today", "date", "signature", "disability"]):
                    d_inp.fill(today_str)
        except Exception:
            pass

    for chk in page.locator('input[id*="disability" i], input[type="radio"], input[type="checkbox"]').all():
        try:
            rid = chk.get_attribute("id") or ""
            lbl_elem = page.locator(f'label[for="{rid}"]').first if rid else None
            lt = (lbl_elem.inner_text().lower() if lbl_elem and lbl_elem.count() > 0 else "")
            if not lt:
                lt = chk.evaluate("el => (el.closest('label') || el.closest('div')).innerText").lower()
            if "no" in lt and any(k in lt for k in ["disabilit", "record", "history"]) and "yes" not in lt and "wish" not in lt and "want" not in lt:
                if not chk.is_checked():
                    if lbl_elem and lbl_elem.is_visible():
                        lbl_elem.click(force=True)
                    else:
                        chk.click(force=True)
                    if not chk.is_checked():
                        chk.evaluate("el => el.click()")
                    break
        except Exception:
            pass

    # 5. Textareas (strictly zero dashes)
    for ta in page.locator('textarea').all():
        try:
            if not ta.is_visible() or ta.input_value().strip():
                continue
            lbl = ta.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, [role=\"group\"], div') || el.parentElement).innerText").lower()
            if any(k in lbl for k in ["visa", "citizenship", "residential", "work auth"]):
                ta.fill("United States Citizen. I do not require visa sponsorship.")
            elif any(k in lbl for k in ["non-compete", "restrictive", "restrictions", "employed"]):
                ta.fill("None. I do not have any non compete or restrictive agreements.")
            elif any(k in lbl for k in ["role description", "description", "responsibilities"]):
                ta.fill("Developed and maintained backend services, REST APIs, and automated data pipelines using Python and Java.")
            elif any(k in lbl for k in ["estimated graduation", "graduation date", "format mm/yyyy"]):
                ta.fill("05/2028")
            elif any(k in lbl for k in ["degree major", "major and/or minor", "major"]):
                ta.fill("Computer Science")
            elif any(k in lbl for k in ["cover letter", "interest", "why do you want", "summary", "tell us"]):
                ta.fill("I am excited to contribute my software engineering background in Python, Java, and cloud systems to your team.")
            elif any(k in lbl for k in ["skills", "technologies", "experience"]):
                ta.fill("Python, Java, TypeScript, React, Docker, AWS, PostgreSQL, REST APIs.")
            else:
                ta.fill("N/A")
        except Exception:
            pass

    # 6. General required text inputs if empty (strictly zero dashes)
    for inp in page.locator('input[type="text"]:not([readonly]), input:not([type]):not([readonly])').all():
        try:
            if not inp.is_visible() or inp.input_value().strip():
                continue
            lbl = inp.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, [role=\"group\"], div') || el.parentElement).innerText").lower()
            ph = (inp.get_attribute("placeholder") or "").lower()
            if any(k in lbl for k in ["linkedin"]):
                inp.fill(CANDIDATE["linkedin"])
            elif any(k in lbl for k in ["github"]):
                inp.fill(CANDIDATE["github"])
            elif any(k in lbl for k in ["website", "portfolio"]):
                inp.fill(CANDIDATE.get("portfolio", CANDIDATE.get("linkedin", "")))
            elif any(k in lbl for k in ["job title", "title *", "title"]):
                inp.fill("Software Engineer")
            elif any(k in lbl for k in ["company", "employer"]):
                inp.fill("Rutgers University")
            elif any(k in lbl for k in ["location"]):
                inp.fill("Piscataway, NJ")
            elif any(k in lbl for k in ["from", "start date"]) or "from" in ph:
                inp.fill("05/2023")
            elif any(k in lbl for k in ["to", "end date"]) or "to" in ph:
                inp.fill("05/2024")
            elif "mm/yyyy" in ph:
                if any(k in lbl for k in ["graduat", "expected", "degree"]):
                    inp.fill("05/2028")
                elif any(k in lbl for k in ["start", "from"]):
                    inp.fill("05/2023")
                else:
                    inp.fill("05/2024")
            elif any(k in lbl for k in ["estimated graduation", "graduation date"]):
                inp.fill("05/2028")
            elif any(k in lbl for k in ["degree major", "major and/or minor"]):
                inp.fill("Computer Science")
            elif any(k in lbl for k in ["gpa"]):
                inp.fill("3.85")
            elif any(k in lbl for k in ["sat"]):
                inp.fill("1280")
            elif any(k in lbl for k in ["language", "coding language", "programming language"]):
                inp.fill("Python")
            elif any(k in lbl for k in ["salary", "compensation", "desired pay"]):
                inp.fill("Competitive")
            elif any(k in lbl for k in ["degree", "major"]):
                inp.fill("Computer Science")
            elif any(k in lbl for k in ["school", "university", "college", "institution"]):
                inp.fill("Rutgers University")
            elif any(k in lbl for k in ["your name", "full name", "signature", "name *", "employee name"]):
                inp.fill(f"{CANDIDATE['first_name']} {CANDIDATE['last_name']}")
            elif any(k in lbl for k in ["today's date", "todays date", "signature date"]):
                inp.fill(f"{today.month:02d}/{today.day:02d}/{today.year}")
            elif any(k in lbl for k in ["first year"]):
                inp.fill("2020")
            elif any(k in lbl for k in ["last year"]):
                inp.fill("2024")
        except Exception:
            pass

    # 6b. Fix any fields flagged with aria-invalid="true" or error
    for inv in page.locator('[aria-invalid="true"], [data-automation-id*="error" i] input').all():
        try:
            lbl = inv.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, [role=\"group\"], div') || el.parentElement).innerText").lower()
            h = page.locator('h2').inner_text().lower() if page.locator('h2').count() > 0 else ''
            if any(k in lbl for k in ["linkedin"]):
                inv.fill(CANDIDATE.get("linkedin", ""))
            elif any(k in lbl for k in ["name", "signature"]) or ('disability' in h and 'name' in lbl):
                inv.fill(f"{CANDIDATE['first_name']} {CANDIDATE['last_name']}")
            elif any(k in lbl for k in ["today", "signature date", "enter today"]) or ('disability' in h and 'date' in lbl):
                inv.fill(f"{today.month:02d}/{today.day:02d}/{today.year}")
            elif any(k in lbl for k in ["job title", "title"]):
                inv.fill("Software Engineer")
            elif any(k in lbl for k in ["company", "employer"]):
                inv.fill("Rutgers University")
            elif any(k in lbl for k in ["date", "from", "start"]):
                inv.fill("05/2023")
            elif any(k in lbl for k in ["to", "end"]):
                inv.fill("05/2024")
        except Exception:
            pass

    # 7. Universal "Select One" Dropdowns
    buttons = page.locator('button:has-text("Select One")').all()
    for b in buttons:
        try:
            if not b.is_visible():
                continue
            pt = b.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, [role=\"group\"], div[id*=\"prompt\"]') || el.parentElement.parentElement).innerText").lower()
            target = "Yes"
            if any(k in pt for k in ["sponsorship", "require sponsorship", "visa"]):
                target = "No"
            elif any(k in pt for k in ["previous worker", "worked at", "employee, consultant", "previously employed", "former employee"]):
                target = "No"
            elif any(k in pt for k in ["relative", "family member", "conflict of interest"]):
                target = "No"
            elif any(k in pt for k in ["non-compete", "restrictive covenant", "agreement with current or former"]):
                target = "No"
            elif any(k in pt for k in ["crime", "felony", "convict"]):
                target = "No"
            elif any(k in pt for k in ["authorized to work", "legally authorized", "eligible to work", "right to work", "us citizen", "18 years", "at least 18", "background check", "drug", "consent"]):
                target = "Yes"
            elif any(k in pt for k in ["enrolled full-time", "currently enrolled", "degree program"]):
                target = "Yes"
            elif any(k in pt for k in ["12-week", "may-september", "full-time 12-week", "relocate"]):
                target = "Yes"
            elif any(k in pt for k in ["competing offer", "deadlines"]):
                target = "No"
            elif "gpa" in pt:
                target = "3.0 - 3.9"
            elif any(k in pt for k in ["hispanic", "latino"]):
                target = "No"
            elif any(k in pt for k in ["ethnicity", "race"]):
                target = "Asian"
            elif "gender" in pt:
                target = "Male"
            elif "veteran" in pt:
                target = "I am not a veteran"
            elif "how did you hear" in pt:
                target = "LinkedIn"

            b.click(force=True)
            time.sleep(1)
            
            match = None
            for opt in page.locator('[role="option"], [data-automation-id*="promptOption"], div[id*="listbox"] li').all():
                ot = opt.inner_text().strip()
                if not ot or "step" in ot.lower():
                    continue
                if target.lower() == ot.lower():
                    match = opt
                    break
                elif target.lower() in ot.lower():
                    if target == "Male" and "female" in ot.lower():
                        continue
                    match = opt
                    break
            if match:
                match.click(force=True)
                time.sleep(1.5)
            else:
                page.keyboard.press("Escape")
                time.sleep(0.5)
        except Exception:
            page.keyboard.press("Escape")

    # 8. Radios with value, label, and label[for=id] checks
    for radio in page.locator('input[type="radio"]').all():
        try:
            rid = radio.get_attribute("id") or ""
            r_name = (radio.get_attribute("name") or "").lower()
            val = (radio.get_attribute("value") or "").lower()
            lbl_elem = page.locator(f'label[for="{rid}"]').first if rid else None
            lt = (lbl_elem.inner_text().lower() if lbl_elem and lbl_elem.count() > 0 else "")
            pt = radio.evaluate('''el => {
                const p = el.closest('fieldset, [role="radiogroup"], [role="group"], div[data-automation-id*="formField"]') || el.parentElement.parentElement;
                return p ? p.innerText : '';
            }''').lower()

            should_click = False
            if "previousworker" in r_name or "priorworker" in r_name:
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["previous worker", "worked at", "employee, consultant", "previously employed", "former employee", "employed by", "in the past", "prior"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["relative", "family member", "conflict of interest"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["non-compete", "restrictive covenant"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["authorized to work", "legally authorized", "eligible to work", "right to work", "us citizen", "18 years", "at least 18", "background check", "drug", "consent"]):
                if "yes" in lt or val in ["true", "1"]:
                    should_click = True
            elif any(k in pt for k in ["enrolled full-time", "currently enrolled", "degree program", "student"]):
                if "yes" in lt or val in ["true", "1"]:
                    should_click = True
            elif any(k in pt for k in ["12-week", "may-september", "full-time 12-week", "relocate", "relocation"]):
                if "yes" in lt or val in ["true", "1"]:
                    should_click = True
            elif any(k in pt for k in ["competing offer", "deadlines"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["sponsorship", "require sponsorship", "visa"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif "veteran" in pt:
                if any(k in lt for k in ["not", "no"]) or val in ["false", "0", "2"]:
                    should_click = True
            elif "disability" in pt:
                if (any(k in lt for k in ["no, i do not", "no, i don", "no disability", "do not have a disability"]) and "wish to answer" not in lt) or val in ["false", "0", "2"]:
                    should_click = True
            elif "gender" in pt:
                if "male" in lt and "female" not in lt:
                    should_click = True
            elif any(k in pt for k in ["hispanic", "latino"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["ethnicity", "race"]):
                if "asian" in lt:
                    should_click = True

            if should_click and not radio.is_checked():
                clicked = False
                if rid:
                    le = page.locator(f'label[for="{rid}"]').first
                    if le.count() > 0:
                        le.click(force=True)
                        clicked = True
                if not clicked or not radio.is_checked():
                    radio.click(force=True)
                if not radio.is_checked():
                    radio.evaluate("el => el.click()")
        except Exception:
            pass

    # 9. Checkboxes (terms, consent, agreements, negative options)
    for c in page.locator('input[type="checkbox"], label:has-text("have not worked"), label:has-text("Never worked"), label:has-text("None of the above")').all():
        try:
            is_label = c.evaluate("e => e.tagName == 'LABEL'")
            txt = c.inner_text().lower() if is_label else c.evaluate("e => (e.closest('label') || e.parentElement).innerText").lower()
            if any(k in txt for k in ["have not worked", "never worked", "none of the above", "not worked for"]):
                c.click(force=True)
            elif not is_label and not c.is_checked():
                cid = c.get_attribute("id") or ""
                if cid:
                    lbl = page.locator(f'label[for="{cid}"]').first
                    if lbl.is_visible():
                        lbl.click(force=True)
                if not c.is_checked():
                    c.click(force=True)
        except Exception:
            pass
def apply_workday_job(browser, job):
    comp = job["company"].strip()
    role = job.get("role") or job.get("title", "Software Engineer")
    url = job["url"].strip()
    today = datetime.now()
    
    print(f"\n{'='*60}")
    print(f"[{comp}] Starting Workday Application: {role}")
    print(f"URL: {url}")

    page = browser.new_page(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 1200}
    )

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # 0. Dismiss Cookie banner if present
        c = page.locator('[data-automation-id="legalNoticeAcceptButton"], button:has-text("Accept Cookies"), button:has-text("Accept all")').first
        if c.is_visible(timeout=2000):
            c.click(force=True)

        # Check if already applied or expired/closed on page
        body_initial = page.locator("body").inner_text().lower()
        if "you've already applied" in body_initial or "already applied for this job" in body_initial:
            print("  ℹ️ Already applied according to page banner. Skipping.", flush=True)
            page.close()
            return False
        if any(k in body_initial for k in ["page you are looking for doesn't exist", "job is no longer available", "no longer accepting applications", "position has been closed"]):
            print("  ℹ️ Job posting is closed/expired. Skipping.", flush=True)
            page.close()
            return False

        # 1. Click Apply
        apply_btn = page.locator('a[data-automation-id="adventureButton"], [data-automation-id="applyButton"], a:has-text("Apply")').first
        if not apply_btn.is_visible(timeout=4000):
            print("  ℹ️ Apply button not found (inactive/closed). Skipping.", flush=True)
            page.close()
            return False
        apply_btn.click(force=True)
        page.wait_for_timeout(2000)

        # 2. Choose Autofill with Resume or Apply Manually
        autofill_btn = page.locator('[data-automation-id="autofillWithResume"], a:has-text("Autofill with Resume"), button:has-text("Autofill with Resume")').first
        manual_btn = page.locator('[data-automation-id="applyManually"], a:has-text("Apply Manually"), button:has-text("Apply Manually")').first

        if autofill_btn.is_visible(timeout=2500):
            autofill_btn.click(force=True)
        elif manual_btn.is_visible(timeout=2500):
            manual_btn.click(force=True)
        page.wait_for_timeout(3000)

        # 3. Handle Workday Auth
        auth_ok = handle_workday_auth(page, comp)
        if not auth_ok:
            print("  ⚠️ Authentication did not complete. Skipping.", flush=True)
            page.close()
            return False

        # 3b. Check if landed on Candidate Home (existing drafts)
        if "userhome" in page.url.lower() or "candidate home" in page.title().lower():
            print("  ℹ️ On Candidate Home. Checking for unsubmitted drafts...", flush=True)
            rows = page.locator('table tbody tr').all()
            draft_resumed = False
            for r in rows:
                rt = r.inner_text()
                if "Not Submitted" in rt:
                    menu_btn = r.locator('button[data-automation-id="actionMenuTarget"]').first
                    if menu_btn.is_visible():
                        menu_btn.click(force=True)
                        page.wait_for_timeout(1000)
                        cont = page.locator('[role="menuitem"]:has-text("Continue Application")').first
                        if cont.is_visible():
                            print("  📝 Resuming unsubmitted draft from Candidate Home...", flush=True)
                            cont.click(force=True)
                            page.wait_for_timeout(4000)
                            draft_resumed = True
                            nxt = page.locator('button[data-automation-id="pageFooterNextButton"]').first
                            if nxt.is_visible():
                                nxt.click(force=True)
                                page.wait_for_timeout(5000)
                            break
            if not draft_resumed:
                print("  ℹ️ No draft on Candidate Home. Navigating back to job posting...", flush=True)
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
                apply_btn = page.locator('a[data-automation-id="adventureButton"], [data-automation-id="applyButton"], a:has-text("Apply")').first
                if apply_btn.is_visible(timeout=4000):
                    apply_btn.click(force=True)
                    page.wait_for_timeout(2000)
                man_btn = page.locator('[data-automation-id="applyManually"], a:has-text("Apply Manually"), button:has-text("Apply Manually"), [data-automation-id="autofillWithResume"], a:has-text("Autofill with Resume")').first
                if man_btn.is_visible(timeout=2500):
                    man_btn.click(force=True)
                    page.wait_for_timeout(3000)

        # 4. Multi-step application loop
        last_sec = ""
        same_sec_retries = 0

        for step_idx in range(1, 25):
            wait_for_workday_spinner(page, timeout_sec=8)
            headings = page.locator("h1, h2, h3").all_inner_texts()
            current_sec = ""
            for h in reversed(headings):
                if h and comp.lower() not in h.lower() and "error" not in h.lower():
                    current_sec = h
                    break
            print(f"  📍 Step {step_idx}: {current_sec}", flush=True)

            if current_sec and current_sec == last_sec:
                same_sec_retries += 1
                for alert in page.locator('[data-automation-id*="error" i], [role="alert"], [data-automation-id*="validation" i], [aria-invalid="true"]').all():
                    try:
                        if alert.is_visible():
                            print(f"  ❌ VISIBLE ERROR ON {current_sec}: {alert.inner_text().strip().replace(chr(10), ' ')}", flush=True)
                    except Exception:
                        pass
                if same_sec_retries >= 6:
                    print(f"  ⚠️ Section '{current_sec}' blocked by unfillable custom tenant fields after {same_sec_retries} attempts. Skipping to next job.", flush=True)
                    page.close()
                    return False
            else:
                same_sec_retries = 0
                last_sec = current_sec

            # Check for Review / Submit in footer FIRST
            sub_btn = page.locator('button[data-automation-id="bottom-navigation-next-button"]:has-text("Submit"), button[data-automation-id="pageFooterNextButton"]:has-text("Submit"), [data-automation-id="pageFooter"] button:has-text("Submit"), button:has-text("Submit")').first
            if sub_btn.is_visible():
                print("  🚀 Review Step Reached! Clicking Submit...", flush=True)
                sub_btn.click(force=True)
                page.wait_for_timeout(8000)

                conf_text = page.locator("body").inner_text().lower()
                if any(w in conf_text for w in ["thank you for applying", "thank you", "application submitted", "congratulations", "your application has been received", "return to home", "you have no more tasks"]):
                    print(f"  🎉 SUBMISSION CONFIRMED for {comp} - {role}!")
                    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", f"{comp}_{role}".lower())[:60]
                    screenshot_path = os.path.join(CONFIRMATIONS_DIR, f"workday_{safe_name}_submitted.png")
                    page.screenshot(path=screenshot_path)
                    print(f"  📸 Screenshot saved: {screenshot_path}", flush=True)

                    # Auto-log to Google Sheet
                    cmd = [
                        sys.executable,
                        LOG_SCRIPT,
                        "--company", comp,
                        "--role", role,
                        "--link", url,
                        "--status", "Applied",
                        "--notes", "Workday autonomous confirmation screenshot saved"
                    ]
                    subprocess.run(cmd, check=False)
                    page.close()
                    return True

            # Resume upload if file input or dropzone exists in DOM
            file_inps = page.locator('input[type="file"], input[data-automation-id="file-upload-input-ref"]')
            body_sub = page.locator("body").inner_text().lower()
            needs_upload = any(k in current_sec.lower() for k in ["autofill", "resume", "upload", "experience"]) or "upload your resume" in body_sub or "resume/cv" in body_sub or "upload a file" in body_sub
            dz_elem = page.locator('div:has-text("Drop files here"), [data-automation-id*="dropZone" i]').first
            dz_visible = dz_elem.is_visible() if dz_elem.count() > 0 else False

            if needs_upload and (dz_visible or file_inps.count() > 0):
                pdf_path = get_fast_tailored_resume(comp, role)
                select_btn = page.locator('button:has-text("Select files"), a:has-text("Select files"), [data-automation-id*="upload" i]:has-text("Select"), [data-automation-id="uploadFileButton"]').first
                if select_btn.is_visible():
                    try:
                        print(f"  📄 Attaching tailored resume via file chooser: {pdf_path}", flush=True)
                        with page.expect_file_chooser(timeout=3000) as fc_info:
                            select_btn.click(force=True)
                        fc_info.value.set_files(pdf_path)
                        page.wait_for_timeout(4000)
                    except Exception:
                        pass
                for finp in file_inps.all():
                    try:
                        finp.set_input_files(pdf_path)
                        page.wait_for_timeout(2000)
                    except Exception:
                        pass

            # Fill all fields on this step
            fill_all_workday_section_fields(page, today)

            # Click Save and Continue / Next in page footer
            next_btn = page.locator('button[data-automation-id="bottom-navigation-next-button"], button[data-automation-id="pageFooterNextButton"], [data-automation-id="pageFooter"] button:has-text("Save and Continue"), [data-automation-id="pageFooter"] button:has-text("Continue"), [data-automation-id="pageFooter"] button:has-text("Next"), button:has-text("Save and Continue"), button:has-text("Next")').first
            if next_btn.is_visible():
                next_btn.click(force=True)
                page.wait_for_timeout(6000)
            else:
                break

    except Exception as e:
        print(f"  ⚠️ Exception during application for {comp}: {e}", flush=True)
    finally:
        try:
            page.close()
        except Exception:
            pass

    return False

def run_workday_batch(limit=189):
    applied_urls, applied_pairs, applied_reqs = load_applied()
    queue_path = Path("application_engine/queue_workday.json")
    with open(queue_path) as f:
        jobs = json.load(f)

    unapplied = []
    for j in jobs:
        # Skip PhD-only roles
        if 'phd' in j.get('role', '').lower() or 'phd' in j.get('title', '').lower() or 'phd' in j['url'].lower():
            continue
        c = j["company"].strip().lower()
        r = (j.get("role") or j.get("title", "")).strip().lower()
        u = normalize_url(j["url"])
        m = re.search(r'([A-Z]{1,3}-?\d{4,}|\b\d{5,}\b)', j['url'])
        req = m.group(1).replace('-', '') if m else None

        if u in applied_urls or f"{c}:::{r}" in applied_pairs:
            continue
        if req and req in applied_reqs:
            continue
        unapplied.append(j)

    print(f"Loaded {len(unapplied)} unapplied Workday jobs. Processing up to {limit} without stopping...", flush=True)

    success = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        for idx, j in enumerate(unapplied[:limit]):
            print(f"\n>>> [{idx+1}/{min(limit, len(unapplied))}] Launching {j['company']} - {j.get('role', j.get('title', ''))}...")
            res = apply_workday_job(browser, j)
            if res:
                success += 1
            time.sleep(2)

        browser.close()

    print(f"\n🏁 Workday batch complete! Confirmed {success} new submissions.")

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 189
    run_workday_batch(limit=limit)
