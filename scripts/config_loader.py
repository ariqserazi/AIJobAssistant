#!/usr/bin/env python3
"""
config_loader.py - Candidate Profile & Application Configuration Loader
Safely loads candidate profile, credentials, and answers from config.json
with zero personal data hardcoded in engine source code.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
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
    "country": "United States",
    "discipline": "Computer Science",
    "major": "Computer Science",
    "field_of_study": "Computer Science",
    "linkedin_url": "https://linkedin.com/in/janedoe",
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
    "current_employer": "Tech Startup",
    "current_title": "Software Engineer",
    "previous_employer": "Software Labs",
    "featured_project": "Distributed Cloud System",
    "default_resume_pdf": "",
    "transcript_pdf": "",
    "workday_password": "",
    "google_sheet_id": "",
    "google_service_account_key": "",
    "ai_reasoner": "ollama",  # "ollama" (0 credit cost, local) or "chat_llm" (active AI chat assistant)
    "enable_ollama": True,
    "ollama_endpoint": "http://127.0.0.1:11434/api/generate",
    "ollama_model": "qwen3:4b-instruct",
    "us_citizen": "Yes",
    "us_person": "Yes",
    "authorized_in_us": "Yes",
    "sponsorship_required": "No",
    "gender": "Male",
    "pronouns": "He/Him",
    "race": "Asian",
    "veteran": "I am not a protected veteran",
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

def find_config_path() -> Path:
    """Locates config.json across standard search locations."""
    candidates = [
        Path.cwd() / "config.json",
        Path(__file__).parent.resolve() / "config.json",
        Path(__file__).parent.parent.resolve() / "config.json",
        Path.home() / ".config" / "aijobassistant" / "config.json",
        Path.home() / ".agents" / "skills" / "resume-tailor-swe" / "config.json"
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return Path.cwd() / "config.json"

def load_config() -> Dict[str, Any]:
    """Loads candidate configuration merging user config.json with safe defaults."""
    cfg = dict(DEFAULT_CONFIG)
    p = find_config_path()
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                user_data = json.load(f)
                if isinstance(user_data, dict):
                    # Merge nested responses dict cleanly
                    if "responses" in user_data and isinstance(user_data["responses"], dict):
                        cfg["responses"].update(user_data["responses"])
                    for k, v in user_data.items():
                        if k != "responses" and v:
                            cfg[k] = v
        except Exception as e:
            print(f"⚠️ [ConfigLoader] Note: Could not parse {p}: {e}")
    return cfg

def get_candidate_dict() -> Dict[str, str]:
    """Returns candidate dictionary compatible with batch application runners."""
    cfg = load_config()
    return {
        "name": cfg.get("candidate_name", "Jane Doe"),
        "first_name": cfg.get("first_name", "Jane"),
        "last_name": cfg.get("last_name", "Doe"),
        "email": cfg.get("candidate_email", "jane.doe@example.com"),
        "phone": cfg.get("phone", "555-123-4567"),
        "location": cfg.get("location", "New York, New York"),
        "city": cfg.get("city", "New York"),
        "state": cfg.get("state", "New York"),
        "country": cfg.get("country", "United States"),
        "zip_code": cfg.get("postal_code", "10001"),
        "postal_code": cfg.get("postal_code", "10001"),
        "discipline": cfg.get("discipline", "Computer Science"),
        "major": cfg.get("major", "Computer Science"),
        "field_of_study": cfg.get("field_of_study", "Computer Science"),
        "current_company": cfg.get("current_employer", "Tech Startup"),
        "current_title": cfg.get("current_title", "Software Engineer"),
        "linkedin": cfg.get("linkedin_url", "https://linkedin.com/in/janedoe"),
        "github": cfg.get("github_url", "https://github.com/janedoe"),
        "portfolio": cfg.get("portfolio_url", "https://janedoe.dev"),
        "school": cfg.get("school_name", "State University"),
        "degree": cfg.get("degree", "Bachelor of Science in Computer Science"),
        "degree_undergrad": cfg.get("degree_undergrad", "Bachelor of Science in Computer Science"),
        "gpa": str(cfg.get("gpa", "3.85")),
        "undergrad_start_year": str(cfg.get("undergrad_start_year", "2022")),
        "undergrad_start_month": str(cfg.get("undergrad_start_month", "September")),
        "undergrad_grad_year": str(cfg.get("undergrad_grad_year", "2026")),
        "undergrad_grad_month": str(cfg.get("undergrad_grad_month", "May")),
        "grad_start_year": str(cfg.get("grad_start_year", "2026")),
        "grad_start_month": str(cfg.get("grad_start_month", "September")),
        "grad_end_year": str(cfg.get("grad_end_year", "2028")),
        "grad_end_month": str(cfg.get("grad_end_month", "May")),
        "grad_date": str(cfg.get("grad_date", "05/2026")),
        "grad_month_year": str(cfg.get("grad_month_year", "May 2026")),
        "salary": str(cfg.get("salary", "80000")),
        "pronouns": cfg.get("pronouns", "He/Him"),
        "gender": cfg.get("gender", "Male"),
        "race": cfg.get("race", "Asian"),
        "veteran": cfg.get("veteran", "I am not a protected veteran"),
        "disability": cfg.get("disability", "No, I do not have a disability"),
        "preferred_language": cfg.get("preferred_language", "Python"),
        "citizenship": cfg.get("citizenship", "U.S. Citizen"),
        "us_citizen": cfg.get("us_citizen", "Yes"),
        "us_person": cfg.get("us_person", "Yes"),
        "authorized_in_us": cfg.get("authorized_in_us", "Yes"),
        "sponsorship_required": cfg.get("sponsorship_required", "No")
    }

def get_responses_dict() -> Dict[str, str]:
    """Returns dynamic free-text essay and question responses."""
    cfg = load_config()
    return cfg.get("responses", DEFAULT_CONFIG["responses"])

if __name__ == "__main__":
    cfg = load_config()
    print("✅ Config loaded successfully:")
    print(f"  Candidate: {cfg.get('candidate_name')} ({cfg.get('candidate_email')})")
    print(f"  Location:  {cfg.get('location')}")
    print(f"  School:    {cfg.get('school_name')} (GPA {cfg.get('gpa')})")
