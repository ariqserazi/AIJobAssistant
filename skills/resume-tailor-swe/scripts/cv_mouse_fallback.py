#!/usr/bin/env python3
"""
cv_mouse_fallback.py - Computer Vision Physical Mouse Click Fallback
Bypasses anti-bot / invisible reCAPTCHA detection (which detects synthetic CDP isTrusted: false clicks)
by using OpenCV template matching and PyAutoGUI to dispatch true native OS-level hardware mouse events.
"""

import os
import sys
import time
import tempfile
import subprocess
import pyautogui
import cv2
import numpy as np

def bring_window_to_front(app_name="Google Chrome"):
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
        print(f"  [CV Mouse] Notice: Could not activate window via osascript ({e})", flush=True)


def click_element_cv(page, locator=None, selector='button[type="submit"], button:has-text("Submit Application")', app_name="Google Chrome", min_confidence=0.80):
    """
    Locates an element visually using OpenCV template matching and clicks it with native OS hardware events.
    
    Args:
        page: Playwright Page object (must be running in non-headless mode).
        locator: Playwright Locator (optional, overrides selector).
        selector: CSS selector string if locator is not provided.
        app_name: Name of application to bring to front via osascript.
        min_confidence: Normalized OpenCV matching threshold (0.0 to 1.0).
        
    Returns:
        bool: True if element was successfully located and clicked via physical mouse, False otherwise.
    """
    try:
        target = locator if locator is not None else page.locator(selector).first
        if not target.is_visible():
            print("  [CV Fallback] Target element is not currently visible on page.")
            return False

        # 1. Scroll target into view
        target.scroll_into_view_if_needed()
        time.sleep(0.5)

        import fcntl
        mouse_lock = open("/tmp/physical_mouse.lock", "w")
        fcntl.flock(mouse_lock, fcntl.LOCK_EX)
        try:
            # 2. Bring designated browser window to front
            bring_window_to_front(app_name)
            time.sleep(0.5)

            # 3. Exact Mathematical Viewport-to-Screen Coordinate Calculation
            try:
                coords = target.evaluate('''el => {
                    const r = el.getBoundingClientRect();
                    const navH = window.outerHeight - window.innerHeight;
                    return {
                        x: window.screenX + r.left + r.width / 2,
                        y: window.screenY + navH + r.top + r.height / 2
                    };
                }''')
                center_x = int(coords['x'])
                center_y = int(coords['y'])
                print(f"  [CV Fallback] Exact element screen coordinates calculated: Point({center_x}, {center_y})")
                
                # Smooth physical mouse glide
                print("  [CV Fallback] Gliding physical mouse cursor with natural easing...")
                pyautogui.moveTo(center_x, center_y, duration=0.6, tween=pyautogui.easeInOutQuad)
                time.sleep(0.2)
                
                # True hardware OS click dispatch
                print("  [CV Fallback] Dispatching native OS hardware click (mouseDown -> 120ms -> mouseUp)...")
                pyautogui.mouseDown()
                time.sleep(0.12)
                pyautogui.mouseUp()
                print("  [CV Fallback] Native hardware click executed successfully.")
                return True
            except Exception as e_math:
                print(f"  [CV Fallback] Mathematical coordinate dispatch failed ({e_math}). Falling back to visual OpenCV matching...")

            # 4. Visual OpenCV Template Matching Fallback
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_template:
                template_path = tmp_template.name
            
            target.screenshot(path=template_path)
            
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_screen:
                screen_path = tmp_screen.name
                
            subprocess.run(["screencapture", "-x", screen_path], check=True)
            
            screen_img = cv2.imread(screen_path)
            template_img = cv2.imread(template_path)
            
            if screen_img is None or template_img is None:
                print("  [CV Fallback] Failed to read screen or template image.")
                return False

            logical_w, logical_h = pyautogui.size()
            scale_x = screen_img.shape[1] / logical_w
            scale_y = screen_img.shape[0] / logical_h

            # Match at native Retina resolution for pixel-perfect template matching
            res = cv2.matchTemplate(screen_img, template_img, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            
            print(f"  [CV Fallback] Template Match Confidence: {max_val * 100:.1f}% (Threshold: {min_confidence * 100:.1f}%)")
            
            if max_val < min_confidence:
                print(f"  [CV Fallback] Match confidence {max_val:.2f} below required {min_confidence:.2f}.")
                return False

            match_x, match_y = max_loc
            t_h, t_w = template_img.shape[:2]
            center_x = int((match_x + t_w // 2) / scale_x)
            center_y = int((match_y + t_h // 2) / scale_y)
            
            print(f"  [CV Fallback] Visual button located at logical screen Point({center_x}, {center_y})")
            pyautogui.moveTo(center_x, center_y, duration=0.8, tween=pyautogui.easeInOutQuad)
            time.sleep(0.2)
            
            pyautogui.mouseDown()
            time.sleep(0.12)
            pyautogui.mouseUp()
            print("  [CV Fallback] Visual match hardware click executed successfully.")
            
            try:
                os.remove(template_path)
                os.remove(screen_path)
            except Exception:
                pass
                
            return True
        finally:
            try:
                fcntl.flock(mouse_lock, fcntl.LOCK_UN)
                mouse_lock.close()
            except Exception:
                pass

    except Exception as e:
        print(f"  [CV Fallback] Error during CV mouse click execution: {e}")
        return False

if __name__ == "__main__":
    print("cv_mouse_fallback is intended to be imported as a module or called during anti-bot fallback routines.")
