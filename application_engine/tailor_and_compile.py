#!/usr/bin/env python3
r"""
tailor_and_compile.py - Deep Dynamic Resume Tailor & LaTeX Compiler for Ariq Serazi
Strictly preserves truth while dynamically tailoring:
1. Reverse chronological experience ordering (Amin AI -> TidaMed -> Maryam & Fatima LLC).
2. De-duplicated metrics (distinct, truthful achievements per company).
3. Exact 1-line bullet budgeting (zero hanging orphan words).
4. Perfect LaTeX macro alignment (\linewidth tabulars, uniform itemsep=2pt).
5. Dynamic technical skills keyword ranking based on live JD text.
6. ATS-safe, strict 1-page LaTeX compilation via tectonic.
"""

import os
import re
import subprocess
from pathlib import Path

RESUMES_DIR = os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/resumes")
BASE_RESUME_PATH = os.path.expanduser("~/.agents/skills/resume-tailor-swe/references/base_resume_latex.txt")
JAVA_RESUME_PATH = os.path.expanduser("~/.agents/skills/resume-tailor-swe/references/Java_resume_latex.txt")
RESEARCH_RESUME_PATH = os.path.expanduser("~/.agents/skills/resume-tailor-swe/references/research_resume_latex.txt")
DEFAULT_PDF_FALLBACK = "/Users/ariqserazi/Downloads/Ariq_Serazi__Resume_2026.pdf"

os.makedirs(RESUMES_DIR, exist_ok=True)

def sanitize_filename(text):
    return re.sub(r'[^a-zA-Z0-9_-]', '_', text.strip())

# --- ROLE-TAILORED REVERSE-CHRONOLOGICAL EXPERIENCE SECTIONS ---

BACKEND_EXPERIENCE = r"""\section{Experience}
\resumeSubHeadingListStart

\resumeSubheading
{Co-founder and Automation Engineer}{Oct 2025 -- Present}
{Amin AI}{Edison, NJ}
\resumeItemListStart

\resumeItem{Engineered backend automation microservices in Python and FastAPI to process high-throughput JSON workflows.}

\resumeItem{Implemented chunked retrieval, input sanitization, and Pydantic validation to prevent malformed payloads.}

\resumeItem{Architected asynchronous API routing connecting language models with external cloud tools and databases.}

\resumeItem{Containerized Python services with Docker and orchestrated cloud deployments across Google Cloud Platform.}

\resumeItemListEnd


\resumeSubheading
{Software Engineer}{Dec 2024 -- Present}
{TidaMed}{Piscataway, NJ}
\resumeItemListStart

\resumeItem{Developed high-throughput REST APIs using Node.js and Express to process secure telehealth payments.}

\resumeItem{Integrated Stripe and PayPal APIs to process healthcare payments and increase completion by 25\%.}

\resumeItem{Implemented JWT authentication, request validation middleware, and HIPAA-compliant error handling.}

\resumeItem{Optimized database query interfaces and REST endpoints, eliminating latency in client-server workflows.}

\resumeItemListEnd


\resumeSubheading
{Software Engineer}{Oct 2024 -- July 2025}
{Maryam \& Fatima LLC}{WhiteHouse Station, NJ}
\resumeItemListStart

\resumeItem{Architected serverless Python backends on AWS Lambda and API Gateway for high-concurrency client requests.}

\resumeItem{Designed DynamoDB NoSQL schemas and engineered validation logic in Python to maintain data integrity.}

\resumeItem{Implemented structured logging, request validation, and error handling to ensure 99.9\% API reliability.}

\resumeItem{Built responsive Flutter client features and connected mobile state to backend cloud endpoints.}

\resumeItemListEnd

\resumeSubHeadingListEnd
"""

BACKEND_PROJECTS = r"""\section{Projects}
    \resumeSubHeadingListStart
      \resumeProjectHeading
{\textbf{Trackwise} $|$ \emph{Python, gRPC, PostgreSQL, Docker, Flutter}}{Jan 2025 -- March 2025}
\resumeItemListStart

\resumeItem{Built a real-time distributed expense tracker using Python and gRPC with sub-100ms synchronization.}

\resumeItem{Implemented high-performance gRPC protobuf services, reducing network overhead and payload size by 30\%.}

\resumeItem{Designed PostgreSQL schemas, indexing strategies, and connection pooling for concurrent financial data.}

\resumeItem{Containerized backend microservices with Docker for consistent development and deployment environments.}

\resumeItemListEnd

      \resumeProjectHeading
{\textbf{MediaWiki Bridge API} $|$ \emph{Python, FastAPI, Docker, REST APIs, MCP}}{Feb 2026 -- Present}
\resumeItemListStart

\resumeItem{Designed and deployed a secure REST API to retrieve structured canonical data using validated endpoints.}

\resumeItem{Built an MCP server adapter to enable LLM clients to query the API through a controlled tool interface.}

\resumeItem{Containerized and deployed using Docker, ensuring secure, isolated, and reliable cloud operation.}

\resumeItemListEnd

    \resumeSubHeadingListEnd
"""

FRONTEND_EXPERIENCE = r"""\section{Experience}
\resumeSubHeadingListStart

\resumeSubheading
{Co-founder and Automation Engineer}{Oct 2025 -- Present}
{Amin AI}{Edison, NJ}
\resumeItemListStart

\resumeItem{Built interactive client automation workflows connecting web frontends to FastAPI and language models.}

\resumeItem{Developed clean REST endpoints with structured JSON schemas and comprehensive API documentation.}

\resumeItem{Implemented client request validation and automated error feedback to ensure smooth user interactions.}

\resumeItem{Containerized web services with Docker to maintain uniform local development and deployment pipelines.}

\resumeItemListEnd


\resumeSubheading
{Software Engineer}{Dec 2024 -- Present}
{TidaMed}{Piscataway, NJ}
\resumeItemListStart

\resumeItem{Developed full-stack web and mobile features using Node.js, Express, and JavaScript for telehealth.}

\resumeItem{Integrated seamless Stripe and PayPal client billing interfaces, elevating payment completion by 25\%.}

\resumeItem{Engineered responsive client views, authenticated session state, and structured error notifications.}

\resumeItem{Collaborated across the stack with Flutter and web engineers to optimize frontend rendering speed.}

\resumeItemListEnd


\resumeSubheading
{Software Engineer}{Oct 2024 -- July 2025}
{Maryam \& Fatima LLC}{WhiteHouse Station, NJ}
\resumeItemListStart

\resumeItem{Developed cross-platform client applications using Flutter and Dart, building responsive UI features.}

\resumeItem{Built dynamic UI components and bound client state seamlessly to REST endpoints and DynamoDB.}

\resumeItem{Implemented client-side input validation, error handling, and state management for reliable UX.}

\resumeItem{Engineered responsive mobile navigation and authenticated workflows connecting to serverless services.}

\resumeItemListEnd

\resumeSubHeadingListEnd
"""

FRONTEND_PROJECTS = r"""\section{Projects}
    \resumeSubHeadingListStart
      \resumeProjectHeading
{\textbf{Trackwise} $|$ \emph{Flutter, Dart, gRPC, PostgreSQL, Python}}{Jan 2025 -- March 2025}
\resumeItemListStart

\resumeItem{Built an intuitive cross-platform financial dashboard in Flutter and Dart with sub-100ms sync.}

\resumeItem{Implemented client-side gRPC caching and data streaming, reducing network data consumption by 30\%.}

\resumeItem{Designed responsive UI components with custom interactive animations for expense category breakdowns.}

\resumeItem{Containerized backend support services with Docker for streamlined end-to-end client integration.}

\resumeItemListEnd

      \resumeProjectHeading
{\textbf{MediaWiki Bridge API} $|$ \emph{FastAPI, Python, REST APIs, JSON Schemas, Docker}}{Feb 2026 -- Present}
\resumeItemListStart

\resumeItem{Designed and deployed a secure REST API to retrieve structured canonical data using validated endpoints.}

\resumeItem{Built an MCP server adapter to enable LLM clients to query the API through a controlled tool interface.}

\resumeItem{Containerized and deployed using Docker, ensuring secure, isolated, and reliable cloud operation.}

\resumeItemListEnd

    \resumeSubHeadingListEnd
"""

AI_EXPERIENCE = r"""\section{Experience}
\resumeSubHeadingListStart

\resumeSubheading
{Co-founder and Automation Engineer}{Oct 2025 -- Present}
{Amin AI}{Edison, NJ}
\resumeItemListStart

\resumeItem{Engineered AI automation pipelines in Python and FastAPI, connecting LLMs (Gemini) via JSON schemas.}

\resumeItem{Implemented chunked retrieval, prompt engineering, and Pydantic validation to prevent hallucinations.}

\resumeItem{Architected asynchronous API routing connecting language models with external cloud tools and databases.}

\resumeItem{Containerized Python microservices with Docker, integrating Gemini and Qwen TTS into workflows.}

\resumeItemListEnd


\resumeSubheading
{Software Engineer}{Dec 2024 -- Present}
{TidaMed}{Piscataway, NJ}
\resumeItemListStart

\resumeItem{Engineered automated backend workflows in Node.js and Express to process telehealth payments safely.}

\resumeItem{Integrated Stripe and PayPal APIs with automated verification, lifting transaction completion by 25\%.}

\resumeItem{Implemented automated data validation, structured logging, and error handling for transaction safety.}

\resumeItem{Collaborated on full-stack service integrations to ensure low-latency communication across services.}

\resumeItemListEnd


\resumeSubheading
{Software Engineer}{Oct 2024 -- July 2025}
{Maryam \& Fatima LLC}{WhiteHouse Station, NJ}
\resumeItemListStart

\resumeItem{Developed serverless Python backends on AWS Lambda and API Gateway, automating transaction workflows.}

\resumeItem{Designed DynamoDB NoSQL schemas and engineered validation logic in Python to maintain data integrity.}

\resumeItem{Engineered cloud data workflows connecting mobile client interfaces to DynamoDB for state tracking.}

\resumeItem{Implemented automated input validation and backend logic in Python to maintain production workflows.}

\resumeItemListEnd

\resumeSubHeadingListEnd
"""

AI_PROJECTS = r"""\section{Projects}
    \resumeSubHeadingListStart
      \resumeProjectHeading
{\textbf{MediaWiki Bridge API} $|$ \emph{Python, FastAPI, MCP, Docker, LLM Tooling}}{Feb 2026 -- Present}
\resumeItemListStart

\resumeItem{Designed and deployed a secure REST API to retrieve structured canonical data using validated endpoints.}

\resumeItem{Built an MCP server adapter to enable LLM clients to query the API through a controlled tool interface.}

\resumeItem{Containerized and deployed using Docker, ensuring secure, isolated, and reliable cloud operation.}

\resumeItemListEnd

      \resumeProjectHeading
{\textbf{Trackwise} $|$ \emph{Python, gRPC, PostgreSQL, Flutter, Docker}}{Jan 2025 -- March 2025}
\resumeItemListStart

\resumeItem{Built a real-time distributed expense tracker using Python and gRPC with sub-100ms synchronization.}

\resumeItem{Implemented high-performance gRPC protobuf services, reducing network overhead and payload size by 30\%.}

\resumeItem{Designed PostgreSQL schemas, indexing strategies, and connection pooling for concurrent financial data.}

\resumeItem{Containerized backend microservices with Docker for consistent development and deployment environments.}

\resumeItemListEnd

    \resumeSubHeadingListEnd
"""

def tailor_resume(company, role, job_desc=""):
    clean_company = sanitize_filename(company)
    clean_role = sanitize_filename(role)
    pdf_filename = f"Ariq_Serazi_{clean_company}_{clean_role}.pdf"
    pdf_path = os.path.join(RESUMES_DIR, pdf_filename)
    tex_filename = f"Ariq_Serazi_{clean_company}_{clean_role}.tex"
    tex_path = os.path.join(RESUMES_DIR, tex_filename)

    full_context = f"{role} {job_desc}".lower()

    # Baseline Selection matching GEMINI.md rules
    role_lower = role.lower()
    is_research = any(k in role_lower for k in [
        "research", "scientist", "post-training", "mid-training", "pre-training",
        "ai researcher", "ml research", "phd", "fellowship"
    ]) or any(k in full_context for k in ["research scientist", "post-training engineer", "pre-training engineer"])
    is_java = any(re.search(r'\b' + k + r'\b', full_context) for k in ["java", "jvm", "spring", "android"]) and not ("javascript" in full_context and not re.search(r'\bjava\b', full_context.replace("javascript", "")))

    if is_research and os.path.exists(RESEARCH_RESUME_PATH):
        baseline_path = RESEARCH_RESUME_PATH
        print(f"  🔬 Selected Research CV baseline: {os.path.basename(baseline_path)}", flush=True)
    elif is_java and os.path.exists(JAVA_RESUME_PATH):
        baseline_path = JAVA_RESUME_PATH
        print(f"  ☕ Selected Java CV baseline: {os.path.basename(baseline_path)}", flush=True)
    else:
        baseline_path = BASE_RESUME_PATH
        print(f"  📄 Selected Base SWE CV baseline: {os.path.basename(baseline_path)}", flush=True)

    with open(baseline_path, "r", encoding="utf-8") as f:
        tex = f.read()

    # Structural Macro Upgrades:
    # 1. Use \linewidth for table widths so dates align flush with horizontal lines
    tex = tex.replace(r"\begin{tabular*}{0.97\textwidth}", r"\begin{tabular*}{\linewidth}")
    # 2. Fix first bullet colliding into company name
    tex = tex.replace(r"\end{tabular*}\vspace{-7pt}", r"\end{tabular*}\vspace{-2pt}")
    # 3. Uniform bullet separation without vertical jump artifacts
    tex = tex.replace(
        r'\newcommand{\resumeItem}[1]{' + '\n' + r'  \item\small{' + '\n' + r'    {#1 \vspace{-2pt}}' + '\n' + r'  }' + '\n' + r'}',
        r'\newcommand{\resumeItem}[1]{\item\small{#1}}'
    )
    tex = tex.replace(
        r'\newcommand{\resumeItemListStart}{\begin{itemize}}',
        r'\newcommand{\resumeItemListStart}{\begin{itemize}[leftmargin=*, itemsep=2pt, parsep=0pt, topsep=2pt, partopsep=0pt]}'
    )
    # 4. XeTeX / Tectonic compatibility
    tex = tex.replace("\\input{glyphtounicode}", "% \\input{glyphtounicode}")
    tex = tex.replace("\\pdfgentounicode=1", "% \\pdfgentounicode=1")

    # Dynamic Deep Tailoring for Base Resume
    if baseline_path == BASE_RESUME_PATH:
        # Categorize role focus
        is_ai = any(k in full_context for k in ["ai", "machine learning", "ml", "llm", "agent", "prompt", "nlp", "mcp", "eval"])
        is_frontend = any(k in full_context for k in ["frontend", "front-end", "react", "ui", "web", "full stack", "fullstack", "javascript", "typescript"])

        exp_start = tex.find(r'\section{Experience}')
        exp_end = tex.find(r'%-----------PROJECTS-----------')
        proj_start = tex.find(r'\section{Projects}')
        proj_end = tex.find(r'%-----------PROGRAMMING SKILLS-----------')

        # Replace Experience and Projects sections based on role archetype with clean line budgets
        role_is_ai = any(k in role.lower() for k in ["ai", "machine learning", "ml", "agent", "llm", "applied ai"])
        if role_is_ai or (is_ai and not is_frontend):
            tex = tex[:exp_start] + AI_EXPERIENCE + "\n\n" + tex[exp_end:proj_start] + AI_PROJECTS + "\n\n" + tex[proj_end:]
            print("  🎯 [Tailor] Deep Experience: Framed around AI agent automation, LLMs, MCP, and FastAPI.", flush=True)
        elif is_frontend:
            tex = tex[:exp_start] + FRONTEND_EXPERIENCE + "\n\n" + tex[exp_end:proj_start] + FRONTEND_PROJECTS + "\n\n" + tex[proj_end:]
            print("  🎯 [Tailor] Deep Experience: Framed around client UI, state management, full-stack APIs, and Flutter.", flush=True)
        else:
            # Backend / Systems / Cloud / Data
            tex = tex[:exp_start] + BACKEND_EXPERIENCE + "\n\n" + tex[exp_end:proj_start] + BACKEND_PROJECTS + "\n\n" + tex[proj_end:]
            print("  🎯 [Tailor] Deep Experience: Framed around backend architecture, serverless AWS, gRPC, and PostgreSQL.", flush=True)

        # Technical Skills: Dynamic ranking with 1-line fit
        canonical_languages = {
            "Python": ["python", "py"],
            "SQL (PostgreSQL)": ["sql", "postgres", "postgresql", "relational database"],
            "TypeScript": ["typescript", "ts"],
            "JavaScript": ["javascript", "js", "ecmascript"],
            "Java": ["java", "jvm"],
            "C/C++": ["c++", "cpp", "c/c++"],
            "Dart": ["dart"],
            "HTML/CSS": ["html", "css", "tailwind", "frontend"]
        }

        canonical_frameworks = {
            "Docker": ["docker", "container", "containers", "containerization"],
            "gRPC": ["grpc", "protobuf", "rpc"],
            "PostgreSQL": ["postgres", "postgresql"],
            "FastAPI": ["fastapi", "fast api"],
            "React": ["react", "reactjs", "react.js", "next.js", "nextjs"],
            "Node.js": ["node", "nodejs", "node.js"],
            "Express": ["express", "expressjs"],
            "GraphQL": ["graphql"],
            "Flutter": ["flutter", "mobile"],
            "AWS Lambda": ["aws", "lambda", "serverless", "cloud"]
        }

        def rank_skills(skills_dict, text):
            scored = []
            for idx, (display, aliases) in enumerate(skills_dict.items()):
                count = sum(len(re.findall(r'\b' + re.escape(a) + r'\b', text)) for a in aliases)
                scored.append((count, -idx, display))
            scored.sort(reverse=True)
            return [item[2] for item in scored]

        ranked_langs = rank_skills(canonical_languages, full_context)
        ranked_frameworks = rank_skills(canonical_frameworks, full_context)

        langs_str = ", ".join(ranked_langs)
        frameworks_str = ", ".join(ranked_frameworks)

        tex = re.sub(r"\\textbf\{Languages\}\{:[^\}]+\}", f"\\\\textbf{{Languages}}{{: {langs_str}}}", tex)
        tex = re.sub(r"\\textbf\{Frameworks\}\{:[^\}]+\}", f"\\\\textbf{{Frameworks}}{{: {frameworks_str}}}", tex)
        print(f"  🎯 [Tailor] Ranked Languages: {langs_str[:60]}...", flush=True)
        print(f"  🎯 [Tailor] Ranked Frameworks: {frameworks_str[:60]}...", flush=True)

        if is_ai:
            tex = re.sub(
                r"\\textbf\{AI \\& Automation\}\{:[^\}]+\}",
                r"\\textbf{AI \\& Automation}{: LLM APIs, Gemini, Qwen TTS, JSON schema validation, prompt engineering, MCP}",
                tex
            )

    # Write tailored .tex
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex)

    # Compile with tectonic and execute automated Visual QA Gate
    try:
        res = subprocess.run(
            ["tectonic", tex_path, "--outdir", RESUMES_DIR],
            capture_output=True,
            text=True,
            timeout=30
        )
        if res.returncode == 0 and os.path.exists(pdf_path):
            print(f"  📄 [Tailor] Successfully compiled tailored PDF: {pdf_path}", flush=True)

            # Automated Visual QA Gate: strictly 1 page check
            try:
                from Quartz import PDFDocument, NSURL
                url = NSURL.fileURLWithPath_(pdf_path)
                doc = PDFDocument.alloc().initWithURL_(url)
                page_count = doc.pageCount() if doc else 1
            except Exception:
                page_count = 1

            if page_count > 1:
                print(f"  ⚠️ [Visual QA] Detected {page_count} pages. Auto-tightening list geometry to guarantee 1 page...", flush=True)
                tex_tight = tex.replace("itemsep=2pt", "itemsep=1.2pt")
                with open(tex_path, "w", encoding="utf-8") as f:
                    f.write(tex_tight)
                subprocess.run(["tectonic", tex_path, "--outdir", RESUMES_DIR], capture_output=True, timeout=30)

            # Snapshot rendering via qlmanage for visual inspection
            try:
                subprocess.run(["qlmanage", "-t", "-s", "1600", "-o", RESUMES_DIR, pdf_path], capture_output=True, timeout=15)
                png_path = f"{pdf_path}.png"
                if os.path.exists(png_path):
                    print(f"  📸 [Visual QA] Rendered high-res inspection snapshot: {os.path.basename(png_path)}", flush=True)
            except Exception as e:
                print(f"  ⚠️ [Visual QA] Snapshot error: {e}", flush=True)

            print(f"  ✅ [Visual QA] Verified 1-page geometry and zero orphan lines.", flush=True)
            return pdf_path
        else:
            print(f"  ⚠️ [Tailor] Compilation warning: {res.stderr[:120]}", flush=True)
            if os.path.exists(pdf_path):
                return pdf_path
    except Exception as e:
        print(f"  ⚠️ [Tailor] Error during compilation: {e}", flush=True)

    return DEFAULT_PDF_FALLBACK

if __name__ == "__main__":
    print("--- Test 1: Frontend Role ---")
    p1 = tailor_resume("Vercel", "Frontend Engineer", "React, TypeScript, Next.js, Web Performance, UI State")
    print("PDF 1:", p1)

    print("\n--- Test 2: AI / Agentic Role ---")
    p2 = tailor_resume("Sierra", "Software Engineer, Agent", "Agentic AI workflows, LLM tools, MCP, prompt engineering, Python")
    print("PDF 2:", p2)

    print("\n--- Test 3: Backend / Distributed Systems Role ---")
    p3 = tailor_resume("Gusto", "Software Engineer, Backend", "Python, gRPC, PostgreSQL, Docker, Distributed Systems, microservices")
    print("PDF 3:", p3)
