try:
    from config_loader import load_config
except ImportError:
    try:
        from application_engine.config_loader import load_config
    except ImportError:
        def load_config(): return {}

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
    named copy (Candidate_Resume.pdf) in an isolated worker directory.
    """
    worker_dir = OUTPUT_DIR / f"worker_{os.getpid()}"
    worker_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    fname = f"{cfg.get('first_name', 'Candidate')}_{cfg.get('last_name', 'Resume')}.pdf"
    dest_path = worker_dir / fname

    # Prioritize exact tailored resume matching company and role keywords
    clean_comp = re.sub(r'[^a-zA-Z0-9]', '_', company.lower())
    role_words = [w for w in re.sub(r'[^a-zA-Z0-9]', ' ', role.lower()).split() if len(w) > 3 and w not in ["intern", "summer", "engineer", "software"]]
    # 1. Try matching company + role keywords (sort by best keyword overlap)
    candidates = [f for f in OUTPUT_DIR.glob("*.pdf") if clean_comp in f.name.lower() and "worker_" not in str(f)]
    if candidates and role_words:
        best = max(candidates, key=lambda f: sum(1 for rw in role_words if rw in f.name.lower()))
        if any(rw in best.name.lower() for rw in role_words):
            shutil.copyfile(str(best), str(dest_path))
            print(f"  ⚡ [Fast Resume] Selected exact tailored resume: {best.name} -> {dest_path.name}", flush=True)
            return str(dest_path)
    # 2. Match company
    for f in candidates:
        shutil.copyfile(str(f), str(dest_path))
        print(f"  ⚡ [Fast Resume] Selected exact tailored resume: {f.name} -> {dest_path.name}", flush=True)
        return str(dest_path)

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
    cfg = load_config()
    fallback = cfg.get("default_resume_pdf") or str(Path(__file__).parent.parent / "references" / "sample_resume.pdf")
    return fallback

if __name__ == "__main__":
    p = get_fast_tailored_resume("Google", "Backend Software Engineer", "Python, gRPC, distributed systems")
    print("Test output:", p)
