#!/usr/bin/env python3
"""Collect leads from employer ATS public APIs (Greenhouse, Ashby, Workday) + LinkedIn rows (jobs.json),
tier by sponsorship evidence, rank, and render index.html. Run after refresh.py and h1b.py."""
import re,json,time,html,subprocess,datetime,zoneinfo
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"
def curl(u,data=None):
    time.sleep(0.6)
    a=["curl","-s","-m","30","-A",UA,u]
    if data: a+=["-X","POST","-H","Content-Type: application/json","-d",json.dumps(data)]
    try: return json.loads(subprocess.run(a,capture_output=True,text=True).stdout)
    except Exception: return None
# ---- role categories: (label, difficulty, rank) ----
CATS=[(r"chief risk|chief actuary|actuarial director|director.{0,30}actuar|actuar.{0,30}director|head of actuar","CRO / Actuarial Director","Depends on experience",5),
 (r"pricing|rate filing|filings|ratemaking","Pricing Actuary","Very easy",0),
 (r"reserv|valuation","Reserving Actuary","Easy",1),
 (r"reinsur","Reinsurance Actuary","Easy-Moderate",2),
 (r"enterprise risk|\berm\b","Enterprise Risk Manager","Easy-Moderate",2),
 (r"predictive|model|analytics|actuarial data scien","Predictive Modeling Actuary","Moderate",3),
 (r"consult","Actuarial Consultant","Easy",1)]
LIFE=r"life|annuit|health|ltc|long term care|pension|retirement|group benefit|medicare|medicaid"
def category(t):
    tl=t.lower(); act="actuar" in tl
    if re.search(CATS[0][0],tl) and (act or "chief risk" in tl): return CATS[0][1:]
    if act and re.search(LIFE,tl) and not re.search(r"pricing|p&c|casualty",tl): return ("Life/Health Actuary","Moderate-Hard",4)
    for rx,lab,dif,rk in CATS[1:]:
        if re.search(rx,tl) and (act or lab=="Enterprise Risk Manager"): return (lab,dif,rk)
    if act: return ("Actuarial Consultant" if "consult" in tl else "Actuary (general)","Easy",1)
    if re.search(r"product manager",tl): return ("Insurance Product Manager","Easy-Moderate",2)
    if re.search(r"data scien",tl): return ("Data Scientist (insurance)","Moderate",3)
    return None
YES=re.compile(r"[^.\n]*(sponsorship (is|may be) available|will sponsor|(visa|immigration) sponsorship (is |may be )?(available|offered|provided)|open to sponsor|eligible for (visa |immigration )?sponsorship)[^.\n]*",re.I)
MAY=re.compile(r"may be available|limited",re.I)
NO=re.compile(r"[^.\n]*((not|unable to|no|won't|will not|cannot|does not|do not)[^.\n]{0,60}sponsor|without (the need for )?(current or future |employer )?sponsorship|sponsorship (is )?not (available|offered))[^.\n]*",re.I)
def spons(txt):
    n=NO.search(txt)
    if n: return ("no",n.group(0).strip())
    y=YES.search(txt)
    if y: return ("may" if MAY.search(y.group(0)) else "yes", y.group(0).strip())
    return ("silent","")
def strip(h): return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",html.unescape(h or ""))))
def group(c):
    c=(c or "").lower()
    if re.search(r"dallas|fort worth|plano|irving|frisco|arlington, ?tx|richardson|addison|mckinney|grapevine|dfw",c): return (0,"Dallas-Fort Worth")
    if re.search(r"san francisco|bay area|san jose|oakland|palo alto|mountain view|san mateo|redwood|sunnyvale|menlo|walnut creek|berkeley|emeryville|santa clara|foster city|pleasanton|fremont",c): return (0,"SF Bay Area")
    if re.search(r"\btx\b|texas|austin|houston|san antonio",c): return (1,"Other Texas")
    return (2,"Rest of US")
NONUS=re.compile(r"edinburgh|sydney|manila|neuilly|paris|barcelona|madrid|milan|warszawa|warsaw|lisbon|kuala lumpur|buenos aires|argentina|melbourne|glasgow|munich|frankfurt|tokyo|seoul|bogota|santiago|lima|johannesburg|dubai|canada|london|united kingdom|\buk\b|sao paulo|brazil|india|ireland|bermuda|mexico|singapore|hong kong|zurich, ch|switzerland|germany|toronto|montreal|australia|tlv|tel aviv|israel|dublin|amsterdam|netherlands|philippines|poland|spain|japan|china|france|head office",re.I)
def best_loc(locs):
    us=[l for l in locs if l and not NONUS.search(l)]
    return sorted(us,key=lambda l:group(l)[0])[0] if us else None
# ---- H-1B evidence (public DOL LCA data via h1bdata.info). employer -> list of (h1b employer name, query)
H1B_MAP={"Coalition":["COALITION INC"],"Hippo":["HIPPO EMPLOYEE SERVICES INC"],"Lemonade":["LEMONADE INC"],"AIG":["AIG PC GLOBAL SERVICES INC"],
 "CNA":["CONTINENTAL CASUALTY COMPANY"],"Swiss Re":["SWISS RE AMERICA HOLDING CORPORATION"],"Liberty Mutual":["LIBERTY MUTUAL GROUP INC"],
 "Milliman":["MILLIMAN INC"],"Munich Re":["MUNICH REINSURANCE AMERICA INC"],"Aon":["AON CONSULTING INC","AON RISK CONSULTANTS INC","AON RE INC"],"State Farm":["STATE FARM MUTUAL AUTOMOBILE INSURANCE COMPANY"],
 "Allstate":["ALLSTATE INSURANCE COMPANY"],"Nationwide":["NATIONWIDE MUTUAL INSURANCE COMPANY"],"Travelers":["TRAVELERS INDEMNITY COMPANY"],"Deloitte":["DELOITTE CONSULTING LLP"],"Pie Insurance":["PIE INSURANCE HOLDINGS INC"],"Kin Insurance":["KIN INSURANCE INC"],"USAA":["UNITED SERVICES AUTOMOBILE ASSOCIATION"],"The Hartford":["HARTFORD FIRE INSURANCE COMPANY","THE HARTFORD STEAM BOILER INSPECTION & INSURANCE CO"],"American Family":["AMERICAN FAMILY MUTUAL INSURANCE COMPANY"],"Everest":["EVEREST REINSURANCE COMPANY"],"Tokio Marine HCC":["HCC SERVICE COMPANY INC"],"Kemper":["KEMPER CORPORATE SERVICES INC"],"Assurant":["ASSURANT INC"],"TransRe":["TRANSATLANTIC REINSURANCE COMPANY"],"PwC":["PRICEWATERHOUSECOOPERS ADVISORY SERVICES LLC"],"Next Insurance":["NEXT INSURANCE US COMPANY"],"Marsh McLennan (Oliver Wyman/Guy Carpenter/Mercer)":["OLIVER WYMAN ACTUARIAL CONSULTING INC","GUY CARPENTER AND COMPANY LLC","MARSH USA LLC","MERCER HEALTH & BENEFITS LLC"],"Branch":["BRANCH FINANCIAL INC"]}
H1B=json.load(open("h1b.json")) if __import__("os").path.exists("h1b.json") else {}
def h1b_ev(company):
    out=[]
    for name in H1B_MAP.get(company,[]):
        for y,n in sorted(H1B.get(name,{}).items(),reverse=True): out.append(f"{n} actuarial-title LCA(s) in {y} ({name.title()})")
    return "; ".join(out)
# ---- sources ----
GH={"coalition":"Coalition","hippo70":"Hippo","pieinsurance":"Pie Insurance","nextinsurance66":"Next Insurance","cowbellcyber":"Cowbell","kettle":"Kettle","federato":"Federato","counterpart":"Counterpart"}
ASHBY={"lemonade":"Lemonade","kin":"Kin Insurance","openly":"Openly","branchinsurance":"Branch","steadily":"Steadily","slide":"Slide Insurance","akur8":"Akur8"}
WD={"Travelers":("travelers","wd5","External"),"Allstate":("allstate","wd5","allstate_careers"),"AIG":("aig","wd1","aig"),"Nationwide":("nationwide","wd1","Nationwide_Career"),"CNA":("cna","wd1","CNA_Careers"),"USAA":("usaa","wd1","USAAJOBSWD"),"The Hartford":("thehartford","wd5","Careers_External"),"American Family":("amfam","wd1","Careers"),"Marsh McLennan (Oliver Wyman/Guy Carpenter/Mercer)":("mmc","wd1","MMC"),"Everest":("everestre","wd5","External"),"Tokio Marine HCC":("tmhcc","wd108","External"),"Kemper":("kemper","wd5","kemper_careers"),"Assurant":("assurant","wd1","Assurant_Careers"),"TransRe":("transre","wd1","transreCareers"),"Hiscox":("hiscox","wd3","Hiscox_External_Site"),"PwC":("pwc","wd3","Global_Experienced_Careers"),"Markel":("markelcorp","wd5","GlobalCareers"),"AXIS Capital":("axiscapital","wd1","axiscareers"),"Sompo International":("endurance","wd103","SompoInternational"),"Auto-Owners":("aoins","wd5","AutoOwners"),"Texas Mutual":("texasmutual","wd1","texas_mutual_careers"),"Arch Insurance":("archgroup","wd1","Careers"),"Starr":("starrcompanies","wd1","Careers"),"MGIC":("mgic","wd5","MGIC"),"EMC Insurance":("emcins","wd5","EMC_Careers")}
WDQ=["actuary","actuarial","pricing actuary","enterprise risk","data scientist","product manager insurance"]
leads=[];status={}
for slug,co in GH.items():
    d=curl(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    if not d: status[f"Greenhouse:{co}"]="failed"; continue
    k=0
    for x in d.get("jobs",[]):
        cat=category(x["title"]);
        if not cat: continue
        loc=best_loc([s.strip() for s in re.split(r";",x["location"]["name"])])
        if not loc: continue
        k+=1; leads.append(dict(title=x["title"],company=co,city=loc,posted=(x.get("first_published") or "")[:10],posted_note="" if x.get("first_published") else ("updated "+x.get("updated_at","")[:10] if x.get("updated_at") else ""),text=strip(x.get("content")),link=x["absolute_url"],src=f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",source="Greenhouse"))
    status[f"Greenhouse:{co}"]=f"ok ({k} matching)"
for slug,co in ASHBY.items():
    d=curl(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if not d: status[f"Ashby:{co}"]="failed"; continue
    k=0
    for x in d.get("jobs",[]):
        cat=category(x["title"])
        if not cat: continue
        loc=best_loc([x.get("location","")]+[s.get("location","") for s in x.get("secondaryLocations",[])])
        if not loc: continue
        k+=1; leads.append(dict(title=x["title"],company=co,city=loc,posted=(x.get("publishedAt") or "")[:10],text=x.get("descriptionPlain",""),link=x.get("jobUrl"),src=f"https://api.ashbyhq.com/posting-api/job-board/{slug}",source="Ashby"))
    status[f"Ashby:{co}"]=f"ok ({k} matching)"
L1CO={"AIG","Chubb","Hiscox","AXIS Capital","Sompo International","Swiss Re","Liberty Mutual","Marsh McLennan (Oliver Wyman/Guy Carpenter/Mercer)","Markel","Everest","Tokio Marine HCC","Arch Insurance","TransRe","Assurant","PwC","Starr","EY"}
L1CTY=re.compile(r"United Kingdom|Ireland|Canada|Switzerland|Germany|France|Netherlands|Belgium|Spain|Italy|Bermuda|Luxembourg|Denmark|Sweden|\b(GB|IE|CA|CH|DE|FR|NL|BE|ES|IT|BM|LU)\b",re.I)
L1T=re.compile(r"actuar|pricing",re.I)
CAPX={"University of Chicago":("uchicago","wd5","External"),"MITRE (nonprofit FFRDC)":("mitre","wd5","mitre"),"Ohio State University":("osu","wd1","osuCareers"),"RAND Corporation":("rand","wd5","External_Career_Site"),"Yale University":("yale","wd1","External_Career_Site")}
CAPT=re.compile(r"actuar|risk (analyst|model|scien|quant)|quantitative|statistic|insurance|catastroph|econometric|data scientist|biostat",re.I)
def wd_one(co,t,w,site,capx=False):
    base=f"https://{t}.{w}.myworkdayjobs.com/wday/cxs/{t}/{site}"; seen={};ok=False;out=[]
    for q in WDQ:
        d=curl(base+"/jobs",{"searchText":q,"limit":20,"offset":0,"appliedFacets":{}})
        if not d or "jobPostings" not in d: continue
        ok=True
        for x in d["jobPostings"]:
            if (CAPT.search(x["title"]) if capx else category(x["title"])) and not re.search(r"\bdirector\b|head of|vice president|\bvp\b|chief|intern\b|student",x["title"],re.I): seen[x["externalPath"]]=x
    if not ok: return co,"failed",[]
    for p,x in list(seen.items())[:30]:
        dd=curl(base+p)
        if not dd: continue
        j=dd.get("jobPostingInfo",{})
        cty=(j.get("country") or {}).get("descriptor","")
        tl=j.get("title",x["title"])
        if cty and "United States" not in cty:
            if co in L1CO and L1CTY.search(cty) and L1T.search(tl) and not re.search(r"analyst|assistant|graduate|intern|life|health|benefit|pension|compensation|auditor|retirement",tl,re.I):
                out.append(dict(title=tl,company=co,city=f'{j.get("location","")}, {cty}',posted=(j.get("startDate") or "")[:10],text="",link=j.get("externalUrl") or f"https://{t}.{w}.myworkdayjobs.com/{site}{p}",src=base+"/jobs",source="Workday",route="L1"))
            continue
        loc=best_loc([j.get("location","")]+j.get("additionalLocations",[]))
        if not loc: continue
        out.append(dict(route="CAPX" if capx else "",title=j.get("title",x["title"]),company=co,city=loc,posted=(j.get("startDate") or "")[:10],posted_note=x.get("postedOn",""),text=strip(j.get("jobDescription")),link=j.get("externalUrl") or f"https://{t}.{w}.myworkdayjobs.com/{site}{p}",src=base+"/jobs",source="Workday"))
    return co,f"ok ({sum(not x.get('route') for x in out)} US, {sum(x.get('route')=='L1' for x in out)} L-1 overseas, {sum(x.get('route')=='CAPX' for x in out)} cap-exempt)",out
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(8) as ex:
    for co,st,out in ex.map(lambda kv:wd_one(kv[0],*kv[1][:3],capx=kv[1][3]),[(k,v+(False,)) for k,v in WD.items()]+[(k,v+(True,)) for k,v in CAPX.items()]):
        status[f"Workday:{co}"]=st; leads+=out

# ---- other ATS families ----
USST=r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b"
def txt(u,extra=()):
    time.sleep(0.4)
    return subprocess.run(["curl","-s","-L","-m","30","-A",UA,*extra,u],capture_output=True,text=True).stdout
def keep(t): return category(t) and not re.search(r"\bdirector\b|head of|vice president|\bvp\b|chief|intern\b",t,re.I)
def oracle(co,host,site):
    out=[]
    for q in ["actuary","actuarial","pricing"]:
        try: d=json.loads(txt(f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList.secondaryLocations&finder=findReqs;siteNumber={site},keyword=%22{q}%22,limit=50,sortBy=POSTING_DATES_DESC"))
        except Exception: continue
        for x in d["items"][0]["requisitionList"]:
            loc=x.get("PrimaryLocation","")
            if not keep(x["Title"]): continue
            if "United States" not in (loc+str(x.get("PrimaryLocationCountry",""))) and x.get("PrimaryLocationCountry")!="US":
                if L1CTY.search(loc) and L1T.search(x["Title"]) and not re.search(r"analyst|assistant|graduate|life|health|benefit|pension|compensation|auditor|retirement",x["Title"],re.I):
                    out.append(dict(title=x["Title"],company=co,city=loc,posted=(x.get("PostedDate") or "")[:10],text="",link=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{x['Id']}",src=f"oracle:{host}:{site}",source="Oracle HCM",route="L1"))
                continue
            out.append(dict(title=x["Title"],company=co,city=loc,posted=(x.get("PostedDate") or "")[:10],text=x.get("ShortDescriptionStr") or "",link=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{x['Id']}",src=f"oracle:{host}:{site}",source="Oracle HCM"))
    return out
def eightfold(co,host,domain,base):
    out=[]
    for q in ["actuary","actuarial","pricing actuary"]:
        try: d=json.loads(txt(f"https://{host}/api/apply/v2/jobs?domain={domain}&query={q.replace(' ','%20')}&num=50&sort_by=timestamp"))
        except Exception: continue
        for p in d.get("positions",[]):
            loc=p.get("location","")
            if not keep(p["name"]): continue
            if "United States" not in loc:
                if L1CTY.search(loc) and L1T.search(p["name"]) and not re.search(r"analyst|assistant|graduate|life|health|benefit|pension|compensation|auditor|retirement",p["name"],re.I):
                    out.append(dict(title=p["name"],company=co,city=loc,posted=datetime.date.fromtimestamp(p["t_create"]).isoformat() if p.get("t_create") else "",text="",link=p.get("canonicalPositionUrl") or f"{base}/job/{p['id']}",src=f"eightfold:{host}",source="Eightfold",route="L1"))
                continue
            out.append(dict(title=p["name"],company=co,city=loc.replace(", United States",""),posted=datetime.date.fromtimestamp(p["t_create"]).isoformat() if p.get("t_create") else "",text=p.get("job_description","") or "",link=p.get("canonicalPositionUrl") or f"{base}/job/{p['id']}",src=f"eightfold:{host}",source="Eightfold"))
    return out
def phenom(co,host,ref):
    out=[]
    for q in ["actuary","actuarial","enterprise risk","pricing"]:
        body={"lang":"en_us","deviceType":"desktop","country":"us","pageName":"search-results","ddoKey":"refineSearch","sortBy":"Most recent","subsearch":"","from":0,"jobs":True,"counts":True,"all_fields":[],"size":50,"clearAll":False,"jdsource":"facets","isSliderEnable":False,"pageId":"page20","siteType":"external","keywords":q,"global":True,"selected_fields":{},"locationData":{},"refNum":ref}
        try: d=json.loads(subprocess.run(["curl","-s","-m","30","-A",UA,"-X","POST","-H","Content-Type: application/json","-d",json.dumps(body),f"https://{host}/widgets"],capture_output=True,text=True).stdout)["refineSearch"]["data"]["jobs"]
        except Exception: continue
        for j in d:
            if not keep(j.get("title","")) or j.get("country") not in (None,"","United States","United States of America","US"): continue
            out.append(dict(title=j["title"],company=co,city=j.get("location",""),posted=(j.get("postedDate") or "")[:10],text=j.get("descriptionTeaser","") or "",link=f"https://{host}/us/en/job/{j.get('jobId') or j.get('jobSeqNo')}",src=f"phenom:{host}",source="Phenom"))
    return out
def rmk(co,host,path=""):
    out=[]
    for q in ["actuary","actuarial","pricing"]:
        x=txt(f"https://{host}{path}/services/rss/job/?locale=en_US&keywords=({q})")
        for it in re.findall(r"<item>(.*?)</item>",x,re.S):
            t=re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>",it,re.S).group(1)
            m=re.match(r"(.*)\((.*)\)\s*$",t); title,loc=(m.group(1).strip(),m.group(2)) if m else (t,"")
            if not keep(title): continue
            if ", US" not in loc:
                if co in L1CO and L1CTY.search(loc) and L1T.search(title) and not re.search(r"analyst|assistant|graduate|life|health|benefit|pension|compensation|auditor|retirement",title,re.I):
                    out.append(dict(title=title,company=co,city=loc,posted="",text="",link=html.unescape(re.search(r"<link>(.*?)</link>",it,re.S).group(1)).split("?")[0],src=f"rmk:{host}",source="SuccessFactors",route="L1"))
                continue
            pd_=re.search(r"<pubDate>(.*?)</pubDate>",it)
            try: posted=datetime.datetime.strptime(pd_.group(1)[:16],"%a, %d %b %Y").date().isoformat()
            except Exception: posted=""
            desc=re.search(r"<description><!\[CDATA\[(.*?)\]\]></description>",it,re.S)
            out.append(dict(title=title,company=co,city=re.sub(r", US.*","",loc),posted=posted,posted_note="SuccessFactors feed date",text=strip(desc.group(1) if desc else ""),link=html.unescape(re.search(r"<link>(.*?)</link>",it,re.S).group(1)).split("?")[0],src=f"rmk:{host}",source="SuccessFactors"))
    return out
def icims(co,host):
    out=[]
    for q in ["actuary","actuarial","pricing"]:
        h=txt(f"https://{host}/jobs/search?ss=1&searchKeyword={q}&in_iframe=1")
        for u,t in re.findall(r'href="(https://[^"]+/jobs/\d+/[^"]+/job)\?in_iframe=1"[^>]*title="\d+ - ([^"]+)"',h):
            t=html.unescape(t)
            if not keep(t): continue
            dd=txt(u+"?in_iframe=1"); loc=(re.search(r'US-([A-Z]{2})-([^<"\n]+)',dd) or None)
            if not loc: continue
            out.append(dict(title=t,company=co,city=f"{loc.group(2).strip()}, {loc.group(1)}",posted=(re.search(r'"datePosted"\s*:\s*"(\d{4}-\d\d-\d\d)',dd) or [None,""])[1],text=strip(dd)[:20000],link=u,src=f"icims:{host}",source="iCIMS"))
    return out
OTHER=[(oracle,("Chubb","fa-ewgu-saasfaprod1.fa.ocs.oraclecloud.com","CX_2001")),(eightfold,("Liberty Mutual","libertymutual.eightfold.ai","libertymutual.com","https://searchjobs.libertymutualgroup.com/careers")),
 (phenom,("CSAA Insurance Group","careers.csaa-insurance.aaa.com","CIEXUS")),(rmk,("Erie Insurance","jobs.erieinsurance.com")),(rmk,("Swiss Re","careers.swissre.com")),(rmk,("EY","careers.ey.com","/ey")),(icims,("W. R. Berkley","careers-berkley.icims.com"))]
with ThreadPoolExecutor(8) as ex:
    for (fn,a),fut in [(o,ex.submit(o[0],*o[1])) for o in OTHER]:
        try: out=fut.result(); seenl=set(); out=[x for x in out if not (x["link"] in seenl or seenl.add(x["link"]))]; leads+=out; status[f"{x_src if False else out[0]['source'] if out else fn.__name__}:{a[0]}"]=f"ok ({len(out)} matching US)"
        except Exception as e: status[f"{fn.__name__}:{a[0]}"]=f"failed ({type(e).__name__})"
# LinkedIn rows from refresh.py (already sponsorship-positive)
try:
    li=json.load(open("jobs.json"))
    for r in li["jobs"]:
        leads.append(dict(title=r["title"],company=r["company"],city=r["city"],posted=r["posted"][:10] if re.match(r"\d{4}-\d\d-\d\d",r["posted"] or "") else "",posted_note="" if re.match(r"\d{4}-",r["posted"] or "") else ("LinkedIn shows: "+r["posted"] if r["posted"] else ""),text=r["quote"],link=r["link"],src="LinkedIn guest job search",source="LinkedIn"))
    status["LinkedIn"]=f"ok ({len(li['jobs'])} sponsorship-positive of {li['checked']} checked)"
except Exception: status["LinkedIn"]="failed"

# ---- title-level H-1B evidence from h1b_rows.json (public DOL LCA filings indexed by h1bdata.info) ----
EMPRX={"Coalition":r"^COALITION INC","Hippo":r"^HIPPO","Lemonade":r"^LEMONADE","AIG":r"^AIG |NATIONAL UNION FIRE|AMERICAN HOME ASSURANCE|LEXINGTON INS","CNA":r"CONTINENTAL CASUALTY|^CNA ",
 "Swiss Re":r"^SWISS RE","Liberty Mutual":r"LIBERTY MUTUAL|SAFECO|IRONSHORE","Milliman":r"^MILLIMAN","Munich Re":r"MUNICH RE(INSURANCE)? AMERICA|MUNICH RE AMERICA|HARTFORD STEAM","Aon":r"^AON ","State Farm":r"^STATE FARM",
 "Allstate":r"^ALLSTATE|NATIONAL GENERAL","Nationwide":r"^NATIONWIDE","Travelers":r"^TRAVELERS","Deloitte":r"^DELOITTE","Pie Insurance":r"^PIE INSURANCE","Kin Insurance":r"^KIN INSURANCE",
 "USAA":r"UNITED SERVICES AUTOMOBILE|^USAA","The Hartford":r"^HARTFORD FIRE|^THE HARTFORD(?! STEAM)|HARTFORD CASUALTY","American Family":r"AMERICAN FAMILY MUTUAL|HOMESITE|MAIN STREET AMERICA","Everest":r"^EVEREST",
 "Tokio Marine HCC":r"^HCC |TOKIO MARINE","Kemper":r"^KEMPER","Assurant":r"^ASSURANT","TransRe":r"TRANSATLANTIC REINSURANCE|^TRANSRE","PwC":r"PRICEWATERHOUSECOOPERS","Next Insurance":r"^NEXT INSURANCE",
 "Marsh McLennan (Oliver Wyman/Guy Carpenter/Mercer)":r"OLIVER WYMAN|GUY CARPENTER|^MARSH |^MERCER (?!HEALTH)","Branch":r"^BRANCH FINANCIAL","Chubb":r"ACE AMERICAN|^CHUBB|ACE PROPERTY|FEDERAL INSURANCE COMPANY",
 "Markel":r"^MARKEL","AXIS Capital":r"^AXIS ","Sompo International":r"^ENDURANCE|^SOMPO","Arch Insurance":r"^ARCH ","Starr":r"^STARR ","MGIC":r"MORTGAGE GUARANTY","EMC Insurance":r"EMPLOYERS MUTUAL CASUALTY",
 "Erie Insurance":r"^ERIE ","CSAA Insurance Group":r"^CSAA","W. R. Berkley":r"BERKLEY","EY":r"^ERNST & YOUNG|^EY ","Auto-Owners":r"AUTO-OWNERS|AUTO OWNERS","Texas Mutual":r"^TEXAS MUTUAL","Akur8":r"^AKUR8",
 "Steadily":r"^STEADILY","Openly":r"^OPENLY","Kettle":r"^KETTLE","Hiscox":r"^HISCOX","Cowbell":r"^COWBELL","Slide Insurance":r"^SLIDE "}
H1R=json.load(open("h1b_rows.json")) if __import__("os").path.exists("h1b_rows.json") else []
TOK=lambda t:set(re.findall(r"[a-z]+",t.lower().replace("sr.","senior").replace("sr ","senior ")))-{"and","of","the","i","ii","iii","remote","us"}
def h1b_title_ev(company,title):
    rx=EMPRX.get(company)
    if not rx: return None
    rs=[r for r in H1R if re.search(rx,r["employer"])]
    if not rs: return None
    lt=TOK(title); key={"pricing","reserving","reinsurance","casualty","predictive","catastrophe","consultant","consulting","actuary","senior","lead","principal","manager"}
    def sim(r):
        ft=TOK(r["title"]); return len(lt&ft&key)*2+len(lt&ft)+(2 if "pricing" in lt&ft else 0)
    best=max(sim(r) for r in rs); top=[r for r in rs if sim(r)==best]
    t=collections.Counter(r["title"] for r in top).most_common(1)[0][0]; tr=[r for r in top if r["title"]==t]
    yr=max(r["year"] for r in tr); sal=[r["salary"] for r in tr if r["salary"]]
    close=best>=4 and ("actuar" in t.lower()) and int(yr)>=TODAY.year-1
    sal_s=(f", ${min(sal)//1000}k" + (f"-${max(sal)//1000}k" if max(sal)!=min(sal) else "")) if sal else ""
    return dict(close=close,text=f"Public filing history (not a promise): {len(tr)} H-1B LCA(s) for “{t.title()}”, latest {yr}{sal_s}; {len(rs)} actuarial-type LCAs at this employer 2024-26",title=t,year=yr,n=len(tr),sal=sal_s.strip(", "),total=len(rs))
import collections
# ---- tiering ----
LH=re.compile(r"\blife\b|pension|penion|health|A&H|accident|annuit|medical|medicare|mortality|longevity",re.I)
TODAY=datetime.date.today()
def isnew(p):
    try: return (TODAY-datetime.date.fromisoformat(p)).days<=2
    except Exception: return False

rows=[];dropped=0;seenk=set()
for L in leads:
    k=(L["company"],L["title"],L["city"])
    if k in seenk: continue
    seenk.add(k)
    cat=category(L["title"]) or (("Cap-exempt research/quant role","Moderate",3) if L.get("route")=="CAPX" else None)
    if not cat or re.search(r"intern\b|early careers|20\d\d start|new grad",L["title"],re.I): continue
    if LH.search(L["title"]+" "+cat[0]): continue  # life/health excluded
    s,q=spons(L["text"])
    if s=="no": dropped+=1; continue
    te=h1b_title_ev(L["company"],L["title"])
    if s=="yes": tier,why="A",f"Posting: “{q}”"+(". "+te["text"] if te else "")
    elif te and te["close"]: tier,why="A",(f"Posting: “{q}”. " if q else "Posting silent on sponsorship. ")+te["text"]
    elif te: tier,why="B",(f"Posting: “{q}”. " if q else "Posting silent on sponsorship. ")+te["text"]
    elif s=="may": tier,why="B",f"Posting: “{q}” (no actuarial H-1B filings found for this employer in 2024-26)"
    else: tier,why="C","Posting silent on sponsorship; no actuarial H-1B filings found for this employer in 2024-26"
    gk,g=group(L["city"])
    rows.append(dict(route=L.get("route",""),tier=tier,why=why,h1b=te,category=cat[0],difficulty=cat[1],drank=cat[2],gk=gk,group=g,lh=bool(LH.search(L["title"]+" "+cat[0])),posted_note=L.get("posted_note",""),**{k:L[k] for k in ("title","company","city","posted","link","src","source")}))
rows.sort(key=lambda r:(r["tier"],r["drank"],r["gk"],r["posted"]=="" ,""),)
for r in rows: r["new"]=isnew(r["posted"]); r["section"]="LH" if r["lh"] else r["tier"]
rows.sort(key=lambda r:r["posted"],reverse=True); rows.sort(key=lambda r:"ABCLH".index(r["section"]) if r["section"]!="LH" else 9)
now=datetime.datetime.now(zoneinfo.ZoneInfo("America/Chicago")).strftime("%b %d, %Y %I:%M %p CT")
json.dump({"updated":now,"status":status,"dropped_no_sponsorship":dropped,"leads":rows},open("leads.json","w"),indent=1)
e=html.escape
TN={"A":"Tier A · Posting explicitly says sponsorship is available","B":"Tier B · Sponsorship “may be available”, or employer has recent actuarial H-1B filings","C":"Tier C · Silent on sponsorship, no H-1B evidence found"}
def pd(r):
    if r["posted"]: return " · <b>Posted "+datetime.date.fromisoformat(r["posted"]).strftime("%b %d, %Y")+"</b>"
    if r["posted_note"]: return " · Posted date not shown ("+e(r["posted_note"])+")"
    return " · Posted date not shown"
TN["LH"]="Life & health roles (deprioritized)"
def card(r): return f'<article><h3>{"<span class=n>NEW</span> " if r["new"] else ""}<a href="{e(r["link"])}">{e(r["title"])}</a></h3><p class=m><span class=g>{e(r["group"])}</span><span class=c>{e(r["category"])} · {e(r["difficulty"])}</span> {e(r["company"])} · {e(r["city"])}{pd(r)}</p><p class=w>{e(r["why"])}</p><p class=s>Source: {e(r["source"])}</p></article>'
body="".join(f'<h2 class=s>{e(TN[t])} ({sum(r["section"]==t for r in rows)})</h2>'+("".join(card(r) for r in rows if r["section"]==t) or "<p>None found right now.</p>") for t in ["A","B","C","LH"])
st="".join(f"<li>{e(k)}: {e(v)}</li>" for k,v in status.items())
open("index.html","w").write(f'''<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Actuarial roles with visa sponsorship · Dallas, SF Bay Area & US</title>
<style>body{{font-family:system-ui,sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem;color:#222;background:#fafafa}}h1{{font-size:1.5rem}}article{{background:#fff;border:1px solid #e3e3e3;border-radius:10px;padding:.9rem 1.2rem;margin:.8rem 0}}h3{{font-size:1.05rem;margin:0}}a{{color:#0a66c2}}.m{{color:#555;margin:.3rem 0}}.w{{margin:.3rem 0;color:#333;font-style:italic}}p.s,small,li{{color:#777;font-size:.85rem}}.g,.c{{border-radius:4px;padding:1px 6px;font-size:.78rem;margin-right:4px}}.g{{background:#e8f0fa;color:#0a66c2}}.c{{background:#eef7ee;color:#26734d}}.n{{background:#d93025;color:#fff;border-radius:4px;padding:1px 6px;font-size:.75rem}}h2.s{{font-size:1.1rem;margin-top:2rem;border-bottom:2px solid #0a66c2}}</style>
<h1>Actuarial &amp; insurance roles: visa sponsorship leads</h1>
<p>For fully credentialed actuaries (all exams passed), pricing focus first. Grouped by sponsorship evidence, then ordered by how easy the move is (easiest first), newest posting first within each group (NEW = posted in last 48h); life &amp; health roles are moved to the bottom. Location tiers: Dallas-Fort Worth and SF Bay Area, other Texas, rest of US. Postings that rule out sponsorship are dropped ({dropped} this run). H-1B counts come from public DOL LCA data (h1bdata.info), cover a limited sample, and are a signal only. Always confirm with the employer.</p>
<p><b>{len(rows)}</b> leads · Last updated {now}</p>{body}
<h2 class=s>Sources this run</h2><ul>{st}</ul></html>''')
print(len(rows),{t:sum(r["section"]==t for r in rows) for t in "ABC"},"dropped",dropped);print(json.dumps(status,indent=1))
