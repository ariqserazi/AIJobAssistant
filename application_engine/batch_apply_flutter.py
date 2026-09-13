#!/usr/bin/env python3
"""
batch_apply_flutter.py - Automated batch application engine dedicated to Flutter & Mobile roles.
Applies to verified Flutter jobs across Ashby, Greenhouse, and Lever.
"""

import os
import sys
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ENGINE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ENGINE_DIR))

from batch_apply_multi_ats import apply_to_job

TARGETS_FILE = ENGINE_DIR.parent / "flutter_jobs_ready.json"

def main():
    target_count = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    print(f"=== 🚀 Starting Flutter Applications Batch (Target: {target_count}) ===")

    if not TARGETS_FILE.exists():
        print(f"Error: {TARGETS_FILE} not found!")
        sys.exit(1)

    with open(TARGETS_FILE) as f:
        jobs = json.load(f)

    print(f"Loaded {len(jobs)} curated Flutter & Mobile roles.")

    success_count = 0
    failed_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )

        for i, job in enumerate(jobs[:target_count], start=1):
            print(f"\n[{i}/{target_count}] Processing Flutter Role: {job['role']} @ {job['company']}...")
            try:
                res = apply_to_job(browser, job)
                if res:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                print(f"  ❌ Error applying to {job['company']}: {e}")
                failed_count += 1

            time.sleep(3)

        browser.close()

    print(f"\n{'='*60}")
    print(f"=== Flutter Batch Complete: {success_count} submitted & confirmed, {failed_count} skipped/pending ===")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
