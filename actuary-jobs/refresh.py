#!/usr/bin/env python3
"""Refresh sponsoring actuarial roles (SF Bay Area + Dallas) from LinkedIn guest pages -> index.html"""
import re, time, json, html, subprocess, datetime, zoneinfo
from bs4 import BeautifulSoup
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
LOCS={"SF Bay Area":"location=San%20Francisco%20Bay%20Area","Dallas-Fort Worth":"location=Dallas-Fort%20Worth%20Metroplex","Texas":"location=Texas","United States":"location=United%20States&geoId=103644278"}
MAXFETCH=60
def group(city):
    c=city.lower()
    if re.search(r"dallas|fort worth|plano|irving|frisco|arlington|richardson|addison|mckinney|grapevine|dfw",c): return (0,"Dallas-Fort Worth")
    if re.search(r"san francisco|bay area|san jose|oakland|palo alto|mountain view|san mateo|redwood|sunnyvale|menlo|walnut creek|berkeley|emeryville|santa clara|foster city|pleasanton|fremont",c): return (0,"SF Bay Area")
    if re.search(r"\btx\b|texas",c): return (1,"Other Texas")
    return (2,"Rest of US")
KEYS=["actuarial","actuary","pricing actuary","actuarial data scientist","insurance data scientist","insurance predictive modeling"]
YES=re.compile(r"[^.\n]*(sponsorship (is|may be) available|will sponsor|(visa|immigration) sponsorship (is |may be )?(available|offered|provided)|sponsor(ship)? (for )?(H-?1B|visa)s? (is )?(available|offered))[^.\n]*\.?",re.I)
NO=re.compile(r"(not|unable to|no|won't|will not|cannot|does not)[^.\n]{0,60}sponsor|without (the need for )?(current or future )?sponsorship",re.I)
def get(u):
    time.sleep(1.1)
    return subprocess.run(["curl","-s","-L","-A",UA,"--max-time","25",u],capture_output=True,text=True).stdout
ids={}
for loc,q in LOCS.items():
  for k in KEYS:
    for start in range(0,30,10):
        s=BeautifulSoup(get(f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={k}&{q}&f_TPR=r2592000&sortBy=DD&start={start}"),"html.parser")
        cards=s.select("div.base-card, li")
        n=0
        for c in cards:
            urn=c.get("data-entity-urn","") or (c.select_one("[data-entity-urn]") or {}).get("data-entity-urn","")
            m=re.search(r"(\d{6,})",urn)
            if not m: continue
            n+=1
            t=c.select_one("time")
            ti=c.select_one(".base-search-card__title"); lo=c.select_one(".job-search-card__location")
            ti=ti.get_text(" ",strip=True) if ti else ""
            if ti and not re.search(r"actuar|enterprise risk|chief risk|insurance product manager|insurance data scien",ti,re.I): continue
            ids.setdefault(m.group(1),{"posted":t.get("datetime") if t else "","loc":lo.get_text(" ",strip=True) if lo else loc})
        if n==0: break
SEED=["4447767959","4426379877","4459618558"]
for j in SEED: ids.setdefault(j,{"posted":"","loc":""})
ids=dict(sorted(ids.items(),key=lambda kv:(kv[0] not in SEED,group(kv[1]["loc"])[0]))[:MAXFETCH])
print("candidate ids",len(ids))
rows=[];unread=0
for jid,meta in ids.items():
    h=""
    for _ in range(4):
        h=get(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}")
        if "description" in h: break
    if "description" not in h: unread+=1; continue
    s=BeautifulSoup(h,"html.parser")
    d=s.select_one(".show-more-less-html__markup, .description__text")
    txt=d.get_text("\n",strip=True) if d else ""
    m=YES.search(txt)
    if not m or NO.search(m.group(0)): continue
    if not meta["posted"]:
        t=s.select_one(".posted-time-ago__text"); meta["posted"]=t.get_text(strip=True) if t else ""
    g=lambda sel:(s.select_one(sel).get_text(" ",strip=True) if s.select_one(sel) else "")
    rows.append(dict(id=jid,title=g(".top-card-layout__title, h2"),company=g(".topcard__org-name-link, .topcard__flavor a"),
        city=g(".topcard__flavor--bullet"),posted=meta["posted"],quote=m.group(0).strip(),ml=bool(re.search(r"machine learning|predictive model|data science|python",txt,re.I)),link=f"https://www.linkedin.com/jobs/view/{jid}/"))
for r in rows: r["gk"],r["group"]=group(r["city"])
rows.sort(key=lambda r:r["posted"],reverse=True)
rows.sort(key=lambda r:r["gk"])
now=datetime.datetime.now(zoneinfo.ZoneInfo("America/Chicago")).strftime("%b %d, %Y %I:%M %p CT")
pass
json.dump({"updated":now,"unreadable":unread,"checked":len(ids),"jobs":rows},open("jobs.json","w"),indent=1)
e=html.escape
rows=[r for r in rows if re.search(r"actuar|enterprise risk|chief risk|product manager|data scien",r["title"],re.I)]
PRI=re.compile(r"pricing|p&c|property|casualty|insurtech|rat(e|ing)|reserv|product|filing|reinsur|model|analytic",re.I)
OTH=re.compile(r"health|life|pension|retirement|benefit",re.I)
for r in rows: r["priority"]=bool(PRI.search(r["title"])) and not OTH.search(r["title"])
card=lambda r:f'<article><h2><a href="{e(r["link"])}">{e(r["title"])}</a></h2><p class=m><span class=g>{e(r["group"])}</span> {e(r["company"])} · {e(r["city"])} · Posted {e(r["posted"])}{" · values ML/modeling skills" if r["ml"] else ""}</p><blockquote>“{e(r["quote"])}”</blockquote></article>'
sec=lambda L:"".join(card(r) for r in L) or "<p>None found right now.</p>"
cards="<h2 class=s>Pricing &amp; related actuarial roles (P&amp;C, insurtech, reserving, reinsurance, product, modeling)</h2>"+sec([r for r in rows if r["priority"]])+"<h2 class=s>Other actuarial roles (health, life, etc.)</h2>"+sec([r for r in rows if not r["priority"]])
open("index.html","w").write(f'''<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Sponsoring Actuarial Roles · Dallas, SF Bay Area & US</title>
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#222;background:#fafafa}}h1{{font-size:1.5rem}}article{{background:#fff;border:1px solid #e3e3e3;border-radius:10px;padding:1rem 1.2rem;margin:1rem 0}}h2{{font-size:1.1rem;margin:0}}a{{color:#0a66c2}}.m{{color:#555;margin:.3rem 0}}blockquote{{margin:.5rem 0 0;padding-left:.8rem;border-left:3px solid #0a66c2;color:#333;font-style:italic}}.g{{background:#e8f0fa;color:#0a66c2;border-radius:4px;padding:1px 6px;font-size:.8rem;margin-right:4px}}h2.s{{font-size:1.15rem;margin-top:2rem;border-bottom:2px solid #0a66c2}}small{{color:#777}}</style>
<h1>Actuarial & insurance roles open to visa sponsorship</h1>
<p>Dallas-Fort Worth and SF Bay Area first, then other Texas and the rest of the US · actuarial roles for fully credentialed actuaries, with P&amp;C / insurtech pricing first. Only postings whose text says sponsorship is or may be available are listed; postings that rule it out are excluded. Always confirm with the employer.</p>
<p><b>{len(rows)}</b> roles · Last updated {now}</p>{cards}
<small>Source: public LinkedIn job postings from the last 30 days. {len(ids)} postings checked{f", {unread} could not be loaded" if unread else ""}.</small></html>''')
print("listed",len(rows),"unread",unread)
