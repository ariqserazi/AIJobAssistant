#!/usr/bin/env python3
import subprocess, time, json, urllib.parse, os, re
import gspread

KEYFILE = os.path.expanduser('~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json')
SPREADSHEET_ID = '1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY'

def search_gmail(query):
    encoded = urllib.parse.quote(query)
    url = f'https://mail.google.com/mail/u/1/#search/{encoded}'
    cmd = f'tell application "Google Chrome" to set URL of tab 19 of window 1 to "{url}"'
    subprocess.run(['osascript', '-e', cmd])
    time.sleep(4)
    
    js = '''(() => {
        const rows = Array.from(document.querySelectorAll('tr.zA'));
        return JSON.stringify(rows.map(r => {
            const senders = (r.querySelector('.yX') || r.querySelector('.yW') || {}).innerText || '';
            const subject = (r.querySelector('.bog') || {}).innerText || '';
            const snippet = (r.querySelector('.y2') || {}).innerText || '';
            const date = (r.querySelector('.xW') || {}).innerText || '';
            return { senders, subject, snippet, date };
        }));
    })()'''
    
    js_escaped = js.replace('\\', '\\\\').replace('"', '\\"')
    cmd_exec = f'tell application "Google Chrome" to execute tab 19 of window 1 javascript "{js_escaped}"'
    res = subprocess.run(['osascript', '-e', cmd_exec], capture_output=True, text=True)
    try:
        return json.loads(res.stdout.strip())
    except Exception as e:
        return []

gc = gspread.service_account(KEYFILE)
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.sheet1
all_rows = ws.get_all_values()

queries = [
    'unfortunately OR "not moving forward" OR "other candidates" OR "careful consideration"',
    '"thank you for your interest" OR "update on your application" OR "status of your application"',
    'interview OR assessment OR "coding challenge" OR codesignal OR hackerrank'
]

emails = []
seen = set()
for q in queries:
    for e in search_gmail(q):
        k = (e['senders'], e['subject'], e['date'])
        if k not in seen:
            seen.add(k)
            emails.append(e)

print(f"Scanned {len(emails)} emails.")

rejection_keywords = [
    'not moving forward', 'decided not to', 'move forward with other',
    'pursue other candidates', 'after careful consideration', 'not to move forward',
    'unfortunately', 'will not be moving forward', 'unable to offer',
    'decided to pursue other', 'not selected', 'chosen to move forward with',
    'position has been filled', 'timing did not line up', 'exceptionally competitive'
]

# Identify rejections
rejections = []
for e in emails:
    full_text = (e['subject'] + " " + e['snippet'] + " " + e['senders']).lower()
    if any(rk in full_text for rk in rejection_keywords):
        rejections.append(e)

print(f"Found {len(rejections)} verified rejection emails.")

updates_to_make = []

for e in rejections:
    email_text = (e['subject'] + " " + e['snippet'] + " " + e['senders']).lower()
    snippet_clean = re.sub(r'[\r\n\t]+', ' ', e['snippet']).strip()
    if snippet_clean.startswith('-'):
        snippet_clean = snippet_clean.lstrip('- ').strip()
    
    # Check all rows
    best_row_idx = None
    best_match_score = 0
    
    for idx, row in enumerate(all_rows[1:], start=2):
        if not row or not row[0].strip():
            continue
        comp = row[0].strip().lower()
        role = row[2].strip().lower() if len(row) > 2 else ""
        current_status = row[1].strip() if len(row) > 1 else ""
        
        # Check if company is in email_text
        # Handle variations: "sentry" in "sentry", "vanta" in "vanta hiring team", etc.
        comp_clean = comp.replace('-', ' ').replace('_', ' ')
        
        if comp in email_text or comp_clean in email_text:
            score = 1
            # Role matching
            if role:
                role_words = [w for w in re.split(r'[\s,/_-]+', role) if len(w) > 3 and w not in ['senior', 'engineer', 'developer', 'software', 'lead', 'staff', 'role', 'team']]
                matched_words = [w for w in role_words if w in email_text]
                if role_words:
                    score += len(matched_words) * 2
            
            if score > best_match_score:
                best_match_score = score
                best_row_idx = idx

    if best_row_idx and best_match_score >= 1:
        row = all_rows[best_row_idx - 1]
        current_status = row[1] if len(row) > 1 else ""
        updates_to_make.append({
            'row_idx': best_row_idx,
            'company': row[0],
            'role': row[2] if len(row) > 2 else '',
            'current_status': current_status,
            'new_status': 'Rejected',
            'reason': snippet_clean[:180],
            'subject': e['subject'],
            'date': e['date']
        })

print(f"\nPrepared {len(updates_to_make)} candidate updates.")
for u in updates_to_make:
    print(f"Row {u['row_idx']} | {u['company']} ({u['role']}): {u['current_status']} -> {u['new_status']}")
    print(f"   Reason: {u['reason']}")
