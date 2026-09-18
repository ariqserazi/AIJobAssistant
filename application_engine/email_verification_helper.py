#!/usr/bin/env python3
"""
email_verification_helper.py - Automated retrieval and entry of one-time security/verification codes
from candidate email for Greenhouse, Workday, and other ATS platforms.
"""

import os
import sys
import time
import json
import re
import subprocess
from pathlib import Path

# Ensure PyObjC ScriptingBridge is loaded for high-speed, non-disruptive Chrome interaction
HAVE_OBJC = False
try:
    from Foundation import NSBundle
    import objc
    NSBundle.bundleWithPath_("/System/Library/Frameworks/ScriptingBridge.framework").load()
    SBApplication = objc.lookUpClass("SBApplication")
    HAVE_OBJC = True
except Exception:
    HAVE_OBJC = False


def _get_chrome_app():
    """Find the running Google Chrome application hosting the user's primary profile via Bundle ID."""
    if not HAVE_OBJC:
        return None, None
    try:
        app = SBApplication.applicationWithBundleIdentifier_("com.google.Chrome")
        if app:
            windows = app.windows()
            if windows and len(windows) > 0:
                for w in windows:
                    for t in w.tabs():
                        if "mail.google.com" in (t.URL() or ""):
                            return app, t
    except Exception:
        pass
    return None, None


def _get_or_create_gmail_tab():
    """Locate the existing Gmail tab in Google Chrome via ScriptingBridge without activating or switching windows."""
    app, tab = _get_chrome_app()
    return tab


USED_CODES_FILE = os.path.expanduser("~/.agents/skills/resume-tailor-swe/references/used_verification_codes.json")
USED_CODES = set()

def _load_used_codes():
    try:
        if os.path.exists(USED_CODES_FILE):
            with open(USED_CODES_FILE, "r") as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()

def _mark_code_used(code):
    try:
        os.makedirs(os.path.dirname(USED_CODES_FILE), exist_ok=True)
        used = _load_used_codes()
        used.add(code)
        with open(USED_CODES_FILE, "w") as f:
            json.dump(list(used), f)
    except Exception:
        pass

import fcntl

def _get_latest_verification_code_inner(company=None, max_wait_sec=45, ignore_codes=None):
    """
    Polls candidate email inbox for a one-time verification code / security code silently.
    Never activates or steals focus from the user's Chrome window.
    """
    used_on_disk = _load_used_codes()
    ignore_set = set(ignore_codes or []).union(USED_CODES).union(used_on_disk)
    print(f"  📬 [Email Code] Checking email inbox for verification code (Company: {company or 'Any'})...", flush=True)

    start_time = time.time()
    tab = _get_or_create_gmail_tab()

    poll_count = 0
    while time.time() - start_time < max_wait_sec:
        poll_count += 1

        # In-app refresh without destroying the SPA DOM
        if tab:
            try:
                js_refresh = """(() => {
                    if (window.location.hash.includes('/') && !window.location.hash.endsWith('#inbox')) {
                        const inboxBtn = document.querySelector('a[href*="#inbox"], div[data-tooltip="Inbox"]');
                        if (inboxBtn) inboxBtn.click();
                    }
                    const btn = document.querySelector('div[aria-label*="Refresh"], div[act="20"], div[data-tooltip*="Refresh"]');
                    if (btn) btn.click();
                })()"""
                tab.executeJavascript_(js_refresh)
            except Exception:
                pass
        time.sleep(2.0)

        js = """
        (() => {
            const rows = Array.from(document.querySelectorAll(".zA"));
            return JSON.stringify(rows.slice(0, 15).map(r => r.textContent));
        })()
        """
        rows_text = []
        if tab:
            try:
                raw = tab.executeJavascript_(js)
                if raw:
                    rows_text = json.loads(raw)
            except Exception:
                rows_text = []

        # If company specified, restrict to rows matching company name
        candidate_rows = []
        raw_comp = (company or "").lower().strip()
        comp_parts = [p for p in re.findall(r"[a-zA-Z0-9]+", raw_comp) if len(p) >= 3]
        for p in list(comp_parts):
            for suffix in ["software", "technologies", "technology", "games", "systems", "labs", "security", "capital", "trading", "solutions"]:
                if p.endswith(suffix) and len(p) > len(suffix) + 2:
                    comp_parts.append(p[:-len(suffix)])
                    comp_parts.append(suffix)
        comp_parts = list(set(comp_parts))
        clean_raw_comp = re.sub(r"[^a-z0-9]", "", raw_comp)

        def matches_company(text):
            t_low = text.lower()
            t_clean = re.sub(r"[^a-z0-9]", "", t_low)
            if any(p in t_low for p in comp_parts):
                return True
            if clean_raw_comp and len(clean_raw_comp) >= 3 and clean_raw_comp in t_clean:
                return True
            return False

        if comp_parts:
            matched_rows = [r for r in rows_text if matches_company(r)]
            if matched_rows:
                candidate_rows = matched_rows
            else:
                # If no company name in snippet, check rows containing "security code" or "greenhouse"
                candidate_rows = [r for r in rows_text if any(k in r.lower() for k in ["security code", "greenhouse", "verification code"])]
        else:
            candidate_rows = rows_text

        # 1. High-Speed List View Inspection: Always inspect the latest email summary snippets first!
        # In Gmail, row index 0 is guaranteed to be the most recent email.
        for row_str in candidate_rows:
            is_company_match = matches_company(row_str)
            active_ignore = set(ignore_codes or []) if is_company_match else ignore_set

            # A. Greenhouse explicit 8-character pattern
            matches8 = re.findall(r"code field on your application:\s*([A-Za-z0-9]{8})", row_str)
            for code in matches8:
                code = code.strip()
                if code not in active_ignore:
                    print(f"  🔑 [Email Code] Successfully retrieved Greenhouse security code from list snippet: {code}", flush=True)
                    return code

            # B. Generic OTP / security code pattern (6-8 chars)
            matches_otp = re.findall(r"(?:code|passcode|pin|verification)\s*(?:is|:)?\s*([A-Za-z0-9]{6,8})", row_str, re.IGNORECASE)
            for code in matches_otp:
                code = code.strip()
                if code not in active_ignore and code.lower() not in ["security", "passcode", "verificat"]:
                    print(f"  🔑 [Email Code] Successfully retrieved OTP code from list snippet: {code}", flush=True)
                    return code

            # C. Standalone 8-character alphanumeric code in company-matched row (e.g. Coinbase snippet 'RgWKcRpw')
            if is_company_match:
                tokens8 = re.findall(r"\b([A-Za-z0-9]{8})\b", row_str)
                banned_words = {"security", "greenhou", "applicat", "confirma", "recruiti", "noreply1", "greenhouse", "resubmit"}
                for code in tokens8:
                    code = code.strip()
                    if code not in active_ignore and code.lower() not in banned_words:
                        if (any(c.isupper() for c in code) and any(c.islower() for c in code)) or any(c.isdigit() for c in code):
                            print(f"  🔑 [Email Code] Successfully retrieved company-matched code from list snippet: {code}", flush=True)
                            return code

        # 2. Deep Thread Inspection Fallback: If matching company thread exists and snippet had no code, open it
        if tab:
            try:
                js_click = f"""(() => {{
                    const parts = {json.dumps(comp_parts)};
                    const rawComp = {json.dumps(clean_raw_comp)};
                    const rows = Array.from(document.querySelectorAll(".zA"));
                    for (const r of rows) {{
                        const txt = r.textContent.toLowerCase();
                        const txtClean = txt.replace(/[^a-z0-9]/g, "");
                        const hasCode = txt.includes("greenhouse") || txt.includes("security code") || txt.includes("verification");
                        const matchComp = parts.length === 0 || parts.some(p => txt.includes(p)) || (rawComp.length >= 3 && txtClean.includes(rawComp));
                        if (matchComp && hasCode) {{
                            r.click();
                            return true;
                        }}
                    }}
                    return false;
                }})()"""
                clicked = tab.executeJavascript_(js_click)
                if clicked:
                    time.sleep(1.8)
                    tab.executeJavascript_("""(() => {
                        const exp = document.querySelector("[aria-label=\\"Expand all\\"], div[aria-label=\\"Expand all\\"]");
                        if (exp) exp.click();
                        document.querySelectorAll(".kQ, div[role=\\"button\\"][aria-expanded=\\"false\\"]").forEach(e => e.click());
                    })()""")
                    time.sleep(1.0)
                    raw_bodies = tab.executeJavascript_("""(() => {
                        const msgs = Array.from(document.querySelectorAll(".ii.gt"));
                        return JSON.stringify(msgs.map(m => m.textContent));
                    })()""")
                    tab.executeJavascript_("window.history.back()")
                    time.sleep(1.5)
                    if raw_bodies:
                        bodies = json.loads(raw_bodies)
                        for b in reversed(bodies):
                            m8 = re.findall(r"code field on your application:\s*([A-Za-z0-9]{8})", b)
                            for c in reversed(m8):
                                c = c.strip()
                                if c not in ignore_set:
                                    print(f"  🔑 [Email Code] Successfully retrieved Greenhouse security code from thread: {c}", flush=True)
                                    return c
                            m_otp = re.findall(r"(?:code|passcode|pin|verification)\s*(?:is|:)?\s*([A-Za-z0-9]{6,8})", b, re.IGNORECASE)
                            for c in reversed(m_otp):
                                c = c.strip()
                                if c not in ignore_set:
                                    print(f"  🔑 [Email Code] Successfully retrieved OTP code from thread: {c}", flush=True)
                                    return c
            except Exception:
                pass

        if poll_count % 3 == 0:
            print(f"  ⏳ [Email Code] Waiting for verification email to arrive in inbox ({int(time.time() - start_time)}s)...", flush=True)

    print(f"  ⚠️ [Email Code] No verification code detected within {max_wait_sec}s.", flush=True)
    return None


def get_latest_verification_code(company=None, max_wait_sec=45, ignore_codes=None):
    """
    Thread-safe & process-safe wrapper ensuring parallel workers don't collide on Gmail tab.
    """
    lock_path = "/tmp/email_otp_lock.lock"
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            return _get_latest_verification_code_inner(company, max_wait_sec, ignore_codes)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def handle_verification_code_if_present(page, company=None, max_wait=45, ignore_codes=None):
    """
    Checks if the active page has an email verification code / security code prompt.
    If so, fetches the code from candidate email, types it in, and resubmits.
    Returns True if a code was handled and submitted, False otherwise.
    """
    try:
        gh_inputs = page.locator("#security-input-0")
        is_gh_verification = gh_inputs.count() > 0 and gh_inputs.first.is_visible()

        # Strict: Do NOT match zip codes, country codes, postal codes, promo codes!
        generic_code_inputs = page.locator(
            "input[name*='otp']:not([type='hidden']), input[id*='otp']:not([type='hidden']), "
            "input[name*='passcode']:not([type='hidden']), input[id*='passcode']:not([type='hidden']), "
            "input[autocomplete='one-time-code']:not([type='hidden']), "
            "input[name*='verification_code']:not([type='hidden']), input[id*='verification_code']:not([type='hidden']), "
            "input[name*='security_code']:not([type='hidden']), input[id*='security_code']:not([type='hidden'])"
        )
        has_generic_code = generic_code_inputs.count() > 0 and generic_code_inputs.first.is_visible()

        body_text = page.locator("body").inner_text().lower()
        has_text_prompt = any(p in body_text for p in [
            "verification code was sent",
            "enter the 8-character code",
            "enter the 6-digit code",
            "security code field",
            "enter security code",
            "enter verification code",
            "we sent a verification code",
            "we've sent a verification code",
            "we sent an email with a code"
        ])

        # A valid verification prompt must be either Greenhouse's dedicated #security-input-0,
        # OR both a generic OTP input AND an explicit verification prompt on the page!
        if not (is_gh_verification or (has_generic_code and has_text_prompt)):
            return False

        print(f"  🔔 [Email Code] Verification prompt detected on {company or 'application'} page!", flush=True)
        time.sleep(2)

        code = get_latest_verification_code(company=company, max_wait_sec=max_wait, ignore_codes=ignore_codes)
        if not code:
            print("  ❌ [Email Code] Failed to retrieve verification code from email.", flush=True)
            return False

        if is_gh_verification:
            print(f"  ⌨️ [Email Code] Autofilling 8-character Greenhouse security code: {code}...", flush=True)
            for i, ch in enumerate(code):
                inp = page.locator(f"#security-input-{i}")
                if inp.count() > 0:
                    inp.evaluate("el => { el.value = ''; el.dispatchEvent(new Event('input', {bubbles: true})); }")
                    inp.focus()
                    time.sleep(0.05)
                    page.keyboard.type(ch, delay=25)
            time.sleep(1.0)

        elif has_generic_code:
            print(f"  ⌨️ [Email Code] Autofilling code into generic input: {code}...", flush=True)
            target_input = generic_code_inputs.first
            target_input.scroll_into_view_if_needed()
            target_input.fill(code)
            time.sleep(1)

        time.sleep(1.0)
        submit_btn = page.locator(
            "button[type='submit']:has-text('Submit application'):not([disabled]), "
            "button[type='submit']:has-text('Submit Application'):not([disabled]), "
            "button[type='submit']:not([disabled]), button#btn-submit:not([disabled]), "
            ".application--submit button[type='submit'], "
            "button:has-text('Submit application'), button:has-text('Submit Application'), "
            "button:has-text('Submit'), input[type='submit']"
        ).first
        if submit_btn.count() > 0:
            submit_btn.scroll_into_view_if_needed()
            time.sleep(0.5)
            try:
                submit_btn.click(force=True, timeout=5000)
            except Exception:
                submit_btn.evaluate("el => el.click()")
            USED_CODES.add(code)
            _mark_code_used(code)
            print("  🚀 [Email Code] Re-clicked submit button after entering code!", flush=True)
            
            # Post-submit check: If code is rejected as incorrect, automatically re-fetch replacement code
            time.sleep(3.0)
            err_el = page.locator("#email-verification-error, .helper-text--error, .email-verification--error")
            has_code_err = err_el.count() > 0 and any("incorrect" in (el.inner_text() or "").lower() for el in err_el.all() if el.is_visible())
            if has_code_err:
                print(f"  ⚠️ [Email Code] Code '{code}' was rejected as incorrect. Waiting for fresh replacement code from inbox...", flush=True)
                time.sleep(6.0)
                fresh_code = get_latest_verification_code(company=company, max_wait_sec=40)
                if fresh_code and fresh_code != code:
                    print(f"  ⌨️ [Email Code] Autofilling fresh replacement code: {fresh_code}...", flush=True)
                    if is_gh_verification:
                        for i, ch in enumerate(fresh_code):
                            inp = page.locator(f"#security-input-{i}")
                            if inp.count() > 0:
                                inp.focus()
                                time.sleep(0.05)
                                page.keyboard.type(ch, delay=25)
                    elif has_generic_code:
                        target_input = generic_code_inputs.first
                        target_input.fill(fresh_code)
                    time.sleep(1.0)
                    sub2 = page.locator("button[type='submit']:has-text('Submit application'), .application--submit button[type='submit'], button#btn-submit").first
                    if sub2.count() > 0:
                        try:
                            sub2.click(force=True)
                        except Exception:
                            sub2.evaluate("el => el.click()")
                        USED_CODES.add(fresh_code)
                        _mark_code_used(fresh_code)
                        print("  🚀 [Email Code] Re-submitted with replacement code!", flush=True)
            return True

        return True

    except Exception as e:
        print(f"  ⚠️ [Email Code] Error while handling verification code: {e}", flush=True)
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test email verification retrieval")
    parser.add_argument("--company", type=str, default=None, help="Company name to match")
    parser.add_argument("--wait", type=int, default=30, help="Max wait seconds")
    args = parser.parse_args()

    found_code = get_latest_verification_code(company=args.company, max_wait_sec=args.wait)
    print(f"Result Code: {found_code}")
