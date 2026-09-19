import urllib.request
import urllib.error
import json
import os
import gspread

KEYFILE = os.path.expanduser('~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json')
gc = gspread.service_account(filename=KEYFILE)
ws = gc.open_by_key('1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY').sheet1
sheet_urls = set(ws.col_values(6))

with open('application_engine/suitable_unapplied_internships.json', 'r') as f:
    queue = json.load(f)

unapplied = [x for x in queue if x.get('url') not in sheet_urls]

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

live_jobs = []
for item in unapplied:
    url = item.get('url')
    if not url:
        continue
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
            final_url = resp.geturl()
            if 'error=true' in final_url or 'no longer available' in content.lower() or 'no longer open' in content.lower():
                continue
            if 'greenhouse' in url or 'lever' in url or 'ashby' in url:
                live_jobs.append(item)
                print(f"LIVE: {item.get('company')} - {item.get('title')} ({item.get('platform')}) -> {url}")
                if len(live_jobs) >= 15:
                    break
    except Exception as e:
        continue

with open('live_unapplied_targets.json', 'w') as f:
    json.dump(live_jobs, f, indent=2)

print(f"Found {len(live_jobs)} live unapplied targets.")
