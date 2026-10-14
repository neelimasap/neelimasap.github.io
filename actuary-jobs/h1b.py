#!/usr/bin/env python3
"""Public DOL LCA (H-1B) filings for actuarial job titles, via h1bdata.info (indexes DOL LCA disclosure data).
Writes h1b_rows.json (every filing row), h1b.json (employer->year->count, legacy), sponsors.json/.csv (employer ranking).
Cached: only re-scrapes if h1b_rows.json is >7 days old (or --force)."""
import subprocess,time,json,collections,urllib.parse,os,sys,re,csv
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
YEARS=["2026","2025","2024"]
TITLES=["ACTUARY","SENIOR ACTUARY","PRICING ACTUARY","SENIOR PRICING ACTUARY","ACTUARIAL ANALYST","SENIOR ACTUARIAL ANALYST","ACTUARIAL ANALYST II","ACTUARIAL ANALYST III",
 "ACTUARIAL ASSOCIATE","SENIOR ACTUARIAL ASSOCIATE","ASSOCIATE ACTUARY","ASSISTANT ACTUARY","ACTUARIAL CONSULTANT","SENIOR ACTUARIAL CONSULTANT","ACTUARIAL SENIOR CONSULTANT",
 "CONSULTING ACTUARY","ACTUARIAL MANAGER","SENIOR ACTUARIAL MANAGER","ACTUARIAL DATA SCIENTIST","ACTUARIAL SPECIALIST","LEAD ACTUARY","PRINCIPAL ACTUARY","RESERVING ACTUARY",
 "CASUALTY ACTUARY","ACTUARIAL SCIENTIST","ACTUARIAL MODELER","PREDICTIVE MODELER","CATASTROPHE MODELER","ACTUARIAL DIRECTOR","DIRECTOR ACTUARY","ACTUARIAL ASSISTANT","STAFF ACTUARY","PRODUCT ACTUARY","REINSURANCE ACTUARY"]
def get(q):
    time.sleep(0.4)
    h=subprocess.run(["curl","-s","-L","-m","40","-A",UA,"-H","Accept: text/html,application/xhtml+xml","-H","Accept-Language: en-US,en;q=0.9","https://h1bdata.info/index.php?"+q],capture_output=True,text=True).stdout
    out=[]
    for r in BeautifulSoup(h,"html.parser").select("tr")[1:]:
        td=[x.get_text(strip=True) for x in r.select("td")]
        if len(td)>=5: out.append(td[:6])
    return out
def run():
    rows={}
    def tq(a):
        t,y=a; return y,get(f"em=&job={urllib.parse.quote_plus(t)}&city=&year={y}")
    def eq(a):
        e,y=a; return y,[r for r in get(f"em={urllib.parse.quote_plus(e)}&job=&city=&year={y}") if re.search(r"ACTUAR|PRICING|RESERV|PREDICTIVE MODEL|CATASTROPHE",r[1].upper())]
    with ThreadPoolExecutor(4) as ex:
        for y,rs in ex.map(tq,[(t,y) for t in TITLES for y in YEARS]):
            for r in rs: rows[tuple(r)]=y
        src=open("sources.py").read()
        emps=set(re.findall(r'"([A-Z][A-Z0-9 &.,\'-]{5,})"',src[src.index("H1B_MAP"):src.index("H1B=")]))|{r[0] for r in rows}
        for y,rs in ex.map(eq,[(e,y) for e in emps for y in YEARS]):
            for r in rs: rows[tuple(r)]=y
    L=[dict(employer=r[0],title=r[1],salary=int(re.sub(r"\D","",r[2]) or 0),city=r[3],submitted=r[4],year=y) for r,y in rows.items()]
    json.dump(L,open("h1b_rows.json","w"),indent=0); return L
if "--force" in sys.argv or not os.path.exists("h1b_rows.json") or time.time()-os.path.getmtime("h1b_rows.json")>7*86400: L=run()
else: L=json.load(open("h1b_rows.json"))
c=collections.defaultdict(collections.Counter)
for r in L: c[r["employer"]][r["year"]]+=1
json.dump({k:dict(v) for k,v in c.items()},open("h1b.json","w"),indent=1)
# sponsors ranking (exclude life/health-only)
LIFE=re.compile(r"\bLIFE\b|ANNUIT|HEALTH|MEDIC|HOSPITAL|BENEFIT|RETIREMENT|PENSION|MUTUAL OF OMAHA|AFLAC|METLIFE|PRUDENTIAL|GENWORTH|TRANSAMERICA|LINCOLN|ATHENE|CIGNA|HUMANA|ANTHEM|ELEVANCE|CENTENE|UNITEDHEALTH|OPTUM|AETNA|KAISER|BLUE CROSS|BLUE SHIELD|\bUPMC\b|DENTAL|MASSACHUSETTS MUTUAL|NEW YORK LIFE|NORTHWESTERN MUTUAL|PRINCIPAL LIFE|PACIFIC LIFE|EQUITABLE|BRIGHTHOUSE|COREBRIDGE|JACKSON NATIONAL|ALLIANZ LIFE|SECURIAN|GUARDIAN|UNUM|SYMETRA|PROTECTIVE|GLOBE LIFE|AMERICAN NATIONAL|NATIONAL WESTERN|F&G|FIDELITY & GUARANTY|RGA|REINSURANCE GROUP OF AMERICA|SCOR GLOBAL LIFE|HANNOVER LIFE|EMPLOYEES|GLOBAL ATLANTIC|MUNICH AMERICAN REASSURANCE|VOYA|\bCVS\b|STANDARD INSURANCE COMPANY|CHENMED|WILTON RE|IPTIQ|HIGHMARK|KUVARE|MARTELLO RE|ALIGHT|VIAC|GABRIEL ROEDER|SUN LIFE|OSCAR|CLOVER|DEVOTED|BRIGHT HEALTH|MOLINA|WELLCARE|CARESOURCE|HORIZON|INDEPENDENCE|EMBLEM|HEALTHFIRST|SEGAL|BUCK|CHEIRON|NYL|OHIO NATIONAL|AMERITAS|MUTUAL OF AMERICA|TIAA|NATIONAL LIFE|FORETHOUGHT|SAMMONS|DELAWARE LIFE|NASSAU|AMERICAN EQUITY|SILAC|ATHENE|RELIANCE STANDARD|HARTFORD LIFE",re.I)
PC=re.compile(r"CASUALTY|PROPERTY|INDEMNITY|FIRE|AUTO|REINSUR|SPECIALTY|SURETY|INSURANCE|UNDERWRIT|MUTUAL|ASSURANCE|RE INC|\bRE\b",re.I)
S=collections.defaultdict(lambda:dict(titles=collections.Counter(),years=set(),sal=[],cities=collections.Counter(),n=0))
for r in L:
    if LIFE.search(r["employer"]) or LIFE.search(r["title"]): continue
    s=S[r["employer"]]; s["n"]+=1; s["titles"][r["title"]]+=1; s["years"].add(r["year"]); s["cities"][r["city"]]+=1
    if r["salary"]: s["sal"].append(r["salary"])
def score(e,s):
    t=" ".join(s["titles"]); sc=s["n"]
    sc+=8*sum(v for k,v in s["titles"].items() if "PRICING" in k)+3*sum(v for k,v in s["titles"].items() if re.search("RESERV|CASUALTY|PREDICTIVE|CATASTROPHE|REINSUR",k))
    if PC.search(e): sc*=1.6
    if "2026" in s["years"] or "2025" in s["years"]: sc*=1.3
    return round(sc,1)
out=[dict(employer=e,score=score(e,s),filings=s["n"],latest_year=max(s["years"]),years=sorted(s["years"]),titles=dict(s["titles"].most_common()),
          salary_min=min(s["sal"]) if s["sal"] else None,salary_max=max(s["sal"]) if s["sal"] else None,cities=dict(s["cities"].most_common(6))) for e,s in S.items()]
out.sort(key=lambda x:-x["score"])
json.dump(out,open("sponsors.json","w"),indent=1)
with open("sponsors.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["rank","employer","pc_relevance_score","filings_FY2024_2026","latest_year","titles","salary_min","salary_max","cities"])
    for i,x in enumerate(out,1): w.writerow([i,x["employer"],x["score"],x["filings"],x["latest_year"],"; ".join(f"{k} ({v})" for k,v in x["titles"].items()),x["salary_min"],x["salary_max"],"; ".join(x["cities"])])
print(len(L),"filing rows;",len(out),"non-life sponsor employers")
