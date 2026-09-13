#!/usr/bin/env python3
import os, sys, re, json

try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except ImportError:
    pass

import gspread

KEYFILE = os.path.expanduser("~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json")
SPREADSHEET_ID = "1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY"

print("Connecting to Google Sheets tracker...", flush=True)
gc = gspread.service_account(filename=KEYFILE)
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.get_worksheet(0)
rows = ws.get_all_values()

applied_urls = set()
applied_pairs = set()
for r in rows[1:]:
    comp = r[0].strip().lower()
    role = r[2].strip().lower()
    url = r[5].strip().lower().rstrip("/")
    if url:
        applied_urls.add(url)
    if comp and role:
        applied_pairs.add(f"{comp}:::{role}")

print(f"Loaded {len(applied_urls)} applied URLs and {len(applied_pairs)} applied pairs from Sheet.", flush=True)

def parse_file(filepath, season_name):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}", flush=True)
        return []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
        
    pattern = re.compile(
        r"<tr>\s*<td>\s*<strong>(?:<a[^>]*>)?([^<]+)(?:</a>)?</strong>\s*</td>\s*"
        r"<td>\s*(.*?)\s*</td>\s*"
        r"<td>\s*(.*?)\s*</td>\s*"
        r"<td>.*?<a href=\"(http[^\"]+)\"[^>]*>\s*<img[^>]*alt=\"Apply\"",
        re.DOTALL | re.IGNORECASE
    )
    
    matches = pattern.findall(text)
    print(f"File {filepath}: found {len(matches)} raw table rows", flush=True)
    
    valid = []
    for comp, role, loc, apply_url in matches:
        if "🔒" in role or "🔒" in comp:
            continue
        clean_comp = re.sub(r"<[^>]+>", "", comp).strip()
        clean_role = re.sub(r"<[^>]+>", "", role).strip()
        clean_loc = re.sub(r"<[^>]+>", "", loc).strip()
        clean_url = apply_url.split("?utm_source=")[0].split("&utm_source=")[0].strip()
        
        u_low = clean_url.lower()
        plat = None
        if "greenhouse.io" in u_low or "gh_jid=" in u_low:
            plat = "greenhouse"
        elif "lever.co" in u_low:
            plat = "lever"
        elif "ashbyhq.com" in u_low:
            plat = "ashby"
        elif "myworkdayjobs.com" in u_low:
            plat = "workday"
            
        if not plat:
            continue
            
        r_low = clean_role.lower()
        if not any(k in r_low for k in ["software", "swe", "engineer", "developer", "machine learning", "ml", "ai", "data", "backend", "full stack", "fullstack", "platform", "cloud", "systems", "infra", "security", "intern", "co-op", "coop"]):
            continue
        if any(k in r_low for k in ["hardware", "sales intern", "marketing", "recruiting", "finance intern", "account", "business intern"]):
            continue
            
        pair_key = f"{clean_comp.lower()}:::{clean_role.lower()}"
        if clean_url.lower().rstrip("/") in applied_urls or pair_key in applied_pairs:
            continue
            
        valid.append({
            "company": clean_comp,
            "role": clean_role,
            "location": clean_loc,
            "url": clean_url,
            "platform": plat,
            "season": season_name
        })
    return valid

summer = parse_file("/tmp/summer2027.md", "Summer 2027")
offseason = parse_file("/tmp/offseason2027.md", "Winter/Off-Season 2027")

queue = summer + offseason
seen_u = set()
deduped_queue = []
for j in queue:
    u = j["url"].lower().rstrip("/")
    if u not in seen_u:
        seen_u.add(u)
        deduped_queue.append(j)

print(f"Total FRESH UNAPPLIED target internships: {len(deduped_queue)}", flush=True)

out_file = "application_engine/internship_queue.json"
with open(out_file, "w") as f:
    json.dump(deduped_queue, f, indent=2)

print(f"✅ Saved fresh queue to {out_file}", flush=True)
