# Autonomous SWE Application Engine: Operational Handoff Guide

## 1. System Overview & Current Milestone
- **Total Logged Applications in Google Sheet**: **678** (Contiguous, Col D blank, zero duplicates).
- **Session Progress (9/13/2026)**: **138 verified submissions** completed in a single session.
- **Google Sheet ID**: `1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY` | Worksheet: `Sheet1`.
- **Target ATS Platforms Supported**:
  - **Greenhouse**: Full embed & hosted automation with 100% automated email OTP code retrieval.
  - **Lever**: Full form filling and demographic compliance.
  - **Ashby**: Fast tailored archetype resume upload, React toggle and dropdown binding, anti-spam delay timing.
  - **Workday**: Specialized automation helper (`apply_workday.py`) using native pointer events and LinkedIn regex formatting.

---

## 2. Candidate Ground Truth & Strict Disclosures

| Category | Canonical Truth | Form Handling / Dropdown Variations |
| :--- | :--- | :--- |
| **Full Name** | Ariq Serazi | First: `Ariq`, Last: `Serazi` |
| **Email** | `ariq.serazi1@gmail.com` | Primary contact & OTP receiver |
| **Phone** | `732-853-6773` | Formats: `7328536773`, `(732) 853-6773` |
| **Location** | Piscataway, New Jersey | Select: `Piscataway, NJ` or `New Jersey` |
| **Citizenship** | United States Citizen | Yes / Permanent US Resident / Authorized for any employer |
| **Visa Sponsorship** | None (No) | No now or in the future |
| **Gender / Pronouns** | Male / Man / Cis-man | Pronouns: `He / Him` |
| **Race / Ethnicity** | Asian (South Asian / Bangladeshi) | Asian / South Asian / Asian Indian |
| **Veteran Status** | Not a protected veteran | I am not a protected veteran / No |
| **Disability Status** | No disability | "No, I do not have a disability and have not had one in the past" |
| **Undergrad Degree** | Rutgers University - New Brunswick | BS Computer Science, May 2024 (Summa Cum Laude, GPA 3.86) |
| **Graduate Degree** | Rutgers University - New Brunswick | MS Computer Science, Projected May 2028 (Currently enrolled / Masters) |
| **Graduation Range** | Projected May 2028 | Matches `2028`, `Spring 2028`, `Jan - April 2028`, `2027 & later` |
| **University Restrictions** | Strictly Rutgers | If asked "Are you enrolled at Northeastern / Columbia / NYU / etc.?", strictly answer **NO** |
| **Standardized Tests** | SAT: **1280** | Matches `1280`, `1201 - 1300`. Never select `< 1200`. ACT: **Did not take** / N/A. GRE: **Did not take** / N/A. |
| **High School Grad** | 2020 / Before 2021 | Matches `2020` or `Before 2021` |
| **Preferred Language** | Python | Software Engineering discipline strictly set to Computer Science |
| **Free-Text Rule** | **STRICTLY ZERO DASHES** | Never use hyphens (`-`, `–`, `—`) in free-text responses |

---

## 3. Architecture & Engine Components

### A. Parallel Orchestrator (`application_engine/parallel_orchestrator.py`)
- Coordinates 5 parallel worker processes running `batch_apply_multi_ats.py`.
- Disjoint partitioning: Worker $i$ processes jobs where `index % 5 == i`.
- Zero focus stealing: runs headless Chrome without activating or raising windows.
- Command to run:
  ```bash
  python3 -u application_engine/parallel_orchestrator.py 655 application_engine/queue_unapplied_gh_lever_ashby.json
  ```

### B. Unified Multi-ATS Engine (`application_engine/batch_apply_multi_ats.py`)
- Unifies Greenhouse, Lever, and Ashby into a single high-throughput engine.
- **Fast Timeout Architecture**: Slashed dead-end timeouts from 90s to **25 seconds** (and **5 seconds** on visible form validation errors).
- **Auto-Reset Timers**: When an email verification code is retrieved and entered, `start_wait` resets to `time.time()`, allowing 30s to verify submission confirmation.
- **Round-Robin Company Pacing**: The queue is interleaved so no two consecutive roles are from the same company, preventing company rate limits.

### C. Automated Email OTP & Security Code Helper (`application_engine/email_verification_helper.py`)
- Automatically retrieves 8-character Greenhouse security codes (e.g. `X0wItQbW`, `sIZClaF6`) and 6-digit Workday PINs without ever prompting the user.
- Uses macOS PyObjC ScriptingBridge (`SBApplication.applicationWithBundleIdentifier_("com.google.Chrome")`) to read Gmail silently in the background without activating Chrome or stealing focus.
- **Critical DOM Navigation**: Checks if the Gmail tab is trapped in an open email thread (`#inbox/FMfcgz...`). If so, automatically clicks `a[href*='#inbox']` to return to the inbox list view so rows (`.zA`) are queryable.
- Concurrency protection: acquires `/tmp/email_otp_lock.lock` using `fcntl.flock` to prevent worker collisions.
- Automatically enters the code into `#security-input-0` through `#security-input-7` with human delays and re-clicks submit.

### D. Google Sheets Logger (`~/.agents/skills/resume-tailor-swe/scripts/log_application.py`)
- Service account: `~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json`.
- Concurrency protection: acquires `/tmp/gspread_sheet_lock.lock` via `fcntl.flock`.
- Caching: Sheet records are cached locally in `/tmp/applied_sheet_records.json` (valid for 300s) to prevent Google Sheets API rate-limiting during worker startup.
- **Column D (Salary)**: Strictly kept blank `""`.
- Deduplication: checks normalized `(company, role)` and exact URL before appending.

---

## 4. Current Target Queues

1. **`application_engine/queue_unapplied_gh_lever_ashby.json`**:
   - 655 clean, deduplicated, unapplied jobs.
   - Interleaved by company: Greenhouse (307) and Lever (45) prioritized first, followed by Ashby (303).
2. **`application_engine/queue_workday.json`**:
   - 184 curated Workday jobs.
   - Standard credentials: `ariq.serazi1@gmail.com` | `AriqWorkday2026!#`.
3. **`application_engine/target_jobs.json`**:
   - Master repository of scraped sweet-spot SWE internship postings.

---

## 5. How to Resume Execution in a New Chat

### Step 1: Verify No Rogue Processes
```bash
ps aux | grep -E "parallel_orchestrator|batch_apply_multi_ats" | grep -v grep || echo "Clean"
```

### Step 2: Check Current Sheet Count
```bash
python3 -c "
import gspread, os
gc = gspread.service_account(os.path.expanduser('~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json'))
sh = gc.open_by_key('1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY')
print('Current total rows:', len([r for r in sh.sheet1.get_all_values() if r and r[0].strip()]))
"
```

### Step 3: Launch Parallel Engine
```bash
python3 -u application_engine/parallel_orchestrator.py 655 application_engine/queue_unapplied_gh_lever_ashby.json
```

### Step 4: Monitor Workers
```bash
for i in {0..4}; do echo "=== WORKER $i ==="; tail -n 5 scratch/parallel_logs/worker_$i.log; done
```

---

## 6. Daily Fresh Role Discovery Protocol

Whenever Ariq requests to find internships or jobs:
1. **Never reuse old or stale queues**: All completed/historical queues are safely archived in `application_engine/queue_archive_2026_09_13/`.
2. **Harvest fresh daily postings**: Run the automated discovery harvester:
   ```bash
   python3 application_engine/fetch_fresh_internships.py
   ```
3. **Automated Deduplication**: The harvester fetches live markdown tables from SimplifyJobs (Summer 2027, Summer 2026, New Grad) and Pitt CSC, checks each role against all 678+ confirmed rows in Google Sheet `1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY`, and skips any role previously applied (by both URL and normalized company/title).
4. **Technical Discipline Filter**: Filters strictly for Computer Science / Software Engineering technical roles (Backend, Full Stack, Distributed Systems, Cloud, AI/ML Infrastructure, Systems, Data).
5. **Round-Robin Company Interleaving**: Auto-generates `queue_unapplied_gh_lever_ashby.json` with company interleaving so no two adjacent jobs belong to the same company, preventing company-specific pacing blocks.
