#!/usr/bin/env python3
"""Community intel (anecdotal): merge seed findings + live Reddit search (public JSON; skipped quietly if blocked) -> community.json"""
import json,subprocess,time,re,datetime,os
UA="linux:actuary-jobs-scan:v1.1 (personal job search, low volume)"
C={x["link"]:x for x in json.load(open("community_seed.json"))}
if os.path.exists("community.json"):
    for x in json.load(open("community.json")): C.setdefault(x["link"],x)
EMP=["Liberty Mutual","Travelers","Hartford","Chubb","AIG","Allstate","Progressive","State Farm","Nationwide","Swiss Re","Munich Re","Milliman","Aon","WTW","Deloitte","EY","PwC","KPMG","Arch","Markel","Everest","Zurich","AXA XL","CNA","USAA","Farmers","Coalition","Lemonade","Hippo","Verisk","Oliver Wyman","Guy Carpenter","Berkley","Sompo","AXIS","Kemper","Hanover","Erie","CSAA","Mercury","Uber"]
ok=0
for sub,q in [("actuary","h1b"),("actuary","sponsorship"),("actuary","visa"),("ActuaryUK","US move"),("h1b","actuary")]:
    time.sleep(2)
    try:
        d=json.loads(subprocess.run(["curl","-s","-m","20","-A",UA,f"https://www.reddit.com/r/{sub}/search.json?q={q.replace(' ','+')}&restrict_sr=1&sort=new&limit=50&t=year"],capture_output=True,text=True).stdout)
    except Exception: continue
    ok+=1
    for c in d.get("data",{}).get("children",[]):
        p=c["data"]; t=p.get("title","")+" "+p.get("selftext","")
        if not re.search(r"sponsor|h-?1b|visa",t,re.I) or not re.search(r"actuar",t,re.I): continue
        emps=[e for e in EMP if re.search(r"\b"+re.escape(e)+r"\b",t)]
        stance="refuse" if re.search(r"(won'?t|will not|doesn'?t|do not|no longer) sponsor",t,re.I) else "sponsor" if re.search(r"sponsored me|will sponsor|did sponsor|got sponsored",t,re.I) else "mixed"
        link="https://www.reddit.com"+p["permalink"]
        C.setdefault(link,dict(source=f"Reddit r/{sub}",date=datetime.date.fromtimestamp(p["created_utc"]).strftime("%b %Y"),link=link,employers=emps,stance=stance,summary=p.get("title","")[:200]))
json.dump(list(C.values()),open("community.json","w"),indent=1)
print(len(C),"community items;","reddit live queries ok:",ok,"/5")
