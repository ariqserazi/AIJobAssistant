#!/usr/bin/env python3
"""
harvest_unique_companies.py
Scrapes and selects ONE fresh US-based early/mid-career SWE/AI role per UNIQUE company.
Enforces:
1. MAX 1 ROLE PER COMPANY across the selection queue.
2. Checks existing Google Sheet rows so we avoid companies already heavily applied to (e.g. LangChain, Notion, Sentry, Poolside).
3. 100% United States (Remote US, NYC Metro, NJ, etc.).
4. Non-senior (exclude VP, Director, Principal, Staff, Senior Manager).
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

def get_applied_stats():
    gc = gspread.service_account(KEYFILE)
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.sheet1
    rows = ws.get_all_values()
    applied_urls = set()
    company_counts = {}
    for r in rows[1:]:
        comp = r[0].strip().lower() if len(r) > 0 else ""
        url = r[5].strip().lower().rstrip("/") if len(r) > 5 else ""
        if comp:
            company_counts[comp] = company_counts.get(comp, 0) + 1
        if url:
            applied_urls.add(url)
    return company_counts, applied_urls

def is_valid_location(loc_str):
    if not loc_str:
        return False
    loc = loc_str.lower()
    non_us = ["london", "united kingdom", "uk", "poland", "germany", "canada", "toronto", "vancouver", "india", "bengaluru", "bangalore", "dubai", "australia", "sydney", "paris", "france", "ireland", "dublin", "netherlands", "amsterdam", "brazil", "singapore", "mexico", "spain", "tokyo", "japan", "china", "switzerland", "ukraine"]
    if any(nu in loc for nu in non_us) and "united states" not in loc and "us" not in loc:
        return False
    pos = ["united states", "usa", "us", "remote", "new york", "nyc", "ny", "new jersey", "nj", "san francisco", "sf", "ca", "seattle", "wa", "boston", "ma", "austin", "tx", "chicago", "il", "colorado", "denver"]
    return any(p in loc for p in pos)

def is_target_role(title):
    t = title.lower()
    exclude = ["director", "vice president", "vp", "principal", "head of", "lead", "staff", "manager", "recruiter", "sales", "account executive", "marketing", "counsel", "operations manager", "compliance", "chief", "executive assistant", "senior manager", "legal", "intern", "internship"]
    if any(e in t for e in exclude):
        return False
    keywords = ["software", "developer", "engineer", "frontend", "backend", "full stack", "fullstack", "ai ", "machine learning", "ml ", "data engineer", "mobile", "ios", "android", "python", "java", "quantitative developer", "quant developer", "cloud", "systems", "solutions engineer", "applications"]
    return any(k in t for k in keywords)

ASHBY_COMPANIES = [
    "ramp", "wispr-flow", "injective-labs", "masabi", "whatnot", "thumbtack",
    "cognition", "linear", "anysphere", "together-ai", "postman",
    "retool", "monad", "ironclad", "brex", "airplane", "replicate", "modal", "statsig", "dbt-labs",
    "outerbounds", "tome", "mistral-ai", "sourcegraph", "hex", "duckdb",
    "launchdarkly", "resend", "speakeasy", "convex", "warp", "hyperline",
    "synthesia", "cursor", "superhuman", "runway", "character-ai", "deepgram",
    "pave", "cohere", "huggingface", "glean", "reflect", "cal-com", "incident-io",
    "clerk", "supabase", "pylon", "livekit", "vapi", "tavus", "exa", "cartesia",
    "wandb", "posthog", "raycast", "unkey", "dub", "sourgum", "confido", "mechanize", "baseten"
]

GREENHOUSE_COMPANIES = [
    "affirm", "figma", "stripe", "databricks", "pinterest", "airtable",
    "mongodb", "snowflake", "robinhood", "gusto", "anduril",
    "scaleai", "anthropic", "discord", "roblox", "instacart", "doordash",
    "coinbase", "chime", "plaid", "toast", "blend", "hashicorp",
    "flexport", "box", "checkr", "klarna", "benchling", "ripple", "gitlab",
    "asana", "dropbox", "reddit", "samsara", "datadog", "servicenow", "zendesk",
    "hubspot", "twilio", "zoom", "unity", "starburst", "dremio", "clickhouse",
    "grafana", "timescale", "yugabyte", "cockroachlabs", "redis", "neo4j", "temporal",
    "prefect", "dataiku", "anyscale", "labelbox", "pinecone", "weaviate", "qdrant", "chroma"
]

LEVER_COMPANIES = [
    "palantir", "atlassian", "spotify", "duolingo", "lyft", "uber", "yelp",
    "eventbrite", "nerdwallet", "branch", "coursera", "creditkarma", "kraken",
    "opensea", "alchemy", "chainalysis", "fireblocks", "ledger"
]

def main():
    print("🚀 Scanning for 100+ UNIQUE COMPANIES (1 role per company)...")
    company_counts, applied_urls = get_applied_stats()
    
    unique_company_jobs = []
    used_companies = set()

    # 1. First, check our existing harvest pool from target_jobs.json
    try:
        existing_targets = json.load(open("application_engine/target_jobs.json"))
        for j in existing_targets:
            comp = j.get("company", "").strip().lower()
            url = j.get("url", "").strip().lower().rstrip("/")
            title = j.get("role") or j.get("title", "")
            loc = j.get("location", "")

            # Filter conditions:
            # - Not in applied URLs
            # - Company has fewer than 3 applications in Sheet (prioritize fresh companies)
            # - Company not already used in this unique list
            if comp and comp not in used_companies and url not in applied_urls:
                if company_counts.get(comp, 0) < 3 and is_target_role(title) and is_valid_location(loc):
                    used_companies.add(comp)
                    unique_company_jobs.append(j)
    except Exception as e:
        print(f"Error checking target_jobs: {e}")

    print(f"Loaded {len(unique_company_jobs)} unique companies from existing target pool.")

    # 2. Scan Ashby companies for fresh companies
    for comp in ASHBY_COMPANIES:
        c_low = comp.lower()
        if c_low in used_companies or company_counts.get(c_low, 0) >= 3:
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
                    norm_u = j_url.lower().rstrip("/")
                    if is_target_role(title) and is_valid_location(loc) and norm_u not in applied_urls:
                        used_companies.add(c_low)
                        unique_company_jobs.append({
                            "company": comp,
                            "role": title,
                            "location": loc,
                            "url": j_url,
                            "salary": "",
                            "platform": "ashby"
                        })
                        print(f"  + [Ashby] {comp}: {title} ({loc})")
                        break
        except Exception:
            pass

    # 3. Scan Greenhouse companies for fresh companies
    for comp in GREENHOUSE_COMPANIES:
        c_low = comp.lower()
        if c_low in used_companies or company_counts.get(c_low, 0) >= 3:
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
                    norm_u = j_url.lower().rstrip("/")
                    if is_target_role(title) and is_valid_location(loc) and norm_u not in applied_urls:
                        used_companies.add(c_low)
                        unique_company_jobs.append({
                            "company": comp,
                            "role": title,
                            "location": loc,
                            "url": j_url,
                            "salary": "",
                            "platform": "greenhouse"
                        })
                        print(f"  + [Greenhouse] {comp}: {title} ({loc})")
                        break
        except Exception:
            pass

    # 4. Scan Lever companies for fresh companies
    for comp in LEVER_COMPANIES:
        c_low = comp.lower()
        if c_low in used_companies or company_counts.get(c_low, 0) >= 3:
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
                        norm_u = j_url.lower().rstrip("/")
                        if is_target_role(title) and is_valid_location(loc) and norm_u not in applied_urls:
                            used_companies.add(c_low)
                            unique_company_jobs.append({
                                "company": comp,
                                "role": title,
                                "location": loc,
                                "url": j_url,
                                "salary": "",
                                "platform": "lever"
                            })
                            print(f"  + [Lever] {comp}: {title} ({loc})")
                            break
        except Exception:
            pass

    print(f"\n🎯 Total UNIQUE COMPANIES harvested: {len(unique_company_jobs)}")
    with open("application_engine/unique_company_jobs.json", "w") as f:
        json.dump(unique_company_jobs, f, indent=2)
    print(f"Saved to application_engine/unique_company_jobs.json")

if __name__ == "__main__":
    main()
