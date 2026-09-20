try:
    from config_loader import load_config
except ImportError:
    try:
        from application_engine.config_loader import load_config
    except ImportError:
        def load_config(): return {}

_cfg = load_config()

#!/usr/bin/env python3
"""
sync_email_responses_to_sheet.py - Dynamically scour candidate email for job responses 
(Rejections, Interviews, Assessments, Offers) and sync corresponding statuses to Google Sheet Tracker.
"""

import os
import sys
import json
import time
import urllib.parse
import subprocess

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except ImportError:
    pass

import gspread

KEYFILE = os.path.expanduser(_cfg.get("google_service_account_key") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY", ""))
SPREADSHEET_ID = _cfg.get("google_sheet_id") or os.environ.get("GOOGLE_SPREADSHEET_ID", "")

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
    if not HAVE_OBJC:
        return None, None
    try:
        out = subprocess.run(["pgrep", "-f", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
                             capture_output=True, text=True).stdout.strip()
        pids = [int(p) for p in out.splitlines() if p.strip()]
        for pid in pids:
            try:
                app = SBApplication.applicationWithProcessIdentifier_(pid)
                windows = app.windows()
                if windows and len(windows) > 0:
                    for w in windows:
                        for t in w.tabs():
                            if "mail.google.com" in (t.URL() or ""):
                                return app, t
            except Exception:
                continue
    except Exception:
        pass
    return None, None

def _get_or_create_gmail_tab():
    app, tab = _get_chrome_app()
    return tab

def fetch_inbox_messages(max_pages=3):
    tab = _get_or_create_gmail_tab()
    if not tab:
        return []
    try:
        tab.executeJavascript_("window.location.hash = '#inbox';")
    except Exception:
        pass
    time.sleep(2.5)
    
    all_items = []
    
    js_read = """
    (() => {
        const rows = Array.from(document.querySelectorAll('tr.zA'));
        return JSON.stringify(rows.map(r => {
            const senders = (r.querySelector('.yX') || r.querySelector('.yW') || {}).textContent || '';
            const subject = (r.querySelector('.bog') || {}).textContent || '';
            const snippet = (r.querySelector('.y2') || {}).textContent || '';
            const date = (r.querySelector('.xW') || {}).textContent || '';
            return { senders, subject, snippet, date };
        }));
    })()
    """
    
    js_click_older = """
    (() => {
        const el = document.querySelector('div[aria-label="Older"]');
        if (el && el.getAttribute('aria-disabled') !== 'true') {
            el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
            el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
            el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
            return true;
        }
        return false;
    })()
    """
    
    js_click_newer = """
    (() => {
        const el = document.querySelector('div[aria-label="Newer"]');
        if (el && el.getAttribute('aria-disabled') !== 'true') {
            el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
            el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
            el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
            return true;
        }
        return false;
    })()
    """

    pages_paginated = 0
    for page in range(max_pages):
        try:
            out = tab.executeJavascript_(js_read)
            items = json.loads(out)
            all_items.extend(items)
        except Exception:
            break
            
        if page < max_pages - 1:
            advanced = tab.executeJavascript_(js_click_older)
            if advanced:
                pages_paginated += 1
                time.sleep(2.5)
            else:
                break
                
    # Return to Page 1
    for _ in range(pages_paginated):
        tab.executeJavascript_(js_click_newer)
        time.sleep(1.0)
        
    return all_items

def search_gmail(query):
    tab = _get_or_create_gmail_tab()
    if not tab:
        return []
    # Use Gmail search box or hash
    js_search = f"""
    (() => {{
        const searchInput = document.querySelector('input[aria-label="Search mail"]') || document.querySelector('input[name="q"]');
        if (searchInput) {{
            searchInput.value = {json.dumps(query)};
            const form = searchInput.closest('form');
            if (form) {{
                form.dispatchEvent(new Event('submit', {{ bubbles: true, cancelable: true }}));
            }} else {{
                searchInput.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, bubbles: true }}));
            }}
            return true;
        }}
        return false;
    }})()
    """
    try:
        done = tab.executeJavascript_(js_search)
        if not done:
            encoded = urllib.parse.quote(query)
            tab.setURL_(f"https://mail.google.com/mail/u/1/#search/{encoded}")
    except Exception:
        pass
    time.sleep(3.5)
    
    js = """
    (() => {
        const rows = Array.from(document.querySelectorAll('tr.zA'));
        return JSON.stringify(rows.map(r => {
            const senders = (r.querySelector('.yX') || r.querySelector('.yW') || {}).textContent || '';
            const subject = (r.querySelector('.bog') || {}).textContent || '';
            const snippet = (r.querySelector('.y2') || {}).textContent || '';
            const date = (r.querySelector('.xW') || {}).textContent || '';
            return { senders, subject, snippet, date };
        }));
    })()
    """
    try:
        out = tab.executeJavascript_(js)
        return json.loads(out)
    except Exception:
        return []

def get_worksheet():
    gc = gspread.service_account(filename=KEYFILE)
    sh = gc.open_by_key(SPREADSHEET_ID)
    return sh.get_worksheet(0)

def classify_email(email_item):
    text = (email_item['subject'] + " " + email_item['snippet']).lower()
    subject = email_item['subject'].lower()
    sender = email_item.get('senders', '').lower()
    
    # 0. Filter out non-application emails, job alerts, digests, newsletters, OTPs
    if any(al in sender or al in subject for al in ["wellfound", "job alert", "alert", "digest", "newsletter", "linkedin job", "indeed", "recommended", "bytebytego", "ladders"]):
        return None, ""
    if "security code" in subject or "verification code" in subject:
        return None, ""
        
    # 1. Offer
    if any(k in text for k in ["offer of employment", "congratulations on your offer", "we are excited to extend an offer"]):
        return "Offer", ""

    # 2. Filter out generic application confirmations UNLESS explicit rejection
    ack_phrases = ["thank you for applying", "thank you for your application", "application received", "we received your application", "application confirmed", "you’re in! thanks for applying", "thanks for applying"]
    is_ack = any(ack in subject for ack in ack_phrases)
    if is_ack and not any(k in text for k in ["unfortunately", "not moving forward", "unable to offer you", "proceed with other candidates", "not selected"]):
        return None, ""

    # 3. Assessment / Coding Challenge
    assessment_indicators = [
        "predictive index", "assessment", "hackerrank", "codesignal", 
        "coderbyte", "coding challenge", "take-home", "take home"
    ]
    if any(k in text for k in assessment_indicators):
        if not any(k in text for k in ["not moving forward", "unfortunately", "decided not to"]):
            return "Assessment", ""
            
    # 4. Rejection
    rejection_indicators = [
        "not moving forward", "decided not to", "decided to move forward with other",
        "pursue other candidates", "after careful consideration", "not to move forward",
        "unfortunately", "will not be moving forward", "unable to offer",
        "decided to pursue", "not selected", "we have chosen to move forward with",
        "proceed with other candidates", "more closely align"
    ]
    if any(k in text for k in rejection_indicators):
        reason = email_item['snippet'][:120].strip()
        return "Rejected", reason

    # 5. Interviewing (require affirmative scheduling or interview invite)
    interview_indicators = [
        "schedule your interview", "schedule an interview", "schedule a call",
        "invitation to interview", "like to invite you to interview", "like to invite you to speak",
        "next steps in the interview", "interview with the team", "phone screen with",
        "first round interview", "technical interview", "chat with our recruiter"
    ]
    if any(k in text for k in interview_indicators):
        return "Interviewing", ""

    return None, ""

def extract_assessment_link_for_item(tab, item):
    """Safely extract assessment URL by reading the href attribute from the email DOM without clicking or opening the URL."""
    if not tab:
        return ""
    subj = item.get("subject", "")
    js_open = f"""
    (() => {{
        const rows = Array.from(document.querySelectorAll("tr.zA"));
        for (const r of rows) {{
            const r_subj = (r.querySelector(".bog") || {{}}).textContent || "";
            if (r_subj && ({json.dumps(subj)}.includes(r_subj) || r_subj.includes({json.dumps(subj)}))) {{
                r.dispatchEvent(new MouseEvent("click", {{ bubbles: true, cancelable: true, view: window }}));
                return true;
            }}
        }}
        return false;
    }})()
    """
    try:
        opened = tab.executeJavascript_(js_open)
        if not opened:
            return ""
        time.sleep(2.5)
        
        js_links = """
        (() => {
            const container = document.querySelector(".ii.gt") || document.querySelector(".a3s.aiL") || document.body;
            const links = Array.from(container.querySelectorAll("a")).map(a => ({
                text: (a.textContent || '').trim().toLowerCase(),
                href: a.getAttribute("href") || ""
            })).filter(l => l.href && !l.href.startsWith("mailto:") && !l.href.startsWith("javascript:"));
            return JSON.stringify(links);
        })()
        """
        raw_links = tab.executeJavascript_(js_links)
        tab.executeJavascript_("window.location.hash = '#inbox';")
        time.sleep(1.0)
        
        if not raw_links:
            return ""
            
        links = json.loads(raw_links)
        assessment_domains = [
            "ondemandassessment.com", "litmushiring.com", "coderbyte.com",
            "hackerrank.com", "codesignal.com", "predictiveindex.com",
            "meritfirst.us", "gallup.com", "testgorilla.com", "codility.com",
            "hirevue.com", "karat.com", "canditech.io", "criteria.com"
        ]
        
        for l in links:
            href = l.get("href", "")
            if any(d in href.lower() for d in assessment_domains):
                if any(skip in href.lower() for skip in ["prep", "terms", "privacy", "blog", "operating-"]):
                    continue
                return href
                
        for l in links:
            text = l.get("text", "")
            href = l.get("href", "")
            if any(kw in text for kw in ["start assessment", "take assessment", "complete assessment", "start test", "take test"]):
                return href
                
        return ""
    except Exception:
        try:
            tab.executeJavascript_("window.location.hash = '#inbox';")
        except Exception:
            pass
        return ""

def sync_all():
    print("Scouring Gmail for application responses (Rejections, Interviews, Assessments)...")
    tab = _get_or_create_gmail_tab()
    ws = get_worksheet()
    all_rows = ws.get_all_values()
    
    # Search queries
    queries = [
        "unfortunately OR \"not moving forward\" OR \"other candidates\" OR \"careful consideration\"",
        "interview OR assessment OR challenge OR \"next steps\""
    ]
    
    scraped = []
    seen = set()
    
    # 1. Fetch current inbox
    inbox_items = fetch_inbox_messages()
    for item in inbox_items:
        key = (item['senders'], item['subject'], item['date'])
        if key not in seen:
            seen.add(key)
            scraped.append(item)
            
    # 2. Search queries
    for q in queries:
        items = search_gmail(q)
        for item in items:
            key = (item['senders'], item['subject'], item['date'])
            if key not in seen:
                seen.add(key)
                scraped.append(item)
                
    print(f"Scanned {len(scraped)} unique messages.")
    
    updates_to_send = []
    for item in scraped:
        status_category, reason = classify_email(item)
        if not status_category:
            continue
            
        text = (item['subject'] + " " + item['snippet'] + " " + item['senders']).lower()
        
        # Resolve company matches
        sender_subj = (item['senders'] + " " + item['subject']).lower()
        candidate_rows = []
        
        for idx, row in enumerate(all_rows[1:], start=2):
            c_name = row[0].lower().strip()
            if not c_name or len(c_name) < 2:
                continue
            c_clean = "".join(ch for ch in c_name if ch.isalnum() or ch.isspace()).strip()
            # Prefer matching in sender or subject
            if c_name in sender_subj or (c_clean and len(c_clean) > 2 and c_clean in sender_subj):
                candidate_rows.append((idx, row))
            elif (c_name in text or (c_clean and len(c_clean) > 2 and c_clean in text)) and any(platform in item['senders'].lower() for platform in ["greenhouse", "lever", "ashby", "workday", "coderbyte", "smartrecruiters", "kayak"]):
                # ATS platform emails often put company name in snippet
                candidate_rows.append((idx, row))
                
        if not candidate_rows:
            continue
            
        # If single candidate row, choose it
        best_match = None
        if len(candidate_rows) == 1:
            best_match = candidate_rows[0]
        else:
            # Multi-role company: match on distinctive role words
            STOP_WORDS = {"intern", "software", "engineer", "engineering", "summer", "2026", "2027", "the", "at", "for", "and", "in", "to", "of", "with", "role", "position", "group", "team", "program"}
            best_score = 0
            for idx, r in candidate_rows:
                r_title = r[2].lower() if len(r) > 2 else ""
                r_words = [w for w in r_title.replace("/", " ").replace("-", " ").split() if len(w) > 2 and w not in STOP_WORDS]
                score = sum(1 for w in r_words if w in text)
                if score > best_score:
                    best_score = score
                    best_match = (idx, r)
            # If no distinctive words matched, only accept if exact role title substring is in text
            if not best_match or best_score == 0:
                for idx, r in candidate_rows:
                    r_title = r[2].lower() if len(r) > 2 else ""
                    if r_title and r_title in text:
                        best_match = (idx, r)
                        break

        if not best_match:
            continue

        idx, row = best_match
        current_status = row[1] if len(row) > 1 else ""
        notes = row[7] if len(row) > 7 else ""
        curr_assessment_link = row[8] if len(row) > 8 else ""

        # Strictly preserve "Assessment Completed" - do not overwrite back to "Assessment"
        if current_status == "Assessment Completed" and status_category == "Assessment":
            if not curr_assessment_link:
                assessment_link = extract_assessment_link_for_item(tab, item)
                if assessment_link:
                    updates_to_send.append({'range': f'I{idx}', 'values': [[assessment_link]]})
            continue

        needs_update = (current_status != status_category) or (
            status_category == "Assessment" and (not curr_assessment_link or "Assessment Link:" not in notes)
        )

        if needs_update:
            print(f"Staging update for Row {idx} ({row[0]} - {row[2]}): {current_status} -> {status_category}")
            updates_to_send.append({'range': f'B{idx}', 'values': [[status_category]]})
            if status_category == "Rejected":
                if any(k in reason.lower() for k in ["position has been filled", "filled this position", "timing did not"]):
                    dropdown_reason = "Applied Too Late"
                elif any(k in reason.lower() for k in ["pipeline", "no new applicants"]):
                    dropdown_reason = "No New Applicants"
                else:
                    dropdown_reason = 'Generic "Not A Good Fit"'
                updates_to_send.append({'range': f'G{idx}', 'values': [[dropdown_reason]]})
            else:
                updates_to_send.append({'range': f'G{idx}', 'values': [['N/A']]})
            
            assessment_link = curr_assessment_link
            if status_category == "Assessment" and not assessment_link:
                assessment_link = extract_assessment_link_for_item(tab, item)
            
            if assessment_link and not curr_assessment_link:
                updates_to_send.append({'range': f'I{idx}', 'values': [[assessment_link]]})
            
            update_note = f"Status: {status_category} ({item['date']}): {item['subject']}"
            if reason:
                update_note += f" | Rejection detail: {reason}"
            if assessment_link and assessment_link not in notes:
                update_note += f" | Assessment Link: {assessment_link}"
                
            if update_note not in notes:
                new_notes = f"{notes} | {update_note}".strip(" |")
                updates_to_send.append({'range': f'H{idx}', 'values': [[new_notes]]})
            
            # Update local representation
            all_rows[idx - 1][1] = status_category

    if updates_to_send:
        print(f"Executing batch update for {len(updates_to_send)} cell updates in single API request...")
        try:
            ws.batch_update(updates_to_send)
            print("✅ Batch update successfully committed to Google Sheet!")
        except Exception as e:
            print(f"Error during batch update: {e}")
            # Fallback with delay
            for u in updates_to_send:
                try:
                    ws.update(u['range'], u['values'])
                    time.sleep(1.0)
                except Exception:
                    pass
    else:
        print("All sheet records are already synchronized with email statuses.")

if __name__ == "__main__":
    sync_all()
