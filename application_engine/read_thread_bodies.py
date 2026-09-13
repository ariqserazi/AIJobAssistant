import os
import sys
import json
import time
import urllib.parse
from Foundation import NSBundle
import objc

NSBundle.bundleWithPath_("/System/Library/Frameworks/ScriptingBridge.framework").load()
SBApplication = objc.lookUpClass("SBApplication")
app = SBApplication.applicationWithBundleIdentifier_("com.google.Chrome")

tab = None
for w in app.windows():
    for t in w.tabs():
        if "mail.google.com" in (t.URL() or ""):
            tab = t
            break
    if tab:
        break

if not tab:
    print("No Gmail tab found")
    sys.exit(1)

def get_email_body_for_search(query):
    # Set hash
    encoded = urllib.parse.quote(query)
    tab.executeJavascript_(f"window.location.hash = '#search/{encoded}';")
    time.sleep(3.0)
    
    # Check if rows exist
    js_check = """
    (() => {
        const rows = document.querySelectorAll("tr.zA");
        return rows.length;
    })()
    """
    count = tab.executeJavascript_(js_check)
    if not count or count == 0:
        # Try reloading to force search render
        tab.executeJavascript_("window.location.reload();")
        time.sleep(4.5)
        
    # Click first row
    js_click = """
    (() => {
        const r = document.querySelector("tr.zA");
        if (r) {
            const subj = (r.querySelector(".bog") || {}).textContent || "";
            const date = (r.querySelector(".xW") || {}).textContent || "";
            r.click();
            return JSON.stringify({ clicked: true, subject: subj, date: date });
        }
        return JSON.stringify({ clicked: false });
    })()
    """
    click_res = tab.executeJavascript_(js_click)
    time.sleep(2.5)
    
    # Read email body
    js_read = """
    (() => {
        // Expand all
        document.querySelectorAll("[aria-label='Expand all'], div[aria-label='Expand all']").forEach(e => e.click());
        document.querySelectorAll(".kQ, div[role='button'][aria-expanded='false']").forEach(e => e.click());
        
        const msgs = Array.from(document.querySelectorAll(".ii.gt"));
        const subj = (document.querySelector("h2.hP") || {}).textContent || "";
        const body = msgs.map(m => m.textContent.trim()).join("\\n---MESSAGE---\\n");
        return JSON.stringify({ subject: subj, body: body });
    })()
    """
    res = tab.executeJavascript_(js_read)
    
    # Go back to search
    tab.executeJavascript_("window.history.back();")
    time.sleep(1.5)
    return res

targets = [
    ("Wispr", "Wispr Flow Application Update"),
    ("Vapi", "Your Application to Vapi"),
    ("LABHOUSE", "LABHOUSE - Application Update"),
    ("Sentry", "Thank you for your interest in Sentry newer_than:4d"),
    ("Trillium", "ACTION REQUIRED: Next Steps to Trillium"),
    ("Gallup", "Complete talent assessment"),
    ("PDT", "Thank you for applying to PDT Partners"),
    ("Roblox", "[Action Required] Your Roblox Application")
]

results = {}
for name, q in targets:
    print(f"Reading {name}...")
    raw = get_email_body_for_search(q)
    try:
        data = json.loads(raw)
        results[name] = data
        print(f"  Subject: {data.get('subject')}")
        print(f"  Body excerpt: {data.get('body', '')[:300]}")
    except Exception as e:
        print(f"  Error reading {name}: {e}")
        results[name] = {"raw": raw}
    print("-" * 50)

with open("/tmp/full_thread_bodies.json", "w") as f:
    json.dump(results, f, indent=2)

tab.executeJavascript_("window.location.hash = '#inbox';")
print("All thread bodies saved to /tmp/full_thread_bodies.json")
