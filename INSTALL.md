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

### Step 3: Automatically Build Your Profile (From Your Resume PDF)

You don't need to manually configure anything! Simply point the setup engine to your existing resume PDF:

```bash
python init_setup.py --resume-pdf /path/to/your/resume.pdf
```

The engine automatically parses your resume PDF and extracts:
- **Contact**: Full Name, Email, Phone, and City/State location.
- **Education**: University, Degree, Major, GPA, and Graduation Date.
- **Links**: LinkedIn, GitHub, and Portfolio URLs.
- **Technical Focus**: Primary programming language and core skills.

From that single PDF, it automatically builds:
1. **`config.json`**: Populated with your details and pointing directly to your resume PDF.
2. **`references/application_profile.md`**: Pre-filled with your confirmed facts and ATS bubble preferences.
3. **`references/base_resume_latex.txt`**: Tailored baseline ATS resume.
4. **Runtime directories & tracking logs**: Ready for immediate application submissions.

> [!TIP]
> **Using an AI Agent (Antigravity, Cursor, Claude Code, etc.)?**
> You can simply drop your resume PDF into chat or ask your agent:
> *"Here is my resume: `path/to/resume.pdf` — please set up my job search profile"*
> The agent will parse your resume and build all necessary files on your machine in seconds!

> [!NOTE]
> `config.json`, `application_profile.md`, and personal resumes are strictly gitignored so your personal information and credentials will **never** be committed or exposed to GitHub.

---

### Step 4: Choose Your AI Form Reasoner (Ollama vs. Current AI Chat)

When applying to jobs on ATS platforms, applications frequently present custom, non-standard, or behavioral questions (e.g., *"Why do you want to work at our company?"*, *"Describe a technical challenge you overcame"*, or ambiguous multi-select checkboxes). An **AI Form Reasoner** reads your candidate profile and dynamically generates tailored, compliant answers with zero manual intervention.

You have two options:

#### Option 1: Ollama Local AI (Recommended — 0 Credit Cost)
* **What it does**: Runs a local reasoning model (`qwen3:4b-instruct`) directly on your machine.
* **Why choose it**: **100% Free** — consumes **0 credits or tokens** from your AI chat assistant, enabling unlimited automated applications.
* **Setup**: Run setup with `--setup-ollama` (or choose Option 1 in interactive mode):
  ```bash
  python init_setup.py --setup-ollama
  ```
  The setup script automatically checks your OS, installs Ollama dependencies (macOS Homebrew, Linux curl, Windows winget), starts the service, and pulls the model for you.

#### Option 2: Current AI Chat Assistant (No Extra Downloads)
* **What it does**: Routes reasoning through your active AI chat assistant (Antigravity / Claude / Gemini).
* **Why choose it**: No extra background services or 2.5 GB models to download.
* **Setup**:
  ```bash
  python init_setup.py --chat-llm
  ```

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
