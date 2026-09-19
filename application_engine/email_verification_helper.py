#!/usr/bin/env python3
"""
email_verification_helper.py - Automated retrieval and entry of one-time security/verification codes
from candidate email inbox for Greenhouse, Workday, and other ATS platforms.
Enforces strict timestamp extraction and sorting so that only the most recent email sent is selected.
"""

import os
import sys
import time
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime

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
CANDIDATE_EMAIL = _c.get("candidate_email", os.getenv("CANDIDATE_EMAIL", ""))

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

BANNED_CODE_WORDS = {
    "reminder", "security", "passcode", "verificat", "greenhouse", "resubmit",
    "embedded", "software", "platform", "engineer", "coinbase", "application",
    "account", "support", "message", "subject", "welcome", "please", "before",
    "remotely", "collapse", "expand", "archive", "starred", "unstarred", "snoozed",
    "details", "forward", "replied", "replies", "actions", "options", "display"
}

def is_valid_code(code):
    if not code:
        return False
    c = code.strip()
    if len(c) not in [6, 8]:
        return False
    if c.lower() in BANNED_CODE_WORDS:
        return False
    if not c.isalnum():
        return False
    # If 6 chars: must be numeric (Workday / standard OTP) or alphanumeric
    if len(c) == 6:
        return c.isdigit() or (any(x.isdigit() for x in c) and any(x.isalpha() for x in c))
    # If 8 chars: Greenhouse codes are random alphanumeric (must not be standard English words)
    if len(c) == 8:
        if re.match(r'^[A-Z][a-z]{7}$', c) or re.match(r'^[a-z]{8}$', c) or re.match(r'^[A-Z]{8}$', c):
            return False
        has_digit = any(x.isdigit() for x in c)
        has_upper = any(x.isupper() for x in c)
        has_lower = any(x.islower() for x in c)
        if has_digit and (has_upper or has_lower):
            return True
        if any(x.isupper() for x in c[1:]) and has_lower:
            return True
        return False
    return False

def fill_gh_security_code(page, code):
    """
    Safely clears and types the 8-character Greenhouse security code across input boxes,
    properly triggering React state updates, paste events, and un-disabling the submit button.
    """
    code = code.strip()[:8]
    # 1. Clear all 8 inputs cleanly using native setter
    page.evaluate('''() => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        for (let j = 0; j < 8; j++) {
            const el = document.querySelector(`#security-input-${j}`);
            if (el) {
                nativeSetter.call(el, '');
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }''')
    time.sleep(0.2)

    # 2. Dispatch Greenhouse's native paste handler on #security-input-0
    page.evaluate('''(code) => {
        const inp0 = document.querySelector('#security-input-0');
        if (inp0) {
            inp0.focus();
            const dt = new DataTransfer();
            dt.setData('text/plain', code);
            const pasteEvent = new ClipboardEvent('paste', { bubbles: true, cancelable: true, clipboardData: dt });
            inp0.dispatchEvent(pasteEvent);
        }
    }''', code)
    time.sleep(0.3)

    # 3. Fallback: Fill each character using React native value setter + synthetic events
    for i, ch in enumerate(code):
        page.evaluate('''(data) => {
            const el = document.querySelector(`#security-input-${data.i}`);
            if (el) {
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(el, data.ch);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new KeyboardEvent('keydown', { key: data.ch, bubbles: true }));
                el.dispatchEvent(new KeyboardEvent('keyup', { key: data.ch, bubbles: true }));
            }
        }''', {"i": i, "ch": ch})
        time.sleep(0.04)

    # 4. Also use Playwright keyboard typing on #security-input-0 to simulate human typing
    try:
        inp0 = page.locator("#security-input-0")
        if inp0.count() > 0:
            inp0.focus()
            time.sleep(0.05)
            page.keyboard.type(code, delay=40)
    except Exception:
        pass
    time.sleep(0.4)

    # 5. Explicitly un-disable and un-grey the submit button
    page.evaluate('''() => {
        const btn = document.querySelector('button#btn-submit, button[type="submit"], .application--submit button');
        if (btn) {
            btn.disabled = false;
            btn.removeAttribute('disabled');
            btn.classList.remove('disabled', 'btn--disabled');
            btn.setAttribute('aria-disabled', 'false');
            btn.style.pointerEvents = 'auto';
            btn.style.opacity = '1';
        }
    }''')
    time.sleep(0.2)


def parse_gmail_timestamp(date_str, display_time=""):
    """
    Parses Gmail row date/time into a UNIX epoch float.
    Examples of full date title: 'Tue, Sep 15, 2026, 12:55 AM'
    Examples of display time: '12:55 AM', 'Sep 14'
    """
    if not date_str and not display_time:
        return 0.0
    for raw in [date_str, display_time]:
        if not raw:
            continue
        clean = re.sub(r"[\u202f\xa0\s]+", " ", str(raw).strip())
        for fmt in [
            "%a, %b %d, %Y, %I:%M %p",
            "%b %d, %Y, %I:%M %p",
            "%a, %d %b %Y, %H:%M:%S",
            "%a, %d %b %Y, %H:%M",
            "%Y-%m-%d %H:%M:%S"
        ]:
            try:
                return datetime.strptime(clean, fmt).timestamp()
            except ValueError:
                pass
        time_match = re.search(r"(\d{1,2}):(\d{2})\s*([AP]M)", clean, re.IGNORECASE)
        if time_match:
            now = datetime.now()
            h, m, ampm = int(time_match.group(1)), int(time_match.group(2)), time_match.group(3).upper()
            if ampm == "PM" and h < 12:
                h += 12
            elif ampm == "AM" and h == 12:
                h = 0
            return now.replace(hour=h, minute=m, second=0, microsecond=0).timestamp()
    return 0.0


def _get_chrome_app():
    """Find the running Google Chrome application hosting the user's primary profile via PID."""
    if not HAVE_OBJC:
        return None, None
    try:
        out = subprocess.run(["pgrep", "-f", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
                             capture_output=True, text=True).stdout.strip()
        pids = [int(p) for p in out.splitlines() if p.strip()]
        
        # 1. First priority: look for a Chrome process and tab that has candidate email or mail.google.com/mail/u/1
        for pid in pids:
            try:
                app = SBApplication.applicationWithProcessIdentifier_(pid)
                windows = app.windows()
                if windows and len(windows) > 0:
                    for w in windows:
                        for t in w.tabs():
                            u = t.URL() or ""
                            title = t.title() or ""
                            if "mail.google.com/mail/u/1" in u or (CANDIDATE_EMAIL and CANDIDATE_EMAIL in title):
                                return app, t
            except Exception:
                continue

        # 2. Second priority: look for any tab with mail.google.com
        for pid in pids:
            try:
                app = SBApplication.applicationWithProcessIdentifier_(pid)
                windows = app.windows()
                if windows and len(windows) > 0:
                    for w in windows:
                        for t in w.tabs():
                            u = t.URL() or ""
                            if "mail.google.com" in u:
                                return app, t
            except Exception:
                continue

        # 3. Third priority: return user's main personal Chrome instance (avoid Playwright temporary profile)
        for pid in sorted(pids):
            try:
                ps_out = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
                if "--remote-debugging" not in ps_out and "--user-data-dir=/var" not in ps_out:
                    app = SBApplication.applicationWithProcessIdentifier_(pid)
                    if app and app.windows() and len(app.windows()) > 0:
                        return app, None
            except Exception:
                continue
    except Exception:
        pass
    return None, None


def _get_or_create_gmail_tab():
    """Locate the existing Gmail tab in Google Chrome via ScriptingBridge, or open one in background if missing."""
    app, tab = _get_chrome_app()
    if tab:
        return tab
    if app:
        try:
            w = app.windows()[0]
            # Create tab in user's main personal window pointing to Gmail inbox
            tab = app.classForScriptingClass_("tab").alloc().initWithProperties_({
                "URL": "https://mail.google.com/mail/u/1/#inbox"
            })
            w.tabs().addObject_(tab)
            time.sleep(3.0)
            return tab
        except Exception:
            pass
    return None


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

def _get_latest_verification_code_inner(company=None, max_wait_sec=120, ignore_codes=None, min_timestamp=None, candidate_keywords=None):
    """
    Polls candidate email inbox for a one-time verification code / security code silently.
    Enforces time comparison: only emails received within the requested timeframe are considered,
    and all candidate codes are sorted by their email timestamp (most recent email first).
    """
    used_on_disk = _load_used_codes()
    ignore_set = set(ignore_codes or []).union(USED_CODES).union(used_on_disk)
    print(f"  📬 [Email Code] Checking inbox for verification code (Company: {company or 'Any'})...", flush=True)

    start_time = time.time()
    # Default to emails sent within the last 5 minutes if min_timestamp not given
    min_ts = min_timestamp if min_timestamp is not None else (start_time - 300)

    tab = _get_or_create_gmail_tab()

    GENERIC_CORP_WORDS = {
        "software", "technologies", "technology", "systems", "solutions", "services",
        "corporation", "inc", "corp", "company", "group", "holdings", "financial",
        "capital", "labs", "security", "global", "media", "interactive", "digital",
        "network", "studios", "management", "consulting", "ventures", "partners",
        "internship", "intern", "embedded", "front", "backend"
    }

    comp_keywords = set()
    if company:
        if isinstance(company, list):
            for c in company:
                comp_keywords.add(str(c).lower().strip())
        else:
            comp_keywords.add(str(company).lower().strip())
    if candidate_keywords:
        for ck in candidate_keywords:
            if ck:
                comp_keywords.add(str(ck).lower().strip())

    comp_parts = set()
    for raw in comp_keywords:
        all_p = [p for p in re.findall(r"[a-zA-Z0-9]+", raw) if len(p) >= 2]
        filtered = [p for p in all_p if p not in GENERIC_CORP_WORDS]
        comp_parts.update(filtered if filtered else all_p)
        if len(all_p) >= 2:
            acronym = "".join([p[0] for p in all_p if p])
            if len(acronym) >= 2:
                comp_parts.add(acronym)

    def matches_company(text):
        # 1. First priority: If this is an explicit Greenhouse security code email, match ONLY the extracted employer name!
        m_sec = re.search(r"Security code for your application to\s+([^,\n\r\-]+)", text, re.IGNORECASE)
        if m_sec:
            em_comp = m_sec.group(1).lower().strip()
            em_parts = [p for p in re.findall(r"[a-zA-Z0-9]+", em_comp) if len(p) >= 3 and p not in GENERIC_CORP_WORDS]
            if any(p in " ".join(comp_keywords).lower() for p in em_parts):
                return True
            if any(p in comp_parts for p in em_parts):
                return True
            # Strictly reject Greenhouse emails meant for another employer
            return False

        # 2. Generic OTP / ATS verification email fallback:
        t_low = text.lower()
        t_clean = re.sub(r"[^a-z0-9]", "", t_low)
        if any(p in t_low for p in comp_parts):
            return True
        for raw in comp_keywords:
            c_clean = re.sub(r"[^a-z0-9]", "", raw)
            if c_clean and len(c_clean) >= 3 and c_clean in t_clean:
                return True
        return False

    poll_count = 0
    while time.time() - start_time < max_wait_sec:
        poll_count += 1
        rows_data = []

        # Fine-grained tab access lock (<1.5s) so parallel workers don't serialize 120s waits
        tab_lock_path = "/tmp/email_otp_tab_access.lock"
        with open(tab_lock_path, "w") as tab_lock:
            try:
                fcntl.flock(tab_lock, fcntl.LOCK_EX)
                if tab:
                    try:
                        js_refresh = """(() => {
                            const backBtn = document.querySelector('div[act="19"], div[aria-label*="Back to Inbox"], div[data-tooltip*="Back to Inbox"]');
                            if (backBtn) {
                                backBtn.click();
                            } else if (window.location.hash.includes('/') && !window.location.hash.endsWith('#inbox')) {
                                const inboxBtn = document.querySelector('a[href*="#inbox"], div[data-tooltip="Inbox"]');
                                if (inboxBtn) inboxBtn.click();
                                else window.location.hash = '#inbox';
                            }
                            const btn = document.querySelector('div[aria-label*="Refresh"], div[act="20"], div[data-tooltip*="Refresh"]');
                            if (btn) btn.click();
                        })()"""
                        tab.executeJavascript_(js_refresh)
                    except Exception:
                        pass
                time.sleep(1.0)

                js = """
                (() => {
                    try {
                        const rows = Array.from(document.querySelectorAll(".zA")).slice(0, 20);
                        return JSON.stringify(rows.map((r, idx) => {
                            const timeEl = r.querySelector(".xW");
                            const span = timeEl ? timeEl.querySelector("span[title]") : null;
                            const fullDate = span ? span.getAttribute("title") : "";
                            const displayTime = timeEl ? timeEl.textContent.trim() : "";
                            const text = (r.textContent || "").replace(/\\n/g, " ");
                            return {
                                index: idx,
                                fullDate: fullDate,
                                displayTime: displayTime,
                                text: text
                            };
                        }));
                    } catch(e) {
                        return JSON.stringify([]);
                    }
                })()
                """
                if tab:
                    try:
                        raw = tab.executeJavascript_(js)
                        if raw:
                            rows_data = json.loads(raw)
                    except Exception:
                        rows_data = []
            finally:
                fcntl.flock(tab_lock, fcntl.LOCK_UN)

        candidates = []
        for it in rows_data:
            ts = parse_gmail_timestamp(it.get("fullDate", ""), it.get("displayTime", ""))
            full_content = it.get("text", "")
            is_company_match = matches_company(full_content)

            # Strict company enforcement: Never use another company's security code
            if company and not is_company_match:
                continue

            # Timestamp verification filter: reject stale emails received before the application session started
            if ts > 0 and min_ts and ts < min_ts:
                continue

            # A. Greenhouse explicit 8-character pattern
            m8 = re.findall(r"code field on your application:\s*([A-Za-z0-9]{8})", full_content)
            for code in m8:
                code = code.strip()
                if code not in ignore_set and is_valid_code(code):
                    candidates.append({
                        "code": code,
                        "ts": ts,
                        "date": it.get("fullDate", ""),
                        "company_match": is_company_match,
                        "index": it.get("index", 0),
                        "type": "greenhouse"
                    })

            # B. Generic OTP / security code pattern (6-8 chars)
            matches_otp = re.findall(r"(?:code|passcode|pin|verification)\s*(?:is|:)?\s*([A-Za-z0-9]{6,8})", full_content, re.IGNORECASE)
            for code in matches_otp:
                code = code.strip()
                if code not in ignore_set and is_valid_code(code):
                    candidates.append({
                        "code": code,
                        "ts": ts,
                        "date": it.get("fullDate", ""),
                        "company_match": is_company_match,
                        "index": it.get("index", 0),
                        "type": "otp"
                    })


        # Sort candidates: Priority 1 = company match, Priority 2 = most recent timestamp (DESC), Priority 3 = top of inbox
        if candidates:
            candidates.sort(key=lambda c: (c["company_match"], c["ts"], -c["index"]), reverse=True)
            best = candidates[0]
            dt_str = datetime.fromtimestamp(best["ts"]).strftime("%I:%M %p") if best["ts"] > 0 else "Just now"
            print(f"  🔑 [Email Code] Successfully retrieved latest security code: {best['code']} (Time: {dt_str}, Company Match: {best['company_match']}, Row: {best['index']})", flush=True)
            return best["code"]

        # 2. Deep Thread Inspection: In Gmail, follow-up security emails from the same employer
        # are bundled into a thread where the list view continues to show the FIRST snippet.
        # If no fresh code is in the list snippet, click into the matching thread to read the latest message!
        if (company or comp_parts) and tab:
            try:
                thread_code = _read_code_from_thread(tab, list(comp_parts) if comp_parts else [str(company)], ignore_set)
                if thread_code:
                    print(f"  🔑 [Email Code] Successfully retrieved latest security code from {company or 'employer'} thread: {thread_code}", flush=True)
                    return thread_code
            except Exception as e:
                print(f"  [Thread inspect notice]: {e}", flush=True)

        if poll_count % 3 == 0:
            print(f"  ⏳ [Email Code] Waiting for verification email to arrive in inbox ({int(time.time() - start_time)}s)...", flush=True)

    print(f"  ⚠️ [Email Code] No verification code detected within {max_wait_sec}s.", flush=True)
    return None


def _read_code_from_thread(tab, comp_parts_list, ignore_set):
    """
    Clicks into the matching email thread and extracts the newest security code from the latest message body.
    """
    try:
        parts_clean = [str(p).lower().strip() for p in (comp_parts_list or []) if len(str(p).strip()) >= 3]

        js_click = f"""(() => {{
            const parts = {json.dumps(parts_clean)};
            const rows = Array.from(document.querySelectorAll(".zA"));
            for (const r of rows) {{
                const txt = r.textContent.toLowerCase();
                const matchComp = parts.length === 0 || parts.some(p => txt.includes(p));
                const isSec = txt.includes("greenhouse") || txt.includes("security code") || txt.includes("verification");
                if (matchComp && isSec) {{
                    const span = r.querySelector("span[data-thread-id], span[data-legacy-thread-id], .bog span, span.bqe, .a4W");
                    if (span) {{
                        span.click();
                        return true;
                    }}
                    r.click();
                    return true;
                }}
            }}
            return false;
        }})()"""
        clicked = tab.executeJavascript_(js_click)
        if not clicked:
            return None
        tab.executeJavascript_("""(() => {
            const collapsed = document.querySelectorAll('.adP, .kQ, .gx, [aria-expanded="false"]');
            collapsed.forEach(el => el.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true, view: window})));
        })()""")
        time.sleep(1.0)

        js_get_text = """(() => {
            const el = document.querySelector("div[role='main']");
            return el ? el.innerText : (document.body ? document.body.innerText : "");
        })()"""
        body_txt = tab.executeJavascript_(js_get_text) or ""
        tab.executeJavascript_("window.location.hash = '#inbox';")
        time.sleep(1.0)

        codes = re.findall(r"code field on your application:\s*([A-Za-z0-9]{8})", body_txt)
        for c in reversed(codes):
            c = c.strip()
            if c not in ignore_set and is_valid_code(c):
                return c

        # Generic OTP fallback inside thread
        otp_codes = re.findall(r"(?:code|passcode|pin|verification)\s*(?:is|:)?\s*([A-Za-z0-9]{6,8})", body_txt, re.IGNORECASE)
        for c in reversed(otp_codes):
            c = c.strip()
            if c not in ignore_set and is_valid_code(c):
                return c

    except Exception:
        try:
            tab.executeJavascript_("window.history.back()")
        except Exception:
            pass
    return None


def get_latest_verification_code(company=None, max_wait_sec=120, ignore_codes=None, min_timestamp=None, candidate_keywords=None):
    """
    Thread-safe & process-safe wrapper ensuring parallel workers don't collide on Gmail tab.
    """
    lock_path = "/tmp/email_otp_lock.lock"
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            return _get_latest_verification_code_inner(
                company, max_wait_sec, ignore_codes, min_timestamp=min_timestamp, candidate_keywords=candidate_keywords
            )
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def handle_verification_code_if_present(page, company=None, max_wait=120, ignore_codes=None):
    """
    Checks if the active page has an email verification code / security code prompt.
    If so, fetches the code from candidate email inbox, types it in, and resubmits.
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

        candidate_keywords = []
        BANNED_KEYWORD_TOKENS = {
            "new", "york", "city", "san", "francisco", "california", "seattle", "austin",
            "chicago", "boston", "denver", "remote", "united", "states", "america",
            "summer", "winter", "fall", "spring", "2026", "2027", "2028", "intern",
            "internship", "software", "engineer", "developer", "engineering", "apply",
            "job", "application", "mobile", "full", "stack", "frontend", "backend", "embedded"
        }
        try:
            p_url = page.url or ""
            for m in re.findall(r"(?:job-boards\.greenhouse\.io/|boards\.greenhouse\.io/embed/job_app\?for=|for=)([a-zA-Z0-9_-]+)", p_url):
                if m and m.lower() not in ["embed", "jobs", "job_app"] and m.lower() not in BANNED_KEYWORD_TOKENS:
                    candidate_keywords.append(m.lower())
            p_title = page.title() or ""
            if p_title:
                for w in re.findall(r"[a-zA-Z0-9]+", p_title):
                    if len(w) >= 3 and w.lower() not in BANNED_KEYWORD_TOKENS:
                        candidate_keywords.append(w.lower())
            for h1 in page.locator("h1").all_inner_texts():
                for w in re.findall(r"[a-zA-Z0-9]+", h1):
                    if len(w) >= 3 and w.lower() not in BANNED_KEYWORD_TOKENS:
                        candidate_keywords.append(w.lower())
        except Exception:
            pass

        prompt_detect_time = time.time()
        # Look for emails received within the last 30 minutes (Greenhouse codes remain valid for 30m)
        min_ts = prompt_detect_time - 1800
        code = get_latest_verification_code(
            company=company, max_wait_sec=max_wait, ignore_codes=ignore_codes, min_timestamp=min_ts, candidate_keywords=candidate_keywords
        )
        if not code:
            print("  ❌ [Email Code] Failed to retrieve verification code from email.", flush=True)
            return False

        if is_gh_verification:
            print(f"  ⌨️ [Email Code] Autofilling 8-character Greenhouse security code: {code}...", flush=True)
            fill_gh_security_code(page, code)

        elif has_generic_code:
            print(f"  ⌨️ [Email Code] Autofilling code into generic input: {code}...", flush=True)
            target_input = generic_code_inputs.first
            target_input.scroll_into_view_if_needed()
            target_input.fill(code)
            time.sleep(1)

        time.sleep(1.0)
        # Explicitly ensure submit button is enabled in DOM
        page.evaluate('''() => {
            const btn = document.querySelector('button#btn-submit, button[type="submit"], .application--submit button');
            if (btn) {
                btn.disabled = false;
                btn.removeAttribute('disabled');
                btn.classList.remove('disabled', 'btn--disabled');
                btn.setAttribute('aria-disabled', 'false');
                btn.style.pointerEvents = 'auto';
                btn.style.opacity = '1';
            }
        }''')
        time.sleep(0.5)

        submit_btn = page.locator(
            "button#btn-submit, "
            "button[type='submit']:has-text('Submit application'), "
            "button[type='submit']:has-text('Submit Application'), "
            "button[type='submit'], "
            ".application--submit button, "
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
            has_code_err = False
            try:
                has_code_err = page.evaluate("() => Array.from(document.querySelectorAll('*')).some(e => e.children.length === 0 && (e.innerText || '').toLowerCase().includes('incorrect security code'))")
            except Exception:
                pass
            if has_code_err:
                print(f"  ⚠️ [Email Code] Code '{code}' was rejected as incorrect. Waiting for fresh replacement code from inbox...", flush=True)
                time.sleep(5.0)
                fresh_code = get_latest_verification_code(company=company, max_wait_sec=120, ignore_codes=[code], min_timestamp=time.time() - 30)
                if fresh_code and fresh_code != code:
                    print(f"  ⌨️ [Email Code] Autofilling fresh replacement code: {fresh_code}...", flush=True)
                    if is_gh_verification:
                        fill_gh_security_code(page, fresh_code)
                    elif has_generic_code:
                        target_input = generic_code_inputs.first
                        target_input.fill(fresh_code)
                    time.sleep(1.0)
                    page.evaluate('''() => {
                        const btn = document.querySelector('button#btn-submit, button[type="submit"], .application--submit button');
                        if (btn) {
                            btn.disabled = false;
                            btn.removeAttribute('disabled');
                            btn.classList.remove('disabled', 'btn--disabled');
                            btn.setAttribute('aria-disabled', 'false');
                            btn.style.pointerEvents = 'auto';
                            btn.style.opacity = '1';
                        }
                    }''')
                    sub2 = page.locator("button#btn-submit, button[type='submit']:has-text('Submit application'), .application--submit button[type='submit']").first
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
    parser.add_argument("--wait", type=int, default=120, help="Max wait seconds (default: 120)")
    args = parser.parse_args()

    found_code = get_latest_verification_code(company=args.company, max_wait_sec=args.wait)
    print(f"Result Code: {found_code}")
