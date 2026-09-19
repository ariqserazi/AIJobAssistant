#!/usr/bin/env python3
"""
dom_filler.py - Atomic DOM interaction and form-filling handlers for Ashby.
"""

import os
import sys
import time
from .dom_scanner import DOMScanner, FormField
from .field_matcher import FieldMatcher

try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from question_logger import log_discovered_question
    from config_loader import load_config
    from ai_form_solver import solve_field_with_ai
except Exception:
    def log_discovered_question(*args, **kwargs):
        pass
    def load_config():
        return {}
    def solve_field_with_ai(*args, **kwargs):
        return None


class DOMFiller:
    """Fills form fields on the page accurately and cleanly."""

    @staticmethod
    def upload_resume(page, resume_pdf_path: str) -> bool:
        """Uploads tailored resume PDF to file inputs, skipping the top autofill dropzone and optional cover letter."""
        file_inputs = page.query_selector_all("input[type='file']")
        if not file_inputs:
            return False

        uploaded = False
        for fi in file_inputs:
            fe_txt = fi.evaluate('''el => {
                const entry = el.closest('[class*="field-entry"], fieldset, [data-field-path]') || el.parentElement?.parentElement || el.parentElement;
                return entry ? entry.innerText.toLowerCase() : "";
            }''')

            # Skip the top "Autofill from resume" dropzone
            if "autofill" in fe_txt and "autofill from resume" in fe_txt:
                print("  [File Upload] Skipping top autofill dropzone.", flush=True)
                continue

            if "cover letter" in fe_txt and "resume" not in fe_txt and "portfolio" not in fe_txt:
                print("  [File Upload] Skipping optional cover letter upload.", flush=True)
                continue

            if "transcript" in fe_txt:
                _cfg = load_config()
                transcript_path = _cfg.get("transcript_pdf", "")
                if transcript_path and os.path.exists(transcript_path):
                    try:
                        fi.set_input_files(transcript_path)
                        time.sleep(2.0)
                        uploaded = True
                        print(f"  [File Upload] Uploaded Transcript PDF: {os.path.basename(transcript_path)}", flush=True)
                        continue
                    except Exception as e:
                        print(f"  [File Upload] Transcript notice: {e}", flush=True)

            try:
                fi.set_input_files(resume_pdf_path)
                time.sleep(2.0)
                uploaded = True
                label = "Resume" if "resume" in fe_txt else ("Portfolio" if "portfolio" in fe_txt else "Document")
                print(f"  [File Upload] Uploaded PDF to '{label}' file input: {os.path.basename(resume_pdf_path)}", flush=True)
            except Exception as e:
                print(f"  [File Upload] Upload notice: {e}", flush=True)

        if uploaded:
            time.sleep(1.0)

        return uploaded

    @staticmethod
    def fill_combobox(page, field: FormField, val: str) -> bool:
        """Handles Ashby comboboxes and dropdowns with robust option clicking."""
        if not val:
            return False
        cb = field.input_element
        try:
            cb.scroll_into_view_if_needed()
            toggle_btn = field.container.query_selector("button[class*='toggleButton'], button[aria-label*='toggle' i]")
            if toggle_btn:
                try:
                    toggle_btn.click(force=True, timeout=2500)
                except Exception:
                    toggle_btn.evaluate("e => e.click()")
            else:
                try:
                    cb.click(force=True, timeout=2500)
                except Exception:
                    cb.evaluate("e => e.click()")
            time.sleep(0.3)

            # Clear any prefilled stale text
            try:
                cb.click(force=True, timeout=2500)
            except Exception:
                cb.evaluate("e => e.focus()")
            page.keyboard.press("Meta+a")
            page.keyboard.press("Backspace")
            time.sleep(0.2)

            tl = field.title.lower()

            # A. University / School
            if any(k in tl for k in ["university", "school", "college", "recent university"]):
                # Directly target Rutgers University, New Brunswick
                page.keyboard.type("New Brunswick", delay=30)
                rutgers_opt = page.locator("[role='option']:has-text('New Brunswick')").first
                if not rutgers_opt.is_visible():
                    rutgers_opt = page.locator("text='Rutgers University, New Brunswick'").first
                if not rutgers_opt.is_visible():
                    page.keyboard.press("Meta+a")
                    page.keyboard.press("Backspace")
                    page.keyboard.type("Rutgers", delay=30)
                    time.sleep(0.8)
                    for opt in page.locator("[role='option'], [class*='option'], [class*='result']").all():
                        if opt.is_visible():
                            otxt = opt.inner_text().strip().lower()
                            if "camden" in otxt or "newark" in otxt or "medical" in otxt:
                                continue
                            if "new brunswick" in otxt:
                                rutgers_opt = opt
                                break
                            if "rutgers" in otxt and ("state university" in otxt or "new jersey" in otxt):
                                rutgers_opt = opt
                                break
                if rutgers_opt and rutgers_opt.is_visible():
                    opt_txt = rutgers_opt.inner_text().strip()
                    try:
                        rutgers_opt.click(force=True, timeout=2500)
                    except Exception:
                        rutgers_opt.evaluate("e => e.click()")
                    print(f"    [Combobox] {field.title[:30]} -> {opt_txt}", flush=True)
                    return True
                else:
                    print("    ⚠️ [Combobox Warning] Rutgers New Brunswick option not found yet.", flush=True)
                    return False

            # B. Location / City
            elif any(k in tl for k in ["location", "city", "where do you live", "where are you located"]):
                page.keyboard.type("Piscataway", delay=30)
                time.sleep(0.6)
                loc_opt = page.locator("[role='option']:has-text('Piscataway'), [role='option']:has-text('New Jersey'), [role='option']:has-text('New York')").first
                if loc_opt.is_visible():
                    opt_txt = loc_opt.inner_text().strip()
                    try:
                        loc_opt.click(force=True, timeout=2500)
                    except Exception:
                        loc_opt.evaluate("e => e.click()")
                    print(f"    [Combobox] {field.title[:30]} -> {opt_txt}", flush=True)
                    return True

            # C. Field of study
            elif any(k in tl for k in ["field of study", "major", "discipline"]):
                page.keyboard.type("Computer Science", delay=30)
                time.sleep(0.6)
                cs_opt = page.locator("[role='option']:has-text('Computer Science')").first
                if cs_opt.is_visible():
                    try:
                        cs_opt.click(force=True, timeout=2500)
                    except Exception:
                        cs_opt.evaluate("e => e.click()")
                    print(f"    [Combobox] {field.title[:30]} -> Computer Science", flush=True)
                    return True

            # D. Year of graduation
            elif any(k in tl for k in ["year of graduation", "graduation year", "grad year"]):
                page.keyboard.type(val or "2027", delay=30)
                time.sleep(0.6)
                yr_opt = page.locator(f"[role='option']:has-text('{val}'), [role='option']:has-text('2027'), [role='option']:has-text('2028')").first
                if yr_opt.is_visible():
                    try:
                        yr_opt.click(force=True, timeout=2500)
                    except Exception:
                        yr_opt.evaluate("e => e.click()")
                    print(f"    [Combobox] {field.title[:30]} -> {val}", flush=True)
                    return True

            # General: Type val and click matching option
            page.keyboard.type(val, delay=30)
            time.sleep(0.5)
            opt = page.locator(f"[role='option']:has-text('{val}'), [class*='option']:has-text('{val}')").first
            if opt.is_visible():
                try:
                    opt.click(force=True, timeout=2500)
                except Exception:
                    opt.evaluate("e => e.click()")
                print(f"    [Combobox] {field.title[:30]} -> {val}", flush=True)
                return True

            if any(k in tl for k in ["university", "school", "college"]):
                print(f"    ⚠️ [Combobox Warning] Strictly skipping generic fallback for school to prevent campus mismatch.", flush=True)
                return False

            first_opt = page.locator("[role='option']").first
            if first_opt.is_visible():
                first_txt = first_opt.inner_text().strip()
                try:
                    first_opt.click(force=True, timeout=2500)
                except Exception:
                    first_opt.evaluate("e => e.click()")
                print(f"    [Combobox] {field.title[:30]} -> {first_txt} (first option)", flush=True)
                return True

            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
            print(f"    [Combobox] {field.title[:30]} -> {val} (keyboard Enter)", flush=True)
            return True
        except Exception as e:
            print(f"    [Combobox] Notice on {field.title[:30]}: {e}", flush=True)
            return False
        finally:
            try:
                time.sleep(0.2)
                page.keyboard.press("Escape")
            except Exception:
                pass


    @staticmethod
    def fill_text(page, field: FormField, val: str) -> bool:
        """Fills standard text, email, phone, and link inputs."""
        if not val:
            return False
        el = field.input_element
        tl = field.title.lower()
        try:
            input_type = (el.get_attribute("type") or "").lower()
            if input_type == "number":
                import re
                num_val = re.sub(r"[^0-9.]", "", val)
                if num_val:
                    val = num_val
            el.scroll_into_view_if_needed()
            try:
                el.click(force=True, timeout=2500)
            except Exception:
                try:
                    el.evaluate("e => e.focus()")
                except Exception:
                    pass

            if input_type == "tel" or any(k in tl for k in ["phone", "mobile", "cell"]):
                # Use native keyboard keystrokes to ensure mask and React listeners trigger cleanly
                page.keyboard.press("Meta+a")
                page.keyboard.press("Backspace")
                clean_phone = "".join(c for c in val if c.isdigit())
                page.keyboard.type(clean_phone if len(clean_phone) == 10 else val, delay=20)
            elif input_type == "date" or any(k in tl for k in ["graduation date", "grad date", "date"]) or "pick date" in (el.get_attribute("placeholder") or "").lower():
                page.keyboard.press("Meta+a")
                page.keyboard.press("Backspace")
                page.keyboard.type(val, delay=25)
                time.sleep(0.2)
                page.keyboard.press("Enter")
            else:
                el.fill(val)

            try:
                el.evaluate("e => { e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); e.dispatchEvent(new Event('blur', {bubbles: true})); }")
                page.keyboard.press("Escape")
                page.evaluate("() => { document.querySelectorAll('.react-datepicker-popper, .react-datepicker, [data-floating-ui-portal]').forEach(e => e.remove()); }")
            except Exception:
                pass
            print(f"    [Text] {field.title[:30]} -> {val[:35]}", flush=True)
            return True
        except Exception as e:
            print(f"    [Text] Notice on {field.title[:30]}: {e}", flush=True)
            return False

    @staticmethod
    def fill_textarea(page, field: FormField, val: str) -> bool:
        """Fills multiline essay and free-text inputs with full React synthetic event dispatching."""
        if not val:
            return False
        el = field.input_element
        try:
            el.scroll_into_view_if_needed()
            try:
                el.click(force=True, timeout=2500)
            except Exception:
                try:
                    el.evaluate("e => e.focus()")
                except Exception:
                    pass
            el.fill(val)
            try:
                el.evaluate("e => { e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); e.dispatchEvent(new Event('blur', {bubbles: true})); }")
            except Exception:
                pass
            print(f"    [Textarea] {field.title[:30]} -> {val[:40]}...", flush=True)
            return True
        except Exception as e:
            print(f"    [Textarea] Notice on {field.title[:30]}: {e}", flush=True)
            return False

    @staticmethod
    def fill_radio(page, field: FormField, val: str, force_reclick: bool = False) -> bool:
        """Fills radio buttons or button groups safely without CSS syntax errors."""
        if not val:
            return False
        container = field.container
        val_lower = val.lower()
        import re

        try:
            try:
                page.evaluate("() => { document.querySelectorAll('.react-datepicker-popper, .react-datepicker, [data-floating-ui-portal]').forEach(e => { if (e !== document.activeElement && !e.contains(document.activeElement)) e.remove(); }); }")
            except Exception:
                pass
            # 1. First priority: Real radio inputs (input[type='radio'])
            radios = container.query_selector_all("input[type='radio']")
            if radios:
                best_match = None
                for r in radios:
                    parent = r.evaluate_handle("el => el.closest('.ashby-application-form-input-radio-group-option') || el.closest('[class*=\"radio-group-option\"]') || el.closest('[class*=\"option\"]') || el.closest('label') || el.parentElement?.parentElement || el.parentElement")
                    txt = parent.as_element().inner_text().strip().lower() if parent.as_element() else ""
                    rid = r.get_attribute("id")
                    if not txt and rid:
                        lbl = container.query_selector(f"label[for='{rid}']")
                        if lbl:
                            txt = lbl.inner_text().strip().lower()

                    # Strict guards against semantic traps
                    if val_lower == "male" and ("female" in txt or txt == "female"):
                        continue
                    if val_lower == "asian" and ("mixed" in txt or "multiple" in txt):
                        continue
                    if val_lower == "yes" and txt.startswith("no"):
                        continue
                    if val_lower == "no" and txt.startswith("yes"):
                        continue
                    # Veteran status guards: never match "identify as one or more" when target is "not a protected veteran"
                    if "not" in val_lower and ("not" not in txt or "identify as one" in txt or "listed above" in txt):
                        continue
                    if "not" not in val_lower and "not" in txt:
                        continue
                    if "decline" not in val_lower and "decline" in txt:
                        continue

                    # Exact match
                    if val_lower == txt:
                        best_match = (r, parent, rid, txt)
                        break
                    # High confidence substring match
                    if val_lower in txt or txt in val_lower:
                        if not best_match:
                            best_match = (r, parent, rid, txt)

                if best_match:
                    r, parent, rid, txt = best_match
                    is_chk = False
                    try:
                        is_chk = r.is_checked()
                    except Exception:
                        pass

                    # If already checked, never re-click (which unchecks Ashby radios!)
                    if is_chk and not force_reclick:
                        print(f"    [Radio] {field.title[:30]} -> {val} (already checked)", flush=True)
                        return True

                    r.scroll_into_view_if_needed()
                    time.sleep(0.1)

                    loc_target = None
                    if rid:
                        try:
                            loc_target = page.locator(f"label[for='{rid}']").first
                        except Exception:
                            pass
                    if not loc_target or not loc_target.is_visible():
                        loc_target = page.locator("label").filter(has_text=re.compile(re.escape(txt), re.I)).first
                    if not loc_target or not loc_target.is_visible():
                        loc_target = page.locator("[class*='radio-group-option']").filter(has_text=re.compile(re.escape(txt), re.I)).first

                    use_mouse_env = os.environ.get("USE_MOUSE", "").lower() in ["true", "1", "yes"]
                    is_custom_question = len(field.options) > 2 or any(k in field.title.lower() for k in ["why", "how", "what", "which", "gravity", "orbit", "astronaut", "physics"])

                    if loc_target and loc_target.is_visible():
                        loc_target.scroll_into_view_if_needed()
                        time.sleep(0.15)
                        if use_mouse_env:
                            try:
                                from .cv_mouse import click_element_cv
                            except Exception:
                                try:
                                    from cv_mouse import click_element_cv
                                except Exception:
                                    from cv_mouse_fallback import click_element_cv
                            print(f"    [CV Mouse] Gliding physical OS mouse to click radio option: '{txt[:45]}'...", flush=True)
                            click_element_cv(page, locator=loc_target)
                        else:
                            try:
                                loc_target.click(force=True, timeout=2500)
                            except Exception:
                                try:
                                    loc_target.evaluate("el => el.click()")
                                except Exception:
                                    pass
                    else:
                        r.check(force=True)

                    time.sleep(0.2)
                    try:
                        if not r.is_checked():
                            r.check(force=True)
                    except Exception:
                        pass

                    print(f"    [Radio] {field.title[:30]} -> {val} (checked input)", flush=True)
                    return True

            # 2. Second priority: Button groups with data-option (e.g. Yes/No button toggles)
            data_btns = container.query_selector_all("button[data-option]")
            for btn in data_btns:
                d_opt = (btn.get_attribute("data-option") or "").strip().lower()
                if d_opt == val_lower or (len(val_lower) > 2 and (val_lower in d_opt or d_opt in val_lower)):
                    btn.scroll_into_view_if_needed()
                    is_pressed = btn.get_attribute("aria-pressed") == "true" or btn.get_attribute("aria-checked") == "true"
                    if not is_pressed or force_reclick:
                        btn.click(force=True)
                        try:
                            btn.evaluate("el => { el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
                        except Exception:
                            pass
                        print(f"    [Radio] {field.title[:30]} -> {val} (data-option clicked)", flush=True)
                    else:
                        print(f"    [Radio] {field.title[:30]} -> {val} (already pressed)", flush=True)
                    return True

            # 3. Third priority: Buttons or custom elements by text
            buttons_and_labels = container.query_selector_all("button, [role='radio']")
            for bl in buttons_and_labels:
                txt = bl.inner_text().strip().lower()
                if val_lower == "male" and ("female" in txt or txt == "female"):
                    continue
                if val_lower == "asian" and ("mixed" in txt or "multiple" in txt):
                    continue
                if val_lower == "yes" and txt.startswith("no"):
                    continue
                if val_lower == "no" and txt.startswith("yes"):
                    continue

                is_match = False
                if val_lower == txt:
                    is_match = True
                elif val_lower in ["yes", "no"] and (txt.startswith(val_lower) or re.search(r'\b' + val_lower + r'\b', txt)):
                    is_match = True
                elif len(val_lower) >= 3 and val_lower in txt:
                    is_match = True

                if is_match:
                    bl.scroll_into_view_if_needed()
                    is_pressed = bl.get_attribute("aria-pressed") == "true" or bl.get_attribute("aria-checked") == "true"
                    if not is_pressed or force_reclick:
                        bl.click(force=True)
                        try:
                            bl.evaluate("el => { el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
                        except Exception:
                            pass
                        print(f"    [Radio] {field.title[:30]} -> {val} (button clicked)", flush=True)
                    else:
                        print(f"    [Radio] {field.title[:30]} -> {val} (already pressed)", flush=True)
                    return True

            return False


        except Exception as e:
            print(f"    [Radio] Notice on {field.title[:30]}: {e}", flush=True)
            return False

    @classmethod
    def fill_education_history(cls, page):
        """Ensures Ashby Education History section (School and Degree) is populated."""
        try:
            edu_containers = page.query_selector_all("div:has-text('Education History')")
            for ec in edu_containers:
                # Fill School
                school_inp = ec.query_selector("input[placeholder*='school' i], input[placeholder*='Search schools' i]")
                if school_inp and not school_inp.input_value().strip():
                    try:
                        school_inp.click(force=True, timeout=2500)
                    except Exception:
                        school_inp.evaluate("e => e.focus()")
                    school_inp.fill("Rutgers")
                    time.sleep(0.8)
                    rutgers_opt = None
                    for opt in page.locator("[role='option'], [class*='option'], [class*='result']").all():
                        if opt.is_visible():
                            otxt = opt.inner_text().strip().lower()
                            if "camden" in otxt or "newark" in otxt or "medical" in otxt:
                                continue
                            if "new brunswick" in otxt:
                                rutgers_opt = opt
                                break
                            if "rutgers" in otxt and ("state university" in otxt or "new jersey" in otxt):
                                rutgers_opt = opt
                                break
                    if rutgers_opt and rutgers_opt.is_visible():
                        try:
                            rutgers_opt.click(force=True, timeout=2500)
                        except Exception:
                            rutgers_opt.evaluate("e => e.click()")
                        print("    [Education] School -> Rutgers, The State University of New Jersey (New Brunswick)", flush=True)
                
                # Fill Degree / Field of Study
                degree_inp = ec.query_selector("input[placeholder*='degree' i], input[placeholder*='Bachelor' i]")
                if degree_inp and not degree_inp.input_value().strip():
                    try:
                        degree_inp.click(force=True, timeout=2500)
                    except Exception:
                        degree_inp.evaluate("e => e.focus()")
                    degree_inp.fill("Master of Science in Computer Science")
                    degree_inp.evaluate("e => { e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); e.dispatchEvent(new Event('blur', {bubbles: true})); }")
                    print("    [Education] Degree -> Master of Science in Computer Science", flush=True)

                study_inp = ec.query_selector("input[placeholder*='computer science' i], input[placeholder*='field of study' i], input[placeholder*='major' i]")
                if study_inp and not study_inp.input_value().strip():
                    try:
                        study_inp.click(force=True, timeout=2500)
                    except Exception:
                        study_inp.evaluate("e => e.focus()")
                    study_inp.fill("Computer Science")
                    study_inp.evaluate("e => { e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); e.dispatchEvent(new Event('blur', {bubbles: true})); }")
                    print("    [Education] Field of Study -> Computer Science", flush=True)
        except Exception as e:
            print(f"    [Education Notice] {e}", flush=True)


    @staticmethod
    def fill_checkbox(page, field: FormField, vals: list, force_recheck: bool = False) -> bool:
        """Checks matching checkboxes within container using native check and synthetic React event dispatch."""
        if not vals:
            return False
        container = field.container
        clicked = False
        import re
        try:
            checkboxes = container.query_selector_all("input[type='checkbox']")
            for cb in checkboxes:
                parent = cb.evaluate_handle("el => el.closest('.ashby-application-form-input-checkbox-group-option') || el.closest('[class*=\"checkbox-group-option\"]') || el.closest('[class*=\"option\"]') || el.closest('label') || el.parentElement?.parentElement || el.parentElement")
                txt = parent.as_element().inner_text().strip().lower() if parent.as_element() else ""
                cid = cb.get_attribute("id")
                if not txt and cid:
                    lbl = container.query_selector(f"label[for='{cid}']")
                    if lbl:
                        txt = lbl.inner_text().strip().lower()

                for target_val in vals:
                    t_val = target_val.lower().strip()
                    if not t_val:
                        continue
                    # Strict protection against substring traps (e.g. 'man' matching 'woman')
                    if t_val == "man" and "woman" in txt:
                        continue
                    if t_val == "asian" and ("mixed" in txt or "multiple" in txt):
                        continue

                    is_match = False
                    if len(checkboxes) == 1:
                        is_match = True
                    elif t_val == txt:
                        is_match = True
                    elif re.search(r'\b' + re.escape(t_val) + r'\b', txt):
                        is_match = True
                    elif len(t_val) >= 4 and t_val in txt:
                        is_match = True

                    if is_match:
                        is_already = False
                        try:
                            is_already = cb.is_checked()
                        except Exception:
                            pass
                        if is_already and not force_recheck:
                            clicked = True
                            print(f"    [Checkbox] Already checked: {txt[:40] if txt else field.title[:30]}", flush=True)
                            break

                        loc_target = None
                        if cid:
                            loc_target = page.locator(f"label[for='{cid}']").first
                        if not loc_target or not loc_target.is_visible():
                            loc_target = page.locator("label").filter(has_text=re.compile(re.escape(txt), re.I)).first
                        if not loc_target or not loc_target.is_visible():
                            loc_target = page.locator(".ashby-application-form-input-checkbox-group-option, [class*='checkbox-group-option']").filter(has_text=re.compile(re.escape(txt), re.I)).first

                        use_mouse_env = os.environ.get("USE_MOUSE", "").lower() in ["true", "1", "yes"]

                        if loc_target and loc_target.is_visible():
                            loc_target.scroll_into_view_if_needed()
                            time.sleep(0.15)
                            if use_mouse_env:
                                try:
                                    from .cv_mouse import click_element_cv
                                except Exception:
                                    try:
                                        from cv_mouse import click_element_cv
                                    except Exception:
                                        from cv_mouse_fallback import click_element_cv
                                print(f"    [CV Mouse] Gliding physical OS mouse to click checkbox: '{txt[:35]}'...", flush=True)
                                click_element_cv(page, locator=loc_target)
                            else:
                                try:
                                    loc_target.click(force=True, timeout=2500)
                                except Exception:
                                    try:
                                        loc_target.evaluate("el => el.click()")
                                    except Exception:
                                        pass
                        else:
                            cb.check(force=True)

                        time.sleep(0.2)
                        try:
                            if not cb.is_checked():
                                cb.check(force=True)
                        except Exception:
                            pass

                        clicked = True
                        print(f"    [Checkbox] Checked: {txt[:40] if txt else field.title[:30]}", flush=True)
                        break
            return clicked
        except Exception as e:
            print(f"    [Checkbox] Notice on {field.title[:30]}: {e}", flush=True)
            return False

    @classmethod
    def fill_all_fields(cls, page, resume_pdf_path: str, company: str, role: str):
        """Scans page and fills all fields in an ordered pass."""
        # 1. Upload Resume
        cls.upload_resume(page, resume_pdf_path)

        # 2. Scan Form Fields
        fields = DOMScanner.scan_page(page)
        print(f"  [Form Engine] Discovered {len(fields)} field containers. Populating...", flush=True)

        for f in fields:
            # Skip if already filled and valid (unless it's a radio/combobox needing verification)
            ans_val = ""
            if f.field_type == "text":
                val = FieldMatcher.match_text_input(f.title, company, role)
                if not val and f.is_required:
                    val = solve_field_with_ai(f.title, "text", company=company, role=role)
                ans_val = val
                if val and (not f.current_value.strip() or f.current_value.strip() != val):
                    cls.fill_text(page, f, val)

            elif f.field_type == "textarea":
                val = FieldMatcher.match_textarea(f.title, company, role)
                if not val and f.is_required:
                    val = solve_field_with_ai(f.title, "textarea", company=company, role=role)
                ans_val = val
                if val and not f.current_value.strip():
                    cls.fill_textarea(page, f, val)

            elif f.field_type == "combobox":
                val = FieldMatcher.match_combobox(f.title, f.options)
                if not val:
                    val = solve_field_with_ai(f.title, "combobox", options=f.options, company=company, role=role)
                ans_val = val
                if val and (not f.current_value.strip() or f.current_value.strip() != val):
                    cls.fill_combobox(page, f, val)

            elif f.field_type == "radio":
                val = FieldMatcher.match_radio_or_toggle(f.title, f.options)
                if not val:
                    val = solve_field_with_ai(f.title, "radio", options=f.options, company=company, role=role)
                ans_val = val
                if val:
                    cls.fill_radio(page, f, val)

            elif f.field_type == "checkbox":
                vals = FieldMatcher.match_checkbox(f.title, f.options)
                if not vals:
                    ai_ans = solve_field_with_ai(f.title, "checkbox", options=f.options, company=company, role=role)
                    if ai_ans == "CHECK_ALL":
                        vals = f.options if f.options else ["agree"]
                    elif ai_ans:
                        vals = [ai_ans]
                ans_val = ", ".join(vals) if vals else ""
                if vals:
                    cls.fill_checkbox(page, f, vals)

            log_discovered_question(
                question=f.title,
                field_type=f.field_type,
                options=f.options,
                answer_used=ans_val,
                status="matched" if ans_val else "unmatched",
                platform="ashby",
                company=company,
                role=role
            )


        # Ensure Education History section is completed
        cls.fill_education_history(page)
        time.sleep(1.0)

        # 3. Dynamic Re-Scan Loop (for conditionally revealed fields e.g. after clicking Yes)
        for pass_idx in range(1, 4):
            new_fields = DOMScanner.scan_page(page)
            unfilled_count = 0
            for f in new_fields:
                if f.field_type == "text":
                    val = FieldMatcher.match_text_input(f.title, company, role)
                    if val and (not f.current_value.strip() or f.current_value.strip() != val):
                        if cls.fill_text(page, f, val):
                            unfilled_count += 1
                elif f.field_type == "textarea":
                    val = FieldMatcher.match_textarea(f.title, company, role)
                    if val and not f.current_value.strip():
                        if cls.fill_textarea(page, f, val):
                            unfilled_count += 1
                elif f.field_type == "combobox":
                    val = FieldMatcher.match_combobox(f.title, f.options)
                    if val and (not f.current_value.strip() or f.current_value.strip() != val):
                        if cls.fill_combobox(page, f, val):
                            unfilled_count += 1
                elif f.field_type == "radio":
                    val = FieldMatcher.match_radio_or_toggle(f.title, f.options)
                    if val and not f.current_value.strip():
                        if cls.fill_radio(page, f, val):
                            unfilled_count += 1
                elif f.field_type == "checkbox":
                    vals = FieldMatcher.match_checkbox(f.title, f.options)
                    if vals and not f.current_value.strip():
                        if cls.fill_checkbox(page, f, vals):
                            unfilled_count += 1

            # Also sweep all Ashby Yes/No button containers directly to guarantee none were skipped due to DOM shifts
            try:
                yesno_containers = page.query_selector_all("div.ashby-application-form-input-yesno, [class*='input-yesno']")
                for c in yesno_containers:
                    parent_txt = c.evaluate("el => el.closest('[class*=\"field-entry\"], [class*=\"fieldEntry\"], fieldset') ? el.closest('[class*=\"field-entry\"], [class*=\"fieldEntry\"], fieldset').innerText.toLowerCase() : ''")
                    target_val = FieldMatcher.match_radio_or_toggle(parent_txt) or "Yes"
                    opt_val = "yes" if target_val.lower().startswith("y") else "no"
                    btn = c.query_selector(f"button[data-option='{opt_val}']")
                    if btn and btn.get_attribute("aria-pressed") != "true":
                        btn.scroll_into_view_if_needed()
                        try:
                            btn.click(force=True, timeout=2500)
                        except Exception:
                            try:
                                btn.evaluate("e => e.click()")
                            except Exception:
                                pass
                        unfilled_count += 1
                        time.sleep(0.2)
            except Exception:
                pass

            if unfilled_count == 0:
                break
            time.sleep(0.5)

    @classmethod
    def diagnose_and_rectify(cls, page, resume_pdf_path: str, company: str, role: str) -> int:
        """Inspects for remaining validation errors or unfilled required fields, captures screenshots, and rectifies them."""
        print("  [Form Engine] Running diagnostic scan for errors and uncompleted fields...", flush=True)

        # 1. Unconditionally capture error screenshot immediately so user and engine have full visual evidence
        try:
            import re
            from pathlib import Path
            clean_c = re.sub(r'[^a-zA-Z0-9_-]', '_', company.lower())
            clean_t = re.sub(r'[^a-zA-Z0-9_-]', '_', role.lower())
            timestamp = int(time.time())
            errors_dir = Path(os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/errors"))
            errors_dir.mkdir(parents=True, exist_ok=True)
            err_img = errors_dir / f"{clean_c}_{clean_t}_error_{timestamp}.png"
            page.screenshot(path=str(err_img), full_page=True)
            scratch_env = os.environ.get("SCRATCH_DIR")
            if scratch_env:
                scratch_img = Path(scratch_env) / f"{clean_c}_{clean_t}_error_{timestamp}.png"
                scratch_img.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(scratch_img), full_page=True)
        except Exception as e:
            print(f"  ⚠️ Could not save error screenshot: {e}", flush=True)

        # 2. Check for error markers and banners
        error_containers = page.query_selector_all(
            "[class*='error']:not(body):not(html), [aria-invalid='true'], [class*='invalid']"
        )
        if error_containers:
            print(f"  [Form Engine] Detected {len(error_containers)} error markers on page.", flush=True)

        # Check for Ashby error banner containing missing field labels
        missing_labels = []
        try:
            banner_items = page.query_selector_all("[class*='error'] li, [class*='error'] a, [role='alert'] li, [role='alert'] a")
            for item in banner_items:
                txt = item.inner_text().strip()
                if "Missing entry for required field:" in txt:
                    label = txt.replace("Missing entry for required field:", "").strip()
                    if label:
                        missing_labels.append(re.sub(r'\s+', ' ', label.replace('\xa0', ' ')).strip().lower())
                elif txt:
                    missing_labels.append(re.sub(r'\s+', ' ', txt.replace('\xa0', ' ')).strip().lower())
            if missing_labels:
                print(f"  [Form Engine] Banner reported missing required fields: {missing_labels[:6]}", flush=True)
        except Exception:
            pass

        # Ensure whole page is scrolled through and rendered
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.3)
            page.evaluate("window.scrollTo(0, 0);")
            time.sleep(0.3)
        except Exception:
            pass

        # 3. Comprehensive Form Inspection: check what is still unfilled or unchecked
        fixed = 0

        # Check if Resume was reported missing in the banner
        if any("resume" in ml for ml in missing_labels):
            print("  [Diagnostic Fix] Banner reported missing Resume -> re-uploading resume PDF...", flush=True)
            if cls.upload_resume(page, resume_pdf_path):
                fixed += 1

        fields = DOMScanner.scan_page(page)
        for f in fields:
            container_html = f.container.evaluate("el => el.outerHTML.toLowerCase()")
            f_tl_clean = re.sub(r'\s+', ' ', f.title.replace('\xa0', ' ')).strip().lower()
            is_empty = not f.current_value.strip()
            banner_match = any(
                (ml in f_tl_clean or f_tl_clean in ml or (len(ml) > 10 and len(f_tl_clean) > 10 and (ml[:25] in f_tl_clean or f_tl_clean[:25] in ml)))
                for ml in missing_labels
            )
            is_flagged = (
                "error" in container_html or 
                "invalid" in container_html or 
                (f.is_required and is_empty) or
                (f.field_type == "radio" and is_empty) or
                banner_match
            )

            # Check text boxes that need to be filled
            if f.field_type == "text":
                if is_flagged or is_empty:
                    val = FieldMatcher.match_text_input(f.title, company, role)
                    if not val and banner_match:
                        val = "N/A"
                    if val and (is_empty or is_flagged or val.lower() != f.current_value.strip().lower()):
                        print(f"    [Diagnostic Fix] Textbox '{f.title[:35]}' empty/flagged -> populating", flush=True)
                        if cls.fill_text(page, f, val):
                            fixed += 1

            # Check textareas that need to be filled
            elif f.field_type == "textarea":
                if is_flagged or is_empty:
                    val = FieldMatcher.match_textarea(f.title, company, role)
                    if not val and banner_match:
                        val = f"I am excited about this opportunity at {company} and look forward to contributing my technical skills."
                    if val:
                        print(f"    [Diagnostic Fix] Textarea '{f.title[:35]}' empty/flagged -> populating", flush=True)
                        if cls.fill_textarea(page, f, val):
                            try:
                                f.input_element.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); }")
                            except Exception:
                                pass
                            fixed += 1

            # Check dropdowns/comboboxes that need to be selected
            elif f.field_type == "combobox":
                if is_flagged or is_empty:
                    val = FieldMatcher.match_combobox(f.title, f.options)
                    if not val and (banner_match or is_flagged) and f.options:
                        val = next((opt for opt in f.options if any(p in opt.lower() for p in ["job board", "linkedin", "yes", "agree", "computer science", "bachelor", "master"])), None)
                        if not val:
                            val = next((opt for opt in f.options if not any(neg in opt.lower() for neg in ["select", "choose", "none", "no"])), f.options[0])
                    if val:
                        print(f"    [Diagnostic Fix] Dropdown '{f.title[:35]}' empty/flagged -> selecting '{val}'", flush=True)
                        if cls.fill_combobox(page, f, val):
                            fixed += 1

            # Check radio groups/toggle buttons: see what is still unchecked or flagged
            elif f.field_type == "radio":
                if is_flagged or is_empty:
                    val = FieldMatcher.match_radio_or_toggle(f.title, f.options)
                    if not val:
                        val = solve_field_with_ai(f.title, "radio", f.options, company, role)
                    if not val and (banner_match or is_flagged) and f.options:
                        val = next((opt for opt in f.options if any(p in opt.lower() for p in ["job board", "linkedin", "internet", "yes", "agree", "true"])), None)
                        if not val:
                            val = next((opt for opt in f.options if not any(neg in opt.lower() for neg in ["employee", "referral", "agency", "internal", "no", "cannot", "false"])), f.options[0])
                    if val:
                        print(f"    [Diagnostic Fix] Radio group '{f.title[:35]}' unchecked/flagged -> selecting '{val}'", flush=True)
                        if cls.fill_radio(page, f, val, force_reclick=is_flagged):
                            fixed += 1

            # Check checkboxes that need to be checked
            elif f.field_type == "checkbox":
                if is_flagged or is_empty:
                    vals = FieldMatcher.match_checkbox(f.title, f.options)
                    if vals:
                        print(f"    [Diagnostic Fix] Checkbox '{f.title[:35]}' unchecked/flagged -> checking {vals}", flush=True)
                        if cls.fill_checkbox(page, f, vals, force_recheck=is_flagged):
                            fixed += 1

        cls.fill_education_history(page)
        print(f"  [Form Engine] Diagnostic sweep completed. Rectified {fixed} fields.", flush=True)
        return fixed



