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

### Step 3: Automatically Build Your Candidate Profile

Run the automated setup wizard to generate all local files needed by the application engines:

```bash
python init_setup.py
```

The interactive wizard asks a few simple questions in your terminal and automatically builds:
1. **`config.json`**: Ground truth for application form fillers, auth, and credentials.
2. **`references/application_profile.md`**: Form bubble reference card, demographics, and compliance preferences.
3. **`references/base_resume_latex.txt` & PDF**: Baseline ATS single-column LaTeX resume compiled into a ready-to-attach PDF.
4. **Runtime directories & tracking logs**: Pre-creates tracking folders and empty application logs.

> [!TIP]
> **Using an AI Agent (Antigravity, Cursor, Claude Code, etc.)?**
> You can simply ask your AI agent in chat:
> *"Help me set up AIJobAssistant for my job search"*
> The agent will prompt you for your details and run `init_setup.py` programmatically to build all necessary files in seconds!

> [!NOTE]
> `config.json`, `application_profile.md`, and custom resumes are automatically gitignored so your personal information and credentials will **never** be committed or exposed to GitHub.

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
