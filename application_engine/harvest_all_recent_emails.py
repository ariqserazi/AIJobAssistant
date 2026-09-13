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
    print("Error: No Gmail tab found in Chrome!")
    sys.exit(1)

def search_query(query):
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
        return JSON.stringify(rows.map((r, idx) => {
            const sender = (r.querySelector(".yX") || r.querySelector(".yW") || {}).textContent || "";
            const subject = (r.querySelector(".bog") || {}).textContent || "";
            const snippet = (r.querySelector(".y2") || {}).textContent || "";
            const date = (r.querySelector(".xW") || {}).textContent || "";
            const id = r.getAttribute("id") || "";
            return {
                idx: idx,
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

def click_next_page():
    js_next = """
    (() => {
        const nextBtn = document.querySelector("div[aria-label='Older'], div[data-tooltip='Older'], div[aria-label='Next page']");
        if (nextBtn && nextBtn.getAttribute("aria-disabled") !== "true") {
            nextBtn.click();
            return true;
        }
        return false;
    })()
    """
    clicked = tab.executeJavascript_(js_next)
    if clicked:
        time.sleep(3.5)
        return True
    return False

# Search for all emails newer than 14 days
print("Searching for 'newer_than:14d' in Gmail...")
search_query("newer_than:14d")

all_emails = {}
page_num = 1
while page_num <= 10:  # Up to 10 pages (~500-1000 emails)
    rows = scrape_current_rows()
    print(f"Page {page_num}: Scraped {len(rows)} rows.")
    new_in_page = 0
    for r in rows:
        key = (r['sender'], r['subject'], r['date'])
        if key not in all_emails:
            all_emails[key] = r
            new_in_page += 1
    
    if new_in_page == 0:
        print("No new emails on this page, stopping pagination.")
        break
        
    has_next = click_next_page()
    if not has_next:
        print("No more pages available.")
        break
    page_num += 1

print(f"\nTotal recent emails harvested: {len(all_emails)}")

with open("/tmp/all_recent_emails_14d.json", "w") as f:
    json.dump(list(all_emails.values()), f, indent=2)

print("Saved to /tmp/all_recent_emails_14d.json")
