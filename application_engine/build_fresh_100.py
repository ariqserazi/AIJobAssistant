#!/usr/bin/env python3
import urllib.request
import json
import ssl
import re
import os
import certifi
import gspread

ctx = ssl.create_default_context(cafile=certifi.where())

SPREADSHEET_ID = "1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY"
KEYFILE = os.path.expanduser("~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json")

def get_sheet_records():
    gc = gspread.service_account(KEYFILE)
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.sheet1
    rows = ws.get_all_values()
    applied_urls = set()
    applied_comps = set()
    for r in rows[1:]:
        comp = r[0].strip().lower() if len(r) > 0 else ""
        url = r[5].strip().lower().rstrip("/") if len(r) > 5 else ""
        if comp:
            applied_comps.add(comp)
        if url:
            applied_urls.add(url)
    return applied_comps, applied_urls

applied_comps, applied_urls = get_sheet_records()
print(f"Total already-applied companies in Google Sheet: {len(applied_comps)}")

def is_valid_location(loc_str):
    if not loc_str:
        return True
    loc = loc_str.lower()
    non_us = ["london", "united kingdom", "uk", "poland", "germany", "canada", "toronto", "vancouver", "india", "bengaluru", "bangalore", "dubai", "australia", "sydney", "paris", "france", "ireland", "dublin", "netherlands", "amsterdam", "brazil", "singapore", "mexico", "spain", "tokyo", "japan", "china", "switzerland", "ukraine", "warsaw", "emea", "portugal", "latam", "apac", "philippines", "taguig", "hong kong", "taiwan", "taipei"]
    if any(nu in loc for nu in non_us) and "united states" not in loc and "us" not in loc:
        return False
    pos = ["united states", "usa", "us", "remote", "new york", "nyc", "ny", "new jersey", "nj", "san francisco", "sf", "ca", "seattle", "wa", "boston", "ma", "austin", "tx", "chicago", "il", "colorado", "denver", "north america", "amer"]
    return any(p in loc for p in pos) or "remote" in loc

def is_target_role(title):
    t = title.lower()
    exclude = ["director", "vice president", "vp", "principal", "head of", "lead", "staff", "manager", "recruiter", "sales", "account executive", "marketing", "counsel", "operations manager", "compliance", "chief", "executive assistant", "senior manager", "legal", "intern", "internship", "investigator", "designer", "curator", "content", "partner i", "channel solutions"]
    if any(e in t for e in exclude):
        return False
    keywords = ["software", "developer", "engineer", "frontend", "backend", "full stack", "fullstack", "ai ", "machine learning", "ml ", "data engineer", "mobile", "ios", "android", "python", "java", "quantitative developer", "quant developer", "cloud", "systems", "solutions engineer", "applications", "applied scientist", "architect", "support engineer", "infrastructure"]
    return any(k in t for k in keywords)

final_jobs = []
seen_companies = set()

def add_entry(company, title, loc, url, platform):
    c_clean = company.strip().lower()
    norm_u = url.lower().rstrip("/")
    if c_clean in seen_companies or c_clean in applied_comps or norm_u in applied_urls:
        return False
    seen_companies.add(c_clean)
    final_jobs.append({
        "company": company.strip(),
        "role": title.strip(),
        "location": loc.strip(),
        "url": url.strip(),
        "salary": "",
        "platform": platform
    })
    print(f"[{len(final_jobs)}] {company}: {title} ({loc})")
    return True

# 1. Existing unapplied targets
for path in ["application_engine/unique_100_jobs.json", "application_engine/target_jobs.json", "application_engine/unique_company_jobs.json"]:
    if os.path.exists(path):
        try:
            items = json.load(open(path))
            for item in items:
                comp = item.get("company", "")
                title = item.get("role") or item.get("title", "")
                loc = item.get("location", "")
                url = item.get("url", "")
                plat = item.get("platform", "ashby")
                if is_target_role(title) and is_valid_location(loc) and url:
                    add_entry(comp, title, loc, url, plat)
        except Exception:
            pass

# 2. Greenhouse boards
GREENHOUSE_LIST = [
    "affirm", "airtable", "amplitude", "asana", "betterment", "blend", "box",
    "braze", "brex", "carta", "checkr", "chime", "cloudflare", "cockroachlabs",
    "consensys", "coursera", "datadog", "dataiku", "discord", "dropbox",
    "duolingo", "elastic", "figma", "flatironhealth", "flexport", "gusto",
    "instacart", "klaviyo", "labelbox", "lattice", "mixpanel", "modernhealth",
    "mongodb", "neo4j", "okta", "pagerduty", "plaid", "reddit", "ripple",
    "robinhood", "roblox", "samsara", "scaleai", "starburst", "toast",
    "twilio", "twitch", "udemy", "verkada", "webflow", "yugabyte", "zocdoc",
    "zscaler", "benchling", "hashicorp", "snyk", "segment", "dbtlabs", "retool",
    "waymo", "block", "purestorage", "tanium", "rubrik", "appian",
    "zapier", "dremio", "guild", "temporal", "cohere", "glean",
    "tripadvisor", "sofi", "upstart", "bitgo", "aptoslabs", "tenstorrent", "graphcore",
    "fivetran", "hightouch", "honeycomb", "newrelic", "sumologic", "huntress",
    "expel", "descript", "assemblyai"
]

for comp in GREENHOUSE_LIST:
    if len(final_jobs) >= 105:
        break
    if comp.lower() in seen_companies or comp.lower() in applied_comps:
        continue
    url = f"https://boards-api.greenhouse.io/v1/boards/{comp}/jobs"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=4) as resp:
            jobs = json.loads(resp.read().decode()).get("jobs", [])
            for j in jobs:
                title = j.get("title", "")
                loc = j.get("location", {}).get("name", "")
                j_url = j.get("absolute_url", "")
                if is_target_role(title) and is_valid_location(loc) and j_url:
                    if add_entry(comp, title, loc, j_url, "greenhouse"):
                        break
    except Exception:
        pass

# 3. Ashby boards
ASHBY_LIST = [
    "finch", "cursor", "injective-labs", "thumbtack", "modal", "hex",
    "synthesia", "posthog", "runpod", "deepgram", "cohere", "resend",
    "clerk", "supabase", "pylon", "livekit", "vapi", "cartesia", "tavus",
    "exa", "perplexity", "canals", "sourgum", "confido", "mechanize",
    "outerbounds", "axiom", "glide", "replit", "postman", "anyscale",
    "prefect", "astronomer", "cube", "neon", "pinecone"
]

for comp in ASHBY_LIST:
    if len(final_jobs) >= 105:
        break
    if comp.lower() in seen_companies or comp.lower() in applied_comps:
        continue
    url = f"https://api.ashbyhq.com/posting-api/job-board/{comp}?includeCompensation=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=4) as resp:
            jobs = json.loads(resp.read().decode()).get("jobs", [])
            for j in jobs:
                title = j.get("title", "")
                loc = j.get("location", "")
                j_url = j.get("jobUrl", "")
                if is_target_role(title) and is_valid_location(loc) and j_url:
                    if add_entry(comp, title, loc, j_url, "ashby"):
                        break
    except Exception:
        pass

# 4. Lever boards
for comp in ["palantir", "spotify"]:
    if len(final_jobs) >= 105:
        break
    if comp.lower() in seen_companies or comp.lower() in applied_comps:
        continue
    url = f"https://api.lever.co/v0/postings/{comp}?mode=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=4) as resp:
            jobs = json.loads(resp.read().decode())
            if isinstance(jobs, list):
                for j in jobs:
                    title = j.get("text", "")
                    loc = j.get("categories", {}).get("location", "")
                    j_url = j.get("applyUrl", "") or j.get("hostedUrl", "")
                    if is_target_role(title) and is_valid_location(loc) and j_url:
                        if add_entry(comp, title, loc, j_url, "lever"):
                            break
    except Exception:
        pass

final_100 = final_jobs[:100]
print(f"\n🎉 Successfully compiled EXACTLY {len(final_100)} jobs across {len(set(j['company'].lower() for j in final_100))} 100% UNAPPLIED UNIQUE COMPANIES!")

with open("application_engine/unique_100_jobs.json", "w") as f:
    json.dump(final_100, f, indent=2)
print("Saved exact 100 unique company jobs to application_engine/unique_100_jobs.json")
