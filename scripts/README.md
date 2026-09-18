# Autonomous Batch Application Engine

This directory contains the production-tested autonomous application engine tailored for modern ATS portals (Ashby, Greenhouse, Lever) with full end-to-end support for:
- Dynamic LaTeX resume tailoring targeting each job's tech stack.
- Direct compilation to PDF via `tectonic`.
- Form filling matching candidate ground truth and ATS rules.
- Strict formatting rules (e.g. zero-dash enforcement in free-text boxes).
- Automatic post-submission DOM diagnostic error inspection and auto-rectification.
- Employer submission confirmation verification before logging.
- Contiguous logging directly to Google Sheets with Column D (Salary) strictly blank (`""`).

---

## Files in this Directory

- `batch_apply_ashby.py`: The complete automated batch application script.
- `tailor_and_compile.py`: The dynamic LaTeX tailor + `tectonic` PDF compilation engine.
- `target_jobs.json`: 195 curated, unapplied software engineering targets (starting with priority NJ and NYC roles).

---

## How to Run in a New Chat

In the new chat within this workspace, simply ask the agent to apply or run:
```bash
python3 application_engine/batch_apply_ashby.py 50
```
This will autonomously process through the target queue, tailor resumes, verify submissions, and log confirmed applications directly to your Google Sheet.
