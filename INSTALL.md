# AIJobAssistant & ResumeTailor Installation Guide

Welcome! This repository provides an end-to-end automated job application and resume tailoring engine supporting **Ashby**, **Greenhouse**, **Lever**, and **Workday** with multi-worker parallel execution, automated email OTP/verification retrieval, and LaTeX resume tailoring.

---

## 🚀 Quickstart in 4 Simple Steps

### Step 1: Clone the Repository
```bash
git clone https://github.com/ariqserazi/AIJobAssistant.git
cd AIJobAssistant
```

### Step 2: Install Python Dependencies & Playwright
```bash
pip install -r requirements.txt
playwright install chromium
```

*(Optional: If you want automatic LaTeX resume compilation into PDF, install Tectonic)*:
- **macOS**: `brew install tectonic`
- **Linux**: `curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.tectonic-typesetting.net | sh`
- **Windows**: `winget install tectonic`

---

### Step 3: Configure Your Profile

> [!TIP]
> **Using an AI Agent (Antigravity, Cursor, Claude Code, etc.)?**
> You don't even need to edit `config.json` manually! Simply ask your agent:
> *"Help me set up AIJobAssistant for my job search"*
> The agent will automatically ask you 5 quick questions in chat and generate your `config.json` for you!


Copy the template configuration file to `config.json`:
```bash
cp config.example.json config.json
```

Open `config.json` in your favorite editor and enter your details:
- **Candidate Info**: Name, email, phone number, address, location.
- **Education**: School name, degree, GPA, start date, projected graduation.
- **Links**: LinkedIn, GitHub, Portfolio website.
- **Demographics & Work Authorization**: US citizenship, visa sponsorship requirements, EEO preferences.
- **Workday Credentials**: Your standard password for Workday application portals.
- **Google Sheets (Optional)**: If you want to automatically log applications to a Google Sheet, add your `google_sheet_id` and service account keyfile path.

> [!NOTE]
> `config.json` is automatically gitignored so your personal information and credentials will **never** be committed or exposed to GitHub.

---

### Step 4: Add Your Resume

Place your baseline PDF resume in `references/sample_resume.pdf` (or specify an absolute path to your resume in `config.json` under `"default_resume_pdf"`).

---

## 🏃 Running the Application Engines

### 1. Parallel Multi-ATS Engine (Greenhouse, Lever, Ashby)
Run up to 5 concurrent workers:
```bash
python application_engine/parallel_orchestrator.py 50 application_engine/queue_unapplied_gh_lever_ashby.json
```

### 2. Single-Worker Unified Multi-ATS Runner
```bash
python application_engine/batch_apply_multi_ats.py your_target_jobs.json
```

### 3. Workday Batch Engine
```bash
python application_engine/batch_apply_workday.py application_engine/queue_workday.json
```

### 4. Harvest Fresh Daily Internships
Scrapes active GitHub repositories (SimplifyJobs, Pitt CSC) for new software engineering roles:
```bash
python application_engine/fetch_fresh_internships.py
```

---

## 🤖 Installing as an Antigravity / AI Agent Skill

If you use Google Antigravity or compatible AI coding agents, you can install this engine as an autonomous agent skill:

```bash
mkdir -p ~/.agents/skills/
cp -r skills/resume-tailor-swe ~/.agents/skills/
```

Whenever you give your agent a job link or application request, it will automatically invoke the `$resume-tailor-swe` skill, customize your resume according to strict ATS impact guidelines, fill out the application form, handle email verification codes, and verify employer confirmation!
