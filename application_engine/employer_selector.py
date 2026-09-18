"""
employer_selector.py - Dynamically selects the most relevant recent employer
based on role title, company description, and tech stack alignment configured in config.json.
"""

import sys
import os

try:
    from config_loader import load_config
except ImportError:
    try:
        from application_engine.config_loader import load_config
    except ImportError:
        def load_config():
            return {}

def get_recent_employer(company: str = "", role: str = "", jd_text: str = "") -> str:
    """
    Returns configured current_employer or previous_employer based on the employer/role context:
    - If the role/employer is focused on Full Stack, Frontend, Web, Node/Express, Payments/Fintech,
      Healthcare/Healthtech, E-commerce, Flutter/Mobile, or general client-facing applications -> previous_employer.
    - If the role/employer is focused on AI, ML, LLM, Agents, Automation, Backend/Distributed Systems,
      Data Engineering, Python, or Infrastructure -> current_employer.
    - Defaults to current_employer if ambiguous.
    """
    cfg = load_config()
    current_emp = cfg.get("current_employer", "Tech Startup")
    previous_emp = cfg.get("previous_employer", "Software Labs")

    combined = f"{company} {role} {jd_text}".lower()

    # Keywords favoring frontend, mobile, full-stack, or e-commerce
    alt_keywords = [
        "health", "care", "medical", "patient", "clinical",
        "full stack", "fullstack", "frontend", "front end", "web developer", "web engineer",
        "node", "express", "react", "javascript", "typescript",
        "payment", "fintech", "stripe", "checkout", "billing", "e-commerce", "ecommerce",
        "flutter", "mobile app", "ios", "android"
    ]

    for kw in alt_keywords:
        if kw in combined:
            return previous_emp

    return current_emp

if __name__ == "__main__":
    test_cases = [
        ("HealthCorp", "Full Stack Developer", "React, Node.js, Stripe payments"),
        ("AI Labs", "Machine Learning Engineer", "Python, LLM orchestration, FastAPI"),
        ("Virtu Financial", "Frontend Developer Internship", "JavaScript, React, UI"),
        ("Datadog", "Software Engineer - Backend", "Distributed systems, Python, Go"),
    ]
    for c, r, jd in test_cases:
        print(f"[{c} - {r}] -> {get_recent_employer(c, r, jd)}")
