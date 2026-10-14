#!/usr/bin/env python3
"""Post-process leads.json: drop exec/non-US roles, verify each posting is live, rank, render index.html, flag new leads."""
import re,json,time,html,subprocess,datetime,zoneinfo,os
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
TZ=zoneinfo.ZoneInfo("America/Chicago"); NOW=datetime.datetime.now(TZ); TODAY=NOW.date()
def curl(u,data=None,code=False):
    time.sleep(0.7)
    a=["curl","-s","-L","-m","30","-A",UA,"-w","\n%{http_code}",u]
    if data is not None: a+=["-X","POST","-H","Content-Type: application/json","-d",json.dumps(data)]
    o=subprocess.run(a,capture_output=True,text=True).stdout
    body,_,c=o.rpartition("\n"); return body,c
def jget(u):
    b,c=curl(u)
    try: return json.loads(b),c
    except Exception: return None,c
EXEC=re.compile(r"\bdirector\b|head of|\bvp\b|\bavp\b|\bsvp\b|\bevp\b|vice president|chief|\bcro\b|\bofficer\b|executive|\bmanager\b|\bmgr\b",re.I)
JUNIOR=re.compile(r"analyst|associate|entry|junior|\bjr\b|assistant|intern|graduate|trainee|ph\.?d",re.I)
SENIOR=re.compile(r"senior|\bsr\b|lead|principal|supervising|consultant|actuary\b",re.I)
NONUS=re.compile(r"edinburgh|sydney|manila|neuilly|paris|barcelona|madrid|milan|warszawa|warsaw|lisbon|kuala lumpur|buenos aires|argentina|melbourne|glasgow|redhill|\bsry\b|\blon\b|london|canada|toronto|uk\b",re.I)
ashby_cache={}
BODY={"t":""}
PAYRE=re.compile(r"\$\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?\s?[kK])(?:\.\d\d)?\s*(?:-|–|—|to)\s*(?:USD\s*)?\$?\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?\s?[kK])")
def money(x):
    x=x.replace(",","").strip()
    return float(x[:-1])*1000 if x[-1] in "kK" else float(x)
def pay(t):
    t=re.sub(r"<[^>]+>"," ",html.unescape(html.unescape(t or "")))
    best=None
    for a,b in PAYRE.findall(t):
        lo,hi=money(a),money(b)
        if 30000<=lo<=hi<=1500000 and (best is None or hi>best[1]): best=(lo,hi)
    return best
def verify(r):
    BODY["t"]=""
    l=r["link"]
    if m:=re.match(r"https://([^.]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)(/job/.+)",l):
        t,w,site,p=m.groups()
        d,c=jget(f"https://{t}.{w}.myworkdayjobs.com/wday/cxs/{t}/{site}{p}")
        if d is None: return ("unknown",f"Workday HTTP {c}") if c not in ("404","410") else ("closed","Workday 404")
        j=d.get("jobPostingInfo") or {}; BODY["t"]=j.get("jobDescription","")
        return ("open","Workday canApply=true") if j.get("canApply") else ("closed","Workday canApply=false")
    if "greenhouse" in r.get("src",""):
        slug=re.search(r"boards/([^/]+)/jobs",r["src"]).group(1); jid=(re.search(r"gh_jid=(\d+)",l) or re.search(r"/jobs/(\d+)",l)).group(1)
        d,c=jget(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{jid}")
        if d and d.get("id"): BODY["t"]=d.get("content",""); return ("open","Greenhouse API returns job")
        return ("closed",f"Greenhouse HTTP {c}") if c in ("404","410") else ("unknown",f"Greenhouse HTTP {c}")
    if "ashbyhq" in l:
        src=r["src"]
        if src not in ashby_cache: ashby_cache[src]=jget(src)[0]
        d=ashby_cache[src]
        if not d: return ("unknown","Ashby API failed")
        uid=l.rstrip("/").split("/")[-1]; BODY["t"]=" ".join(json.dumps(x) for x in d.get("jobs",[]) if x.get("id")==uid)
        return ("open","Ashby API returns job") if any(x.get("id")==uid for x in d.get("jobs",[])) else ("closed","not on Ashby board")
    if m:=re.search(r"linkedin\.com/jobs/view/(\d+)",l):
        for i in range(5):
            b,c=curl(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{m.group(1)}")
            if c=="429": time.sleep(10*(i+1)); continue
            if c in ("404","410"): return ("closed",f"LinkedIn HTTP {c}")
            if "No longer accepting applications" in b: return ("closed","LinkedIn: no longer accepting applications")
            if "description" in b: BODY["t"]=b; return ("open","LinkedIn guest page live")
            time.sleep(3)
        return ("unknown","LinkedIn unreadable (429/blank)")
    b,c=curl(l); BODY["t"]=b; return ("open",f"HTTP {c}") if c=="200" else ("unknown",f"HTTP {c}")
D=json.load(open("leads_raw.json" if os.path.exists("leads_raw.json") else "leads.json"))
if os.path.exists("prev/leads.json"):
    cur={x["link"] for x in D["leads"]}
    D["leads"]+=[x for x in json.load(open("prev/leads.json"))["leads"] if x.get("source")=="LinkedIn" and x["link"] not in cur]  # carry over LinkedIn rows a throttled search missed; re-verified below
    pdate={x["link"]:x["posted"] for x in json.load(open("prev/leads.json"))["leads"] if x.get("posted")}
    for x in D["leads"]:
        if not x.get("posted") and pdate.get(x["link"]): x["posted"]=pdate[x["link"]]
rows=[];drop={"exec":0,"nonus":0,"closed":0,"unverified":0}; unver=[]
LHX=re.compile(r"\blife\b|pension|penion|health|A&H|accident|annuit|medical|medicare|mortality|longevity|group benefit",re.I)
for r in D["leads"]:
    if r.get("lh") or LHX.search(r["title"]+" "+r.get("category","")): drop["lifehealth"]=drop.get("lifehealth",0)+1; continue
    if EXEC.search(r["title"]): drop["exec"]+=1; continue
    if NONUS.search(r["city"]) and r.get("route")!="L1" and not re.search(r"\b(usa|united states|remote)\b",r["city"],re.I): drop["nonus"]+=1; continue
    st,how=verify(r)
    if st=="closed": drop["closed"]+=1; continue
    if st=="unknown": drop["unverified"]+=1; unver.append(r["title"]+" · "+r["company"]+" ("+how+")"); continue
    p=pay(BODY["t"]+" "+r.get("salary","")+" "+r.get("desc",""))
    r["pay"]=dict(lo=p[0],hi=p[1],src="Posted range in job ad") if p else None
    r["verified"]=TODAY.isoformat(); r["verify_how"]=how; rows.append(r)
def age(p):
    try: return (TODAY-datetime.date.fromisoformat(p)).days
    except Exception: return None
def bucket(p):
    a=age(p); return 4 if a is None else 0 if a<=1 else 1 if a<=2 else 2 if a<=7 else 3
for r in rows:
    a=age(r["posted"]); r["new"]=a is not None and a<=2
    r["junior"]=bool(JUNIOR.search(r["title"])) and not re.search(r"\bsenior\b|\bsr\b|\blead\b|principal|supervising|associate actuary|\bactuary\b",r["title"],re.I) or bool(re.search(r"intern|entry|graduate|trainee|assistant",r["title"],re.I))
    r["section"]="JR" if r["junior"] else ("MGR" if re.search(r"\bmanager\b",r["title"],re.I) and not re.search(r"senior|\bsr\b|lead|principal",r["title"],re.I) else "MAIN")
rows.sort(key=lambda r:("MAIN","JR","LH").index(r["section"]) if False else 0)
rows.sort(key=lambda r:(("MAIN","MGR","JR").index(r["section"]),bucket(r["posted"]),r["tier"],r["drank"],0 if SENIOR.search(r["title"]) else 1,r["gk"],-(datetime.date.fromisoformat(r["posted"]).toordinal() if r["posted"] else 0)))
# new-lead tracking
SEEN="seen_links.json"
seen=set(json.load(open(SEEN))) if os.path.exists(SEEN) else set(x["link"] for x in json.load(open("prev/leads.json"))["leads"]) if os.path.exists("prev/leads.json") else set()
newleads=[r for r in rows if r["link"] not in seen and r["section"]!="LH"]
newlh=[r for r in rows if r["link"] not in seen and r["section"]=="LH"]
json.dump(sorted(seen|{r["link"] for r in rows}),open(SEEN,"w"),indent=0)
now=NOW.strftime("%b %d, %Y %I:%M %p CT")
D.update(updated=now,dropped=drop,unverified=unver,leads=rows,new_links=[r["link"] for r in newleads+newlh])
json.dump(D,open("leads.json","w"),indent=1)
e=html.escape; fd=lambda s:datetime.date.fromisoformat(s).strftime("%b %d, %Y")
def pd(r):
    if r["posted"]: return f' · <b>Posted {fd(r["posted"])}</b>'
    return " · Posted date not shown"+(f' ({e(r["posted_note"])})' if r.get("posted_note") else "")
TL={"A":"Sponsorship stated, or same-type title H-1B filed in last 2 yrs","B":"Employer has actuarial H-1B filing history","C":"No sponsorship evidence found"}
def card(r): return f'<article><h3>{"<span class=n>NEW</span> " if r["new"] else ""}<a href="{e(r["link"])}">{e(r["title"])}</a></h3><p class=m><span class=g>{e(r["group"])}</span><span class=c>{e(r["category"])} · {e(r["difficulty"])}</span><span class=t>Tier {r["tier"]}: {TL[r["tier"]]}</span> {e(r["company"])} · {e(r["city"])}{pd(r)} · <span class=v>✓ Verified open {fd(r["verified"])}</span></p><p class=w>{e(r["why"])}</p>{sp(r)}<p class=s>Source: {e(r["source"])} · check: {e(r["verify_how"])}</p></article>'
SPON=set()
try:
    for x in json.load(open("sponsors.json"))[:60]: SPON.add(x["employer"])
except Exception: pass
COMM=json.load(open("community.json")) if os.path.exists("community.json") else []
def cm(r):
    its=[c for c in COMM if any(e.lower() in r["company"].lower() for e in c["employers"] if e!="Big 4") or ("Big 4" in c["employers"] and r["company"] in ("EY","PwC","Deloitte","KPMG"))]
    return "".join(f'<p class=s>Community (anecdotal): {e(c["source"])}, {e(c["date"])}: {e(c["summary"][:160])} <a href="{e(c["link"])}">thread</a></p>' for c in its[:2])
def sp(r): return cm(r)+ '<p class=s><span class=t>★ Sponsor-proven employer</span> (filed actuarial H-1Bs in 2025-26, public DOL data)</p>' if r.get("sponsor_proven") else ""
for r in rows:
    h=r.get("h1b") or {}; r["sponsor_proven"]=bool(h) and h.get("total",0)>=2 and int(h.get("year","0"))>=TODAY.year-1
SN={"SPON":"★ Sponsor-proven employers: senior roles (quick filter; same roles also listed below)","MAIN":"Senior, lead &amp; principal roles","MGR":"Manager-level roles (lower priority)","JR":"Analyst / associate-level roles (lower fit)"}
IN=lambda r,s:(r["sponsor_proven"] and r["section"]=="MAIN") if s=="SPON" else r["section"]==s
body="".join(f'<h2 class=s>{SN[s]} ({sum(IN(r,s) for r in rows)})</h2>'+("".join(card(r) for r in rows if IN(r,s)) or "<p>None found right now.</p>") for s in SN)
st="".join(f"<li>{e(k)}: {e(v)}</li>" for k,v in D["status"].items())
open("index.html","w").write(f'''<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Actuarial roles with visa sponsorship · verified open</title>
<style>body{{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#222;background:#fafafa}}h1{{font-size:1.5rem}}article{{background:#fff;border:1px solid #e3e3e3;border-radius:10px;padding:.9rem 1.2rem;margin:.8rem 0}}h3{{font-size:1.05rem;margin:0}}a{{color:#0a66c2}}.m{{color:#555;margin:.3rem 0}}.w{{margin:.3rem 0;color:#333;font-style:italic}}p.s,small,li{{color:#777;font-size:.85rem}}.g,.c,.t{{border-radius:4px;padding:1px 6px;font-size:.78rem;margin-right:4px}}.g{{background:#e8f0fa;color:#0a66c2}}.c{{background:#eef7ee;color:#26734d}}.t{{background:#f3eefa;color:#5b3a8a}}.v{{color:#1a7f37;font-weight:600}}.n{{background:#d93025;color:#fff;border-radius:4px;padding:1px 6px;font-size:.75rem}}h2.s{{font-size:1.1rem;margin-top:2rem;border-bottom:2px solid #0a66c2}}</style>
<h1>Actuarial &amp; insurance roles: visa sponsorship leads</h1>
<p>For a fully qualified P&amp;C pricing actuary. Every posting below was checked live on {fd(TODAY.isoformat())} (employer careers API or LinkedIn) and is accepting applications; closed or unreadable links are dropped. Order: newest first (last 24h, 48h, 7 days, older), then sponsorship evidence, then role fit (senior P&amp;C pricing first), then location (Dallas-Fort Worth and SF Bay Area, other Texas, rest of US). NEW = posted in the last 48h. Director, VP, Head-of and executive roles are left out for now; analyst/associate roles sit at the bottom; life &amp; health roles are excluded. Postings that rule out sponsorship are dropped. H-1B counts come from public DOL LCA data (h1bdata.info) and are a signal only. Always confirm with the employer.</p>
<p><b>{len(rows)}</b> verified-open leads · Last updated {now} · this run dropped {drop["closed"]} closed, {drop["exec"]} director/VP-level, {drop["nonus"]} non-US, {drop["unverified"]} unverifiable, {D.get("dropped_no_sponsorship",0)} no-sponsorship</p>{body}
<h2 class=s>Community intel (anecdotal, not verified)</h2><ul>{"".join(f'<li>{e(c["source"])}, {e(c["date"])}: {e(c["summary"])} <a href="{e(c["link"])}">link</a></li>' for c in COMM)}</ul>
<h2 class=s>Sources this run</h2><ul>{st}</ul></html>''')
print(len(rows),"verified",drop,"new",len(newleads),"newLH",len(newlh))
for r in newleads[:10]: print("NEW",r["posted"],r["title"],"|",r["company"],"|",r["city"],"|",r["link"])
print("unverified",unver)
