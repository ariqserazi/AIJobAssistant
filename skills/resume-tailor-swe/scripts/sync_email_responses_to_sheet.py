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

def search_gmail(query):
    tab = _get_or_create_gmail_tab()
    if not tab:
        return []
    encoded = urllib.parse.quote(query)
    url = f"https://mail.google.com/mail/u/1/#search/{encoded}"
    try:
        tab.setURL_(url)
    except Exception:
        pass
    time.sleep(3.5)
    
    js = """
    (() => {
        const rows = Array.from(document.querySelectorAll('tr.zA'));
        return JSON.stringify(rows.map(r => {
            const senders = (r.querySelector('.yX') || r.querySelector('.yW') || {}).innerText || '';
            const subject = (r.querySelector('.bog') || {}).innerText || '';
            const snippet = (r.querySelector('.y2') || {}).innerText || '';
            const date = (r.querySelector('.xW') || {}).innerText || '';
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
    
    # 1. Offer
    if any(k in text for k in ["offer of employment", "congratulations on your offer", "we are excited to extend an offer"]):
        return "Offer", ""
    
    # 2. Rejection
    rejection_indicators = [
        "not moving forward", "decided not to", "decided to move forward with other",
        "pursue other candidates", "after careful consideration", "not to move forward",
        "unfortunately", "will not be moving forward", "unable to offer",
        "decided to pursue", "not selected", "we have chosen to move forward with"
    ]
    if any(k in text for k in rejection_indicators):
        reason = email_item['snippet'][:100].strip()
        return "Rejected", reason

    # 3. Assessment / Coding Challenge
    assessment_indicators = [
        "predictive index", "assessment", "hackerrank", "codesignal", 
        "coderbyte", "coding challenge", "take-home", "take home"
    ]
    if any(k in text for k in assessment_indicators):
        return "Assessment", ""

    # Filter out job alerts, newsletters, and digests
    sender = email_item.get('senders', '').lower()
    if any(al in sender or al in subject for al in ["wellfound", "job alert", "alert", "digest", "newsletter", "linkedin job", "indeed", "recommended"]):
        return None, ""
        
    # Filter out generic application received acknowledgments
    if any(ack in subject for ack in ["thank you for applying", "thank you for your application", "application received", "we received your application", "application confirmed"]):
        return None, ""

    # 4. Interviewing (require affirmative scheduling or interview invite)
    interview_indicators = [
        "schedule your interview", "schedule an interview", "schedule a call",
        "invitation to interview", "like to invite you to interview", "like to invite you to speak",
        "next steps in the interview", "interview with the team", "phone screen with",
        "first round interview", "technical interview", "chat with our recruiter"
    ]
    if any(k in text for k in interview_indicators):
        return "Interviewing", ""

    return None, ""

def sync_all():
    print("Scouring Gmail for application responses (Rejections, Interviews, Assessments)...")
    ws = get_worksheet()
    all_rows = ws.get_all_values()
    
    # Search queries
    queries = [
        "unfortunately OR \"not moving forward\" OR \"other candidates\" OR \"careful consideration\"",
        "interview OR assessment OR challenge OR \"next steps\""
    ]
    
    scraped = []
    seen = set()
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
        
        # Match against Google Sheet rows (starting row 2)
        for idx, row in enumerate(all_rows[1:], start=2):
            company = row[0].lower().strip()
            role = row[2].lower().strip() if len(row) > 2 else ""
            current_status = row[1] if len(row) > 1 else ""
            
            if not company:
                continue
                
            # Check company match
            if company in text:
                # If multiple roles exist for company, check role match if possible
                if role and len([r for r in all_rows[1:] if r[0].lower().strip() == company]) > 1:
                    role_words = [w for w in role.split() if len(w) > 3]
                    if not any(rw in text for rw in role_words):
                        continue
                        
                # Update status if changed
                if current_status != status_category:
                    print(f"Staging update for Row {idx} ({row[0]} - {row[2]}): {current_status} -> {status_category}")
                    updates_to_send.append({'range': f'B{idx}', 'values': [[status_category]]})
                    if status_category == "Rejected" and reason:
                        updates_to_send.append({'range': f'G{idx}', 'values': [[reason]]})
                    
                    notes = row[7] if len(row) > 7 else ""
                    update_note = f"Status: {status_category} ({item['date']}): {item['subject']}"
                    if update_note not in notes:
                        new_notes = f"{notes} | {update_note}".strip(" |")
                        updates_to_send.append({'range': f'H{idx}', 'values': [[new_notes]]})
                    
                    # Update local row representation so subsequent matches don't re-stage
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
