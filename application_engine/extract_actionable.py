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

emails = {}
for path in ["/tmp/scoured_job_emails.json", "/tmp/all_recent_emails_14d.json"]:
    if os.path.exists(path):
        with open(path) as f:
            for e in json.load(f):
                key = (e["sender"], e["subject"], e["date"])
                emails[key] = e

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

def clean_str(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

actionable = []
for app in pending_apps:
    comp = app["company"]
    clean_comp = clean_str(comp)
    if len(clean_comp) < 3 or clean_comp in ["made", "team", "hire", "work"]:
        continue
        
    for key, e in emails.items():
        sender = e["sender"].lower()
        subj = e["subject"].lower()
        snip = e["snippet"].lower()
        full = f"{sender} {subj} {snip}"
        
        # Exclude verification codes
        if any(k in subj for k in ["security code", "your code", "verification code"]):
            continue

        pattern = r"\b" + re.escape(comp.lower()) + r"\b"
        if re.search(pattern, full) or clean_comp in clean_str(sender) or clean_comp in clean_str(subj):
            
            # Check rejection
            has_rejection = any(k in full for k in [
                "not moving forward", "decided not to", "move forward with other",
                "move forward with another", "pursue other candidates",
                "after careful consideration", "not to move forward",
                "unfortunately, we will not", "unfortunately we will not", "unfortunately, we won't",
                "unable to offer", "not selected", "position has been filled",
                "timing did not line up", "exceptionally competitive", "closed this position",
                "decision not to move forward"
            ])
            # Check assessment
            has_assessment = any(k in full for k in [
                "complete talent assessment", "trader personality assessment",
                "predictive index behavioral assessment", "predictive index assessment",
                "codesignal", "hackerrank", "coderbyte", "take-home challenge",
                "online assessment", "action required: next steps to trillium"
            ]) or ("assessment" in subj and any(k in subj for k in ["invitation", "complete", "action required", "next step", "expire"]))
            
            # Check interview
            has_interview = any(k in full for k in [
                "schedule your interview", "schedule an interview", "schedule a call",
                "invitation to interview", "like to invite you to interview", "like to invite you to speak",
                "next steps in the interview", "interview with the team", "phone screen with",
                "first round interview", "technical interview", "virtual interview", "interview confirmation"
            ])
            
            # Note: Do not count generic "If you are not selected" boilerplate inside confirmation emails as rejection!
            if has_rejection:
                # If it's a confirmation email with boilerplate "If you are not selected... keep an eye on jobs page", skip
                if any(bp in snip for bp in ["if you are not selected for this position, keep an eye", "if you are not selected, we encourage", "if you don't hear back, we've likely"]):
                    continue
                if "thank you for applying" in subj or "application received" in subj:
                    # check if body really rejected
                    if not any(k in snip for k in ["decided not to", "move forward with other", "not moving forward", "unable to offer"]):
                        continue
                actionable.append({"app": app, "email": e, "type": "Rejected"})
            elif has_assessment:
                actionable.append({"app": app, "email": e, "type": "Assessment"})
            elif has_interview:
                actionable.append({"app": app, "email": e, "type": "Interviewing"})

print(f"Total actionable matches for pending applications: {len(actionable)}")
seen_combos = set()
for act in actionable:
    a = act["app"]
    em = act["email"]
    t = act["type"]
    combo = (a["row_idx"], t, em["subject"])
    if combo in seen_combos:
        continue
    seen_combos.add(combo)
    print(f"Row {a['row_idx']} | {a['company']} ({a['role']}) -> {t}")
    print(f"   Date: {em['date']} | Subj: {em['subject']}")
    print(f"   Snippet: {em['snippet'][:120]}")
    print("-" * 50)
