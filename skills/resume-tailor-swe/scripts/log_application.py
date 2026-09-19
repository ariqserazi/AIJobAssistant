#!/usr/bin/env python3
"""
log_application.py - Directly log confirmed job applications to Google Sheets Tracker and local markdown log.
"""

import os
import sys
import argparse
import datetime
from pathlib import Path

# Fix macOS Python SSL certificate validation
try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except ImportError:
    pass

try:
    from config_loader import load_config
except ImportError:
    try:
        from application_engine.config_loader import load_config
    except ImportError:
        def load_config(): return {}

_cfg = load_config()

KEYFILE = os.path.expanduser(_cfg.get("google_service_account_key") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY") or "")
SPREADSHEET_ID = _cfg.get("google_sheet_id") or os.environ.get("GOOGLE_SPREADSHEET_ID", "")

def get_tracking_md_path() -> Path:
    """Finds or initializes local application tracking markdown file."""
    candidates = [
        Path.cwd() / "references" / "application_tracking.md",
        Path(__file__).parent.parent.resolve() / "references" / "application_tracking.md",
        Path.home() / ".agents" / "skills" / "resume-tailor-swe" / "references" / "application_tracking.md"
    ]
    for c in candidates:
        if c.exists():
            return c
    p = Path.cwd() / "references" / "application_tracking.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    header = """# Job Application Tracker

| Date Applied | Company | Role | Location | Job Link | Resume Used | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    with open(p, "w", encoding="utf-8") as f:
        f.write(header)
    return p

TRACKING_MD = str(get_tracking_md_path())

def get_worksheet():
    if not SPREADSHEET_ID:
        raise ValueError("Google Spreadsheet ID is not configured in config.json or environment.")
    if not KEYFILE or not os.path.exists(KEYFILE):
        raise FileNotFoundError(f"Service account keyfile not found at {KEYFILE}")
    gc = gspread.service_account(filename=KEYFILE)
    sh = gc.open_by_key(SPREADSHEET_ID)
    return sh.get_worksheet(0)

def find_next_row(ws):
    """Finds the first row where Col A is blank or an empty template row."""
    col_a = ws.col_values(1)
    # Scan from row 2 onwards
    for idx, val in enumerate(col_a[1:], start=2):
        if not val or not val.strip():
            return idx
    # If all existing cells in Col A have values, next row is len + 1
    return len(col_a) + 1

import fcntl

def log_to_google_sheets(company, role, job_link, status="Submitted - Pending Response", notes="", date_str=None, rejection_reason="N/A"):
    if not SPREADSHEET_ID:
        print("ℹ️ Google Sheet ID not configured in config.json. Application is tracked locally in references/application_tracking.md.")
        return None
    if not KEYFILE or not os.path.exists(KEYFILE):
        print(f"ℹ️ Google service account key not found. Application is tracked locally in references/application_tracking.md.")
        return None

    lock_path = "/tmp/gspread_sheet_lock.lock"
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            ws = get_worksheet()
            target_row = find_next_row(ws)
            
            if not date_str:
                now = datetime.datetime.now()
                date_str = f"{now.month}/{now.day}/{now.year}"

            # Exact 8-column layout:
            # Col A: Company Name
            # Col B: Application Status
            # Col C: Role
            # Col D: Salary (MANDATORY: left blank to match sheet convention)
            # Col E: Date Submitted (M/D/YYYY)
            # Col F: Link to Job Req
            # Col G: Rejection Reason
            # Col H: Notes
            row_values = [
                company,
                status,
                role,
                "",  # Col D left strictly blank
                date_str,
                job_link,
                rejection_reason,
                notes
            ]
            
            range_name = f"A{target_row}:H{target_row}"
            ws.update(range_name=range_name, values=[row_values])
            print(f"Logged application to Google Sheet row {target_row}: {company} - {role}")
            return target_row
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)

def log_to_markdown(company, role, job_link, location="Remote (US)", resume_used="Base (Resume_2026.pdf)", status="Submitted (Confirmed)", notes="", date_iso=None):
    if not os.path.exists(TRACKING_MD):
        return
    if not date_iso:
        date_iso = datetime.datetime.now().strftime("%Y-%m-%d")

    row_line = f"| **{date_iso}** | **{company}** | {role} | {location} | [Job Link]({job_link}) | {resume_used} | **{status}** | {notes} |\n"
    
    with open(TRACKING_MD, "r") as f:
        content = f.read()

    # Append to markdown table if table header is found
    if "| Date Applied | Company |" in content:
        lines = content.splitlines(keepends=True)
        new_lines = []
        appended = False
        for line in lines:
            new_lines.append(line)
            if line.startswith("| :--- | :--- |") and not appended:
                # Add right after header separator
                new_lines.append(row_line)
                appended = True
        if not appended:
            new_lines.append(row_line)
        with open(TRACKING_MD, "w") as f:
            f.writelines(new_lines)
        print(f"✅ Appended entry to {TRACKING_MD}")

def main():
    parser = argparse.ArgumentParser(description="Log a job application to Google Sheets and tracking markdown.")
    parser.add_argument("--company", required=True, help="Company name (e.g. Lumanu, Wynd Labs)")
    parser.add_argument("--role", required=True, help="Role title (e.g. Junior Software Engineer)")
    parser.add_argument("--link", required=True, help="Job requisition or application link")
    parser.add_argument("--status", default="Submitted - Pending Response", help="Application status")
    parser.add_argument("--notes", default="", help="Notes (salary range, location, submission details)")
    parser.add_argument("--date", default=None, help="Submission date in M/D/YYYY format")
    parser.add_argument("--location", default="Remote (US)", help="Location / work mode")
    parser.add_argument("--resume", default="Base (Resume_2026.pdf)", help="Resume variant used")
    
    args = parser.parse_args()
    
    log_to_google_sheets(
        company=args.company,
        role=args.role,
        job_link=args.link,
        status=args.status,
        notes=args.notes,
        date_str=args.date
    )
    
    log_to_markdown(
        company=args.company,
        role=args.role,
        job_link=args.link,
        location=args.location,
        resume_used=args.resume,
        status="Submitted (Confirmed)" if "Submitted" in args.status else args.status,
        notes=args.notes
    )

if __name__ == "__main__":
    main()
