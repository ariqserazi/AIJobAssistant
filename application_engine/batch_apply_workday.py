#!/usr/bin/env python3
"""
batch_apply_workday.py - Autonomous Workday External Portal Application Engine
Specifically tailored for early-career SWE and university internship positions.
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
from ai_form_solver import solve_field_with_ai

LOG_SCRIPT = os.path.expanduser("~/.agents/skills/resume-tailor-swe/scripts/log_application.py")
CONFIRMATIONS_DIR = os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/confirmations")
os.makedirs(CONFIRMATIONS_DIR, exist_ok=True)

def bring_window_to_front(app_name="Google Chrome"):
    """Brings Chrome to the foreground so the user sees it and clicks land natively."""
    script = f'''
    tell application "System Events"
        set processList to (name of every process)
        if "{app_name}" is in processList then
            tell application "{app_name}" to activate
        else if "Google Chrome" is in processList then
            tell application "Google Chrome" to activate
        else if "Chromium" is in processList then
            tell application "Chromium" to activate
        end if
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.4)
    except Exception:
        pass

try:
    from config_loader import get_candidate_dict, load_config
except ImportError:
    try:
        from application_engine.config_loader import get_candidate_dict, load_config
    except ImportError:
        def get_candidate_dict(): return {}
        def load_config(): return {}

_cfg = load_config()
_c = get_candidate_dict()

CANDIDATE = {
    "first_name": _c.get("first_name", "Ariq"),
    "last_name": _c.get("last_name", "Serazi"),
    "email": _c.get("email") or _c.get("candidate_email") or os.getenv("CANDIDATE_EMAIL", "ariq.serazi1@gmail.com"),
    "password": _c.get("workday_password") or os.getenv("WORKDAY_PASSWORD", "AriqWorkday2026!#"),
    "phone": _c.get("phone", "732-853-6773"),
    "address": _c.get("address", "123 Main St"),
    "city": _c.get("city", "Piscataway"),
    "state": _c.get("state", "New Jersey"),
    "zip": _c.get("postal_code") or _c.get("zip_code", "08854"),
    "country": _c.get("country", "United States of America"),
    "linkedin": _c.get("linkedin") or _c.get("linkedin_url", "https://www.linkedin.com/in/ariq-serazi/"),
    "github": _c.get("github") or _c.get("github_url", "https://github.com/ariqserazi"),
    "school": _c.get("school") or _c.get("school_name", "Rutgers University"),
    "degree": _c.get("degree", "Bachelor of Science in Computer Science"),
    "degree_ms": _c.get("degree_ms", "Master of Science in Computer Science"),
    "field": _c.get("discipline", "Computer Science"),
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
    keyfile = os.path.expanduser("~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json")
    try:
        gc = gspread.service_account(keyfile)
        sh = gc.open_by_key("1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY")
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
                    val = m.group(1).replace('-', '')
                    if not any(bad in val.lower() for bad in ["xml", "2026", "2027", "2028"]):
                        applied_reqs.add(val)
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
    """Checks if the user has navigated past login/registration into the application form."""
    try:
        # Negative signals: only return False if password input or auth submit buttons are actually VISIBLE
        pw_loc = page.locator('input[data-automation-id="password"], input[type="password"]')
        if pw_loc.count() > 0:
            for i in range(pw_loc.count()):
                try:
                    if pw_loc.nth(i).is_visible():
                        return False
                except Exception:
                    pass

        auth_btn_selectors = [
            'button[data-automation-id="signInSubmitButton"]',
            '[data-automation-id="signInSubmitButton"]',
            'button[data-automation-id="createAccountSubmitButton"]',
            '[data-automation-id="createAccountSubmitButton"]',
            '[data-automation-id="SignInWithEmailButton"]'
        ]
        for sel in auth_btn_selectors:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                return False

        body = page.locator("body").inner_text().lower()
        # If still on explicit login screen
        if ("create account/sign in" in body or "sign in to your account" in body or "step 1: sign in" in body) and ("email address*" in body or "password*" in body):
            return False

        # Positive signals: form steps, footer navigation, progress bar, or candidate home
        if page.locator('button[data-automation-id="bottom-navigation-next-button"], button[data-automation-id="pageFooterNextButton"], [data-automation-id="pageFooter"] button').count() > 0:
            return True
        if page.locator('[data-automation-id="progressBar"]').count() > 0:
            return True
        if any(k in body for k in ["my information", "my experience", "application questions", "voluntary disclosures", "review and submit", "autofill with resume"]):
            return True
        if "candidate home" in body:
            return True
    except Exception:
        pass
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

    # Dismiss cookie banner if present
    cookie_btn = page.locator('button:has-text("Accept Cookies"), button:has-text("Accept All"), button[data-automation-id="legalNoticeAcceptButton"]').first
    if cookie_btn.is_visible(timeout=2000):
        try:
            cookie_btn.click(force=True)
            time.sleep(1)
        except Exception:
            pass

    for attempt in range(5):
        if is_authenticated(page):
            print("  ✅ Authenticated into application flow.", flush=True)
            return True

        body_text = page.locator("body").inner_text().lower()

        # Check for unverified account lock
        if any(k in body_text for k in ["verify your account before you sign in", "account might be locked"]):
            print("  ⚠️ Workday tenant requires email verification link or is locked. Skipping.", flush=True)
            return False

        # Check for email verification OTP prompt
        if any(k in body_text for k in ["verification code", "security code", "one-time passcode", "enter code"]):
            print(f"  🔔 Workday OTP requested for {company_name}! Fetching from Gmail...", flush=True)
            code = get_latest_verification_code(company=company_name, max_wait_sec=90)
            if code:
                code_inp = page.locator('input[data-automation-id*="code"], input[aria-label*="code" i], input[id*="code" i]').first
                if code_inp.is_visible():
                    code_inp.fill(code)
                    time.sleep(1)
                    page.locator('button:has-text("Verify"), button:has-text("Submit"), button:has-text("Continue")').first.click(force=True)
                    time.sleep(5)
            if is_authenticated(page):
                print("  ✅ Workday authentication successful.", flush=True)
                return True

        # Check if error indicates account already exists
        if any(k in body_text for k in ["already exists", "account with this email already exists", "an account with this email address already exists"]):
            print("  ℹ️ Account already exists on this tenant. Switching to Sign In...", flush=True)
            signin_link = page.locator('[data-automation-id="signInLink"], button[data-automation-id="signInLink"], button:has-text("Sign In"), a:has-text("Sign In")').first
            if signin_link.is_visible(timeout=2000):
                signin_link.click(force=True)
                time.sleep(3)
                continue

        # Check if error indicates account does not exist / invalid credentials
        if any(k in body_text for k in ["wrong email address or password", "cannot find your account", "invalid user name", "invalid user name or password"]):
            print("  ℹ️ Account does not exist on this tenant. Switching to Create Account...", flush=True)
            create_link = page.locator('[data-automation-id="createAccountLink"], button[data-automation-id="createAccountLink"], button:has-text("Create Account"), a:has-text("Create Account")').first
            if create_link.is_visible(timeout=2000):
                create_link.click(force=True)
                time.sleep(3)
                continue

        email_inp = page.locator('input[data-automation-id="email"]').first
        pw_inp = page.locator('input[data-automation-id="password"]').first
        vpw_inp = page.locator('input[data-automation-id="verifyPassword"]').first

        if vpw_inp.count() > 0 and (vpw_inp.is_visible() or vpw_inp.evaluate("e => e.offsetParent !== null")):
            # Create Account mode
            print("  📝 In Create Account mode. Filling credentials...", flush=True)
            if email_inp.count() > 0:
                try:
                    email_inp.scroll_into_view_if_needed()
                    email_inp.fill(CANDIDATE["email"])
                    email_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
                except Exception:
                    pass
            if pw_inp.count() > 0:
                try:
                    pw_inp.scroll_into_view_if_needed()
                    pw_inp.fill(CANDIDATE["password"])
                    pw_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
                except Exception:
                    pass
            try:
                vpw_inp.scroll_into_view_if_needed()
                vpw_inp.fill(CANDIDATE["password"])
                vpw_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
            except Exception:
                pass
            chk = page.locator('input[data-automation-id="createAccountCheckbox"], [data-automation-id="createAccountCheckbox"]').first
            if chk.count() > 0:
                try:
                    chk.check(force=True)
                except Exception:
                    try:
                        chk.click(force=True)
                    except Exception:
                        chk.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('change', {bubbles: true})); }")
            # Click click_filter overlay if present
            filter_div = page.locator('[data-automation-id="click_filter"]').first
            if filter_div.count() > 0 and filter_div.is_visible():
                try:
                    filter_div.click()
                except Exception:
                    pass
            create_btn = page.locator('button[data-automation-id="createAccountSubmitButton"], [data-automation-id="createAccountSubmitButton"], button:has-text("Create Account")').first
            if create_btn.count() > 0:
                try:
                    create_btn.click(force=True)
                except Exception:
                    create_btn.evaluate("el => { el.click(); if (el.parentElement) el.parentElement.click(); }")
            try:
                vpw_inp.press("Enter")
            except Exception:
                pass
            for _ in range(12):
                time.sleep(1)
                if is_authenticated(page):
                    print("  ✅ Workday authentication successful.", flush=True)
                    return True
                body_t = page.locator("body").inner_text().lower()
                if any(k in body_t for k in ["already exists", "account with this email already exists"]):
                    break
        else:
            # Sign In mode
            print("  🔐 Submitting Sign In...", flush=True)
            if email_inp.count() > 0:
                try:
                    email_inp.scroll_into_view_if_needed()
                    email_inp.fill(CANDIDATE["email"])
                    email_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
                except Exception:
                    pass
            if pw_inp.count() > 0:
                try:
                    pw_inp.scroll_into_view_if_needed()
                    pw_inp.fill(CANDIDATE["password"])
                    pw_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
                except Exception:
                    pass
            # Click click_filter overlay if present
            filter_div = page.locator('[data-automation-id="click_filter"]').first
            if filter_div.count() > 0 and filter_div.is_visible():
                try:
                    filter_div.click()
                except Exception:
                    pass
            signin_btn = page.locator('button[data-automation-id="signInSubmitButton"], [data-automation-id="signInSubmitButton"]').first
            if signin_btn.count() > 0:
                try:
                    signin_btn.click(force=True)
                except Exception:
                    signin_btn.evaluate("el => { el.click(); if (el.parentElement) el.parentElement.click(); }")
            try:
                pw_inp.press("Enter")
            except Exception:
                pass
            for _ in range(12):
                time.sleep(1)
                if is_authenticated(page):
                    print("  ✅ Workday authentication successful.", flush=True)
                    return True
                body_t = page.locator("body").inner_text().lower()
                if any(k in body_t for k in ["verification code", "security code", "one-time passcode", "enter code", "already exists", "verify your account", "invalid user name", "wrong email"]):
                    break

        if is_authenticated(page):
            print("  ✅ Workday authentication successful.", flush=True)
            return True

    return is_authenticated(page)

def fill_all_workday_section_fields(page, today, comp="", role=""):
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
    if postal.is_visible():
        current_zip = postal.input_value().strip()
        if not current_zip or current_zip == "10001":
            postal.fill("08854")
            try:
                postal.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
            except Exception:
                pass

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
    pt_btns = page.locator(
        'button[id*="phoneType" i], button[name*="phoneType" i], '
        'button[aria-label*="Phone Device Type" i], button[aria-label*="Device Type" i], '
        'div:has(label:has-text("Phone Device Type")) button, '
        'div:has(label:has-text("Phone Device Type")) [data-automation-id="select-widget"], '
        'div:has(label:has-text("Phone Device Type")) div[role="button"], '
        'div:has(label:has-text("Device Type")) button, '
        'div:has(label:has-text("Device Type")) [data-automation-id="select-widget"], '
        'div[data-automation-id*="phoneDeviceType" i] button, '
        'div[data-automation-id*="phoneDeviceType" i] [data-automation-id="select-widget"]'
    ).all()
    for pt in pt_btns:
        try:
            if pt.is_visible():
                txt = ((pt.get_attribute("aria-label") or "") + " " + pt.inner_text()).lower()
                if "select one" in txt or not pt.inner_text().strip():
                    pt.scroll_into_view_if_needed(timeout=2000)
                    pt.click(force=True)
                    time.sleep(1.2)
                    mob = page.locator(
                        '[role="option"]:has-text("Mobile"), [data-automation-id*="promptOption"]:has-text("Mobile"), '
                        'li:has-text("Mobile"), [role="option"]:has-text("Cell"), [role="option"]:has-text("Home")'
                    ).first
                    if mob.is_visible(timeout=2000):
                        mob.click(force=True)
                        time.sleep(1)
                    else:
                        page.keyboard.press("Escape")
        except Exception:
            pass

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

    src_btns = page.locator(
        'button[id*="source" i], button[name*="source" i], button[aria-label*="Hear" i], '
        'button[aria-label*="Source" i], div:has(label:has-text("Hear About")) button, '
        'div:has(label:has-text("Hear About")) [data-automation-id="select-widget"], '
        'div:has(label:has-text("Hear About")) div[role="button"], '
        'div:has(label:has-text("Source")) button, div:has(label:has-text("Source")) [data-automation-id="select-widget"], '
        'div[data-automation-id*="source" i] button, div[data-automation-id*="source" i] [data-automation-id="select-widget"], '
        'div[data-automation-id*="source" i] div[role="button"]'
    ).all()
    for s_btn in src_btns:
        try:
            if s_btn.is_visible():
                btn_txt = ((s_btn.get_attribute("aria-label") or "") + " " + s_btn.inner_text()).lower()
                if "select one" in btn_txt or not s_btn.inner_text().strip():
                    s_btn.scroll_into_view_if_needed(timeout=2000)
                    s_btn.click(force=True)
                    time.sleep(1.2)
                    opt = page.locator(
                        '[role="option"]:has-text("LinkedIn"), '
                        'li:has-text("LinkedIn"), '
                        '[data-automation-id*="promptOption"]:has-text("LinkedIn"), '
                        '[role="option"]:has-text("Job Board"), '
                        'li:has-text("Job Board"), '
                        '[role="option"]:has-text("Career Site"), '
                        '[role="option"]:has-text("Internet"), '
                        '[role="option"]:has-text("Website"), '
                        '[role="option"]:has-text("Online"), '
                        '[role="option"]:has-text("Other"), '
                        'li:has-text("Other")'
                    ).first
                    if opt.is_visible(timeout=2500):
                        print(f"    ✅ Selected source: '{opt.inner_text().strip()}'", flush=True)
                        opt.click(force=True)
                        time.sleep(0.8)
                        # If subcategory opened (e.g. Job Board -> LinkedIn)
                        sub_opt = page.locator(
                            '[role="option"]:has-text("LinkedIn"), '
                            'li:has-text("LinkedIn"), '
                            '[data-automation-id*="promptOption"]:has-text("LinkedIn"), '
                            '[role="option"]:has-text("Indeed"), '
                            'li:has-text("Indeed"), '
                            '[role="option"]:has-text("Glassdoor"), '
                            '[role="option"]:has-text("Online")'
                        ).first
                        if sub_opt.is_visible(timeout=1000):
                            sub_opt.click(force=True)
                            time.sleep(0.5)
                    else:
                        page.keyboard.press("Escape")
        except Exception:
            pass

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

    deg_btn = page.locator('button[id*="degree" i], button[aria-label*="Degree " i], button[data-automation-id*="degree" i]').first
    if deg_btn.is_visible() and ("Select One" in (deg_btn.get_attribute("aria-label") or "") or "Select One" in deg_btn.inner_text() or "Prompt" in (deg_btn.get_attribute("aria-label") or "")):
        deg_btn.click(force=True)
        time.sleep(1.2)
        deg_opt = page.locator('[role="option"]:has-text("Bachelor"), [data-automation-id*="promptOption"]:has-text("Bachelor"), [data-automation-id*="select-options"] li:has-text("Bachelor"), li:has-text("Bachelor")').first
        if not deg_opt.is_visible():
            deg_opt = page.locator('[role="option"]:has-text("BS"), [role="option"]:has-text("Undergraduate"), [role="option"]:has-text("Master"), [role="option"]:has-text("MS")').first
        if not deg_opt.is_visible():
            deg_opt = page.locator('[data-automation-id*="promptOption"], [role="option"]').first
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

    # Generic Text & Textarea inputs in Application Questions / custom sections
    for inp in page.locator('input[type="text"]:not([id*="date" i]):not([id*="Month" i]):not([id*="Day" i]):not([id*="Year" i]), textarea').all():
        try:
            if not inp.is_visible():
                continue
            cur_val = inp.input_value().strip()
            if cur_val and cur_val != "Select One":
                continue
            
            lbl = inp.evaluate('''el => {
                let cur = el;
                for (let i = 0; i < 4 && cur; i++) {
                    cur = cur.parentElement;
                    if (cur) {
                        const da = cur.getAttribute('data-automation-id') || '';
                        if (da.includes('formField') || cur.tagName === 'FIELDSET' || cur.getAttribute('role') === 'group') {
                            return cur.innerText;
                        }
                    }
                }
                return (el.closest('[data-automation-id*="formField"], fieldset, [role="group"]') || el.parentElement).innerText;
            }''').lower()

            auto_id = (inp.get_attribute("data-automation-id") or "").lower()
            elem_id = (inp.get_attribute("id") or "").lower()

            if any(k in lbl or k in auto_id or k in elem_id for k in ["university", "college", "school"]):
                inp.fill("Rutgers University")
            elif any(k in lbl or k in auto_id or k in elem_id for k in ["gpa", "grade average", "cumulative gpa"]):
                inp.fill("3.85")
            elif any(k in lbl or k in auto_id or k in elem_id for k in ["major", "field of study", "degree program"]):
                inp.fill("Computer Science")
            elif any(k in lbl or k in auto_id or k in elem_id for k in ["degree"]):
                inp.fill("Bachelor of Science")
            elif any(k in lbl or k in auto_id or k in elem_id for k in ["linkedin"]):
                inp.fill(CANDIDATE.get("linkedin", ""))
            elif any(k in lbl or k in auto_id or k in elem_id for k in ["github"]):
                inp.fill(CANDIDATE.get("github", ""))
            elif any(k in lbl or k in auto_id or k in elem_id for k in ["website", "portfolio"]):
                inp.fill(CANDIDATE.get("github", ""))
            elif any(k in lbl or k in auto_id or k in elem_id for k in ["facebook", "twitter", "x.com", "instagram", "tiktok"]):
                inp.fill("")
            elif any(k in lbl or k in auto_id or k in elem_id for k in ["salary", "compensation", "desired pay"]):
                inp.fill("80000")
            elif any(k in lbl or k in auto_id or k in elem_id for k in ["why", "excite", "interest", "tell us", "describe", "about yourself", "project", "experience"]):
                inp.fill("I am excited to apply my background in computer science, distributed systems, and software engineering to build impactful solutions and contribute effectively to the team.")
            elif any(k in lbl or k in auto_id or k in elem_id for k in ["signature", "sign"]):
                inp.fill(f"{CANDIDATE.get('first_name', '')} {CANDIDATE.get('last_name', '')}".strip())
            else:
                ai_val = solve_field_with_ai(lbl, "text", company=comp, role=role)
                if ai_val:
                    clean_val = re.sub(r'[-–—]', ' ', ai_val).strip()
                    inp.fill(clean_val)
                    print(f"      🤖 [Qwen AI] Filled text for '{lbl[:35]}'", flush=True)
            
            inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass

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
    # 3. Date pickers (Month, Day, Year inputs)
    for m_inp in page.locator('input[id*="dateSectionMonth-input" i], input[id*="Month-input" i]').all():
        try:
            if m_inp.is_visible():
                lbl = m_inp.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, div') || el.parentElement).innerText").lower()
                h2_t = page.locator('h2, [data-automation-id="pageHeaderTitle"]').inner_text().lower() if page.locator('h2, [data-automation-id="pageHeaderTitle"]').count() > 0 else ''
                if any(k in h2_t for k in ["disability", "self-identification", "eeo", "disclosure"]) or any(k in lbl for k in ["today", "signature", "disability", "date"]):
                    m_val = f"{today.month:02d}"
                elif any(k in lbl for k in ["graduat", "expected", "degree"]):
                    m_val = "05"
                else:
                    m_val = f"{today.month:02d}"
                if m_inp.input_value().strip() == m_val:
                    continue
                m_inp.fill(m_val)
                m_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass

    for d_inp in page.locator('input[id*="dateSectionDay-input" i], input[id*="Day-input" i]').all():
        try:
            if d_inp.is_visible():
                d_val = f"{today.day:02d}"
                if d_inp.input_value().strip() == d_val:
                    continue
                d_inp.fill(d_val)
                d_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass

    for y_inp in page.locator('input[id*="dateSectionYear-input" i], input[id*="Year-input" i]').all():
        try:
            if y_inp.is_visible():
                lbl = y_inp.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, div') || el.parentElement).innerText").lower()
                h2_t = page.locator('h2, [data-automation-id="pageHeaderTitle"]').inner_text().lower() if page.locator('h2, [data-automation-id="pageHeaderTitle"]').count() > 0 else ''
                if any(k in h2_t for k in ["disability", "self-identification", "eeo", "disclosure"]) or any(k in lbl for k in ["today", "signature", "disability", "date"]):
                    y_val = f"{today.year}"
                elif any(k in lbl for k in ["graduat", "expected", "degree", "end", "completion"]):
                    y_val = "2028"
                elif any(k in lbl for k in ["work", "job", "from", "experience"]):
                    y_val = "2023"
                else:
                    y_val = f"{today.year}"
                if y_inp.input_value().strip() == y_val:
                    continue
                y_inp.fill(y_val)
                y_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass

    # 4. Self Identify (Disability signature & Date)
    today_str = f"{today.month:02d}/{today.day:02d}/{today.year}"
    for n_inp in page.locator('input[id*="name" i], input[data-automation-id*="name" i], input[aria-label*="name" i]').all():
        try:
            inp_id = (n_inp.get_attribute("id") or "").lower()
            if any(x in inp_id for x in ["datesection", "month", "day", "year"]):
                continue
            if n_inp.is_visible() and not n_inp.input_value().strip():
                n_inp.fill(f"{CANDIDATE.get('first_name', '')} {CANDIDATE.get('last_name', '')}".strip())
                n_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass

    for d_inp in page.locator('input[id*="date" i], input[data-automation-id*="date" i], input[aria-label*="date" i], input[placeholder*="YYYY" i], input[placeholder*="yyyy" i]').all():
        try:
            if d_inp.is_visible():
                inp_id = (d_inp.get_attribute("id") or "").lower()
                auto_id = (d_inp.get_attribute("data-automation-id") or "").lower()
                if any(x in inp_id or x in auto_id for x in ["datesection", "month", "day", "year", "dateinput", "datewidget"]):
                    continue
                lbl = d_inp.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, div') || el.parentElement).innerText").lower()
                h2_t = page.locator('h2, [data-automation-id="pageHeaderTitle"]').inner_text().lower() if page.locator('h2, [data-automation-id="pageHeaderTitle"]').count() > 0 else ''
                if any(k in h2_t for k in ["disability", "self-identification", "eeo", "disclosure"]) or any(k in lbl for k in ["today", "date", "signature", "disability"]):
                    if d_inp.input_value().strip() == today_str:
                        continue
                    d_inp.fill(today_str)
                    d_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass

    # 4b. Explicit CC-305 Disability Selection ("No, I do not have a disability")
    try:
        clicked_disability = page.evaluate('''() => {
            const all = Array.from(document.querySelectorAll('label, div, span, p, input'));
            const target = all.find(el => {
                const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                return (t.includes('no, i do not have a disability') || t.includes('have not had one in the past')) && !t.includes('yes, i have') && !t.includes('want to answer');
            });
            if (target) {
                target.scrollIntoView({behavior: 'instant', block: 'center'});
                const inp = target.querySelector('input') || target.closest('label')?.querySelector('input') || target.parentElement?.querySelector('input');
                if (inp) {
                    inp.click();
                    inp.checked = true;
                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                }
                target.click();
                return true;
            }
            return false;
        }''')
        if clicked_disability:
            print("      ✅ Selected CC-305 Disability: 'No, I do not have a disability'", flush=True)
            time.sleep(0.5)
    except Exception as e:
        print(f"      ⚠️ CC-305 JS click error: {e}", flush=True)

    # First: Direct label click by text
    for no_lbl in page.locator(
        'label:has-text("No, I do not have a disability"), '
        'label:has-text("No, I don\'t have a disability"), '
        'label:has-text("have not had one in the past"), '
        'div[data-automation-id*="radio"]:has-text("No, I do not have a disability")'
    ).all():
        try:
            no_lbl.scroll_into_view_if_needed(timeout=2000)
            no_lbl.click(force=True, timeout=2000)
            time.sleep(0.3)
        except Exception:
            pass

    # Second: Inspect individual radio containers (scoped to parentElement to avoid matching entire group)
    for chk in page.locator('input[type="radio"], input[type="checkbox"]').all():
        try:
            rid = chk.get_attribute("id") or ""
            lbl_elem = page.locator(f'label[for="{rid}"]').first if rid else None
            lt = (lbl_elem.inner_text().lower() if lbl_elem and lbl_elem.count() > 0 else "")
            if not lt:
                lt = chk.evaluate("el => (el.closest('label') || el.parentElement).innerText").lower()
            if any(k in lt for k in ["no, i do not have a disability", "no, i don't have a disability", "have not had one in the past"]) or ("no" in lt and "disabilit" in lt and "yes" not in lt):
                chk.scroll_into_view_if_needed(timeout=2000)
                if not chk.is_checked():
                    if lbl_elem and lbl_elem.is_visible():
                        lbl_elem.click(force=True, timeout=2000)
                    else:
                        chk.click(force=True, timeout=2000)
                    if not chk.is_checked():
                        chk.evaluate("el => el.click()")
                    time.sleep(0.3)
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
                ta.fill("None")
        except Exception:
            pass

    # 6. General required text inputs if empty (strictly zero dashes)
    for inp in page.locator('input[type="text"]:not([readonly]), input:not([type]):not([readonly])').all():
        try:
            if not inp.is_visible() or inp.input_value().strip():
                continue
            inp_id = (inp.get_attribute("id") or "").lower()
            if any(x in inp_id for x in ["datesection", "month-input", "day-input", "year-input"]):
                continue
            lbl = inp.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, [role=\"group\"], div') || el.parentElement).innerText").lower()
            ph = (inp.get_attribute("placeholder") or "").lower()
            if any(k in lbl for k in ["linkedin"]):
                inp.fill(CANDIDATE["linkedin"])
            elif any(k in lbl for k in ["github"]):
                inp.fill(CANDIDATE["github"])
            elif any(k in lbl for k in ["website", "portfolio"]):
                inp.fill(CANDIDATE.get("github", ""))
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
            elif any(k in lbl for k in ["salary", "compensation", "desired pay", "pay expectation", "base salary"]):
                inp.fill("80000")
            elif any(k in lbl for k in ["degree", "major"]):
                inp.fill("Computer Science")
            elif any(k in lbl for k in ["school", "university", "college", "institution"]):
                inp.fill("Rutgers University")
            elif any(k in lbl for k in ["your name", "full name", "signature", "name *", "employee name"]):
                inp.fill(f"{CANDIDATE.get('first_name', '')} {CANDIDATE.get('last_name', '')}".strip())
            elif any(k in lbl for k in ["today's date", "todays date", "signature date"]):
                inp.fill(f"{today.month:02d}/{today.day:02d}/{today.year}")
            elif any(k in lbl for k in ["first year"]):
                inp.fill("2020")
            elif any(k in lbl for k in ["last year"]):
                inp.fill("2024")
            elif any(k in lbl for k in ["if so", "detail", "position", "date", "interviewer", "explain", "describe", "notes", "clarif"]):
                inp.fill("None")
            elif "required" in lbl or inp.get_attribute("aria-required") == "true" or inp.get_attribute("required"):
                inp.fill("None")
            inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass

    # 6b. Number inputs if empty
    for num_inp in page.locator('input[type="number"]:not([readonly])').all():
        try:
            if not num_inp.is_visible() or num_inp.input_value().strip():
                continue
            lbl = num_inp.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, [role=\"group\"], div') || el.parentElement).innerText").lower()
            if "gpa" in lbl:
                num_inp.fill("3.85")
            elif "sat" in lbl:
                num_inp.fill("1280")
            elif any(k in lbl for k in ["salary", "pay", "rate", "compensation", "base"]):
                num_inp.fill("35")
            elif "year" in lbl:
                num_inp.fill("2024")
            else:
                num_inp.fill("0")
            num_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass

    # 6c. Fix any fields flagged with aria-invalid="true" or error
    for inv in page.locator('[aria-invalid="true"], [data-automation-id*="error" i] input').all():
        try:
            inp_id = (inv.get_attribute("id") or "").lower()
            if any(x in inp_id for x in ["datesection", "month-input", "day-input", "year-input"]):
                continue
            lbl = inv.evaluate("el => (el.closest('[data-automation-id*=\"formField\"], fieldset, [role=\"group\"], div') || el.parentElement).innerText").lower()
            h = page.locator('h2').inner_text().lower() if page.locator('h2').count() > 0 else ''
            if any(k in lbl for k in ["facebook", "twitter", "x.com", "instagram", "tiktok", "social"]):
                inv.fill("")
            elif any(k in lbl for k in ["linkedin"]):
                inv.fill(CANDIDATE.get("linkedin", ""))
            elif any(k in lbl for k in ["website", "portfolio", "url"]):
                inv.fill(CANDIDATE.get("github", ""))
            elif any(k in lbl for k in ["name", "signature"]) or ('disability' in h and 'name' in lbl):
                inv.fill(f"{CANDIDATE.get('first_name', '')} {CANDIDATE.get('last_name', '')}".strip())
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
            elif any(k in lbl for k in ["salary", "pay", "rate", "compensation", "base"]):
                inv.fill("80000")
            else:
                inv.fill("None")
            inv.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass

    # 7. Universal "Select One" Dropdowns
    dropdown_sel = (
        'button:has-text("Select One"), '
        'button[aria-label*="Select One" i], '
        'div[role="button"]:has-text("Select One"), '
        'div[role="combobox"]:has-text("Select One"), '
        '[data-automation-id="select-widget"]:has-text("Select One")'
    )
    initial_count = page.locator(dropdown_sel).count()
    if initial_count > 0:
        print(f"    [Workday Dropdowns] Found {initial_count} 'Select One' dropdowns to fill", flush=True)

    skipped_indices = set()
    b_counter = 0
    for _ in range(initial_count * 2):
        loc = page.locator(dropdown_sel)
        cur_cnt = loc.count()
        if cur_cnt == 0 or len(skipped_indices) >= cur_cnt:
            break
        target_idx = None
        for i in range(cur_cnt):
            if i not in skipped_indices:
                target_idx = i
                break
        if target_idx is None:
            break
        b = loc.nth(target_idx)
        b_counter += 1
        try:
            if not b.is_visible():
                skipped_indices.add(target_idx)
                continue
            pt = b.evaluate('''el => {
                let cur = el;
                for (let i = 0; i < 6 && cur; i++) {
                    cur = cur.parentElement;
                    if (cur) {
                        const da = cur.getAttribute('data-automation-id') || '';
                        if (da.includes('formField') || cur.tagName === 'FIELDSET' || cur.getAttribute('role') === 'group') {
                            return cur.innerText;
                        }
                    }
                }
                return (el.closest('[data-automation-id*="formField"], fieldset, [role="group"]') || el.parentElement.parentElement).innerText;
            }''').lower()
            target = "Yes"
            if any(k in pt for k in ["sponsorship", "sponsor", "immigration", "petition", "require to", "future require", "require tokyo", "require sponsorship"]) and not any(k in pt for k in ["legally authorized", "authorized to work"]):
                target = "No"
            elif any(k in pt for k in ["military", "veteran", "armed forces", "active duty"]):
                target = "No"
            elif any(k in pt for k in ["terminate", "termination", "discharged", "fired", "asked to resign", "disciplinary", "laid off", "involuntary"]):
                target = "No"
            elif any(k in pt for k in ["overtime"]):
                target = "Yes"
            elif any(k in pt for k in ["kind of employment", "type of employment"]):
                target = "Internship"
            elif any(k in pt for k in ["hispanic", "latino"]):
                target = "No"
            elif any(k in pt for k in ["ethnicity", "race"]):
                target = "Asian"
            elif any(k in pt for k in ["highest level of education", "grade completed", "education level", "degree level"]) or (pt.strip().startswith("degree") and "enrolled" not in pt) or "degree*" in pt:
                target = "Bachelor"
            elif any(k in pt for k in ["previous worker", "worked at", "worked with", "worked for us", "worked with us", "previously worked", "employee, consultant", "previously employed", "former employee", "ever been employed", "employed by", "interviewed", "previously interviewed", "prior employment", "interviews", "worked for tel", "current employee", "currently an employee", "internal candidate", "internal employee", "currently work for", "currently employed by", "employee of"]):
                target = "No"
            elif any(k in pt for k in ["agency", "recruiter", "recruiting agency", "third party", "search firm", "represented by"]):
                target = "No"
            elif any(k in pt for k in ["relative", "family member", "household", "same household", "conflict of interest", "conflict of interests", "outside work", "business opportunity", "business opportunities"]):
                target = "No"
            elif any(k in pt for k in ["contractual", "obligation", "non-compete", "restrictive covenant", "agreement with current or former", "commitments or agreement", "confidentiality agreement"]):
                target = "No"
            elif any(k in pt for k in ["crime", "felony", "convict"]):
                target = "No"
            elif any(k in pt for k in ["authorized to work", "legally authorized", "eligible to work", "right to work", "us citizen", "u.s. person", "us person", "export control", "itar", "18 years", "at least 18", "background check", "drug", "consent"]):
                target = "Yes"
            elif any(k in pt for k in ["what level clearance", "level clearance", "level of clearance", "clearance do you possess"]):
                target = "NoClearance"
            elif any(k in pt for k in ["security clearance", "hold a clearance", "hold a security clearance"]):
                target = "No"
            elif any(k in pt for k in ["amount of time", "travel percentage", "how much travel", "percent travel"]):
                target = "TravelTime"
            elif any(k in pt for k in ["enrolled full-time", "currently enrolled", "enrolled in a degree program"]):
                target = "Yes"
            elif any(k in pt for k in ["how soon", "when can you start", "soon could you start"]):
                target = "StartSoon"
            elif any(k in pt for k in ["essential function", "essential job functions", "reasonable accommodation", "willing and able", "able to use this skill", "use this skill set", "serve our customers"]):
                target = "Yes"
            elif any(k in pt for k in ["currently employed", "are you employed"]):
                target = "Yes"
            elif any(k in pt for k in ["english level", "language level", "english proficiency"]):
                target = "Proficient"
            elif any(k in pt for k in ["12-week", "may-september", "full-time 12-week", "relocate", "relocation"]):
                target = "Yes"
            elif any(k in pt for k in ["competing offer", "deadlines"]):
                target = "No"
            elif any(k in pt for k in ["salary", "desired salary", "compensation", "base salary", "pay expectation", "hourly rate", "pay rate"]):
                target = "Salary"
            elif "gpa" in pt:
                target = "GPA"
            elif any(k in pt for k in ["machine learning", "artificial intelligence", "exposure to"]):
                target = "Yes"
            elif any(k in pt for k in ["source control", "git", "version control"]):
                target = "SourceControl"
            elif any(k in pt for k in ["where you currently live", "office location", "work location"]):
                target = "Location"
            elif any(k in pt for k in ["current university", "current college", "attending university", "university/college"]) or (any(k in pt for k in ["university", "college", "school"]) and not any(m in pt for m in ["machine learning", "coursework", "exposure", "taken", "in school", "high school"])):
                target = "School"
            elif any(k in pt for k in ["semester", "term", "quarter"]):
                target = "Semester"
            elif any(k in pt for k in ["graduation year", "expected graduation year", "grad year", "anticipate graduating"]):
                target = "GradYear"
            elif any(k in pt for k in ["level of involvement", "how would you describe your level"]):
                target = "Involvement"
            elif any(k in pt for k in ["programming language", "primary programming", "preferred programming", "coding language"]):
                target = "ProgrammingLanguage"
            elif any(k in pt for k in ["language", "languages spoken", "native language"]):
                target = "English"
            elif any(k in pt for k in ["front-end or back-end", "backend or frontend", "frontend or backend", "prefer a front-end"]):
                target = "Backend"
            elif any(k in pt for k in ["terms you are available", "which terms", "start dates in the spring", "internship experiences with start dates"]):
                target = "Summer"
            elif any(k in pt for k in ["algorithm", "data structure"]):
                target = "Yes"
            elif any(k in pt for k in ["campus and/or other", "student organization", "club", "community group"]):
                target = "Yes"
            elif any(k in pt for k in ["related work experience", "prior experience", "job experience"]):
                target = "Yes"
            elif any(k in pt for k in ["major", "field of study", "degree program"]):
                target = "Major"
            elif any(k in pt for k in ["gender", "sex"]):
                target = "Male"
            elif any(k in pt for k in ["acknowledge", "polygraph", "maryland law", "understand the statement"]):
                target = "Acknowledge"
            elif any(k in pt for k in ["within the state of", "in the state of"]):
                target = "No"
            elif "veteran" in pt:
                target = "I am not a veteran"
            elif "how did you hear" in pt:
                target = "LinkedIn"

            print(f"    👉 Dropdown {b_counter}/{initial_count}: '{pt[:40].replace(chr(10), ' ')}' -> target='{target}'", flush=True)

            # Dismiss any leftover open popups first
            page.keyboard.press("Escape")
            time.sleep(0.2)

            try:
                b.evaluate('el => el.scrollIntoView({block: "center", inline: "center"})')
                time.sleep(0.3)
            except Exception:
                b.scroll_into_view_if_needed(timeout=2000)

            b.click(force=True, timeout=2000)
            time.sleep(1.2)

            # Fast check for direct LinkedIn option
            if target == "LinkedIn":
                opt_li = page.locator('[role="option"]:has-text("LinkedIn"), li:has-text("LinkedIn")').first
                if opt_li.is_visible():
                    print(f"      ✅ Selected via direct match: '{opt_li.inner_text().strip()}'", flush=True)
                    opt_li.click(force=True)
                    time.sleep(0.4)
                    continue

            # Get visible options only, excluding phone country codes
            opt_texts = page.evaluate('''() => {
                const els = Array.from(document.querySelectorAll('[role="option"], [data-automation-id*="promptOption"], [data-automation-id*="select-options"] li, ul[role="listbox"] li, div[id*="listbox"] li, div[data-automation-id*="menuItem"], [data-automation-id="select-item"]'))
                    .filter(el => {
                        const rect = el.getBoundingClientRect();
                        const txt = el.innerText.trim();
                        return rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden' && !txt.includes('+1');
                    });
                return els.map(e => e.innerText.trim());
            }''')
            if not opt_texts:
                time.sleep(1.0)
                opt_texts = page.evaluate('''() => {
                    const els = Array.from(document.querySelectorAll('[role="option"], [data-automation-id*="promptOption"], [data-automation-id*="select-options"] li, ul[role="listbox"] li, div[id*="listbox"] li, div[data-automation-id*="menuItem"], [data-automation-id="select-item"]'))
                        .filter(el => {
                            const rect = el.getBoundingClientRect();
                            const txt = el.innerText.trim();
                            return rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden' && !txt.includes('+1');
                        });
                    return els.map(e => e.innerText.trim());
                }''')
            if not opt_texts:
                try:
                    b.focus()
                    b.press("ArrowDown")
                    time.sleep(1.0)
                except Exception:
                    b.click(force=True)
                    time.sleep(1.2)
                opt_texts = page.evaluate('''() => {
                    const els = Array.from(document.querySelectorAll('[role="option"], [data-automation-id*="promptOption"], [data-automation-id*="select-options"] li, ul[role="listbox"] li, div[id*="listbox"] li, div[data-automation-id*="menuItem"], [data-automation-id="select-item"]'))
                        .filter(el => {
                            const rect = el.getBoundingClientRect();
                            const txt = el.innerText.trim();
                            return rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden' && !txt.includes('+1');
                        });
                    return els.map(e => e.innerText.trim());
                }''')

            match_idx = None
            
            # Pass 1: Exact match
            for idx, ot in enumerate(opt_texts):
                if not ot or "step" in ot.lower():
                    continue
                if target.lower() == ot.lower():
                    match_idx = idx
                    break

            # Pass 2: Keyword match
            if match_idx is None:
                for idx, ot in enumerate(opt_texts):
                    ot_low = ot.lower()
                    if not ot_low or "step" in ot_low:
                        continue
                    if target == "No":
                        if ot_low.startswith("no") or "no," in ot_low or "not require" in ot_low or "do not" in ot_low or "none" in ot_low or "false" in ot_low or "i will not" in ot_low or "i do not" in ot_low or "not applicable" in ot_low or "n/a" in ot_low or "none of the above" in ot_low or "not eligible" in ot_low or "ineligible" in ot_low:
                            match_idx = idx
                            break
                    elif target == "Yes":
                        if ot_low.startswith("yes") or "yes," in ot_low or "authorized" in ot_low or "citizen" in ot_low or "u.s. person" in ot_low or "agree" in ot_low or "accept" in ot_low or "true" in ot_low or "i am authorized" in ot_low or "i am eligible" in ot_low:
                            match_idx = idx
                            break
                    elif target == "Asian":
                        if "asian" in ot_low and not any(k in ot_low for k in ["two or more", "mixed", "multiple", "native hawaiian", "pacific islander"]):
                            match_idx = idx
                            break
                    elif target in ["Bachelor", "Degree"]:
                        if any(s in ot_low for s in ["bachelor of science", "bachelor's", "bachelor", "bs", "undergraduate", "college"]) and not any(neg in ot_low for neg in ["associate", "high school", "master", "phd", "doctorate"]):
                            match_idx = idx
                            break
                        elif any(s in ot_low for s in ["master of science", "master", "graduate"]) and not any(neg in ot_low for neg in ["associate", "high school"]):
                            match_idx = idx
                            break
                        elif any(s in ot_low for s in ["bachelor", "degree"]):
                            match_idx = idx
                            break
                    elif target == "Salary":
                        if any(s in ot_low for s in ["$", "80,000", "70,000", "60,000", "50,000", "40,000", "40", "35", "30", "25", "20", "negotiable", "competitive", "market", "hour", "hr"]):
                            match_idx = idx
                            break
                    elif target == "Internship":
                        if any(s in ot_low for s in ["intern", "internship", "full time", "full-time", "seasonal"]):
                            match_idx = idx
                            break
                    elif target == "TravelTime":
                        if any(s in ot_low for s in ["0-25%", "25%", "minimal", "none", "10%", "15%", "20%", "up to 25%", "no travel", "0%"]):
                            match_idx = idx
                            break
                        elif any(s in ot_low for s in ["month", "weeks", "notice", "days"]):
                            match_idx = idx
                            break
                    elif target == "NoClearance":
                        if any(s in ot_low for s in ["no clearance", "none", "not applicable", "n/a", "no", "do not possess"]):
                            match_idx = idx
                            break
                    elif target == "StartSoon":
                        if any(s in ot_low for s in ["within 1 month", "1 month", "2-3 weeks", "2 weeks", "3 weeks", "immediately", "flexible", "as soon"]):
                            match_idx = idx
                            break
                    elif target == "Proficient":
                        if any(s in ot_low for s in ["proficient", "fluent", "native", "advanced", "upper intermediate"]):
                            match_idx = idx
                            break
                    elif target == "English":
                        if any(s in ot_low for s in ["english", "fluent", "proficient", "native"]):
                            match_idx = idx
                            break
                    elif target == "LinkedIn":
                        # Prioritize exact or high confidence matches first
                        for l_idx, l_ot in enumerate(opt_texts):
                            l_low = l_ot.lower()
                            if any(k in l_low for k in ["opt out", "opt-out", "decline"]):
                                continue
                            if "linkedin" in l_low:
                                match_idx = l_idx
                                break
                        if match_idx is None:
                            for l_idx, l_ot in enumerate(opt_texts):
                                l_low = l_ot.lower()
                                if any(k in l_low for k in ["opt out", "opt-out", "decline"]):
                                    continue
                                if any(s in l_low for s in ["career site", "job board", "external", "internet", "social media", "online"]):
                                    match_idx = l_idx
                                    break
                        if match_idx is None:
                            for l_idx, l_ot in enumerate(opt_texts):
                                l_low = l_ot.lower()
                                if any(k in l_low for k in ["opt out", "opt-out", "decline"]):
                                    continue
                                if "other" in l_low:
                                    match_idx = l_idx
                                    break
                        break
                    elif target == "School":
                        for s_idx, s_ot in enumerate(opt_texts):
                            s_low = s_ot.lower()
                            if "rutgers" in s_low and not any(c in s_low for c in ["camden", "newark"]):
                                match_idx = s_idx
                                break
                        if match_idx is None:
                            for s_idx, s_ot in enumerate(opt_texts):
                                if any(o in s_ot.lower() for o in ["other", "not listed", "none of the above", "unlisted"]):
                                    match_idx = s_idx
                                    break
                        if match_idx is None and len(opt_texts) > 1:
                            match_idx = 1
                        break
                    elif target == "Semester":
                        for s_idx, s_ot in enumerate(opt_texts):
                            if "spring" in s_ot.lower():
                                match_idx = s_idx
                                break
                        if match_idx is None:
                            for s_idx, s_ot in enumerate(opt_texts):
                                if any(s in s_ot.lower() for s in ["summer", "fall"]):
                                    match_idx = s_idx
                                    break
                        break
                    elif target == "GradYear":
                        for g_idx, g_ot in enumerate(opt_texts):
                            if any(y in g_ot for y in ["2028", "2027 & later", "2027 and later", "2027", "2026"]):
                                match_idx = g_idx
                                break
                        if match_idx is None and opt_texts:
                            match_idx = len(opt_texts) - 1
                        break
                    elif target == "ProgrammingLanguage":
                        for pl_idx, pl_ot in enumerate(opt_texts):
                            if any(pl in pl_ot.lower() for pl in ["python", "java", "c++"]):
                                match_idx = pl_idx
                                break
                        break
                    elif target == "Backend":
                        for b_i, b_ot in enumerate(opt_texts):
                            if any(bk in b_ot.lower() for bk in ["back", "backend", "back-end", "full", "full stack"]):
                                match_idx = b_i
                                break
                    elif target == "Acknowledge":
                        for a_idx, a_ot in enumerate(opt_texts):
                            if any(ak in a_ot.lower() for ak in ["acknowledge", "agree", "yes", "i have read"]):
                                match_idx = a_idx
                                break
                        if match_idx is None and len(opt_texts) > 1:
                            match_idx = 1
                        break
                    elif target == "Major":
                        for m_idx, m_ot in enumerate(opt_texts):
                            if any(m in m_ot.lower() for m in ["computer science", "computer engineering", "software", "computing", "other"]):
                                match_idx = m_idx
                                break
                        break
                    elif target == "GPA" or "gpa" in pt:
                        for g_idx, g_ot in enumerate(opt_texts):
                            g_low = g_ot.lower()
                            if any(hi in g_low for hi in ["3.5", "3.8", "3.7", "3.0 - 4.0", "3.5 - 4.0", "3.0 - 3.9", "3.0+", "3.5+"]) and "below" not in g_low and "<" not in g_low:
                                match_idx = g_idx
                                break
                        if match_idx is None:
                            for g_idx, g_ot in enumerate(opt_texts):
                                if "3.0" in g_ot and "below" not in g_ot.lower():
                                    match_idx = g_idx
                                    break
                        break
                    elif target == "Summer":
                        for sm_idx, sm_ot in enumerate(opt_texts):
                            if "summer" in sm_ot.lower():
                                match_idx = sm_idx
                                break
                        break
                    elif target == "Involvement":
                        for inv_i, inv_ot in enumerate(opt_texts):
                            if any(inv in inv_ot.lower() for inv in ["engaged", "member", "attendee", "leadership", "officer"]):
                                match_idx = inv_i
                                break
                        break
                    elif target == "SourceControl":
                        for sc_i, sc_ot in enumerate(opt_texts):
                            if any(sc in sc_ot.lower() for sc in ["git", "github", "gitlab"]):
                                match_idx = sc_i
                                break
                        break
                    elif target == "Location":
                        for loc_i, loc_ot in enumerate(opt_texts):
                            if any(loc in loc_ot.lower() for loc in ["remote", "new york", "chicago", "ames", "bozeman", "denver"]):
                                match_idx = loc_i
                                break
                        if match_idx is None and len(opt_texts) > 1:
                            match_idx = 1
                        break
                    elif target.lower() in ot_low:
                        if target == "Male" and "female" in ot_low:
                            continue
                        match_idx = idx
                        break

            # Pass 3: Fallback for Salary or other (non-strict)
            if match_idx is None and opt_texts and target not in ["Yes", "No", "Male"]:
                for idx, ot in enumerate(opt_texts):
                    if ot and "select one" not in ot.lower() and "step" not in ot.lower() and "+1" not in ot and "phone" not in ot.lower():
                        match_idx = idx
                        break

            if match_idx is not None and match_idx < len(opt_texts):
                matched_label = opt_texts[match_idx]
                print(f"      ✅ Selected: '{matched_label}'", flush=True)
                page.evaluate('''(targetIdx) => {
                    const els = Array.from(document.querySelectorAll('[role="option"], [data-automation-id*="promptOption"], [data-automation-id*="select-options"] li, ul[role="listbox"] li, div[id*="listbox"] li, div[data-automation-id*="menuItem"], [data-automation-id="select-item"]'))
                        .filter(el => {
                            const rect = el.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden';
                        });
                    if (targetIdx < els.length) {
                        els[targetIdx].scrollIntoView({ block: 'nearest' });
                        els[targetIdx].click();
                    }
                }''', match_idx)
                time.sleep(0.4)
                # If clicking match opened sub-level options for source only (e.g. Job Board -> LinkedIn)
                if any(k in pt for k in ["how did you hear", "source"]):
                    time.sleep(0.5)
                    page.evaluate('''() => {
                        const kw = ["linkedin", "indeed", "glassdoor", "social media", "internet", "job board", "online", "other"];
                        const visibleSubs = Array.from(document.querySelectorAll('[role="option"], [data-automation-id*="promptOption"], div[data-automation-id*="menuItem"], li[role="option"]'))
                            .filter(el => {
                                const rect = el.getBoundingClientRect();
                                return rect.width > 0 && rect.height > 0;
                            });
                        if (!visibleSubs.length) return;
                        for (const k of kw) {
                            const found = visibleSubs.find(el => el.innerText.toLowerCase().includes(k));
                            if (found) {
                                found.scrollIntoView({ block: 'nearest' });
                                found.click();
                                return;
                            }
                        }
                        visibleSubs[0].scrollIntoView({ block: 'nearest' });
                        visibleSubs[0].click();
                    }''')
                    time.sleep(0.3)
            else:
                valid_opts = [o for o in opt_texts if "select one" not in o.lower() and o.strip()]
                ai_opt = solve_field_with_ai(pt, "select", options=valid_opts, company=comp, role=role)
                if ai_opt:
                    for o_i, o_t in enumerate(opt_texts):
                        if "select one" in o_t.lower():
                            continue
                        if ai_opt.lower() in o_t.lower() or o_t.lower() in ai_opt.lower():
                            match_idx = o_i
                            print(f"      🤖 [Qwen AI] Selected '{o_t}' for '{pt[:35]}'", flush=True)
                            page.evaluate(f'''() => {{
                                const els = Array.from(document.querySelectorAll('[role="option"], [data-automation-id*="promptOption"], [data-automation-id*="select-options"] li, ul[role="listbox"] li, div[id*="listbox"] li, div[data-automation-id*="menuItem"], [data-automation-id="select-item"]'))
                                    .filter(el => {{
                                        const rect = el.getBoundingClientRect();
                                        const txt = el.innerText.trim();
                                        return rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden' && !txt.includes('+1');
                                    }});
                                if (els[{o_i}]) {{
                                    els[{o_i}].scrollIntoView({{ block: 'nearest' }});
                                    els[{o_i}].click();
                                }}
                            }}''')
                            break
                if match_idx is None and valid_opts:
                    for o_i, o_t in enumerate(opt_texts):
                        if o_t == valid_opts[0]:
                            match_idx = o_i
                            print(f"      ✅ Fallback selected: '{o_t}' for '{pt[:35]}'", flush=True)
                            page.evaluate(f'''() => {{
                                const els = Array.from(document.querySelectorAll('[role="option"], [data-automation-id*="promptOption"], [data-automation-id*="select-options"] li, ul[role="listbox"] li, div[id*="listbox"] li, div[data-automation-id*="menuItem"], [data-automation-id="select-item"]'))
                                    .filter(el => {{
                                        const rect = el.getBoundingClientRect();
                                        const txt = el.innerText.trim();
                                        return rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden' && !txt.includes('+1');
                                    }});
                                if (els[{o_i}]) {{
                                    els[{o_i}].scrollIntoView({{ block: 'nearest' }});
                                    els[{o_i}].click();
                                }}
                            }}''')
                            break
                if match_idx is None:
                    print(f"      ⚠️ No match found for '{target}'. Available: {opt_texts[:5]}", flush=True)
                    page.keyboard.press("Escape")
                    time.sleep(0.3)
                    skipped_indices.add(target_idx)
        except Exception as ex:
            print(f"      ⚠️ Dropdown error: {ex}", flush=True)
            page.keyboard.press("Escape")
            skipped_indices.add(target_idx)

    # 8. Radios with value, label, and label[for=id] checks
    for radio in page.locator('input[type="radio"]').all():
        try:
            rid = radio.get_attribute("id") or ""
            r_name = (radio.get_attribute("name") or "").lower()
            val = (radio.get_attribute("value") or "").lower()
            lbl_elem = page.locator(f'label[for="{rid}"]').first if rid else None
            lt = (lbl_elem.inner_text().lower() if lbl_elem and lbl_elem.count() > 0 else "")
            if not lt:
                try:
                    lt = radio.evaluate('''el => {
                        const sibling = el.parentElement ? el.parentElement.querySelector('label, [data-automation-id*="Label"]') : null;
                        if (sibling && sibling.innerText.trim()) return sibling.innerText.trim();
                        if (el.nextElementSibling && el.nextElementSibling.innerText.trim()) return el.nextElementSibling.innerText.trim();
                        const pLabel = el.closest('label');
                        if (pLabel && pLabel.innerText.trim()) return pLabel.innerText.trim();
                        return el.value || '';
                    }''').lower()
                except Exception:
                    lt = ""
            pt = radio.evaluate('''el => {
                const p = el.closest('fieldset, [role="radiogroup"], [role="group"], div[data-automation-id*="formField"]') || el.parentElement.parentElement;
                return p ? p.innerText : '';
            }''').lower()

            should_click = False
            if "previousworker" in r_name or "priorworker" in r_name:
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["previous worker", "worked at", "employee, consultant", "previously employed", "former employee", "employed by", "in the past", "prior", "interviewed", "previously interviewed", "current employee", "currently an employee", "internal candidate", "internal employee", "currently work for", "currently employed by", "employee of"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["terminate", "termination", "discharged", "fired", "asked to resign", "disciplinary", "laid off", "involuntary"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["overtime"]):
                if "yes" in lt or val in ["true", "1"]:
                    should_click = True
            elif any(k in pt for k in ["kind of employment", "type of employment"]):
                if "intern" in lt or val in ["internship", "intern"]:
                    should_click = True
            elif any(k in pt for k in ["agency", "recruiter", "recruiting agency", "third party", "search firm", "represented by"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["relative", "family member", "conflict of interest"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["non-compete", "restrictive covenant", "obligations, contractual", "contractual obligations"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["educational degree", "highest degree", "degree earned", "education level", "degree you have earned"]):
                if "bachelor" in lt or "undergraduate" in lt or "college" in lt:
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
            elif any(k in pt for k in ["terms you are available", "which terms", "start dates in the spring", "internship experiences with start dates"]):
                if "summer" in lt or "full-time" in lt:
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
            elif any(k in pt for k in ["gender", "sex"]):
                if "male" in lt and "female" not in lt:
                    should_click = True
            elif any(k in pt for k in ["hispanic", "latino"]):
                if "no" in lt or val in ["false", "0", "2"]:
                    should_click = True
            elif any(k in pt for k in ["ethnicity", "race"]) or ("asian" in lt and not any(k in lt for k in ["two or more", "mixed", "multiple", "native hawaiian", "pacific islander"])):
                if "asian" in lt and not any(k in lt for k in ["two or more", "mixed", "multiple", "native hawaiian", "pacific islander"]):
                    should_click = True

            if should_click and not radio.is_checked():
                clicked = False
                if rid:
                    le = page.locator(f'label[for="{rid}"]').first
                    if le.count() > 0:
                        le.click(force=True, timeout=2000)
                        clicked = True
                if not clicked or not radio.is_checked():
                    radio.click(force=True, timeout=2000)
                if not radio.is_checked():
                    radio.evaluate("el => el.click()")
        except Exception:
            pass

    # 9. Checkboxes (terms, consent, agreements, negative options, internship, ethnicity)
    for agree_lbl in page.locator('label[for*="acceptTermsAndAgreements" i], label:has-text("I agree"), label:has-text("terms and conditions"), label:has-text("read and consent"), label:has-text("acknowledge"), label:has-text("privacy policy"), label:has-text("candidate privacy"), label:has-text("I have read")').all():
        try:
            if agree_lbl.is_visible():
                agree_lbl.scroll_into_view_if_needed(timeout=2000)
                agree_lbl.click(force=True, timeout=2000)
                time.sleep(0.3)
        except Exception:
            pass

    for c in page.locator('input[type="checkbox"], label:has-text("have not worked"), label:has-text("Never worked"), label:has-text("None of the above"), label:has-text("terms and conditions"), label:has-text("read and consent"), label:has-text("Internship"), label:has-text("Asian"), label:has-text("I agree"), label:has-text("agree"), label:has-text("acknowledge"), label:has-text("privacy policy")').all():
        try:
            is_label = c.evaluate("e => e.tagName == 'LABEL'")
            txt = c.inner_text().lower() if is_label else c.evaluate("e => (e.closest('label') || e.parentElement).innerText").lower()
            if any(k in txt for k in ["have not worked", "never worked", "none of the above", "not worked for"]):
                c.click(force=True, timeout=2000)
            elif any(k in txt for k in ["1st shift", "first shift", "day shift", "any shift", "flexible"]) or ("shift" in txt and not any(x in txt for x in ["night", "graveyard", "3rd", "4th"])):
                c.click(force=True, timeout=2000)
            elif any(k in txt for k in ["terms and conditions", "read and consent", "have read and consent", "i have read", "acknowledge", "privacy policy", "candidate privacy"]):
                if not is_label and not c.is_checked():
                    cid = c.get_attribute("id") or ""
                    if cid:
                        lbl = page.locator(f'label[for="{cid}"]').first
                        if lbl.count() > 0:
                            lbl.click(force=True, timeout=2000)
                    if not c.is_checked():
                        c.click(force=True, timeout=2000)
                    if not c.is_checked():
                        c.evaluate("el => el.click()")
                elif is_label:
                    c.click(force=True, timeout=2000)
                    c.evaluate("el => el.click()")
            elif "asian" in txt and not any(k in txt for k in ["two or more", "mixed", "multiple", "native hawaiian", "pacific islander"]):
                if not is_label and not c.is_checked():
                    cid = c.get_attribute("id") or ""
                    if cid:
                        lbl = page.locator(f'label[for="{cid}"]').first
                        if lbl.count() > 0:
                            lbl.click(force=True, timeout=2000)
                    if not c.is_checked():
                        c.click(force=True, timeout=2000)
                    if not c.is_checked():
                        c.evaluate("el => el.click()")
                elif is_label:
                    c.click(force=True, timeout=2000)
                    c.evaluate("el => el.click()")
            elif any(k in txt for k in ["agree", "consent", "acknowledge", "certify", "affirm"]) and not any(x in txt for x in ["disability", "sponsor"]):
                if not is_label and not c.is_checked():
                    cid = c.get_attribute("id") or ""
                    if cid:
                        lbl = page.locator(f'label[for="{cid}"]').first
                        if lbl.count() > 0:
                            lbl.click(force=True, timeout=2000)
                    if not c.is_checked():
                        c.click(force=True, timeout=2000)
                    if not c.is_checked():
                        c.evaluate("el => el.click()")
                elif is_label:
                    c.click(force=True, timeout=2000)
                    c.evaluate("el => el.click()")
            elif any(k in txt for k in ["internship", "intern"]) and not any(k in txt for k in ["full time", "part time"]):
                if not is_label and not c.is_checked():
                    cid = c.get_attribute("id") or ""
                    if cid:
                        lbl = page.locator(f'label[for="{cid}"]').first
                        if lbl.is_visible():
                            lbl.click(force=True, timeout=2000)
                    if not c.is_checked():
                        c.click(force=True, timeout=2000)
                elif is_label:
                    c.click(force=True, timeout=2000)
        except Exception:
            pass
def apply_workday_job(browser, job, headful=False):
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
        from playwright_stealth import Stealth
        Stealth().apply_stealth_sync(page)
    except Exception:
        pass

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        if headful:
            bring_window_to_front()

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
        if any(k in body_initial for k in [
            "page you are looking for doesn't exist", "job is no longer available",
            "no longer accepting applications", "position has been closed",
            "workday is currently unavailable", "service interruption", "under maintenance"
        ]) or "maintenance-page" in page.url.lower():
            print("  ℹ️ Job posting is closed/expired or tenant under maintenance. Skipping.", flush=True)
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

        # 3c. If still on job description page (/job/) after auth, click Apply -> Apply Manually / Autofill
        if "/job/" in page.url.lower() and "/apply" not in page.url.lower():
            print("  ℹ️ Still on job posting after auth. Clicking Apply...", flush=True)
            apply_btn = page.locator('a[data-automation-id="adventureButton"], [data-automation-id="applyButton"], a:has-text("Apply")').first
            if apply_btn.is_visible(timeout=3000):
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

            step_body = page.locator("body").inner_text().lower()
            if any(k in step_body for k in ["workday is currently unavailable", "service interruption", "under maintenance"]) or "maintenance-page" in page.url.lower():
                print("  ⚠️ Workday tenant is currently under maintenance. Skipping.", flush=True)
                page.close()
                return False

            if not is_authenticated(page):
                print("  🔑 Re-detected unauthenticated state inside step loop. Handling auth...", flush=True)
                handle_workday_auth(page, comp)
                page.wait_for_timeout(3000)
                continue

            conf_text = page.locator("body").inner_text().lower()

            # Check for immediate Workday submission confirmation
            if any(w in conf_text for w in [
                "application submitted",
                "congratulations on your successful application",
                "thank you for applying",
                "thank you for your interest",
                "your application has been received",
                "you have no more tasks",
                "in process, under consideration"
            ]) and ("userhome" in page.url.lower() or "submitted" in conf_text or "my applications" in conf_text or "application submitted" in conf_text):
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
                    "--status", "Submitted - Pending Response",
                    "--notes", "Workday autonomous confirmation screenshot saved"
                ]
                subprocess.run(cmd, check=False)
                page.close()
                return True

            # Check if Workday crashed or has draft conflict ("Something went wrong")
            if "something went wrong" in conf_text or "something went wrong" in current_sec.lower():
                print("  ⚠️ Encountered 'Something went wrong'. Checking Candidate Home for unsubmitted draft...", flush=True)
                if "/job/" in url:
                    userhome_url = url.split("/job/")[0] + "/userHome"
                    page.goto(userhome_url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(3000)
                    if not is_authenticated(page):
                        handle_workday_auth(page, comp)
                    rows = page.locator('table tbody tr').all()
                    draft_resumed = False
                    for r in rows:
                        rt = r.inner_text()
                        if "Not Submitted" in rt:
                            menu_btn = r.locator('button[data-automation-id="actionMenuTarget"], button[aria-label*="Action" i], button:has-text("...")').first
                            if menu_btn.is_visible():
                                menu_btn.click(force=True)
                                page.wait_for_timeout(1200)
                                cont = page.locator('[role="menuitem"]:has-text("Continue Application"), button:has-text("Continue Application"), a:has-text("Continue Application")').first
                                if cont.is_visible():
                                    print("  📝 Successfully resumed unsubmitted draft from Candidate Home!", flush=True)
                                    cont.click(force=True)
                                    page.wait_for_timeout(5000)
                                    draft_resumed = True
                                    break
                    if draft_resumed:
                        continue
                    else:
                        print("  ⚠️ Could not find recoverable draft on Candidate Home. Skipping.", flush=True)
                        page.close()
                        return False

            if current_sec and current_sec == last_sec:
                same_sec_retries += 1
                for alert in page.locator('[data-automation-id*="error" i], [role="alert"], [data-automation-id*="validation" i], [aria-invalid="true"]').all():
                    try:
                        if alert.is_visible():
                            err_txt = alert.inner_text().strip().replace(chr(10), ' ')
                            print(f"  ❌ VISIBLE ERROR ON {current_sec}: {err_txt}", flush=True)
                            try:
                                os.makedirs("artifacts/scratch", exist_ok=True)
                                safe_n = re.sub(r"[^a-zA-Z0-9_]", "_", f"{comp}_{role}".lower())[:50]
                                page.screenshot(path=f"artifacts/scratch/workday_error_{safe_n}.png")
                            except Exception:
                                pass
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
                if any(w in conf_text for w in ["thank you for applying", "thank you", "application submitted", "congratulations", "your application has been received", "return to home", "you have no more tasks", "in process, under consideration"]):
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
                        "--status", "Submitted - Pending Response",
                        "--notes", "Workday autonomous confirmation screenshot saved"
                    ]
                    subprocess.run(cmd, check=False)
                    page.close()
                    return True

            # Resume / Transcript upload if file input or dropzone exists in DOM
            file_inps = page.locator('input[type="file"], input[data-automation-id="file-upload-input-ref"]')
            body_sub = page.locator("body").inner_text().lower()
            needs_upload = any(k in current_sec.lower() for k in ["autofill", "resume", "upload", "experience", "question"]) or any(k in body_sub for k in ["upload your resume", "resume/cv", "upload a file", "upload", "transcript", "attachment", "drop files here"]) or file_inps.count() > 0
            dz_elem = page.locator('div:has-text("Drop files here"), [data-automation-id*="dropZone" i]').first
            dz_visible = dz_elem.is_visible() if dz_elem.count() > 0 else False

            if needs_upload and (dz_visible or file_inps.count() > 0):
                primary_resume = "/Users/ariqserazi/Downloads/Ariq_Serazi__Resume_2026.pdf"
                if os.path.exists(primary_resume):
                    pdf_path = primary_resume
                else:
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
            fill_all_workday_section_fields(page, today, comp=comp, role=role)

            # Click Save and Continue / Next in page footer
            next_btn = page.locator('button[data-automation-id="bottom-navigation-next-button"], button[data-automation-id="pageFooterNextButton"], [data-automation-id="pageFooter"] button:has-text("Save and Continue"), [data-automation-id="pageFooter"] button:has-text("Continue"), [data-automation-id="pageFooter"] button:has-text("Next"), button:has-text("Save and Continue"), button:has-text("Next")').first
            if next_btn.is_visible():
                next_btn.click(force=True)
                page.wait_for_timeout(6000)
            else:
                # If next_btn not visible, check if we need to click Apply / Apply Manually from job view
                apply_btn = page.locator('a[data-automation-id="adventureButton"], button[data-automation-id="adventureButton"], [data-automation-id="applyButton"], [data-automation-id*="apply" i]:has-text("Apply"), a:has-text("Apply"), button:has-text("Apply")').first
                man_btn = page.locator('[data-automation-id="applyManually"], a:has-text("Apply Manually"), button:has-text("Apply Manually"), [data-automation-id="autofillWithResume"], a:has-text("Autofill with Resume"), button:has-text("Autofill with Resume")').first
                if man_btn.is_visible(timeout=1500):
                    print("  👉 Clicking Apply Manually / Autofill from job view...", flush=True)
                    man_btn.click(force=True)
                    page.wait_for_timeout(3000)
                    continue
                elif apply_btn.is_visible(timeout=1500) and "/job/" in page.url.lower() and "/apply" not in page.url.lower():
                    print("  👉 Clicking Apply from job view...", flush=True)
                    apply_btn.click(force=True)
                    page.wait_for_timeout(2000)
                    continue

                page.wait_for_timeout(3000)
                conf_text = page.locator("body").inner_text().lower()
                if any(w in conf_text for w in [
                    "application submitted",
                    "congratulations on your successful application",
                    "thank you for applying",
                    "thank you for your interest",
                    "your application has been received",
                    "you have no more tasks",
                    "in process, under consideration"
                ]) and ("userhome" in page.url.lower() or "submitted" in conf_text or "my applications" in conf_text or "application submitted" in conf_text):
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
                        "--status", "Submitted - Pending Response",
                        "--notes", "Workday autonomous confirmation screenshot saved"
                    ]
                    subprocess.run(cmd, check=False)
                    page.close()
                    return True

                # Check for Review Submit button
                sub_btn = page.locator('button[data-automation-id="bottom-navigation-next-button"]:has-text("Submit"), button[data-automation-id="pageFooterNextButton"]:has-text("Submit"), [data-automation-id="pageFooter"] button:has-text("Submit"), button:has-text("Submit")').first
                if sub_btn.is_visible(timeout=2000):
                    print("  🚀 Review Step Reached! Clicking Submit...", flush=True)
                    sub_btn.click(force=True)
                    page.wait_for_timeout(8000)
                    continue

                # Check once more with a brief wait in case page is still rendering navigation
                page.wait_for_timeout(3000)
                retry_btn = page.locator('button[data-automation-id="bottom-navigation-next-button"], button[data-automation-id="pageFooterNextButton"], [data-automation-id="pageFooter"] button:has-text("Save and Continue"), [data-automation-id="pageFooter"] button:has-text("Continue"), [data-automation-id="pageFooter"] button:has-text("Next"), button:has-text("Save and Continue"), button:has-text("Next"), button:has-text("Submit")').first
                if retry_btn.is_visible(timeout=2500):
                    retry_btn.click(force=True)
                    page.wait_for_timeout(6000)
                    continue
                if step_idx <= 2:
                    page.wait_for_timeout(4000)
                    continue
                break

    except Exception as e:
        print(f"  ⚠️ Exception during application for {comp}: {e}", flush=True)
    finally:
        try:
            page.close()
        except Exception:
            pass

    return False

def run_workday_batch(limit=189, queue_file="application_engine/queue_workday.json", headful=False):
    applied_urls, applied_pairs, applied_reqs = load_applied()
    queue_path = Path(queue_file)
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
        if req and any(bad in req.lower() for bad in ["xml", "2026", "2027", "2028"]):
            req = None

        if u in applied_urls or f"{c}:::{r}" in applied_pairs:
            continue
        if req and req in applied_reqs:
            continue
        unapplied.append(j)

    print(f"Loaded {len(unapplied)} unapplied Workday jobs. Target confirmed submissions: {limit}...", flush=True)

    success = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=not headful,
            args=["--disable-blink-features=AutomationControlled"]
        )

        for idx, j in enumerate(unapplied):
            if success >= limit:
                print(f"🎯 Target of {limit} confirmed submissions reached!", flush=True)
                break
            print(f"\n>>> [{idx+1}/{len(unapplied)}] (Confirmed: {success}/{limit}) Launching {j['company']} - {j.get('role', j.get('title', ''))}...", flush=True)
            res = apply_workday_job(browser, j, headful=headful)
            if res:
                success += 1
                print(f"✅ Current batch confirmed: {success}/{limit}", flush=True)
                if success >= limit:
                    print(f"🎯 Target of {limit} confirmed submissions reached!", flush=True)
                    break
            time.sleep(2)

        browser.close()

    print(f"\n🏁 Workday batch complete! Confirmed {success} new submissions.")

if __name__ == "__main__":
    headful = "--headful" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--headful"]
    limit = int(args[0]) if len(args) > 0 else 189
    queue_file = args[1] if len(args) > 1 else "application_engine/queue_workday.json"
    run_workday_batch(limit=limit, queue_file=queue_file, headful=headful)
