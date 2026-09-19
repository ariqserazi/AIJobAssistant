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

gc = gspread.service_account(KEYFILE)
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.sheet1
all_rows = ws.get_all_values()

VALID_DROPDOWN_OPTIONS = [
    'Filled - Internal',
    'Generic "Not A Good Fit"',
    'No New Applicants',
    'Eliminated Role',
    'Changed Job Scope',
    'Applied Too Late',
    'Auto-Reject: No Feedback Provided',
    '1st Round Rejection - Feedback Provided',
    '1st Round Rejection - No Feedback Provided',
    'Middle Round Rejection - Feedback Provided',
    'Middle Round Rejection - No Feedback Provided',
    'Final Round Rejection - Feedback Provided',
    'Final Round Rejection - No Feedback Provided',
    'No Response: Sent Email',
    'Post-Interview Follow-Up Email',
    'N/A'
]

plan = []
for idx, r in enumerate(all_rows[1:678], start=2):
    comp = r[0].strip()
    status = r[1].strip() if len(r) > 1 else ""
    role = r[2].strip() if len(r) > 2 else ""
    reason = r[6].strip() if len(r) > 6 else ""
    notes = r[7].strip() if len(r) > 7 else ""
    
    # Deepgram fix
    if comp.lower() == "deepgram" and "schedule an interview as soon as possible" in reason:
        plan.append({
            "row": idx,
            "company": comp,
            "role": role,
            "old_status": status,
            "new_status": "Submitted - Pending Response",
            "old_reason": reason,
            "new_reason": "N/A",
            "notes": notes.replace(" | Status: Rejected (Sep 9): Thank you for applying to Deepgram!", "")
        })
        continue

    if status == "Rejected" and reason not in VALID_DROPDOWN_OPTIONS:
        reason_lower = reason.lower()
        
        # Determine best dropdown option
        if any(k in reason_lower for k in ["position has been filled", "filled this position", "timing did not line up", "timing did not"]):
            chosen = "Applied Too Late"
        elif any(k in reason_lower for k in ["pipeline", "no new applicants", "process them as a priority"]):
            chosen = "No New Applicants"
        elif any(k in reason_lower for k in ["eliminated", "cancelled", "freeze", "closed this position"]):
            chosen = "Eliminated Role"
        else:
            chosen = 'Generic "Not A Good Fit"'
            
        # Ensure the snippet is preserved in notes
        clean_reason = re.sub(r"[\r\n\t]+", " ", reason).strip().lstrip("- \xa0")
        reason_note = f"Rejection reason: {clean_reason}"
        if clean_reason and clean_reason not in notes:
            new_notes = f"{notes} | {reason_note}".strip(" |")
        else:
            new_notes = notes
            
        plan.append({
            "row": idx,
            "company": comp,
            "role": role,
            "old_status": status,
            "new_status": status,
            "old_reason": reason,
            "new_reason": chosen,
            "notes": new_notes
        })

print(f"Total rows planned for dropdown normalization: {len(plan)}")
for p in plan[:15]:
    print(f"Row {p['row']:3d} | {p['company']} ({p['role'][:25]}):")
    print(f"   Old Reason: {p['old_reason'][:50]}...")
    print(f"   New Reason: {p['new_reason']}")
    print("-" * 50)
