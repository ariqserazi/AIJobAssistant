import os
import sys
import json
import time
import re
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
    print("Error: No Gmail tab found in Chrome!")
    sys.exit(1)

def execute_search(query):
    js_search = f"""
    (() => {{
        const input = document.querySelector("input[name='q']");
        if (!input) return "no-input";
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

def scrape_current_rows():
    js_rows = """
    (() => {
        const rows = Array.from(document.querySelectorAll("tr.zA"));
        return JSON.stringify(rows.map(r => {
            const sender = (r.querySelector(".yX") || r.querySelector(".yW") || {}).textContent || "";
            const subject = (r.querySelector(".bog") || {}).textContent || "";
            const snippet = (r.querySelector(".y2") || {}).textContent || "";
            const date = (r.querySelector(".xW") || {}).textContent || "";
            const id = r.getAttribute("id") || "";
            return {
                id: id,
                sender: sender.trim(),
                subject: subject.trim(),
                snippet: snippet.trim(),
                date: date.trim()
            };
        }));
    })()
    """
    res = tab.executeJavascript_(js_rows)
    try:
        return json.loads(res)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return []

def get_thread_body(row_index):
    # Click row at index, read full text, then go back
    js_click = f"""
    (() => {{
        const rows = Array.from(document.querySelectorAll("tr.zA"));
        if (rows[{row_index}]) {{
            rows[{row_index}].click();
            return true;
        }}
        return false;
    }})()
    """
    clicked = tab.executeJavascript_(js_click)
    if not clicked:
        return ""
    time.sleep(2.0)
    
    # Expand collapsed messages
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
        return msgs.map(m => m.textContent.trim()).join("\\n\\n---MESSAGE---\\n\\n");
    })()
    """
    body = tab.executeJavascript_(js_read) or ""
    tab.executeJavascript_("window.history.back()")
    time.sleep(2.0)
    return body

queries = [
    # 1. Rejections
    '"not moving forward" OR "other candidates" OR "careful consideration"',
    'unfortunately (application OR candidate OR role OR position OR candidacy OR resume)',
    '"decided not to" OR "unable to offer" OR "not selected" OR "chosen to move forward with"',
    '"position has been filled" OR "timing did not line up" OR "exceptionally competitive"',
    # 2. Interviews & Next steps
    '"interview confirmation" OR "invitation to interview" OR "schedule your interview" OR "schedule an interview"',
    '"phone screen" OR "technical interview" OR "virtual interview" OR "speak with our team"',
    # 3. Assessments
    'assessment OR "coding challenge" OR codesignal OR hackerrank OR coderbyte OR "predictive index"',
    # 4. Offers
    '"offer of employment" OR "offer letter" OR "congratulations on your offer"',
    # 5. Status updates
    '"status of your application" OR "update on your application" OR "update regarding your application"'
]

all_found = {}

print(f"Starting email scour across {len(queries)} search queries...")
for idx, q in enumerate(queries, 1):
    print(f"\n[{idx}/{len(queries)}] Searching query: {q}")
    execute_search(q)
    rows = scrape_current_rows()
    print(f"  Found {len(rows)} matching rows.")
    for r in rows:
        key = (r['sender'], r['subject'], r['date'])
        if key not in all_found:
            all_found[key] = r

print(f"\nTotal unique emails found across all queries: {len(all_found)}")
with open("/tmp/scoured_job_emails.json", "w") as f:
    json.dump(list(all_found.values()), f, indent=2)

print("Saved scoured emails to /tmp/scoured_job_emails.json")
