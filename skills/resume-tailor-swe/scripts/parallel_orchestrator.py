#!/usr/bin/env python3
"""
parallel_orchestrator.py - Coordinates 3 parallel worker processes for maximum throughput.
Each worker processes a disjoint partition of the 800 queue.
File locks protect:
  1) Google Sheets append operations (fcntl on /tmp/gspread_sheet_lock.lock)
  2) Email OTP retrievals (fcntl on /tmp/email_otp_lock.lock)
"""

import os
import sys
# Enable mouse‑click mode for workers if explicitly requested
os.environ.setdefault("USE_MOUSE", "false")
import time
import subprocess
from pathlib import Path

if __name__ == "__main__":
    NUM_WORKERS = int(os.environ.get("NUM_WORKERS", 5))
    QUEUE_FILE = sys.argv[2] if len(sys.argv) > 2 else "application_engine/queue_unapplied_gh_lever_ashby.json"
    LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 400

    LOGS_DIR = Path("scratch/parallel_logs")
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    processes = []
    log_files = []

    print(f"🚀 Launching {NUM_WORKERS} parallel application workers on {QUEUE_FILE}...", flush=True)

    for wid in range(NUM_WORKERS):
        log_path = LOGS_DIR / f"worker_{wid}.log"
        lf = open(log_path, "w")
        log_files.append(lf)
        cmd = [
            sys.executable,
            "-u",
            "application_engine/batch_apply_multi_ats.py",
            str(LIMIT),
            QUEUE_FILE,
            "--worker-id", str(wid),
            "--total-workers", str(NUM_WORKERS)
        ]
        p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
        processes.append(p)
        print(f"  ⚡ Worker {wid+1}/{NUM_WORKERS} started (PID {p.pid}, logging to {log_path})", flush=True)
        time.sleep(2.5)  # Stagger initial Chromium launches

    print("\n📡 Real-time progress monitoring active across workers...\n", flush=True)

    TARGET_NEW_APPS = int(os.environ.get("TARGET_NEW_APPS", LIMIT))
    TARGET_TOTAL = int(os.environ.get("TARGET_TOTAL", 1253)) if os.environ.get("TARGET_TOTAL") else None
    KEYFILE = os.path.expanduser("~/.config/gcloud/legacy_credentials/google-auto-n8n@decoded-tribute-475218-j4.iam.gserviceaccount.com/adc.json")
    SPREADSHEET_ID = "1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY"

    initial_count = 854
    try:
        if os.path.exists(KEYFILE):
            import gspread
            gc = gspread.service_account(filename=KEYFILE)
            sh = gc.open_by_key(SPREADSHEET_ID)
            ws = sh.get_worksheet(0)
            col_a = ws.col_values(1)
            initial_count = len([c for c in col_a[1:] if c.strip()])
            target_total = TARGET_TOTAL if TARGET_TOTAL else initial_count + TARGET_NEW_APPS
            print(f"📊 Starting Sheet Total: {initial_count}. Target: {target_total} confirmed applications (+{target_total - initial_count} needed).", flush=True)
    except Exception as e:
        print(f"⚠️ [Sheet Monitor Notice]: {e}", flush=True)
        target_total = TARGET_TOTAL if TARGET_TOTAL else initial_count + TARGET_NEW_APPS

    try:
        poll_timer = 0
        while any(p.poll() is None for p in processes):
            time.sleep(5)
            poll_timer += 5
            if poll_timer % 15 == 0:
                try:
                    if os.path.exists(KEYFILE):
                        col_a = ws.col_values(1)
                        current_count = len([c for c in col_a[1:] if c.strip()])
                        print(f"📊 [Monitor] Current Confirmed Applications: {current_count}/{target_total} (+{current_count - initial_count} new)", flush=True)
                        if current_count >= target_total:
                            print(f"🎯 Target of {TARGET_NEW_APPS} new applications reached ({current_count} total)! Gracefully stopping workers...", flush=True)
                            for p in processes:
                                if p.poll() is None:
                                    p.terminate()
                            break
                except Exception:
                    pass
    finally:
        for p in processes:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        for lf in log_files:
            try:
                lf.close()
            except Exception:
                pass

    print("🏁 Parallel orchestrator execution finished.", flush=True)
