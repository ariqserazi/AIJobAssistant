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

# 1. Combine emails
emails_dict = {}
for path in ["/tmp/scoured_job_emails.json", "/tmp/all_recent_emails_14d.json"]:
    if os.path.exists(path):
        with open(path) as f:
            for e in json.load(f):
                key = (e['sender'], e['subject'], e['date'])
                if key not in emails_dict:
                    emails_dict[key] = e

emails = list(emails_dict.values())
print(f"Total deduplicated candidate emails: {len(emails)}")

# 2. Load Google Sheet
gc = gspread.service_account(KEYFILE)
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.sheet1
all_rows = ws.get_all_values()

sheet_apps = []
for idx, r in enumerate(all_rows[1:678], start=2):
    comp = r[0].strip()
    status = r[1].strip() if len(r) > 1 else ""
    role = r[2].strip() if len(r) > 2 else ""
    date_sub = r[4].strip() if len(r) > 4 else ""
    link = r[5].strip() if len(r) > 5 else ""
    reason = r[6].strip() if len(r) > 6 else ""
    notes = r[7].strip() if len(r) > 7 else ""
    if comp:
        sheet_apps.append({
            "row_idx": idx,
            "company": comp,
            "status": status,
            "role": role,
            "date": date_sub,
            "link": link,
            "reason": reason,
            "notes": notes
        })

print(f"Loaded {len(sheet_apps)} applications from Google Sheet.")

# 3. Classify emails rigorously
def classify(e):
    sender = e["sender"].lower()
    subject = e["subject"].lower()
    snippet = e["snippet"].lower()
    combined = f"{sender} {subject} {snippet}"
    date = e["date"]

    # Filter spam / newsletters
    if any(bl in sender or bl in subject for bl in ["wellfound", "job alert", "digest", "newsletter", "linkedin job", "indeed", "recommended", "getcracked", "ziprecruiter", "full focus", "michael hyatt"]):
        return None, ""

    # Offers
    offer_phrases = ["offer of employment", "we are excited to extend an offer", "offer letter", "congratulations on your offer"]
    if any(p in combined for p in offer_phrases):
        return "Offer", ""

    # Rejections
    rejection_phrases = [
        "not moving forward", "decided not to", "move forward with other",
        "move forward with another", "pursue other candidates", "pursue another candidate",
        "after careful consideration", "not to move forward",
        "unfortunately, we will not", "unfortunately we will not", "unfortunately, we won't",
        "unable to offer", "decided to pursue other", "not selected",
        "chosen to move forward with", "position has been filled", "timing did not line up",
        "exceptionally competitive", "closed this position", "role has been closed",
        "will not be proceeding", "not advancing", "decision not to move forward"
    ]
    
    # Specific check for rejections
    for rp in rejection_phrases:
        if rp in combined:
            # Clean snippet for reason
            snip = re.sub(r"[\r\n\t]+", " ", e["snippet"]).strip()
            snip = snip.lstrip("- \xa0").strip()
            return "Rejected", snip[:180]

    # Assessments / Coding Challenges
    assessment_phrases = [
        "complete talent assessment", "trader personality assessment",
        "predictive index behavioral assessment", "predictive index assessment",
        "codesignal", "hackerrank", "coderbyte", "take-home challenge",
        "online assessment", "action required: next steps to trillium"
    ]
    # Also check subject specifically for assessments
    if any(p in combined for p in assessment_phrases) or "your roblox assessments invitation" in combined:
        return "Assessment", ""
    
    if "assessment" in subject and any(k in subject for k in ["invitation", "complete", "action required", "next step", "expire"]):
        return "Assessment", ""

    # Interviews
    interview_phrases = [
        "schedule your interview", "schedule an interview", "schedule a call",
        "invitation to interview", "like to invite you to interview", "like to invite you to speak",
        "next steps in the interview", "interview with the team", "phone screen with",
        "first round interview", "technical interview", "virtual interview", "interview confirmation"
    ]
    if any(p in combined for p in interview_phrases):
        # Exclude automated tips or generic marketing
        if not any(k in subject for k in ["tips", "how to", "prep", "webinar"]):
            return "Interviewing", ""

    return None, ""

# Let us see what emails classify into actions
classified_emails = []
for e in emails:
    cat, reason = classify(e)
    if cat:
        classified_emails.append({
            "email": e,
            "category": cat,
            "reason": reason
        })

print(f"\nTotal classified emails: {len(classified_emails)}")
for c in classified_emails:
    e = c["email"]
    print(f"[{e['date']:8s}] -> {c['category']:12s} | {e['sender'][:25]:25s} | {e['subject']}")
    if c['reason']:
        print(f"    Reason snippet: {c['reason'][:100]}")
