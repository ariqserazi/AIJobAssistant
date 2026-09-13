#!/usr/bin/env python3
"""
apply_workday.py - Workday External Portal Application Automation Helper.
Implements robust Workday automation:
1. Native pointer sequencing for React prompt popovers (data-automation-id="promptIcon").
2. Prototype descriptor override for LinkedIn URL regex formatting (e.g. https://www.linkedin.com/in/username/).
3. Standardized truth EEO, questionnaire, and voluntary disclosure selections.
4. Employer submission confirmation verification and auto-logging.
"""

import subprocess
import json
import time
import sys

from config_loader import get_config

WORKDAY_PASSWORD = get_config("workday_password", "")
LINKEDIN_URL = get_config("linkedin_url", "https://www.linkedin.com/in/username/")


def run_chrome_js(js_code: str) -> str:
    """Executes arbitrary JavaScript in the frontmost Google Chrome tab via AppleScript."""
    clean_js = js_code.replace('\n', ' ').replace('\r', ' ')
    escaped = clean_js.replace('\\', '\\\\').replace('"', '\\"')
    apple_script = f'tell application "Google Chrome" to execute front window\'s active tab javascript "{escaped}"'
    res = subprocess.run(["osascript", "-e", apple_script], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Chrome AppleScript execution failed: {res.stderr}")
    return res.stdout.strip()

def select_workday_prompt(field_automation_id: str, category_label: str, target_item_label: str) -> bool:
    """
    Opens a Workday custom prompt dropdown widget using native pointer sequencing
    and selects the specified hierarchical options.
    """
    js = f"""
    (() => {{
      const container = document.querySelector('[data-automation-id="{field_automation_id}"]');
      if (!container) return 'container_not_found';
      
      const icon = container.querySelector('[data-automation-id="promptIcon"]');
      if (!icon) return 'icon_not_found';
      
      const down = new MouseEvent("mousedown", {{ bubbles: true, cancelable: true, view: window }});
      const up = new MouseEvent("mouseup", {{ bubbles: true, cancelable: true, view: window }});
      const click = new MouseEvent("click", {{ bubbles: true, cancelable: true, view: window }});
      
      icon.dispatchEvent(down);
      icon.dispatchEvent(up);
      icon.dispatchEvent(click);
      return 'opened_prompt';
    }})()
    """
    res = run_chrome_js(js)
    time.sleep(0.5)
    
    # Click parent category
    click_opt_js = f"""
    (() => {{
      const options = Array.from(document.querySelectorAll('[data-automation-id="promptOption"]'));
      const cat = options.find(o => (o.getAttribute("data-automation-label") || o.textContent).trim() === "{category_label}");
      if (!cat) return 'category_not_found';
      
      cat.dispatchEvent(new MouseEvent("mousedown", {{ bubbles: true, cancelable: true, view: window }}));
      cat.dispatchEvent(new MouseEvent("mouseup", {{ bubbles: true, cancelable: true, view: window }}));
      cat.dispatchEvent(new MouseEvent("click", {{ bubbles: true, cancelable: true, view: window }}));
      return 'clicked_category';
    }})()
    """
    run_chrome_js(click_opt_js)
    time.sleep(0.5)
    
    # Click target item
    click_target_js = f"""
    (() => {{
      const options = Array.from(document.querySelectorAll('[data-automation-id="promptOption"]'));
      const target = options.find(o => (o.getAttribute("data-automation-label") || o.textContent).trim() === "{target_item_label}");
      if (!target) return 'target_not_found';
      
      target.dispatchEvent(new MouseEvent("mousedown", {{ bubbles: true, cancelable: true, view: window }}));
      target.dispatchEvent(new MouseEvent("mouseup", {{ bubbles: true, cancelable: true, view: window }}));
      target.dispatchEvent(new MouseEvent("click", {{ bubbles: true, cancelable: true, view: window }}));
      return 'clicked_target';
    }})()
    """
    res = run_chrome_js(click_target_js)
    return 'clicked_target' in res

def fix_linkedin_url(input_id="socialNetworkAccounts--linkedInAccount", url=LINKEDIN_URL):
    """Bypasses React shadow value tracking to satisfy Workday's LinkedIn URL regex."""
    js = f"""
    (() => {{
      const input = document.getElementById('{input_id}');
      if (!input) return 'input_not_found';
      
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      nativeSetter.call(input, '{url}');
      
      input.dispatchEvent(new Event('input', {{ bubbles: true }}));
      input.dispatchEvent(new Event('change', {{ bubbles: true }}));
      input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
      return 'success';
    }})()
    """
    return run_chrome_js(js)

def answer_select_one_questions(question_answer_map):
    """
    Answers Workday 'Select One' popover dropdowns.
    question_answer_map is a list of tuples: (substring_in_label, "Yes"|"No"|etc.)
    """
    for needle, answer in question_answer_map:
        js = f"""
        (() => {{
          const fields = Array.from(document.querySelectorAll('[data-automation-id^="formField"]'));
          for (const f of fields) {{
            const text = f.innerText.replace(/\\n/g, ' ');
            if (text.toLowerCase().includes('{needle.lower()}')) {{
              const btn = f.querySelector('button');
              if (btn) {{
                btn.click();
                return 'opened';
              }}
            }}
          }}
          return 'field_not_found';
        }})()
        """
        out = run_chrome_js(js)
        if out == 'opened':
            time.sleep(0.3)
            select_opt_js = f"""
            (() => {{
              const options = Array.from(document.querySelectorAll('[role="option"]'));
              const match = options.find(o => o.textContent.trim().toLowerCase() === '{answer.lower()}');
              if (match) {{
                match.click();
                return 'selected';
              }}
              return 'option_not_found';
            }})()
            """
            run_chrome_js(select_opt_js)
            time.sleep(0.3)

def handle_workday_verification_code(company=None, max_wait=45):
    """
    Checks if Workday has popped up a verification code modal or screen.
    If so, retrieves the code from the candidate email and enters it.
    """
    import os, sys
    sys.path.insert(0, os.path.expanduser("~/.agents/skills/resume-tailor-swe/scripts"))
    try:
        from email_verification_helper import get_latest_verification_code
    except ImportError:
        return False

    check_js = """
    (() => {
        const inputs = Array.from(document.querySelectorAll('input'));
        const codeInp = inputs.find(i => {
            const autoId = (i.getAttribute('data-automation-id') || '').toLowerCase();
            const aria = (i.getAttribute('aria-label') || '').toLowerCase();
            const name = (i.getAttribute('name') || '').toLowerCase();
            const id = (i.id || '').toLowerCase();
            return autoId.includes('code') || autoId.includes('verification') ||
                   aria.includes('code') || aria.includes('verification') ||
                   name.includes('code') || name.includes('verification') ||
                   id.includes('code') || id.includes('verification');
        });
        const body = document.body.innerText.toLowerCase();
        const hasText = body.includes('verification code') || body.includes('security code') || body.includes('one-time passcode');
        return JSON.stringify({ hasInput: !!codeInp, hasText, inputId: codeInp ? (codeInp.id || codeInp.getAttribute('data-automation-id')) : null });
    })()
    """
    try:
        res = json.loads(run_chrome_js(check_js))
        if res.get('hasInput') or res.get('hasText'):
            print(f"  🔔 [Workday Verification] Verification code detected on page! Fetching from email...", flush=True)
            code = get_latest_verification_code(company=company, max_wait_sec=max_wait)
            if not code:
                return False
            
            fill_js = f"""
            (() => {{
                const inputs = Array.from(document.querySelectorAll('input'));
                const codeInp = inputs.find(i => {{
                    const autoId = (i.getAttribute('data-automation-id') || '').toLowerCase();
                    const aria = (i.getAttribute('aria-label') || '').toLowerCase();
                    const name = (i.getAttribute('name') || '').toLowerCase();
                    const id = (i.id || '').toLowerCase();
                    return autoId.includes('code') || autoId.includes('verification') ||
                           aria.includes('code') || aria.includes('verification') ||
                           name.includes('code') || name.includes('verification') ||
                           id.includes('code') || id.includes('verification');
                }});
                if (codeInp) {{
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeSetter.call(codeInp, '{code}');
                    codeInp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    codeInp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    codeInp.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                    return 'filled';
                }}
                return 'input_not_found';
            }})()
            """
            run_chrome_js(fill_js)
            time.sleep(1)
            # Click submit/continue/verify button
            click_btn_js = """
            (() => {
                const btns = Array.from(document.querySelectorAll('button, input[type="submit"]'));
                const submitBtn = btns.find(b => {
                    const t = (b.textContent || b.value || '').toLowerCase();
                    return t.includes('verify') || t.includes('submit') || t.includes('continue') || t.includes('next');
                });
                if (submitBtn) {
                    submitBtn.click();
                    return 'clicked';
                }
                return 'btn_not_found';
            })()
            """
            run_chrome_js(click_btn_js)
            time.sleep(2)
            return True
    except Exception as e:
        print(f"  ⚠️ [Workday Verification Error]: {e}", flush=True)
    return False

if __name__ == "__main__":
    print("Workday application helper module ready.")
