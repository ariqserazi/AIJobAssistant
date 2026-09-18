#!/usr/bin/env python3
"""
apply_playwright.py (Generalized ATS & Ashby Application Runner)
Automates end-to-end job application form-filling, radio/bubble answering, resume uploading,
and employer submission verification across any Ashby or modern ATS job posting.
"""

import os
import sys
import time
import argparse
import subprocess
from playwright.sync_api import sync_playwright

try:
    from config_loader import load_config, get_candidate_dict, get_responses_dict
except ImportError:
    try:
        from application_engine.config_loader import load_config, get_candidate_dict, get_responses_dict
    except ImportError:
        def load_config(): return {}
        def get_candidate_dict(): return {}
        def get_responses_dict(): return {}

_cfg = load_config()
_c = get_candidate_dict()
_resp = get_responses_dict()

DEFAULT_RESUME_PATH = _cfg.get("default_resume_pdf") or str(Path(__file__).parent.parent / "references" / "sample_resume.pdf")

CANDIDATE_DATA = {
    "first_name": _c.get("first_name", "Jane"),
    "last_name": _c.get("last_name", "Doe"),
    "full_name": _c.get("name", "Jane Doe"),
    "email": _c.get("email", "jane.doe@example.com"),
    "phone": _c.get("phone", "555-123-4567"),
    "location": _c.get("location", "New York, NY"),
    "linkedin": _c.get("linkedin", "https://linkedin.com/in/janedoe"),
    "github": _c.get("github", "https://github.com/janedoe"),
    "portfolio": _c.get("portfolio", "https://janedoe.dev"),
    "school": _c.get("school", "State University"),
    "degree": _c.get("discipline", "Computer Science"),
    "salary_expectation": _c.get("salary", "80000"),
}

DEFAULT_FREE_TEXT_RESPONSES = _resp


def bring_window_to_front():
    try:
        subprocess.run([
            "osascript", "-e",
            'tell application "Google Chrome for Testing" to activate'
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def fill_basic_fields(page):
    name_el = page.locator("input[name='_systemfield_name'], [data-field-path='_systemfield_name'] input, input[placeholder*='full name' i]").first
    if name_el.is_visible():
        name_el.click()
        name_el.fill("")
        name_el.fill(CANDIDATE_DATA["full_name"])
        print(f"  [Field] Name -> {CANDIDATE_DATA['full_name']}")

    email_el = page.locator("input[name='_systemfield_email'], [data-field-path='_systemfield_email'] input, input[type='email']").first
    if email_el.is_visible():
        email_el.click()
        email_el.fill("")
        email_el.fill(CANDIDATE_DATA["email"])
        print(f"  [Field] Email -> {CANDIDATE_DATA['email']}")

    phone_el = page.locator("input[type='tel'], [data-field-path*='phone'] input, input[name*='phone']").first
    if phone_el.is_visible():
        phone_el.click()
        phone_el.fill("")
        phone_el.fill(CANDIDATE_DATA["phone"])
        print(f"  [Field] Phone -> {CANDIDATE_DATA['phone']}")

def select_location_autocomplete(page):
    loc_input = page.locator("[data-field-path='_systemfield_location'] input, input[placeholder*='Start typing'][role='combobox']").first
    if loc_input.is_visible():
        loc_input.click()
        loc_input.fill("")
        loc_input.type("Piscataway, New Jersey", delay=50)
        time.sleep(1.2)
        opt = page.locator("[role='option']").first
        if opt.is_visible():
            opt_text = opt.inner_text().strip()
            opt.click()
            print(f"  [Location] Selected from listbox: {opt_text}")
        else:
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
            print("  [Location] Selected via ArrowDown + Enter")
        time.sleep(0.5)

def upload_resume(page, resume_path):
    if not os.path.exists(resume_path):
        print(f"  [Warning] Resume file not found at: {resume_path}")
        return False
    
    file_inputs = page.query_selector_all('input[type="file"]')
    for fi in file_inputs:
        try:
            fi.set_input_files(resume_path)
            print(f"  [Resume] Successfully attached PDF: {resume_path}")
            time.sleep(3.5)
            return True
        except Exception as e:
            print(f"  [Resume] Could not attach to element: {e}")
    return False

def audit_all_field_entries(page):
    field_entries = page.query_selector_all("[class*='field-entry'], [class*='fieldEntry'], [data-qa*='field']")
    print(f"  [Audit] Inspecting {len(field_entries)} field entries individually...")

    for i, fe in enumerate(field_entries):
        try:
            q_title = fe.query_selector("label, [class*='question-title']")
            title_text = q_title.inner_text().strip() if q_title else ""
            tl = title_text.lower()

            yesno_btns = fe.query_selector_all("button[data-option]")
            if yesno_btns:
                target = "no"
                if any(k in tl for k in ["onsite", "authorized", "comfortable", "18 years", "eligible", "commute", "travel", "meet this requirement"]):
                    target = "yes"
                elif any(k in tl for k in ["sponsor", "sponsorship", "visa"]):
                    target = "no"
                elif any(k in tl for k in ["felony", "relative", "non-compete", "previously employed"]):
                    target = "no"

                for btn in yesno_btns:
                    if btn.get_attribute("data-option") == target:
                        btn.click()
                        print(f"    [Bubble] Entry {i}: '{title_text[:35]}' -> Clicked {target.upper()}")
                continue

            opt_buttons = fe.query_selector_all("button._option_1svni_32, [role='radio'], input[type='radio']")
            for b in opt_buttons:
                bt = b.inner_text().strip().lower()
                val = (b.get_attribute("value") or "").strip().lower()
                txt = bt or val
                if "male" in txt and "female" not in txt:
                    b.click()
                    print("    [Bubble] Gender -> Male")
                    break
                elif "asian" in txt:
                    b.click()
                    print("    [Bubble] Race -> Asian")
                    break
                elif "not hispanic" in txt:
                    b.click()
                    print("    [Bubble] Hispanic -> No")
                    break
                elif "not a protected veteran" in txt or "not a veteran" in txt:
                    b.click()
                    print("    [Bubble] Veteran -> Not Veteran")
                    break
                elif "no, i don't have a disability" in txt or "no, i do not" in txt:
                    b.click()
                    print("    [Bubble] Disability -> No Disability")
                    break

            txt_inputs = fe.query_selector_all("input[type='text'], input[type='url'], input[type='number'], input:not([type])")
            for inp in txt_inputs:
                if inp.get_attribute("role") == "combobox" and inp.input_value().strip():
                    continue
                val = inp.input_value()
                if not val.strip():
                    if "linkedin" in tl:
                        inp.fill(CANDIDATE_DATA["linkedin"])
                    elif "github" in tl:
                        inp.fill(CANDIDATE_DATA["github"])
                    elif "portfolio" in tl or "website" in tl:
                        inp.fill(CANDIDATE_DATA["portfolio"])
                    elif "hear about" in tl or "source" in tl:
                        inp.fill("Company career page")
                    elif "visa" in tl and "type" in tl:
                        inp.fill("N/A")
                    elif any(k in tl for k in ["salary", "compensation"]):
                        inp.fill(CANDIDATE_DATA["salary_expectation"])

            textareas = fe.query_selector_all("textarea")
            for ta in textareas:
                if not ta.is_visible() or ta.get_attribute("name") == "g-recaptcha-response":
                    continue
                if not ta.input_value().strip():
                    if any(k in tl for k in ["process", "system you've implemented", "impact"]):
                        ta.fill(DEFAULT_FREE_TEXT_RESPONSES["process"])
                    elif any(k in tl for k in ["well-run", "culture", "organization"]):
                        ta.fill(DEFAULT_FREE_TEXT_RESPONSES["organization"])
                    elif any(k in tl for k in ["why", "interested", "draw"]):
                        ta.fill(DEFAULT_FREE_TEXT_RESPONSES["why"])
                    elif any(k in tl for k in ["experience", "background"]):
                        ta.fill(DEFAULT_FREE_TEXT_RESPONSES["experience"])
                    else:
                        ta.fill(DEFAULT_FREE_TEXT_RESPONSES["project"])
        except Exception:
            continue

def check_submission_confirmed(page, max_wait_seconds=30):
    confirmation_keywords = [
        "application submitted",
        "application was successfully submitted",
        "thank you for applying",
        "submission confirmed",
        "we received your application",
        "received your submission"
    ]
    start = time.time()
    while time.time() - start < max_wait_seconds:
        time.sleep(1.5)
        if page.is_closed():
            return False
        try:
            body = page.inner_text("body").lower()
            for kw in confirmation_keywords:
                if kw in body:
                    print(f"🎉 CONFIRMED: Found confirmation phrase '{kw}'!")
                    return True
        except Exception:
            break
    return False

def run_application(url, resume_path=DEFAULT_RESUME_PATH, auto_submit=False, auto_log=False, company="", role="", notes=""):
    print(f"\n========================================================")
    print(f"🚀 Starting Application: {url}")
    print(f"========================================================")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1280,900", "--window-position=50,50"]
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        bring_window_to_front()

        app_url = url if "/application" in url else url.rstrip("/") + "/application"
        print(f"Navigating to: {app_url}")
        try:
            page.goto(app_url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            page.goto(url, timeout=30000)
        
        time.sleep(1.5)

        print("\n1. Uploading resume PDF...")
        upload_resume(page, resume_path)

        print("\n2. Filling basic information...")
        fill_basic_fields(page)

        print("\n3. Handling Location autocomplete...")
        select_location_autocomplete(page)

        print("\n4. Auditing all field entries...")
        audit_all_field_entries(page)

        bring_window_to_front()

        if auto_submit:
            print("\n5. Auto-submitting application...")
            submit_btn = page.query_selector('button[type="submit"], button:has-text("Submit Application"), button:has-text("Submit")')
            if submit_btn:
                submit_btn.click()
                print("Clicked Submit button.")
            else:
                print("⚠️ Submit button not found.")

            confirmed = check_submission_confirmed(page, max_wait_seconds=15)

            if not confirmed:
                try:
                    body_text = page.inner_text("body").lower()
                    if any(k in body_text for k in ["possible spam", "couldn't submit your application", "flagged"]):
                        print("  [Anti-Bot Alert] Submission flagged as possible spam by synthetic event detector.")
                        print("  [Fallback] Triggering Computer Vision Physical Mouse Click fallback...")
                        
                        # Add scripts directory to path if needed
                        scripts_dir = os.path.dirname(os.path.abspath(__file__))
                        if scripts_dir not in sys.path:
                            sys.path.insert(0, scripts_dir)
                            
                        from cv_mouse_fallback import click_element_cv
                        clicked = click_element_cv(page)
                        if clicked:
                            print("  [Fallback] Dispatched OS-level physical click! Waiting for confirmation...")
                            confirmed = check_submission_confirmed(page, max_wait_seconds=20)
                except Exception as e:
                    print(f"  [Fallback Error] Could not run CV mouse fallback: {e}")

            if confirmed and auto_log and company and role:
                print("\n6. Logging submission to Google Sheet...")
                log_script = os.path.expanduser("~/.agents/skills/resume-tailor-swe/scripts/log_application.py")
                cmd = [
                    "python3", log_script,
                    "--company", company,
                    "--role", role,
                    "--link", url,
                    "--notes", notes or "Submitted via automated ATS copilot; verified employer confirmation."
                ]
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    print(res.stdout)
                except subprocess.CalledProcessError as e:
                    print(f"Failed to log application: {e.stderr}")

        else:
            print("\nBrowser is open for your review. Submit whenever ready!")
            try:
                page.wait_for_selector("body", timeout=600000)
            except Exception:
                pass

        browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automate job application form filling.")
    parser.add_argument("url", help="URL of the job posting or application page")
    parser.add_argument("--resume", default=DEFAULT_RESUME_PATH, help="Path to resume PDF")
    parser.add_argument("--submit", action="store_true", help="Automatically submit once filled")
    parser.add_argument("--log", action="store_true", help="Log to central Google Sheet tracker on confirmed submission")
    parser.add_argument("--company", default="", help="Company name for logging")
    parser.add_argument("--role", default="", help="Role title for logging")
    parser.add_argument("--notes", default="", help="Notes for logging")

    args = parser.parse_args()
    run_application(
        args.url,
        resume_path=args.resume,
        auto_submit=args.submit,
        auto_log=args.log,
        company=args.company,
        role=args.role,
        notes=args.notes
    )
