import json
import os
import re
import gspread

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except ImportError:
    pass

KEYFILE = os.path.expanduser("~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json")
SPREADSHEET_ID = "1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY"

# Load emails
emails = {}
for path in ["/tmp/scoured_job_emails.json", "/tmp/all_recent_emails_14d.json"]:
    if os.path.exists(path):
        with open(path) as f:
            for e in json.load(f):
                key = (e['sender'], e['subject'], e['date'])
                emails[key] = e

print(f"Total deduplicated emails: {len(emails)}")

# Load sheet
gc = gspread.service_account(KEYFILE)
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.sheet1
all_rows = ws.get_all_values()

pending_apps = []
for idx, r in enumerate(all_rows[1:678], start=2):
    comp = r[0].strip()
    status = r[1].strip() if len(r) > 1 else ""
    role = r[2].strip() if len(r) > 2 else ""
    date_sub = r[4].strip() if len(r) > 4 else ""
    reason = r[6].strip() if len(r) > 6 else ""
    notes = r[7].strip() if len(r) > 7 else ""
    if comp and status == "Submitted - Pending Response":
        pending_apps.append({
            "row_idx": idx,
            "company": comp,
            "role": role,
            "date": date_sub,
            "reason": reason,
            "notes": notes
        })

print(f"Total Pending Applications: {len(pending_apps)}")

# Check each pending app against emails
def clean_str(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

for app in pending_apps:
    comp = app["company"]
    clean_comp = clean_str(comp)
    # Ignore if comp name is too generic
    if len(clean_comp) < 3 or clean_comp in ["made", "team", "hire", "work"]:
        continue
        
    for key, e in emails.items():
        sender = e["sender"].lower()
        subj = e["subject"].lower()
        snip = e["snippet"].lower()
        full = f"{sender} {subj} {snip}"
        
        # Exact word match for company
        pattern = r"\b" + re.escape(comp.lower()) + r"\b"
        if re.search(pattern, full) or clean_comp in clean_str(sender) or clean_comp in clean_str(subj):
            # Exclude generic security code or confirmation unless it has decision/assessment
            is_ack = any(k in subj for k in ["application received", "thank you for applying", "thank you for your application", "security code"])
            has_decision = any(k in full for k in ["not moving forward", "unfortunately", "careful consideration", "other candidates", "assessment", "interview", "offer", "next steps"])
            
            print(f"Match found for Row {app['row_idx']} | {app['company']} ({app['role']}):")
            print(f"  Email Date: {e['date']} | Subj: {e['subject']}")
            print(f"  Snippet: {e['snippet'][:120]}")
            print(f"  Is Ack: {is_ack} | Has Decision/Action: {has_decision}")
            print("-" * 50)
