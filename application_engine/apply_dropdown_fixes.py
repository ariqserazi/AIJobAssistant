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

cells_to_update = []
updated_summary = []

for idx, r in enumerate(all_rows[1:678], start=2):
    comp = r[0].strip()
    status = r[1].strip() if len(r) > 1 else ""
    role = r[2].strip() if len(r) > 2 else ""
    reason = r[6].strip() if len(r) > 6 else ""
    notes = r[7].strip() if len(r) > 7 else ""
    
    # 1. Correct false rejection for Deepgram (acknowledgment email)
    if comp.lower() == "deepgram" and "schedule an interview as soon as possible" in reason:
        cleaned_notes = notes.replace(" | Status: Rejected (Sep 9): Thank you for applying to Deepgram!", "")
        cells_to_update.append(gspread.Cell(idx, 2, "Submitted - Pending Response"))
        cells_to_update.append(gspread.Cell(idx, 7, "N/A"))
        cells_to_update.append(gspread.Cell(idx, 8, cleaned_notes))
        updated_summary.append((idx, comp, role, "Submitted - Pending Response", "N/A"))
        continue

    # 2. Normalize free-text rejection reasons into valid dropdown options
    if status == "Rejected" and reason not in VALID_DROPDOWN_OPTIONS:
        reason_lower = reason.lower()
        
        if any(k in reason_lower for k in ["position has been filled", "filled this position", "timing did not line up", "timing did not"]):
            chosen = "Applied Too Late"
        elif any(k in reason_lower for k in ["pipeline", "no new applicants", "process them as a priority"]):
            chosen = "No New Applicants"
        elif any(k in reason_lower for k in ["eliminated", "cancelled", "freeze", "closed this position"]):
            chosen = "Eliminated Role"
        else:
            chosen = 'Generic "Not A Good Fit"'
            
        # Ensure exact original quote/reason is preserved in Notes (Col H)
        clean_reason = re.sub(r"[\r\n\t]+", " ", reason).strip().lstrip("- \xa0")
        if clean_reason and clean_reason not in notes:
            new_notes = f"{notes} | Rejection detail: {clean_reason}".strip(" |")
        else:
            new_notes = notes
            
        # Col G (col 7): Dropdown selection
        cells_to_update.append(gspread.Cell(idx, 7, chosen))
        # Col H (col 8): Preserved notes
        cells_to_update.append(gspread.Cell(idx, 8, new_notes))
        
        updated_summary.append((idx, comp, role, status, chosen))

print(f"Total cells to update: {len(cells_to_update)} across {len(updated_summary)} rows.")
if cells_to_update:
    ws.update_cells(cells_to_update)
    print("✅ All cells successfully updated with valid Google Sheet dropdown options!")
else:
    print("All rows already compliant.")
