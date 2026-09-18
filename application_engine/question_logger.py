#!/usr/bin/env python3
"""
question_logger.py - Centralized logger for form questions discovered across ATS platforms.
Persists questions, field types, available options, resolved answers, and match statuses
into application_engine/discovered_questions_log.json.
"""

import os
import json
import time
from typing import List, Optional, Dict, Any

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discovered_questions_log.json")

def load_logged_questions() -> List[Dict[str, Any]]:
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []

def log_discovered_question(
    question: str,
    field_type: str = "text",
    options: Optional[List[str]] = None,
    answer_used: str = "",
    status: str = "matched",
    platform: str = "",
    company: str = "",
    role: str = ""
) -> None:
    """
    Records a question prompt into discovered_questions_log.json.
    Deduplicates by (question.strip().lower(), field_type, company.lower()).
    """
    q_norm = question.strip()
    if not q_norm:
        return

    entry = {
        "question": q_norm,
        "field_type": field_type,
        "options": options or [],
        "answer_used": answer_used,
        "status": status,
        "platform": platform,
        "company": company,
        "role": role,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        existing = load_logged_questions()
        key = (q_norm.lower(), field_type.lower(), company.lower())
        updated = False
        for idx, item in enumerate(existing):
            item_key = (
                item.get("question", "").strip().lower(),
                item.get("field_type", "").strip().lower(),
                item.get("company", "").strip().lower()
            )
            if item_key == key:
                if status == "matched" and item.get("status") != "matched":
                    existing[idx] = entry
                updated = True
                break
        
        if not updated:
            existing.append(entry)

        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[QuestionLogger] Error persisting question log: {e}")

if __name__ == "__main__":
    log_discovered_question(
        question="Do you require relocation or relocation assistance?",
        field_type="radio",
        options=["Yes", "No", "Need at least 1 month"],
        answer_used="Need at least 1 month",
        status="matched",
        platform="test",
        company="TestCorp",
        role="SWE Intern"
    )
    print(f"Logged test question to {LOG_FILE}. Current entries: {len(load_logged_questions())}")
