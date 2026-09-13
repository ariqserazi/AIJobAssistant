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
import time
import subprocess
from pathlib import Path

NUM_WORKERS = 5
QUEUE_FILE = sys.argv[2] if len(sys.argv) > 2 else "application_engine/internship_queue_800.json"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 800

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

print("\n📡 Real-time progress monitoring active across all 3 workers...\n", flush=True)

try:
    while any(p.poll() is None for p in processes):
        time.sleep(5)
finally:
    for lf in log_files:
        try:
            lf.close()
        except Exception:
            pass

print("🏁 All parallel workers completed.", flush=True)
