#!/usr/bin/env python3
"""Build Adrian's private dashboard: plain app (box only: dashboard_plain.html) -> AES-256-GCM encrypted index.html
(key = PBKDF2-SHA256(username + ':' + password, salt, 250k iters)); all data embedded inside the ciphertext."""
import json,re,os,base64,datetime,zoneinfo,html
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
USER=os.environ["DASHBOARD_USER"]; PASS=os.environ["DASHBOARD_PASS"]; ITERS=250000
TZ=zoneinfo.ZoneInfo("America/Chicago"); TODAY=datetime.datetime.now(TZ).date()
D=json.load(open("leads.json"))
COMM=json.load(open("community.json")) if os.path.exists("community.json") else []
SP=json.load(open("sponsors.json")) if os.path.exists("sponsors.json") else []
# contacts.md table -> company keyword -> contact
CT={}
if os.path.exists("contacts.md"):
    for line in open("contacts.md"):
        c=[x.strip() for x in line.strip().strip("|").split("|")]
        if len(c)>=4 and ":" in c[0] and not c[0].startswith("Lead"):
            co=c[0].split(":")[0].strip()
            if "Not identified" in c[1]: continue
            m=re.match(r"(.+?),\s*(.+?)(\s*\(|;|$)",c[1]); name,title=(m.group(1),m.group(2)) if m else (c[1],"")
            CT[co.lower()]=dict(name=name,title=title,src=c[1],email=c[2],conf=c[3],ev=re.findall(r"https?://\S+",c[4]) if len(c)>4 else [],note=re.sub(r"https?://\S+","",c[4]).strip(" ;,") if len(c)>4 else "")
LH=re.compile(r"\blife\b|health|A&H|accident|annuit|medical|medicare|mortality|longevity|group benefit|pension|benefits|compensation|epidemiolog|auditor",re.I)
EX=re.compile(r"\bdirector\b|head of|\bvp\b|\bavp\b|\bsvp\b|vice president|chief|officer|executive|\bmanager\b|\bmgr\b",re.I)
ROLE={"Pricing Actuary":"Pricing","Reserving Actuary":"Reserving","Reinsurance Actuary":"Reinsurance","Enterprise Risk Manager":"ERM","Insurance Product Manager":"Product","Actuarial Consultant":"Consulting","Predictive Modeling Actuary":"Modeling","Data Scientist (insurance)":"Modeling","Actuary (general)":"Pricing"}
REP={"AIG":"Global top-10 P&C carrier, deep specialty book","Chubb":"World's largest publicly traded P&C insurer, A++ rated","Liberty Mutual":"Top-5 US P&C carrier, large actuarial org","Travelers":"Top-3 US commercial P&C carrier, strong pricing culture","CNA":"Major US commercial/specialty carrier (Loews)","The Hartford":"Fortune 200 P&C carrier, large pricing teams","Everest":"Global reinsurer/specialty insurer, A+ rated, fast-growing","Markel":"Specialty insurer with Berkshire-like stability","Arch Insurance":"A+ specialty insurer/reinsurer, pricing-heavy H-1B record","Allstate":"Top-5 US personal lines carrier","Nationwide":"Fortune 100 mutual, very stable","USAA":"Top personal lines carrier, Texas HQ","American Family":"Large mutual (incl. Homesite), stable","Swiss Re":"Top-2 global reinsurer","Munich Re":"Largest global reinsurer","TransRe":"Global reinsurer (Berkshire Hathaway)","Tokio Marine HCC":"Specialty insurer backed by Tokio Marine, Houston HQ","Coalition":"Leading cyber insurtech, pricing-led","Hippo":"Home insurtech, Texas presence","Kemper":"Mid-size US personal auto carrier","AXIS Capital":"Global specialty insurer/reinsurer","Sompo International":"Global specialty arm of Sompo","Marsh McLennan (Oliver Wyman/Guy Carpenter/Mercer)":"World's largest broker/consultancy","Akur8":"Pricing-software firm used by top carriers","W. R. Berkley":"Fortune 500 specialty insurer, decentralized units","CSAA Insurance Group":"AAA insurer, Walnut Creek HQ","MGIC":"Leading US mortgage insurer","Lemonade":"Public insurtech","Next Insurance":"SMB insurtech (Ergo/Munich Re-owned)","Erie Insurance":"Fortune 500 mutual","Starr":"Global specialty insurer","Assurant":"Fortune 500 specialty insurer"}
def whyb(r,h,sp,role,sec):
    a=[REP.get(r["company"],"Established insurance employer")]
    if h: a.append(f'{h.get("total",0)} actuarial H-1B filings 2024-26 (latest {h.get("year")})' + (", incl. a closely matching title" if h.get("close") else ""))
    else: a.append("no actuarial H-1B record found, so ask early")
    a.append("direct fit for senior P&C pricing" if role=="Pricing" and sec=="MAIN" else f"adjacent fit ({role.lower()})")
    return "; ".join(a)
import time as _t
_src=open("sources.py").read(); _m=re.search(r"^EMPRX=\{.*?\n(?=\S)",_src,re.S|re.M)
EMPRX=eval(_m.group(0)[6:]) if _m else {}
H1R=json.load(open("h1b_rows.json")) if os.path.exists("h1b_rows.json") else []
def emp_hist(co):
    rx=EMPRX.get(co)
    if not rx: return None
    rs=[x for x in H1R if re.search(rx,x["employer"])]
    if not rs: return None
    yc={y:sum(1 for x in rs if x["year"]==y) for y in ("2024","2025","2026")}
    sal=sorted(x["salary"] for x in rs if x["salary"])
    return dict(years=yc,total=len(rs),lo=sal[0] if sal else None,hi=sal[-1] if sal else None,med=sal[len(sal)//2] if sal else None)
def careers(link):
    m=re.match(r"(https://[^/]+)(/[^/]+)?",link); return (m.group(1)+(m.group(2) or "")) if m else link
rows=[];DROPJR=[]
for r in D["leads"]:
    if LH.search(r["title"]) or r.get("lh") or EX.search(r["title"]): continue
    if r.get("route")=="CAPX": r["tier"]="A"
    h=r.get("h1b") or {}
    sp=bool(h) and h.get("total",0)>=2 and int(h.get("year","0") or 0)>=TODAY.year-1
    loc=(r["city"]+" "+r["title"]).lower(); locs=[]
    if r["group"]=="Dallas-Fort Worth": locs.append("dallas")
    if r["group"]=="SF Bay Area": locs.append("sf")
    if r["group"] in("Dallas-Fort Worth","Other Texas") or re.search(r"\btx\b|texas",loc): locs.append("texas")
    if "remote" in loc or "any location" in loc: locs.append("remote")
    role=ROLE.get(r["category"],"Pricing")
    if re.search(r"pricing|rate",r["title"],re.I): role="Pricing"
    elif re.search(r"reserv",r["title"],re.I): role="Reserving"
    contact=next((v for k,v in CT.items() if k.split()[0] in r["company"].lower()),None)
    comm=[dict(src=c["source"],date=c["date"],text=c["summary"],link=c["link"]) for c in COMM if any(e.lower() in r["company"].lower() for e in c["employers"] if e!="Big 4") or ("Big 4" in c["employers"] and r["company"] in("EY","PwC","Deloitte","KPMG"))]
    pp=r.get("pay")
    def num(x):
        n=re.findall(r"\$?(\d[\d,.]*)\s*([kK]?)",str(x))
        if not n: return None
        a,k=n[-1]; v=float(a.replace(",","")); return v*1000 if k else v
    hs=num(h.get("sal")) if h.get("sal") else None
    if pp: payv=dict(v=pp["hi"],lo=pp["lo"],hi=pp["hi"],src="Posted range in job ad")
    elif hs: payv=dict(v=hs,lo=None,hi=hs,src=f'H-1B salary, {(h.get("title") or "closest title").title()} at {r["company"]} ({h.get("year","")})')
    else: payv=None
    if r["section"]=="JR" and not (payv and payv["v"]>=120000): DROPJR.append(r["title"]+" · "+r["company"]); continue
    rows.append(dict(eh=emp_hist(r["company"]),careers=careers(r["link"]),rep=REP.get(r["company"],""),hsal=h.get("sal",""),htitle=(h.get("title") or "").title(),hyear=h.get("year",""),hcount=h.get("n",0),pay=payv,wb=whyb(r,h,sp,role,r["section"]),hn=h.get("total",0),route=r.get("route",""),id=re.sub(r"\W","",r["link"])[-40:],title=r["title"],company=r["company"],city=r["city"],posted=r["posted"],verified=r.get("verified",""),
        tier=r["tier"],why=r["why"],h1b=h.get("text",""),sponsor=sp,section=r["section"],role=role,locs=locs,link=r["link"],source=r["source"],contact=contact,comm=comm[:2],drank=r["drank"],gk=r["gk"]))
BUILD=int(_t.time()*1000)
REC=[dict(n="Actuarial Careers, Inc.",d="Places actuaries worldwide",links=[["Submit resume","https://www.actuarialcareers.com/submit-resume/"],["Contact","https://www.actuarialcareers.com/contact-us/"]]),dict(n="DW Simpson",d="Actuarial-only recruiter, 35+ years",links=[["Contact","https://www.dwsimpson.com/contact/"],["Live jobs","https://jobs.dwsimpson.com/"]]),dict(n="Ezra Penland",d="P&C pricing & analytics; 800-580-3972",links=[["Live jobs","https://jobs.ezrapenland.com/"]]),dict(n="Smith Hanley Associates",d="Rory Hauser (actuarial lead): rhauser@smithhanley.com (Verified: published on smithhanley.com), 203-319-4305",links=[["Email Rory","mailto:rhauser@smithhanley.com"],["Contact","https://www.smithhanley.com/contact-us/"]]),dict(n="The Jacobson Group",d="Insurance-wide; interim pricing/reserving actuaries",links=[["Candidates","https://www.jacobsononline.com/candidates/"],["Contact","https://www.jacobsononline.com/contact-us/"]])]
DATA=dict(build=BUILD,recruiters=REC,updated=datetime.datetime.now(TZ).strftime("%b %d, %Y %I:%M %p CT"),rows=rows,community=COMM,
          sponsors=[dict(e=x["employer"],n=x["filings"],y=x["latest_year"],t=list(x["titles"])[:3],lo=x["salary_min"],hi=x["salary_max"]) for x in SP[:25]])
APP0=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"dashboard_app.html")).read()
APP=APP0.replace("__BUILD__",str(BUILD)).replace("__DATA__",json.dumps(DATA).replace("</","<\\/"))
open("dashboard_plain.html","w").write(APP)
salt=os.urandom(16); iv=os.urandom(12)
key=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=ITERS).derive((USER.strip().lower()+":"+PASS).encode())
ct=AESGCM(key).encrypt(iv,APP.encode(),None)
b=lambda x:base64.b64encode(x).decode()
LOCK=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"dashboard_lock.html")).read()
open("index.html","w").write(LOCK.replace("__BUILD__",str(BUILD)).replace("__SALT__",b(salt)).replace("__IV__",b(iv)).replace("__CT__",b(ct)).replace("__ITERS__",str(ITERS)))
json.dump(DROPJR,open("dropped_junior.json","w"),indent=1)
print("dashboard: dropped",len(DROPJR),"low/unknown-pay junior roles;",len(rows),"rows; encrypted index.html",os.path.getsize("index.html"),"bytes")
