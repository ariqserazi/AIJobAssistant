#!/usr/bin/env python3
"""
fetch_fresh_internships.py - Daily Fresh SWE Internship & Job Harvester
Fetches newly-posted early-career SWE and technical internship postings across live tracking repositories,
filters out all existing applications in Ariq's Google Sheet, enforces candidate constraints,
and builds fresh, deduplicated, company-interleaved application queues.
"""

import os
import sys
import re
import json
import ssl
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl._create_unverified_context()

import gspread

KEYFILE = os.path.expanduser("~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json")
SPREADSHEET_ID = "1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY"

REPO_SOURCES_HTML = [
    {
        "name": "SimplifyJobs/Summer2027-Internships",
        "url": "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README.md"
    },
    {
        "name": "SimplifyJobs/Summer2026-Internships",
        "url": "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"
    },
    {
        "name": "SimplifyJobs/Summer2025-Internships",
        "url": "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/README.md"
    },
    {
        "name": "pittcsc/Summer2025-Internships",
        "url": "https://raw.githubusercontent.com/pittcsc/Summer2025-Internships/dev/README.md"
    }
]

SPEEDYAPPLY_MD = {
    "name": "speedyapply/2026-SWE-College-Jobs",
    "url": "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/README.md"
}

def load_applied_from_sheet():
    print("📊 Fetching applied records from Ariq's Google Sheet...", flush=True)
    applied_urls = set()
    applied_pairs = set()
    try:
        gc = gspread.service_account(KEYFILE)
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.sheet1
        rows = ws.get_all_values()
        for r in rows[1:]:
            c = r[0].strip().lower() if len(r) > 0 else ""
            role_val = r[2].strip().lower() if len(r) > 2 else ""
            u = r[5].strip().lower().rstrip("/") if len(r) > 5 else ""
            if c and role_val:
                applied_pairs.add(f"{c}:::{role_val}")
            if u:
                applied_urls.add(u)
        print(f"  ✅ Loaded {len(applied_urls)} applied URLs and {len(applied_pairs)} applied pairs (Total Rows: {len(rows)}).", flush=True)
    except Exception as e:
        print(f"  ⚠️ Warning fetching sheet records: {e}", flush=True)
    return applied_urls, applied_pairs

def is_suitable_candidate_role(title, comp, loc):
    t = title.lower()
    c = comp.lower()
    l = loc.lower()

    # Must be an internship / co-op / student fellow role
    if not any(k in t for k in ["intern", "co-op", "coop", "fellow"]):
        return False

    # Exclude non-early-career / experienced / senior roles
    unwanted_seniority = [
        "senior", "staff", "principal", "lead", "manager", "director", "architect",
        "head of", "yoe", "years of experience", "3+ years", "4+ years", "5+ years",
        "phd only", "phd intern", "doctoral", "postdoc"
    ]
    if any(k in t for k in unwanted_seniority):
        return False

    # Exclude non-CS engineering disciplines
    unwanted_disciplines = [
        "electrical engineer", "hardware engineer", "mechanical", "chemical", "materials",
        "optical", "rf engineer", "propulsion", "aerospace", "civil engineer", "battery"
    ]
    if any(k in t for k in unwanted_disciplines):
        return False

    # Exclude non-technical / business / compliance / trading roles
    unwanted_nontech = [
        "aml", "investigator", "compliance", "legal", "recruiter", "recruiting", "talent",
        "sales", "marketing", "account executive", "financial analyst", "tax intern",
        "audit intern", "graphic design", "conversation designer", "content designer",
        "trader", "trading intern", "equity trader", "quant trader", "broker"
    ]
    if any(k in t for k in unwanted_nontech):
        return False

    # Must match SWE / Computer Science / Technical roles
    tech_matches = [
        "software", "swe", "sde", "developer", "backend", "front", "full stack", "fullstack",
        "systems", "cloud", "devops", "infrastructure", "platform", "distributed",
        "data engineer", "machine learning", "applied ai", "ai engineer", "mobile", "android", "ios",
        "security engineer", "application security", "information technology", "qa engineer",
        "test engineer", "automation", "product manager", "pm intern"
    ]
    if not any(k in t for k in tech_matches):
        return False

    # Exclude strictly foreign / international locations without US option
    foreign_locs = [
        "canada", "ontario", "toronto", "vancouver", "montreal", "quebec", "waterloo", "ottawa", "markham",
        "united kingdom", "london", "germany", "berlin", "india", "bangalore", "hyderabad", "pune", "gurgaon",
        "singapore", "australia", "sydney", "melbourne", "france", "paris", "netherlands", "amsterdam",
        "poland", "warsaw", "krakow", "switzerland", "zurich", "japan", "tokyo", "taiwan", "ireland", "dublin",
        "brazil", "mexico", "israel", "tel aviv", "china", "spain"
    ]
    is_foreign = any(fl in l for fl in foreign_locs)
    has_us = any(us in l for us in ["usa", "remote", "united states", "us", "ny", "nj", "ca", "tx", "ma", "wa", "il", "va", "co", "pa", "nc", "fl", "ga"])
    if is_foreign and not has_us:
        return False

    return True

def parse_html_table(text):
    postings = []
    last_comp = "Unknown"
    for r in text.split("<tr>"):
        if "<td>" not in r:
            continue
        tds = re.findall(r"<td[^>]*>(.*?)</td>", r, re.DOTALL)
        if len(tds) >= 4:
            raw_comp = re.sub(r"<[^>]+>", "", tds[0]).strip()
            raw_comp = raw_comp.replace("🔥", "").replace("🔒", "").strip()
            if raw_comp and "↳" not in raw_comp:
                last_comp = raw_comp
            comp = last_comp

            role = re.sub(r"<[^>]+>", "", tds[1]).replace("🔥", "").replace("🔒", "").strip()
            loc = re.sub(r"<[^>]+>", "", tds[2]).strip()
            href_m = re.search(r'href=\"([^\"]+)\"', tds[3])
            if href_m and "🔒" not in tds[1]:
                u = href_m.group(1).strip().split("?utm_source=")[0].split("&utm_source=")[0].split("?ref=")[0].strip()
                if u.startswith("http"):
                    postings.append({
                        "company": comp,
                        "title": role,
                        "role": role,
                        "location": loc,
                        "url": u
                    })
    return postings

def parse_speedyapply_table(text):
    postings = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 5:
            comp = re.sub(r"<[^>]+>", "", parts[0]).replace("🔥", "").replace("🔒", "").strip()
            role = parts[1].replace("🔥", "").replace("🔒", "").strip()
            loc = parts[2].strip()
            href_m = re.search(r'href=\"([^\"]+)\"', parts[4])
            if href_m and "🔒" not in parts[1]:
                u = href_m.group(1).strip().split("?utm_source=")[0].split("&utm_source=")[0].split("?ref=")[0].strip()
                if u.startswith("http"):
                    postings.append({
                        "company": comp,
                        "title": role,
                        "role": role,
                        "location": loc,
                        "url": u
                    })
    return postings

def round_robin_interleave(jobs):
    by_comp = defaultdict(list)
    for j in jobs:
        by_comp[j["company"].lower()].append(j)
    
    interleaved = []
    while any(by_comp.values()):
        for comp in list(by_comp.keys()):
            if by_comp[comp]:
                interleaved.append(by_comp[comp].pop(0))
            else:
                del by_comp[comp]
    return interleaved

def harvest_fresh(limit=500):
    applied_urls, applied_pairs = load_applied_from_sheet()
    raw_jobs = []
    
    for src in REPO_SOURCES_HTML:
        print(f"🌐 Fetching live postings from {src['name']}...", flush=True)
        try:
            req = urllib.request.Request(src["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12, context=SSL_CTX) as resp:
                text = resp.read().decode("utf-8")
                parsed = parse_html_table(text)
                print(f"  Found {len(parsed)} active table rows.", flush=True)
                raw_jobs.extend(parsed)
        except Exception as e:
            print(f"  ❌ Error fetching {src['name']}: {e}", flush=True)

    print(f"🌐 Fetching live postings from {SPEEDYAPPLY_MD['name']}...", flush=True)
    try:
        req = urllib.request.Request(SPEEDYAPPLY_MD["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12, context=SSL_CTX) as resp:
            text = resp.read().decode("utf-8")
            parsed = parse_speedyapply_table(text)
            print(f"  Found {len(parsed)} active markdown rows.", flush=True)
            raw_jobs.extend(parsed)
    except Exception as e:
        print(f"  ❌ Error fetching {SPEEDYAPPLY_MD['name']}: {e}", flush=True)

    print(f"\n🔍 Filtering and curating {len(raw_jobs)} total harvested postings for Ariq...", flush=True)
    
    fresh_gh_lever_ashby = []
    fresh_workday = []
    fresh_other = []
    seen = set()

    for j in raw_jobs:
        c = j["company"].strip()
        t = j["title"].strip()
        loc = j["location"].strip()
        u = j["url"].strip().rstrip("/")
        pair = f"{c.lower()}:::{t.lower()}"
        u_low = u.lower()

        # Deduplication against Sheet and current run
        if u_low in applied_urls or pair in applied_pairs:
            continue
        if u_low in seen or pair in seen:
            continue

        # Check candidate suitability filter
        if not is_suitable_candidate_role(t, c, loc):
            continue

        seen.add(u_low)
        seen.add(pair)

        # Assign location priority
        l_low = loc.lower()
        is_priority_loc = any(k in l_low for k in ["remote", "new york", "nyc", "new jersey", "nj", "jersey city", "princeton", "newark", "hoboken", "piscataway"])
        j["is_priority_location"] = is_priority_loc

        if "myworkdayjobs.com" in u_low or "workday" in u_low:
            j["platform"] = "workday"
            fresh_workday.append(j)
        elif "greenhouse.io" in u_low or "boards.greenhouse.io" in u_low or "job-boards.greenhouse.io" in u_low:
            j["platform"] = "greenhouse"
            fresh_gh_lever_ashby.append(j)
        elif "lever.co" in u_low or "jobs.lever.co" in u_low:
            j["platform"] = "lever"
            fresh_gh_lever_ashby.append(j)
        elif "ashbyhq.com" in u_low or "jobs.ashbyhq.com" in u_low:
            j["platform"] = "ashby"
            fresh_gh_lever_ashby.append(j)
        else:
            j["platform"] = "other"
            fresh_other.append(j)

    # Sort each list putting Priority Locations (Remote / NJ / NYC) first
    fresh_gh_lever_ashby.sort(key=lambda x: not x.get("is_priority_location", False))
    fresh_workday.sort(key=lambda x: not x.get("is_priority_location", False))

    # Interleave to prevent company pacing rate limits
    gh_priority = [j for j in fresh_gh_lever_ashby if j["platform"] == "greenhouse" and j.get("is_priority_location")]
    gh_other = [j for j in fresh_gh_lever_ashby if j["platform"] == "greenhouse" and not j.get("is_priority_location")]

    lever_priority = [j for j in fresh_gh_lever_ashby if j["platform"] == "lever" and j.get("is_priority_location")]
    lever_other = [j for j in fresh_gh_lever_ashby if j["platform"] == "lever" and not j.get("is_priority_location")]

    ashby_priority = [j for j in fresh_gh_lever_ashby if j["platform"] == "ashby" and j.get("is_priority_location")]
    ashby_other = [j for j in fresh_gh_lever_ashby if j["platform"] == "ashby" and not j.get("is_priority_location")]

    final_gh_lever_ashby = (
        round_robin_interleave(ashby_priority) +
        round_robin_interleave(lever_priority) +
        round_robin_interleave(gh_priority) +
        round_robin_interleave(ashby_other) +
        round_robin_interleave(lever_other) +
        round_robin_interleave(gh_other)
    )

    wd_priority = [j for j in fresh_workday if j.get("is_priority_location")]
    wd_other = [j for j in fresh_workday if not j.get("is_priority_location")]
    final_workday = round_robin_interleave(wd_priority) + round_robin_interleave(wd_other)

    out_gh = Path("application_engine/queue_unapplied_gh_lever_ashby.json")
    out_wd = Path("application_engine/queue_workday.json")
    out_all_suitable = Path("application_engine/suitable_unapplied_internships.json")

    with open(out_gh, "w") as f:
        json.dump(final_gh_lever_ashby, f, indent=2)

    with open(out_wd, "w") as f:
        json.dump(final_workday, f, indent=2)

    all_suitable = final_gh_lever_ashby + final_workday + fresh_other
    with open(out_all_suitable, "w") as f:
        json.dump(all_suitable, f, indent=2)

    print(f"\n🎉 Candidate-Tailored Harvester Complete!")
    print(f"  Total Suitable Unapplied Postings Found: {len(all_suitable)}")
    print(f"  📁 Saved {len(final_gh_lever_ashby)} suitable GH/Lever/Ashby targets to {out_gh}")
    print(f"     - Priority Remote/NJ/NYC: {len(ashby_priority) + len(lever_priority) + len(gh_priority)}")
    print(f"     - Other US Tech Hubs: {len(ashby_other) + len(lever_other) + len(gh_other)}")
    print(f"  📁 Saved {len(final_workday)} suitable Workday targets to {out_wd}")
    print(f"     - Priority Remote/NJ/NYC: {len(wd_priority)}")
    print(f"     - Other US Tech Hubs: {len(wd_other)}")
    print(f"  📁 Saved all {len(all_suitable)} suitable targets to {out_all_suitable}")

if __name__ == "__main__":
    harvest_fresh()
