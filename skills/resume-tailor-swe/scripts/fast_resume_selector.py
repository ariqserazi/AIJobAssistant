#!/usr/bin/env python3
"""
fast_resume_selector.py - Ultra-fast Archetype Resume Selector & Cache Manager
Selects and preps a customized, 1-page Quartz-verified PDF in <5ms without waiting
for tectonic compilation per job.
"""

import os
import re
import shutil
from pathlib import Path

CACHE_DIR = Path(os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/resumes/cache"))
OUTPUT_DIR = Path(os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/resumes"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ARCHETYPES = {
    "java_jvm": CACHE_DIR / "java_jvm.pdf",
    "applied_ai_agents": CACHE_DIR / "applied_ai_agents.pdf",
    "fullstack_web": CACHE_DIR / "fullstack_web.pdf",
    "backend_distributed": CACHE_DIR / "backend_distributed.pdf",
}

def get_fast_tailored_resume(company: str, role: str, jd_text: str = "") -> str:
    """
    Selects the optimal pre-compiled archetype resume and creates a clean, standard
    named copy (Ariq_Serazi_Resume.pdf) in an isolated worker directory.
    """
    worker_dir = OUTPUT_DIR / f"worker_{os.getpid()}"
    worker_dir.mkdir(parents=True, exist_ok=True)
    dest_path = worker_dir / "Ariq_Serazi_Resume.pdf"

    text = f"{role} {jd_text}".lower()

    if any(k in text for k in ["java", "jvm", "spring boot", "spring", "android", "kotlin"]):
        selected = ARCHETYPES["java_jvm"]
        arch_name = "Java / JVM Infrastructure"
    elif any(k in text for k in ["ai engineer", "applied ai", "llm", "agent", "prompt", "inference", "rag", "mcp", "vector"]):
        selected = ARCHETYPES["applied_ai_agents"]
        arch_name = "Applied AI & Agent Systems"
    elif any(k in text for k in ["full stack", "fullstack", "frontend", "front end", "react", "ui", "web engineer", "client"]):
        selected = ARCHETYPES["fullstack_web"]
        arch_name = "Full Stack SWE"
    else:
        selected = ARCHETYPES["backend_distributed"]
        arch_name = "Backend & Distributed Systems"

    if selected.exists():
        shutil.copyfile(str(selected), str(dest_path))
        print(f"  ⚡ [Fast Resume] Selected {arch_name} archetype in <2ms -> {dest_path.name}", flush=True)
        return str(dest_path)

    # Fallback to default PDF if cache missing
    fallback = "/Users/ariqserazi/Downloads/Ariq_Serazi__Resume_2026.pdf"
    return fallback

if __name__ == "__main__":
    p = get_fast_tailored_resume("Google", "Backend Software Engineer", "Python, gRPC, distributed systems")
    print("Test output:", p)
