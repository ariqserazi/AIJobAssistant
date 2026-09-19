#!/usr/bin/env python3
"""
dom_scanner.py - Universal DOM extractor for Ashby application forms.
Extracts questions, input types, options, and validation states into normalized FormField objects.
"""

from dataclasses import dataclass
from typing import List, Optional, Any

@dataclass
class FormField:
    index: int
    title: str
    field_type: str  # 'file', 'combobox', 'textarea', 'radio', 'checkbox', 'text'
    container: Any
    input_element: Any
    is_required: bool
    options: List[str]
    current_value: str = ""

class DOMScanner:
    """Scans and parses the application form DOM."""
    
    @staticmethod
    def scan_page(page) -> List[FormField]:
        """Discovers all active form field containers on the page."""
        containers = page.query_selector_all(
            "[data-field-path], [class*='fieldEntry']:not([data-field-path] *), "
            "[class*='field-entry']:not([data-field-path] *), [data-qa*='field']"
        )
        
        fields = []
        for idx, fe in enumerate(containers):
            # Extract question title
            label_el = fe.query_selector("label, [class*='question-title'], [class*='field-label']")
            if label_el:
                title = label_el.inner_text().strip()
            else:
                full_txt = fe.inner_text().strip()
                title = full_txt.split("\n")[0] if full_txt else f"Field_{idx}"
                
            title = " ".join(title.replace("\xa0", " ").split())
            title_lower = title.lower()
            
            # Detect required status
            is_req = "*" in title or "required" in title_lower or not ("optional" in title_lower)
            
            # Detect field type and input element
            # 1. File Upload
            file_input = fe.query_selector("input[type='file']")
            if file_input:
                fields.append(FormField(
                    index=idx,
                    title=title,
                    field_type="file",
                    container=fe,
                    input_element=file_input,
                    is_required=is_req,
                    options=[]
                ))
                continue
                
            # 2. Combobox (Dropdown)
            combobox = fe.query_selector("input[role='combobox'], [aria-haspopup='listbox']")
            if combobox:
                val = ""
                try:
                    val = combobox.input_value() if hasattr(combobox, "input_value") else ""
                except Exception:
                    pass
                if not val:
                    try:
                        val = (combobox.inner_text() or "").strip()
                    except Exception:
                        pass
                fields.append(FormField(
                    index=idx,
                    title=title,
                    field_type="combobox",
                    container=fe,
                    input_element=combobox,
                    is_required=is_req,
                    options=[],
                    current_value=val or ""
                ))
                continue
                
            # 3. Textarea
            textarea = fe.query_selector("textarea")
            if textarea:
                val = textarea.input_value() if hasattr(textarea, "input_value") else ""
                fields.append(FormField(
                    index=idx * 10 + 2,
                    title=title,
                    field_type="textarea",
                    container=fe,
                    input_element=textarea,
                    is_required=is_req,
                    options=[],
                    current_value=val or ""
                ))
                if not fe.query_selector("input[type='radio'], button[role='radio'], button[data-option]"):
                    continue
                
            # 4. Standard Text Input (if present)
            text_input = fe.query_selector("input:not([type='file']):not([type='radio']):not([type='checkbox']):not([type='hidden']):not([role='combobox']):not([aria-haspopup='listbox'])")
            has_text_input = False
            if text_input:
                has_text_input = True
                val = text_input.input_value() if hasattr(text_input, "input_value") else ""
                fields.append(FormField(
                    index=idx * 10,
                    title=title,
                    field_type="text",
                    container=fe,
                    input_element=text_input,
                    is_required=is_req,
                    options=[],
                    current_value=val or ""
                ))

            # 5. Radio Group or Toggle Buttons
            radios = fe.query_selector_all("input[type='radio']")
            toggle_buttons = fe.query_selector_all("button[role='radio'], button[data-option], button[aria-pressed], [class*='buttonGroup'] button")
            if radios or toggle_buttons:
                options = []
                selected_val = ""
                for r in radios:
                    txt = ""
                    rid = r.get_attribute("id")
                    if rid:
                        lbl = fe.query_selector(f"label[for='{rid}']")
                        if lbl:
                            txt = lbl.inner_text().strip()
                    if not txt:
                        opt_box = r.evaluate_handle("el => el.closest('.ashby-application-form-input-radio-group-option') || el.closest('[class*=\"radio-group-option\"]') || el.closest('[class*=\"option\"]') || el.closest('label')")
                        if opt_box and opt_box.as_element():
                            txt = opt_box.as_element().inner_text().strip()
                    if not txt:
                        parent = r.evaluate_handle("el => el.closest('label') || el.parentElement?.parentElement || el.parentElement")
                        txt = parent.as_element().inner_text().strip() if parent.as_element() else ""
                    if txt:
                        options.append(txt)
                    try:
                        if r.is_checked():
                            selected_val = txt
                    except Exception:
                        pass
                for b in toggle_buttons:
                    txt = (b.get_attribute("data-option") or b.inner_text() or "").strip()
                    if txt:
                        options.append(txt)
                    try:
                        if b.get_attribute("aria-pressed") == "true":
                            selected_val = txt
                    except Exception:
                        pass

                radio_title = title
                # If text_input was already extracted from this container, refine radio_title
                if has_text_input:
                    container_text = fe.inner_text().lower()
                    if "text message" in container_text or "sms" in container_text:
                        radio_title = "SMS Text Message Consent"
                    else:
                        radio_title = f"{title} (Options)"

                fields.append(FormField(
                    index=idx * 10 + 1,
                    title=radio_title,
                    field_type="radio",
                    container=fe,
                    input_element=radios[0] if radios else (toggle_buttons[0] if toggle_buttons else fe),
                    is_required=is_req and not has_text_input,
                    options=options,
                    current_value=selected_val
                ))
                continue
                
            # 6. Checkbox
            checkboxes = fe.query_selector_all("input[type='checkbox']")
            if checkboxes:
                options = []
                selected_vals = []
                for cb in checkboxes:
                    parent = cb.evaluate_handle("el => el.closest('.ashby-application-form-input-checkbox-group-option') || el.closest('[class*=\"checkbox-group-option\"]') || el.closest('[class*=\"option\"]') || el.closest('label') || el.parentElement?.parentElement || el.parentElement")
                    txt = parent.as_element().inner_text().strip() if parent.as_element() else ""
                    cid = cb.get_attribute("id")
                    if not txt and cid:
                        lbl = fe.query_selector(f"label[for='{cid}']")
                        if lbl:
                            txt = lbl.inner_text().strip()
                    if not txt and cb.get_attribute("name"):
                        txt = cb.get_attribute("name").strip()
                    if txt:
                        options.append(txt)
                    try:
                        if cb.is_checked():
                            selected_vals.append(txt or "checked")
                    except Exception:
                        pass
                fields.append(FormField(
                    index=idx * 10 + 2,
                    title=title,
                    field_type="checkbox",
                    container=fe,
                    input_element=checkboxes[0],
                    is_required=is_req and not has_text_input,
                    options=options,
                    current_value=", ".join(selected_vals)
                ))
                continue

            if has_text_input:
                continue
                
        return fields
