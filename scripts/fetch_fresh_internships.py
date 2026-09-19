#!/usr/bin/env python3
"""
fetch_fresh_internships.py - Daily Fresh SWE Internship & Job Harvester
Harvests strictly newly-posted (0-7 days old) early-career SWE and technical internship postings
across live tracking repositories, filters out all existing applications in Google Sheet Tracker,
enforces candidate constraints, and builds fresh, deduplicated, company-interleaved application queues.
"""

import os
import sys
import re
import json
import ssl
import time
import urllib.request
from datetime import datetime
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

# Live active sources with fresh posting tags
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
        "name": "SimplifyJobs/New-Grad-Positions",
        "url": "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
    }
]

REPO_SOURCES_MD = [
    {
        "name": "speedyapply/2026-SWE-College-Jobs",
        "url": "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/README.md",
        "type": "speedyapply"
    },
    {
        "name": "zshah101/Summer-2027-Fall-2026",
        "url": "https://raw.githubusercontent.com/zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships/main/README.md",
        "type": "zshah101"
    }
]

REFERENCE_DATE = datetime(2026, 9, 19)

def parse_age(s):
    s = str(s).strip().lower()
    if not s:
        return 999
    if "just now" in s or "today" in s or s == "0d":
        return 0
    if "yesterday" in s or s == "1d":
        return 1
    m_d = re.search(r"^(\d+)\s*d", s)
    if m_d:
        return int(m_d.group(1))
    m_h = re.search(r"^(\d+)\s*h", s)
    if m_h:
        return 0
    m_w = re.search(r"^(\d+)\s*w", s)
    if m_w:
        return int(m_w.group(1)) * 7
    m_m = re.search(r"^(\d+)\s*m", s)
    if m_m:
        return int(m_m.group(1)) * 30
    return 999

def parse_date_string(s, ref_date=REFERENCE_DATE):
    s = str(s).strip()
    if not s:
        return 999
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            delta = (ref_date - dt).days
            return max(0, delta)
        except ValueError:
            pass
    for fmt in ("%b %d", "%B %d"):
        try:
            dt = datetime.strptime(s, fmt).replace(year=2026)
            delta = (ref_date - dt).days
            return max(0, delta)
        except ValueError:
            pass
    return 999

def load_applied_from_sheet():
    print("📊 Fetching applied records from Google Sheet Tracker...", flush=True)
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
            if c and role_val and c != "company":
                applied_pairs.add(f"{c}:::{role_val}")
            if u:
                applied_urls.add(u)
        print(f"  ✅ Loaded {len(applied_urls)} applied URLs and {len(applied_pairs)} applied pairs (Total Sheet Rows: {len(rows)}).", flush=True)
    except Exception as e:
        print(f"  ⚠️ Warning fetching sheet records: {e}", flush=True)
    return applied_urls, applied_pairs

def is_suitable_candidate_role(title, comp, loc):
    t = title.lower()
    c = comp.lower()
    l = loc.lower()

    if not any(k in t for k in ["intern", "co-op", "coop", "fellow"]):
        return False

    unwanted_seniority = [
        "senior", "staff", "principal", "lead", "manager", "director", "architect",
        "head of", "yoe", "years of experience", "3+ years", "4+ years", "5+ years",
        "doctoral", "postdoc"
    ]
    if any(k in t for k in unwanted_seniority):
        return False

    if "phd" in t and not any(k in t for k in ["undergrad", "ms", "master", "bs"]):
        return False

    unwanted_disciplines = [
        "electrical engineer", "hardware engineer", "mechanical", "chemical", "materials",
        "optical", "rf engineer", "propulsion", "aerospace", "civil engineer", "battery",
        "manufacturing engineer", "structural engineer"
    ]
    if any(k in t for k in unwanted_disciplines):
        return False

    unwanted_nontech = [
        "aml", "investigator", "compliance", "legal", "recruiter", "recruiting", "talent",
        "sales", "marketing", "account executive", "financial analyst", "tax intern",
        "audit intern", "graphic design", "conversation designer", "content designer",
        "trader", "trading intern", "equity trader", "quant trader", "broker"
    ]
    if any(k in t for k in unwanted_nontech):
        return False

    tech_matches = [
        "software", "swe", "sde", "developer", "backend", "front", "full stack", "fullstack",
        "systems", "cloud", "devops", "infrastructure", "platform", "distributed",
        "data engineer", "machine learning", "applied ai", "ai engineer", "mobile", "android", "ios",
        "security engineer", "application security", "information technology", "qa engineer",
        "test engineer", "automation", "product manager", "pm intern"
    ]
    if not any(k in t for k in tech_matches):
        return False

    FOREIGN_REGEX = re.compile(
        r"\b(canada|ontario|toronto|vancouver|montreal|quebec|waterloo|ottawa|markham|calgary|edmonton|"
        r"alberta|british columbia|united kingdom|london|england|uk|great britain|germany|berlin|munich|"
        r"frankfurt|india|bangalore|bengaluru|hyderabad|pune|gurgaon|noida|chennai|mumbai|singapore|"
        r"australia|sydney|melbourne|france|paris|netherlands|amsterdam|poland|warsaw|krakow|switzerland|"
        r"zurich|japan|tokyo|taiwan|ireland|dublin|brazil|mexico|israel|china|spain|sweden|norway|finland|"
        r"denmark|italy|austria|new zealand|korea)\b",
        re.IGNORECASE
    )
    if FOREIGN_REGEX.search(l):
        us_match = re.search(r"\b(usa|united states|us|remote|ny|new york|nyc|nj|new jersey|ca|tx|wa|ma|il|va|co|ga|nc|fl)\b", l, re.IGNORECASE)
        if not us_match or ("canada" in l and not any(k in l for k in ["usa", "united states", "new york", "ny", "new jersey", "nj"])):
            return False

    US_INDICATORS = re.compile(
        r"\b(usa|united states|remote|virtual|telecommute|new york|nyc|ny|new jersey|nj|jersey city|princeton|"
        r"newark|hoboken|piscataway|california|ca|san francisco|sf|bay area|los angeles|la|san diego|seattle|"
        r"washington|wa|austin|texas|tx|dallas|boston|massachusetts|ma|chicago|illinois|il|virginia|va|colorado|"
        r"co|denver|boulder|georgia|ga|atlanta|north carolina|nc|raleigh|durham|florida|fl|pennsylvania|pa|"
        r"philadelphia|pittsburgh|ohio|oh|michigan|mi|arizona|az|utah|ut|indiana|in|minnesota|mn|missouri|mo|"
        r"tennessee|tn|district of columbia|dc)\b",
        re.IGNORECASE
    )
    if not US_INDICATORS.search(l):
        return False

    return True

def parse_html_table(text):
    postings = []
    last_comp = "Unknown"
    for r in text.split("<tr>"):
        if "<td>" not in r:
            continue
        if "🔒" in r or "closed" in r.lower():
            continue
        tds = re.findall(r"<td[^>]*>(.*?)</td>", r, re.DOTALL)
        if len(tds) >= 4:
            raw_comp = re.sub(r"<[^>]+>", "", tds[0]).replace("🔥", "").strip()
            if raw_comp and "↳" not in raw_comp:
                last_comp = raw_comp
            comp = last_comp

            role = re.sub(r"<[^>]+>", "", tds[1]).replace("🔥", "").strip()
            loc = re.sub(r"<[^>]+>", "", tds[2]).strip()
            href_m = re.search(r'href=[\'"]([^\'"]+)[\'"]', tds[3])
            age_str = re.sub(r"<[^>]+>", "", tds[4]).strip() if len(tds) >= 5 else ""
            age_days = parse_age(age_str)

            if href_m and role:
                u = href_m.group(1).strip().split("?utm_source=")[0].split("&utm_source=")[0].split("?ref=")[0].strip()
                if u.startswith("http"):
                    postings.append({
                        "company": comp,
                        "title": role,
                        "role": role,
                        "location": loc,
                        "url": u,
                        "age_days": age_days,
                        "age_str": age_str
                    })
    return postings

def parse_speedyapply_table(text):
    postings = []
    for line in text.splitlines():
        if not line.startswith("|") or "🔒" in line or "closed" in line.lower():
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 5:
            comp = re.sub(r"<[^>]+>", "", parts[0]).replace("🔥", "").strip()
            role = parts[1].replace("🔥", "").strip()
            loc = parts[2].strip()
            href_m = re.search(r'href=[\'"]([^\'"]+)[\'"]', parts[4])
            age_str = parts[5].strip() if len(parts) >= 6 else ""
            age_days = parse_age(age_str)
            if href_m and comp and role and "Company" not in comp and "---" not in comp:
                u = href_m.group(1).strip().split("?utm_source=")[0].split("&utm_source=")[0].split("?ref=")[0].strip()
                if u.startswith("http"):
                    postings.append({
                        "company": comp,
                        "title": role,
                        "role": role,
                        "location": loc,
                        "url": u,
                        "age_days": age_days,
                        "age_str": age_str
                    })
    return postings

def parse_zshah101_table(text):
    postings = []
    for line in text.splitlines():
        if not line.startswith("|") or "🔒" in line or "closed" in line.lower():
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 4:
            comp = re.sub(r"<[^>]+>", "", parts[0]).replace("🔥", "").replace("🆁", "").replace("✓", "").strip()
            is_new = "🆕" in parts[1]
            role = parts[1].replace("🔥", "").replace("🆕", "").replace("🛂", "").replace("🇺🇸", "").strip()
            href_m = re.search(r"\[Apply\]\(([^\)]+)\)", parts[2] if len(parts) > 2 else "")
            loc = parts[3] if len(parts) > 3 else ""
            age_days = 1 if is_new else 999
            age_str = "1d" if is_new else ""
            if len(parts) >= 6 and parts[5]:
                parsed_days = parse_date_string(parts[5])
                if parsed_days != 999:
                    age_days = parsed_days
                    age_str = f"{age_days}d"
            if href_m and comp and role and "Company" not in comp and "---" not in comp:
                u = href_m.group(1).strip().split("?utm_source=")[0].split("&utm_source=")[0].split("?ref=")[0].strip()
                if u.startswith("http"):
                    postings.append({
                        "company": comp,
                        "title": role,
                        "role": role,
                        "location": loc,
                        "url": u,
                        "age_days": age_days,
                        "age_str": age_str
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

def harvest_fresh(max_age_days=7):
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

    for src in REPO_SOURCES_MD:
        print(f"🌐 Fetching live postings from {src['name']}...", flush=True)
        try:
            req = urllib.request.Request(src["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12, context=SSL_CTX) as resp:
                text = resp.read().decode("utf-8")
                t = src.get("type", "")
                if t == "speedyapply":
                    parsed = parse_speedyapply_table(text)
                elif t == "zshah101":
                    parsed = parse_zshah101_table(text)
                else:
                    parsed = parse_speedyapply_table(text)
                print(f"  Found {len(parsed)} active markdown rows.", flush=True)
                raw_jobs.extend(parsed)
        except Exception as e:
            print(f"  ❌ Error fetching {src['name']}: {e}", flush=True)

    print(f"\n🔍 Filtering {len(raw_jobs)} harvested postings for candidate (strictly <= {max_age_days} days old)...", flush=True)
    
    fresh_gh = []
    fresh_lever = []
    fresh_ashby = []
    fresh_workday = []
    fresh_other = []
    seen = set()

    filtered_age_count = 0
    filtered_applied_count = 0
    filtered_role_count = 0

    for j in raw_jobs:
        c = j["company"].strip()
        t = j["title"].strip()
        loc = j["location"].strip()
        u = j["url"].strip().rstrip("/")
        age_days = j.get("age_days", 999)
        pair = f"{c.lower()}:::{t.lower()}"
        u_low = u.lower()

        if age_days > max_age_days:
            filtered_age_count += 1
            continue

        if u_low in applied_urls or pair in applied_pairs:
            filtered_applied_count += 1
            continue
        if u_low in seen or pair in seen:
            continue

        if not is_suitable_candidate_role(t, c, loc):
            filtered_role_count += 1
            continue

        seen.add(u_low)
        seen.add(pair)

        l_low = loc.lower()
        is_priority_loc = any(k in l_low for k in [
            "remote", "new york", "nyc", "new jersey", "nj", "jersey city",
            "princeton", "newark", "hoboken", "piscataway"
        ])
        j["is_priority_location"] = is_priority_loc

        gh_match = re.search(r"gh_jid=([0-9]+)", u_low)
        if gh_match:
            gh_token = gh_match.group(1)
            j["url"] = f"https://boards.greenhouse.io/embed/job_app?token={gh_token}"
            j["platform"] = "greenhouse"
            fresh_gh.append(j)
        elif "greenhouse.io" in u_low or "boards.greenhouse.io" in u_low or "job-boards.greenhouse.io" in u_low:
            j["platform"] = "greenhouse"
            fresh_gh.append(j)
        elif "lever.co" in u_low or "jobs.lever.co" in u_low:
            j["platform"] = "lever"
            fresh_lever.append(j)
        elif "myworkdayjobs.com" in u_low or "workday" in u_low:
            j["platform"] = "workday"
            fresh_workday.append(j)
        elif "ashbyhq.com" in u_low or "jobs.ashbyhq.com" in u_low:
            j["platform"] = "ashby"
            fresh_ashby.append(j)
        else:
            j["platform"] = "other"
            fresh_other.append(j)

    print(f"  Discarded {filtered_age_count} listings older than {max_age_days} days.")
    print(f"  Filtered out {filtered_applied_count} already-applied roles and {filtered_role_count} unsuitable roles.")

    def sort_key(x):
        return (x.get("age_days", 99), not x.get("is_priority_location", False))

    fresh_gh.sort(key=sort_key)
    fresh_lever.sort(key=sort_key)
    fresh_ashby.sort(key=sort_key)
    fresh_workday.sort(key=sort_key)

    final_gh_lever_ashby = (
        round_robin_interleave([j for j in fresh_gh if j.get("is_priority_location")]) +
        round_robin_interleave([j for j in fresh_gh if not j.get("is_priority_location")]) +
        round_robin_interleave([j for j in fresh_lever if j.get("is_priority_location")]) +
        round_robin_interleave([j for j in fresh_lever if not j.get("is_priority_location")]) +
        round_robin_interleave([j for j in fresh_ashby if j.get("is_priority_location")]) +
        round_robin_interleave([j for j in fresh_ashby if not j.get("is_priority_location")])
    )

    final_workday = (
        round_robin_interleave([j for j in fresh_workday if j.get("is_priority_location")]) +
        round_robin_interleave([j for j in fresh_workday if not j.get("is_priority_location")])
    )

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
    print(f"  Total Fresh (<= {max_age_days}d) Unapplied Postings Found: {len(all_suitable)}")
    print(f"  📁 Saved {len(final_gh_lever_ashby)} fresh GH/Lever/Ashby targets to {out_gh}")
    print(f"     - Greenhouse: {len(fresh_gh)} (Freshness: 0d-7d)")
    print(f"     - Lever: {len(fresh_lever)} (Freshness: 0d-7d)")
    print(f"     - Ashby: {len(fresh_ashby)} (Freshness: 0d-7d)")
    print(f"  📁 Saved {len(final_workday)} fresh Workday targets to {out_wd}")
    print(f"     - Workday: {len(fresh_workday)} (Freshness: 0d-7d)")
    print(f"  📁 Saved all {len(all_suitable)} suitable targets to {out_all_suitable}")

if __name__ == "__main__":
    max_days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    harvest_fresh(max_days)
