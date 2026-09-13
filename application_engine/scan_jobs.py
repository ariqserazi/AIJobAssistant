import urllib.request
import json
import ssl
import certifi
import re

ctx = ssl.create_default_context(cafile=certifi.where())

def search_ms(query):
    url = "https://ms.wd5.myworkdayjobs.com/wday/cxs/ms/external/jobs"
    payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": query}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read().decode()).get("jobPostings", [])

jobs = []
seen = set()
for q in ["Developer", "Software", "Python", "Java", "Technology Analyst", "Data Engineer", "Cloud"]:
    for j in search_ms(q):
        path = j.get("externalPath")
        if path not in seen and "United States" in j.get("locationsText", ""):
            seen.add(path)
            jobs.append(j)

print(f"Total unique US tech jobs at MS: {len(jobs)}")

for j in jobs:
    path = j.get("externalPath")
    slug = path.split("/job/")[-1]
    url = f"https://ms.wd5.myworkdayjobs.com/wday/cxs/ms/external/job/{slug}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            info = data.get("jobPostingInfo", {})
            desc = info.get("jobDescription", "")
            title = j.get("title")
            loc = j.get("locationsText")
            req_id = info.get("jobReqId")
            
            has_bachelor = "bachelor" in desc.lower() or "b.s." in desc.lower() or "bs in" in desc.lower()
            requires_master_only = ("master’s degree" in desc.lower() or "master's degree" in desc.lower()) and not has_bachelor
            is_senior = any(k in title.lower() for k in ["vice president", "director", "executive director", "lead", "principal", "manager"])
            
            if not is_senior and not requires_master_only:
                print(f"\n🎯 [{req_id}] {title} | {loc}")
                print(f"   URL: https://ms.wd5.myworkdayjobs.com/en-US/external{path}")
                # snippet of requirements
                clean = re.sub("<[^<]+?>", " ", desc)
                print(f"   Desc snippet: {clean[:200].strip()}")
    except Exception as e:
        pass
