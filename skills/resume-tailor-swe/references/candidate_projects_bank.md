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
> "Developed a parallel browser automation engine in Python using Playwright to handle high volume web tasks. Spun up five concurrent Chromium instances using modulo task partitioning and POSIX file locks to prevent worker collisions. Routed dynamic form inputs to an on device 4B model running in Ollama for local schema resolution with zero API cost, and integrated macOS ScriptingBridge to extract 2FA codes silently in the background. Completed over one thousand multi step runs across Workday, Greenhouse, and Lever without concurrency bugs."

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
> "Engineered a distributed real time expense tracker featuring a Python gRPC backend and a Flutter frontend. Wrote Protocol Buffer contracts over HTTP/2 to reduce network payload sizes by 30 percent and maintain sub 100 millisecond synchronization across clients. Designed PostgreSQL schemas with composite indexes and connection pooling to keep concurrent ledger entries strictly consistent."

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
> "Created a microservice in Python and FastAPI to extract and clean structured data for language models. Used Pydantic v2 to strictly validate query parameters and responses at runtime, and implemented a Model Context Protocol server adapter allowing AI agents to query the service directly as a tool. Containerized the application using multi stage Docker builds to keep image sizes small and environments consistent."

---

## Tailoring Selection Strategy

When tailoring a 1-page resume (which comfortably fits **2 featured projects**):

| Role Type | Recommended Project 1 | Recommended Project 2 | Rationale |
| :--- | :--- | :--- | :--- |
| **AI / Agentic / Automation / RPA** | **AIJobAssistant** | **MediaWiki Bridge API** | Highlights local LLM inference, browser agents, MCP, and FastAPI. |
| **Distributed Systems / Backend** | **AIJobAssistant** | **Trackwise** | Highlights multiprocessing concurrency, POSIX locking, gRPC, and PostgreSQL. |
| **Python / Cloud / Microservices** | **AIJobAssistant** | **MediaWiki Bridge API** | Showcases modern async Python, Playwright, Docker, and REST APIs. |
| **Full Stack / Mobile / FinTech** | **Trackwise** | **MediaWiki Bridge API** | Highlights Flutter/Dart client, PostgreSQL transactions, and backend services. |
