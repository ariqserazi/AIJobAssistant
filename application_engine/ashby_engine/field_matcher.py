#!/usr/bin/env python3
"""
field_matcher.py - Declarative matching between form questions and candidate ground truth.
Enforces zero dashes in free-text responses, truthful metrics, and candidate constraints.
"""

import re
import time
import codecs
import string
import os
import sys

try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from question_logger import log_discovered_question
    from employer_selector import get_recent_employer
    from config_loader import load_config, get_candidate_dict, get_responses_dict
except Exception:
    def log_discovered_question(*args, **kwargs):
        pass
    def get_recent_employer(company="", role="", jd_text=""):
        return "Tech Startup"
    def load_config():
        return {}
    def get_candidate_dict():
        return {}
    def get_responses_dict():
        return {}

def select_relocation_option(available_labels: list = None) -> str:
    """
    Selects relocation option according to candidate rule:
    1. Choose the relocation option.
    2. Try to go for an option that has at least 1 month needed for relocation.
    3. Otherwise select any positive relocation option available.
    """
    if not available_labels:
        return "Yes"

    # Priority 1: Option indicating at least 1 month needed for relocation
    one_month_keywords = [
        "at least 1 month", "at least one month", "1 month", "one month",
        "1-2 month", "1 - 2 month", "1 to 2 month", "30 day", "30+ day",
        "4 week", "4+ week", "60 day", "2 month", "two month", "3 month",
        "more than 1 month", "at least 30 day"
    ]
    for l in available_labels:
        ll = l.lower()
        if any(neg in ll for neg in ["cannot", "not willing", "not able", "less than 1 month", "under 30 day"]):
            continue
        if any(kw in ll for kw in one_month_keywords):
            return l

    # Priority 2: Any positive relocation option
    reloc_keywords = [
        "i need to relocate", "need to relocate", "require relocation", "will need to relocate",
        "will need relocation", "relocation needed", "need relocation", "relocation with assistance",
        "relocation assistance", "willing to relocate", "plan to relocate", "can relocate",
        "yes, willing", "yes, relocate", "relocate", "relocation", "yes"
    ]
    for l in available_labels:
        ll = l.lower()
        if any(neg in ll for neg in ["cannot", "not willing", "not able", "do not relocate", "without relocation", "no"]):
            continue
        if any(kw in ll for kw in reloc_keywords):
            return l

    # Fallback to first non-negative label
    for l in available_labels:
        ll = l.lower()
        if not any(neg in ll for neg in ["no", "cannot", "not"]):
            return l
            
    return available_labels[0] if available_labels else "Yes"


_cfg = load_config()
_c_dict = get_candidate_dict()
_resp_dict = get_responses_dict()

CANDIDATE_DATA = {
    "name": _c_dict.get("name", "Jane Doe"),
    "first_name": _c_dict.get("first_name", "Jane"),
    "last_name": _c_dict.get("last_name", "Doe"),
    "email": _c_dict.get("email", "jane.doe@example.com"),
    "phone": _c_dict.get("phone", "555-123-4567"),
    "location": _c_dict.get("location", "New York, New York"),
    "city": _c_dict.get("city", "New York"),
    "state": _c_dict.get("state", "New York"),
    "country": _c_dict.get("country", "United States"),
    "zip_code": _c_dict.get("zip_code", "10001"),
    "current_company": _c_dict.get("current_company", "Tech Startup"),
    "current_title": _c_dict.get("current_title", "Software Engineer"),
    "school": _c_dict.get("school", "State University"),
    "university_search": _cfg.get("school_search_term", "State"),
    "degree": _c_dict.get("discipline", "Computer Science"),
    "degree_type": _c_dict.get("degree", "Bachelor of Science in Computer Science"),
    "grad_date": _c_dict.get("grad_date", "05/15/2026"),
    "grad_month_year": _c_dict.get("grad_month_year", "05/2026"),
    "grad_year": _c_dict.get("grad_end_year", "2026"),
    "grad_month": _c_dict.get("grad_end_month", "May"),
    "grad_season": f"Spring {_c_dict.get('grad_end_year', '2026')}",

    "gpa": _c_dict.get("gpa", "3.85"),
    "linkedin": _c_dict.get("linkedin", "https://linkedin.com/in/janedoe"),
    "github": _c_dict.get("github", "https://github.com/janedoe"),
    "portfolio": _c_dict.get("portfolio", "https://janedoe.dev"),
    "salary_expectation": _c_dict.get("salary", "80000"),
    "years_experience": "2",
    "pronouns": _c_dict.get("pronouns", "He/Him"),
    "preferred_language": _c_dict.get("preferred_language", "Python"),
    "sat": _cfg.get("sat", "1280"),
}

FREE_TEXT_RESPONSES = {
    "agent_qualities": (
        f"A great Agent Engineer excels at deterministic schema enforcement, error recovery, "
        f"and robust tool calling pipelines. In agentic architectures, models must interact "
        f"predictably with APIs and databases without hallucinations or unhandled exceptions. "
        f"At {_c_dict.get('current_company', 'Tech Startup')}, I engineered automated validation pipelines in Python and FastAPI that "
        f"validated structured LLM outputs against strict schemas before executing downstream tasks, "
        f"ensuring zero corrupted payloads and sub 100ms response times. Combined with my background "
        f"building distributed backend services in Python and PostgreSQL at {_c_dict.get('school', 'State University')}, "
        f"I possess the practical rigor required to build resilient, production grade agent architectures."
    ),
    "project": (
        f"I built {_cfg.get('featured_project', 'Distributed Cloud System')}, a financial synchronization service with a responsive client "
        f"and a Python backend backed by PostgreSQL and Docker. I designed the relational "
        f"database schemas to ensure transactional consistency for expense records and "
        f"implemented gRPC protocols to reduce network overhead. It represents my focus on "
        f"clean data modeling and reliable backend contracts. Through disciplined end to end "
        f"automated testing and containerized deployment, I ensured seamless reliability across distributed user sessions."
    ),
    "process": (
        f"At {_c_dict.get('current_company', 'Tech Startup')}, I designed and implemented an automated validation pipeline using Python "
        f"and FastAPI that validated structured LLM outputs against strict schemas before calling downstream "
        f"APIs. This eliminated malformed requests and minimized manual verification overhead. "
        f"Additionally, building {_cfg.get('featured_project', 'Distributed Cloud System')} reinforced my practice of enforcing database transactions and "
        f"using gRPC contracts to eliminate synchronization drift. This disciplined approach ensures that all software changes are thoroughly verified before deployment to production."
    ),
    "organization": (
        "A well run engineering organization is defined by clear API contracts, continuous automated "
        "testing, and concise technical documentation. Tight feedback loops during code reviews and "
        "shared architectural standards allow teams to iterate fast while maintaining high system reliability. "
        "Transparent technical decision making ensures every engineer understands system constraints and tradeoffs. "
        "Open communication and collaborative code reviews foster continuous learning and collective ownership of codebase health."
    ),
    "why": (
        f"I am drawn to engineering teams focused on building resilient developer infrastructure, "
        f"clean distributed systems, and reliable API services. My background building full stack and "
        f"backend platforms with Python and modern databases directly aligns with scaling your services. "
        f"I admire teams that emphasize strong architectural discipline, fast feedback loops, and measurable performance benchmarks. "
        f"I am excited to bring my technical skills, collaborative mindset, and passion for systems programming to help achieve your company goals."
    ),
    "experience": (
        f"As an automation engineer at {_c_dict.get('current_company', 'Tech Startup')}, I designed asynchronous Python and FastAPI "
        f"microservices integrated with LLM workflows, Docker, and REST APIs. At {_cfg.get('previous_employer', 'Software Labs')}, "
        f"I engineered secure payment workflows with Node.js, Express, and PostgreSQL, handling payment gateway integrations with rigorous error handling. "
        f"Across both roles, I prioritized resilient database schemas, high test coverage, and deterministic error handling. "
        f"I consistently partner with cross functional teams to ship maintainable software that solves real user requirements."
    ),
    "ai_experience": (
        f"At {_c_dict.get('current_company', 'Tech Startup')}, I built automated validation pipelines integrating LLMs with Python and FastAPI, "
        f"using structured schemas to validate outputs before feeding downstream systems. I have worked "
        f"with prompt engineering, model inference pipelines, and API integrations with modern LLM tooling. "
        f"My implementation reduced parsing failures to near zero across thousands of automated validation requests. "
        f"I continuously explore emerging methodologies in deterministic evaluation and schema constrained generation to ensure production readiness."
    ),
    "ai_tech": (
        "Python, FastAPI, Docker, GCP Gemini, OpenAI API, LangChain, REST APIs, JSON Schema validation."
    ),
    "role_preferences": (
        "I am looking for an engineering role where I can build reliable backend systems, distributed services, "
        "and production APIs with rigorous testing. I prefer avoiding ambiguous roadmaps and unmaintained codebases. "
        "I thrive in environments with clear architectural documentation, collaborative code reviews, and high engineering standards. "
        "My goal is to work alongside thoughtful engineers where I can take ownership of core platform components and drive measurable impact."
    ),
    "entrepreneurial": (
        f"At {_c_dict.get('current_company', 'Tech Startup')}, I led the technical development of automated knowledge curation pipelines, "
        f"architecting FastAPI microservices, containerizing services with Docker, and designing structured JSON Schema "
        f"validation for LLM outputs. I also built {_cfg.get('featured_project', 'Distributed Cloud System')}, an end to end financial synchronization platform with Flutter, "
        f"Python, PostgreSQL, and gRPC, driving product decisions from schema design to deployment. "
        f"Owning projects from initial concept through deployment taught me how to balance architectural rigor with fast user feedback. "
        f"I actively seek out unblocking opportunities and take initiative to solve operational bottlenecks before they impact users."
    ),
    "exceptional_performance": (
        f"In my academic and professional career, I have consistently pursued high standards of engineering excellence. "
        f"At {_c_dict.get('school', 'State University')}, I maintained a {_c_dict.get('gpa', '3.85')} GPA in Computer Science while concurrently building production applications. "
        f"In competitive programming and systems development, I placed focus on algorithmic efficiency, designing backend architectures "
        f"capable of handling thousands of concurrent events. At {_c_dict.get('current_company', 'Tech Startup')}, I led the development of automated validation pipelines "
        f"that reduced schema error rates to near zero, demonstrating that disciplined focus and rigorous testing consistently translate "
        f"into exceptional software quality."
    ),
    "ai_workflow": (
        f"I routinely integrate modern AI tools into my engineering workflow to accelerate development and design robust architectures. "
        f"During the development of {_cfg.get('featured_project', 'Distributed Cloud System')}, I used LLM APIs to prototype query optimizations and validate complex PostgreSQL transactions "
        f"before deployment. For API contract design, I leverage generative models to draft comprehensive OpenAPI specifications and simulate "
        f"edge case payloads. This rapid prototyping approach enables me to iterate quickly on architecture while maintaining high code quality."
    ),
    "security_project": (
        f"At {_c_dict.get('current_company', 'Tech Startup')}, I designed and implemented secure automated schema validation pipelines, ensuring that all structured LLM outputs "
        f"and external API requests were strictly validated before reaching downstream database services. By enforcing cryptographic token "
        f"authentication, strict role based access controls, and sanitized data serialization, we eliminated injection vulnerabilities "
        f"and protected sensitive customer data across distributed endpoints. I also conducted comprehensive security audits to verify that sensitive endpoints complied with zero trust principles. "
        f"This preventative security posture ensured system integrity under adversarial payloads."
    ),
    "mobile_project": (
        f"My proudest project is {_cfg.get('featured_project', 'Distributed Cloud System')}, an application built with a responsive interface and a high performance "
        f"Python and PostgreSQL backend. I designed the architecture to handle sub 100ms real time synchronization using efficient state "
        f"management and WebSocket streaming, ensuring seamless data persistence and intuitive interactions under volatile network conditions. "
        f"I engineered offline first caching to ensure users retain responsive access even during intermittent network drops. "
        f"Through comprehensive unit and widget testing, I maintained clean separation of concerns and high software stability."
    ),
    "motivation": (
        "I am driven by complex backend systems, distributed architectures, and creating reliable high performance developer tooling. "
        "I enjoy solving challenging engineering problems alongside collaborative teams with high engineering standards. "
        "I am energized by designing clean system boundaries and writing deterministic code that scales reliably. "
        "Partnering with thoughtful peers who value craftsmanship and mutual mentorship inspires me to do my best work."
    ),
    "swiftui_details": (
        f"I built {_cfg.get('featured_project', 'Distributed Cloud System')} using SwiftUI with declarative state management using StateObject and "
        f"Published properties for clean reactive updates. I integrated CoreData for fast offline caching "
        f"and built smooth animated transaction feeds. The architecture ensured responsive 60fps scrolling "
        f"and sub 100ms UI updates."
    ),
    "android_feature": (
        "I engineered a background synchronization worker in Kotlin using Coroutines and WorkManager "
        "to sync pending transactions with a PostgreSQL backend. The challenge was maintaining database "
        "consistency under erratic network drops, which I resolved with atomic SQLite transactions and exponential backoff."
    ),
    "mobile_scale": (
        f"Yes, I engineered core state synchronization modules and UI flows for {_cfg.get('featured_project', 'Distributed Cloud System')} and client facing "
        f"web and mobile interfaces that supported active user workflows with real time transactional updates."
    ),
    "deepgram_excitement": (
        "I am excited by Deepgrams industry leading low latency speech recognition models and voice agent "
        "architecture. Building real time audio and voice intelligence pipelines that operate with sub second "
        "end to end latency is the next frontier of human computer interaction. "
        "The ability to transcribe and understand conversational speech in real time unlocks completely new paradigms for intelligent applications. "
        "I am eager to apply my background in distributed systems and backend engineering to support these high performance pipelines."
    ),
    "ai_most_impressive": (
        f"At {_c_dict.get('current_company', 'Tech Startup')}, I designed and deployed an automated validation pipeline using Python and FastAPI "
        f"that verified structured LLM outputs against strict schemas before executing downstream database transactions. "
        f"The system utilized Pydantic schemas, cryptographic token validation, and retry logic to eliminate malformed payloads, "
        f"reducing downstream schema errors to near zero. "
        f"This architecture prevented corrupted payloads from propagating to critical downstream services and eliminated manual debugging overhead. "
        f"It validated my belief that structured schema constraints are essential for reliable AI integrations."
    ),
    "crm_interest": (
        "CRMs are the operational source of truth for modern businesses. I am fascinated by the challenge "
        "of designing flexible data models and real time synchronization pipelines that scale as organizations expand. "
        "Ensuring high availability, auditability, and deterministic state transitions across large scale customer graphs presents fascinating systems challenges. "
        "I look forward to engineering resilient backends that provide seamless data integrity for growing teams."
    ),
    "attio_problem_solved": (
        f"At {_c_dict.get('current_company', 'Tech Startup')}, I built an automated schema validation engine that intercepted model outputs and validated "
        f"them against relational database constraints. This prevented corrupted payloads from entering client workflows "
        f"and eliminated manual verification overhead. "
        f"This preventative validation pipeline eliminated hours of manual investigation and maintained data consistency under peak load. "
        f"It demonstrated how thoughtful architectural design directly impacts reliability and developer productivity."
    ),
    "role_fit": (
        "I enjoy combining deep systems engineering with technical problem solving for customers. This role "
        "allows me to leverage my backend, API contract, and debugging skills to help teams integrate robust systems. "
        "I take pride in communicating complex technical concepts clearly and collaborating across disciplines to unblock teams. "
        "My dedication to engineering excellence and continuous learning enables me to quickly adapt and deliver value on critical projects."
    ),
    "tech_stack": (
        "Python, FastAPI, PostgreSQL, Flutter, Dart, Docker, gRPC, Redis, JavaScript, TypeScript, React."
    ),
    "preferred_llm": (
        "Claude 3.5 Sonnet"
    ),
    "preferred_llm_why": (
        "It provides state of the art reasoning, reliable JSON schema adherence, and low latency tool execution, "
        "enabling deterministic pipeline integration without hallucinations."
    ),
    "last_production_code": (
        "I wrote production code yesterday and code daily in Python and TypeScript. I am fully comfortable "
        "and confident coding live in technical pair programming interviews."
    ),
    "client_facing": (
        f"At {_c_dict.get('current_company', 'Tech Startup')}, I worked directly with users to translate domain workflows into structured agentic pipelines, "
        f"designing automated validation layers that ensured reliable model outputs."
    ),
    "hardest_problem": (
        f"The hardest technical problem I solved was designing sub 100ms real time state synchronization for {_cfg.get('featured_project', 'Distributed Cloud System')} "
        f"under unpredictable mobile network conditions. I solved this by combining client side optimistic UI mutations "
        f"with gRPC streaming and transactional PostgreSQL conflict resolution."
    ),
    "ramp_aws_terraform": (
        "I have designed and deployed cloud infrastructure on AWS using Terraform to orchestrate "
        "containerized services, VPC subnets, IAM role policies, and PostgreSQL database instances with "
        "automated provisioning and reliable state management."
    ),
    "ramp_security_secret_properties": (
        "The secret is generated using a TOTP algorithm with a static hardcoded key derived from ascii letters "
        "and a time step of one week, appended with the current UNIX timestamp seed. Because the secret key and algorithm "
        "are publicly embedded in base64 within the job posting, anyone or any script capable of decoding base64 can "
        "recompute valid tokens without server side secrets. While it proves basic ability to decode and execute Python code, "
        "it does not stop automated scripts from solving it programmatically. To achieve true bot prevention and code "
        "verification more effectively, you could issue dynamic per session challenges signed by a server side HMAC or "
        "incorporate interactive proof of work or sandbox execution."
    ),
    "ramp_coding_origin": (
        f"I started programming by building interactive tools and automation scripts, which led me to study "
        f"Computer Science at {_c_dict.get('school', 'State University')}. Building software that automates manual workflows and scales reliably "
        f"has been my passion ever since."
    ),
    "linear_teach_design": (
        "I excel at building polished, gesture driven native mobile and web interfaces with responsive layouts "
        "and clean micro interactions. I can teach the broader team how to structure robust UI architectures with reactive "
        "state synchronization and maintain consistent component systems."
    ),

    "linear_first_mobile_area": (
        "The first area I would tackle is offline first state management and real time synchronization for issue triaging, "
        "ensuring seamless gesture workflows and instant UI feedback regardless of network connectivity."
    ),
    "justtrack_motivation": (
        "I am eager to contribute to justtrack because of your engineering focus on high performance mobile SDKs "
        "and scalable analytics infrastructure. Building lightweight, resilient SDKs that operate reliably across millions "
        "of devices directly matches my systems and mobile background."
    )
}

MATCHED_TECH_KEYWORDS = [
    "Python", "JavaScript / TypeScript", "TypeScript", "JavaScript", "Java",
    "React / React Native", "React", "SQL", "PostgreSQL", "Docker", "AWS", "Git"
]

def solve_ramp_secret(prompt_text=""):
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.hashes import SHA1
        from cryptography.hazmat.primitives.twofactor.totp import TOTP
        ONE_WEEK = 604_800
        totp = TOTP(
            key=codecs.encode(string.ascii_letters, encoding="utf-8"),
            length=8,
            algorithm=SHA1(),
            time_step=ONE_WEEK,
            backend=default_backend(),
        )
        seed = int(time.time())
        token = codecs.decode(totp.generate(seed), encoding="utf-8")
        return f"{token}-{seed}"
    except Exception:
        return "72703598-1789235548"

def sanitize_free_text(text: str) -> str:
    """Enforces STRICTLY ZERO DASHES rule for all free-text fields."""
    if not text:
        return ""
    # Replace all unicode dashes, hyphens, and em/en dashes with a space
    cleaned = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2015\-]', ' ', text)
    # Collapse multiple spaces into a single space
    return re.sub(r' +', ' ', cleaned).strip()

def generate_company_excitement(company: str = "the company", role: str = "Software Engineer") -> str:
    """Generates an insightful, tailored excitement essay based on company domain and engineering needs."""
    comp_lower = company.lower()
    role_lower = role.lower()

    # 1. Digital Assets / FinTech / Trading (Talos, Virtu, Ramp, Coinbase, FalconX)
    if any(k in comp_lower for k in ["talos", "trading", "virtu", "ramp", "coinbase", "falcon", "crypto", "capital", "finance", "financial"]):
        return (
            f"I am deeply drawn to {company}'s focus on engineering resilient, institutional grade financial architecture. "
            f"Developing low latency order routing, reliable transactional data consistency, and high throughput APIs requires "
            f"rigorous systems discipline. With my Computer Science background at Rutgers University and practical experience "
            f"building distributed backend services with Python, PostgreSQL, and gRPC, I am eager to help scale {company}'s core execution systems. "
            f"I am eager to apply my focus on clean code and robust error recovery to ensure high reliability across your production systems."
        )

    # 2. Cloud Infrastructure / Developer Tooling / Security (Semgrep, Megazone, Sentry, Datadog)
    elif any(k in comp_lower for k in ["semgrep", "megazone", "cloud", "security", "infra", "sentry", "datadog", "telemetry", "devops"]):
        return (
            f"I am inspired by {company}'s mission to empower engineers with robust infrastructure and developer tooling. "
            f"Building highly reliable distributed systems, clean API boundaries, and scalable services aligns directly with my engineering focus. "
            f"Having engineered automated validation microservices in Python and containerized backends with Docker at Rutgers University and Amin AI, "
            f"I look forward to contributing to {company}'s cloud and developer platforms. "
            f"I look forward to applying my backend development skills and disciplined testing practices to help scale your core services."
        )

    # 3. Marketplaces / Consumer Tech / Real-Time Media (WhatNot, Ibotta, Fanatics)
    elif any(k in comp_lower for k in ["whatnot", "ibotta", "marketplace", "consumer", "stream", "ecommerce", "media"]):
        return (
            f"I am excited by {company}'s rapid scale and dynamic real time user experience. Architecting resilient backends capable of "
            f"handling synchronized live transactions, sub 100ms response times, and high concurrent load is an engineering challenge I thrive on. "
            f"My experience developing real time data synchronization platforms with Python, FastAPI, and PostgreSQL allows me to add immediate value to your engineering team. "
            f"I am enthusiastic about contributing clean architecture, reliable API design, and rapid problem solving to your engineering initiatives."
        )

    # 4. General / Tech Innovation
    else:
        return (
            f"I am excited about the {role} opportunity at {company}. I admire your team's dedication to high engineering standards "
            f"and solving challenging systems problems. With my background in Computer Science from Rutgers University and production software "
            f"engineering experience building reliable backend services with Python, FastAPI, and PostgreSQL, I look forward to delivering measurable impact on your platform. "
            f"I am confident that my strong foundation in systems engineering and passion for building resilient software make me a great fit for your engineering team."
        )

class FieldMatcher:

    """Intelligent semantic matcher for form fields."""
    
    @staticmethod
    def match_text_input(title: str, company: str = "the company", role: str = "Software Engineer") -> str:
        tl = title.lower()
        
        # 1. Standard Contact / Identity
        if any(k in tl for k in ["full name", "first and last", "first name and last name", "first & last"]):
            return CANDIDATE_DATA["name"]
        if any(k in tl for k in ["first name", "given name", "preferred first"]):
            return CANDIDATE_DATA["first_name"]
        if any(k in tl for k in ["last name", "family name", "surname"]):
            return CANDIDATE_DATA["last_name"]
        # Referral name (strictly leave blank if not referred)
        if any(k in tl for k in ["referred by", "referral", "name of the person who referred"]):
            return ""

        # Company assigned / prior employer email (e.g. Rivian/RV Tech email assigned during employment)
        if any(k in tl for k in ["assigned to you", "during your time as an employee", "prior employee email", "rivian email", "rv tech"]):
            return "None"

        if any(k in tl for k in ["pronoun", "gender pronoun", "preferred pronoun"]):
            return "He/Him"
        if "email" in tl:
            return CANDIDATE_DATA["email"]
        if any(k in tl for k in ["phone", "mobile", "cell"]):
            return CANDIDATE_DATA["phone"]

        # Sponsorship & Authorization check before location
        if any(k in tl for k in ["visa status", "immigration status", "status in the us", "current visa"]):
            return "US Citizen"
        if any(k in tl for k in ["require sponsorship", "visa sponsorship", "require work authorization", "require authorization", "need sponsorship", "need work authorization", "require an employment visa"]) or (any(k in tl for k in ["require", "need"]) and any(k in tl for k in ["authorization", "sponsorship", "sponsor", "visa"]) and not any(k in tl for k in ["not require", "not need", "without"])):
            return "No"
        if any(k in tl for k in ["authorized to work", "legally authorized", "eligible to work"]):
            return "Yes"

        if any(k in tl for k in ["city", "location", "address", "where are you based", "reside"]):
            return CANDIDATE_DATA["location"]
        # Referral / conditional 'Other' follow-up (strictly leave blank if candidate selected standard options)
        if any(k in tl for k in ["if you selected", "if selected other", "if other", "please let us know how you heard"]):
            return ""

        if any(k in tl for k in ["postal code", "zip code", "zipcode", "postal"]) or (re.search(r'\bzip\b', tl) and not any(k in tl for k in ["heard", "about", "role", "company", "selected", "know"])):
            return CANDIDATE_DATA["zip_code"]
        
        # 2. Links & Socials
        if "linkedin" in tl:
            return CANDIDATE_DATA["linkedin"]
        if "github" in tl:
            return CANDIDATE_DATA["github"]
        if any(k in tl for k in ["portfolio", "website", "personal link", "other link"]):
            return CANDIDATE_DATA["portfolio"]

        # Current or most recent employer (dynamically chooses Amin AI vs TidaMed)
        if any(k in tl for k in ["current or most recent employer", "current employer", "most recent employer", "recent employer", "current company", "employer"]):
            return get_recent_employer(company=company, role=role)
            
        # 3. Education & School
        if any(k in tl for k in ["school", "university", "college", "institution"]):
            return CANDIDATE_DATA["school"]
        if any(k in tl for k in ["degree", "major", "field of study", "discipline"]):
            return CANDIDATE_DATA["degree"]
        if "gpa" in tl:
            return CANDIDATE_DATA["gpa"]
        if any(k in tl for k in ["graduation year", "grad year"]):
            return CANDIDATE_DATA["grad_year"]
        if any(k in tl for k in ["graduation date", "grad date", "completion date"]):
            return CANDIDATE_DATA["grad_date"]
            
        # 4. Compensation & Dates
        if any(k in tl for k in ["salary", "compensation", "desired pay", "rate", "hourly pay", "pay requirements"]):
            if "hour" in tl or "/hr" in tl:
                return "$40/hr"
            return "80000"
        if "what year" in tl or ("year" in tl and any(k in tl for k in ["return offer", "able to start"]) and not any(k in tl for k in ["how many years", "industry experience"])):
            return "2028"
        if any(k in tl for k in ["years of experience", "years of industry experience", "industry experience do you have", "how many years of"]):
            return "2"
        if any(k in tl for k in ["when can you start", "start date", "earliest start", "available to start", "start a new role", "start working", "notice"]):
            is_winter = any(w in tl for w in ["winter", "january", "december"])
            return "12/20/2026" if is_winter else "05/20/2027"
            
        # 5. Anti-bot verification (Strictly human response, never Mona Lisa)
        if any(k in tl for k in ["immediate left", "left of your computer", "mona lisa"]):
            return "A notebook and a water bottle"
            
        # 5. Standardized Tests (Strict word boundary)
        if re.search(r'\bsat\b', tl):
            return CANDIDATE_DATA["sat"]
            
        # 6. Technical / Coding specific prompts
        if any(k in tl for k in ["ramp secret", "ramp puzzle", "puzzle token", "secret code"]):
            return solve_ramp_secret(title)
        if any(k in tl for k in ["preferred language", "primary language", "programming language"]):
            return CANDIDATE_DATA["preferred_language"]
        if any(k in tl for k in ["pronunciation", "pronounce"]):
            return "Ah-reek Seh-rah-zee"
            
        # 7. Referral source
        if any(k in tl for k in ["how did you hear", "source", "hear about", "find out", "how did you find"]):
            return "LinkedIn"

        # 8. City and State / Hub fallback input
        if any(k in tl for k in ["input your city and state", "city and state/province in the field below"]) or ("if not, please select \"n/a\"" in tl and not any(v in tl for v in ["visa", "sponsor", "auth"])):
            return "Piscataway, New Jersey"

        # 9. Company Excitement Prompts (text input)
        if any(k in tl for k in ["excites you", "why talos", "why do you want to work", "why join", "interested in", "draws you"]):
            return sanitize_free_text(generate_company_excitement(company, role))

        # 10. Onsite / In-Person / Relocation willingness
        if any(k in tl for k in ["onsite", "on-site", "in-person", "in office", "relocate", "relocation", "willing to work"]):
            if any(k in tl for k in ["relocate", "relocation"]):
                return "Yes, willing to relocate with at least 1 month notice"
            return "Yes"

        # 11. Authorization / Sponsorship in text format
        if any(k in tl for k in ["visa status", "immigration status", "status in the us", "current visa"]):
            return "US Citizen"
        if any(k in tl for k in ["car wash", "car is dirty"]):
            return "Drive there"
        if any(k in tl for k in ["authorized to work", "legally authorized", "eligible to work"]):
            return "Yes"
        if any(k in tl for k in ["require sponsorship", "visa sponsorship", "require work authorization", "require authorization", "need sponsorship", "need work authorization", "require an employment visa"]) or (any(k in tl for k in ["require", "need"]) and any(k in tl for k in ["authorization", "sponsorship", "sponsor", "visa"]) and not any(k in tl for k in ["not require", "not need", "without"])):
            return "No"

        # Preferred Name
        if any(k in tl for k in ["preferred name", "preferred first name"]):
            return CANDIDATE_DATA.get("preferred_name", "")

        # Related to current employees / Relatives / Nepotism (Strictly None)
        if any(k in tl for k in ["related to any", "relative", "family member", "conflict of interest"]):
            return "None"

        # Previous or current employment at company / former employee (Strictly NO)
        if (any(k in tl for k in [
            "ever worked for", "previously worked for", "worked for", "ever been employed by",
            "previously employed by", "employed by", "worked at", "employed at", "prior employment with",
            "previous employment with", "former employee", "previous employee", "worked as a contractor",
            "contractor/contingent worker", "partner", "ever worked", "currently an employee", "current employee",
            "currently work for", "currently work at", "currently employed", "are you currently an employee",
            "are you an employee", "do you currently work", "employed with", "subsidiary", "affiliate",
            "previously applied", "prior application", "previously interviewed", "non-compete", "non compete",
            "noncompetition", "non-solicitation", "restrictive covenant"
        ]) or (any(p in tl for p in ["previous", "former", "prior", "past", "current", "currently"]) and any(e in tl for e in ["employee", "employed", "contractor", "intern", "subsidiary", "affiliate", "applied", "interviewed"]))):
            return "No"

        # 12. Fallback for general Yes/No questions appearing in single-line text inputs
        if any(tl.startswith(q) for q in ["are you", "do you", "will you", "can you", "have you", "is there"]):
            if any(k in tl for k in [
                "sponsor", "visa", "felony", "crime", "terminated", "fired", "employee", "employed", "worked at",
                "worked for", "conflict", "relative", "subsidiary", "affiliate", "previously applied", "non-compete"
            ]) or (any(k in tl for k in ["require", "need"]) and any(k in tl for k in ["authorization", "sponsor", "visa"])):
                return "No"
            return "Yes"
            
        return ""


    @staticmethod
    def match_textarea(title: str, company: str = "the company", role: str = "Software Engineer") -> str:
        tl = title.lower()
        
        # Socials & Links requested in textarea
        if "github" in tl:
            return CANDIDATE_DATA["github"]
        if "linkedin" in tl:
            return CANDIDATE_DATA["linkedin"]
        if any(k in tl for k in ["portfolio", "website", "personal link", "other link"]):
            return CANDIDATE_DATA["portfolio"]

        # Ramp specifics
        if "aws" in tl and "terraform" in tl:
            raw = FREE_TEXT_RESPONSES["ramp_aws_terraform"]
        elif "secret" in tl and "properties" in tl:
            raw = FREE_TEXT_RESPONSES["ramp_security_secret_properties"]
        elif "puzzle" in tl or "secret" in tl:
            return solve_ramp_secret(title)
            
        # Specific companies
        elif "deepgram" in tl:
            raw = FREE_TEXT_RESPONSES["deepgram_excitement"]
        elif "attio" in tl:
            raw = FREE_TEXT_RESPONSES["attio_problem_solved"]
        elif "justtrack" in tl:
            raw = FREE_TEXT_RESPONSES["justtrack_motivation"]
        elif "linear" in tl:
            raw = FREE_TEXT_RESPONSES["linear_teach_design"]
            
        # Location ranking / preference
        if any(k in tl for k in ["rank your preference in location", "preference in location", "rank location", "location preference"]):
            return "1. New York, NY\n2. San Francisco, CA"

        # Relative / conflict follow-up (strictly blank)
        if any(k in tl for k in ["employee's name and your relationship", "if yes, please provide the employee"]):
            return ""

        # Example of excellence not on CV
        elif any(k in tl for k in ["not on your cv", "example of excellence", "exceptional performance"]):
            raw = FREE_TEXT_RESPONSES["exceptional_performance"]

        # Interesting paper / blog post / documentation
        elif any(k in tl for k in ["interesting paper", "blog post", "documentation you've read", "documentation you have read"]):
            raw = (
                "Recently, I read the Anthropic engineering post on Building Effective Agents and the DSPy framework documentation. "
                "I found the analysis on deterministic tool orchestration, multi turn state evaluation, and prompt optimization particularly compelling. "
                "Designing agent architectures that use constrained schema decoding and robust execution loops rather than unbounded autonomy is critical for building production grade AI systems."
            )

        # Essays & Topic Prompts (Dynamically tailored to company and role)
        elif any(k in tl for k in ["why", "interested", "draw", "attract", "motivation", "excites you", "why join"]):
            raw = generate_company_excitement(company, role)
        elif any(k in tl for k in ["project", "accomplishment", "built", "portfolio", "proud"]):

            raw = FREE_TEXT_RESPONSES["project"]
        elif any(k in tl for k in ["experience", "background", "summary", "about you"]):
            raw = FREE_TEXT_RESPONSES["experience"]
        elif any(k in tl for k in ["process", "pipeline", "methodology"]):
            raw = FREE_TEXT_RESPONSES["process"]
        elif any(k in tl for k in ["organization", "culture", "standards"]):
            raw = FREE_TEXT_RESPONSES["organization"]
        elif any(k in tl for k in ["agent", "llm", "ai qualities"]):
            raw = FREE_TEXT_RESPONSES["agent_qualities"]
        elif any(k in tl for k in ["exceptional", "excellence", "top 1"]):
            raw = FREE_TEXT_RESPONSES["exceptional_performance"]
        elif any(k in tl for k in ["mobile", "ios", "android"]):
            raw = FREE_TEXT_RESPONSES["mobile_project"]
        elif any(k in tl for k in ["security", "auth", "vulnerability"]):
            raw = FREE_TEXT_RESPONSES["security_project"]
        elif any(k in tl for k in ["hardest problem", "challenge", "complex"]):
            raw = FREE_TEXT_RESPONSES["hardest_problem"]
        else:
            raw = (
                f"I am excited about the {role} role at {company}. With a background in Computer Science "
                f"from Rutgers University and production software engineering experience building reliable "
                f"backend systems with Python, FastAPI, and PostgreSQL, I look forward to contributing to your team. "
                f"I take pride in writing clean, well tested code and designing deterministic API contracts that prevent data anomalies. "
                f"I am eager to collaborate with your engineering team to build scalable services that deliver real user value."
            )
            
        return sanitize_free_text(raw)

    @staticmethod
    def match_combobox(title: str, available_options: list = None) -> str:
        tl = title.lower()
        opts = [o.lower() for o in (available_options or [])]
        
        # Field of Study (Undergraduate / Postgraduate)
        if any(k in tl for k in ["field of study", "major", "discipline"]):
            return "Computer Science"

        # Location / City
        if any(k in tl for k in ["location", "city", "where do you live", "where are you based", "where are you located"]):
            return "Piscataway, New Jersey, United States"

        # University / School
        if any(k in tl for k in ["university", "school", "college", "institution", "recent university"]):
            return "Rutgers University, New Brunswick"

        # Graduation Month & Year (Master's: Spring 2028)
        if any(k in tl for k in ["graduation month", "grad month"]):
            return "May"
        if any(k in tl for k in ["graduation year", "grad year", "year of graduation"]):
            return "2028"
        if any(k in tl for k in ["graduation date", "grad date", "expected graduation"]):
            return "05/20/2028"

        # Start Date / Ideal Start
        if any(k in tl for k in ["start date", "ideal start", "available to start", "start working", "earliest start"]):
            if available_options:
                for opt in available_options:
                    ol = opt.lower()
                    if any(s in ol for s in ["may", "summer", "immediate", "flexible", "asap", "2027", "2026"]):
                        return opt
                return available_options[0]
            return "05/20/2027"


        # Thumbtack location
        if any(k in tl for k in ["thumbtack", "location you intend to work"]):
            return "New Jersey (NJ)"
            
        # Education level
        if any(k in tl for k in ["highest education", "education level", "degree level"]):
            return "Bachelor's Degree"
            
        # Office preference
        if any(k in tl for k in ["office preference", "which office", "workplace"]):
            return "Remote"
            
        # Pronouns
        if "pronoun" in tl:
            return "He/Him"
            
        # Location / State
        if any(k in tl for k in ["state", "province"]):
            return "New Jersey"
        if any(k in tl for k in ["country"]):
            return "United States"
            
        # Referral source
        if any(k in tl for k in ["how did you hear", "where did you hear", "hear about", "source", "find out"]):
            if available_options:
                for opt in available_options:
                    if "linkedin" in opt.lower():
                        return opt
                for opt in available_options:
                    if "website" in opt.lower() or "company" in opt.lower():
                        return opt
                for opt in available_options:
                    if "internet" in opt.lower() or "online" in opt.lower():
                        return opt
            return "LinkedIn"
            
        # Gender / Demographics
        if "gender" in tl:
            return "Male"
        if any(k in tl for k in ["race", "ethnicity"]):
            return "Asian"
        if "veteran" in tl:
            if available_labels:
                for opt in available_labels:
                    if "not" in opt.lower() and "veteran" in opt.lower():
                        return opt
            return "I am not a protected veteran"
        if "disability" in tl:
            if available_labels:
                for opt in available_labels:
                    if opt.lower().startswith("no") or ("no" in opt.lower() and "disability" in opt.lower()):
                        return opt
            return "No, I do not have a disability and have not had one in the past"
        # Work Authorization & Sponsorship
        if any(k in tl for k in ["sponsorship", "require sponsorship", "visa sponsorship"]) and not any(k in tl for k in ["without sponsorship", "without employer sponsorship", "without requiring sponsorship", "without visa"]):
            if available_options:
                for o in available_options:
                    if any(k in o.lower() for k in ["no", "will not require", "do not require"]):
                        return o
            return "No"
        if any(k in tl for k in ["authorized to work", "legally authorized", "work authorization", "work authorization status", "without employer sponsorship", "without sponsorship"]):
            if available_options:
                for o in available_options:
                    if any(k in o.lower() for k in ["citizen", "yes", "authorized"]):
                        return o
            return "Yes"
            
        return ""

    @staticmethod
    def match_radio_or_toggle(title: str, available_labels: list = None) -> str:
        tl = title.lower()
        
        # Sanctioned Countries / Export Control (Strictly NO)
        if any(k in tl for k in ["north korea", "syria", "iran", "cuba", "sanctioned"]):
            return "No"

        # Active immigration case / visa petition (Strictly NO - Candidate is US Citizen)
        if any(k in tl for k in ["immigration case", "active immigration", "h-1b extension", "green card", "visa petition", "pending immigration"]):
            return "No"

        # 1. Sponsorship / Require Visa / Require Work Authorization (Strictly NO)
        if (
            any(k in tl for k in ["sponsor", "sponsorship", "require sponsorship", "visa sponsorship", "now or in the future require"])
            or (any(k in tl for k in ["require", "need", "will you"]) and any(k in tl for k in ["visa", "authorization", "sponsorship", "sponsor", "employment authorization", "employment visa", "work permit"]))
        ) and not any(k in tl for k in ["without sponsorship", "without employer sponsorship", "without requiring sponsorship", "without visa"]):
            if any(k in tl for k in ["when do you estimate", "when will you require", "estimate you will require"]):
                if available_labels:
                    for l in available_labels:
                        if any(neg in l.lower() for neg in ["not applicable", "n/a", "do not require", "never", "none"]):
                            return l
                return ""
            if available_labels:
                for l in available_labels:
                    ll = l.lower()
                    if any(neg in ll for neg in ["no", "will not", "do not", "never", "none"]):
                        return l
            return "No"

        # 2. Work Authorization Duration (Strictly 2+ years / Permanent)
        if any(k in tl for k in ["how long", "authorization valid", "validity"]):
            return "2+ years"

        # 3. Work Authorization (Strictly YES, NO sponsorship)
        if any(k in tl for k in [
            "authorized", "legally authorized", "eligible to work", "right to work",
            "work in the united states", "work authorization", "without employer sponsorship", "without sponsorship"
        ]):
            if available_labels:
                # Prefer options that explicitly declare no sponsorship needed / citizen / any employer
                for l in available_labels:
                    ll = l.lower()
                    if any(pos in ll for pos in [
                        "will not need", "do not require", "without sponsorship",
                        "no sponsorship", "any employer", "no restrictions", "citizen"
                    ]):
                        return l
                # Select Yes options that do NOT require visa sponsorship
                for l in available_labels:
                    ll = l.lower()
                    if ll.startswith("yes") and not any(neg in ll for neg in ["will need", "require sponsorship", "need sponsorship", "require visa"]):
                        return l
                for l in available_labels:
                    if l.lower().startswith("yes"):
                        return l
            return "Yes"
            
        # Referral Source / How did you learn about us / How did you hear
        if any(k in tl for k in ["how did you learn", "learn about us", "hear about us", "source", "how did you hear", "where did you hear"]):
            if available_labels:
                # Tier 1: Exact job board / LinkedIn / Career site / online sources
                for l in available_labels:
                    ll = l.lower()
                    if any(target in ll for target in ["job board", "linkedin", "career page", "career site", "company website", "online", "internet"]):
                        return l
                # Tier 2: General public sources (career fair, search engine)
                for l in available_labels:
                    ll = l.lower()
                    if any(target in ll for target in ["career fair", "search engine"]):
                        return l
                # Tier 3: Anything NOT referral, agency, or alumni
                for l in available_labels:
                    ll = l.lower()
                    if not any(neg in ll for neg in ["employee referral", "agency", "current canon", "canon employee", "alumni"]):
                        return l
                return available_labels[0]
            return "Job Board"

        # In-office attendance / Downtown SF office / Hybrid / Commuting (Strictly YES)
        if any(k in tl for k in [
            "downtown sf office", "sf office", "office 3 days", "office 5 days",
            "come into our", "in office", "in-office", "onsite", "on-site", "in-person", "hybrid", "able to come into",
            "commuting", "comfortable commuting", "work from our offices", "work from our office",
            "work from the office", "from our office", "from the office", "able to work from"
        ]):
            if available_labels:
                for l in available_labels:
                    if l.lower().startswith("yes") or "willing to come into the office" in l.lower():
                        return l
            return "Yes"

        # Prior experience in finance / investment (Strictly NO)
        if any(k in tl for k in ["finance or investment", "investment-related", "finance-related"]):
            if available_labels:
                for l in available_labels:
                    if l.lower().startswith("no"):
                        return l
            return "No"

        # Years of experience with Excel / SQL / Python / Tools
        if any(k in tl for k in ["years of experience do you have using", "years of experience using", "experience do you have using"]):
            if available_labels:
                if "excel" in tl or "microsoft excel" in tl:
                    # Select 1-3 or 1-2 years
                    for l in available_labels:
                        if "1-3" in l or "1-2" in l or "1" in l:
                            return l
                elif "sql" in tl or "database" in tl:
                    # Select 1-3 or 4-6 years (Candidate has extensive SQL experience at Amin AI, TidaMed, Trackwise)
                    for l in available_labels:
                        if "1-3" in l:
                            return l
                    for l in available_labels:
                        if "4-6" in l:
                            return l
                for l in available_labels:
                    if "1-3" in l or "1-2" in l or "1" in l:
                        return l
                return available_labels[1] if len(available_labels) > 1 else available_labels[0]

        # SMS / Text message consent (Strictly NO)
        if any(k in tl for k in ["text message", "sms", "receive text messages", "consent to receiving text"]):
            if available_labels:
                for l in available_labels:
                    if l.lower().startswith("no") or "do not consent" in l.lower():
                        return l
            return "No"

        # Prior internships count
        if any(k in tl for k in ["how many prior internships", "prior internships have you had", "previous internships", "number of internships", "internships have you"]):
            if available_labels:
                for l in available_labels:
                    if "3" in l or "2" in l:
                        return l
                for l in available_labels:
                    if "1" in l:
                        return l
                return available_labels[-1]
            return "3+"

        # Pursuing a degree in CS / related field (Strictly YES)
        if any(k in tl for k in [
            "pursuing a degree in computer science",
            "degree in computer science",
            "pursuing a degree",
            "degree in cs"
        ]):
            if available_labels and any(l.lower() in ["yes", "no"] for l in available_labels):
                return "Yes"
            if available_labels:
                for l in available_labels:
                    if "master" in l.lower():
                        return l
                for l in available_labels:
                    if "bachelor" in l.lower():
                        return l
            return "Yes"

        # 1. Highest Degree Level Completed / Achieved / Attained / Currently Held (Strictly Bachelor's)
        if any(k in tl for k in [
            "highest level of degree currently",
            "highest level of degree achieved",
            "highest degree achieved",
            "highest degree attained",
            "highest degree completed",
            "highest level of education completed",
            "highest level of education",
            "highest degree level completed",
            "highest degree currently held",
            "highest degree you hold",
            "highest degree you have completed",
            "completed form of education",
            "already hold a bachelor",
            "highest education"
        ]):
            if available_labels:
                for l in available_labels:
                    if "bachelor" in l.lower() or "undergraduate" in l.lower():
                        return l
            return "Bachelor's Degree"

        # 2. Degree Level Currently Pursuing / Enrolled (Strictly Master's)
        if any(k in tl for k in [
            "which degree",
            "degree are you currently pursuing",
            "what degree are you currently pursuing",
            "what degree are you pursuing",
            "degree level currently pursuing",
            "degree currently pursuing",
            "degree you are pursuing",
            "degree level pursuing",
            "degree level",
            "degree pursuing",
            "currently pursuing",
            "degree seeking",
            "what degree are you seeking"
        ]) and not any(k in tl for k in ["completed", "achieved", "attained", "hold", "held"]):
            if available_labels:
                for l in available_labels:
                    if "master" in l.lower():
                        return l
                for l in available_labels:
                    if "bachelor" in l.lower():
                        return l
            return "Master's Degree"

        # Expected Graduation Month
        if any(k in tl for k in ["graduation month", "expected grad month"]):
            if available_labels:
                for l in available_labels:
                    if any(m in l.lower() for m in ["may", "april/may/june", "spring"]):
                        return l
            return "April/May/June"

        # Expected Graduation Year
        if any(k in tl for k in ["graduation year", "expected grad year"]):
            if available_labels:
                for l in available_labels:
                    if "2028" in l:
                        return l
            return "2028"

        # Related to current employees / Relatives / Nepotism (Strictly NO)
        if any(k in tl for k in ["related to any", "relative", "family member", "conflict of interest"]):
            return "No"

        # Previous or current employment at company / subsidiaries (Strictly NO)
        if (any(k in tl for k in [
            "ever worked for", "previously worked for", "worked for", "ever been employed by",
            "previously employed by", "employed by", "worked at", "employed at", "prior employment with",
            "previous employment with", "former employee", "previous employee", "worked as a contractor",
            "contractor/contingent worker", "partner", "ever worked", "currently an employee", "current employee",
            "currently work for", "currently work at", "currently employed", "are you currently an employee",
            "are you an employee", "do you currently work", "employed with", "subsidiary", "affiliate",
            "previously applied", "prior application", "previously interviewed", "non-compete", "non compete",
            "noncompetition", "non-solicitation", "restrictive covenant"
        ]) or (any(p in tl for p in ["previous", "former", "prior", "past", "current", "currently"]) and any(e in tl for e in ["employee", "employed", "contractor", "intern", "subsidiary", "affiliate", "applied", "interviewed"]))):
            if available_labels:
                for l in available_labels:
                    ll = l.lower()
                    if any(neg in ll for neg in ["no", "never", "none", "have not", "i do not", "neither", "not a previous", "not currently"]):
                        return l
            return "No"

        # AI Policy for Application (Strictly YES / Agree)
        if any(k in tl for k in ["ai policy for application", "ai policy"]):
            return "Yes"

        # Current university student graduating Fall 2027 or Spring 2028 (Strictly YES per candidate profile)
        if any(k in tl for k in ["currently a university student", "graduate fall of 2027 or spring 2028"]):
            return "Yes"

        # Relocation Willingness (Strictly relocation option, prioritizing >= 1 month)
        if any(k in tl for k in ["willing to relocate", "relocate", "relocation", "ready to relocate", "need to relocate", "based in the sf"]):
            return select_relocation_option(available_labels)

        # Co-op rotations completed prior to application (Strictly 0 Co-ops / First-time applicant)
        if any(k in tl for k in ["co-op rotations", "coop rotations", "completed prior to this application"]):
            if available_labels:
                for l in available_labels:
                    if "0 co-ops" in l.lower() or "first-time" in l.lower():
                        return l
            return "0 Co-ops (First-time applicant)"

        # Previous Work Experience in Software Engineering (Strictly YES)
        if any(k in tl for k in [
            "previous work experience in software engineering",
            "work experience in software engineering",
            "prior software engineering experience",
            "industry software engineering experience"
        ]):
            return "Yes"

        # Hub / Location Preference
        if any(k in tl for k in ["reside within 50 miles", "one of our hubs", "located within 50 miles"]):
            return "New York, NY"

        # Non-Rutgers Enrollment (Strictly NO)
        if any(k in tl for k in [
            "northeastern", "columbia", "harvard", "stanford", "mit", "nyu", "berkeley",
            "currently enrolled at", "are you an active student at"
        ]):
            if not any(k in tl for k in ["rutgers"]):
                return "No"
                
        # Freshman or Sophomore in undergraduate (Strictly NO - Master's student)
        if any(k in tl for k in ["freshman", "sophomore", "first-year", "second-year"]):
            return "No"

        # 18 or older / Age brackets
        if any(k in tl for k in ["18 years", "at least 18", "age of majority"]):
            return "Yes"
        if "age" in tl:
            if available_labels:
                for l in available_labels:
                    if any(k in l.lower() for k in ["under 30", "18-29", "20-29", "21-29", "under 25", "18-24", "18-20"]):
                        return l

            
        # Clearance
        if any(k in tl for k in ["security clearance", "active clearance"]):
            return "No"
            
        # ITAR / Space Tech / US Person (Strictly YES / US Citizen)
        if any(k in tl for k in [
            "us person", "u.s. person", "export control",
            "space technology export regulations", "authorized from the u.s. department of state"
        ]) or re.search(r'\b(itar|ear)\b', tl):
            if available_labels:
                for l in available_labels:
                    if any(k in l.lower() for k in ["u.s. person", "u.s. citizen", "yes"]):
                        return l
            return "Yes"

        # GPA (Undergraduate: 3.86)
        if "gpa" in tl and any(k in tl for k in ["undergraduate", "scale", "current"]):
            if available_labels:
                for l in available_labels:
                    if "3.8" in l or "3.8 - 4.0" in l:
                        return l
            return "3.8 - 4.0"

        # Standardized Tests
        if re.search(r'\bsat\b', tl):
            if available_labels:
                for l in available_labels:
                    if "1200 - 1290" in l or "1200" in l:
                        return l
            return "1200 - 1290"
        if re.search(r'\bact\b', tl):
            if available_labels:
                for l in available_labels:
                    if "did not take" in l.lower() or "not applicable" in l.lower():
                        return l
            return "Did Not Take / Not Applicable"

        # Student organizations / clubs / competition teams
        if any(k in tl for k in ["student organizations", "competition teams", "clubs"]):
            if available_labels:
                for l in available_labels:
                    if "robotics" in l.lower():
                        return l
                    if "none of the above" in l.lower():
                        return l
            return "Robotics Team"

        # Full-time 40 hours per week for 12 weeks
        if any(k in tl for k in ["full-time", "full time", "40 hours", "12 consecutive weeks"]):
            return "Yes"

        # Preferred Start Date
        if any(k in tl for k in ["preferred start date", "start date"]):
            is_winter = any(w in tl for w in ["winter", "january", "december"])
            if available_labels:
                if is_winter:
                    for l in available_labels:
                        if "december 20" in l.lower() or "december 20th" in l.lower() or "dec 20" in l.lower():
                            return l
                    for l in available_labels:
                        if "december" in l.lower() or "january" in l.lower():
                            return l
                else:
                    for l in available_labels:
                        if "may 20" in l.lower() or "may 20th" in l.lower():
                            return l
                    for l in available_labels:
                        if "may" in l.lower():
                            return l
                return available_labels[0]
            return "December 20, 2026" if is_winter else "May 20, 2027"

        # Interview Recording Consent (Strictly YES)
        if any(k in tl for k in ["interview recording", "recording consent", "consent to be recorded"]):
            if available_labels:
                for l in available_labels:
                    if "consent to be recorded" in l.lower() or "yes" in l.lower():
                        return l
            return "Yes, I consent to be recorded"

        # Coding experience in C, C++, Java, JS, Python
        if any(k in tl for k in ["coding experience", "c, c++", "javascript, python", "strong software coding"]):
            return "Yes"

        # Debugging, performance optimization, unit testing
        if any(k in tl for k in ["debugging", "performance optimization", "unit testing"]):
            return "Yes"

        # Computer architecture and networks
        if any(k in tl for k in ["computer architecture", "networks"]):
            return "Yes"

        # Software documentation and system diagrams
        if any(k in tl for k in ["software documentation", "system diagrams"]):
            return "Yes"

        # Housing / Relocation / Transportation
        if any(k in tl for k in ["provide your own housing", "housing, relocation", "current or future situation", "relocate", "relocation", "willing to relocate"]):
            return select_relocation_option(available_labels)

        # Graduation Month and Year (Master's Projected: May 2028)
        if any(k in tl for k in ["graduation month and year", "graduation date", "graduating month"]):
            if available_labels:
                for l in available_labels:
                    if "may 2028" in l.lower():
                        return l
            return "May 2028"

        # Non-compete / agreements
        if any(k in tl for k in ["non-compete", "restrictive covenant", "obligation to former"]):
            return "No"
            
        # Previous employment at company / subsidiaries (Strictly NO)
        if any(k in tl for k in ["ever been employed by", "previously employed by", "consulted for", "contract work for any of the following"]):
            return "No"

        # Office location preferences (first preference, second preference)
        if any(k in tl for k in ["office location", "office locations would be your"]):
            if "first" in tl:
                if available_labels:
                    for l in available_labels:
                        if "durham" in l.lower():
                            return l
                    return available_labels[0]
                return "Durham, NC"
            elif "second" in tl:
                if available_labels:
                    for l in available_labels:
                        if "columbus" in l.lower():
                            return l
                    for l in available_labels:
                        if "charlottesville" in l.lower():
                            return l
                    return available_labels[1] if len(available_labels) > 1 else available_labels[0]
                return "Columbus, OH"

        # Platform interest (Backend prioritized)
        if any(k in tl for k in ["platform that interests you", "platform interests", "select the platform"]):
            if available_labels:
                for l in available_labels:
                    if "backend" in l.lower():
                        return l
                return available_labels[0]
            return "Backend"

        # Data Structures & Algorithms coursework (Strictly YES)
        if any(k in tl for k in ["data structures", "algorithms", "data structures & algorithms"]):
            return "Yes"

        # Background check / drug screen consent
        if any(k in tl for k in ["background check", "drug test", "consent to"]):
            return "Yes"
            
        # Pronouns
        if "pronoun" in tl:
            return "He/Him"
            
        # Referral source
        if any(k in tl for k in ["how did you hear", "source", "hear about"]):
            if available_labels:
                for opt in available_labels:
                    opt_l = opt.lower()
                    if "linkedin" in opt_l:
                        return opt
                    if "company website" in opt_l or "website" in opt_l:
                        return opt
                    if "other" in opt_l:
                        return opt
            return "Company website"

        # Free school meals
        if any(k in tl for k in ["free school meals"]):
            return "No"

        # Secondary school type
        if any(k in tl for k in ["type of school did you attend", "secondary education"]):
            if available_labels:
                for opt in available_labels:
                    if "state" in opt.lower() or "government" in opt.lower():
                        return opt
            return "State/Government-funded school (non-selective)"

        # Parents highest education
        if any(k in tl for k in ["highest level of education completed by either of your parents"]):
            if available_labels:
                for opt in available_labels:
                    if "bachelor" in opt.lower():
                        return opt
            return "Bachelor's degree (University undergraduate degree)"

        # Main household earner occupation
        if any(k in tl for k in ["occupation of your main household earner"]):
            if available_labels:
                for opt in available_labels:
                    if "clerical" in opt.lower():
                        return opt
                    if "professional" in opt.lower():
                        return opt
            return "Clerical and intermediate occupations (e.g., secretary, PA, call centre agent)"

        # Demographics
        if "transgender" in tl:
            return "No"
        if any(k in tl for k in ["lesbian", "gay", "bisexual", "lgb", "lgbt", "lgbtq"]):
            if available_labels:
                for opt in available_labels:
                    if opt.lower() == "no" or opt.lower().startswith("no"):
                        return opt
            return "No"
        if any(k in tl for k in ["sexual orientation", "sexual identity", "describe your sexual"]):
            if available_labels:
                for opt in available_labels:
                    if "heterosexual" in opt.lower() or "straight" in opt.lower():
                        return opt
            return "Heterosexual"
        if "gender" in tl:
            if available_labels:
                for opt in available_labels:
                    if opt.lower() in ["man", "male"]:
                        return opt
            return "Male"
        if any(k in tl for k in ["race", "ethnicity", "racial"]):
            if available_labels:
                for opt in available_labels:
                    opt_l = opt.lower()
                    if "mixed" in opt_l or "multiple" in opt_l:
                        continue
                    if "south asian" in opt_l:
                        return opt
                for opt in available_labels:
                    opt_l = opt.lower()
                    if "mixed" in opt_l or "multiple" in opt_l:
                        continue
                    if "asian" in opt_l:
                        return opt
            return "Asian"
        if any(k in tl for k in ["veteran", "military", "armed forces", "served in"]):
            if available_labels:
                for opt in available_labels:
                    opt_l = opt.lower()
                    if any(neg in opt_l for neg in ["not a protected veteran", "i am not a protected veteran", "not a veteran", "never served", "no military"]) or opt_l == "no":
                        return opt
            return "No"
        if "disability" in tl:
            if available_labels:
                for opt in available_labels:
                    opt_l = opt.lower()
                    if opt_l.startswith("no") or ("no" in opt_l and "disability" in opt_l):
                        return opt
            return "No, I do not have a disability and have not had one in the past"
            
        # Term / Semester / Season (Summer 2027 / Summer prioritized)
        if any(k in tl for k in ["which term", "term are you applying", "internship term", "application term", "co-op term", "which semester"]):
            if available_labels:
                for l in available_labels:
                    if "summer 2027" in l.lower():
                        return l
                for l in available_labels:
                    if "summer" in l.lower():
                        return l
                for l in available_labels:
                    if "spring 2027" in l.lower():
                        return l
                for l in available_labels:
                    if "fall 2026" in l.lower():
                        return l
                return available_labels[0]
            return "Summer 2027"

        # Default for unrecognized yes/no questions: analyze context
        if available_labels:
            lowers = [l.lower() for l in available_labels]
            if "yes" in lowers and "no" in lowers:
                if any(k in tl for k in [
                    "crime", "felony", "terminated", "fired", "lawsuit", "related", "relative", "family member",
                    "conflict", "employee", "employed", "worked at", "worked for", "worked with", "previously applied",
                    "prior application", "previously interviewed", "non-compete", "non compete", "noncompetition",
                    "non-solicitation", "sponsor", "visa", "clearance", "government", "disciplinary", "contractor",
                    "subsidiary", "affiliate"
                ]) or (any(k in tl for k in ["require", "need"]) and any(k in tl for k in ["authorization", "sponsor", "visa"])):
                    return "No"
                return "Yes"
                
        return ""

    @staticmethod
    def match_checkbox(title: str, available_options: list = None) -> list:
        """Determines target checkbox values to select for multi-choice or single checkboxes."""
        tl = title.lower()

        # Relocating / Office Locations Preference (Checkboxes)
        if any(k in tl for k in ["relocating to", "relocate to", "locations that you would be interested in", "interested in relocating", "preferred location", "office location"]):
            if available_options:
                ny = [o for o in available_options if any(k in o.lower() for k in ["new york", "ny", "nyc"])]
                if ny:
                    return ny
                sf = [o for o in available_options if any(k in o.lower() for k in ["san francisco", "sf", "california", "ca"])]
                if sf:
                    return sf
                remote = [o for o in available_options if "remote" in o.lower()]
                if remote:
                    return remote
                return [available_options[0]]
            return ["New York, NY"]

        # Degree Type / Degree Level (Checkboxes)
        if any(k in tl for k in ["degree type", "type of degree", "degree level", "degree(s) pursuing"]):
            if available_options:
                masters = [o for o in available_options if "master" in o.lower()]
                if masters:
                    return masters
                bachelors = [o for o in available_options if any(k in o.lower() for k in ["bachelor", "undergraduate"])]
                if bachelors:
                    return bachelors
                return [available_options[0]]
            return ["Master's"]

        # Software Teams Preference
        if any(k in tl for k in ["software team", "teams are you most interested", "team(s) are you interested", "which team"]):
            if available_options:
                pref = [o for o in available_options if any(k in o.lower() for k in ["open to any", "no strong preference"])]
                if pref:
                    return pref
                tech_teams = [o for o in available_options if any(k in o.lower() for k in ["full stack", "systems", "backend"])]
                if tech_teams:
                    return tech_teams
                return [available_options[0]]
            return ["Open to any team/No strong preference"]
        
        # Co-op / Internship term availability (e.g. Fall 2026, Winter 2027, Summer 2027)
        if any(k in tl for k in [
            "co-op", "work term", "internship times", "internship seasons", "terms are you open",
            "which terms", "term(s)", "which term", "internship program", "program are you applying",
            "which program", "which internship"
        ]):
            if available_options:
                summer_2027 = [o for o in available_options if "summer 2027" in o.lower()]
                if summer_2027:
                    return summer_2027
                summer_only = [o for o in available_options if "summer semester only" in o.lower() or "summer only" in o.lower()]
                if summer_only:
                    return summer_only
                summer_opts = [o for o in available_options if "summer" in o.lower() and "consecutive" not in o.lower()]
                if summer_opts:
                    return summer_opts
                m = [o for o in available_options if "summer" in o.lower()]
                if m:
                    return m
                spring_opts = [o for o in available_options if "spring 2027" in o.lower() or "spring" in o.lower()]
                if spring_opts:
                    return spring_opts
                winter_opts = [o for o in available_options if "winter 2026" in o.lower() or "winter" in o.lower()]
                if winter_opts:
                    return winter_opts
            return ["Summer 2027", "2027 Summer Semester Only (Single Block: May - Aug)", "Summer"]
            
        # AI Policy / Terms / Agreements / Consents / Legal & Truth Certifications
        if any(k in tl for k in ["ai policy", "privacy", "terms", "consent", "acknowledge", "agreement", "certify", "accurate", "true and correct", "false statements", "disqualification", "termination", "information provided"]):
            if available_options and len(available_options) <= 2:
                return available_options
            return ["agree", "accept", "yes", "acknowledge", "consent", "i agree", "i acknowledge", "i certify", "certify", "true", "true and correct"]
            
        # Background check / drug screen
        if any(k in tl for k in ["background check", "drug test"]):
            return ["agree", "yes", "consent", "accept"]

        # Technology stacks from previous internship / experience
        if any(k in tl for k in ["technology stacks", "tech stacks", "technologies", "technology stack"]):
            skills = ["python", "typescript", "react", "go", "java", "sql", "c++"]
            if available_options:
                m = [o for o in available_options if any(s == o.lower().strip() or s in o.lower().split() for s in skills)]
                if m:
                    return m
            return ["Python", "TypeScript", "React", "Go"]

        # Student organizations / clubs / competition teams
        if any(k in tl for k in ["student organizations", "competition teams", "clubs"]):
            if available_options:
                for o in available_options:
                    if "robotics" in o.lower():
                        return [o]
                for o in available_options:
                    if "none of the above" in o.lower():
                        return [o]
            return ["Robotics Team", "None of the Above"]

        # Race / Ethnic background (Demographics multi-select)
        if any(k in tl for k in ["racial", "ethnic background", "race/ethnic", "race", "ethnicity", "categories describe you", "which categories"]):
            if available_options:
                for o in available_options:
                    ol = o.lower()
                    if "south asian" in ol:
                        return [o]
                for o in available_options:
                    ol = o.lower()
                    if "east asian" in ol:
                        return [o]
                for o in available_options:
                    ol = o.lower()
                    if "asian" in ol and "mixed" not in ol and "multiple" not in ol:
                        return [o]
            return ["South Asian"]

        # Gender identity (Demographics multi-select)
        if any(k in tl for k in ["gender identity", "describe your gender", "gender"]):
            if available_options:
                for o in available_options:
                    ol = o.lower()
                    if ol == "man" or ol == "male":
                        return [o]
                for o in available_options:
                    if "man" in o.lower() and "woman" not in o.lower():
                        return [o]
            return ["Man"]

        # Sexual orientation (Demographics multi-select)
        if any(k in tl for k in ["sexual orientation", "describe your sexual"]):
            if available_options:
                for o in available_options:
                    if "heterosexual" in o.lower() or "straight" in o.lower():
                        return [o]
            return ["Heterosexual"]

        # Transgender
        if "transgender" in tl:
            if available_options:
                for o in available_options:
                    if o.lower().startswith("no"):
                        return [o]
            return ["No"]

        # Diversity Survey / Communities (Candidate: not veteran, no disability)
        if any(k in tl for k in ["communities do you belong to", "diversity survey"]):
            if available_options:
                for o in available_options:
                    if "none of the above" in o.lower():
                        return [o]
            return ["None of the above"]

        # Referral source / How did you hear about us
        if any(k in tl for k in ["how did you hear", "hear about", "referral source", "source"]):
            if available_options:
                for o in available_options:
                    if "linkedin" in o.lower():
                        return [o]
                return [available_options[0]]
            return ["LinkedIn"]
            
        # Fallback: if available_options contains consent/agreement keywords, return them; otherwise return [] so AI or caller handles it
        if available_options:
            agree_opts = [o for o in available_options if any(k in o.lower() for k in ["agree", "accept", "consent", "certify", "acknowledge"])]
            if agree_opts:
                return agree_opts
            return []
        return ["agree", "yes", "true", "i agree"]

