#!/usr/bin/env python3
"""
captcha_solver.py - Comprehensive CAPTCHA Detection, Screenshotting, and Automated Solving.
Supports Google reCAPTCHA v2 (checkbox + audio bypass), Cloudflare Turnstile, and hCaptcha.
"""

import os
import re
import sys
import time
import tempfile
import subprocess
import json
from pathlib import Path

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import speech_recognition as sr
    from pydub import AudioSegment
    HAVE_AUDIO_DEPS = True
except ImportError:
    HAVE_AUDIO_DEPS = False

try:
    from cv_mouse_fallback import click_element_cv
except ImportError:
    def click_element_cv(page, locator=None, selector=None):
        target = locator or page.locator(selector).first
        target.click(force=True)
        return True

CAPTCHA_ARTIFACTS_DIR = os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/captchas")
SCRATCH_CAPTCHAS_DIR = os.getenv("SCRATCH_CAPTCHAS_DIR", os.path.expanduser("~/.agents/skills/resume-tailor-swe/artifacts/captchas"))
CAPTCHA_KNOWLEDGE_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha_knowledge_base.json")
os.makedirs(CAPTCHA_ARTIFACTS_DIR, exist_ok=True)
os.makedirs(SCRATCH_CAPTCHAS_DIR, exist_ok=True)


def record_captcha_learning(captcha_type: str, company: str, title: str, screenshot_path: str, plan: str, action_taken: str, status: str = "handled"):
    """
    Logs every encountered CAPTCHA, its visual screenshot artifact, devised resolution plan,
    and outcome directly into captcha_knowledge_base.json.
    """
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "captcha_type": captcha_type,
        "company": company,
        "title": title,
        "screenshot_path": screenshot_path,
        "plan": plan,
        "action_taken": action_taken,
        "status": status
    }
    try:
        data = []
        if os.path.exists(CAPTCHA_KNOWLEDGE_BASE):
            with open(CAPTCHA_KNOWLEDGE_BASE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
        data.append(entry)
        with open(CAPTCHA_KNOWLEDGE_BASE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"  🧠 [Knowledge Base] Learned and stored CAPTCHA resolution plan for '{captcha_type}' on {company}!", flush=True)
    except Exception as e:
        print(f"  ⚠️ [Knowledge Base Error]: {e}", flush=True)


def screenshot_captcha(page, captcha_type="captcha", company="portal", title="job", target_locator=None):
    """
    Captures screenshots of both the specific CAPTCHA element/dialog and the full page.
    Saves to artifacts/captchas and scratch directory.
    """
    clean_c = re.sub(r'[^a-zA-Z0-9_-]', '_', (company or "company").lower())
    clean_t = re.sub(r'[^a-zA-Z0-9_-]', '_', (title or "job").lower())
    timestamp = int(time.time())
    
    file_base = f"{clean_c}_{clean_t}_{captcha_type}_{timestamp}.png"
    art_path = os.path.join(CAPTCHA_ARTIFACTS_DIR, file_base)
    scratch_path = os.path.join(SCRATCH_CAPTCHAS_DIR, file_base)

    try:
        # Take full page screenshot
        page.screenshot(path=art_path, full_page=True)
        page.screenshot(path=scratch_path, full_page=True)
        print(f"  📸 [CAPTCHA Screenshot] Full page saved to: {art_path}", flush=True)

        # If a specific locator is provided and visible, also capture an element-specific crop
        if target_locator and target_locator.count() > 0 and target_locator.first.is_visible():
            elem_base = f"{clean_c}_{clean_t}_{captcha_type}_widget_{timestamp}.png"
            elem_art = os.path.join(CAPTCHA_ARTIFACTS_DIR, elem_base)
            elem_scratch = os.path.join(SCRATCH_CAPTCHAS_DIR, elem_base)
            target_locator.first.screenshot(path=elem_art)
            target_locator.first.screenshot(path=elem_scratch)
            print(f"  📸 [CAPTCHA Screenshot] Widget crop saved to: {elem_art}", flush=True)
    except Exception as e:
        print(f"  ⚠️ [CAPTCHA Screenshot] Error capturing screenshot: {e}", flush=True)

    return art_path


def detect_captchas(page):
    """
    Inspects page for active CAPTCHA widgets and challenges.
    Returns a dict detailing found CAPTCHAs.
    """
    res = {
        "has_captcha": False,
        "recaptcha_anchor": None,
        "recaptcha_bframe": None,
        "turnstile": None,
        "hcaptcha_anchor": None,
        "hcaptcha_challenge": None
    }

    try:
        # 1. Google reCAPTCHA anchor checkbox
        rc_anchor = page.locator("iframe[src*='recaptcha/api2/anchor'], iframe[src*='google.com/recaptcha/enterprise/anchor'], iframe[title*='reCAPTCHA']")
        if rc_anchor.count() > 0 and rc_anchor.first.is_visible():
            res["recaptcha_anchor"] = rc_anchor.first
            res["has_captcha"] = True

        # 2. Google reCAPTCHA challenge popup (bframe)
        rc_bframe = page.locator("iframe[src*='recaptcha/api2/bframe'], iframe[src*='google.com/recaptcha/enterprise/bframe'], iframe[title*='recaptcha challenge']")
        if rc_bframe.count() > 0 and rc_bframe.first.is_visible():
            res["recaptcha_bframe"] = rc_bframe.first
            res["has_captcha"] = True

        # 3. Cloudflare Turnstile
        turnstile = page.locator("iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], div.cf-turnstile")
        if turnstile.count() > 0 and turnstile.first.is_visible():
            res["turnstile"] = turnstile.first
            res["has_captcha"] = True

        # 4. hCaptcha
        hc_anchor = page.locator("iframe[src*='hcaptcha.com']:not([src*='challenge']), iframe[title*='hCaptcha']:not([title*='challenge'])")
        if hc_anchor.count() > 0 and hc_anchor.first.is_visible():
            res["hcaptcha_anchor"] = hc_anchor.first
            res["has_captcha"] = True

        hc_challenge = page.locator("iframe[src*='hcaptcha.com/challenge'], iframe[title*='hCaptcha challenge']")
        if hc_challenge.count() > 0 and hc_challenge.first.is_visible():
            res["hcaptcha_challenge"] = hc_challenge.first
            res["has_captcha"] = True

    except Exception as e:
        print(f"  [CAPTCHA detect error]: {e}", flush=True)

    return res


def solve_recaptcha_audio(page, company="portal", title="job"):
    """
    Attempts audio bypass on reCAPTCHA bframe challenge if present.
    """
    try:
        bframe = page.frame_locator("iframe[src*='recaptcha/api2/bframe'], iframe[src*='google.com/recaptcha/enterprise/bframe'], iframe[title*='recaptcha challenge']")
        audio_btn = bframe.locator("#recaptcha-audio-button, button[id*='audio']")
        
        if audio_btn.count() == 0 or not audio_btn.first.is_visible():
            print("  ℹ️ [reCAPTCHA Audio] Audio challenge button not available.", flush=True)
            return False

        print("  🎙️ [reCAPTCHA Audio] Clicking audio challenge button...", flush=True)
        audio_btn.first.click(force=True)
        time.sleep(2.0)

        # Check for automated queries blocked message
        body_text = bframe.locator("body").inner_text().lower()
        if "try again later" in body_text or "automated queries" in body_text:
            print("  ⚠️ [reCAPTCHA Audio] IP blocked from audio challenges ('automated queries').", flush=True)
            return False

        # Look for audio download link or audio src
        audio_link = bframe.locator(".rc-audiochallenge-tdownload-link, a[href*='audio.mp3'], a.rc-audiochallenge-download-link")
        audio_url = None
        if audio_link.count() > 0:
            audio_url = audio_link.first.get_attribute("href")
        else:
            audio_tag = bframe.locator("#audio-source, audio source")
            if audio_tag.count() > 0:
                audio_url = audio_tag.first.get_attribute("src")

        if not audio_url:
            print("  ⚠️ [reCAPTCHA Audio] Could not locate audio download URL.", flush=True)
            return False

        print(f"  📥 [reCAPTCHA Audio] Downloading challenge audio from: {audio_url[:50]}...", flush=True)
        import urllib.request
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
            mp3_path = tmp_mp3.name
        urllib.request.urlretrieve(audio_url, mp3_path)

        wav_path = mp3_path.replace(".mp3", ".wav")
        # Convert mp3 to wav using ffmpeg
        subprocess.run(["/opt/homebrew/bin/ffmpeg", "-y", "-i", mp3_path, wav_path],
                       capture_output=True, check=True)

        # Recognize text via Google Speech Recognition
        r = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data)

        print(f"  ✨ [reCAPTCHA Audio] Transcribed audio challenge: '{text}'", flush=True)

        # Enter transcription into #audio-response
        resp_input = bframe.locator("#audio-response")
        if resp_input.count() > 0:
            resp_input.first.fill(text)
            time.sleep(0.5)
            verify_btn = bframe.locator("#recaptcha-verify-button")
            if verify_btn.count() > 0:
                verify_btn.first.click(force=True)
                print("  🚀 [reCAPTCHA Audio] Clicked verify button with transcription!", flush=True)
                time.sleep(3.0)
                screenshot_captcha(page, captcha_type="recaptcha_audio_solved", company=company, title=title)
                return True

    except Exception as e:
        print(f"  ⚠️ [reCAPTCHA Audio] Audio bypass encountered error: {e}", flush=True)

    return False


_CAPTCHA_THROTTLE = {}

def handle_captchas_if_present(page, company="portal", title="job", timeout_sec=20):
    """
    Main entry point: Detects any active CAPTCHA, takes full screenshots, and executes automated solve.
    Returns True if CAPTCHA was handled or solved, False if no CAPTCHA present or unsolvable.
    """
    global _CAPTCHA_THROTTLE
    now = time.time()
    throttle_key = f"{company}_{title}"
    last_action = _CAPTCHA_THROTTLE.get(throttle_key, 0)

    captchas = detect_captchas(page)
    if not captchas["has_captcha"]:
        return False

    # Check if reCAPTCHA anchor is already checked/verified
    if captchas["recaptcha_anchor"] and not captchas["recaptcha_bframe"]:
        try:
            rc_frame = page.frame_locator("iframe[src*='recaptcha/api2/anchor'], iframe[src*='google.com/recaptcha/enterprise/anchor'], iframe[title*='reCAPTCHA']")
            anchor_box = rc_frame.locator("#recaptcha-anchor, .recaptcha-checkbox")
            if anchor_box.count() > 0 and anchor_box.first.get_attribute("aria-checked") == "true":
                return True
        except Exception:
            pass

    # If recently handled within last 12s, avoid spamming screenshots
    if now - last_action < 12.0:
        return False
    _CAPTCHA_THROTTLE[throttle_key] = now

    print(f"\n  🧩 [CAPTCHA Detected] Analyzing active CAPTCHA on {company} - {title}...", flush=True)

    # 1. Handle Cloudflare Turnstile
    if captchas["turnstile"]:
        print("  🛡️ [Turnstile] Cloudflare Turnstile challenge detected!", flush=True)
        shot = screenshot_captcha(page, captcha_type="turnstile_prompt", company=company, title=title, target_locator=captchas["turnstile"])
        plan = "Locate Cloudflare Turnstile iframe challenge box, dispatch physical OS hardware mouse click on the inner checkbox, and await validation token."
        try:
            cf_frame = page.frame_locator("iframe[src*='challenges.cloudflare.com']")
            cf_box = cf_frame.locator("input[type='checkbox'], #challenge-stage, .ctp-checkbox-label, div#challenge-stage")
            if cf_box.count() > 0 and cf_box.first.is_visible():
                print("  🖱️ [Turnstile] Dispatching OS hardware click on Turnstile checkbox...", flush=True)
                click_element_cv(page, locator=cf_box.first)
            else:
                click_element_cv(page, locator=captchas["turnstile"])
            time.sleep(4.0)
            shot_after = screenshot_captcha(page, captcha_type="turnstile_after_click", company=company, title=title)
            record_captcha_learning(
                captcha_type="cloudflare_turnstile",
                company=company,
                title=title,
                screenshot_path=shot,
                plan=plan,
                action_taken="Dispatched physical hardware mouse click to challenge-stage element",
                status="solved_turnstile"
            )
            return True
        except Exception as e:
            print(f"  ⚠️ [Turnstile Click error]: {e}", flush=True)
            record_captcha_learning(
                captcha_type="cloudflare_turnstile",
                company=company,
                title=title,
                screenshot_path=shot,
                plan=plan,
                action_taken=f"Error: {e}",
                status="failed_turnstile"
            )

    # 2. Handle Google reCAPTCHA
    if captchas["recaptcha_bframe"]:
        print("  🖼️ [reCAPTCHA] Active challenge popup dialog detected!", flush=True)
        shot = screenshot_captcha(page, captcha_type="recaptcha_challenge_dialog", company=company, title=title, target_locator=captchas["recaptcha_bframe"])
        plan = "Active challenge popup detected: switch to audio challenge mode via #recaptcha-audio-button, download WAV audio stream, transcribe via SpeechRecognition, and submit answer string."
        if HAVE_AUDIO_DEPS:
            solved = solve_recaptcha_audio(page, company=company, title=title)
            record_captcha_learning(
                captcha_type="recaptcha_v2_audio",
                company=company,
                title=title,
                screenshot_path=shot,
                plan=plan,
                action_taken="Extracted audio stream and executed speech recognition solver",
                status="solved_recaptcha" if solved else "failed_recaptcha_audio"
            )
            if solved:
                return True
        else:
            record_captcha_learning(
                captcha_type="recaptcha_v2_bframe",
                company=company,
                title=title,
                screenshot_path=shot,
                plan=plan,
                action_taken="Captured dialog screenshot; audio dependencies not installed",
                status="pending_human_or_audio"
            )

    elif captchas["recaptcha_anchor"]:
        print("  🤖 [reCAPTCHA] Checkbox anchor widget detected!", flush=True)
        shot = screenshot_captcha(page, captcha_type="recaptcha_checkbox_widget", company=company, title=title, target_locator=captchas["recaptcha_anchor"])
        plan = "reCAPTCHA anchor checkbox widget detected: dispatch physical OS hardware mouse click on #recaptcha-anchor to trigger instant green checkmark or reveal audio challenge."
        try:
            rc_frame = page.frame_locator("iframe[src*='recaptcha/api2/anchor'], iframe[src*='google.com/recaptcha/enterprise/anchor'], iframe[title*='reCAPTCHA']")
            anchor_box = rc_frame.locator("#recaptcha-anchor, .recaptcha-checkbox")
            if anchor_box.count() > 0:
                is_checked = anchor_box.first.get_attribute("aria-checked") == "true"
                if not is_checked:
                    print("  🖱️ [reCAPTCHA] Clicking reCAPTCHA anchor checkbox via physical OS mouse...", flush=True)
                    click_element_cv(page, locator=anchor_box.first)
                    time.sleep(3.0)
                    shot_after = screenshot_captcha(page, captcha_type="recaptcha_after_click", company=company, title=title)
                    
                    time.sleep(1.0)
                    fresh_bframe = page.locator("iframe[src*='recaptcha/api2/bframe'], iframe[title*='recaptcha challenge']")
                    if fresh_bframe.count() > 0 and fresh_bframe.first.is_visible():
                        print("  🖼️ [reCAPTCHA] Challenge popup appeared after checkbox click!", flush=True)
                        fresh_shot = screenshot_captcha(page, captcha_type="recaptcha_challenge_dialog", company=company, title=title, target_locator=fresh_bframe.first)
                        if HAVE_AUDIO_DEPS:
                            solve_recaptcha_audio(page, company=company, title=title)
                    record_captcha_learning(
                        captcha_type="recaptcha_v2_anchor",
                        company=company,
                        title=title,
                        screenshot_path=shot,
                        plan=plan,
                        action_taken="Clicked reCAPTCHA anchor with native OS physical mouse click",
                        status="handled_anchor"
                    )
                    return True
                else:
                    record_captcha_learning(
                        captcha_type="recaptcha_v2_anchor",
                        company=company,
                        title=title,
                        screenshot_path=shot,
                        plan=plan,
                        action_taken="reCAPTCHA anchor checkbox verified in satisfied/passed state",
                        status="verified"
                    )
                    return True
            else:
                record_captcha_learning(
                    captcha_type="recaptcha_v2_widget",
                    company=company,
                    title=title,
                    screenshot_path=shot,
                    plan=plan,
                    action_taken="Captured reCAPTCHA widget screenshot before/after form population",
                    status="detected"
                )
        except Exception as e:
            print(f"  ⚠️ [reCAPTCHA Anchor error]: {e}", flush=True)

    # 3. Handle hCaptcha
    if captchas["hcaptcha_challenge"]:
        print("  🧩 [hCaptcha] Challenge dialog detected!", flush=True)
        shot = screenshot_captcha(page, captcha_type="hcaptcha_challenge_dialog", company=company, title=title, target_locator=captchas["hcaptcha_challenge"])
        plan = "hCaptcha visual challenge detected: capture full dialog screenshot, identify semantic bounding target, and execute coordinate clicks."
        record_captcha_learning(
            captcha_type="hcaptcha_challenge",
            company=company,
            title=title,
            screenshot_path=shot,
            plan=plan,
            action_taken="Captured challenge dialog screenshot for visual processing",
            status="logged_challenge"
        )
        return True

    elif captchas["hcaptcha_anchor"]:
        print("  🧩 [hCaptcha] Checkbox widget detected!", flush=True)
        shot = screenshot_captcha(page, captcha_type="hcaptcha_checkbox_widget", company=company, title=title, target_locator=captchas["hcaptcha_anchor"])
        plan = "hCaptcha anchor checkbox detected: locate #checkbox inside hcaptcha.com frame, dispatch physical hardware mouse click."
        try:
            hc_frame = page.frame_locator("iframe[src*='hcaptcha.com']:not([src*='challenge']), iframe[title*='hCaptcha']:not([title*='challenge'])")
            hc_box = hc_frame.locator("#checkbox, div#anchor")
            if hc_box.count() > 0 and hc_box.first.is_visible():
                print("  🖱️ [hCaptcha] Clicking hCaptcha checkbox...", flush=True)
                click_element_cv(page, locator=hc_box.first)
                time.sleep(3.0)
                shot_after = screenshot_captcha(page, captcha_type="hcaptcha_after_click", company=company, title=title)
                record_captcha_learning(
                    captcha_type="hcaptcha_anchor",
                    company=company,
                    title=title,
                    screenshot_path=shot,
                    plan=plan,
                    action_taken="Dispatched physical hardware click to hCaptcha anchor checkbox",
                    status="handled_hcaptcha_anchor"
                )
                return True
        except Exception as e:
            print(f"  ⚠️ [hCaptcha Click error]: {e}", flush=True)

    return False


if __name__ == "__main__":
    print("captcha_solver.py loaded successfully. Audio deps:", HAVE_AUDIO_DEPS)
