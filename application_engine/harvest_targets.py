#!/usr/bin/env python3
"""
harvest_targets.py - High-throughput job discovery engine.
Scrapes and filters early-career SWE, AI, Backend, and Full Stack positions across:
- Ashby (API)
- Greenhouse (API)
- Lever (API)
- Workday (CXS API)
Filters:
- Must be US-based (Remote US, NY/NYC Metro, NJ)
- Non-senior (exclude VP, Director, Principal, Staff, Senior Manager)
- Must match SWE, AI, Backend, Full Stack, Data, Python, Java, Cloud, Frontend, Mobile
- Checks against existing Google Sheet entries to ensure zero duplicates
"""

import urllib.request
import json
import ssl
import re
import os
import certifi
import gspread
from pathlib import Path

ctx = ssl.create_default_context(cafile=certifi.where())

SPREADSHEET_ID = "1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY"
KEYFILE = os.path.expanduser("~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json")

def get_applied_from_sheet():
    try:
        gc = gspread.service_account(KEYFILE)
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.sheet1
        rows = ws.get_all_values()
        applied_urls = set()
        applied_keys = set()
        for r in rows[1:]:
            comp = r[0].strip().lower() if len(r) > 0 else ""
            role = r[2].strip().lower() if len(r) > 2 else ""
            url = r[5].strip().lower().rstrip("/") if len(r) > 5 else ""
            if comp and role:
                applied_keys.add(f"{comp}:::{role}")
            if url:
                applied_urls.add(url)
        return applied_keys, applied_urls
    except Exception as e:
        print(f"Warning: Failed to fetch sheet records: {e}")
        return set(), set()

def is_valid_location(loc_str):
    if not loc_str:
        return False
    loc = loc_str.lower()
    # Exclude non-US locations
    non_us = ["london", "united kingdom", "uk", "poland", "germany", "canada", "toronto", "vancouver", "india", "bengaluru", "bangalore", "dubai", "australia", "sydney", "paris", "france", "ireland", "dublin", "netherlands", "amsterdam", "brazil", "singapore", "mexico", "spain", "tokyo", "japan", "china", "switzerland"]
    if any(nu in loc for nu in non_us) and "united states" not in loc and "us" not in loc:
        return False
    
    # Positive location indicators
    pos = ["united states", "usa", "us", "remote", "new york", "nyc", "ny", "new jersey", "nj", "san francisco", "sf", "ca", "seattle", "wa", "boston", "ma", "austin", "tx", "chicago", "il"]
    return any(p in loc for p in pos)

def is_target_role(title):
    t = title.lower()
    # Exclude senior / executive / non-tech
    exclude = ["director", "vice president", "vp", "principal", "head of", "lead", "staff", "manager", "recruiter", "sales", "account executive", "marketing", "counsel", "operations manager", "compliance", "chief", "executive assistant", "senior manager"]
    if any(e in t for e in exclude):
        return False
    
    # Must match engineering / tech keywords
    keywords = ["software", "developer", "engineer", "frontend", "backend", "full stack", "fullstack", "ai ", "machine learning", "ml ", "data engineer", "mobile", "ios", "android", "python", "java", "quantitative developer", "quant developer", "cloud", "systems"]
    return any(k in t for k in keywords)

# Curated companies using Ashby
ASHBY_COMPANIES = [
    "ramp", "wispr-flow", "injective-labs", "masabi", "whatnot", "thumbtack",
    "cognition", "linear", "anysphere", "perplexity", "together-ai", "postman",
    "retool", "sentry", "monad", "ironclad", "vanta", "brex", "airplane",
    "replicate", "baseten", "quora", "modal", "statsig", "dbt-labs",
    "outerbounds", "tome", "langchain", "elevenlabs", "mistral-ai",
    "sourcegraph", "hex", "duckdb", "axiom", "launchdarkly", "resend",
    "speakeasy", "convex", "warp", "modal-labs", "hyperline", "synthesia",
    "cursor", "superhuman", "runway", "character-ai", "poolside", "deepgram",
    "pave", "cohere", "huggingface", "glean", "reflect", "cal-com"
]

# Curated companies using Greenhouse
GREENHOUSE_COMPANIES = [
    "affirm", "figma", "stripe", "databricks", "pinterest", "airtable",
    "notion", "mongodb", "snowflake", "robinhood", "gusto", "anduril",
    "scaleai", "anthropic", "discord", "roblox", "instacart", "doordash",
    "coinbase", "chime", "plaid", "toast", "datadog", "blend", "hashicorp",
    "flexport", "gusto", "affirm", "box", "checkr", "klarna", "benchling"
]

# Curated companies using Lever
LEVER_COMPANIES = [
    "palantir", "atlassian", "spotify", "duolingo", "lyft", "uber", "yelp",
    "eventbrite", "nerdwallet", "gitlab", "datadoghq", "branch"
]

def fetch_ashby_jobs():
    results = []
    print(f"Scanning {len(ASHBY_COMPANIES)} Ashby company boards...")
    for comp in ASHBY_COMPANIES:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{comp}?includeCompensation=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                jobs = data.get("jobs", [])
                for j in jobs:
                    title = j.get("title", "")
                    loc = j.get("location", "")
                    job_url = j.get("jobUrl", "")
                    if is_target_role(title) and is_valid_location(loc) and job_url:
                        results.append({
                            "company": comp,
                            "role": title,
                            "location": loc,
                            "url": job_url,
                            "salary": "",
                            "platform": "ashby"
                        })
        except Exception:
            pass
    print(f"Found {len(results)} potential Ashby roles.")
    return results

def fetch_greenhouse_jobs():
    results = []
    print(f"Scanning {len(GREENHOUSE_COMPANIES)} Greenhouse company boards...")
    for comp in GREENHOUSE_COMPANIES:
        url = f"https://boards-api.greenhouse.io/v1/boards/{comp}/jobs"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                jobs = data.get("jobs", [])
                for j in jobs:
                    title = j.get("title", "")
                    loc = j.get("location", {}).get("name", "")
                    job_url = j.get("absolute_url", "")
                    if is_target_role(title) and is_valid_location(loc) and job_url:
                        results.append({
                            "company": comp,
                            "role": title,
                            "location": loc,
                            "url": job_url,
                            "salary": "",
                            "platform": "greenhouse"
                        })
        except Exception:
            pass
    print(f"Found {len(results)} potential Greenhouse roles.")
    return results

def fetch_lever_jobs():
    results = []
    print(f"Scanning {len(LEVER_COMPANIES)} Lever company boards...")
    for comp in LEVER_COMPANIES:
        url = f"https://api.lever.co/v0/postings/{comp}?mode=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                jobs = json.loads(resp.read().decode())
                if isinstance(jobs, list):
                    for j in jobs:
                        title = j.get("text", "")
                        cats = j.get("categories", {})
                        loc = cats.get("location", "")
                        job_url = j.get("applyUrl", "") or j.get("hostedUrl", "")
                        if is_target_role(title) and is_valid_location(loc) and job_url:
                            results.append({
                                "company": comp,
                                "role": title,
                                "location": loc,
                                "url": job_url,
                                "salary": "",
                                "platform": "lever"
                            })
        except Exception:
            pass
    print(f"Found {len(results)} potential Lever roles.")
    return results

def fetch_workday_morgan_stanley():
    results = []
    print("Scanning Morgan Stanley Workday portal...")
    seen = set()
    for q in ["Developer", "Software", "Python", "Java", "Analyst", "Data", "Cloud"]:
        url = "https://ms.wd5.myworkdayjobs.com/wday/cxs/ms/external/jobs"
        payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=6) as resp:
                postings = json.loads(resp.read().decode()).get("jobPostings", [])
                for p in postings:
                    path = p.get("externalPath", "")
                    title = p.get("title", "")
                    loc = p.get("locationsText", "")
                    if path not in seen and is_target_role(title) and is_valid_location(loc):
                        seen.add(path)
                        results.append({
                            "company": "Morgan Stanley",
                            "role": title,
                            "location": loc,
                            "url": f"https://ms.wd5.myworkdayjobs.com/en-US/external{path}",
                            "salary": "",
                            "platform": "workday"
                        })
        except Exception:
            pass
    print(f"Found {len(results)} Morgan Stanley Workday roles.")
    return results

def main():
    print("🚀 Starting Multi-Platform Job Harvesting Engine...")
    applied_keys, applied_urls = get_applied_from_sheet()
    print(f"Loaded {len(applied_keys)} existing keys and {len(applied_urls)} URLs from Sheet.")

    existing_targets_path = Path("application_engine/target_jobs.json")
    existing_targets = []
    if existing_targets_path.exists():
        try:
            existing_targets = json.load(open(existing_targets_path))
        except Exception:
            existing_targets = []

    all_harvested = []
    all_harvested.extend(existing_targets)
    all_harvested.extend(fetch_ashby_jobs())
    all_harvested.extend(fetch_greenhouse_jobs())
    all_harvested.extend(fetch_lever_jobs())
    all_harvested.extend(fetch_workday_morgan_stanley())

    # De-duplicate and filter
    final_list = []
    seen_urls = set()
    seen_keys = set()

    for item in all_harvested:
        comp = item.get("company", "").strip()
        role = (item.get("role") or item.get("title", "")).strip()
        url = item.get("url", "").strip()
        norm_u = url.lower().rstrip("/")
        key = f"{comp.lower()}:::{role.lower()}"

        if not url or not comp or not role:
            continue
        if norm_u in seen_urls or key in seen_keys:
            continue
        if norm_u in applied_urls or key in applied_keys:
            continue

        seen_urls.add(norm_u)
        seen_keys.add(key)
        final_list.append(item)

    print(f"\n✅ Total fresh, unapplied targets ready for processing: {len(final_list)}")
    
    # Save to application_engine/target_jobs.json
    with open(existing_targets_path, "w") as f:
        json.dump(final_list, f, indent=2)
    print(f"Saved {len(final_list)} targets to {existing_targets_path}")

    # Also save to skill references
    skill_ref = Path(os.path.expanduser("~/.agents/skills/resume-tailor-swe/references/target_jobs.json"))
    try:
        with open(skill_ref, "w") as f:
            json.dump(final_list, f, indent=2)
        print(f"Synced targets to {skill_ref}")
    except Exception as e:
        print(f"Could not sync to skill ref: {e}")

if __name__ == "__main__":
    main()
