import os
import sys
import json
import time
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

def search_query(query):
    js_search = f"""
    (() => {{
        const input = document.querySelector("input[name='q']");
        input.focus();
        input.value = {json.dumps(query)};
        input.dispatchEvent(new Event("input", {{ bubbles: true }}));
        input.dispatchEvent(new KeyboardEvent("keydown", {{ key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }}));
        input.dispatchEvent(new KeyboardEvent("keypress", {{ key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }}));
        input.dispatchEvent(new KeyboardEvent("keyup", {{ key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }}));
        return "searched";
    }})()
    """
    tab.executeJavascript_(js_search)
    time.sleep(3.5)

def read_first_thread():
    js_click = """
    (() => {
        const r = document.querySelector("tr.zA");
        if (r) {
            r.click();
            return true;
        }
        return false;
    })()
    """
    clicked = tab.executeJavascript_(js_click)
    if not clicked:
        return "Not found"
    time.sleep(2.0)
    
    # Expand
    tab.executeJavascript_("""
    (() => {
        document.querySelectorAll("[aria-label='Expand all'], div[aria-label='Expand all']").forEach(e => e.click());
        document.querySelectorAll(".kQ, div[role='button'][aria-expanded='false']").forEach(e => e.click());
    })()
    """)
    time.sleep(0.8)
    
    js_read = """
    (() => {
        const msgs = Array.from(document.querySelectorAll(".ii.gt"));
        const subj = (document.querySelector("h2.hP") || {}).textContent || "";
        const text = msgs.map(m => m.textContent.trim()).join("\\n---MESSAGE---\\n");
        return JSON.stringify({ subject: subj, body: text });
    })()
    """
    res = tab.executeJavascript_(js_read)
    tab.executeJavascript_("window.history.back()")
    time.sleep(2.0)
    return res

targets = [
    ("Wispr Flow", "from:wispr OR subject:\"Wispr Flow\""),
    ("Vapi", "from:vapi OR subject:\"Vapi\""),
    ("LABHOUSE", "from:labhouse OR subject:\"LABHOUSE\""),
    ("PDT Partners", "from:pdt OR subject:\"PDT Partners\""),
    ("Roblox", "subject:\"Roblox\" newer_than:2d"),
    ("Trillium", "subject:\"Trillium\""),
    ("Gallup", "subject:\"Gallup\""),
    ("Sentry", "subject:\"Sentry\" newer_than:4d")
]

results = {}
for name, q in targets:
    print(f"\nSearching for {name} ({q})...")
    search_query(q)
    data = read_first_thread()
    print(f"Result for {name}:")
    try:
        parsed = json.loads(data)
        print(f"Subject: {parsed['subject']}")
        print(f"Body: {parsed['body'][:400]}")
        results[name] = parsed
    except Exception as e:
        print(f"Raw: {data[:300]}")
        results[name] = {"raw": data}

with open("/tmp/target_threads_inspected.json", "w") as f:
    json.dump(results, f, indent=2)

tab.setURL_("https://mail.google.com/mail/u/1/#inbox")
print("\nSaved all thread details to /tmp/target_threads_inspected.json and reset tab to inbox.")
