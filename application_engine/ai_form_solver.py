import os
import re
import json
import urllib.request
from typing import List, Optional

try:
    from config_loader import get_candidate_dict, load_config
except ImportError:
    try:
        from application_engine.config_loader import get_candidate_dict, load_config
    except ImportError:
        def get_candidate_dict(): return {}
        def load_config(): return {}

_cfg = load_config()
AI_REASONER = _cfg.get("ai_reasoner", "ollama" if _cfg.get("enable_ollama", True) else "disabled")
ENABLE_OLLAMA = _cfg.get("enable_ollama", True) and AI_REASONER == "ollama"
OLLAMA_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", _cfg.get("ollama_endpoint", "http://127.0.0.1:11434/api/generate"))
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", _cfg.get("ollama_model", "qwen3:4b-instruct"))

def get_candidate_ground_truth() -> str:
    _c = get_candidate_dict()
    first = _c.get("first_name", "Candidate")
    last = _c.get("last_name", "User")
    email = _c.get("candidate_email", "candidate@example.com")
    phone = _c.get("phone", "555-123-4567")
    loc = _c.get("location", "New York, New York, United States")
    school = _c.get("school_name", "State University")
    gpa = _c.get("gpa", "3.85")
    curr_emp = _c.get("current_employer", "Tech Startup")
    prev_emp = _c.get("previous_employer", "Software Labs")
    return f"""
Candidate Ground Truth:
- Full Name: {first} {last} (First: {first}, Last: {last})
- Email: {email} | Phone: {phone}
- Location: {loc}
- Citizenship: United States of America (U.S. Citizen)
- Work Authorization: Authorized to work for any employer in the United States. Strictly does NOT need visa sponsorship now or in the future (Visa/Sponsorship needed: No, Legally authorized: Yes).
- Education: {school}.
  - BS in Computer Science: May 2024 (GPA: {gpa} / 4.0)
  - MS in Computer Science: Projected May 2028 (Graduation year: 2028, Season: Spring 2028)
- Demographics:
  - Gender: Male / Man
  - Race/Ethnicity: Asian (South Asian, not Hispanic or Latino)
  - Veteran Status: I am not a protected veteran (Not a veteran, Never served, No military)
  - Disability: No, I do not have a disability
- Employment History:
  - Current/Recent: {curr_emp} (Software Engineer, AI/Backend/Python)
  - Previous: {prev_emp} (Full Stack Engineer, Healthcare/Web)
  - Never worked at the applying company before unless specified.
- Relocation: Yes, willing to relocate (prefer at least 1 month notice if possible).
- Preferred Start Date: May 20, 2027 for Summer; December 20, 2026 for Winter.
- Salary Expectation: 80000 / year or $40/hr.
- Strict Formatting Rule: Free text must strictly contain ZERO dashes or hyphens. Never use N/A. Use None or Not applicable.
"""

def _query_ollama(prompt: str, timeout_sec: float = 12.0) -> Optional[str]:
    """Queries local Ollama instance (0 credit cost, runs on-device)."""
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 120
            }
        }
        req = urllib.request.Request(
            OLLAMA_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ans = data.get("response", "").strip()
            return ans.strip("`'\" \n\t")
    except Exception:
        return None


def query_ai_reasoner(prompt: str, timeout_sec: float = 12.0) -> Optional[str]:
    """Queries the configured AI reasoning engine (Ollama for 0 credit cost, or Active Chat Assistant)."""
    if AI_REASONER == "disabled":
        return None

    # Option 1: Ollama Local AI (0 credit cost)
    if AI_REASONER == "ollama" or ENABLE_OLLAMA:
        ans = _query_ollama(prompt, timeout_sec=timeout_sec)
        if ans:
            return ans

    # Option 2: Current AI Chat Assistant (chat_llm)
    # When running headless without Ollama, return None so the script gracefully falls back
    # to candidate ground truth and regex heuristics, or allows the active chat agent to solve it.
    if AI_REASONER == "chat_llm":
        return None

    return None

def solve_field_with_ai(
    question: str,
    field_type: str,
    options: Optional[List[str]] = None,
    company: str = "",
    role: str = ""
) -> Optional[str]:
    q_clean = " ".join(question.replace("\xa0", " ").split())
    
    if field_type in ["radio", "combobox", "select"]:
        if not options:
            return None
        
        prompt = f"""{get_candidate_ground_truth()}

Task: Choose the single best option for the following job application question for {company or "the employer"} ({role or "Internship"}).

Question: {q_clean}
Available Options:
{json.dumps(options, indent=2)}

Instructions:
1. Select exactly ONE option from the Available Options list that truthfully represents the candidate.
2. If asking about veteran status, select 'I am not a protected veteran' or 'No'.
3. If asking about work authorization, select the U.S. Citizen / Authorized option without sponsorship.
4. If asking about sanctioned countries (North Korea, Syria, Iran, Cuba), select 'No'.
5. Output ONLY the exact text of the chosen option string verbatim. Do not add explanation or punctuation.

Chosen Option:"""
        
        res = query_ai_reasoner(prompt)
        if res:
            res_low = res.lower().strip()
            for opt in options:
                if opt.lower().strip() == res_low:
                    return opt
            for opt in options:
                if res_low in opt.lower() or opt.lower() in res_low:
                    return opt
        return None

    elif field_type == "checkbox":
        prompt = f"""{get_candidate_ground_truth()}

Task: Determine which checkbox options should be checked for the question on {company or "the employer"}'s application form.

Question: {q_clean}
Available Checkbox Options:
{json.dumps(options or [], indent=2)}

Instructions:
1. If this is a legal certification, truth statement, consent, or policy acknowledgment, answer 'CHECK_ALL'.
2. If specific choices apply to the candidate, list only the matching options verbatim.
3. Output ONLY the matching option strings separated by newline, or 'CHECK_ALL'.

Answer:"""
        res = query_ai_reasoner(prompt)
        if res:
            if "CHECK_ALL" in res or "agree" in res.lower() or "certify" in res.lower():
                return "CHECK_ALL"
            return res.strip()
        return None

    elif field_type in ["text", "textarea"]:
        is_substantive = field_type == "textarea" or any(k in q_clean.lower() for k in [
            "why", "interest", "project", "experience", "background", "describe",
            "challenge", "fit", "tell us", "accomplish", "proud", "cover letter", "about you"
        ])

        if is_substantive:
            instructions_block = """Instructions:
1. This is a substantive open-ended question that deserves a detailed, thoughtful answer.
2. Write a polished, professional response of AT LEAST 4 COMPLETE SENTENCES.
3. Truthfully highlight the candidate's background in Computer Science at Rutgers University (GPA 3.85) and software engineering experience (Python, FastAPI, PostgreSQL, distributed systems, clean architecture, deterministic validation).
4. STRICT RULE: Zero dashes or hyphens anywhere in the response. No 'N/A' (use 'None' or 'Not applicable').
5. Provide ONLY the final text to be entered into the textbox."""
        else:
            instructions_block = """Instructions:
1. If asking for a company-assigned email or internal account during previous employment and the candidate never worked there, answer 'None'.
2. If asking for a short factual answer (e.g. name, date, link, salary, number of years, city), answer directly and concisely based on the candidate's profile.
3. STRICT RULE: Zero dashes or hyphens anywhere in the response. No 'N/A' (use 'None' or 'Not applicable').
4. Provide ONLY the final text to be entered into the input box."""

        prompt = f"""{get_candidate_ground_truth()}

Task: Provide the truthful answer for the following question on {company or "the employer"}'s application form.

Question: {q_clean}
Applying for: {role or "Software Engineer"} at {company or "the company"}

{instructions_block}

Input Text:"""
        res = query_ai_reasoner(prompt)
        if res:
            res = res.replace("-", " ").replace("—", " ").replace("–", " ")
            res = re.sub(r"\s+", " ", res).strip()
            return res
        return None

    return None
