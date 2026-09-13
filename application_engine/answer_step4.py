import time
from chrome_js import run_js

# The 10 questions and their target answers:
answers = [
    ("legally authorized to work", "Yes"),
    ("currently require", "No"),
    ("in the future require sponsorship", "No"),
    ("registered in the securities industry", "No"),
    ("Government Official", "No"),
    ("influence the award", "No"),
    ("post-employment restrictions", "No"),
    ("Immediate Family Member", "No"),
    ("referred or recommended", "No"),
    ("consent to receive follow up communication", "Yes"),
]

js_script = """
(async () => {
  const fields = Array.from(document.querySelectorAll('[data-automation-id^="formField"]'));
  const results = [];
  
  for (let i = 0; i < fields.length; i++) {
    const f = fields[i];
    const text = f.innerText.replace(/\\n/g, ' ');
    const btn = f.querySelector('button');
    if (!btn) continue;
    
    // determine target answer
    let target = "No";
    if (text.includes("legally authorized") || text.includes("consent to receive")) {
      target = "Yes";
    }
    
    btn.click();
    await new Promise(r => setTimeout(r, 250));
    
    const options = Array.from(document.querySelectorAll('[role="option"]'));
    const opt = options.find(o => o.textContent.trim().toLowerCase() === target.toLowerCase());
    if (opt) {
      opt.click();
      results.push({ field: text.slice(0, 40), target, success: true });
    } else {
      results.push({ field: text.slice(0, 40), target, success: false });
    }
    await new Promise(r => setTimeout(r, 250));
  }
  return JSON.stringify(results, null, 2);
})()
"""

res = run_js(js_script)
print(res)
