# Candidate Projects Bank & Database

This document serves as the canonical project repository for tailoring ATS-compliant resumes and answering technical project questions on job applications.

---

## Project 1: AIJobAssistant (Autonomous Agentic Workflow & RPA Platform)

* **Repository**: [github.com/ariqserazi/AIJobAssistant](https://github.com/ariqserazi/AIJobAssistant)
* **Date Range**: Nov 2025 – Present
* **Core Technologies**: Python, Playwright, Chromium, Ollama (`qwen3:4b-instruct`), macOS PyObjC ScriptingBridge, Google Cloud API (`gspread`), LaTeX (`tectonic`), POSIX File Locks (`fcntl`).
* **Best Fit / Target Roles**:
  * AI / Agentic Systems & LLM Tooling
  * Distributed Systems & Concurrency
  * Backend & Python Engineering
  * Browser Automation, RPA & Web Systems
  * Quality, Performance & Infrastructure Engineering

### ATS Resume Bullets (LaTeX Ready)
```latex
\resumeProjectHeading
{\textbf{AIJobAssistant: Autonomous Agentic RPA Platform} $|$ \emph{Python, Playwright, Ollama, macOS IPC, GCP}}{Nov 2025 -- Present}
\resumeItemListStart
\resumeItem{Architected a 5-worker parallel browser automation engine using Python and Playwright, implementing disjoint task partitioning and POSIX file locks to execute high-throughput web automation workflows.}
\resumeItem{Integrated an on-device local LLM (\texttt{qwen3:4b-instruct} via Ollama) to dynamically classify form schemas and reason through complex inputs with sub-second latency and 100\% cost reduction (\$0/token).}
\resumeItem{Engineered an OS-level IPC integration using macOS \texttt{ScriptingBridge} to programmatically extract real-time 2FA and OTP verification codes from browser sessions without stealing window focus.}
\resumeItem{Executed and verified over 1,000+ multi-step enterprise workflows across 4 distinct dynamic DOM architectures (Workday, Greenhouse, Lever, Ashby) with zero race conditions.}
\resumeItemListEnd
```

### Free-Text Application Narrative (Strictly Zero Dashes)
> "I architected an autonomous browser automation and agentic workflow platform in Python using Playwright and local LLMs. The system coordinates five concurrent headless browser workers using disjoint modulo partitioning and atomic file locking to eliminate race conditions. It integrates a local quantized language model via Ollama for real time schema reasoning with zero API cost, and connects to Google Chrome via macOS ScriptingBridge to capture two factor authentication codes automatically. The platform has verified and executed over one thousand multi step workflows across major enterprise web platforms."

---

## Project 2: Trackwise (Distributed Real-Time Financial Tracker)

* **Date Range**: Jan 2025 – March 2025
* **Core Technologies**: Python, gRPC, Protobuf, PostgreSQL, Docker Compose, Flutter, Dart.
* **Best Fit / Target Roles**:
  * Distributed Systems & Microservices
  * Backend Systems & High-Performance Protocols (gRPC / Protobuf)
  * Database Architecture & Financial / FinTech Engineering
  * Full Stack & Mobile Engineering

### ATS Resume Bullets (LaTeX Ready)
```latex
\resumeProjectHeading
{\textbf{Trackwise} $|$ \emph{Python, gRPC, PostgreSQL, Docker, Flutter}}{Jan 2025 -- March 2025}
\resumeItemListStart
\resumeItem{Built a real-time distributed expense tracker using Python and gRPC with sub-100ms synchronization.}
\resumeItem{Implemented high-performance gRPC protobuf contracts, cutting network payload sizes by 30\% over JSON.}
\resumeItem{Designed PostgreSQL schemas, indexing strategies, and connection pooling for concurrent financial data.}
\resumeItem{Containerized backend microservices with Docker Compose, standardizing local and production runtimes.}
\resumeItemListEnd
```

### Free-Text Application Narrative (Strictly Zero Dashes)
> "I built Trackwise, a distributed real time financial tracking platform using Python, gRPC, PostgreSQL, and Docker. I designed strict protocol buffer contracts to replace standard JSON, reducing network payload sizes by thirty percent and achieving sub 100 millisecond synchronization across mobile and web clients. I structured relational PostgreSQL schemas with composite indexes and connection pooling to ensure strict ACID transactional guarantees for concurrent ledger entries."

---

## Project 3: MediaWiki Bridge API (Structured Knowledge & Agent Tooling)

* **Date Range**: Feb 2026 – Present
* **Core Technologies**: Python, FastAPI, Docker, Pydantic, REST APIs, Model Context Protocol (MCP).
* **Best Fit / Target Roles**:
  * API Architecture & REST Microservices
  * Backend & Python / FastAPI Roles
  * LLM Tooling, Agent Interfaces & Model Context Protocol (MCP)
  * Data Normalization & Knowledge Retrieval

### ATS Resume Bullets (LaTeX Ready)
```latex
\resumeProjectHeading
{\textbf{MediaWiki Bridge API} $|$ \emph{Python, FastAPI, Docker, REST APIs, MCP}}{Feb 2026 -- Present}
\resumeItemListStart
\resumeItem{Designed a high-performance FastAPI REST service to retrieve canonical data with strict Pydantic models.}
\resumeItem{Built an MCP server adapter to enable autonomous AI agents to query external tools via structured calls.}
\resumeItem{Containerized and deployed using Docker, ensuring secure, isolated environments and 99.9\% availability.}
\resumeItemListEnd
```

### Free-Text Application Narrative (Strictly Zero Dashes)
> "I developed the MediaWiki Bridge API, a high throughput microservice built with Python and FastAPI to extract and normalize structured canonical data. I implemented strict Pydantic v2 schemas for runtime validation and created a custom Model Context Protocol adapter enabling external language models and AI agents to query structured data tools safely. The service is containerized using Docker with multi stage builds ensuring isolated production environments and high availability."

---

## Tailoring Selection Strategy

When tailoring a 1-page resume (which comfortably fits **2 featured projects**):

| Role Type | Recommended Project 1 | Recommended Project 2 | Rationale |
| :--- | :--- | :--- | :--- |
| **AI / Agentic / Automation / RPA** | **AIJobAssistant** | **MediaWiki Bridge API** | Highlights local LLM inference, browser agents, MCP, and FastAPI. |
| **Distributed Systems / Backend** | **AIJobAssistant** | **Trackwise** | Highlights multiprocessing concurrency, POSIX locking, gRPC, and PostgreSQL. |
| **Python / Cloud / Microservices** | **AIJobAssistant** | **MediaWiki Bridge API** | Showcases modern async Python, Playwright, Docker, and REST APIs. |
| **Full Stack / Mobile / FinTech** | **Trackwise** | **MediaWiki Bridge API** | Highlights Flutter/Dart client, PostgreSQL transactions, and backend services. |
