#!/usr/bin/env python3
"""
batch_apply_ashby.py - Modular, Headful Ashby Application Co-Pilot.
Opens visible Chrome on desktop, populates fields live, enables visual review,
and dispatches native physical mouse clicks to submit without triggering spam filters.
"""

import os
import sys
import time
import json
import re
import argparse
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

# Fix macOS Python SSL certificate validation
try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
except ImportError:
    pass

ENGINE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, os.path.expanduser("~/.agents/skills/resume-tailor-swe/scripts"))

from ashby_engine import (
    FieldMatcher,
    DOMScanner,
    DOMFiller,
    SubmissionVerifier,
    click_element_cv,
    bring_window_to_front,
    CANDIDATE_DATA
)
from fast_resume_selector import get_fast_tailored_resume
from log_application import log_to_google_sheets
from captcha_solver import handle_captchas_if_present

DEFAULT_QUEUE = ENGINE_DIR / "queue_unapplied_gh_lever_ashby.json"
TARGET_JOBS = ENGINE_DIR / "target_jobs.json"
CONFIRMATIONS_DIR = os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/confirmations")
os.makedirs(CONFIRMATIONS_DIR, exist_ok=True)
ERRORS_DIR = Path(os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/errors"))
ERRORS_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH_ERRORS_DIR = Path(os.getenv("SCRATCH_ERRORS_DIR", os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/errors")))
SCRATCH_ERRORS_DIR.mkdir(parents=True, exist_ok=True)


def norm_url(u: str) -> str:
    """Normalizes URL for deduplication."""
    if not u:
        return ""
    u = u.strip().split("?")[0].rstrip("/")
    return u.lower()

def apply_to_job(target_obj, job: dict, review_delay: float = 4.0) -> bool:
    """
    Applies to an Ashby job posting in visible Chrome with physical mouse submission.
    Accepts either a Playwright Page or Browser/BrowserContext object.
    """
    created_context = False
    if hasattr(target_obj, "new_page"):
        context = target_obj.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ) if hasattr(target_obj, "new_context") else target_obj
        page = context.new_page()
        created_context = True
    else:
        page = target_obj

    try:
        from playwright_stealth import Stealth
        Stealth().apply_stealth_sync(page)
    except Exception:
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def _cleanup():
        if created_context:
            try:
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass

    url = job.get("url") or job.get("link") or ""
    if "/application" not in url:
        parts = url.split("?")
        base_path = parts[0].rstrip("/") + "/application"
        query = ("?" + parts[1]) if len(parts) > 1 else ""
        url = base_path + query
    if "embed=true" not in url:
        url = url + ("&embed=true" if "?" in url else "?embed=true")
    company = job.get("company", "the company")
    role = job.get("title") or job.get("role", "Software Engineer")
    loc = job.get("location", "Remote US")

    FOREIGN_LOC_REGEX = re.compile(
        r'\b(apj|apac|emea|latam|menap|sea\b|europe|asia|canada|toronto|vancouver|montreal|ontario|waterloo|uk\b|united kingdom|london|england|germany|berlin|munich|india|bangalore|bengaluru|hyderabad|pune|gurgaon|noida|mumbai|singapore|australia|sydney|melbourne|anz\b|france|paris|netherlands|amsterdam|poland|warsaw|krakow|switzerland|zurich|japan|tokyo|taiwan|ireland|dublin|brazil|mexico|israel|china|shanghai|beijing|shenzhen|spain|sweden|korea|philippines|vietnam|colombia|argentina|chile|nigeria|egypt|kenya|south africa)\b',
        re.IGNORECASE
    )
    if FOREIGN_LOC_REGEX.search(loc) and not re.search(r'\b(united states|usa|remote\s*-\s*us|us\b)\b', loc.lower()):
        print(f"  🚫 [Strict US Filter] Skipping non-US location at {company}: '{loc}'", flush=True)
        _cleanup()
        return False
    if FOREIGN_LOC_REGEX.search(role) and not re.search(r'\b(united states|usa|remote\s*-\s*us|us\b)\b', role.lower()):
        print(f"  🚫 [Strict US Filter] Skipping non-US role in title at {company}: '{role}'", flush=True)
        _cleanup()
        return False

    print(f"\n{'='*70}", flush=True)
    print(f"🚀 Processing: {company} - {role} ({loc})", flush=True)
    print(f"🔗 URL: {url}", flush=True)
    print(f"{'='*70}", flush=True)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2.0)
    except Exception as e:
        print(f"  [Error] Failed to load page: {e}", flush=True)
        _cleanup()
        return False

    # Check if job is expired or no longer accepting applications
    body_text = page.evaluate("() => document.body ? document.body.innerText.toLowerCase() : ''")
    if any(k in body_text for k in [
        "no longer accepting", "position has been closed", "job has expired",
        "job not found", "page not found", "requested was not found",
        "the job you requested", "job is no longer available", "view all open positions"
    ]):
        print(f"  [Notice] Job at {company} is closed or expired. Skipping.", flush=True)
        _cleanup()
        return False

    # Check active CAPTCHAs before resume upload
    try:
        handle_captchas_if_present(page, company=company, title=role)
    except Exception:
        pass

    # 1. Select / Tailor Resume PDF (<2ms)
    resume_pdf = get_fast_tailored_resume(company, role, body_text)
    print(f"  [Resume] Selected tailored PDF: {os.path.basename(resume_pdf)}", flush=True)

    # 2. Bring window to front so user sees Chrome live
    bring_window_to_front("Google Chrome for Testing")

    # 3. Populate Form Fields
    print("  [Form Engine] Populating form fields live...", flush=True)
    DOMFiller.fill_all_fields(page, resume_pdf, company, role)

    # Check active CAPTCHAs after resume upload and form population
    try:
        handle_captchas_if_present(page, company=company, title=role)
    except Exception:
        pass

    # 4. Natural User Interaction & Visual Review
    dwell_time = max(review_delay, 8.0)
    print(f"  [Co-Pilot] Form filled. Simulating natural dwell and review ({dwell_time:.1f}s)...", flush=True)
    page.evaluate("window.scrollTo({ top: document.body.scrollHeight / 2, behavior: 'smooth' })")
    time.sleep(dwell_time / 2)
    page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
    time.sleep(dwell_time / 2)

    # 5. Dispatch Native Hardware Mouse Click onto Submit Button
    print("  [Anti-Spam] Engaging native OS hardware mouse to click Submit...", flush=True)
    clicked = click_element_cv(page, selector='button[type="submit"], button:has-text("Submit Application")')
    if not clicked:
        print("  [Anti-Spam Fallback] Physical mouse click failed; using Playwright click...", flush=True)
        try:
            page.locator('button[type="submit"], button:has-text("Submit Application")').first.click(timeout=5000)
        except Exception as e:
            print(f"  [Error] Could not click submit button: {e}", flush=True)
            _cleanup()
            return False

    # 6. Verify Submission Confirmation
    print("  [Verification] Awaiting employer confirmation screen...", flush=True)
    if SubmissionVerifier.is_confirmed(page, max_wait_seconds=12):
        print(f"  ✅ Submission CONFIRMED for {company} - {role}!", flush=True)
        _handle_success(page, company, role, url, resume_pdf)
        _cleanup()
        return True

    # 7. Diagnostic Rectification Loop if not confirmed immediately
    print("  [Diagnostics] Confirmation not seen immediately. Checking for validation errors...", flush=True)
    for attempt in range(1, 4):
        if SubmissionVerifier.is_confirmed(page, max_wait_seconds=3):
            print(f"  ✅ Submission CONFIRMED for {company} - {role}!", flush=True)
            _handle_success(page, company, role, url, resume_pdf)
            _cleanup()
            return True

        fixed = DOMFiller.diagnose_and_rectify(page, resume_pdf, company, role)

        # Check if Ashby displayed the "flagged as possible spam - please submit your application again" banner
        try:
            body_text = page.evaluate("() => document.body ? document.body.innerText.toLowerCase() : ''")
            if "flagged as possible spam" in body_text or "please submit your application again" in body_text:
                print("  ⚠️ [Anti-Spam Bypass] Ashby prompted 'please submit your application again'. Waiting 2.5s and re-submitting directly...", flush=True)
                time.sleep(2.5)
                page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
                time.sleep(1.0)

                submit_locator = page.locator('button[type="submit"], button:has-text("Submit Application"), button:has-text("Submit application"), button:has-text("Submit")').first
                if submit_locator.is_visible():
                    submit_locator.scroll_into_view_if_needed()
                    time.sleep(0.5)

                if not click_element_cv(page, selector='button[type="submit"], button:has-text("Submit Application")'):
                    try:
                        submit_locator.click(force=True, timeout=5000)
                    except Exception:
                        page.evaluate("() => { const b = document.querySelector('button[type=\"submit\"]') || Array.from(document.querySelectorAll('button')).find(x => x.textContent.toLowerCase().includes('submit')); if (b) b.click(); }")
                if SubmissionVerifier.is_confirmed(page, max_wait_seconds=15):
                    print(f"  ✅ Submission CONFIRMED after anti-spam re-submit for {company} - {role}!", flush=True)
                    _handle_success(page, company, role, url, resume_pdf)
                    _cleanup()
                    return True
                time.sleep(1.0)
                fixed += DOMFiller.diagnose_and_rectify(page, resume_pdf, company, role)
        except Exception as e:
            print(f"  ⚠️ Error checking spam banner: {e}", flush=True)

        if fixed == 0:
            if SubmissionVerifier.is_confirmed(page, max_wait_seconds=3):
                print(f"  ✅ Submission CONFIRMED for {company} - {role}!", flush=True)
                _handle_success(page, company, role, url, resume_pdf)
                _cleanup()
                return True
            break
        print(f"  [Diagnostics] Rectified {fixed} fields on attempt {attempt}. Re-submitting...", flush=True)
        time.sleep(1.5)
        if not click_element_cv(page, selector='button:has-text("Submit Application"), button[type="submit"]'):
            try:
                page.locator('button:has-text("Submit Application"), button[type="submit"]').first.click(force=True, timeout=5000)
            except Exception:
                pass
        if SubmissionVerifier.is_confirmed(page, max_wait_seconds=10):
            print(f"  ✅ Submission CONFIRMED after rectification for {company} - {role}!", flush=True)
            _handle_success(page, company, role, url, resume_pdf)
            _cleanup()
            return True

    # Final check before declaring failure
    if SubmissionVerifier.is_confirmed(page, max_wait_seconds=3):
        print(f"  ✅ Submission CONFIRMED for {company} - {role}!", flush=True)
        _handle_success(page, company, role, url, resume_pdf)
        _cleanup()
        return True


    print(f"  ❌ Unconfirmed submission for {company} - {role}.", flush=True)
    try:
        clean_c = re.sub(r'[^a-zA-Z0-9_-]', '_', company.lower())
        clean_t = re.sub(r'[^a-zA-Z0-9_-]', '_', role.lower())
        timestamp = int(time.time())
        err_filename = f"{clean_c}_{clean_t}_unconfirmed_{timestamp}.png"
        err_path = ERRORS_DIR / err_filename
        page.screenshot(path=str(err_path), full_page=True)
        print(f"  📸 [Error Screenshot] Captured unconfirmed error state: {err_path}", flush=True)
        scratch_path = SCRATCH_ERRORS_DIR / err_filename
        page.screenshot(path=str(scratch_path), full_page=True)
    except Exception as e:
        print(f"  ⚠️ Could not capture error screenshot: {e}", flush=True)

    _record_failed_job(job, company, role, url)
    _cleanup()
    return False


def _record_failed_job(job: dict, company: str, role: str, url: str):
    """Keeps track of all failed submissions in active_failed_jobs.json without duplicates."""
    failed_file = ENGINE_DIR / "active_failed_jobs.json"
    failed_list = []
    try:
        if failed_file.exists():
            with open(failed_file, "r") as f:
                failed_list = json.load(f)
    except Exception:
        failed_list = []

    norm_target = norm_url(url)
    exists = any(norm_url(j.get("url", "")) == norm_target for j in failed_list)
    if not exists:
        record = dict(job)
        record.setdefault("company", company)
        record.setdefault("role", role)
        record.setdefault("url", url)
        failed_list.append(record)
        try:
            with open(failed_file, "w") as f:
                json.dump(failed_list, f, indent=2)
            print(f"  📝 Recorded to active_failed_jobs.json (total: {len(failed_list)})", flush=True)
        except Exception as e:
            print(f"  ⚠️ Could not record failed job: {e}", flush=True)

def _handle_success(page, company: str, role: str, url: str, resume_pdf: str):
    """Saves confirmation screenshot and logs to Google Sheet."""
    clean_c = re.sub(r'[^a-zA-Z0-9_-]', '_', company.lower())
    clean_t = re.sub(r'[^a-zA-Z0-9_-]', '_', role.lower())
    img_path = os.path.join(CONFIRMATIONS_DIR, f"{clean_c}_{clean_t}_confirmed.png")
    try:
        page.screenshot(path=img_path)
        print(f"  [Screenshot] Saved confirmation artifact to {img_path}", flush=True)
    except Exception:
        pass

    notes = f"Location: Remote/US. Tailored resume: {os.path.basename(resume_pdf)}. Submission verified."
    try:
        log_script = os.path.expanduser("~/.agents/skills/resume-tailor-swe/scripts/log_application.py")
        cmd = [
            "python3", log_script,
            "--company", company,
            "--role", role,
            "--link", url,
            "--notes", notes
        ]
        subprocess.run(cmd, timeout=30)
        print(f"  [Sheet Log] Successfully logged to Google Sheet (Col D blank).", flush=True)
    except Exception as e:
        print(f"  [Sheet Log Notice] {e}", flush=True)

def main():
    parser = argparse.ArgumentParser(description="Modular, Headful Ashby Application Co-Pilot")
    parser.add_argument("limit", nargs="?", type=int, default=1, help="Number of applications to complete (default: 1)")
    parser.add_argument("--queue", type=str, default="", help="Path to job queue JSON file")
    parser.add_argument("--review-delay", type=float, default=2.0, help="Seconds to pause for visual review before submit (default: 2.0)")
    parser.add_argument("--headless", action="store_true", help="Run headless instead of visible Chrome (default: visible)")
    args = parser.parse_args()

    # Determine Queue File
    queue_path = None
    for cand in [args.queue, DEFAULT_QUEUE, TARGET_JOBS]:
        if cand and os.path.exists(cand):
            queue_path = cand
            break

    if not queue_path:
        print("Error: No valid target queue found.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading queue: {queue_path}")
    with open(queue_path, "r") as f:
        data = json.load(f)

    # Filter for Ashby jobs
    all_jobs = data if isinstance(data, list) else data.get("jobs", [])
    ashby_jobs = [
        j for j in all_jobs
        if "ashbyhq.com" in (j.get("url") or j.get("link") or "")
    ]
    print(f"Found {len(ashby_jobs)} Ashby targets in queue.")

    if not ashby_jobs:
        print("No Ashby jobs available to process.")
        sys.exit(0)

    # Launch Playwright (Defaults to HEADFUL so user sees Chrome on screen)
    is_headless = args.headless
    print(f"\n🌐 Launching Google Chrome (Headless: {is_headless})...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=is_headless,
            channel="chrome",
            args=[
                "--start-maximized",
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(no_viewport=True)
        context.add_init_script("""
            Object.defineProperty(navigator, "webdriver", { get: () => undefined });
            delete Object.getPrototypeOf(navigator).webdriver;
            window.chrome = { runtime: {} };
        """)
        page = context.new_page()

        applied_count = 0
        processed_count = 0
        for job in ashby_jobs:
            if applied_count >= args.limit:
                break

            processed_count += 1
            success = apply_to_job(page, job, review_delay=args.review_delay)
            if success:
                applied_count += 1
                print(f"Progress: [{applied_count}/{args.limit}] completed.")
                try:
                    with open(queue_path, "r") as qf:
                        cur_queue = json.load(qf)
                    norm_curr = norm_url(job.get("url") or job.get("link") or "")
                    new_queue = [q for q in cur_queue if norm_url(q.get("url") or q.get("link") or "") != norm_curr]
                    with open(queue_path, "w") as qf:
                        json.dump(new_queue, qf, indent=2)
                    print(f"  [Queue] Removed confirmed job from queue. Remaining: {len(new_queue)}", flush=True)
                except Exception as qe:
                    print(f"  [Queue Notice] Could not update queue file: {qe}", flush=True)
                time.sleep(2.0)

        browser.close()
        print(f"\n🏁 Session complete. Total confirmed submissions: {applied_count}")

if __name__ == "__main__":
    main()
