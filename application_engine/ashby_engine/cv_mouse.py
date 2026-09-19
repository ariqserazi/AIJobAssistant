#!/usr/bin/env python3
"""
cv_mouse.py - Hardware OS Physical Mouse Click & Window Activation.
Dispatches genuine OS hardware events (PyAutoGUI) to bypass anti-bot and spam filters.
"""

import os
import time
import tempfile
import subprocess
import pyautogui

def bring_window_to_front(app_name="Google Chrome for Testing"):
    """Brings Chrome to the foreground so the user sees it and clicks land natively."""
    script = f'''
    tell application "System Events"
        set processList to (name of every process)
        if "{app_name}" is in processList then
            tell application "{app_name}" to activate
        else if "Google Chrome" is in processList then
            tell application "Google Chrome" to activate
        else if "Chromium" is in processList then
            tell application "Chromium" to activate
        end if
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.4)
    except Exception as e:
        pass


def click_element_cv(page, locator=None, selector='button[type="submit"], button:has-text("Submit Application")', app_name="Google Chrome for Testing", min_confidence=0.80) -> bool:
    """
    Locates an element and dispatches a true native OS hardware mouse click.
    """
    use_mouse = os.getenv("USE_MOUSE", "false").lower() in ["true", "1", "yes"]
    if not use_mouse:
        return False

    try:
        target = locator if locator is not None else page.locator(selector).first
        if not target.is_visible():
            print("  [CV Mouse] Target submit button is not currently visible on page.", flush=True)
            return False

        # 1. Scroll into view
        target.scroll_into_view_if_needed()
        time.sleep(0.4)

        import fcntl
        mouse_lock = open("/tmp/physical_mouse.lock", "w")
        fcntl.flock(mouse_lock, fcntl.LOCK_EX)
        try:
            # 2. Bring window to front
            bring_window_to_front(app_name)
            time.sleep(0.4)

        # 3. Viewport-to-Screen Coordinate Math (Exact calibrated Chrome toolbar offset on macOS)
        try:
            coords = target.evaluate('''el => {
                const r = el.getBoundingClientRect();
                const toolbarH = (window.outerHeight - window.innerHeight) > 0 ? (window.outerHeight - window.innerHeight) : 80;
                return {
                    x: window.screenX + r.left + r.width / 2,
                    y: window.screenY + toolbarH + r.top + r.height / 2
                };
            }''')
            center_x = int(coords['x'])
            center_y = int(coords['y'])
            sw, sh = pyautogui.size()
            if center_y >= sh or center_y < 0 or center_x >= sw or center_x < 0:
                print(f"  [CV Mouse] Coordinates ({center_x}, {center_y}) out of screen bounds ({sw}x{sh}). Re-centering...", flush=True)
                target.scroll_into_view_if_needed()
                time.sleep(0.5)
                coords2 = target.evaluate('''el => {
                    const r = el.getBoundingClientRect();
                    const toolbarH = (window.outerHeight - window.innerHeight) > 0 ? (window.outerHeight - window.innerHeight) : 80;
                    return {
                        x: window.screenX + r.left + r.width / 2,
                        y: window.screenY + toolbarH + r.top + r.height / 2
                    };
                }''')
                center_x = max(10, min(sw - 10, int(coords2['x'])))
                center_y = max(10, min(sh - 10, int(coords2['y'])))

            print(f"  [CV Mouse] Calculated screen coordinates: Point({center_x}, {center_y})", flush=True)

            # Smooth physical mouse glide
            print("  [CV Mouse] Gliding physical mouse cursor with natural easing...", flush=True)
            pyautogui.moveTo(center_x, center_y, duration=0.5, tween=pyautogui.easeInOutQuad)
            time.sleep(0.15)

            # Detect toggleable elements (radios, checkboxes, options, labels) vs standard action buttons
            is_toggle = target.evaluate('''el => {
                const tag = (el.tagName || "").toLowerCase();
                const role = el.getAttribute("role") || "";
                const cls = el.className || "";
                return tag === "label" || tag === "input" || role === "radio" || role === "checkbox" || cls.includes("option") || cls.includes("checkbox") || cls.includes("radio");
            }''')

            if is_toggle:
                # Single authoritative click on the interactive target to trigger React state cleanly without double-toggling
                try:
                    target.click(timeout=3000, force=True)
                except Exception:
                    pyautogui.mouseDown()
                    time.sleep(0.1)
                    pyautogui.mouseUp()
            else:
                # Native hardware OS click for submit buttons
                print("  [CV Mouse] Dispatching native OS hardware click (isTrusted: true)...", flush=True)
                pyautogui.mouseDown()
                time.sleep(0.12)
                pyautogui.mouseUp()
                time.sleep(0.1)
                try:
                    target.click(timeout=3000)
                except Exception:
                    pass

            print("  [CV Mouse] Hardware click executed successfully.", flush=True)
            return True

        except Exception as e_math:
            print(f"  [CV Mouse] Mathematical coordinate dispatch failed ({e_math}). Falling back to OpenCV...", flush=True)

        # 4. OpenCV Template Matching Fallback
        import cv2
        import numpy as np

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_template:
            template_path = tmp_template.name
        target.screenshot(path=template_path)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_screen:
            screen_path = tmp_screen.name
        subprocess.run(["screencapture", "-x", screen_path], check=True)

        screen_img = cv2.imread(screen_path)
        template_img = cv2.imread(template_path)

        if screen_img is None or template_img is None:
            return False

        logical_w, logical_h = pyautogui.size()
        scale_x = screen_img.shape[1] / logical_w
        scale_y = screen_img.shape[0] / logical_h

        res = cv2.matchTemplate(screen_img, template_img, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= min_confidence:
            h, w = template_img.shape[:2]
            best_x = int((max_loc[0] + w / 2) / scale_x)
            best_y = int((max_loc[1] + h / 2) / scale_y)
            print(f"  [CV Mouse] OpenCV matched template at Point({best_x}, {best_y}) with confidence {max_val:.2f}", flush=True)
            pyautogui.moveTo(best_x, best_y, duration=0.6, tween=pyautogui.easeInOutQuad)
            time.sleep(0.2)
            pyautogui.mouseDown()
            time.sleep(0.12)
            pyautogui.mouseUp()
            return True
        else:
            print(f"  [CV Mouse] OpenCV match confidence ({max_val:.2f}) below threshold ({min_confidence})", flush=True)
            return False
            
    except Exception as e:
        print(f"  [CV Mouse] Execution error: {e}", flush=True)
        return False
    finally:
        try:
            fcntl.flock(mouse_lock, fcntl.LOCK_UN)
            mouse_lock.close()
        except Exception:
            pass
        for p in [locals().get("template_path"), locals().get("screen_path")]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
