import json
import re

with open("/tmp/scoured_job_emails.json") as f:
    emails = json.load(f)

# Filter for recent emails: timestamps like 'PM', 'AM', 'Sep'
recent_emails = []
for e in emails:
    date = e["date"]
    if any(k in date for k in ["AM", "PM", "Sep"]):
        recent_emails.append(e)

print(f"Total recent emails (Sep 2026): {len(recent_emails)}")
for i, e in enumerate(recent_emails, 1):
    print(f"[{i:2d}] {e['date']:8s} | {e['sender'][:30]:30s} | {e['subject']}")
    print(f"     Snippet: {e['snippet'][:140]}")
    print()
