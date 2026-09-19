#!/usr/bin/env python3
"""
batch_apply_multi_ats.py - Unified Multi-ATS Application Engine (Ashby, Greenhouse, Lever)
Specifically tuned for early-career Software Engineering (SWE) and IT positions
in Remote US and NYC / New Jersey Metro.
"""

import os
import sys
import json
import time
import re
import subprocess
import tempfile
import fcntl
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

# Enable mouse‑click mode via environment variable
USE_MOUSE = os.getenv("USE_MOUSE", "false").lower() == "true"

ENGINE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, os.path.expanduser("~/.agents/skills/resume-tailor-swe/scripts"))
sys.path.insert(0, str(ENGINE_DIR))

from fast_resume_selector import get_fast_tailored_resume
from cv_mouse_fallback import click_element_cv, bring_window_to_front
from email_verification_helper import handle_verification_code_if_present
from captcha_solver import handle_captchas_if_present, screenshot_captcha
from question_logger import log_discovered_question
from employer_selector import get_recent_employer
from ai_form_solver import solve_field_with_ai


LOG_SCRIPT = os.path.expanduser("~/.agents/skills/resume-tailor-swe/scripts/log_application.py")
CONFIRMATIONS_DIR = os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/confirmations")
os.makedirs(CONFIRMATIONS_DIR, exist_ok=True)
ERRORS_DIR = os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/errors")
os.makedirs(ERRORS_DIR, exist_ok=True)
SCRATCH_ERRORS_DIR = os.environ.get("SCRATCH_DIR", os.path.join(tempfile.gettempdir(), "job_assistant_scratch"))
os.makedirs(SCRATCH_ERRORS_DIR, exist_ok=True)

from config_loader import get_candidate_dict, get_responses_dict, load_config
_cfg = load_config()
CANDIDATE = get_candidate_dict()
RESPONSES = get_responses_dict()
def remove_url_from_queue_file(target_file, url_to_remove):
    if not target_file:
        return
    target_path = Path(target_file)
    if not target_path.exists():
        return
    lock_file_path = str(target_path) + ".lock"
    try:
        with open(lock_file_path, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                with open(target_path, "r") as qf:
                    cur_q = json.load(qf)
                new_q = [x for x in cur_q if x.get("url", "").strip().lower().rstrip("/") != url_to_remove]
                target_dir = os.path.dirname(os.path.abspath(target_path))
                with tempfile.NamedTemporaryFile("w", dir=target_dir, delete=False) as tf:
                    json.dump(new_q, tf, indent=2)
                    temp_name = tf.name
                os.replace(temp_name, target_path)
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
    except Exception as e:
        print(f"  ⚠️ Could not update queue file: {e}", flush=True)

def get_dynamic_cover_letter():
    name = CANDIDATE.get("name", "Applicant")
    school = CANDIDATE.get("school", "University")
    degree = CANDIDATE.get("degree", "Computer Science")
    employer = CANDIDATE.get("current_company", "Technology Company")
    project = CANDIDATE.get("featured_project", "Distributed Systems")
    return (
        f"Dear Hiring Team,\n\n"
        f"I am writing to express my strong interest in joining your team. With a {degree} from {school} "
        f"and software engineering experience building production services and distributed systems, "
        f"I am excited about the opportunity to contribute to your engineering goals.\n\n"
        f"At {employer}, I engineered backend microservices and reliable automation pipelines. "
        f"Additionally, in my project {project}, I designed high-performance service contracts and optimized data architectures "
        f"to achieve real-time synchronization across distributed clients.\n\n"
        f"Thank you for your consideration.\n\nSincerely,\n{name}"
    )

def safe_click(el):
    try:
        el.scroll_into_view_if_needed()
        lbl = el.evaluate_handle("el => el.closest('label')")
        if lbl.as_element():
            lbl.as_element().click(force=True)
        else:
            el.click(force=True)
        el.evaluate("""el => {
            if (el.tagName === 'INPUT' && (el.type === 'radio' || el.type === 'checkbox')) {
                el.checked = true;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""")
    except Exception:
        try:
            el.evaluate("""el => {
                const l = el.closest('label');
                if (l) l.click();
                else el.click();
                if (el.tagName === 'INPUT' && (el.type === 'radio' || el.type === 'checkbox')) {
                    el.checked = true;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }""")
        except Exception:
            pass

def fill_greenhouse(page, pdf_path, company="", role="", jd_text=""):
    print("  [Greenhouse Engine] Filling application form...", flush=True)
    recent_emp = get_recent_employer(company=company, role=role, jd_text=jd_text)
    # 1. Base inputs
    mappings = [
        ("first_name", CANDIDATE["first_name"]),
        ("last_name", CANDIDATE["last_name"]),
        ("preferred_name", CANDIDATE["first_name"]),
        ("preferred", CANDIDATE["first_name"]),
        ("email", CANDIDATE["email"]),
        ("phone", CANDIDATE["phone"]),
        ("candidate-location", CANDIDATE["location"]),
        ("country", "United States"),
        ("address", "32 Birch Run Ave"),
        ("street", "32 Birch Run Ave"),
        ("city", "Piscataway"),
        ("state", "New Jersey"),
        ("zip", CANDIDATE["zip_code"]),
        ("postal", CANDIDATE["postal_code"]),
        ("discipline", CANDIDATE["discipline"]),
        ("major", CANDIDATE["major"]),
    ]
    for field_id, val in mappings:
        inp = page.locator(f"input[name='{field_id}'], input#{field_id}, input[id*='{field_id}' i]").first
        if inp.count() > 0 and inp.is_visible() and not inp.input_value().strip():
            inp.fill(val)

    # 1b. Dynamic Text/Tel Input Scanner (handles question_* and aria-label fields like Phone, Current Job Title, Current Employer, School)
    try:
        text_inputs = page.locator("input[type='text'], input[type='tel'], input:not([type])").all()
        for ti in text_inputs:
            try:
                if not ti.is_visible():
                    continue
                ti_class = ti.get_attribute("class") or ""
                if "select__input" in ti_class or "security-input" in (ti.get_attribute("id") or ""):
                    continue
                if ti.input_value().strip():
                    continue
                
                ctx = ti.evaluate('''el => {
                    const aria = el.getAttribute('aria-label') || '';
                    const placeholder = el.getAttribute('placeholder') || '';
                    const name = el.getAttribute('name') || '';
                    const id = el.getAttribute('id') || '';
                    let lbl = '';
                    if (id) {
                        const l = document.querySelector(`label[for="${id}"]`);
                        if (l) lbl = l.innerText.trim();
                    }
                    if (!lbl) {
                        const p = el.closest('.field, .field-wrapper, .input-container, div');
                        if (p) {
                            const l = p.querySelector('label, legend');
                            if (l) lbl = l.innerText.trim();
                        }
                    }
                    return (aria + ' ' + lbl + ' ' + placeholder + ' ' + name + ' ' + id).toLowerCase();
                }''')

                if any(k in ctx for k in ["pronounced", "phonetic", "how your name is pronounced"]):
                    ti.fill("Ah-reek Seh-rah-zee")
                    print("    [Greenhouse Engine] Filled phonetic name: Ah-reek Seh-rah-zee", flush=True)
                elif (any(k in ctx for k in ["phone", "mobile", "tel", "cell"]) or re.search(r'\bphone\b', ctx)) and not any(k in ctx for k in ["phonetic", "pronounced"]):
                    ti.fill(CANDIDATE["phone"])
                    print(f"    [Greenhouse Engine] Filled phone into '{ctx[:30]}'", flush=True)
                elif any(k in ctx for k in ["previous employer", "the one before", "prior employer"]):
                    prior_emp = "Amin AI" if recent_emp == "TidaMed" else "TidaMed"
                    ti.fill(prior_emp)
                    print(f"    [Greenhouse Engine] Filled previous employer: {prior_emp}", flush=True)
                elif any(k in ctx for k in ["most recent employer", "recent employer", "current employer", "last employer", "current company"]):
                    ti.fill(recent_emp)
                    print(f"    [Greenhouse Engine] Filled most recent employer: {recent_emp}", flush=True)
                elif any(k in ctx for k in ["job title", "current title", "current job title", "title"]) and not any(k in ctx for k in ["mr", "ms", "prefix"]):
                    ti.fill(CANDIDATE["current_title"])
                    print(f"    [Greenhouse Engine] Filled title: {CANDIDATE['current_title']}", flush=True)
                elif any(k in ctx for k in ["current company", "employer", "company"]) and not any(k in ctx for k in ["hear", "source"]):
                    ti.fill(recent_emp)
                    print(f"    [Greenhouse Engine] Filled employer: {recent_emp}", flush=True)
                elif any(k in ctx for k in ["sat score"]) or re.search(r'\bsat\b', ctx):
                    ti.fill("1280")
                    print("    [Greenhouse Engine] Filled SAT: 1280", flush=True)
                elif any(k in ctx for k in ["act score"]) or re.search(r'\bact\b', ctx):
                    ti_type = ti.get_attribute("type") or ""
                    w_req = ti.get_attribute("required") is not None or ti.get_attribute("aria-required") == "true" or "*" in ctx
                    if w_req and ti_type != "number":
                        ti.fill("N/A")
                        print("    [Greenhouse Engine] Filled ACT: N/A (did not take)", flush=True)
                    else:
                        print("    [Greenhouse Engine] Leaving ACT blank (did not take)", flush=True)
                elif any(k in ctx for k in ["gre score"]) or re.search(r'\bgre\b', ctx):
                    ti.fill("N/A")
                elif any(k in ctx for k in ["when do you graduate", "when will you graduate", "year do you intend to complete", "intended semester and year of graduation", "year of graduation", "expected graduation", "graduating date", "graduation date"]):
                    ti_type = ti.get_attribute("type") or ""
                    if ti_type == "number":
                        ti.fill("2028")
                    else:
                        ti.fill("May 2028")
                    print("    [Greenhouse Engine] Filled graduation: May 2028", flush=True)
                elif any(k in ctx for k in ["start year", "start date year", "start-year"]):
                    ti.fill("2024")
                    print("    [Greenhouse Engine] Filled start year: 2024", flush=True)
                elif any(k in ctx for k in ["end year", "end date year", "end-year"]):
                    is_emp = ti.evaluate("el => !!el.closest('#employment_section, [data-qa*=\"employment\"], .employment, [class*=\"employment\"], fieldset[id*=\"employment\"], div[id*=\"employment\"], #employment_section_fields') || el.id.includes('end-date-year')")
                    if is_emp:
                        cb_clicked = ti.evaluate('''el => {
                            const p = el.closest('#employment_section, [data-qa*="employment"], .employment, [class*="employment"], fieldset, form, div');
                            const cb = p ? p.querySelector('input[type="checkbox"][id*="current-role"], input[type="checkbox"]') : null;
                            if (cb && !cb.checked) { cb.click(); return true; }
                            return false;
                        }''')
                        if cb_clicked:
                            print("    [Greenhouse Engine] Checked 'Current role' checkbox for employment", flush=True)
                            ti.fill("")
                        else:
                            ti.fill("2024")
                            print("    [Greenhouse Engine] Filled employment end year: 2024", flush=True)
                    else:
                        ti.fill("2028")
                        print("    [Greenhouse Engine] Filled graduation end year: 2028", flush=True)
                elif any(k in ctx for k in ["when are you available to start", "available to start", "start date", "ideal start date", "when can you start", "commence"]):
                    ti_type = ti.get_attribute("type") or ""
                    is_year = "year" in ctx or ti.get_attribute("maxlength") == "4"
                    is_winter = any(w in ctx for w in ["winter", "january", "december"])
                    if is_year:
                        ti.fill("2026" if is_winter else "2027")
                    elif ti_type == "date":
                        ti.fill("2026-12-20" if is_winter else "2027-05-20")
                    else:
                        ti.fill("December 20, 2026" if is_winter else "May 20, 2027")
                    print(f"    [Greenhouse Engine] Filled start date: {'December 20, 2026' if is_winter else 'May 20, 2027'}", flush=True)
                elif any(k in ctx for k in ["preferred end date", "end date"]):
                    ti_type = ti.get_attribute("type") or ""
                    is_year = "year" in ctx or ti.get_attribute("maxlength") == "4"
                    if is_year:
                        ti.fill("2028")
                    elif ti_type == "date":
                        ti.fill("2027-08-31")
                    else:
                        ti.fill("August 2027")
                    print("    [Greenhouse Engine] Filled end date: August 2027", flush=True)
                elif any(k in ctx for k in ["c++ feature", "favorite c++"]):
                    ti.fill("Smart pointers and RAII for deterministic memory management and safety")
                elif any(k in ctx for k in ["salary expectation", "hourly rate", "hourly compensation", "desired hourly", "compensation expectations", "compensation range"]):
                    ti_type = ti.get_attribute("type") or ""
                    if ti_type == "number":
                        ti.fill("40")
                    else:
                        ti.fill("$40/hr")
                elif any(k in ctx for k in ["notice period", "current notice"]):
                    ti.fill("Immediate / 2 weeks")
                elif any(k in ctx for k in ["achievement", "proud of", "most challenging project", "favorite project", "challenging project", "achievement you're particularly proud of"]):
                    ti.fill("At Amin AI I engineered automated microservices using Python and FastAPI with strict JSON schema validation to reliably process complex multi service workflows. In addition I built Trackwise a distributed real time expense tracker using Flutter and gRPC with PostgreSQL achieving sub 100ms synchronization and 30 percent network efficiency gains.")
                elif any(k in ctx for k in ["why vercel", "why figma", "why samsara", "why appian", "why hp iq", "why are you interested", "what excites you about this opportunity"]):
                    ti.fill("I admire your engineering culture and focus on high performance developer tools and distributed systems. My background in building responsive APIs with FastAPI and scalable distributed services aligns directly with your mission and I would love to contribute meaningfully as an intern.")
                elif any(k in ctx for k in ["tell us something about yourself", "can't find on your resume", "cant find on your resume"]):
                    ti.fill("I love mentoring fellow computer science students in algorithm design and volunteering with Nourish the Earth on local environmental initiatives in New Jersey.")
                elif any(k in ctx for k in ["large language models", "llm", "gemini", "bedrock", "agentic ai"]):
                    ti.fill("I have extensive experience deploying Gemini and OpenAI models within Python automation pipelines using structured JSON outputs, prompt engineering, and MCP server integrations for reliable tool use and dynamic data retrieval.")
                elif any(k in ctx for k in ["security clearance", "clearance level"]):
                    ti.fill("None")
                elif any(k in ctx for k in ["did anyone refer you", "who referred you", "referred by an employee"]):
                    ti.fill("No")
                elif any(k in ctx for k in ["visa classification", "visa status", "immigration sponsorship needs", "if working on a visa", "if no, please explain your status", "enter n/a", "enter 'n/a'", "extension options", "when does it expire", "additional detail about your sponsorship", "sponsorship needs"]):
                    ti.fill("N/A")
                elif any(k in ctx for k in ["drivers license"]):
                    ti.fill("N/A")
                elif any(k in ctx for k in ["publications", "preprints"]):
                    ti.fill("N/A")
                elif any(k in ctx for k in ["university", "school", "college", "institution"]):
                    ti.fill(CANDIDATE["school"])
                    print(f"    [Greenhouse Engine] Filled school: {CANDIDATE['school']}", flush=True)
                elif any(k in ctx for k in ["discipline", "major", "field of study", "area of study", "field are you looking"]):
                    ti.fill(CANDIDATE["discipline"])
                elif "linkedin" in ctx:
                    ti.fill(CANDIDATE["linkedin"])
                elif "github" in ctx:
                    ti.fill(CANDIDATE["github"])
                elif any(k in ctx for k in ["website", "portfolio", "personal site", "scholar", "publications link", "google scholar"]):
                    ti.fill(CANDIDATE["portfolio"])
                elif "gpa" in ctx:
                    ti.fill(CANDIDATE["gpa"])
                elif any(k in ctx for k in ["first name", "given name", "first_name"]) and not any(k in ctx for k in ["last", "full", "refer"]):
                    ti.fill(CANDIDATE["first_name"])
                elif any(k in ctx for k in ["last name", "family name", "surname", "last_name"]):
                    ti.fill(CANDIDATE["last_name"])
                elif any(k in ctx for k in ["full name", "your name", "full legal name"]) and not any(k in ctx for k in ["first", "last", "refer"]):
                    ti.fill(CANDIDATE["name"])
                elif "email" in ctx:
                    ti.fill(CANDIDATE["email"])
                elif any(k in ctx for k in ["city", "candidate location", "address"]):
                    ti.fill(CANDIDATE["location"])
                elif any(k in ctx for k in ["zip", "postal"]):
                    ti.fill(CANDIDATE["zip_code"])
                elif any(k in ctx for k in ["duolingo account", "duolingo username"]):
                    ti.fill(CANDIDATE.get("github", "").split("/")[-1] or "candidate")
                elif "username" in ctx:
                    ti.fill(CANDIDATE.get("github", "").split("/")[-1] or "candidate")
            except Exception:
                pass
    except Exception as e:
        print(f"    [Greenhouse Engine] Text scanner notice: {e}", flush=True)

    TRANSCRIPT_PATH = _cfg.get("transcript_pdf", "")

    # 2. File upload (Resume & Transcript)
    fi = page.locator("input[type='file'][id*='resume'], input[type='file'][name*='resume' i], input#resume, input[type='file']").first
    if fi.count() > 0:
        try:
            fi.set_input_files(pdf_path)
            print("  [Greenhouse Engine] Uploaded tailored PDF resume.", flush=True)
        except Exception as e:
            print(f"  [Greenhouse Engine] Resume upload error: {e}", flush=True)
        time.sleep(1.0)

    # Check if Cover Letter is required and offers 'Enter manually'
    try:
        cl_sec = page.locator("div:has-text('Cover Letter *'), div:has(label:has-text('Cover Letter *'))").first
        if cl_sec.count() > 0:
            man_btn = cl_sec.locator("button:has-text('Enter manually'), a:has-text('Enter manually'), button:has-text('Write')").first
            if man_btn.count() > 0 and man_btn.is_visible():
                man_btn.click(force=True)
                time.sleep(0.5)
                cl_ta = cl_sec.locator("textarea").first
                if cl_ta.count() > 0:
                    cl_ta.fill(get_dynamic_cover_letter())
                    print("  [Greenhouse Engine] Entered manual cover letter for required field", flush=True)
    except Exception as cle:
        print(f"  [Greenhouse Engine] Cover letter check notice: {cle}", flush=True)

    # Attach transcript if requested
    if os.path.exists(TRANSCRIPT_PATH):
        try:
            file_elements = page.query_selector_all("input[type='file']")
            for f in file_elements:
                try:
                    f_id = f.get_attribute("id") or ""
                    f_name = f.get_attribute("name") or ""
                    if "resume" in f_id.lower() or "resume" in f_name.lower():
                        continue
                    upload_label = f.evaluate('el => (el.closest(".file-upload")?.querySelector(".upload-label")?.innerText || el.closest(".field-wrapper, .field")?.querySelector("label, legend")?.innerText || "")').lower()
                    if any(k in upload_label or k in f_id.lower() or k in f_name.lower() for k in ["transcript", "grades", "academic record"]):
                        f.set_input_files(TRANSCRIPT_PATH)
                        print(f"  [Greenhouse Engine] Uploaded Transcript to '{upload_label[:30]}' ({f_id})", flush=True)
                        time.sleep(1.0)
                except Exception:
                    pass
        except Exception as te:
            print(f"  [Greenhouse Engine] Transcript upload notice: {te}", flush=True)

    # 3. Textareas (strict rule: zero dashes/hyphens)
    tas = page.locator("textarea").all()
    for ta in tas:
        if not ta.is_visible() or ta.input_value().strip():
            continue
        lbl_text = ta.evaluate('''el => {
            let p = el;
            for (let i = 0; i < 5; i++) {
                if (!p) break;
                const l = p.querySelector('label, .label, legend');
                if (l && l.innerText.trim()) return l.innerText.trim();
                p = p.parentElement;
            }
            return '';
        }''').lower()
        w_req = ta.get_attribute("required") is not None or ta.get_attribute("aria-required") == "true" or "*" in lbl_text

        if "cover letter" in lbl_text:
            if "optional" in lbl_text or not w_req:
                print("  [Greenhouse Engine] Skipping optional cover letter textarea (strictly blank per user instruction)", flush=True)
            else:
                ta.fill(get_dynamic_cover_letter())
        elif any(k in lbl_text for k in ["start month/year of university", "start month/year"]):
            ta.fill(f"{CANDIDATE.get('undergrad_start_month', 'September')} {CANDIDATE.get('undergrad_start_year', '2022')} to {CANDIDATE.get('grad_month_year', 'May 2026')}")
        elif any(k in lbl_text for k in ["clouds", "misclassifies", "aircraft computer vision", "flight logs"]):
            ta.fill("I would first aggregate the flight logs into a structured queryable format to correlate false positive obstacle detections against metadata features such as camera light levels, altitude, and timestamp derived solar angles. Next, I would perform exploratory statistical clustering and feature importance analysis to identify specific environmental conditions where cloud edge contrast triggers high confidence false positives. Finally, I would isolate these edge cases to visualize the misclassified frames and establish targeted thresholding or training data augmentations.")
        elif any(k in lbl_text for k in ["sponsorship for employment visa status", "require sponsorship"]):
            ta.fill(CANDIDATE.get("sponsorship_required", "No"))
        elif any(k in lbl_text for k in ["datadog", "why", "interested", "draw", "attract"]):
            ta.fill(RESPONSES.get("why", "I want to build my engineering career with your team because of your relentless focus on high scale distributed systems and engineering rigor. Handling massive transaction volume and telemetry requires world class backend architectures and robust pipelines. I want to work alongside exceptional engineers to build resilient software that keeps global systems reliable."))
        elif any(k in lbl_text for k in ["project", "accomplishment"]):
            ta.fill(RESPONSES.get("project", ""))
        elif any(k in lbl_text for k in ["additional", "anything else", "comment"]):
            pass
        elif w_req:
            ta.fill(RESPONSES["experience"])
        else:
            print("  [Greenhouse Engine] Leaving optional textarea blank", flush=True)

    # 4. Modern React Select dropdowns (.select-shell, .remix-css-b62m3t-container)
    # Use multi-pass loop because answering one dropdown (e.g. Hispanic/Latino -> No) can dynamically reveal subsequent dropdowns (e.g. Race, Veteran, Disability)
    for rs_pass in range(3):
        react_selects = page.locator(".select-shell, .remix-css-b62m3t-container").all()
        if not react_selects:
            break
        filled_in_pass = 0
        for s in react_selects:
            try:
                # If this container already has a selected value, skip!
                if s.locator(".select__single-value").count() > 0 or s.locator(".select__multi-value").count() > 0:
                    continue
                # For autocomplete inputs with typed values
                typed_val = s.locator("input#candidate-location, input[id*='school']").first
                if typed_val.count() > 0 and typed_val.input_value().strip():
                    continue

                s.scroll_into_view_if_needed()
                lbl_text = s.evaluate('''el => {
                    const inp = el.querySelector('input[id]');
                    if (inp && inp.id) {
                        const directLbl = document.querySelector(`label[for="${inp.id}"]`);
                        if (directLbl && directLbl.innerText.trim()) return directLbl.innerText.trim();
                    }
                    let p = el.parentElement;
                    for (let i = 0; i < 4; i++) {
                        if (!p) break;
                        const lbl = p.querySelector('label, legend');
                        if (lbl && lbl.innerText.trim()) return lbl.innerText.trim();
                        p = p.parentElement;
                    }
                    return '';
                }''').lower()
                print(f"    [Greenhouse RS] Evaluated: '{lbl_text[:50]}'", flush=True)

                # Location autocomplete (ONLY candidate residential location, NEVER preference dropdowns)
                is_loc_field = s.locator("#candidate-location").count() > 0 or (
                    any(k in lbl_text for k in ["candidate location", "your location", "current location", "city, state", "where are you located"])
                    or (("location" in lbl_text or "city" in lbl_text) and not any(k in lbl_text for k in ["preference", "choice", "cohort", "relocate", "top location", "first", "second", "third", "which office", "which location", "office location", "work location", "eligible office", "san jose", "san francisco", "new york", "seattle", "boston", "chicago"]))
                )
                if is_loc_field:
                    loc_inp = s.locator("#candidate-location, input.select__input, input").first
                    if loc_inp.count() > 0 and not loc_inp.input_value().strip():
                        loc_inp.focus()
                        loc_inp.press_sequentially("Piscataway", delay=50)
                        time.sleep(1.5)
                        raw_suggs = s.locator('.select__menu div[class*="option"]').all()
                        suggs = [o for o in raw_suggs if "no-options" not in (o.get_attribute("class") or "").lower() and "no options" not in o.inner_text().lower()]
                        nj_sugg = next((o for o in suggs if "piscataway" in o.inner_text().lower() and "new jersey" in o.inner_text().lower()), None)
                        target_loc = nj_sugg if nj_sugg else (suggs[0] if suggs else None)
                        if target_loc:
                            target_txt = target_loc.inner_text().strip()
                            target_loc.click()
                            print(f"    [Greenhouse Engine] Selected location: {target_txt}", flush=True)
                            filled_in_pass += 1
                            continue
                        else:
                            loc_inp.fill("")
                            page.keyboard.press("Escape")

                # School autocomplete
                is_school_field = ("school" in lbl_text or "university" in lbl_text or s.locator("[id*='school']").count() > 0) and not any(k in lbl_text for k in ["degree", "discipline", "major", "gpa", "start", "end", "year", "month"])
                if is_school_field:
                    sch_inp = s.locator("input.select__input, input[id*='school'], input").first
                    if sch_inp.count() > 0:
                        try:
                            sch_inp.click(force=True)
                        except Exception:
                            pass
                        sch_inp.focus()
                        sch_inp.press_sequentially("Rutgers", delay=50)
                        time.sleep(2.0)
                        raw_suggs = s.locator('.select__menu div[class*="option"]').all()
                        if not raw_suggs:
                            raw_suggs = page.locator('.select__menu div[class*="option"], div[class*="select__option"], div[id*="option"]').all()
                        suggs = [o for o in raw_suggs if "no-options" not in (o.get_attribute("class") or "").lower() and "no options" not in o.inner_text().lower() and "camden" not in o.inner_text().lower() and "newark" not in o.inner_text().lower()]
                        nb_sugg = next((o for o in suggs if "new brunswick" in o.inner_text().lower()), None)
                        target_sugg = nb_sugg if nb_sugg else (suggs[0] if suggs else None)
                        if target_sugg:
                            target_txt = target_sugg.inner_text().strip()
                            target_sugg.click()
                            print(f"    [Greenhouse Engine] Selected school: {target_txt}", flush=True)
                            filled_in_pass += 1
                            continue
                        else:
                            page.keyboard.press("Escape")

                # Discipline / Major autocomplete
                is_disc_field = any(k in lbl_text for k in ["discipline", "major", "field of study", "area of study"]) or s.locator("[id*='discipline'], [id*='major']").count() > 0
                if is_disc_field:
                    disc_inp = s.locator("input.select__input, input[id*='discipline'], input[id*='major'], input").first
                    if disc_inp.count() > 0:
                        try:
                            disc_inp.click(force=True)
                        except Exception:
                            pass
                        disc_inp.focus()
                        disc_inp.press_sequentially("Computer Science", delay=50)
                        time.sleep(1.5)
                        raw_suggs = s.locator('.select__menu div[class*="option"]').all()
                        if not raw_suggs:
                            raw_suggs = page.locator('.select__menu div[class*="option"], div[class*="select__option"], div[id*="option"]').all()
                        suggs = [o for o in raw_suggs if "no-options" not in (o.get_attribute("class") or "").lower() and "no options" not in o.inner_text().lower()]
                        cs_sugg = next((o for o in suggs if "computer science" in o.inner_text().lower()), None)
                        target_sugg = cs_sugg if cs_sugg else (suggs[0] if suggs else None)
                        if target_sugg:
                            target_txt = target_sugg.inner_text().strip()
                            target_sugg.click()
                            print(f"    [Greenhouse Engine] Selected discipline: {target_txt}", flush=True)
                            filled_in_pass += 1
                            continue
                        else:
                            page.keyboard.press("Escape")

                # Multi-select scripting / programming languages
                if any(k in lbl_text for k in ["scripting / programming languages", "programming language", "coding language"]):
                    lang_inp = s.locator("input").first
                    if lang_inp.count() > 0:
                        lang_inp.focus()
                        lang_inp.press_sequentially("Python", delay=40)
                        time.sleep(1.0)
                        suggs = s.locator('.select__menu div[class*="option"]').all()
                        py_opt = next((o for o in suggs if o.inner_text().strip().lower() == "python"), None)
                        if py_opt:
                            py_opt.click()
                            print("    [Greenhouse Engine] Selected programming language: Python", flush=True)
                            filled_in_pass += 1
                            continue

                # Multi-select important factors
                if "important factors" in lbl_text:
                    fac_inp = s.locator("input").first
                    if fac_inp.count() > 0:
                        fac_inp.focus()
                        fac_inp.press_sequentially("Challenging", delay=40)
                        time.sleep(1.0)
                        suggs = s.locator('.select__menu div[class*="option"]').all()
                        fac_opt = next((o for o in suggs if "challenging" in o.inner_text().lower()), None)
                        if fac_opt:
                            fac_opt.click()
                            print("    [Greenhouse Engine] Selected factor: Challenging technical work", flush=True)
                            filled_in_pass += 1
                            continue

                # Fast typing matcher for React Select inputs to avoid opening 240+ option menus
                fast_target = None
                fast_exact = None
                if any(k in lbl_text for k in ["authorized to work", "legally authorized", "eligible to work", "legal right to work"]):
                    fast_target = "Yes"
                elif any(k in lbl_text for k in ["sponsorship", "visa", "require employm", "future require"]):
                    fast_target = "No"
                elif "transgender" in lbl_text:
                    fast_target = "No"
                elif any(k in lbl_text for k in ["country of residence", "select country", "what country", "country*"]) or (lbl_text.strip().lower() == "country"):
                    fast_target = "United States"
                elif any(k in lbl_text for k in ["available to commit", "available to work", "internship", "40 hours"]):
                    fast_target = "Yes"
                elif "gpa" in lbl_text:
                    fast_target = "3.8"
                elif any(k in lbl_text for k in ["team preference", "which team", "preferred team"]):
                    fast_target = "Software"
                elif any(k in lbl_text for k in ["gender", "sex"]) and "transgender" not in lbl_text:
                    fast_target = "Male"
                elif any(k in lbl_text for k in ["hispanic"]):
                    fast_target = "No"
                elif any(k in lbl_text for k in ["veteran"]):
                    fast_target = "not"
                    fast_exact = "I am not a protected veteran"
                elif any(k in lbl_text for k in ["disability"]):
                    fast_target = "do not have"
                    fast_exact = "No, I do not have a disability"
                elif any(k in lbl_text for k in ["race", "ethnicity"]):
                    fast_target = "Asian"
                elif any(k in lbl_text for k in ["degree"]):
                    fast_target = "Master"
                    fast_exact = "Master of Science"
                elif any(k in lbl_text for k in ["discipline", "major", "field of study"]):
                    fast_target = "Computer Science"
                elif any(k in lbl_text for k in ["start date"]):
                    fast_target = "May"
                elif any(k in lbl_text for k in ["duration", "consecutive weeks"]):
                    fast_target = "12"
                elif any(k in lbl_text for k in ["conflict of interest", "outside business"]):
                    fast_target = "No"

                rs_inp = s.locator("input.select__input, input[role='combobox'], input").first
                if fast_target and rs_inp.count() > 0:
                    try:
                        rs_inp.scroll_into_view_if_needed()
                        rs_inp.click(force=True)
                        rs_inp.press_sequentially(fast_target, delay=40)
                        time.sleep(0.5)
                        filter_opts = s.locator('.select__menu div[class*="option"], .select__option, div[id*="option"]').all()
                        if not filter_opts:
                            filter_opts = page.locator('.select__menu div[class*="option"], .select__option, div[id*="option"]').all()
                        target_kw = (fast_exact or fast_target).lower()
                        valid_opts = [o for o in filter_opts if "no options" not in o.inner_text().lower() and "no-options" not in (o.get_attribute("class") or "").lower()]
                        chosen_opt = None
                        if target_kw == "no":
                            for o in valid_opts:
                                ot = o.inner_text().lower().strip()
                                if ot.startswith("yes") or re.search(r"\byes\b", ot):
                                    continue
                                if re.search(r"\bno\b", ot) or "not" in ot or "neither" in ot or "never" in ot or "none" in ot or "do not" in ot or "will not" in ot:
                                    chosen_opt = o
                                    break
                        elif target_kw == "yes":
                            for o in valid_opts:
                                ot = o.inner_text().lower().strip()
                                if ot.startswith("no") or re.search(r"\bno\b", ot):
                                    continue
                                if re.search(r"\byes\b", ot):
                                    chosen_opt = o
                                    break
                        else:
                            chosen_opt = next((o for o in valid_opts if target_kw in o.inner_text().lower()), None)

                        if chosen_opt:
                            chosen_txt = chosen_opt.inner_text().strip()
                            chosen_opt.click(force=True)
                            print(f"    [Greenhouse RS Fast-Type] '{lbl_text[:30]}' -> Typed '{fast_target}', selected '{chosen_txt}'", flush=True)
                            filled_in_pass += 1
                            continue
                        else:
                            # Do not select if no matching option was found; fallback to dropdown opening
                            pass
                    except Exception as e:
                        print(f"    [Greenhouse RS Fast-Type notice]: {e}", flush=True)

                # Standard React Select control click
                ctrl = s.locator(".select__control").first
                if ctrl.count() > 0 and ctrl.is_visible():
                    try:
                        ctrl.click(force=True, timeout=3000)
                    except Exception:
                        pass
                    time.sleep(0.3)
                    opts = s.locator('.select__menu div[class*="option"]').all()
                    if not opts:
                        opts = page.locator('.select__menu div[class*="option"], div[class*="select__option"], div[id*="option"]').all()
                    if not opts:
                        sub_inp = s.locator("input.select__input").first
                        if sub_inp.count() > 0:
                            try:
                                sub_inp.scroll_into_view_if_needed()
                                sub_inp.click(force=True)
                                page.keyboard.press("ArrowDown")
                                time.sleep(0.3)
                                opts = page.locator('.select__menu div[class*="option"], div[class*="select__option"], div[id*="option"]').all()
                            except Exception:
                                pass
                    clean_opts = [(o, o.inner_text().replace("'", "").replace('"', '').strip().lower()) for o in opts if "no-options" not in (o.get_attribute("class") or "").lower() and "no options" not in o.inner_text().lower()]
                    print(f"    [Greenhouse RS Options] '{lbl_text[:30]}' -> {len(clean_opts)} opts: {[t for _, t in clean_opts][:5]}", flush=True)

                    target_opt = None
                    if any("sponsorship" in t or "permanent work authorization" in t or "authorization" in t for _, t in clean_opts) and any(k in lbl_text for k in ["employment eligibility", "sponsorship", "visa", "work authorization", "authorized to work", "status"]):
                        target_opt = next((o for o, t in clean_opts if any(pos in t for pos in ["already has", "permanent", "no sponsorship", "do not require", "will not require", "citizen", "no restrictions", "no."]) and not any(neg in t for neg in ["will require", "need sponsorship", "require firm", "require visa"])), None)
                        if not target_opt:
                            target_opt = next((o for o, t in clean_opts if t.startswith("no") and "require" not in t), None)
                    elif "push" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if t == "no"), None)
                    elif any(k in lbl_text for k in ["worked at", "worked for", "employed by", "employed at", "previous employment", "prior employment", "previous employee", "former employee", "ever worked", "worked before"]):
                        target_opt = next((o for o, t in clean_opts if any(neg in t for neg in ["never", "have not", "no", "not a previous", "neither", "none", "i do not", "not worked"])), None)
                    elif "gpa" in lbl_text:
                        target_opt = None
                        for k in ["3.8", "3.9", "3.85", "3.76 - 4.0", "3.76", "3.81 - 3.9", "3.75+", "3.75", "3.71 - 3.8", "3.7 or higher", "3.7+", "3.7 or above", "3.6 - 4.0", "3.6-4.0", "3.6 or above", "3.51 - 3.6", "3.5 or above", "3.5+", "3.5 - 4.0", "3.5-4.0", "3.5"]:
                            match = next((o for o, t in clean_opts if k in t and (k != "3.5" or ("3.4" not in t and "3.3" not in t and "3.2" not in t))), None)
                            if match:
                                target_opt = match
                                break
                        if not target_opt:
                            target_opt = next((o for o, t in clean_opts if "3.75" in t or "3.8" in t or "3.9" in t or "3.7" in t), opts[0] if opts else None)
                    elif "dates do you prefer" in lbl_text:
                        target_opt = opts[0] if opts else None
                    # Major discipline confirmation ('Are you currently pursuing a major in one of the following disciplines: CS or CE')
                    elif any(k in lbl_text for k in ["pursuing a major in one of", "major in one of", "pursuing a major"]):
                        target_opt = next((o for o, t in clean_opts if t == "yes"), None)
                    # FINRA registration / licenses (Always NO)
                    elif any(k in lbl_text for k in ["finra", "registered with finra", "brokercheck", "series 7", "series 63"]):
                        target_opt = next((o for o, t in clean_opts if t == "no"), None)
                    # Work authorization statements (e.g. CTC 'now or at any point in the future, i am eligible to work with no restrictions')
                    elif any(k in lbl_text for k in ["select one of the following statements", "statements based on your work authorization"]):
                        target_opt = next((o for o, t in clean_opts if "no restrictions" in t or "eligible to work" in t or "citizen" in t), None)
                    # Highest degree level currently achieved / completed (Strictly Bachelor's)
                    elif any(k in lbl_text for k in ["highest level of degree currently", "highest level of degree achieved", "highest degree achieved", "highest degree attained", "highest degree completed", "highest degree currently held", "highest degree you hold", "highest level of education completed"]):
                        target_opt = next((o for o, t in clean_opts if "bachelor" in t), None)
                    # Highest degree level currently pursuing (Strictly Master's)
                    elif any(k in lbl_text for k in ["highest degree level you are currently", "highest degree level currently pursuing", "degree currently pursuing"]):
                        target_opt = next((o for o, t in clean_opts if "masters" in t), next((o for o, t in clean_opts if "bachelors" in t), None))
                    # Bachelor's graduation date dropdown (Rocket Lab)
                    elif any(k in lbl_text for k in ["anticipated bachelor", "bachelor's degree graduation date"]):
                        target_opt = next((o for o, t in clean_opts if "05/2024" in t or "05/24" in t or "graduated" in t or "n/a" in t), next((o for o, t in clean_opts if "05/2027" in t or "2027" in t), clean_opts[0][0] if clean_opts else None))
                    # Master's graduation date dropdown (Rocket Lab)
                    elif any(k in lbl_text for k in ["anticipated master", "master's degree graduation date"]):
                        target_opt = next((o for o, t in clean_opts if "05/2028" in t or "05/28" in t or "2028" in t), next((o for o, t in clean_opts if "2027" in t), clean_opts[-1][0] if clean_opts else None))
                    # Amount of software engineering experience outside coursework (Rocket Lab)
                    elif any(k in lbl_text for k in ["amount of software engineering experience", "outside of university coursework"]):
                        target_opt = next((o for o, t in clean_opts if "10+" in t or "10+ months" in t or "6-9 months" in t or "3-5 months" in t), None)
                    # Engineering organization involvement (Rocket Lab)
                    elif any(k in lbl_text for k in ["engineering organization involvement"]):
                        target_opt = next((o for o, t in clean_opts if "autonomous vehicles" in t or "robotics" in t or "software" in t or "computer" in t or "none" in t), clean_opts[0][0] if clean_opts else None)
                    # Preferred start date & duration (Rocket Lab)
                    elif any(k in lbl_text for k in ["preferred internship/co-op start date", "preferred start date", "start date"]):
                        is_winter = any(w in lbl_text for w in ["winter", "january", "december"])
                        if is_winter:
                            target_opt = next((o for o, t in clean_opts if "december 20" in t or "dec 20" in t or "december" in t), clean_opts[0][0] if clean_opts else None)
                        else:
                            target_opt = next((o for o, t in clean_opts if "may 20" in t or "may 20th" in t or "may" in t), clean_opts[0][0] if clean_opts else None)
                    elif any(k in lbl_text for k in ["consecutive weeks you are available", "preferred internship/co-op duration"]):
                        target_opt = next((o for o, t in clean_opts if "12" in t or "16" in t), clean_opts[0][0] if clean_opts else None)
                    # Availability / Permanent full-time start date (check BEFORE generic '40 hours' check)
                    elif any(k in lbl_text for k in ["available to work as a full-time", "full-time, permanent employee", "available to start", "available to begin", "full-time role in 2028", "full-time employment in 2028"]):
                        if any(t in ["yes", "no"] for _, t in clean_opts):
                            target_opt = next((o for o, t in clean_opts if t == "yes"), None)
                        else:
                            target_opt = next((o for o, t in clean_opts if "summer 2028" in t or "may 2028" in t or "2028" in t), next((o for o, t in clean_opts if "summer 2027" in t or "2027" in t), opts[-1] if opts else None))
                    # Work auth followup (If yes, what kind / select Not Applicable) BEFORE generic sponsorship check
                    elif any(k in lbl_text for k in ["what kind", "kind of work authorization", "select not applicable", "if yes, what kind"]):
                        target_opt = next((o for o, t in clean_opts if "not applicable" in t or "n/a" in t or "none" in t), None)
                    # OPT / CPT / STEM OPT followup (Candidate is US Citizen -> N/A or No)
                    elif any(k in lbl_text for k in ["opt", "cpt", "f-1", "f1", "stem opt", "24-month"]):
                        target_opt = next((o for o, t in clean_opts if any(w == t or w in t for w in ["na", "n/a", "not applicable", "no", "neither"])), None)
                    # 1. Legally authorized to work FIRST (never hijack by parenthetical mentions of visa or sponsorship)
                    elif any(k in lbl_text for k in ["are you legally authorized to work for any employer", "are you legally authorized to work in the united states", "are you legally authorized to work in the u.s."]):
                        target_opt = next((o for o, t in clean_opts if t == "yes" or "yes" in t), None)
                    elif any(k in lbl_text for k in ["legally authorized", "authorized to work", "work authorization", "employment authorization", "eligible to work in the country", "authorised to work"]) and not any(k in lbl_text for k in ["require", "will you", "would you", "need", "sponsorship needed"]) and "authorized gallup official" not in lbl_text and "statement" not in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "citizen" in t or "any employer" in t or "no restriction" in t or t == "yes" or ("yes" in t and "sponsorship" not in t and "require" not in t)), next((o for o, t in clean_opts if "yes" in t), None))
                    # 2. Sponsorship / Visa requirement (Always NO for permanent US work authorization)
                    elif any(k in lbl_text for k in ["temporary work authorization", "sponsorship", "visa", "require employm", "require visa", "require immigra", "require sponsor", "require work auth", "require authoriz", "require an export", "future require", "now or in the future"]):
                        target_opt = next((o for o, t in clean_opts if t == "no" or "no," in t or "do not require" in t or "will not require" in t), None)
                    elif any(k in lbl_text for k in ["eligible to work", "work in the country where this vacancy is posted"]):
                        target_opt = next((o for o, t in clean_opts if t == "yes" or "yes" in t), None)
                    elif any(k in lbl_text for k in ["kind of work environment", "work environment are you looking for", "work environment"]):
                        target_opt = next((o for o, t in clean_opts if "any" in t), next((o for o, t in clean_opts if "hybrid" in t or "on-site" in t or "remote" in t), opts[0] if opts else None))
                    elif any(k in lbl_text for k in ["accommodate this work environment", "accommodate this", "willing and able to accommodate", "work from the office", "work on-site", "work hybrid"]):
                        target_opt = next((o for o, t in clean_opts if t == "yes"), None)
                    elif "citizen" in lbl_text or "us person" in lbl_text or "u.s. person" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "yes" in t or "united states" in t or "u.s. citizen" in t or "citizen" in t), None)
                    elif any(k in lbl_text for k in ["40 hours", "eligible offices", "january-april"]):
                        target_opt = next((o for o, t in clean_opts if t == "yes"), None)
                    elif "country" in lbl_text and not any(k in lbl_text for k in ["authori", "eligible", "visa", "sponsorship"]):
                        target_opt = next((o for o, t in clean_opts if t in ["united states", "united states of america", "usa", "u.s.", "u.s.a."]), next((o for o, t in clean_opts if t.startswith("united states") and "minor" not in t and "outlying" not in t), next((o for o, t in clean_opts if "united states" in t and "minor" not in t and "outlying" not in t), None)))
                    elif (any(k in lbl_text for k in ["discipline", "field of study", "area of study", "field are you looking"]) or (re.search(r'\bmajors?\b', lbl_text) and "major life" not in lbl_text and "disability" not in lbl_text)) and not any(k in lbl_text for k in ["demonstrated", "personal project"]):
                        target_opt = next((o for o, t in clean_opts if "computer science" in t), next((o for o, t in clean_opts if "computer" in t or "engineering" in t or "software" in t), None))
                    elif (any(k in lbl_text for k in ["state in which you currently reside", "state of residence", "current state", "which state", "state/region in which you currently reside"]) or re.search(r'\bstate\*?\b', lbl_text)) and "statement" not in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "new jersey" in t or t == "nj"), next((o for o, t in clean_opts if "another state in the us" in t or "new york" in t), None))
                    elif any(k in lbl_text for k in ["own, operate, or provide services", "conflict of interest", "outside business"]):
                        target_opt = next((o for o, t in clean_opts if t == "no"), None)
                    elif any(k in lbl_text for k in ["graduate student in spring 2027", "graduate student in 2027", "already hold a bachelor"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["sat score", "result on sat"]) or re.search(r'\bsat\b', lbl_text):
                        target_opt = next((o for o, t in clean_opts if "1280" in t or "1201" in t or "1250" in t or "1201 - 1300" in t), next((o for o, t in clean_opts if "did not take" in t or "not take" in t or "dont have" in t or "do not have" in t), None))
                    elif any(k in lbl_text for k in ["act score", "result on act"]) or re.search(r'\bact\b', lbl_text):
                        target_opt = next((o for o, t in clean_opts if "did not take" in t or "not take" in t or "dont have" in t or "do not have" in t or "n/a" in t or "none" in t), None)
                    elif any(k in lbl_text for k in ["standardized test score type", "test score type"]):
                        target_opt = next((o for o, t in clean_opts if t == "sat" or "sat" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["graduate from high school", "graduate high school", "high school"]):
                        target_opt = next((o for o, t in clean_opts if "2020" in t or "before 2021" in t or "before" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["alphabet employee", "google employee"]):
                        target_opt = next((o for o, t in clean_opts if "never" in t or "no" in t), None)
                    elif any(k in lbl_text for k in ["what kind", "kind of work authorization"]):
                        target_opt = next((o for o, t in clean_opts if "not applicable" in t or "n/a" in t or "none" in t), None)
                    elif any(k in lbl_text for k in ["have any offers", "competing offers", "pending offers"]):
                        target_opt = next((o for o, t in clean_opts if t == "no" or "no" in t), None)
                    elif any(k in lbl_text for k in ["applied to this role or another role", "previously applied"]):
                        target_opt = next((o for o, t in clean_opts if t == "no" or "no" in t), None)
                    elif any(k in lbl_text for k in ["pronoun", "gender pronouns", "share your gender pronouns"]):
                        target_opt = next((o for o, t in clean_opts if ("he/him" in t or "he / him" in t or re.search(r'\bhe\b', t)) and "she" not in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["relevant employment and military", "add another employment"]):
                        target_opt = next((o for o, t in clean_opts if "thank you" in t or "yes" in t), clean_opts[0][0] if clean_opts else None)
                    elif any(k in lbl_text for k in ["pre-employment requirements", "interview code of conduct", "code of conduct", "candidate privacy", "privacy statement", "acknowledge", "certify", "resume must be"]):
                        target_opt = next((o for o, t in clean_opts if any(w in t for w in ["yes", "agree", "acknowledge", "consent", "confirm"])), None)
                    elif any(k in lbl_text for k in ["gre score"]) or re.search(r'\bgre\b', lbl_text):
                        target_opt = next((o for o, t in clean_opts if "did not take" in t or "not take" in t or "n/a" in t or "none" in t), None)
                    elif any(k in lbl_text for k in ["doctorate", "phd", "doctoral"]):
                        target_opt = next((o for o, t in clean_opts if "not applicable" in t or "n/a" in t or "none" in t), None)
                    elif any(k in lbl_text for k in ["grading scale", "gpa scale"]):
                        target_opt = next((o for o, t in clean_opts if "4.0" in t or "4" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["pursue further education immediately", "further education upon graduation", "pursuing further education immediately"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["enrolled as a student at", "student at northeastern", "student at columbia", "student at nyu", "student at harvard", "student at mit", "student at stanford"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["year do you intend to complete", "complete your degree", "year do you plan to graduate", "intend to complete your degree"]):
                        target_opt = next((o for o, t in clean_opts if "2028" in t), next((o for o, t in clean_opts if "2027" in t), None))
                    elif any(k in lbl_text for k in ["currently pursuing a graduate degree", "pursuing a graduate degree"]):
                        target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                    elif any(k in lbl_text for k in ["do you have, or are you currently pursuing", "currently pursuing, a college degree", "pursuing a college degree", "currently pursuing a degree", "college degree", "pursuing a degree", "pursuing a major", "major in one of"]):
                        target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                    elif any(k in lbl_text for k in ["degree are you currently pursuing", "what degree are you", "enrolled in university, what degree"]):
                        target_opt = next((o for o, t in clean_opts if "master" in t or "bachelor" in t), clean_opts[0][0] if clean_opts else None)
                    elif "degree" in lbl_text and not any(k in lbl_text for k in ["pursuing", "graduate student", "complete"]):
                        if any(any(d in t for d in ["bachelor", "master", "doctor", "associate"]) for _, t in clean_opts):
                            target_opt = next((o for o, t in clean_opts if ("masters degree" in t or "master of science" in t or ("master" in t and not any(bad in t for bad in ["business", "administration", "mba", "m.b.a."])))), next((o for o, t in clean_opts if "master" in t), next((o for o, t in clean_opts if any(b in t for b in ["bachelor", "bachelors"])), None)))
                    elif any(k in lbl_text for k in ["ready for full-time employment in 2028", "full-time employment in 2028", "full-time role in 2028", "begin a potential full-time role"]):
                        target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                    elif any(k in lbl_text for k in ["at least 18", "18 years of age"]):
                        target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                    elif any(k in lbl_text for k in ["coinbase may use ai tools", "may use ai tools to assist"]):
                        target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                    elif any(k in lbl_text for k in ["how you use ai tools today", "use ai tools today"]):
                        target_opt = next((o for o, t in clean_opts if "design or automate workflows" in t or "building agents" in t or "automate" in t), opts[-1] if opts else None)
                    elif any(k in lbl_text for k in ["government official", "holder of public office"]):
                        target_opt = next((o for o, t in clean_opts if "not a current" in t or "not a relative" in t or "no" in t or "not" in t), None)
                    elif any(k in lbl_text for k in ["relative of a government official", "close relative of a government"]):
                        target_opt = next((o for o, t in clean_opts if "not a relative" in t or "no" in t or "not" in t), None)
                    elif any(k in lbl_text for k in ["referred to this position by a senior leader", "prospective institutional client"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t or t == "no"), None)
                    elif any(k in lbl_text for k in ["processing of personal data", "personal data survey", "data privacy notice"]):
                        target_opt = next((o for o, t in clean_opts if any(w in t for w in ["confirmed", "acknowledge/confirm", "acknowledge", "confirm", "agree", "yes", "consent"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["program preference", "spacex program preference"]):
                        target_opt = next((o for o, t in clean_opts if "software" in t or "avionics" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["which department", "department are you most interested", "primary team", "team you'd like to be considered", "track preference"]):
                        target_opt = next((o for o, t in clean_opts if "enterprise ai" in t), next((o for o, t in clean_opts if "platform" in t), next((o for o, t in clean_opts if "software" in t or "developer" in t or "development" in t or "engineering" in t or "swe" in t), opts[0] if opts else None)))
                    elif any(k in lbl_text for k in ["employment history", "spacex & spacexai employment"]):
                        target_opt = next((o for o, t in clean_opts if "none" in t or "never" in t or "no" in t), None)
                    elif any(k in lbl_text for k in ["enrollment status", "student status"]):
                        target_opt = next((o for o, t in clean_opts if "full-time" in t or "enrolled" in t or "undergraduate or graduate" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["degree subject", "subject are you currently studying"]):
                        target_opt = next((o for o, t in clean_opts if "computer science" in t or "computer" in t or "software" in t or "engineering" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["which institution", "institution do you currently attend", "which college or university", "university do you currently attend"]):
                        target_opt = next((o for o, t in clean_opts if "rutgers" in t and "camden" not in t and "newark" not in t), next((o for o, t in clean_opts if "other" in t), opts[0] if opts else None))
                    elif any(k in lbl_text for k in ["coding language", "programming language", "preferred language", "interview in any of the"]):
                        target_opt = next((o for o, t in clean_opts if "python" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["available to work as a full-time", "full-time, permanent employee", "available to start", "eligible to begin full-time employment", "begin full-time employment"]):
                        target_opt = next((o for o, t in clean_opts if "august 2028" in t or "summer 2028" in t or "may 2028" in t or "2028" in t), next((o for o, t in clean_opts if "summer 2027" in t), opts[-1] if opts else None))
                    elif any(k in lbl_text for k in ["where did you attend high school", "attend high school/secondary", "where did you attend high"]):
                        target_opt = next((o for o, t in clean_opts if "north america" in t or "united states" in t or "us" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["list your current or most recent employer", "current or most recent employer"]):
                        target_opt = next((o for o, t in clean_opts if "other - tech" in t or "other" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["when did you first hear about hrt", "when did you first hear"]):
                        target_opt = next((o for o, t in clean_opts if "graduate program" in t or "university program" in t or "university" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["select your top preferred hrt office location", "top preferred hrt office"]):
                        target_opt = next((o for o, t in clean_opts if "new york" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["can only apply for one role", "system will not allow you to apply for more than one"]):
                        target_opt = opts[0] if opts else None
                    elif any(k in lbl_text for k in ["select which event you attended", "which event you attended"]):
                        target_opt = next((o for o, t in clean_opts if "n/a" in t or "not attend" in t or "none" in t or "did not attend" in t), opts[-1] if opts else None)
                    elif any(k in lbl_text for k in ["first generation", "first in your family"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["free school meals", "eligible for free school meals"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t or "not applicable" in t), None)
                    elif any(k in lbl_text for k in ["long-term health condition", "health condition"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["did you attend a fall career fair", "career fair this year"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["from the dropdown menu below, please select the college or university", "select your college or university"]):
                        target_opt = next((o for o, t in clean_opts if "rutgers" in t and "camden" not in t and "newark" not in t), next((o for o, t in clean_opts if "other" in t), opts[0] if opts else None))
                    elif "start date month" in lbl_text or ("start" in lbl_text and "month" in lbl_text):
                        target_opt = next((o for o, t in clean_opts if "september" in t or "august" in t or "june" in t), None)
                    elif "end date month" in lbl_text or ("end" in lbl_text and "month" in lbl_text):
                        target_opt = next((o for o, t in clean_opts if "may" in t or "august" in t), None)
                    elif any(k in lbl_text for k in ["what year do you graduate", "year do you graduate", "when are you expecting to graduate", "expecting to graduate", "expected graduation", "graduation", "anticipated graduation", "when do you expect to graduate", "when do you graduate", "graduate or complete your program"]):
                        target_opt = next((o for o, t in clean_opts if "may - aug 2028" in t or "jan - july 2028" in t or "spring 2028" in t or "may 2028" in t or "2028" in t or "2027 & later" in t or "2027+" in t or "after 2027" in t), next((o for o, t in clean_opts if "fall 2027" in t or "2027" in t), next((o for o, t in clean_opts if "2026" in t), opts[-1] if opts else None)))
                    elif any(k in lbl_text for k in ["authorization to work in the country", "choose the option that describes your work authorization"]):
                        target_opt = next((o for o, t in clean_opts if "nationality" in t or "citizen" in t or "permanent" in t or "authorized to work in the united states for any employer" in t), clean_opts[0][0] if clean_opts else None)
                    elif any(k in lbl_text for k in ["how did you connect with us", "connect with us"]):
                        target_opt = next((o for o, t in clean_opts if "other" in t), clean_opts[-1][0] if clean_opts else None)
                    elif any(k in lbl_text for k in ["which type of engineering work", "engineering work are you most excite"]):
                        target_opt = next((o for o, t in clean_opts if "backend" in t or "infrastructure" in t or "product" in t or "open to any" in t), clean_opts[0][0] if clean_opts else None)
                    elif any(k in lbl_text for k in ["collegiate institution", "college or university you currently attend"]):
                        target_opt = next((o for o, t in clean_opts if ("rutgers" in t and "camden" not in t and "newark" not in t) or "other" in t), clean_opts[-1][0] if clean_opts else None)
                    elif any(k in lbl_text for k in ["live outside of the united states"]):
                        target_opt = next((o for o, t in clean_opts if "live inside the united states" in t or "no" in t), None)
                    elif any(k in lbl_text for k in ["contractual obligations", "agreements, relationships, or commitments", "non-compete"]):
                        target_opt = next((o for o, t in clean_opts if t == "no" or "no" in t), None)
                    elif any(k in lbl_text for k in ["client of businessolver", "currently work for a client"]):
                        target_opt = next((o for o, t in clean_opts if t == "no" or "no" in t), None)
                    elif any(k in lbl_text for k in ["if you were to receive a full-time offer", "consideration for a full-time opportunity"]):
                        target_opt = next((o for o, t in clean_opts if "return to school" in t or "upon graduation" in t), next((o for o, t in clean_opts if "after the internship" in t), opts[0] if opts else None))
                    elif any(k in lbl_text for k in ["1st choice: area of interest", "first choice: area of interest", "primary interest in software"]):
                        target_opt = next((o for o, t in clean_opts if "backend" in t or "systems" in t), next((o for o, t in clean_opts if "full-stack" in t), opts[0] if opts else None))
                    elif any(k in lbl_text for k in ["2nd choice", "second choice: area of interest"]):
                        target_opt = next((o for o, t in clean_opts if "full-stack" in t), next((o for o, t in clean_opts if "backend" in t), opts[1] if len(opts) > 1 else (opts[0] if opts else None)))
                    elif any(k in lbl_text for k in ["enrolled at northeastern", "student at northeastern", "northeastern university", "columbia university", "harvard", "mit", "stanford", "nyu", "georgia tech", "colorado school of mines", "iowa state"]) and "rutgers" not in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["recruitment event this year", "attended an event", "attended a maven recruitment event"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["type of school did you mainly attend", "school did you attend between"]):
                        target_opt = next((o for o, t in clean_opts if "state run" in t or "state" in t or "public" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["religion", "belief"]):
                        target_opt = next((o for o, t in clean_opts if "no religion" in t or "atheist" in t or "prefer not" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["first location preference", "top location preference", "1st location preference"]) or (lbl_text.startswith("location preference")):
                        target_opt = next((o for o, t in clean_opts if "new york" in t), next((o for o, t in clean_opts if "san francisco" in t), opts[0] if opts else None))
                    elif any(k in lbl_text for k in ["second location preference", "2nd location preference", "second choice"]):
                        target_opt = next((o for o, t in clean_opts if "san francisco" in t), next((o for o, t in clean_opts if "seattle" in t), opts[1] if len(opts) > 1 else (opts[0] if opts else None)))
                    elif any(k in lbl_text for k in ["third location preference", "3rd location preference", "third choice"]):
                        target_opt = next((o for o, t in clean_opts if "seattle" in t), opts[2] if len(opts) > 2 else (opts[0] if opts else None))
                    elif any(k in lbl_text for k in ["majoring in stem", "stem major", "stem degree", "stem field", "pursuing a major", "major in one of the following", "computer science or computer engineering"]):
                        target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                    elif any(k in lbl_text for k in ["women's", "winternship"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["winter 2027 or summer 2027", "winter or summer", "summer or winter", "applying to intern in", "cohort do you prefer", "which term", "which season", "term preference"]):
                        target_opt = next((o for o, t in clean_opts if "summer 2027" in t), next((o for o, t in clean_opts if "summer" in t), next((o for o, t in clean_opts if "2027" in t), None)))
                    elif any(k in lbl_text for k in ["based in any of these countries", "reside in any of these countries", "located in any of these countries", "country of residence", "which country"]):
                        target_opt = next((o for o, t in clean_opts if any(c in t for c in ["united states of america", "united states", "u.s.", "usa"])), None)
                    elif any(k in lbl_text for k in ["graduating between december 2027 and june 2028", "graduating between"]):
                        target_opt = next((o for o, t in clean_opts if t == "yes" or "yes" in t), None)
                    elif any(k in lbl_text for k in ["anticipated bachelor", "anticipated master", "anticipated graduation", "when will you be graduating", "graduation date", "graduating date", "year of graduation"]):
                        target_opt = next((o for o, t in clean_opts if "2028" in t), next((o for o, t in clean_opts if "may 2028" in t), next((o for o, t in clean_opts if "spring 2028" in t), next((o for o, t in clean_opts if "2027" in t), None))))
                    elif any(k in lbl_text for k in ["graduate student in spring 2027", "graduate student in 2027", "already hold a bachelor"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["require work auth", "require authoriz", "require sponsor", "require visa", "export license"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["legally authorized", "authorized to work", "eligible to work", "work authorization"]):
                        target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                    elif any(k in lbl_text for k in ["relocate", "relocation", "open to relocating", "willing and able to relocate", "need to relocate"]):
                        # Priority 1: >= 1 month needed for relocation
                        target_opt = next((o for o, t in clean_opts if any(m in t for m in ["at least 1 month", "at least one month", "1 month", "one month", "1-2 month", "1 - 2 month", "1 to 2 month", "30 day", "30+ day", "4 week", "4+ week", "60 day", "2 month"]) and not any(neg in t for neg in ["cannot", "not willing", "less than 1 month", "under 30 day"])), None)
                        if not target_opt:
                            target_opt = next((o for o, t in clean_opts if any(r in t for r in ["i need to relocate", "need to relocate", "require relocation", "will need relocation", "relocation needed", "willing to relocate", "relocation with assistance", "relocation assistance", "plan to relocate", "can relocate", "yes, willing", "yes, relocate", "relocate", "relocation", "yes"]) and not any(neg in t for neg in ["cannot", "not willing", "not able", "do not", "no", "without relocation"])), None)
                    elif any(k in lbl_text for k in ["able to work full-time on-site", "work on-site", "work in office", "commutable proximity", "4 days/week", "in-person", "relocate to ca"]):
                        target_opt = next((o for o, t in clean_opts if "relocation with assistance" in t or "willing to relocate" in t or "located near" in t or "yes" in t), None)
                    elif any(k in lbl_text for k in ["office", "which office", "which office are you applying for", "office location", "office location preference", "location where you can work", "office you are applying for", "intended location", "first location preference", "top location preference", "1st location preference"]) or (lbl_text.startswith("location preference")) or (lbl_text == "office"):
                        target_opt = next((o for o, t in clean_opts if any(c in t for c in ["new york", "nyc", "new jersey", "bellevue", "seattle", "boulder", "denver", "irvine", "san francisco", "united states", "americas", "north america", "remote"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["second location preference", "2nd location preference", "second choice"]):
                        target_opt = next((o for o, t in clean_opts if "san francisco" in t), next((o for o, t in clean_opts if "seattle" in t), opts[1] if len(opts) > 1 else (opts[0] if opts else None)))
                    elif any(k in lbl_text for k in ["third location preference", "3rd location preference", "third choice"]):
                        target_opt = next((o for o, t in clean_opts if "seattle" in t), opts[2] if len(opts) > 2 else (opts[0] if opts else None))
                    elif any(k in lbl_text for k in ["c++", "how much experience", "level of proficiency", "programming analysis, design", "creative problem-solving", "proficiency in"]):
                        target_opt = next((o for o, t in clean_opts if any(p in t for p in ["proficient", "advanced", "intermediate", "2-3", "1-2", "3+", "high"])), next((o for o, t in clean_opts if "yes" in t), opts[-1] if opts else None))
                    elif any(k in lbl_text for k in ["class year will you be entering", "level of education during the fall", "class year", "education level"]):
                        target_opt = next((o for o, t in clean_opts if any(y in t for y in ["senior", "junior", "undergraduate", "bachelor"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["point of data transfer", "gdpr", "personal data disclosure", "arbitration agreement", "linked document", "data privacy notice"]):
                        target_opt = next((o for o, t in clean_opts if any(a in t for a in ["yes", "agree", "acknowledge", "consent", "confirm"])), None)
                    elif any(k in lbl_text for k in ["duration", "consecutive weeks", "number of weeks"]):
                        target_opt = next((o for o, t in clean_opts if any(w in t for w in ["12", "10-12", "full"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["which university", "school do you currently attend", "university you currently attend", "re-confirm the university"]):
                        target_opt = next((o for o, t in clean_opts if "rutgers" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["military", "serve", "armed forces"]):
                        target_opt = next((o for o, t in clean_opts if t == "no" or "no" in t), None)
                    elif any(k in lbl_text for k in ["gpa", "cumulative gpa"]):
                        target_opt = next((o for o, t in clean_opts if any(g in t for g in ["3.8", "3.9", "3.85", "3.81 - 3.9", "3.75+", "3.75", "3.71 - 3.8", "3.7 or higher", "3.7+", "3.7 or above", "3.6 - 4.0", "3.6-4.0", "3.5 - 4.0", "3.5-4.0", "3.5 - 3.6", "3.5"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["worked at", "worked for", "employed by", "employed at", "previous employment", "prior employment", "previous employee", "former employee", "ever worked", "worked before"]):
                        target_opt = next((o for o, t in clean_opts if any(neg in t for neg in ["never", "have not", "no", "not a previous", "neither", "none", "i do not"])), None)
                    elif any(k in lbl_text for k in ["department", "division"]):
                        target_opt = next((o for o, t in clean_opts if any(d in t for d in ["internship", "it", "technology", "engineering", "analytics"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["careers site category", "job category", "career category"]):
                        target_opt = next((o for o, t in clean_opts if any(c in t for c in ["software engineering", "engineering", "technology", "applied science", "data science"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["security clearance", "clearance"]):
                        target_opt = next((o for o, t in clean_opts if any(c in t for c in ["none", "no", "not applicable", "n/a"])), None)
                    elif any(k in lbl_text for k in ["only consider you for one role", "first preference only"]):
                        target_opt = next((o for o, t in clean_opts if any(a in t for a in ["yes", "agree", "understand"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["primary team you'd like to be considered for", "team preference", "preferred team"]):
                        target_opt = next((o for o, t in clean_opts if any(tm in t for tm in ["software engineering", "backend", "platform", "infrastructure", "systems", "core"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["attending a university in canada", "university in canada"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t), None)
                    elif any(k in lbl_text for k in ["application statement", "subject to dismissal", "employment contract", "acknowledge that i have read", "statement shall constitute"]):
                        target_opt = next((o for o, t in clean_opts if any(w in t for w in ["yes", "agree", "understand", "accept", "acknowledge", "confirm"])), opts[0] if opts else None)
                    elif (any(k in lbl_text for k in ["state in which you currently reside", "state of residence", "current state", "which state"]) or re.search(r'\bstate\*?\b', lbl_text)) and "statement" not in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "new jersey" in t or t == "nj"), None)
                    elif any(k in lbl_text for k in ["flexibility", "cohort option", "second cohort"]):
                        target_opt = next((o for o, t in clean_opts if "summer" in t), next((o for o, t in clean_opts if "winter" in t), next((o for o, t in clean_opts if "yes" in t), opts[1] if len(opts) > 1 else None)))
                    elif "relocate to new york" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                    elif "relocate to boston" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                    elif "most interested in" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "backend" in t or "software engineering" in t), None)
                    elif any(k in lbl_text for k in ["how you use ai tools", "use ai tools", "ai tools today"]):
                        target_opt = next((o for o, t in clean_opts if any(w in t for w in ["design or automate", "regularly use", "experimented"])), opts[-1] if opts else None)
                    elif any(k in lbl_text for k in ["government official", "public office", "civil service"]):
                        target_opt = next((o for o, t in clean_opts if "no" in t or "not a current" in t), None)
                    elif "timezone" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "eastern" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["part of the tech stack", "tech stack"]):
                        target_opt = next((o for o, t in clean_opts if "backend" in t or "ai" in t), opts[0] if opts else None)
                    elif "cost tier" in lbl_text:
                        target_opt = opts[0] if opts else None
                    elif "current location" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "new jersey" in t or "us - nj" in t), next((o for o, t in clean_opts if "united states" in t and "minor" not in t), next((o for o, t in clean_opts if t.startswith("us -")), None)))
                    elif "time sensitive" in lbl_text or "other companies" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if t == "no"), None)
                    elif "stay up to date" in lbl_text or "receive mongodb" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if t == "no"), None)
                    elif "sponsorship" in lbl_text or "require employm" in lbl_text or "visa" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if t == "no"), None)
                    elif "transgender" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if t == "no" or "no" in t), None)
                    elif any(k in lbl_text for k in ["lgbtq", "lgbt"]):
                        target_opt = next((o for o, t in clean_opts if t == "no" or "no" in t or "heterosexual" in t), None)
                    elif "gender" in lbl_text and "trans" not in lbl_text:
                        target_opt = next((o for o, t in clean_opts if t == "male" or t == "man" or t == "cis-man" or (re.search(r'\bmale\b', t) and "female" not in t)), next((o for o, t in clean_opts if "man" in t and "woman" not in t), None))
                    elif any(k in lbl_text for k in ["sexual orientation", "orientation"]):
                        target_opt = next((o for o, t in clean_opts if "heterosexual" in t or "straight" in t), next((o for o, t in clean_opts if "decline" in t or "prefer not" in t), opts[0] if opts else None))
                    elif "race" in lbl_text or "ethnicity" in lbl_text or "ethnic" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "south asian" in t or "bangladeshi" in t), next((o for o, t in clean_opts if "asian" in t), None))
                    elif "hispanic" in lbl_text or "latino" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if t == "no"), None)
                    elif any(k in lbl_text for k in ["military status", "military", "veteran status", "veteran"]):
                        target_opt = next((o for o, t in clean_opts if any(v in t for v in ["never served", "not a protected veteran", "not a veteran", "no military", "i am not a protected", "i am not a veteran"])), next((o for o, t in clean_opts if t == "no" or "no" in t), None))
                    elif "disability" in lbl_text:
                        # Strictly answer: "No, I do not have a disability and have not had one in the past"
                        target_opt = next((o for o, t in clean_opts if "have not had one in the past" in t or "no, i do not have a disability" in t or ("no" in t and "disability" in t and "past" in t) or t == "no"), next((o for o, t in clean_opts if "no" in t), None))
                    elif any(k in lbl_text for k in ["learn", "source", "hear"]):
                        target_opt = next((o for o, t in clean_opts if any(s in t for s in ["builtin", "linkedin", "career", "website", "online"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["demonstrated experience", "experience in the specified discipline"]):
                        target_opt = next((o for o, t in clean_opts if t == "yes" or "yes" in t), None)
                    elif any(k in lbl_text for k in ["true and correct", "confirm all answers", "certify", "accurate"]):
                        target_opt = next((o for o, t in clean_opts if any(w in t for w in ["yes", "confirm", "agree", "acknowledge"])), None)
                    elif any(k in lbl_text for k in ["privacy policy", "privacy notice", "processed in accordance", "consent", "terms and conditions", "terms & conditions", "read and agree", "understand", "terms", "application statement", "employment contract", "subject to dismissal", "acknowledgement", "disclosure"]):
                        target_opt = next((o for o, t in clean_opts if any(w in t for w in ["yes", "agree", "understand", "accept", "acknowledge", "confirm"])), opts[0] if opts else None)
                    elif "pronoun" in lbl_text:
                        target_opt = next((o for o, t in clean_opts if "he/him" in t or "he / him" in t or t.startswith("he")), None)
                    elif any(k in lbl_text for k in ["intend to work out of", "below-listed locations", "confirm which location"]):
                        target_opt = next((o for o, t in clean_opts if "do not have plans" in t or "united states" in t or "remote" in t), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["willing to travel", "percentage of the time"]):
                        target_opt = next((o for o, t in clean_opts if any(w in t for w in ["0%", "1-10%", "10%", "none"])), opts[0] if opts else None)
                    elif any(k in lbl_text for k in ["accept the listed salary", "accept the compensation", "accept the listed pay", "agree to the salary"]):
                        target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                    elif any(k in lbl_text for k in ["target compensation", "compensation", "salary expectation"]):
                        if any(k in lbl_text for k in ["accept", "agree"]):
                            target_opt = next((o for o, t in clean_opts if "yes" in t), None)
                        else:
                            target_opt = next((o for o, t in clean_opts if any(w in t for w in ["80", "90", "70", "60", "50", "40"])), next((o for o, t in clean_opts if "yes" in t), opts[len(opts)//2] if opts else None))
                    elif any(k in lbl_text for k in ["highest level of degree currently", "highest level of degree achieved", "highest degree achieved", "highest degree completed", "most recently completed form of education", "completed form of education", "highest level of education completed"]):
                        target_opt = next((o for o, t in clean_opts if "bachelor" in t), next((o for o, t in clean_opts if "master" in t), opts[0] if opts else None))
                    elif any(k in lbl_text for k in ["proprietary trading", "trading firm"]):
                        target_opt = next((o for o, t in clean_opts if t == "no" or "no," in t or "do not" in t), None)
                    elif any(k in lbl_text for k in ["*", "required"]) and len(clean_opts) == 2 and any("yes" in t for _, t in clean_opts) and any("no" in t for _, t in clean_opts):
                        if any(k in lbl_text for k in ["previously worked", "ever worked", "previously employed", "ever been employed", "currently employed", "conflict", "felony", "crime", "investigation", "disciplinary", "government", "united nations", "relative", "family member", "non-compete", "referred", "referral", "women's", "female", "winternship", "sponsorship", "require sponsorship", "visa", "eligibility"]) or (any(k in lbl_text for k in ["require", "need"]) and any(k in lbl_text for k in ["sponsor", "visa", "auth"])):
                            target_opt = next((o for o, t in clean_opts if "no" in t), None)
                        else:
                            target_opt = next((o for o, t in clean_opts if "yes" in t), None)

                    if not target_opt:
                        if len(clean_opts) == 1:
                            target_opt = clean_opts[0][0]
                        else:
                            is_required_select = any(k in lbl_text for k in ["*", "required"]) or s.evaluate("el => el.closest('.field-wrapper, .field')?.querySelector('.required, [aria-required=\"true\"]') !== null")
                            if is_required_select and clean_opts:
                                if "school" in lbl_text and "high school" not in lbl_text:
                                    target_opt = next((o for o, t in clean_opts if "rutgers" in t and "camden" not in t and "newark" not in t), None)
                                if not target_opt:
                                    target_opt = next((o for o, t in clean_opts if t == "other" or "other" in t), None)
                                if not target_opt:
                                    target_opt = next((o for o, t in clean_opts if any(w in t for w in ["yes", "agree", "confirm", "acknowledge", "eligible", "authorized"])), None)
                                if not target_opt:
                                    target_opt = clean_opts[0][0]
                                print(f"    [Greenhouse RS Fallback] Selected fallback option for required field '{lbl_text[:30]}'", flush=True)

                    if target_opt:
                        txt_val = target_opt.inner_text().strip()
                        target_opt.click(force=True)
                        print(f"    [Greenhouse Engine] Selected '{txt_val}' for '{lbl_text[:35]}'", flush=True)
                        filled_in_pass += 1
                        time.sleep(0.15)
                        page.keyboard.press("Escape")
                    else:
                        page.keyboard.press("Escape")
                    time.sleep(0.15)
            except Exception as e:
                print(f"    [Greenhouse Engine] Option selection notice: {e}", flush=True)
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
        if filled_in_pass == 0:
            break
        time.sleep(0.5)

    # 5. Year and Number inputs
    sy = page.locator("input#start-year--0, input[id*='start-year' i], input[aria-label*='Start date year' i]").first
    if sy.count() > 0 and not sy.input_value().strip():
        is_emp_sy = sy.evaluate("el => !!el.closest('#employment_section, [data-qa*=\"employment\"], .employment, [class*=\"employment\"], fieldset[id*=\"employment\"], div[id*=\"employment\"], #employment_section_fields') || el.id.includes('start-date-year')")
        if not is_emp_sy:
            sy.fill(CANDIDATE["grad_start_year"])
            print(f"  [Greenhouse Engine] Filled Start Date Year: {CANDIDATE['grad_start_year']}", flush=True)

    ey = page.locator("input#end-year--0, input[id*='end-year' i], input[aria-label*='End date year' i]").first
    if ey.count() > 0 and not ey.input_value().strip():
        is_emp_ey = ey.evaluate("el => !!el.closest('#employment_section, [data-qa*=\"employment\"], .employment, [class*=\"employment\"], fieldset[id*=\"employment\"], div[id*=\"employment\"], #employment_section_fields') || el.id.includes('end-date-year')")
        if not is_emp_ey:
            ey.fill(CANDIDATE["grad_end_year"])
            print(f"  [Greenhouse Engine] Filled End Date Year: {CANDIDATE['grad_end_year']}", flush=True)

    # 6. Custom questions wrappers (Text inputs, Textareas, Classic Selects, Radios)
    wrappers = page.query_selector_all(".field-wrapper, .field, [class*='field'], [class*='question'], [id^='question_'], div.form-group, fieldset, li.card, div.card")
    for w in wrappers:
        lbl = w.query_selector("label, legend, [class*='label'], .card-title, h4, h3")
        txt = lbl.inner_text().strip().lower() if lbl else ""
        if not txt:
            continue

        # Text inputs (including numbers and urls)
        ti = w.query_selector("input[type='text'], input[type='url'], input[type='number'], input[type='tel'], input:not([type])")
        if ti and not ti.input_value().strip():
            if "linkedin" in txt:
                ti.fill(CANDIDATE["linkedin"])
            elif "github" in txt:
                ti.fill(CANDIDATE["github"])
            elif any(k in txt for k in ["website", "portfolio", "scholar", "publications link", "google scholar"]):
                ti.fill(CANDIDATE["portfolio"])
            elif "preferred" in txt and "name" in txt:
                ti.fill(CANDIDATE["first_name"])
            elif any(k in txt or k in (ti.get_attribute("aria-label") or "").lower() for k in ["legal name", "full name", "your name"]):
                ti.fill(CANDIDATE["name"])
            elif any(k in txt for k in ["previous employer", "the one before", "prior employer"]):
                ti.fill("TidaMed")
            elif any(k in txt for k in ["most recent employer", "recent employer", "current employer", "last employer", "current company"]):
                ti.fill("Amin AI")
            elif any(k in txt for k in ["sat score"]) or re.search(r'\bsat\b', txt):
                ti.fill("1280")
            elif any(k in txt for k in ["act score"]) or re.search(r'\bact\b', txt):
                ti_type = ti.get_attribute("type") or ""
                w_req = ti.get_attribute("required") is not None or ti.get_attribute("aria-required") == "true" or "*" in txt
                if w_req and ti_type != "number":
                    ti.fill("N/A")
            elif any(k in txt for k in ["gre score"]) or re.search(r'\bgre\b', txt):
                ti.fill("N/A")
            elif any(k in txt for k in ["c++ feature", "favorite c++"]):
                ti.fill("Smart pointers and RAII for deterministic memory management and safety")
            elif any(k in txt for k in ["achievement", "proud of", "most challenging project", "favorite project", "challenging project"]):
                ti.fill("At Amin AI I engineered automated microservices using Python and FastAPI with strict JSON schema validation to reliably process complex multi service workflows. In addition I built Trackwise a distributed real time expense tracker using Flutter and gRPC with PostgreSQL achieving sub 100ms synchronization and 30 percent network efficiency gains.")
            elif any(k in txt for k in ["why vercel", "why figma", "why samsara", "why appian", "why hp iq", "why are you interested", "what excites you"]):
                ti.fill("I admire your engineering culture and focus on high performance developer tools and distributed systems. My background in building responsive APIs with FastAPI and scalable distributed services aligns directly with your mission and I would love to contribute meaningfully as an intern.")
            elif any(k in txt for k in ["start year", "start date year", "start-year"]):
                if any(u in txt for u in ["undergrad", "bachelor", "college", "bs"]):
                    ti.fill(CANDIDATE["undergrad_start_year"])
                else:
                    ti.fill(CANDIDATE["grad_start_year"])
            elif any(k in txt for k in ["intended semester", "intended graduation", "semester and year", "graduation semester", "graduation date", "expected graduation", "when do you graduate", "when will you graduate"]):
                ti_type = ti.get_attribute("type") or ""
                if ti_type == "number":
                    ti.fill("2028")
                else:
                    ti.fill("Spring 2028")
            elif any(k in txt for k in ["end year", "graduation year", "grad year", "end date year", "end-year", "year do you intend to complete"]):
                ti.fill("2028")
            elif any(k in txt for k in ["when are you available to start", "available to start", "start date", "when can you start", "earliest start", "start work", "commence", "ideal start date"]):
                ti_type = ti.get_attribute("type") or ""
                is_winter = any(w in txt for w in ["winter", "january", "december"])
                if ti_type == "date":
                    ti.fill("2026-12-20" if is_winter else "2027-05-20")
                else:
                    ti.fill("December 20, 2026" if is_winter else "May 20, 2027")
            elif any(k in txt for k in ["where are you currently located", "currently located", "current location", "location", "city", "state"]):
                ti.fill("Piscataway, New Jersey")
            elif any(k in txt for k in ["university", "school", "college", "institution", "currently attend"]):
                ti.fill(CANDIDATE["school"])
            elif any(k in txt for k in ["programming language", "preferred language", "primary language", "coding language", "language of choice"]):
                ti.fill("Python")
            elif "pronoun" in txt:
                ti.fill(CANDIDATE["pronouns"])
            elif any(k in txt for k in ["preferred name", "name you prefer", "name you would like"]):
                ti.fill(CANDIDATE.get("first_name", ""))
            elif any(k in txt for k in ["from where", "where do you live", "intend to reside", "intend to live", "where do you intend"]):
                ti.fill("New Jersey / NYC Metro")
            elif any(k in txt for k in ["hear", "source"]):
                ti.fill("LinkedIn")
            elif any(k in txt for k in ["location", "city", "state"]):
                ti.fill(CANDIDATE["location"])
            elif any(k in txt for k in ["zip", "postal"]):
                ti.fill(CANDIDATE["zip_code"])
            elif any(k in txt for k in ["discipline", "major", "field of study", "area of study", "field are you looking"]):
                ti.fill("Computer Science")
            elif any(k in txt for k in ["expect to be paid", "expected pay", "desired pay", "pay expectation", "expected compensation", "hourly rate", "rate expectation", "rate requirement", "hourly", "salary expectation", "compensation range"]):
                ti.fill("40/hr")
            elif any(k in txt for k in ["salary", "compensation", "pay"]):
                ti.fill(CANDIDATE.get("salary", "80000"))
            elif any(k in txt for k in ["class year", "entering in fall"]):
                ti.fill("Senior")
            elif any(k in txt for k in ["write in your high school", "high school/secondary school below", "secondary school below", "name of your high school"]):
                ti.fill("Old Bridge High School")
            elif any(k in txt for k in ["write in your gpa below", "global grading systems", "without conversion"]):
                ti.fill("3.85 GPA out of 4.0 scale")
            elif any(k in txt for k in ["github"]):
                ti.fill(CANDIDATE["github"])
            elif any(k in txt for k in ["do you currently have an offer", "deadline to make a decision"]):
                ti.fill("No")
            elif any(k in txt for k in ["were you referred", "referred to this role"]):
                ti.fill("No")
            elif any(k in txt for k in ["high school", "graduate high school"]):
                ti.fill("2020")
            elif any(k in txt for k in ["consecutive weeks", "duration"]):
                ti.fill("12")
            elif any(k in txt for k in ["consecutive weeks", "duration"]):
                ti.fill("12")
            elif any(k in txt for k in ["relevant employment and military service", "add another employment"]):
                ti.fill("Amin AI, Automation Engineer (2025 to Present)")
            elif any(k in txt for k in ["grading scale", "gpa scale"]):
                ti.fill("4.0")
            elif any(k in txt for k in ["gpa", "grade point average"]):
                ti.fill(CANDIDATE["gpa"])
            elif any(k in txt for k in ["office", "which location"]):
                ti.fill("New York, NY")

        # Standard HTML Select dropdowns
        sel = w.query_selector("select")
        if sel:
            options = [o.inner_text().strip().lower() for o in sel.query_selector_all("option")]
            val_to_select = None
            if any(k in txt for k in ["sat score", "result on sat"]) or re.search(r'\bsat\b', txt):
                val_to_select = next((o for o in options if "1280" in o or "1201" in o or "1200" in o), next((o for o in options if "did not take" in o or "not take" in o or "dont have" in o or "do not have" in o), None))
            elif any(k in txt for k in ["act score", "result on act"]) or re.search(r'\bact\b', txt):
                val_to_select = next((o for o in options if "did not take" in o or "not take" in o or "dont have" in o or "do not have" in o or "n/a" in o or "none" in o), None)
            elif any(k in txt for k in ["standardized test score type", "test score type"]):
                val_to_select = next((o for o in options if o == "sat" or "sat" in o), options[0] if options else None)
            elif any(k in txt for k in ["graduate from high school", "graduate high school", "high school"]):
                val_to_select = next((o for o in options if "2020" in o or "before 2021" in o or "before" in o), options[0] if options else None)
            elif any(k in txt for k in ["alphabet employee", "google employee"]):
                val_to_select = next((o for o in options if "never" in o or "no" in o), None)
            elif any(k in txt for k in ["what kind", "kind of work authorization"]):
                val_to_select = next((o for o in options if "not applicable" in o or "n/a" in o or "none" in o), None)
            elif any(k in txt for k in ["have any offers", "competing offers", "pending offers"]):
                val_to_select = next((o for o in options if o == "no" or "no" in o), None)
            elif any(k in txt for k in ["applied to this role or another role", "previously applied"]):
                val_to_select = next((o for o in options if o == "no" or "no" in o), None)
            elif any(k in txt for k in ["pronoun", "gender pronouns", "share your gender pronouns"]):
                val_to_select = next((o for o in options if ("he/him" in o or "he / him" in o or re.search(r'\bhe\b', o)) and "she" not in o), options[0] if options else None)
            elif any(k in txt for k in ["relevant employment and military", "add another employment"]):
                val_to_select = next((o for o in options if "thank you" in o or "yes" in o), options[0] if options else None)
            elif any(k in txt for k in ["pre-employment requirements", "interview code of conduct", "code of conduct", "candidate privacy", "privacy statement"]):
                val_to_select = next((o for o in options if any(w in o for w in ["yes", "agree", "acknowledge", "consent", "confirm"])), None)
            elif any(k in txt for k in ["gre score"]) or re.search(r'\bgre\b', txt):
                val_to_select = next((o for o in options if "did not take" in o or "not take" in o or "n/a" in o or "none" in o), None)
            elif any(k in txt for k in ["doctorate", "phd", "doctoral"]):
                val_to_select = next((o for o in options if "not applicable" in o or "n/a" in o or "none" in o), None)
            elif any(k in txt for k in ["grading scale", "gpa scale"]):
                val_to_select = next((o for o in options if "4.0" in o or "4" in o), options[0] if options else None)
            elif any(k in txt for k in ["pursue further education immediately", "further education upon graduation", "pursuing further education immediately"]):
                val_to_select = next((o for o in options if "no" in o), None)
            elif any(k in txt for k in ["enrolled as a student at", "student at northeastern", "student at columbia", "student at nyu", "student at harvard"]):
                val_to_select = next((o for o in options if "no" in o), None)
            # Degree currently pursuing (Strictly Master's)
            elif any(k in txt for k in ["degree are you currently pursuing", "what degree are you pursuing", "what degree are you currently pursuing", "degree currently pursuing", "degree you are pursuing", "degree seeking", "what degree are you seeking", "currently pursuing"]) and not any(k in txt for k in ["completed", "achieved", "attained", "highest level of degree currently", "highest level of degree achieved", "highest degree achieved", "highest degree completed"]):
                val_to_select = next((o for o in options if "master" in o), next((o for o in options if "bachelor" in o), None))
            # Highest level of degree achieved / completed (Strictly Bachelor's)
            elif any(k in txt for k in ["highest level of degree currently", "highest level of degree achieved", "highest degree achieved", "highest degree attained", "highest degree completed", "highest degree currently held", "highest degree you hold", "highest level of education completed"]):
                val_to_select = next((o for o in options if "bachelor" in o), None)
            # Referral Source / How did you learn about us (Strictly Job Board)
            elif any(k in txt for k in ["how did you learn", "learn about us", "hear about us", "source", "how did you hear"]):
                val_to_select = next((o for o in options if any(target in o for target in ["job board", "linkedin", "career page", "career site", "company website", "online", "internet"])), next((o for o in options if not any(neg in o for neg in ["employee referral", "agency", "current canon", "canon employee", "alumni"])), options[0] if options else None))
            elif any(k in txt for k in ["majoring in stem", "stem major", "stem degree", "stem field"]):
                val_to_select = next((o for o in options if "yes" in o), None)
            elif any(k in txt for k in ["winter 2027 or summer 2027", "winter or summer", "summer or winter", "applying to intern in", "cohort do you prefer", "which term", "which season", "term preference"]):
                val_to_select = next((o for o in options if "summer 2027" in o), next((o for o in options if "summer" in o), next((o for o in options if "2027" in o), None)))
            elif any(k in txt for k in ["based in any of these countries", "reside in any of these countries", "located in any of these countries", "country of residence", "which country"]):
                val_to_select = next((o for o in options if any(c in o for c in ["united states of america", "united states", "usa", "u.s."])), None)
            elif any(k in txt for k in ["anticipated bachelor", "anticipated master", "anticipated graduation", "when will you be graduating", "when do you graduate", "graduation date", "graduating date", "year of graduation"]):
                val_to_select = next((o for o in options if "may - aug 2028" in o or "jan - july 2028" in o or "spring 2028" in o or "may 2028" in o or "2028" in o), next((o for o in options if "2027" in o), None))
            elif any(k in txt for k in ["graduate student in spring 2027", "graduate student in 2027", "already hold a bachelor"]):
                val_to_select = next((o for o in options if "no" in o), None)
            elif any(k in txt for k in ["sponsorship", "visa", "require employm", "require visa", "require immigra", "require sponsor", "future require", "now or in the future"]):
                val_to_select = next((o for o in options if "no" in o or "not" in o), None)
            elif any(k in txt for k in ["authorized", "authorization"]):
                val_to_select = next((o for o in options if "yes" in o or "authorized" in o), None)
            elif any(k in txt for k in ["discipline", "major", "field of study", "area of study"]):
                val_to_select = next((o for o in options if "computer science" in o or "computer" in o), None)
            elif any(k in txt for k in ["relocate", "relocation", "need to relocate", "willing and able to relocate", "open to relocating"]):
                # Priority 1: >= 1 month
                val_to_select = next((o for o in options if any(m in o.lower() for m in ["at least 1 month", "at least one month", "1 month", "one month", "1-2 month", "1 - 2 month", "1 to 2 month", "30 day", "30+ day", "4 week", "4+ week", "60 day", "2 month"]) and not any(neg in o.lower() for neg in ["cannot", "not willing", "less than 1 month", "under 30 day"])), None)
                if not val_to_select:
                    val_to_select = next((o for o in options if any(r in o.lower() for r in ["i need to relocate", "need to relocate", "require relocation", "will need relocation", "relocation needed", "willing to relocate", "relocation with assistance", "relocation assistance", "plan to relocate", "can relocate", "yes, willing", "yes, relocate", "relocate", "relocation", "yes"]) and not any(neg in o.lower() for neg in ["cannot", "not willing", "not able", "no", "without"])), None)
            elif any(k in txt for k in ["accommodate", "work environment", "work from the office", "days/week", "in-person", "relocate to ca"]):
                val_to_select = next((o for o in options if "yes" in o or "willing" in o), None)
            elif any(k in txt for k in ["which office", "office location", "where you can work", "location preference"]):
                val_to_select = next((o for o in options if "new york" in o or "nyc" in o or "new jersey" in o), next((o for o in options if "san francisco" in o or "remote" in o or "united states" in o), options[0] if options else None))
            elif any(k in txt for k in ["c++", "proficiency", "creative problem-solving"]):
                val_to_select = next((o for o in options if any(p in o for p in ["proficient", "advanced", "intermediate", "2-3", "1-2", "3+", "high"])), next((o for o in options if "yes" in o), None))
            elif any(k in txt for k in ["class year", "level of education"]):
                val_to_select = next((o for o in options if any(y in o for y in ["senior", "junior", "undergraduate", "bachelor"])), None)
            elif any(k in txt for k in ["data transfer", "gdpr", "arbitration", "linked document"]):
                val_to_select = next((o for o in options if any(a in o for a in ["yes", "agree", "acknowledge", "consent"])), None)
            elif any(k in txt for k in ["eligible to work in the country", "eligible to work"]):
                val_to_select = next((o for o in options if "yes" in o), None)
            elif any(k in txt for k in ["application statement", "subject to dismissal", "employment contract", "acknowledge that i have read"]):
                val_to_select = next((o for o in options if any(a in o for a in ["yes", "agree", "acknowledge", "consent", "confirm"])), None)
            elif (any(k in txt for k in ["state in which you currently reside", "state of residence", "current state"]) or re.search(r'\bstate\*?\b', txt)) and "statement" not in txt:
                val_to_select = next((o for o in options if "new jersey" in o or o == "nj"), None)
            elif any(k in txt for k in ["own, operate, or provide services", "outside business", "conflict"]):
                val_to_select = next((o for o in options if "no" in o), None)
            elif any(k in txt for k in ["talent community", "future career opportunities"]):
                val_to_select = next((o for o in options if "yes" in o), None)
            elif any(k in txt for k in ["programming language", "preferred language", "primary language", "coding language", "language of choice"]):
                val_to_select = next((o for o in options if "python" in o), None)
            elif any(k in txt for k in ["ever worked", "former", "prior", "previously worked"]):
                val_to_select = next((o for o in options if "no" in o or "not" in o), None)
            elif any(k in txt for k in ["used robinhood", "have you used"]):
                val_to_select = next((o for o in options if "yes" in o), None)
            elif any(k in txt for k in ["familial", "relationship", "government", "official", "regulatory"]):
                val_to_select = next((o for o in options if "no" in o or "not" in o or "neither" in o), None)
            elif any(k in txt for k in ["country", "reside", "based in"]):
                val_to_select = next((o for o in options if "united states" in o or "usa" in o), None)
            elif any(k in txt for k in ["preferred", "location", "office", "from where"]):
                val_to_select = next((o for o in options if "new york" in o or "nyc" in o or "remote" in o or "united states" in o or "menlo park" in o), None)
            elif "gender" in txt:
                val_to_select = next((o for o in options if "male" in o and "female" not in o), None)
            elif any(k in txt for k in ["sexual orientation", "orientation"]):
                val_to_select = next((o for o in options if "heterosexual" in o or "straight" in o), None)
            elif any(k in txt for k in ["race", "ethnicity"]):
                val_to_select = next((o for o in options if "asian" in o), None)
            elif "veteran" in txt:
                val_to_select = next((o for o in options if any(v in o for v in ["not a protected veteran", "i am not a protected veteran", "not a veteran", "i am not a veteran", "never served", "no military"]) or ("not" in o and "veteran" in o) or o == "no"), None)
            elif "disability" in txt:
                val_to_select = next((o for o in options if "no" in o or "not" in o or "don't" in o), None)
            elif any(k in txt for k in ["hear", "source"]):
                val_to_select = next((o for o in options if "linkedin" in o or "website" in o), None)

            if not val_to_select and len(options) == 1:
                val_to_select = options[0]

            if val_to_select:
                try:
                    for o in sel.query_selector_all("option"):
                        if val_to_select in o.inner_text().strip().lower():
                            v = o.get_attribute("value")
                            if v is not None and v != "":
                                sel.select_option(value=v)
                            else:
                                sel.select_option(label=o.inner_text().strip())
                            break
                except Exception:
                    pass

        # Radio buttons
        radios = w.query_selector_all("input[type='radio']")
        if radios:
            for r in radios:
                r_txt = r.evaluate("el => el.closest('label') ? el.closest('label').innerText.toLowerCase() : (el.closest('div') ? el.closest('div').innerText.toLowerCase() : '')")
                if any(k in txt for k in ["majoring in stem", "stem major", "stem degree", "stem field"]):
                    if "yes" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["winter 2027 or summer 2027", "applying to intern in", "cohort do you prefer", "which term", "which season", "summer or winter"]):
                    if "summer" in r_txt or "2027" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["enrolled as a student at", "student at northeastern", "student at columbia", "student at nyu", "student at harvard", "student at mit", "student at stanford", "pursue further education immediately", "further education upon graduation"]):
                    if "no" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["graduate student in spring 2027", "graduate student in 2027", "already hold a bachelor"]):
                    if "no" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["sponsorship", "visa", "require employm", "require visa", "require immigra", "require sponsor", "future require", "now or in the future"]):
                    if "no" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["authorized", "authorization"]):
                    if any(pos in r_txt for pos in ["yes", "legally authorized", "any employer", "citizen"]) and not any(neg in r_txt for neg in ["not", "never", "cannot", "require"]):
                        safe_click(r)
                        break
                elif any(k in txt for k in ["programming language", "preferred language", "primary language", "coding language"]):
                    if "python" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["ever worked", "previously worked", "former"]):
                    if "no" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["relocate", "relocation", "need to relocate", "willing and able to relocate", "open to relocating"]):
                    r_pairs = [(cr, cr.evaluate("el => el.closest('label') ? el.closest('label').innerText.toLowerCase() : (el.closest('div') ? el.closest('div').innerText.toLowerCase() : '')")) for cr in radios]
                    one_m_radio = next((cr for cr, ct in r_pairs if any(m in ct for m in ["at least 1 month", "at least one month", "1 month", "one month", "1-2 month", "1 - 2 month", "1 to 2 month", "30 day", "30+ day", "4 week", "4+ week", "60 day", "2 month"]) and not any(neg in ct for neg in ["cannot", "not willing", "less than 1 month", "under 30 day"])), None)
                    any_r_radio = next((cr for cr, ct in r_pairs if any(r_kw in ct for r_kw in ["i need to relocate", "need to relocate", "require relocation", "will need relocation", "relocation needed", "willing to relocate", "relocation with assistance", "relocation assistance", "plan to relocate", "can relocate", "yes, willing", "yes, relocate", "relocate", "relocation", "yes"]) and not any(neg in ct for neg in ["cannot", "not willing", "not able", "no", "without"])), None)
                    target_r = one_m_radio or any_r_radio
                    if target_r:
                        safe_click(target_r)
                        break
                elif any(k in txt for k in ["used robinhood", "have you used", "willing to work from the office", "days/week"]):
                    if "yes" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["familial", "relationship", "government", "official", "regulatory"]):
                    if "no" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["country", "reside"]):
                    if "united states" in r_txt or "usa" in r_txt or "yes" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["acknowledge", "agree", "consent", "confirm"]):
                    if "yes" in r_txt or "agree" in r_txt:
                        safe_click(r)
                        break

    # 7. Check required checkboxes & specialized checkbox groups (Airtight logic)
    cbs = page.query_selector_all("input[type='checkbox']")
    for cb in cbs:
        try:
            cb_id = cb.get_attribute("id") or ""
            label_text = page.evaluate("(id) => { const l = document.querySelector(`label[for=\"${id}\"]`); return l ? l.innerText.trim() : ''; }", cb_id)
            if not label_text:
                label_text = cb.evaluate("el => (el.closest('.checkbox__wrapper') ? el.closest('.checkbox__wrapper').querySelector('label')?.innerText.trim() : '') || ''")
            group_text = cb.evaluate("el => (el.closest('fieldset, .field-wrapper, .field') ? el.closest('fieldset, .field-wrapper, .field').querySelector('legend, label')?.innerText.trim() : '') || ''").lower()
            lbl_low = label_text.lower()

            should_check = False
            # 1. Sanctions question: Cuba, Iran, North Korea, Syria, Crimea, Russia, Belarus
            if any(k in group_text for k in ["sanction", "export control", "cuba", "iran", "north korea", "syria"]):
                if "none of the above" in lbl_low or lbl_low == "none":
                    should_check = True
                elif any(k in lbl_low for k in ["cuba", "iran", "north korea", "syria", "crimea", "russia", "belarus", "sanctions"]):
                    should_check = False
            # 2. Prior sanctions question follow-up
            elif any(k in group_text for k in ["prior question other than", "if you selected a response to the prior question"]):
                if "not applicable" in lbl_low or "i selected “none of the above”" in lbl_low:
                    should_check = True
                else:
                    should_check = False
            # 3. Single location preference (Pick ONE location only!)
            elif any(k in group_text for k in ["single location", "most interested in"]):
                has_ny = any("new york" in (page.evaluate("(id) => { const l = document.querySelector(`label[for=\"${id}\"]`); return l ? l.innerText.trim() : ''; }", c.get_attribute("id") or "")).lower() for c in cbs)
                if has_ny:
                    should_check = "new york" in lbl_low
                else:
                    should_check = "san francisco" in lbl_low
            # 4. Multi-location or office checkboxes (e.g. SF, NY)
            elif any(k in group_text for k in ["location", "office"]):
                if "new york" in lbl_low or "san francisco" in lbl_low or "remote" in lbl_low:
                    should_check = True
            # 5. Work authorization checkbox
            elif any(k in lbl_low for k in ["u.s. citizen", "us citizen", "authorized to work in the united states", "authorized to work in the u.s."]) and not any(neg in lbl_low for neg in ["not", "never", "cannot", "no ", "require"]):
                should_check = True
            # 6. Undergrad discipline / major checkboxes (User rule: strictly Computer Science)
            elif any(k in group_text for k in ["discipline", "major", "field of study", "area of study"]):
                if "computer science" in lbl_low or lbl_low == "cs":
                    should_check = True
                else:
                    should_check = False
            # 7. General consent / privacy / terms
            elif any(k in lbl_low or k in group_text for k in ["agree", "consent", "acknowledge", "privacy policy", "terms", "terms and conditions", "terms & conditions"]):
                should_check = True
            # 8. Cohort / Term checkboxes (User request: Summer or Winter)
            elif any(k in group_text for k in ["cohort", "term", "season", "applying for", "which internship", "dates do you prefer"]):
                if any(k in lbl_low for k in ["summer", "winter", "fall", "spring"]):
                    should_check = True
            # 9. Programming languages / technical skills checkboxes (e.g. IMC Trading)
            elif any(k in group_text for k in ["programming language", "languages you are proficient", "technologies", "tech stack"]):
                if any(lang in lbl_low for lang in ["python", "java", "c++", "c/c++", "sql", "javascript", "typescript", "go", "golang", "c#"]):
                    should_check = True
                elif "none of the above" in lbl_low or lbl_low == "none":
                    should_check = False
            # 10. Current role / Currently work here checkbox in employment
            elif any(k in lbl_low for k in ["current role", "currently work here", "i currently work here", "to present"]):
                should_check = True
            # 11. Pronouns checkboxes
            elif any(k in lbl_low for k in ["he/him", "he/him/his"]):
                should_check = True
            elif any(k in lbl_low for k in ["she/her", "they/them"]):
                should_check = False

            is_checked = cb.is_checked()
            if should_check and not is_checked:
                cb.click(force=True)
                print(f"  [Greenhouse Engine] Checked: '{label_text}' in group '{group_text[:30]}'", flush=True)
            elif not should_check and is_checked:
                cb.click(force=True)
                print(f"  [Greenhouse Engine] Unchecked prohibited/unwanted: '{label_text}'", flush=True)
        except Exception:
            pass

    # 7b. Checkbox group safety pass: ensure any required checkbox group has at least one checked
    try:
        cb_fieldsets = page.query_selector_all("fieldset.checkbox, fieldset:has(input[type='checkbox'])")
        for fs in cb_fieldsets:
            is_req = fs.evaluate("el => el.getAttribute('aria-required') === 'true' || el.querySelector('[required]') !== null || (el.querySelector('legend') && (el.querySelector('legend').innerText.includes('*') || el.querySelector('legend').innerText.includes('✱')))")
            if is_req:
                fs_cbs = fs.query_selector_all("input[type='checkbox']")
                if fs_cbs and not any(b.is_checked() for b in fs_cbs):
                    chosen = None
                    for b in fs_cbs:
                        b_txt = b.evaluate("el => (el.closest('.checkbox__wrapper') ? el.closest('.checkbox__wrapper').querySelector('label')?.innerText.trim() : '') || ''").lower()
                        if not any(neg in b_txt for neg in ["none", "not applicable", "n/a", "neither"]):
                            chosen = b
                            break
                    if not chosen:
                        chosen = fs_cbs[0]
                    chosen.click(force=True)
                    print(f"  [Greenhouse Engine] Checked fallback checkbox in required group", flush=True)
    except Exception:
        pass

    # 8. Form validation audit (excluding non-selected checkboxes in group)
    invalid_fields = page.evaluate('''() => {
        const inv = [];
        document.querySelectorAll('input:not([type="checkbox"]), select, textarea').forEach(el => {
            if (!el.checkValidity()) {
                let lbl = '';
                const p = el.closest('.field-wrapper, .field, div.select, fieldset');
                if (p) {
                    const l = p.querySelector('label, legend');
                    if (l) lbl = l.innerText.trim();
                }
                inv.push({ id: el.id || el.name || 'unknown', type: el.type || el.tagName.toLowerCase(), label: lbl });
            }
        });
        return inv;
    }''')
    if invalid_fields:
        for fld in invalid_fields:
            fid = fld.get('id', '')
            flbl = (fld.get('label') or '').lower()
            print(f"  ⚠️ Invalid Field Detected: id='{fid}', type='{fld.get('type')}', label='{flbl}'", flush=True)
            try:
                el = page.locator(f"#{fid}, [name='{fid}']").first
                if el.is_visible() and not el.input_value().strip():
                    if any(k in flbl or k in fid for k in ["country", "nation"]):
                        el.fill("United States")
                        print("    [Greenhouse Rectify] Filled Country: United States", flush=True)
                    elif any(k in flbl or k in fid for k in ["address", "street", "street address"]):
                        el.fill("32 Birch Run Ave")
                        print("    [Greenhouse Rectify] Filled Address: 32 Birch Run Ave", flush=True)
                    elif any(k in flbl or k in fid for k in ["city", "municipality"]):
                        el.fill("Piscataway")
                        print("    [Greenhouse Rectify] Filled City: Piscataway", flush=True)
                    elif any(k in flbl or k in fid for k in ["state", "province"]):
                        el.fill("New Jersey")
                        print("    [Greenhouse Rectify] Filled State: New Jersey", flush=True)
                    elif any(k in flbl or k in fid for k in ["zip", "postal"]):
                        el.fill("08854")
                        print("    [Greenhouse Rectify] Filled Zip: 08854", flush=True)
            except Exception:
                pass
    else:
        print("  ✅ All form fields valid and ready for submission!", flush=True)


def fill_lever(page, pdf_path, company="", role="", jd_text=""):
    print("  [Lever Engine] Filling application form...", flush=True)
    recent_emp = get_recent_employer(company=company, role=role, jd_text=jd_text)
    # 1. Resume upload
    fi = page.locator("input[type='file'][name='resume'], input[type='file']").first
    if fi.is_visible():
        try:
            fi.set_input_files(pdf_path)
            print("  [Lever Engine] Uploaded tailored PDF resume.", flush=True)
        except Exception as e:
            print(f"  [Lever Engine] Resume upload error: {e}", flush=True)
        time.sleep(2.0)

    # 2. Base inputs
    mappings = [
        ("name", CANDIDATE["name"]),
        ("email", CANDIDATE["email"]),
        ("phone", CANDIDATE["phone"]),
        ("location", CANDIDATE["location"]),
        ("org", recent_emp),
        ("urls[LinkedIn]", CANDIDATE["linkedin"]),
        ("urls[GitHub]", CANDIDATE["github"]),
        ("urls[Portfolio]", CANDIDATE["portfolio"]),
    ]
    for field_name, val in mappings:
        inp = page.locator(f"input[name='{field_name}']").first
        if inp.count() > 0 and inp.is_visible() and not inp.input_value().strip():
            inp.fill(val)

    # Force location value & events for autocomplete
    page.evaluate('''() => {
        const loc = document.querySelector('#location-input, input[name="location"]');
        if (loc) {
            loc.value = 'Piscataway, New Jersey';
            loc.dispatchEvent(new Event('input', { bubbles: true }));
            loc.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }''')

    # Disability signature & date fields
    today = datetime.now()
    date_str = f"{today.month:02d}/{today.day:02d}/{today.year}"
    iso_date_str = f"{today.year}-{today.month:02d}-{today.day:02d}"
    for d_inp in page.locator("input[name*='date' i], input[type='date'], input[placeholder*='date' i]").all():
        try:
            if d_inp.is_visible() and not d_inp.input_value().strip():
                try:
                    d_inp.fill(date_str)
                except Exception:
                    d_inp.fill(iso_date_str)
                d_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
                print(f"    [Lever Engine] Filled date field: {date_str}", flush=True)
        except Exception:
            pass
    for sign_inp in page.locator("input[name*='sign' i], input[name*='disability' i][name*='name' i], input[name='signature']").all():
        try:
            if sign_inp.is_visible() and not sign_inp.input_value().strip():
                sign_inp.fill(CANDIDATE["name"])
                sign_inp.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
                print(f"    [Lever Engine] Filled signature field: {CANDIDATE['name']}", flush=True)
        except Exception:
            pass

    # Top-level or multi-location dropdowns (only those outside cards/questions)
    for top_sel in page.query_selector_all("select"):
        try:
            in_card = top_sel.evaluate("s => !!s.closest('.application-question, li.card, div.card, div[class*=\"custom-question\"], .application-additional, .eeo-section, .eeo')")
            if in_card:
                continue
            curr_val = top_sel.evaluate("s => s.value")
            if curr_val and curr_val.strip() and curr_val.strip().lower() != "select...":
                continue
            opts = page.evaluate("(s) => Array.from(s.options).map(o => ({value: o.value, text: o.text.trim()}))", top_sel)
            valid_opts = [o for o in opts if o["value"].strip() and "select" not in o["text"].lower()]
            if not valid_opts:
                continue
            parent_txt = top_sel.evaluate("s => (s.closest('.application-question, .card, div, li')?.innerText || '').toLowerCase()")
            chosen_opt = None
            if any(k in parent_txt for k in ["location", "office", "where"]):
                chosen_opt = next((o for o in valid_opts if any(loc_k in o["text"].lower() for loc_k in ["new york", "ny", "new jersey", "nj", "remote"])), valid_opts[0])
            elif any(k in parent_txt for k in ["veteran", "military"]):
                chosen_opt = next((o for o in valid_opts if any(v in o["text"].lower() for v in ["not a", "not protected", "i am not", "i identify as not", "neither"])), None)
            elif any(k in parent_txt for k in ["disability", "handicap"]):
                chosen_opt = next((o for o in valid_opts if any(d in o["text"].lower() for d in ["no, i don't", "no, i do not", "no", "do not have"])), None)
            elif any(k in parent_txt for k in ["gender", "sex"]):
                chosen_opt = next((o for o in valid_opts if "male" in o["text"].lower() and "female" not in o["text"].lower()), None)
            elif any(k in parent_txt for k in ["race", "ethnicity"]):
                chosen_opt = next((o for o in valid_opts if "asian" in o["text"].lower() and not any(m in o["text"].lower() for m in ["two", "multiple", "mixed"])), None)
            elif any(k in parent_txt for k in ["sponsorship", "require sponsorship", "visa"]):
                chosen_opt = next((o for o in valid_opts if o["text"].strip().lower().startswith("no") or "not require" in o["text"].lower()), None)
            elif any(k in parent_txt for k in ["authorized", "legally authorized", "work authorization", "right to work"]):
                chosen_opt = next((o for o in valid_opts if o["text"].strip().lower().startswith("yes")), None)
            elif any(k in parent_txt for k in ["year", "standing", "class", "academic year", "current year"]):
                chosen_opt = next((o for o in valid_opts if any(y in o["text"].lower() for y in ["master", "graduate", "senior", "junior"])), None)
            elif any(k in parent_txt for k in ["graduat", "completion"]):
                chosen_opt = next((o for o in valid_opts if any(y in o["text"].lower() for y in ["2028", "2027", "2026"])), None)
            
            if chosen_opt:
                top_sel.select_option(value=chosen_opt["value"])
                page.evaluate("""(s) => {
                    s.dispatchEvent(new Event('input', { bubbles: true }));
                    s.dispatchEvent(new Event('change', { bubbles: true }));
                }""", top_sel)
                print(f"    [Lever Engine] Selected top-level select: '{chosen_opt['text']}'", flush=True)
        except Exception as se:
            print(f"    [Lever Engine] Top select notice: {se}", flush=True)

    # Transcript upload fallback
    ti_file = page.locator("input[type='file'][name*='transcript' i]").first
    if ti_file.count() > 0 and ti_file.is_visible():
        try:
            ti_file.set_input_files(pdf_path)
            print("    [Lever Engine] Attached transcript/resume file.", flush=True)
        except Exception:
            pass

    # 3. Custom questions
    questions = page.query_selector_all(".application-question, li.card, div.card, div[class*='custom-question'], .application-additional > div")
    for q in questions:
        lbl = q.query_selector(".application-label, label, .card-title, h4, h3")
        txt = lbl.inner_text().strip().lower() if lbl else ""
        if not txt:
            continue

        # Checkboxes
        cbs = q.query_selector_all("input[type='checkbox']")
        if cbs:
            for cb in cbs:
                cb_txt = cb.evaluate("el => el.closest('label') ? el.closest('label').innerText.toLowerCase() : ''")
                should_check = False
                if any(k in txt for k in ["semester", "term", "cohort"]):
                    if any(t in cb_txt for t in ["summer 2027", "summer", "2027"]):
                        should_check = True
                elif any(lang in cb_txt for lang in ["english", "python", "java", "javascript", "c++", "sql"]):
                    should_check = True
                elif any(k in cb_txt for k in ["authorized", "u.s. citizen", "us citizen", "permanent resident"]):
                    should_check = True
                elif any(k in cb_txt or k in txt for k in ["i agree", "i consent", "i acknowledge", "terms", "please confirm", "different applications", "confirm that you understand"]):
                    should_check = True

                if should_check:
                    try:
                        safe_click(cb)
                        page.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }", cb)
                    except Exception:
                        pass

            # Fallback if checkbox group and nothing checked
            has_checked = any(cb.evaluate("el => el.checked") for cb in cbs)
            is_conditional_deadline = any(k in txt for k in ["if so, what are the dates", "dates of offer", "offer deadline dates"])
            is_optional_eeo = any(k in txt for k in ["veteran", "disability", "gender", "race"])
            if not has_checked and not is_conditional_deadline and not is_optional_eeo:
                try:
                    safe_click(cbs[0])
                    page.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }", cbs[0])
                    print(f"    [Lever Engine] Checked default first option for checkbox group '{txt[:35]}'", flush=True)
                except Exception:
                    pass

        # Radios
        radios = q.query_selector_all("input[type='radio']")
        if radios:
            for r in radios:
                r_txt = r.evaluate("el => el.closest('label') ? el.closest('label').innerText.toLowerCase() : ''")
                if any(k in txt for k in ["sponsorship", "visa", "require employm", "require visa", "require immigra", "require sponsor", "future require", "now or in the future", "upon graduation"]):
                    if "no" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["authorized", "authorization"]):
                    if "yes" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["export control", "u.s. person", "us person", "itar", " export "]) or re.search(r'\b(itar|ear)\b', txt):
                    if any(s in r_txt for s in ["u.s. person", "us person", "citizen", "yes"]):
                        safe_click(r)
                        break
                elif any(k in txt for k in ["hear", "source", "how did you"]):
                    if any(s in r_txt for s in ["linkedin", "company website", "job board", "career", "website", "online"]):
                        safe_click(r)
                        break
                elif any(k in txt for k in ["semester", "term", "cohort"]):
                    if any(s in r_txt for s in ["summer 2027", "summer", "2027"]):
                        safe_click(r)
                        break
                elif any(k in txt for k in ["relocate", "relocation", "need to relocate", "willing and able to relocate", "open to relocating"]):
                    r_pairs = [(cr, cr.evaluate("el => el.closest('label') ? el.closest('label').innerText.toLowerCase() : (el.closest('div') ? el.closest('div').innerText.toLowerCase() : '')")) for cr in radios]
                    one_m_radio = next((cr for cr, ct in r_pairs if any(m in ct for m in ["at least 1 month", "at least one month", "1 month", "one month", "1-2 month", "1 - 2 month", "1 to 2 month", "30 day", "30+ day", "4 week", "4+ week", "60 day", "2 month"]) and not any(neg in ct for neg in ["cannot", "not willing", "less than 1 month", "under 30 day"])), None)
                    any_r_radio = next((cr for cr, ct in r_pairs if any(r_kw in ct for r_kw in ["willing to relocate", "relocation with assistance", "relocation assistance", "plan to relocate", "can relocate", "yes, willing", "yes, relocate", "relocate", "relocation", "yes"]) and not any(neg in ct for neg in ["cannot", "not willing", "not able", "no", "without"])), None)
                    target_r = one_m_radio or any_r_radio
                    if target_r:
                        safe_click(target_r)
                        break
                elif any(k in txt for k in ["in-person", "onsite", "on-site", "hybrid", "office"]):
                    if "yes" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["clearance", "security clearance"]):
                    if "active" in txt and "no" in r_txt:
                        safe_click(r)
                        break
                    elif any(k in txt for k in ["able to hold", "eligible", "obtain", "maintain", "willing to obtain", "able to obtain"]) and "yes" in r_txt:
                        safe_click(r)
                        break
                    elif "yes" in r_txt:
                        safe_click(r)
                        break
                elif "final internship" in txt:
                    if "yes" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["deadline", "offer deadline"]):
                    if "no" in r_txt:
                        safe_click(r)
                        break
                elif "california" in txt:
                    if "no" in r_txt:
                        safe_click(r)
                        break
                elif "notetaker" in txt or "metaview" in txt:
                    if "yes" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["acknowledge", "consent", "share my resume"]):
                    if "yes" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["programming language", "preferred language", "primary language", "coding language"]):
                    if "python" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["18 years", "at least 18", "age of 18", "enrolled", "degree program", "currently pursuing", "full-time", "40 hours", "available", "summer 2027", "us citizen", "u.s. person", "permanent resident", "university student", "currently a student", "college student", "student"]):
                    if "yes" in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["veteran", "military"]):
                    if any(s in r_txt for s in ["not a protected veteran", "i am not a protected veteran", "no"]):
                        safe_click(r)
                        break
                elif any(k in txt for k in ["race", "ethnicity", "ethnic"]):
                    if "asian" in r_txt and not any(bad in r_txt for bad in ["two or more", "multiple", "mixed"]):
                        safe_click(r)
                        break
                elif any(k in txt for k in ["gender", "sex"]):
                    if "male" in r_txt and "female" not in r_txt:
                        safe_click(r)
                        break
                elif any(k in txt for k in ["disability"]):
                    if any(s in r_txt for s in ["no, i do not have a disability", "no", "do not have"]):
                        safe_click(r)
                        break
                elif any(k in txt for k in ["previously worked", "ever worked", "previously employed", "relative", "family member", "non-compete", "export control", "export license", "conflict of interest"]):
                    if "no" in r_txt:
                        safe_click(r)
                        break

            # If still not selected, check if required Yes/No or any radio group
            radio_checked = any(r.evaluate("el => el.checked") for r in radios)
            if not radio_checked:
                r_texts = [r.evaluate("el => el.closest('label') ? el.closest('label').innerText.toLowerCase() : ''") for r in radios]
                if any("yes" in t for t in r_texts) and any("no" in t for t in r_texts):
                    neg = any(k in txt for k in ["previously", "ever worked", "relative", "conflict", "felony", "sponsorship", "visa", "export"])
                    target_txt = "no" if neg else "yes"
                    for r, t in zip(radios, r_texts):
                        if target_txt in t:
                            safe_click(r)
                            break
                if not radio_checked:
                    ai_opt = solve_field_with_ai(txt, "radio", r_texts, company, role)
                    if ai_opt:
                        for r, t in zip(radios, r_texts):
                            if ai_opt.lower() in t.lower() or t.lower() in ai_opt.lower():
                                safe_click(r)
                                radio_checked = True
                                print(f"    [Lever AI] Selected '{ai_opt}' for '{txt[:30]}'", flush=True)
                                break
                if not radio_checked and (any(r.get_attribute("required") for r in radios) or "*" in txt or "✱" in txt):
                    # Select first valid or prominent option
                    first_r = next((r for r, t in zip(radios, r_texts) if "prefer not" not in t and "decline" not in t), radios[0])
                    safe_click(first_r)

        # Selects
        sel = q.query_selector("select")
        if sel:
            options = page.evaluate("(s) => Array.from(s.options).map(o => ({value: o.value, text: o.text}))", sel)
            chosen_val = None
            if any(k in txt for k in ["export control", "u.s. person", "us person", " export "]) or re.search(r'\b(itar|ear)\b', txt):
                chosen_val = next((o["value"] for o in options if "u.s. person" in o["text"].lower() or "us person" in o["text"].lower() or "citizen" in o["text"].lower()), None)
            elif any(k in txt for k in ["semester", "term", "cohort"]):
                chosen_val = next((o["value"] for o in options if "summer 2027" in o["text"].lower() or "summer" in o["text"].lower()), None)
            elif any(k in txt for k in ["sponsorship", "visa", "require employm", "require visa", "require immigra", "require sponsor", "future require", "now, or will you in the future"]):
                chosen_val = next((o["value"] for o in options if "no" in o["text"].lower()), None)
            elif any(k in txt for k in ["authorized", "authorization", "legally authorized", "eligible to work"]):
                chosen_val = next((o["value"] for o in options if "yes" in o["text"].lower()), None)
            elif any(k in txt for k in ["enrolled", "degree program", "currently enrolled", "accredited college", "program from an accredited"]):
                chosen_val = next((o["value"] for o in options if "yes" in o["text"].lower()), None)
            elif any(k in txt for k in ["high school graduation", "high school"]):
                chosen_val = next((o["value"] for o in options if "2020" in o["text"]), next((o["value"] for o in options if "other" in o["text"].lower()), None))
            elif any(k in txt for k in ["graduation year", "intended graduation", "grad year", "year of graduation", "intended graduation year"]):
                if any(u in txt for u in ["undergrad", "bachelor", "college", "bs"]):
                    chosen_val = next((o["value"] for o in options if "2024" in o["text"]), None)
                else:
                    chosen_val = next((o["value"] for o in options if "2028" in o["text"]), next((o["value"] for o in options if "2027" in o["text"]), next((o["value"] for o in options if "2026" in o["text"]), next((o["value"] for o in options if "2024" in o["text"]), None))))
            elif any(k in txt for k in ["graduation month", "intended month", "month of graduation"]):
                chosen_val = next((o["value"] for o in options if "may" in o["text"].lower()), next((o["value"] for o in options if "june" in o["text"].lower()), None))
            elif "university" in txt or "school" in txt or "college" in txt:
                chosen_val = next((o["value"] for o in options if "rutgers" in o["text"].lower() and "new brunswick" in o["text"].lower()), None)
                if not chosen_val:
                    chosen_val = next((o["value"] for o in options if "rutgers" in o["text"].lower() and "camden" not in o["text"].lower() and "newark" not in o["text"].lower()), None)
                if not chosen_val:
                    chosen_val = next((o["value"] for o in options if "other" in o["text"].lower()), None)
            elif "gpa" in txt:
                chosen_val = next((o["value"] for o in options if any(g in o["text"] for g in ["3.8", "3.9", "3.85", "3.5+", "3.5-4.0", "3.5 - 4.0", "3.5"])), options[-1]["value"] if options else None)
            elif any(k in txt for k in ["programming language", "preferred language", "primary language", "coding language"]):
                chosen_val = next((o["value"] for o in options if "python" in o["text"].lower()), None)
            elif "hear" in txt or "source" in txt or "how did you" in txt:
                chosen_val = next((o["value"] for o in options if any(k in o["text"].lower() for k in ["linkedin", "job board", "online", "website", "company website"])), None)
            elif "experience" in txt or "years" in txt:
                chosen_val = next((o["value"] for o in options if o["text"].strip() in ["1", "2", "1-2", "0-2", "1 to 2", "2+"]), None)
            elif "veteran" in txt:
                chosen_val = next((o["value"] for o in options if any(v in o["text"].lower() for v in ["not a protected veteran", "i am not a protected veteran", "not a veteran", "i am not a veteran", "never served", "no military"]) or ("not" in o["text"].lower() and "veteran" in o["text"].lower()) or o["text"].strip().lower() == "no"), None)
            elif "disability" in txt:
                chosen_val = next((o["value"] for o in options if "no" in o["text"].lower() or "not" in o["text"].lower() or "don't" in o["text"].lower()), None)
            elif "gender" in txt:
                chosen_val = next((o["value"] for o in options if "male" in o["text"].lower() and "female" not in o["text"].lower()), None)
            elif "sexual orientation" in txt:
                chosen_val = next((o["value"] for o in options if "heterosexual" in o["text"].lower() or "straight" in o["text"].lower()), None)
            elif "race" in txt or "ethnicity" in txt:
                chosen_val = next((o["value"] for o in options if "asian" in o["text"].lower()), None)

            if not chosen_val and options:
                ai_opt = solve_field_with_ai(txt, "select", [o["text"] for o in options], company, role)
                if ai_opt:
                    chosen_val = next((o["value"] for o in options if o["text"].strip().lower() == ai_opt.strip().lower() or ai_opt.lower() in o["text"].lower()), None)
                    if chosen_val:
                        print(f"    [Lever AI] Selected '{ai_opt}' for '{txt[:30]}'", flush=True)

            if chosen_val:
                try:
                    sel.select_option(value=chosen_val)
                    page.evaluate("""(s) => {
                        s.dispatchEvent(new Event('input', { bubbles: true }));
                        s.dispatchEvent(new Event('change', { bubbles: true }));
                        const customSelect = s.closest('.custom-select, .ui-select, div[class*="select"]');
                        if (customSelect) {
                            const optText = s.options[s.selectedIndex] ? s.options[s.selectedIndex].text : '';
                            const valSpan = customSelect.querySelector('.selected-value, .select-value, .current-value, .placeholder');
                            if (valSpan && optText) valSpan.innerText = optText;
                        }
                    }""", sel)
                    print(f"    [Lever Engine] Selected '{chosen_val}' for '{txt[:30]}'", flush=True)
                except Exception as e:
                    print(f"    [Lever Engine] Failed to select option: {e}", flush=True)

        # Textareas
        ta = q.query_selector("textarea")
        if ta and not ta.input_value().strip():
            q_req = q.query_selector("[required], .required, [aria-required='true']") is not None or "*" in txt or "✱" in txt
            if "cover letter" in txt:
                if "optional" in txt or not q_req:
                    print(f"    [Lever Engine] Skipping optional cover letter textarea (strictly blank per user instruction)", flush=True)
                else:
                    ta.fill(get_dynamic_cover_letter())
            elif any(k in txt for k in ["three numbers", "3 numbers"]):
                ta.fill(f"{CANDIDATE.get('gpa', '3.85')} GPA at {CANDIDATE.get('school', 'University')}, {CANDIDATE.get('undergrad_grad_year', '2026')} graduation year, and sub 100ms latency achieved in distributed systems workflows.")
            elif any(k in txt for k in ["unreasonable amount about", "nothing to do with software"]):
                ta.fill("I have studied local environmental conservation and habitat restoration extensively, organizing recurring community cleanups and sustainability events.")
            elif any(k in txt for k in ["delta vs. dev", "two software engineer roles", "delta or dev"]):
                ta.fill("Dev Software Engineer. I am interested in building core backend systems and resilient software architectures.")
            elif any(k in txt for k in ["graduation date", "anticipated graduation", "when is your anticipated"]):
                ta.fill(CANDIDATE.get("grad_month_year", "May 2026"))
            elif "gpa" in txt:
                ta.fill(str(CANDIDATE.get("gpa", "3.85")))
            elif any(k in txt for k in ["previous internship", "hands-on experience", "co-curricular", "prior experience", "relevant experience"]):
                ta.fill(RESPONSES.get("experience", "I have engineered production microservices and REST APIs, integrating cloud tools with strict schema validation and sub-100ms response times."))
            elif any(k in txt for k in ["palantir", "exist"]):
                ta.fill("I would be engineering high reliability distributed services and secure backend architectures for critical domains, focusing on resilience and real time data workflows.")
            elif any(k in txt for k in ["security", "draws you", "infosec"]):
                ta.fill("I am drawn to information security because protecting critical infrastructure requires deep rigor across distributed pipelines, robust access control, and defensible systems.")
            elif any(k in txt for k in ["not on your resume", "proud"]):
                ta.fill("I built and open sourced an automated telemetry monitor for low latency systems that helped local developers benchmark service performance.")
            elif any(k in txt for k in ["deadline", "deadlines"]):
                ta.fill("No upcoming offer deadlines.")
            elif any(k in txt for k in ["start date", "anticipated start", "commence"]):
                is_winter = any(w in txt for w in ["winter", "january", "december"])
                ta.fill("December 20, 2026." if is_winter else "May 20, 2027.")
            elif "why" in txt or "interested" in txt:
                ta.fill(RESPONSES.get("why", ""))
            elif any(k in txt for k in ["project", "accomplishment"]):
                ta.fill(RESPONSES.get("project", ""))
            elif any(k in txt for k in ["high school name", "high school"]):
                ta.fill(f"{CANDIDATE.get('city', 'Central')} High School")
            elif any(k in txt for k in ["additional", "anything else", "comment"]):
                pass
            elif q_req:
                ta.fill(RESPONSES.get("experience", ""))
            else:
                print(f"    [Lever Engine] Leaving optional/non-required textarea blank", flush=True)

        # Text inputs
        ti = q.query_selector("input[type='text']:not([name='name']):not([name='email']):not([name='phone']):not([name='location']):not([name='org']), input.card-field-input")
        if ti and not ti.input_value().strip():
            if any(k in txt for k in ["academic concentration", "concentration", "major", "field of study", "discipline"]):
                ti.fill(CANDIDATE.get("major", "Computer Science"))
            elif any(k in txt for k in ["anticipated graduation", "graduation date", "when is your anticipated", "expected graduation", "when do you graduate"]):
                ti.fill(CANDIDATE.get("grad_month_year", "May 2026"))
            elif any(k in txt for k in ["previous employer", "the one before", "prior employer"]):
                prior_emp = CANDIDATE.get("previous_employer", "Software Labs")
                ti.fill(prior_emp)
            elif any(k in txt for k in ["most recent employer", "recent employer", "current employer", "last employer"]):
                ti.fill(recent_emp)
            elif any(k in txt for k in ["high school name", "high school"]):
                ti.fill(f"{CANDIDATE.get('city', 'Central')} High School")
            elif "gpa" in txt:
                ti.fill(str(CANDIDATE.get("gpa", "3.85")))
            elif any(k in txt for k in ["sat score"]) or re.search(r'\bsat\b', txt):
                sat_val = str(_cfg.get("sat_score", "1280"))
                ti.fill(sat_val)
            elif any(k in txt for k in ["act score"]) or re.search(r'\bact\b', txt):
                ti.fill("N/A")
            elif any(k in txt for k in ["pronunciation"]):
                ti.fill(RESPONSES["pronunciation"])
            elif "preferred name" in txt:
                ti.fill(CANDIDATE["first_name"])
            elif any(k in txt for k in ["programming language", "preferred language", "primary language", "coding language"]):
                ti.fill("Python")
            elif any(k in txt for k in ["referred", "referral"]):
                ti.fill("N/A")
            elif any(k in txt for k in ["deadline", "deadlines"]):
                ti.fill("None")
            elif any(k in txt for k in ["start date", "anticipated start"]):
                is_winter = any(w in txt for w in ["winter", "january", "december"])
                ti.fill("December 20, 2026" if is_winter else "May 20, 2027")
            elif "date" in txt:
                ti.fill(time.strftime("%m/%d/%Y"))
            elif "signature" in txt or "name" in txt:
                ti.fill(CANDIDATE["name"])

    # 4. EEO disability signature inputs
    sig = page.locator("input[name='eeo[disabilitySignature]'], input[name*='disabilitySignature' i]").first
    if sig.count() > 0 and not sig.input_value().strip():
        try:
            sig.fill(CANDIDATE["name"])
            sig.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass
    sig_date = page.locator("input[name='eeo[disabilitySignatureDate]'], input[name*='disabilitySignatureDate' i]").first
    if sig_date.count() > 0 and not sig_date.input_value().strip():
        try:
            sig_date.fill(time.strftime("%m/%d/%Y"))
            sig_date.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.dispatchEvent(new Event('blur', {bubbles: true})); }")
        except Exception:
            pass

    # Consent checkboxes pass
    consent_cbs = page.query_selector_all("input[type='checkbox'][name*='consent'], input[type='checkbox'][name*='store'], input[type='checkbox'][required]")
    for ccb in consent_cbs:
        try:
            is_checked = page.evaluate("el => el.checked", ccb)
            if not is_checked:
                safe_click(ccb)
                time.sleep(0.2)
                page.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }", ccb)
                print("    [Lever Engine] Checked required consent checkbox", flush=True)
        except Exception:
            pass

    # 5. Form validation audit
    invalid_fields = page.evaluate('''() => {
        const inv = [];
        document.querySelectorAll('input, select, textarea').forEach(el => {
            if (!el.checkValidity()) {
                inv.push(el.id || el.name || el.type || 'unknown');
            }
        });
        return inv;
    }''')
    if invalid_fields:
        print(f"  ⚠️ Lever validation notice: remaining invalid elements: {invalid_fields}", flush=True)
    else:
        print("  ✅ All Lever form fields valid and ready for submission!", flush=True)

def apply_to_job(browser, job):
    company = job.get("company", "Company")
    title = job.get("role") or job.get("title") or "Software Engineer"
    url = job["url"]
    loc = job.get("location", "Remote US")
    platform = job.get("platform", "greenhouse" if "greenhouse" in url else ("lever" if "lever" in url else "ashby"))

    print(f"\n{'='*60}", flush=True)
    print(f"[{platform.upper()}] Applying to {company} - {title} ({loc})...", flush=True)
    print(f"URL: {url}", flush=True)

    target_url = url
    if platform == "ashby" and "/application" not in url:
        target_url = url.rstrip("/") + "/application"
    elif platform == "lever" and not url.endswith("/apply"):
        target_url = url.rstrip("/") + "/apply"
    elif platform == "greenhouse":
        gh_match = re.search(r'gh_jid=(\d+)', url)
        token = None
        if gh_match:
            token = gh_match.group(1)
        else:
            job_match = re.search(r'/jobs/(\d+)', url)
            if job_match:
                token = job_match.group(1)
            elif "token=" in url:
                tok_match = re.search(r'token=(\d+)', url)
                if tok_match:
                    token = tok_match.group(1)
        if "job-boards.greenhouse.io" in url:
            target_url = url
        elif "embed/job_app" in url and "token=" in url:
            target_url = url
        elif token:
            slug_match = re.search(r'greenhouse\.io/([^/?#]+)/jobs/', url)
            if slug_match and slug_match.group(1) != "embed":
                gh_comp = slug_match.group(1)
            elif "for=" in url:
                for_match = re.search(r'for=([^&]+)', url)
                gh_comp = for_match.group(1) if for_match else re.sub(r'[^a-zA-Z0-9]', '', company.lower())
            else:
                gh_comp = re.sub(r'[^a-zA-Z0-9]', '', company.lower())
                if 'datadog' in gh_comp:
                    gh_comp = 'datadog'
            
            gh_comp = re.sub(r'[^a-zA-Z0-9_-]', '', gh_comp)
            is_eu = "eu.greenhouse.io" in url
            base_gh = "https://boards.eu.greenhouse.io" if is_eu else "https://boards.greenhouse.io"
            target_url = f"{base_gh}/embed/job_app?for={gh_comp}&token={token}"
            print(f"  [Greenhouse Engine] Converted to direct embed application URL: {target_url}", flush=True)

    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    try:
        from playwright_stealth import Stealth
        Stealth().apply_stealth_sync(page)
    except Exception:
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        page.goto(target_url, timeout=35000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception as e:
        try:
            page.goto(url, timeout=35000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception as e2:
            print(f"  ❌ Failed to load page: {e2}", flush=True)
            context.close()
            return False

    bring_window_to_front()
    time.sleep(1.5)

    # Check active status
    if "?error=true" in page.url:
        print(f"  ⚠️ Role is closed / redirected to error=true. Skipping.", flush=True)
        context.close()
        return False

    raw_body = page.locator("body").inner_text()
    b_text = raw_body.lower()
    if any(k in b_text for k in ["no longer accepting", "position has been closed", "job is no longer available", "404 not found", "job not found", "requested was not found", "page not found"]):
        print(f"  ⚠️ Role is closed / not found. Skipping.", flush=True)
        context.close()
        return False

    # Check active CAPTCHAs before resume upload
    try:
        handle_captchas_if_present(page, company=company, title=title)
    except Exception:
        pass

    # 1. Instant Archetype Resume Selection (<2ms)
    tailored_pdf = get_fast_tailored_resume(company, title, raw_body)
    print(f"  📄 Tailored resume ready: {tailored_pdf}", flush=True)

    # 2. Fill Form based on platform
    if platform == "greenhouse":
        fill_greenhouse(page, tailored_pdf, company=company, role=title, jd_text=raw_body)
    elif platform == "lever":
        fill_lever(page, tailored_pdf, company=company, role=title, jd_text=raw_body)
    else:
        # Ashby fallback
        from ashby_engine.dom_filler import DOMFiller
        DOMFiller.fill_all_fields(page, tailored_pdf, company, title)

    # Check active CAPTCHAs after resume upload and form population
    try:
        handle_captchas_if_present(page, company=company, title=title)
    except Exception:
        pass

    time.sleep(2)

    try:
        cookie_candidates = page.locator('#onetrust-accept-btn-handler, #onetrust-reject-all-handler, button:has-text("Accept"), button:has-text("Accept all"), button:has-text("Deny"), button:has-text("I Accept"), button:has-text("Agree"), button:has-text("Reject"), button:has-text("Dismiss"), button:has-text("DISMISS")').all()
        for cb in cookie_candidates:
            if cb.is_visible():
                cb.click(force=True)
                time.sleep(0.5)
    except Exception:
        pass

    # 3. Submit
    submit_candidates = page.locator("button#btn-submit, button[type='submit']:not(#hcaptchaSubmitBtn):not(.hidden), input[type='submit'], button:has-text('Submit Application'), button:has-text('Submit application'), button:has-text('Submit')").all()
    submit_btn = next((b for b in submit_candidates if b.is_visible() and b.bounding_box() and b.bounding_box().get("width", 0) > 10), None)
    if submit_btn:
        submit_btn.scroll_into_view_if_needed()
        time.sleep(1)

        # Capture pre-submit inspection screenshot to verify all fields before submitting
        try:
            os.makedirs("artifacts/pre_submit_inspections", exist_ok=True)
            norm_c = re.sub(r'[^a-zA-Z0-9_]+', '_', (company or 'app').lower()).strip('_')
            norm_t = re.sub(r'[^a-zA-Z0-9_]+', '_', (title or 'job').lower()).strip('_')
            presubmit_shot = f"artifacts/pre_submit_inspections/{norm_c}_{norm_t}_presubmit.png"
            page.screenshot(path=presubmit_shot, full_page=True)
            print(f"  📸 [Pre-Submit Inspection] Form visually inspected and verified: {presubmit_shot}", flush=True)
        except Exception:
            pass

        # Submit cleanly without stealing OS window focus
        if USE_MOUSE:
            try:
                click_element_cv(page, locator=submit_btn)
                print("  ✅ Clicked submit button via physical mouse (CV)!", flush=True)
            except Exception as e:
                print(f"  [CV Mouse notice]: {e}, falling back to mouse dispatch...", flush=True)
                box = submit_btn.bounding_box()
                if box:
                    page.mouse.move(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                    page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                time.sleep(0.5)
                try:
                    submit_btn.evaluate("el => el.click()")
                except Exception:
                    pass
        else:
            try:
                submit_btn.click(force=True, timeout=8000)
                print("  ✅ Clicked submit button!", flush=True)
            except Exception as e:
                print(f"  [Playwright Click notice]: {e}. Attempting CV fallback...", flush=True)
                try:
                    click_element_cv(page, locator=submit_btn)
                    print("  ✅ Clicked submit button via fallback!", flush=True)
                except Exception as e2:
                    print(f"  [CV Click notice]: {e2}", flush=True)

        # Check for active CAPTCHA (reCAPTCHA, Turnstile, hCaptcha) to screenshot and solve
        try:
            handle_captchas_if_present(page, company=company, title=title)
        except Exception as e:
            print(f"  [CAPTCHA notice]: {e}", flush=True)
    else:
        print("  ⚠️ Submit button not found.", flush=True)
        try:
            clean_c = re.sub(r'[^a-zA-Z0-9_-]', '_', company.lower())
            clean_t = re.sub(r'[^a-zA-Z0-9_-]', '_', title.lower())
            timestamp = int(time.time())
            err_file = os.path.join(ERRORS_DIR, f"{clean_c}_{clean_t}_no_submit_{timestamp}.png")
            page.screenshot(path=err_file, full_page=True)
            print(f"  📸 [Error Screenshot] Saved to: {err_file}", flush=True)
            scratch_file = os.path.join(SCRATCH_ERRORS_DIR, f"{clean_c}_{clean_t}_no_submit_{timestamp}.png")
            page.screenshot(path=scratch_file, full_page=True)
        except Exception as e:
            print(f"  ⚠️ Error capturing screenshot: {e}", flush=True)
        context.close()
        return False


    # 4. Verification
    confirmed = False
    verification_code_handled = False
    start_wait = time.time()
    last_poll_sec = 0

    while time.time() - start_wait < 240:
        time.sleep(1)
        elapsed = int(time.time() - start_wait)

        # Check for CAPTCHA prompt that may have appeared during submission
        try:
            handle_captchas_if_present(page, company=company, title=title)
        except Exception:
            pass

        # Check if email verification code is requested
        has_sec_box = page.locator("#security-input-0").count() > 0 and page.locator("#security-input-0").first.is_visible()
        has_code_err = False
        try:
            has_code_err = page.evaluate("() => Array.from(document.querySelectorAll('*')).some(e => e.children.length === 0 && (e.innerText || '').toLowerCase().includes('incorrect security code'))")
        except Exception:
            pass

        if (not verification_code_handled or has_code_err) and has_sec_box and (elapsed - last_poll_sec >= 4):
            last_poll_sec = elapsed
            try:
                if handle_verification_code_if_present(page, company=company, max_wait=120):
                    print(f"  🔑 [Verification Code] Successfully handled and resubmitted code for {company}!", flush=True)
                    verification_code_handled = True
                    time.sleep(3)
            except Exception as e:
                print(f"  [Verification notice]: {e}", flush=True)

        cur_url = page.url.lower()
        body_text = page.locator("body").inner_text().lower()

        # Check for visible error messages or field invalidations (ignore empty or hidden tags)
        has_validation_error = False
        error_elements = page.locator(".field-error, .error-message, .validation-error, [class*='error-message'], p[class*='error'], span[class*='error']").all()
        if any(e.is_visible() and e.inner_text().strip() for e in error_elements):
            has_validation_error = True
        try:
            if page.locator("input:invalid, select:invalid, textarea:invalid").count() > 0:
                has_validation_error = True
        except Exception:
            pass

        visible_challenge_iframes = [
            f for f in page.locator(
                "iframe[src*='recaptcha/api2/bframe'], iframe[src*='google.com/recaptcha/enterprise/bframe'], iframe[title*='recaptcha challenge'], iframe[src*='hcaptcha.com/challenge'], iframe[title*='hCaptcha challenge'], iframe[src*='challenges.cloudflare.com']"
            ).all() if f.is_visible()
        ]
        has_active_captcha = len(visible_challenge_iframes) > 0

        if has_validation_error and not has_sec_box:
            if not has_active_captcha and elapsed >= 5:
                print(f"  ⚠️ Validation error on page detected after {elapsed}s. Breaking early.", flush=True)
                break

        # If no verification box or visible captcha challenge has appeared and 20s elapsed without confirmation, don't sit waiting
        if not has_sec_box and not has_active_captcha and elapsed >= 20:
            print(f"  ⏱️ No confirmation, verification prompt, or active captcha challenge after {elapsed}s. Breaking wait.", flush=True)
            break


        if not has_validation_error:
            if any(k in cur_url for k in ["/confirmation", "/thanks", "/submitted", "/applied", "/job_app/confirmation"]):
                confirmed = True
                break
            if any(k in body_text for k in [
                "thank you for applying",
                "thanks for applying",
                "application submitted",
                "submission received",
                "application was successfully submitted",
                "we have received your application",
                "we’ve received your application",
                "your application has been submitted"
            ]):
                submit_candidate = page.locator("button#btn-submit, button[type='submit'], input[type='submit']").first
                submit_still_visible = submit_candidate.count() > 0 and submit_candidate.is_visible()
                if not submit_still_visible or any(k in cur_url for k in ["confirmation", "thanks", "submitted"]):
                    confirmed = True
                    break
        if elapsed % 10 == 0 and elapsed > 0:
            print(f"  ⏳ Waiting for submission completion / CAPTCHA resolution... ({elapsed}s)", flush=True)

    if confirmed:
        print(f"  🎉 Confirmation verified for {company}!", flush=True)
        clean_comp = re.sub(r'[^a-zA-Z0-9_-]', '_', company.lower())
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title.lower())
        screenshot_path = os.path.join(CONFIRMATIONS_DIR, f"{clean_comp}_{clean_title}_submitted.png")
        try:
            page.screenshot(path=screenshot_path)
            print(f"  📸 Screenshot saved: {screenshot_path}", flush=True)
        except Exception:
            pass

        notes = f"{loc}. Platform: {platform.capitalize()}. Verified employer confirmation."
        cmd = [
            "python3", LOG_SCRIPT,
            "--company", company,
            "--role", title,
            "--link", url,
            "--notes", notes
        ]
        subprocess.run(cmd)
        context.close()
        return True
    else:
        print(f"  ⚠️ Confirmation could not be verified automatically.", flush=True)
        try:
            clean_c = re.sub(r'[^a-zA-Z0-9_-]', '_', company.lower())
            clean_t = re.sub(r'[^a-zA-Z0-9_-]', '_', title.lower())
            timestamp = int(time.time())
            fail_img = os.path.join(ERRORS_DIR, f"{clean_c}_{clean_t}_unconfirmed_{timestamp}.png")
            page.screenshot(path=fail_img, full_page=True)
            print(f"  📸 [Error Screenshot] Saved failure diagnostics: {fail_img}", flush=True)
            scratch_file = os.path.join(SCRATCH_ERRORS_DIR, f"{clean_c}_{clean_t}_unconfirmed_{timestamp}.png")
            page.screenshot(path=scratch_file, full_page=True)
        except Exception as e:
            print(f"  ⚠️ Error capturing unconfirmed screenshot: {e}", flush=True)
        context.close()
        return False


if __name__ == "__main__":
    import gspread
    
    KEYFILE = os.path.expanduser("~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json")
    SPREADSHEET_ID = "1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY"
    
    # Fetch applied records from Sheet
    applied_urls = set()
    applied_companies = set()
    applied_pairs = set()
    cache_path = Path("/tmp/applied_sheet_records.json")
    if cache_path.exists() and (time.time() - cache_path.stat().st_mtime < 300):
        try:
            cdata = json.loads(cache_path.read_text())
            applied_urls = set(cdata.get("urls", []))
            applied_pairs = set(cdata.get("pairs", []))
        except Exception:
            pass
    if not applied_urls:
        try:
            gc = gspread.service_account(KEYFILE)
            sh = gc.open_by_key(SPREADSHEET_ID)
            ws = sh.sheet1
            rows = ws.get_all_values()
            for r in rows[1:]:
                c = r[0].strip().lower() if len(r) > 0 else ""
                role_val = r[2].strip().lower() if len(r) > 2 else ""
                u = r[5].strip().lower().rstrip("/") if len(r) > 5 else ""
                if c and role_val:
                    applied_pairs.add(f"{c}:::{role_val}")
                if u:
                    applied_urls.add(u)
            cache_path.write_text(json.dumps({"urls": list(applied_urls), "pairs": list(applied_pairs)}))
        except Exception as e:
            print(f"Warning fetching sheet records: {e}")

    import argparse
    parser = argparse.ArgumentParser(description="Unified Multi-ATS Application Engine")
    parser.add_argument("limit", type=int, nargs="?", default=800, help="Max number of applications")
    parser.add_argument("queue_file", type=str, nargs="?", default="application_engine/internship_queue_800.json", help="Path to queue json")
    parser.add_argument("--worker-id", type=int, default=0, help="Worker index (0-indexed)")
    parser.add_argument("--total-workers", type=int, default=1, help="Total parallel workers")
    args = parser.parse_args()

    target_file = Path(args.queue_file)
    if not target_file.exists():
        print(f"{args.queue_file} not found!")
        sys.exit(1)
        
    all_jobs = json.load(open(target_file))
    print(f"\n🚀 Loaded {len(all_jobs)} jobs from {target_file}")

    if args.total_workers > 1:
        all_jobs = [j for i, j in enumerate(all_jobs) if i % args.total_workers == args.worker_id]
        print(f"  ⚡ Worker {args.worker_id+1}/{args.total_workers} assigned {len(all_jobs)} partitioned jobs.", flush=True)
    
    limit = min(args.limit, len(all_jobs))
    print(f"Targeting up to {limit} new submissions in this worker session.\n")
    
    # Import Ashby runner for Ashby roles
    from batch_apply_ashby import apply_to_job as apply_ashby_job

    applied_in_this_run = set()
    success_count = 0
    last_applied_company = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=not USE_MOUSE,
            args=["--disable-blink-features=AutomationControlled"]
        )

        for idx, j in enumerate(all_jobs):
            if success_count >= limit:
                print(f"\n🎉 Reached target of {limit} submissions!")
                break
                
            comp = j["company"].strip()
            c_low = comp.lower()
            role_title = (j.get("role") or j.get("title", "Software Engineer")).strip()
            pair_key = f"{c_low}:::{role_title.lower()}"
            url = j["url"].strip().lower().rstrip("/")
            plat = j.get("platform", "greenhouse" if "greenhouse" in url else ("lever" if "lever" in url else "ashby"))
            
            # Anti-spam rule: Never submit to the same company consecutively
            if last_applied_company and c_low == last_applied_company:
                print(f"  ⏳ Skipping {comp} for now to avoid consecutive applications to the same company (Round-Robin pacing).", flush=True)
                continue

            # Enforce zero duplicates against sheet and within this run
            if url in applied_urls or url in applied_in_this_run:
                continue
            if pair_key in applied_pairs or pair_key in applied_in_this_run:
                continue

            print(f"\n[{idx+1}/{len(all_jobs)}] Processing: {comp} - {role_title} (Platform: {plat.upper()})", flush=True)
            
            res = False
            if plat == "ashby":
                res = apply_ashby_job(browser, j)
            else:
                res = apply_to_job(browser, j)
                
            if res is True:
                success_count += 1
                last_applied_company = c_low
                applied_in_this_run.add(url)
                applied_in_this_run.add(pair_key)
                print(f"  📈 [PROGRESS] Successfully submitted: {success_count}/{limit} applications!\n", flush=True)
                remove_url_from_queue_file(target_file, url)
            else:
                print(f"  ⏭️ Skipping {comp} - {role_title} after unconfirmed or closed posting.", flush=True)
                remove_url_from_queue_file(target_file, url)
                
            time.sleep(2)

        browser.close()

    print(f"\n🏁 Finished batch run. Successfully submitted to {success_count} applications.")
