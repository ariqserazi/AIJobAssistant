import json
import os
import re
from collections import Counter
import gspread

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except ImportError:
    pass

KEYFILE = os.path.expanduser("~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json")
SPREADSHEET_ID = "1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY"

with open("/tmp/scoured_job_emails.json") as f:
    emails = json.load(f)

print(f"Loaded {len(emails)} emails.")

gc = gspread.service_account(KEYFILE)
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.sheet1
all_rows = ws.get_all_values()

# Load Google Sheet data (rows 2 to 678)
sheet_apps = []
for idx, r in enumerate(all_rows[1:678], start=2):
    company = r[0].strip()
    status = r[1].strip() if len(r) > 1 else ""
    role = r[2].strip() if len(r) > 2 else ""
    date_submitted = r[4].strip() if len(r) > 4 else ""
    link = r[5].strip() if len(r) > 5 else ""
    reason = r[6].strip() if len(r) > 6 else ""
    notes = r[7].strip() if len(r) > 7 else ""
    if company:
        sheet_apps.append({
            "row_idx": idx,
            "company": company,
            "status": status,
            "role": role,
            "date_submitted": date_submitted,
            "link": link,
            "reason": reason,
            "notes": notes
        })

print(f"Loaded {len(sheet_apps)} applications from Google Sheet.")

# Helper to normalize company names
def norm_name(name):
    n = name.lower()
    n = re.sub(r"[^a-z0-9]", "", n)
    for s in ["technologies", "technology", "software", "solutions", "security", "capital", "systems", "trading", "labs", "inc", "llc", "corp"]:
        if n.endswith(s) and len(n) > len(s) + 2:
            n = n[:-len(s)]
    return n

# Classify emails
rejection_keywords = [
    "not moving forward", "decided not to", "move forward with other",
    "move forward with another", "pursue other candidates", "pursue another candidate",
    "after careful consideration", "not to move forward",
    "unfortunately", "will not be moving forward", "unable to offer",
    "decided to pursue other", "not selected", "chosen to move forward with",
    "position has been filled", "timing did not line up", "exceptionally competitive",
    "decided to freeze", "closed this position", "role has been closed",
    "we have decided to proceed with", "will not be proceeding", "not advancing"
]

assessment_keywords = [
    "predictive index", "assessment", "hackerrank", "codesignal", 
    "coderbyte", "coding challenge", "take-home", "take home", "online assessment"
]

interview_keywords = [
    "schedule your interview", "schedule an interview", "schedule a call",
    "invitation to interview", "like to invite you to interview", "like to invite you to speak",
    "next steps in the interview", "interview with the team", "phone screen with",
    "first round interview", "technical interview", "chat with our recruiter",
    "virtual interview", "interview confirmation"
]

offer_keywords = [
    "offer of employment", "congratulations on your offer", "we are excited to extend an offer",
    "formal offer", "offer letter"
]

# Match emails against applications
matches = []

for e in emails:
    sender = e["sender"].lower()
    subject = e["subject"].lower()
    snippet = e["snippet"].lower()
    full_text = f"{sender} {subject} {snippet}"
    date_str = e["date"]

    # Skip general newsletters, job boards, alerts
    if any(bl in sender or bl in subject for bl in ["wellfound", "job alert", "digest", "newsletter", "linkedin job", "indeed", "recommended", "getcracked", "ziprecruiter"]):
        continue

    # Skip generic confirmation / application received
    if any(ack in subject for ack in ["thank you for applying", "thank you for your application", "application received", "we received your application", "application confirmed", "security code"]):
        # Unless it explicitly contains rejection or interview in body
        if not any(rk in snippet for rk in rejection_keywords) and not any(ik in snippet for ik in interview_keywords):
            continue

    # Determine status
    matched_status = None
    reason_str = ""

    if any(ok in full_text for ok in offer_keywords):
        matched_status = "Offer"
    elif any(ik in full_text for ik in interview_keywords):
        matched_status = "Interviewing"
    elif any(ak in full_text for ak in assessment_keywords) and not any(rk in full_text for rk in rejection_keywords):
        matched_status = "Assessment"
    elif any(rk in full_text for rk in rejection_keywords):
        matched_status = "Rejected"
        # Extract reason snippet cleanly
        clean_snip = re.sub(r"[\r\n\t]+", " ", e["snippet"]).strip()
        clean_snip = clean_snip.lstrip("- \xa0").strip()
        reason_str = clean_snip[:150]

    if not matched_status:
        continue

    # Now find matching application in Google Sheet
    best_app = None
    best_score = 0

    for app in sheet_apps:
        comp = app["company"]
        c_norm = norm_name(comp)
        c_raw = comp.lower().strip()
        
        # Check match
        matched_comp = False
        if c_raw in full_text:
            matched_comp = True
        elif c_norm and len(c_norm) >= 3 and (c_norm in full_text.replace(" ", "").replace("-", "")):
            matched_comp = True

        if not matched_comp:
            continue

        score = 1
        role = app["role"].lower()
        if role:
            role_words = [w for w in re.split(r"[\s,/_-]+", role) if len(w) > 3 and w not in ["senior", "engineer", "developer", "software", "lead", "staff", "role", "team", "intern"]]
            matching_words = [w for w in role_words if w in full_text]
            score += len(matching_words) * 3

        if score > best_score:
            best_score = score
            best_app = app

    if best_app and best_score >= 1:
        matches.append({
            "email": e,
            "status": matched_status,
            "reason": reason_str,
            "app": best_app,
            "score": best_score
        })

print(f"\nFound {len(matches)} potential email-to-sheet matches:")
for m in matches:
    app = m["app"]
    e = m["email"]
    print(f"Row {app['row_idx']:3d} | {app['company']} ({app['role']})")
    print(f"  Current: {app['status']} -> Detected: {m['status']}")
    print(f"  Email: [{e['date']}] {e['subject']}")
    if m['reason']:
        print(f"  Reason: {m['reason']}")
    print("-" * 50)
