#!/usr/bin/env python3
"""
init_setup.py - AIJobAssistant & ResumeTailor Initialization Engine
Builds all necessary local working files on a new machine or instance when personal
information is provided by a candidate or AI copilot.

Generates:
1. config.json (Local runtime candidate ground truth, strictly gitignored)
2. references/application_profile.md (Structured profile for ATS forms and EEO bubbles)
3. references/base_resume_latex.txt (Tailored base ATS resume in LaTeX)
4. references/base_resume.pdf (Compiled PDF via tectonic, if available)
5. Runtime directories (artifacts/confirmations, errors, captchas, resumes)
6. Tracking & question logs (application_tracking.md, discovered_questions_log.json)
"""

import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG_VALUES = {
    "candidate_name": "Jane Doe",
    "first_name": "Jane",
    "last_name": "Doe",
    "candidate_email": "jane.doe@example.com",
    "phone": "555-123-4567",
    "address": "123 Innovation Way",
    "city": "New York",
    "state": "New York",
    "location": "New York, New York",
    "postal_code": "10001",
    "country": "United States of America",
    "discipline": "Computer Science",
    "major": "Computer Science",
    "field_of_study": "Computer Science",
    "linkedin_url": "https://www.linkedin.com/in/janedoe/",
    "github_url": "https://github.com/janedoe",
    "portfolio_url": "https://janedoe.dev",
    "school_name": "State University",
    "school_search_term": "State",
    "degree": "Bachelor of Science in Computer Science",
    "degree_undergrad": "Bachelor of Science in Computer Science",
    "gpa": "3.85",
    "undergrad_start_year": "2022",
    "undergrad_start_month": "September",
    "undergrad_grad_year": "2026",
    "undergrad_grad_month": "May",
    "grad_start_year": "2026",
    "grad_start_month": "September",
    "grad_end_year": "2028",
    "grad_end_month": "May",
    "grad_date": "05/2026",
    "grad_month_year": "May 2026",
    "salary": "80000",
    "preferred_language": "Python",
    "current_employer": "Tech Innovations LLC",
    "current_title": "Software Engineer",
    "previous_employer": "Software Labs",
    "featured_project": "Distributed Cloud System",
    "default_resume_pdf": "",
    "transcript_pdf": "",
    "workday_password": "",
    "google_sheet_id": "",
    "google_service_account_key": "",
    "us_citizen": "Yes",
    "us_person": "Yes",
    "authorized_in_us": "Yes",
    "sponsorship_required": "No",
    "gender": "Male",
    "pronouns": "He/Him",
    "race_ethnicity": "Asian",
    "hispanic_latino": "No",
    "veteran_status": "I am not a protected veteran",
    "disability": "No, I do not have a disability",
    "responses": {
        "why": "I am deeply inspired by your team's mission and engineering standards. My background in building high-reliability software and scalable pipelines aligns directly with this role.",
        "experience": "I have engineered production microservices and REST APIs, integrating cloud tools with strict schema validation and sub-100ms response times.",
        "project": "I built a distributed real-time system utilizing modern data contracts and high-performance protocols, reducing network overhead and ensuring seamless state synchronization.",
        "clearance": "U.S. Citizen eligible for clearance.",
        "pronunciation": "",
        "relocation": "Yes, I am open to relocating and prefer standard advance notice."
    }
}


def create_directories(base_dir: Path):
    """Initializes all necessary runtime directories."""
    dirs = [
        base_dir / "references",
        base_dir / "artifacts" / "confirmations",
        base_dir / "artifacts" / "errors",
        base_dir / "artifacts" / "captchas",
        base_dir / "artifacts" / "resumes",
        base_dir / "application_engine",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def build_config_json(base_dir: Path, data: Dict[str, Any], overwrite: bool = False) -> Path:
    """Builds config.json merging inputs with safe defaults."""
    cfg_file = base_dir / "config.json"
    if cfg_file.exists() and not overwrite:
        print(f"  ℹ️ {cfg_file} already exists. Skipping overwrite (use --force to overwrite).")
        return cfg_file

    config = dict(DEFAULT_CONFIG_VALUES)
    for k, v in data.items():
        if k == "responses" and isinstance(v, dict):
            config["responses"].update(v)
        elif v:
            config[k] = v

    # Derive full name if not explicitly set
    if not data.get("candidate_name") and (data.get("first_name") or data.get("last_name")):
        fn = data.get("first_name", config["first_name"])
        ln = data.get("last_name", config["last_name"])
        config["candidate_name"] = f"{fn} {ln}".strip()

    # Ensure location matches city and state
    if not data.get("location") and (config.get("city") and config.get("state")):
        config["location"] = f"{config["city"]}, {config["state"]}"

    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"  ✅ Built config.json at {cfg_file}")
    return cfg_file


def build_application_profile(base_dir: Path, cfg: Dict[str, Any], overwrite: bool = False) -> Path:
    """Generates references/application_profile.md for ATS form bubbles and standard answers."""
    prof_file = base_dir / "references" / "application_profile.md"
    if prof_file.exists() and not overwrite:
        print(f"  ℹ️ {prof_file} already exists. Skipping overwrite.")
        return prof_file

    name = cfg.get("candidate_name", "Jane Doe")
    email = cfg.get("candidate_email", "jane.doe@example.com")
    phone = cfg.get("phone", "555-123-4567")
    loc = cfg.get("location", "New York, NY")
    linkedin = cfg.get("linkedin_url", "https://www.linkedin.com/")
    github = cfg.get("github_url", "https://github.com/")
    portfolio = cfg.get("portfolio_url", "")
    resume_path = cfg.get("default_resume_pdf", str(base_dir / "references" / "base_resume.pdf"))
    workday_pw = cfg.get("workday_password", "")
    school = cfg.get("school_name", "State University")
    degree = cfg.get("degree", "Bachelor of Science in Computer Science")
    gpa = cfg.get("gpa", "3.85")
    grad_date = cfg.get("grad_month_year", "May 2026")
    pref_lang = cfg.get("preferred_language", "Python")

    content = f"""# Application Profile

Candidate personal profile and form answer reference card.
Strictly ignored in git to preserve candidate privacy.

## Candidate Contact & Links
- **Name**: {name}
- **Email**: {email}
- **Phone**: {phone}
- **Location**: {loc}
- **LinkedIn**: {linkedin}
- **GitHub**: {github}
- **Portfolio**: {portfolio}
- **Default Resume PDF**: `{resume_path}`
- **Workday Account**: `{email}`
- **Workday Standard Password**: `{workday_pw}`
- **Workday LinkedIn URL Requirement**: `{linkedin}` (requires trailing slash)

---

## Work Authorization & Demographics (Form Bubbles / Radios)
- **Citizenship**: **United States Citizen (U.S. Citizen)**
- **Work Authorization**: Authorized to work in the United States for any employer.
- **Visa Sponsorship**: Does **not** require current or future visa sponsorship (Answer: **No** to sponsorship needed, **Yes** to legally authorized).
- **Demographics & Equal Employment Opportunity (EEO)**:
  - **Gender**: {cfg.get("gender", "Decline to self-identify")}
  - **Pronouns**: {cfg.get("pronouns", "He/Him")}
  - **Hispanic / Latino**: {cfg.get("hispanic_latino", "No")}
  - **Race / Ethnicity**: {cfg.get("race_ethnicity", "Asian")}
  - **Veteran Status**: {cfg.get("veteran_status", "I am not a protected veteran")}
  - **Disability Status**: {cfg.get("disability", "No, I do not have a disability")}
- **Job Preferences & Policies**:
  - **Preferred Programming Language**: {pref_lang}
  - **Salary Range Acceptance**: Acceptable / Yes
  - **Travel Expectations**: Willing to travel as required (Yes)
  - **Relocation Preference**: Willing to relocate (prefer at least 1 month notice)
  - **Role Priority**: Software Engineering (Backend, Full Stack, Distributed Systems, Cloud, AI/ML Infrastructure)

---

## Application Rules & Constraints
- **Punctuation in Free Text Boxes**: Never use dashes in application free-text boxes. Use periods, commas, or standard spacing.
- **Target Roles**: Early career Software Engineering roles (Backend, Full Stack, Java, Python, Cloud, AI/ML Infrastructure).

---

## Confirmed Facts & Background

### Education
- **Institution**: {school}
- **Degree**: {degree}
  - **Graduation Date**: {grad_date}
  - **GPA**: {gpa}

### Core Skills
- **Preferred / Primary Language**: {pref_lang}
- **Languages**: Python, Java, JavaScript, TypeScript, SQL, C/C++
- **Frameworks & Tools**: FastAPI, React, Node.js, Docker, PostgreSQL, AWS, Linux, Git
"""
    with open(prof_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ Built application_profile.md at {prof_file}")
    return prof_file


def build_base_resume(base_dir: Path, cfg: Dict[str, Any], compile_pdf: bool = True, overwrite: bool = False) -> Path:
    """Builds references/base_resume_latex.txt and compiles into PDF if tectonic is available."""
    latex_file = base_dir / "references" / "base_resume_latex.txt"
    sample_template = base_dir / "references" / "sample_resume_latex.txt"
    
    name = cfg.get("candidate_name", "Jane Doe")
    email = cfg.get("candidate_email", "jane.doe@example.com")
    phone = cfg.get("phone", "555-123-4567")
    linkedin = cfg.get("linkedin_url", "https://www.linkedin.com/")
    github = cfg.get("github_url", "https://github.com/")
    portfolio = cfg.get("portfolio_url", "")
    school = cfg.get("school_name", "State University")
    degree = cfg.get("degree", "Bachelor of Science in Computer Science")
    gpa = cfg.get("gpa", "3.85")
    loc = cfg.get("location", "City, State")

    clean_li = linkedin.replace("https://www.", "").replace("https://", "").rstrip("/")
    clean_gh = github.replace("https://", "").rstrip("/")
    clean_port = portfolio.replace("https://", "").rstrip("/") if portfolio else clean_gh

    if sample_template.exists():
        with open(sample_template, "r", encoding="utf-8") as f:
            t = f.read()
        t = t.replace("Jane Doe", name)
        t = t.replace("555-019-2834", phone)
        t = t.replace("jane.doe@example.com", email)
        t = t.replace("linkedin.com/in/username", clean_li)
        t = t.replace("github.com/username", clean_gh)
        t = t.replace("username.github.io", clean_port)
        t = t.replace("State University", school)
        t = t.replace("Bachelor of Science in Computer Science", degree)
        t = t.replace("3.85", gpa)
    else:
        grad_my = cfg.get("grad_month_year", "May 2026")
        t = (
            "\\documentclass[letterpaper,11pt]{article}\n"
            "\\usepackage[empty]{fullpage}\n"
            "\\usepackage{hyperref}\n"
            "\\begin{document}\n"
            "\\begin{center}\n"
            f"    \\textbf{{\\Huge {name}}} \\\\ \\vspace{{2pt}}\n"
            f"    \\small {phone} $|$ \\href{{mailto:{email}}}{{{email}}} $|$ \\href{{{linkedin}}}{{{clean_li}}} $|$ \\href{{{github}}}{{{clean_gh}}}\n"
            "\\end{center}\n"
            "\\section*{Education}\n"
            f"\\textbf{{{school}}} \\hfill {loc} \\\\\n"
            f"\\textit{{{degree}; GPA: {gpa}}} \\hfill Expected {grad_my}\n"
            "\\section*{Technical Skills}\n"
            "\\textbf{Languages:} Python, Java, JavaScript, TypeScript, SQL, C/C++ \\\\\n"
            "\\textbf{Frameworks \\& Tools:} FastAPI, React, Node.js, Docker, PostgreSQL, AWS, Linux, Git\n"
            "\\end{document}\n"
        )

    if not latex_file.exists() or overwrite:
        with open(latex_file, "w", encoding="utf-8") as f:
            f.write(t)
        print(f"  ✅ Built base_resume_latex.txt at {latex_file}")

    # Compile PDF via tectonic if requested and available
    pdf_file = base_dir / "references" / "base_resume.pdf"
    if compile_pdf and shutil.which("tectonic"):
        try:
            res = subprocess.run(["tectonic", "-o", str(base_dir / "references"), str(latex_file)],
                                 capture_output=True, text=True)
            if res.returncode == 0 and pdf_file.exists():
                print(f"  ✅ Compiled base_resume.pdf via tectonic at {pdf_file}")
                cfg_path = base_dir / "config.json"
                if cfg_path.exists():
                    with open(cfg_path, "r") as f:
                        c = json.load(f)
                    c["default_resume_pdf"] = str(pdf_file)
                    with open(cfg_path, "w") as f:
                        json.dump(c, f, indent=2)
            else:
                print(f"  ⚠️ Note: Tectonic compilation stderr: {res.stderr[:200]}")
        except Exception as e:
            print(f"  ⚠️ Note: Could not compile LaTeX via tectonic: {e}")

    return latex_file


def build_logs_and_tracking(base_dir: Path):
    """Initializes tracking markdown and question logs if not present."""
    track_file = base_dir / "references" / "application_tracking.md"
    if not track_file.exists():
        header = """# Job Application Tracker

| Date Applied | Company | Role | Location | Job Link | Resume Used | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
        with open(track_file, "w", encoding="utf-8") as f:
            f.write(header)
        print(f"  ✅ Initialized application_tracking.md at {track_file}")

    q_file = base_dir / "application_engine" / "discovered_questions_log.json"
    if not q_file.exists():
        with open(q_file, "w", encoding="utf-8") as f:
            f.write("[]\n")
        print(f"  ✅ Initialized discovered_questions_log.json at {q_file}")

    used_file = base_dir / "references" / "used_verification_codes.json"
    if not used_file.exists():
        with open(used_file, "w", encoding="utf-8") as f:
            f.write("[]\n")
        print(f"  ✅ Initialized used_verification_codes.json at {used_file}")


def run_setup(base_dir: Path, data: Dict[str, Any], overwrite: bool = False, compile_pdf: bool = True):
    """Runs complete end-to-end initialization."""
    print(f"\n🚀 Initializing AIJobAssistant in: {base_dir}")
    create_directories(base_dir)
    cfg_file = build_config_json(base_dir, data, overwrite=overwrite)
    with open(cfg_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    build_application_profile(base_dir, cfg, overwrite=overwrite)
    build_base_resume(base_dir, cfg, compile_pdf=compile_pdf, overwrite=overwrite)
    build_logs_and_tracking(base_dir)
    print("\n🎉 Initialization Complete! Your candidate profile and application engine are ready.")


def prompt_interactive() -> Dict[str, Any]:
    """Interactively prompts user in terminal for profile details."""
    print("\n👋 Welcome to AIJobAssistant Setup Wizard!")
    print("Answer these quick questions to generate your local files.\n")
    data = {}
    
    first_name = input("1. First Name [Jane]: ").strip() or "Jane"
    last_name = input("2. Last Name [Doe]: ").strip() or "Doe"
    data["first_name"] = first_name
    data["last_name"] = last_name
    data["candidate_name"] = f"{first_name} {last_name}"

    data["candidate_email"] = input("3. Email [jane.doe@example.com]: ").strip() or "jane.doe@example.com"
    data["phone"] = input("4. Phone [555-123-4567]: ").strip() or "555-123-4567"
    
    city = input("5. City [New York]: ").strip() or "New York"
    state = input("6. State [NY]: ").strip() or "NY"
    data["city"] = city
    data["state"] = state
    data["location"] = f"{city}, {state}"

    data["school_name"] = input("7. University / School [State University]: ").strip() or "State University"
    data["degree"] = input("8. Degree [Bachelor of Science in Computer Science]: ").strip() or "Bachelor of Science in Computer Science"
    data["gpa"] = input("9. GPA [3.85]: ").strip() or "3.85"
    data["grad_month_year"] = input("10. Expected Graduation [May 2026]: ").strip() or "May 2026"

    data["linkedin_url"] = input("11. LinkedIn URL [https://www.linkedin.com/]: ").strip() or "https://www.linkedin.com/"
    data["github_url"] = input("12. GitHub URL [https://github.com/]: ").strip() or "https://github.com/"
    data["workday_password"] = input("13. Workday Standard Password (optional): ").strip()
    
    auth = input("14. Are you a US Citizen / Authorized without sponsorship? (Y/n) [Y]: ").strip().lower()
    if auth in ["n", "no"]:
        data["us_citizen"] = "No"
        data["sponsorship_required"] = "Yes"
    else:
        data["us_citizen"] = "Yes"
        data["sponsorship_required"] = "No"

    return data


def main():
    parser = argparse.ArgumentParser(description="Initialize AIJobAssistant candidate profile & local files.")
    parser.add_argument("--target-dir", default=None, help="Directory to initialize (defaults to current working directory)")
    parser.add_argument("--json", dest="json_str", default=None, help="Candidate profile as JSON string")
    parser.add_argument("--file", dest="json_file", default=None, help="Path to JSON file with candidate profile")
    parser.add_argument("--interactive", action="store_true", help="Prompt user interactively in terminal")
    parser.add_argument("--force", action="store_true", help="Overwrite existing configuration files")
    parser.add_argument("--no-tectonic", action="store_true", help="Skip LaTeX tectonic compilation")
    
    args = parser.parse_args()
    target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd().resolve()

    data = {}
    if args.json_str:
        try:
            data = json.loads(args.json_str)
        except Exception as e:
            sys.exit(f"❌ Error: Invalid JSON passed to --json: {e}")
    elif args.json_file:
        try:
            with open(args.json_file, "r") as f:
                data = json.load(f)
        except Exception as e:
            sys.exit(f"❌ Error: Could not read JSON file {args.json_file}: {e}")
    elif args.interactive or sys.stdin.isatty():
        data = prompt_interactive()
    else:
        print("ℹ️ Running in automated mode with standard template defaults.")
        data = {}

    run_setup(target_dir, data, overwrite=args.force, compile_pdf=not args.no_tectonic)


if __name__ == "__main__":
    main()
