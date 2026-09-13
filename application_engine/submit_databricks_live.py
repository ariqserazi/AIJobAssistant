import time
import os
import sys
from playwright.sync_api import sync_playwright

sys.path.append("/Users/ariqserazi/.agents/skills/resume-tailor-swe/scripts")
import log_application

RESUME_PATH = "/Users/ariqserazi/Downloads/Ariq_Serazi__Resume_2026.pdf"
TRANSCRIPT_PATH = "/Users/ariqserazi/Downloads/Ariq_Serazi_Rutgers_Transcript.pdf"
CONF_DIR = os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/confirmations")
os.makedirs(CONF_DIR, exist_ok=True)
CONF_IMG = os.path.join(CONF_DIR, "databricks_swe_intern_confirmed.png")

URL = "https://job-boards.greenhouse.io/embed/job_app?for=databricks&token=8732364002"
JOB_LINK = "https://databricks.com/company/careers/open-positions/job?gh_jid=8732364002"
ROLE = "Software Engineering Intern (2027 Start) - Winter"
COMPANY = "databricks"

print(f"🚀 Starting live submission for {COMPANY} - {ROLE}...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(URL, timeout=45000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)

    # 1. Base inputs
    page.locator("#first_name").fill("Ariq")
    page.locator("#last_name").fill("Serazi")
    pref = page.locator("#preferred_name")
    if pref.count() > 0:
        pref.fill("Ariq")
    page.locator("#email").fill("ariq.serazi1@gmail.com")
    page.locator("#phone").fill("732-853-6773")
    print("  Filled basic candidate contact fields.")

    # 2. File Uploads
    page.locator("input[type='file']#resume").set_input_files(RESUME_PATH)
    print(f"  Uploaded resume: {RESUME_PATH}")
    time.sleep(1)

    # Transcripts
    t_inputs = page.query_selector_all("input[type='file']")
    for fi in t_inputs:
        fid = fi.get_attribute("id") or ""
        if fid != "resume":
            fi.set_input_files(TRANSCRIPT_PATH)
            print(f"  Uploaded transcript to file input #{fid}")
            time.sleep(0.5)

    # 3. React Selects
    react_selects = page.locator(".select-shell, .remix-css-b62m3t-container").all()
    print(f"  Found {len(react_selects)} React Select dropdowns.")
    for s in react_selects:
        try:
            s.scroll_into_view_if_needed()
            lbl_text = s.evaluate('''el => {
                let p = el;
                for (let i = 0; i < 5; i++) {
                    if (!p) break;
                    const lbl = p.querySelector('label, legend');
                    if (lbl && lbl.innerText.trim() && !lbl.innerText.toLowerCase().includes('select')) return lbl.innerText.trim();
                    p = p.parentElement;
                }
                return '';
            }''').lower()

            # Location autocomplete
            if "location" in lbl_text or "city" in lbl_text or s.locator("#candidate-location").count() > 0:
                loc_inp = s.locator("#candidate-location, input.select__input, input").first
                if loc_inp.count() > 0 and not loc_inp.input_value().strip():
                    loc_inp.focus()
                    loc_inp.press_sequentially("Piscataway", delay=50)
                    time.sleep(1.5)
                    suggs = s.locator('.select__menu div[class*="option"]').all()
                    nj_sugg = next((o for o in suggs if "piscataway" in o.inner_text().lower() and "new jersey" in o.inner_text().lower()), None)
                    target = nj_sugg if nj_sugg else (suggs[0] if suggs else None)
                    if target:
                        print(f"  Selected location: {target.inner_text().strip()}")
                        target.click()
                        continue

            # School autocomplete
            if "school" in lbl_text or "university" in lbl_text or s.locator("[id*='school']").count() > 0:
                sch_inp = s.locator("input.select__input, input[id*='school'], input").first
                if sch_inp.count() > 0:
                    sch_inp.focus()
                    sch_inp.press_sequentially("Rutgers", delay=40)
                    time.sleep(1.5)
                    suggs = s.locator('.select__menu div[class*="option"]').all()
                    nb_sugg = next((o for o in suggs if "new brunswick" in o.inner_text().lower()), None)
                    target_sugg = nb_sugg if nb_sugg else (suggs[0] if suggs else None)
                    if target_sugg:
                        target_txt = target_sugg.inner_text().strip()
                        target_sugg.click()
                        print(f"  Selected school: {target_txt}")
                        continue

            # Discipline autocomplete
            if any(k in lbl_text for k in ["discipline", "major", "field of study", "area of study"]) or s.locator("[id*='discipline'], [id*='major']").count() > 0:
                disc_inp = s.locator("input.select__input, input[id*='discipline'], input[id*='major'], input").first
                if disc_inp.count() > 0:
                    disc_inp.focus()
                    disc_inp.press_sequentially("Computer Science", delay=40)
                    time.sleep(1.0)
                    suggs = s.locator('.select__menu div[class*="option"]').all()
                    cs_sugg = next((o for o in suggs if "computer science" in o.inner_text().lower()), None)
                    target_sugg = cs_sugg if cs_sugg else (suggs[0] if suggs else None)
                    if target_sugg:
                        target_txt = target_sugg.inner_text().strip()
                        target_sugg.click()
                        print(f"  Selected discipline: {target_txt}")
                        continue

            # Standard React Select control click
            ctrl = s.locator(".select__control").first
            if ctrl.count() > 0 and ctrl.is_visible():
                ctrl.click()
                time.sleep(0.3)
                opts = s.locator('.select__menu div[class*="option"]').all()
                clean_opts = [(o, o.inner_text().replace("'", "").replace('"', '').strip().lower()) for o in opts]

                target_opt = None
                if "country" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if "united states" in t), None)
                elif "degree" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if "master" in t), next((o for o, t in clean_opts if "bachelor" in t), None))
                elif "end date month" in lbl_text or ("end" in lbl_text and "month" in lbl_text):
                    target_opt = next((o for o, t in clean_opts if "may" in t), None)
                elif "graduation date" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if "spring 2028" in t or "2028" in t), None)
                elif "gpa" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if "3.6 or above" in t or "3.8" in t or "3.5 or above" in t), None)
                elif "40 hours" in lbl_text or "full-time" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if t == "yes"), None)
                elif any(k in lbl_text for k in ["learn", "source", "hear"]):
                    target_opt = next((o for o, t in clean_opts if "linkedin" in t or "career" in t), opts[0] if opts else None)
                elif "authori" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if t == "yes" or "authorized" in t), None)
                elif "sponsorship" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if t == "no"), None)
                elif "previously" in lbl_text or "worked" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if t == "no"), None)
                elif "gender" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if t == "male" or t == "man"), None)
                elif "race" in lbl_text or "ethnicity" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if "asian" in t), None)
                elif "hispanic" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if t == "no"), None)
                elif "veteran" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if "not" in t or t == "no"), None)
                elif "disability" in lbl_text:
                    target_opt = next((o for o, t in clean_opts if "no" in t), None)

                if target_opt:
                    print(f"  Selected '{target_opt.inner_text().strip()}' for '{lbl_text[:30]}'")
                    target_opt.click()
                else:
                    page.keyboard.press("Escape")
                time.sleep(0.15)
        except Exception as e:
            print(f"  Notice during select {lbl_text[:20]}: {e}")
            page.keyboard.press("Escape")

    # 4. Text inputs (LinkedIn, website)
    for w in page.query_selector_all(".field-wrapper, .field"):
        lbl_el = w.query_selector("label, legend")
        lbl = (lbl_el.inner_text() if lbl_el else "").lower()
        ti = w.query_selector("input[type='text']:not(#first_name):not(#last_name):not(#email):not(#phone):not(#candidate-location)")
        if ti and not ti.input_value().strip():
            if "linkedin" in lbl:
                ti.fill("https://linkedin.com/in/ariq-serazi")
            elif "website" in lbl or "portfolio" in lbl:
                ti.fill("https://ariqserazi.github.io/")

    # 5. End Date Year
    ey = page.locator("input#end-year--0, input[id*='end-year' i]").first
    if ey.count() > 0 and not ey.input_value().strip():
        ey.fill("2028")
        print("  Filled End Date Year: 2028")

    # 6. Checkboxes (Strictly Sanctions "None of the above" ONLY & SF location)
    cbs = page.query_selector_all("input[type='checkbox']")
    for cb in cbs:
        cb_id = cb.get_attribute("id") or ""
        label_text = page.evaluate("(id) => { const l = document.querySelector(`label[for=\"${id}\"]`); return l ? l.innerText.trim() : ''; }", cb_id)
        if not label_text:
            label_text = cb.evaluate("el => (el.closest('.checkbox__wrapper') ? el.closest('.checkbox__wrapper').querySelector('label')?.innerText.trim() : '') || ''")
        group_text = cb.evaluate("el => (el.closest('fieldset, .field-wrapper, .field') ? el.closest('fieldset, .field-wrapper, .field').querySelector('legend, label')?.innerText.trim() : '') || ''").lower()
        lbl_low = label_text.lower()
        
        should_check = False
        if any(k in group_text for k in ["sanction", "export control", "cuba", "iran", "north korea", "syria"]):
            if "none of the above" in lbl_low or lbl_low == "none":
                should_check = True
            elif any(k in lbl_low for k in ["cuba", "iran", "north korea", "syria", "crimea", "russia", "belarus", "sanctions"]):
                should_check = False
        elif any(k in group_text for k in ["prior question other than", "if you selected a response to the prior question"]):
            if "not applicable" in lbl_low or "i selected “none of the above”" in lbl_low:
                should_check = True
            else:
                should_check = False
        elif any(k in group_text for k in ["single location", "most interested in"]):
            if "san francisco" in lbl_low:
                should_check = True
            else:
                should_check = False
        elif any(k in lbl_low for k in ["agree", "consent", "acknowledge", "privacy policy", "terms"]):
            should_check = True
            
        is_checked = cb.is_checked()
        if should_check and not is_checked:
            cb.click(force=True)
            print(f"  CHECKED: '{label_text}' in group '{group_text[:30]}'")
        elif not should_check and is_checked:
            cb.click(force=True)
            print(f"  UNCHECKED: '{label_text}' in group '{group_text[:30]}'")

    time.sleep(1)

    # 7. Form validation pre-check
    invalid = page.evaluate("""() => {
        const inv = [];
        document.querySelectorAll('input:not([type=\"checkbox\"]), select, textarea').forEach(el => {
            if (!el.checkValidity()) {
                inv.push({ id: el.id, name: el.name, type: el.type });
            }
        });
        return inv;
    }""")
    if invalid:
        print("❌ Warning: Invalid form fields detected before submit:", invalid)
    else:
        print("✅ Pre-submission validation passed! 0 invalid elements.")

    # 8. Submit Application
    sub_btn = page.locator("button#submit_app, button[type='submit'], button:has-text('Submit Application')").first
    print("  Clicking submit button...")
    sub_btn.scroll_into_view_if_needed()
    time.sleep(0.5)
    sub_btn.click()

    # 9. Wait for confirmation
    print("  Waiting for employer confirmation...")
    sys.path.insert(0, "/Users/ariqserazi/Documents/antigravity/radiant-kepler/application_engine")
    from email_verification_helper import handle_verification_code_if_present

    confirmed = False
    for i in range(60):
        time.sleep(1)
        
        # Check if email verification code is requested
        if i % 3 == 0:
            if handle_verification_code_if_present(page, company=COMPANY, max_wait=35):
                print(f"  🔑 [Verification Code] Successfully handled and resubmitted code for {COMPANY}!")

        content = page.content().lower()
        title = page.title().lower()
        url = page.url.lower()

        if any(k in content or k in title for k in [
            "thank you for applying", "application submitted", "thanks for applying",
            "we have received your application", "application received", "successfully submitted"
        ]) or "confirmation" in url or "submitted" in url:
            confirmed = True
            print(f"  🎉 CONFIRMED: Employer confirmation verified after {i+1}s!")
            break

    if confirmed:
        page.screenshot(path=CONF_IMG, full_page=True)
        print(f"  📸 Saved confirmation screenshot to {CONF_IMG}")
        
        # 10. Auto-log to Google Sheet
        print(f"  📊 Auto-logging submission to Google Sheet (1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY)...")
        log_application.log_to_google_sheets(
            company=COMPANY,
            role=ROLE,
            job_link=JOB_LINK,
            status="Submitted - Pending Response",
            notes="Databricks Greenhouse live verified submission"
        )
        print("  ✅ Logged successfully to Google Sheet!")
    else:
        err_path = "/Users/ariqserazi/.gemini/antigravity/brain/110f767a-21b6-4af2-b8d3-fe58a783a63c/scratch/databricks_submission_unconfirmed.png"
        page.screenshot(path=err_path, full_page=True)
        print(f"  ⚠️ Confirmation not detected within 40s. Saved screenshot to {err_path}")

    browser.close()
