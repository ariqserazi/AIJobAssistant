# Autonomous SWE Application Engine: Operational Handoff Guide

## 1. System Overview
- **Google Sheets Integration**: Tracks all submitted applications with strict column alignment (Col D kept blank, zero duplicates).
- **Target ATS Platforms Supported**:
  - **Greenhouse**: Full embed & hosted automation with 100% automated email OTP code retrieval.
  - **Lever**: Full form filling and demographic compliance.
  - **Ashby**: Fast tailored archetype resume upload, React toggle and dropdown binding, anti-spam delay timing.
  - **Workday**: Specialized automation helper (`apply_workday.py`) using native pointer events and LinkedIn regex formatting.

---

## 2. Candidate Ground Truth & Configuration

Candidate details are configured in `references/application_profile.md` and `config.json`:

| Category | Source | Form Handling / Dropdown Variations |
| :--- | :--- | :--- |
| **Full Name** | `config.json` | First name, last name |
| **Email** | `config.json` | Primary contact & OTP receiver |
| **Phone** | `config.json` | Formats: numeric or formatted with dashes |
| **Location** | `application_profile.md` | Candidate city, state, country |
| **Citizenship** | `application_profile.md` | Authorized for any employer |
| **Visa Sponsorship** | `application_profile.md` | No now or in the future |
| **Demographics** | `application_profile.md` | Gender, Race, Veteran, Disability |
| **Education** | `application_profile.md` | University, Degree, Graduation date, GPA |
| **Standardized Tests** | `application_profile.md` | SAT, ACT, GRE |
| **Preferred Language** | `application_profile.md` | Software Engineering discipline (e.g. Python) |
| **Free-Text Rule** | `application_profile.md` | **STRICTLY ZERO DASHES** in free-text responses |

---

## 3. Architecture & Engine Components

### A. Parallel Orchestrator (`application_engine/parallel_orchestrator.py`)
- Coordinates 5 parallel worker processes running `batch_apply_multi_ats.py`.
- Disjoint partitioning: Worker $i$ processes jobs where `index % 5 == i`.
- Zero focus stealing: runs headless Chrome without activating or raising windows.
- Command to run:
  ```bash
  python3 -u application_engine/parallel_orchestrator.py 500 path/to/queue.json
  ```

### B. Unified Multi-ATS Engine (`application_engine/batch_apply_multi_ats.py`)
- Unifies Greenhouse, Lever, and Ashby into a single high-throughput engine.
- **Fast Timeout Architecture**: Slashed dead-end timeouts from 90s to **25 seconds** (and **5 seconds** on visible form validation errors).
- **Auto-Reset Timers**: When an email verification code is retrieved and entered, timers reset allowing verification of submission confirmation.
- **Round-Robin Company Pacing**: Interleaves queues so no two consecutive roles are from the same company, preventing company rate limits.

### C. Automated Email OTP & Security Code Helper (`application_engine/email_verification_helper.py`)
- Automatically retrieves 8-character Greenhouse security codes and 6-digit Workday PINs without user prompting.
- Uses macOS ScriptingBridge or local IMAP/API to read verification codes in the background.
- Acquires `/tmp/email_otp_lock.lock` to prevent worker collisions.
- Automatically enters codes with human delays and re-submits.

### D. Google Sheets Logger (`scripts/log_application.py`)
- Reads spreadsheet ID from `config.json` (`google_sheet_id`) or environment variables (`GOOGLE_SHEET_ID`).
- Authenticates using Google Cloud Service Account credentials (`credentials.json` or ADC).
- Acquires `/tmp/gspread_sheet_lock.lock` for atomic appends.
- Caches sheet records locally in `/tmp/applied_sheet_records.json` (300s TTL) to prevent API rate limits.
- **Column D (Salary)**: Strictly kept blank `""`.

---

## 4. How to Resume Execution in a New Chat

### Step 1: Verify No Rogue Processes
```bash
ps aux | grep -E "parallel_orchestrator|batch_apply_multi_ats" | grep -v grep || echo "Clean"
```

### Step 2: Check Active Queue
Inspect your active target queue JSON file (e.g. `path/to/queue.json`).

### Step 3: Launch Parallel Engine
```bash
python3 -u application_engine/parallel_orchestrator.py 500 path/to/queue.json
```

### Step 4: Monitor Workers
```bash
for i in {0..4}; do echo "=== WORKER $i ==="; tail -n 5 scratch/parallel_logs/worker_$i.log; done
```

---

## 5. Daily Fresh Role Discovery Protocol

Whenever discovering internships or jobs:
1. **Never reuse old or stale queues**: Archive historical queues.
2. **Harvest fresh daily postings**: Run the automated discovery harvester:
   ```bash
   python3 application_engine/fetch_fresh_internships.py
   ```
3. **Automated Deduplication**: The harvester fetches live job lists, checks each role against all confirmed rows in your Google Sheet, and skips any role previously applied.
4. **Technical Discipline Filter**: Filters strictly for Software Engineering technical roles.
5. **Round-Robin Company Interleaving**: Generates target queues with company interleaving to prevent company-specific pacing blocks.
