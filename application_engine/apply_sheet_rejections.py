#!/usr/bin/env python3
import os, gspread

KEYFILE = os.path.expanduser('~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json')
SPREADSHEET_ID = '1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY'

gc = gspread.service_account(KEYFILE)
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.sheet1

updates = [
    {
        'row': 11,
        'company': 'Made',
        'role': 'Frontend Engineer',
        'status': 'Rejected',
        'reason': 'Decision to move forward with other candidates whose experience more closely aligns with current needs.',
        'notes': 'Status: Rejected (Email response): Decision to move forward with other candidates.'
    },
    {
        'row': 16,
        'company': 'Wealth.com',
        'role': 'Associate Software Engineer',
        'status': 'Rejected',
        'reason': 'After careful consideration, decided not to move forward with candidacy for this role.',
        'notes': 'Status: Rejected (Sep 8): Your application to Wealth.com'
    },
    {
        'row': 29,
        'company': 'notion',
        'role': 'Forward Deployed Engineer, GTM, AMER',
        'status': 'Rejected',
        'reason': 'Not moving forward with candidacy for Forward Deployed Engineer, GTM, AMER position.',
        'notes': 'Status: Rejected (Sep 10, 4:17 PM): Update on your application to Notion, Ariq'
    },
    {
        'row': 39,
        'company': 'uniswap',
        'role': 'Software Engineer - Early Career',
        'status': 'Rejected',
        'reason': 'After carefully reviewing application, decided to move forward with other candidates at this time.',
        'notes': 'Status: Rejected (Sep 9): Uniswap Labs- Software Engineer - Early Career Opportunity Update'
    },
    {
        'row': 40,
        'company': 'uniswap',
        'role': 'Software Engineer- General Interest',
        'status': 'Rejected',
        'reason': 'After carefully reviewing application, decided to move forward with other candidates at this time.',
        'notes': 'Status: Rejected (Sep 10, 9:05 AM): Uniswap Labs- Software Engineer- General Interest Opportunity Update'
    },
    {
        'row': 47,
        'company': 'sierra',
        'role': 'Enterprise Sales Engineer',
        'status': 'Rejected',
        'reason': 'After careful consideration, decided to move forward with other candidates at this time.',
        'notes': 'Status: Rejected (Sep 10, 11:03 AM): Thank you for your interest in Sierra'
    },
    {
        'row': 48,
        'company': 'sierra',
        'role': 'Software Engineer, Platform',
        'status': 'Rejected',
        'reason': 'After careful consideration, decided to move forward with other candidates at this time.',
        'notes': 'Status: Rejected (Sep 10, 12:11 PM): Thank you for your interest in Sierra'
    },
    {
        'row': 57,
        'company': 'sourgum',
        'role': 'Software Engineer – Backend & DevOps',
        'status': 'Rejected',
        'reason': 'Exceptionally competitive process; decided to move forward with other candidates.',
        'notes': 'Status: Rejected (Sep 10, 11:20 AM): Update on Application for Software Engineer – Backend & DevOps - Sourgum'
    },
    {
        'row': 87,
        'company': 'resend',
        'role': 'Customer Success Engineer',
        'status': 'Rejected',
        'reason': 'After careful consideration, decided to pursue other candidates who are a better match at this time.',
        'notes': 'Status: Rejected (Sep 9): Customer Success Engineer at Resend'
    },
    {
        'row': 127,
        'company': 'palantir',
        'role': 'Backend Software Engineer - Application Development',
        'status': 'Rejected',
        'reason': 'After careful consideration, regret to inform you that we will not be proceeding with candidacy at this time.',
        'notes': 'Status: Rejected (Sep 8): Your application to Palantir'
    },
    {
        'row': 135,
        'company': 'palo-it',
        'role': 'Mobile Flutter Developer',
        'status': 'Rejected',
        'reason': 'After careful consideration, decided not to move forward with application for this role.',
        'notes': 'Status: Rejected (Sep 9): Update about your application to PALO IT'
    },
    {
        'row': 147,
        'company': 'everis',
        'role': 'Full-Stack Software Engineer, Growth',
        'status': 'Rejected',
        'reason': 'After carefully reviewing background and experience, decided not to move forward with application for this particular role.',
        'notes': 'Status: Rejected (Sep 10, 6:15 PM): Thank You for Applying to Everis'
    },
    {
        'row': 165,
        'company': 'creditgenie',
        'role': 'Staff iOS Engineer',
        'status': 'Rejected',
        'reason': 'After reviewing experience, decided not to move forward at this time.',
        'notes': 'Status: Rejected (Sep 9): Staff iOS Engineer at Credit Genie'
    },
    {
        'row': 197,
        'company': 'sentry',
        'role': 'Senior Technical Support Engineer',
        'status': 'Rejected',
        'reason': 'Timing did not line up as position has been filled.',
        'notes': 'Status: Rejected (Sep 10, 5:31 PM): Updates about the Senior Technical Support Engineer at Sentry'
    },
    {
        'row': 205,
        'company': 'vanta',
        'role': 'Senior Analytics Engineer',
        'status': 'Rejected',
        'reason': "Reviewed resume and won't be moving forward with application for this role at this time.",
        'notes': 'Status: Rejected (Sep 10, 1:59 PM): Vanta | Thank You for Applying!'
    },
    {
        'row': 235,
        'company': 'sentry',
        'role': 'Technical Support Engineer (4PM-12AM PST)',
        'status': 'Rejected',
        'reason': 'Timing did not line up as position has been filled.',
        'notes': 'Status: Rejected (Sep 10, 4:25 PM): Updates about the Technical Support Engineer (4PM-12AM PST) at Sentry'
    },
    {
        'row': 257,
        'company': 'synthesia',
        'role': 'Developer Advocate',
        'status': 'Rejected',
        'reason': 'After careful review, decided not to move forward with candidacy for this role.',
        'notes': 'Status: Rejected (Sep 10, 5:15 AM): An update on your application to Synthesia'
    }
]

# Fetch existing rows to preserve existing notes
sheet_rows = ws.get_all_values()

cells_to_update = []
print(f"Applying {len(updates)} rejection updates to Google Sheet:")

for u in updates:
    r = u['row']
    # Col B: Application Status (col 2)
    cells_to_update.append(gspread.Cell(r, 2, u['status']))
    # Col G: Rejection Reason (col 7)
    cells_to_update.append(gspread.Cell(r, 7, u['reason']))
    # Col H: Notes (col 8)
    existing_notes = sheet_rows[r-1][7] if len(sheet_rows[r-1]) > 7 else ""
    if u['notes'] not in existing_notes:
        combined_notes = f"{existing_notes} | {u['notes']}".strip(" |")
    else:
        combined_notes = existing_notes
    cells_to_update.append(gspread.Cell(r, 8, combined_notes))
    print(f"  Row {r:3d}: {u['company']} ({u['role']}) -> {u['status']}")

ws.update_cells(cells_to_update)
print("\n✅ Successfully updated all 17 rejection statuses, reasons, and notes in Google Sheet!")
