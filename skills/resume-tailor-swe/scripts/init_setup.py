#!/usr/bin/env python3
"""
init_setup.py - AIJobAssistant & ResumeTailor Initialization Engine
Builds all necessary local working files on a new machine or instance when personal
information is provided by a candidate, a resume PDF, or an AI copilot.

Supported Input Modes:
1. Resume PDF: python init_setup.py --resume-pdf /path/to/resume.pdf
   Automatically extracts candidate name, email, phone, location, links, school,
   degree, GPA, graduation date, and skills directly from the PDF!
2. Programmatic JSON: python init_setup.py --json '{"first_name": ...}'
3. Interactive Wizard: python init_setup.py

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
import re
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

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


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts plain text from a PDF using macOS Quartz PDFKit, pypdf, or CLI tools."""
    p = Path(pdf_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Resume PDF not found at: {p}")

    # Method 1: macOS native Quartz.PDFKit (zero dependencies on macOS)
    try:
        from Foundation import NSURL
        import Quartz.PDFKit as PDFKit
        url = NSURL.fileURLWithPath_(str(p))
        doc = PDFKit.PDFDocument.alloc().initWithURL_(url)
        if doc:
            txt = doc.string()
            if txt and len(txt.strip()) > 30:
                return txt
    except Exception:
        pass

    # Method 2: pypdf / pypdf2 if installed
    try:
        import pypdf
        reader = pypdf.PdfReader(str(p))
        txt = "".join([page.extract_text() or "" for page in reader.pages])
        if txt and len(txt.strip()) > 30:
            return txt
    except Exception:
        pass

    # Method 3: pdfplumber if installed
    try:
        import pdfplumber
        with pdfplumber.open(str(p)) as pdf:
            txt = "".join([page.extract_text() or "" for page in pdf.pages])
            if txt and len(txt.strip()) > 30:
                return txt
    except Exception:
        pass

    # Method 4: pdftotext CLI
    try:
        res = subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True)
        if res.returncode == 0 and len(res.stdout.strip()) > 30:
            return res.stdout
    except Exception:
        pass

    raise RuntimeError(f"Could not extract text from {p}. Ensure the PDF is not an image-only scan.")


def parse_resume_data(text: str, pdf_path: str) -> Dict[str, Any]:
    """Parses candidate profile fields directly from extracted resume text."""
    data = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 1. Full Name (from the top header lines)
    candidate_name = ""
    for l in lines[:6]:
        clean = re.sub(r'[^a-zA-Z\s]', '', l).strip()
        words = clean.split()
        if 2 <= len(words) <= 4 and not any(w.lower() in ["resume", "curriculum", "vitae", "cv", "page", "email", "phone", "contact"] for w in words):
            candidate_name = clean
            break
    if not candidate_name and lines:
        candidate_name = lines[0]
    
    parts = candidate_name.split()
    first_name = parts[0] if parts else "Jane"
    last_name = " ".join(parts[1:]) if len(parts) > 1 else "Doe"
    data["candidate_name"] = candidate_name
    data["first_name"] = first_name
    data["last_name"] = last_name

    # 2. Email Address
    email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    if email_match:
        data["candidate_email"] = email_match.group(0).strip()

    # 3. Phone Number
    phone_match = re.search(r'(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})', text)
    if phone_match:
        data["phone"] = phone_match.group(0).strip()

    # 4. Location (City, State)
    loc_match = re.search(r'([A-Z][a-zA-Z\s]+),\s*([A-Z]{2})', text)
    if loc_match:
        data["city"] = loc_match.group(1).strip()
        data["state"] = loc_match.group(2).strip()
        data["location"] = f"{data['city']}, {data['state']}"

    # 5. LinkedIn URL
    li_match = re.search(r'(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_-]+)/?', text, re.IGNORECASE)
    if li_match:
        data["linkedin_url"] = f"https://www.linkedin.com/in/{li_match.group(1)}/"

    # 6. GitHub URL
    gh_match = re.search(r'(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_-]+)/?', text, re.IGNORECASE)
    if gh_match:
        data["github_url"] = f"https://github.com/{gh_match.group(1)}"

    # 7. Portfolio URL
    port_match = re.search(r'(?:https?://)?([a-zA-Z0-9_-]+\.github\.io|[a-zA-Z0-9_-]+\.(?:dev|me|io|tech))/?', text, re.IGNORECASE)
    if port_match and not any(k in port_match.group(1) for k in ["linkedin", "github", "google", "gmail"]):
        data["portfolio_url"] = f"https://{port_match.group(1)}"

    # 8. Education: University / School Name
    for l in lines:
        if any(k in l.lower() for k in ["university", "college", "institute of technology", "polytechnic"]) and not any(k in l.lower() for k in ["software", "intern", "engineer", "club"]):
            s = re.split(r'–|-|\||	', l)[0].strip()
            s = re.sub(r'\s+[A-Z][a-zA-Z\s]+,\s*[A-Z]{2}$', '', s).strip()
            data["school_name"] = s
            data["school_search_term"] = s.split()[0] if s else ""
            break

    # 9. Degree & Major
    for l in lines:
        if any(k in l.lower() for k in ["bachelor", "master", "ph.d", "bs in", "b.s.", "ms in", "m.s."]):
            deg = re.split(r';|–|-|\||	', l)[0].strip()
            data["degree"] = deg
            data["degree_undergrad"] = deg
            break

    # 10. GPA
    gpa_match = re.search(r'GPA:?\s*([0-4]\.\d{1,2})', text, re.IGNORECASE)
    if gpa_match:
        data["gpa"] = gpa_match.group(1)

    # 11. Graduation Date
    grad_match = re.search(r'(?:Expected|Graduation|Class of)?\s*(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Spring|Summer|Fall|Winter)?\s*(202[4-9]|203[0-5])', text, re.IGNORECASE)
    if grad_match:
        m = grad_match.group(1) or "May"
        y = grad_match.group(2)
        data["grad_month_year"] = f"{m.capitalize()} {y}"
        data["undergrad_grad_year"] = y

    # 12. Preferred Programming Language
    lang_counts = {}
    for lang in ["Python", "Java", "C++", "JavaScript", "TypeScript", "Go", "Rust", "C#", "Swift", "Kotlin"]:
        cnt = len(re.findall(r'' + re.escape(lang) + r'', text, re.IGNORECASE))
        if cnt > 0:
            lang_counts[lang] = cnt
    if lang_counts:
        data["preferred_language"] = max(lang_counts, key=lang_counts.get)

    # 13. Default Resume PDF Path
    data["default_resume_pdf"] = str(Path(pdf_path).resolve())

    return data


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

    if not data.get("candidate_name") and (data.get("first_name") or data.get("last_name")):
        fn = data.get("first_name", config["first_name"])
        ln = data.get("last_name", config["last_name"])
        config["candidate_name"] = f"{fn} {ln}".strip()

    if not data.get("location") and (config.get("city") and config.get("state")):
        config["location"] = f"{config['city']}, {config['state']}"

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
  - **Gender**: {cfg.get('gender', 'Decline to self-identify')}
  - **Pronouns**: {cfg.get('pronouns', 'He/Him')}
  - **Hispanic / Latino**: {cfg.get('hispanic_latino', 'No')}
  - **Race / Ethnicity**: {cfg.get('race_ethnicity', 'Asian')}
  - **Veteran Status**: {cfg.get('veteran_status', 'I am not a protected veteran')}
  - **Disability Status**: {cfg.get('disability', 'No, I do not have a disability')}
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
        lines_t = [
            r"\documentclass[letterpaper,11pt]{article}",
            r"\usepackage[empty]{fullpage}",
            r"\usepackage{hyperref}",
            r"\begin{document}",
            r"\begin{center}",
            f"    \\textbf{{\\Huge {name}}} \\\\ \\vspace{{2pt}}",
            f"    \\small {phone} $|$ \\href{{mailto:{email}}}{{{email}}} $|$ \\href{{{linkedin}}}{{{clean_li}}} $|$ \\href{{{github}}}{{{clean_gh}}}",
            r"\end{center}",
            r"\section*{Education}",
            f"\\textbf{{{school}}} \\hfill {loc} \\\\",
            f"\\textit{{{degree}; GPA: {gpa}}} \\hfill Expected {grad_my}",
            r"\section*{Technical Skills}",
            r"\textbf{Languages:} Python, Java, JavaScript, TypeScript, SQL, C/C++ \\",
            r"\textbf{Frameworks \& Tools:} FastAPI, React, Node.js, Docker, PostgreSQL, AWS, Linux, Git",
            r"\end{document}"
        ]
        t = "\n".join(lines_t) + "\n"

    if not latex_file.exists() or overwrite:
        with open(latex_file, "w", encoding="utf-8") as f:
            f.write(t)
        print(f"  ✅ Built base_resume_latex.txt at {latex_file}")

    # If user already has a valid default_resume_pdf, keep it
    existing_pdf = cfg.get("default_resume_pdf", "")
    if existing_pdf and Path(existing_pdf).exists():
        print(f"  📄 Using candidate resume PDF: {existing_pdf}")
        return latex_file

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
    """Interactively prompts user in terminal for profile details or resume PDF."""
    print("\n👋 Welcome to AIJobAssistant Setup Wizard!")
    data = {}
    
    resume_path = input("📄 Have a Resume PDF? Enter path (or press Enter to fill manually): ").strip()
    if resume_path and Path(resume_path).expanduser().exists():
        full_path = str(Path(resume_path).expanduser().resolve())
        print(f"\n🔍 Reading and extracting candidate profile from: {full_path}...")
        try:
            txt = extract_text_from_pdf(full_path)
            extracted = parse_resume_data(txt, full_path)
            print(f"  ✅ Found Candidate: {extracted.get('candidate_name', 'Unknown')}")
            print(f"  ✅ Found Email: {extracted.get('candidate_email', 'Unknown')}")
            print(f"  ✅ Found Phone: {extracted.get('phone', 'Unknown')}")
            print(f"  ✅ Found School: {extracted.get('school_name', 'Unknown')}")
            print(f"  ✅ Found Degree: {extracted.get('degree', 'Unknown')}")
            print(f"  ✅ Found GPA: {extracted.get('gpa', 'Unknown')}")
            print(f"  ✅ Found Preferred Lang: {extracted.get('preferred_language', 'Python')}")
            data.update(extracted)
        except Exception as e:
            print(f"  ⚠️ Could not auto-parse PDF: {e}. Falling back to manual prompts.")

    if not data.get("first_name"):
        first_name = input("1. First Name [Jane]: ").strip() or "Jane"
        last_name = input("2. Last Name [Doe]: ").strip() or "Doe"
        data["first_name"] = first_name
        data["last_name"] = last_name
        data["candidate_name"] = f"{first_name} {last_name}"

    if not data.get("candidate_email"):
        data["candidate_email"] = input("3. Email [jane.doe@example.com]: ").strip() or "jane.doe@example.com"

    if not data.get("phone"):
        data["phone"] = input("4. Phone [555-123-4567]: ").strip() or "555-123-4567"

    if not data.get("school_name"):
        data["school_name"] = input("5. University / School [State University]: ").strip() or "State University"

    workday_pw = input("6. Workday Standard Password (optional): ").strip()
    if workday_pw:
        data["workday_password"] = workday_pw

    auth = input("7. Are you a US Citizen / Authorized without sponsorship? (Y/n) [Y]: ").strip().lower()
    if auth in ["n", "no"]:
        data["us_citizen"] = "No"
        data["sponsorship_required"] = "Yes"
    else:
        data["us_citizen"] = "Yes"
        data["sponsorship_required"] = "No"

    return data


def main():
    parser = argparse.ArgumentParser(description="Initialize AIJobAssistant candidate profile & local files.")
    parser.add_argument("--resume-pdf", "--resume", dest="resume_pdf", default=None, help="Path to candidate resume PDF for automatic parsing")
    parser.add_argument("--target-dir", default=None, help="Directory to initialize (defaults to current working directory)")
    parser.add_argument("--json", dest="json_str", default=None, help="Candidate profile as JSON string")
    parser.add_argument("--file", dest="json_file", default=None, help="Path to JSON file with candidate profile")
    parser.add_argument("--interactive", action="store_true", help="Prompt user interactively in terminal")
    parser.add_argument("--force", action="store_true", help="Overwrite existing configuration files")
    parser.add_argument("--no-tectonic", action="store_true", help="Skip LaTeX tectonic compilation")
    
    args = parser.parse_args()
    target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd().resolve()

    data = {}

    # If resume PDF provided, parse it first
    if args.resume_pdf:
        pdf_path = Path(args.resume_pdf).expanduser().resolve()
        print(f"📄 Extracting profile from resume PDF: {pdf_path}")
        try:
            txt = extract_text_from_pdf(str(pdf_path))
            parsed = parse_resume_data(txt, str(pdf_path))
            data.update(parsed)
            print(f"  ✅ Extracted: {data.get('candidate_name')} | {data.get('candidate_email')} | {data.get('school_name')}")
        except Exception as e:
            sys.exit(f"❌ Error extracting resume PDF: {e}")

    # If JSON string or file provided, merge it over (allows overrides)
    if args.json_str:
        try:
            data.update(json.loads(args.json_str))
        except Exception as e:
            sys.exit(f"❌ Error: Invalid JSON passed to --json: {e}")
    elif args.json_file:
        try:
            with open(args.json_file, "r") as f:
                data.update(json.load(f))
        except Exception as e:
            sys.exit(f"❌ Error: Could not read JSON file {args.json_file}: {e}")
    elif args.interactive or (sys.stdin.isatty() and not args.resume_pdf):
        data.update(prompt_interactive())

    run_setup(target_dir, data, overwrite=args.force, compile_pdf=not args.no_tectonic)


if __name__ == "__main__":
    main()
