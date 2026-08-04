# IEEE Entity Resolution — workbooks-as-code generator.
# Usage: python3 build_ieee_er.py <SIGMA_BASE_URL> <TOKEN> <CONNECTION_ID> <FOLDER_ID>
# Data: raw_source_records.csv (multi-source member records) + pairwise_match_scores.csv
#       -> clustered into members, survivorship recommendations w/ confidence (er_data.py).
# App:  Page 1 Resolution Command Center (KPIs, conflicts-by-attribute, recommendation grid,
#       source-record evidence). Page 2 Golden Record Review (human-in-the-loop: pick a member,
#       compare source records vs recommended golden values, edit+approve via modal -> writeback
#       to a Golden Record input table). Clean light aesthetic, IEEE-blue accents.
import json,sys,os,base64,urllib.request,urllib.error,xml.dom.minidom as _MD
import er_data

BASE,TOKEN,CONN,FOLDER=sys.argv[1:5]
H={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json","Accept":"application/json"}
def b64(s): return base64.b64encode(s.encode()).decode()

# ---- palette (light canvas, IEEE blue accents) ----
NAVY="#00385E"; IEEE="#00629B"; INK="#12232E"; SLATE="#5A6B78"
TEAL="#1f9e8f"; CORAL="#e0526a"; AMBER="#d98a2b"; W="#FFFFFF"
GREY="#f5f7f9"; LINE="#dbe3ea"
CARD={"backgroundColor":W,"borderColor":LINE,"borderWidth":1,"borderRadius":"pill"}
GCARD={"backgroundColor":GREY,"borderColor":LINE,"borderWidth":1,"borderRadius":"pill"}
TINT={"backgroundColor":"#eaf3f9","borderColor":"#cfe3f0","borderWidth":1,"borderRadius":"pill"}
NUM0={"kind":"number","formatString":",.0f"}
PCT0={"kind":"number","formatString":".0%"}
PCT1={"kind":"number","formatString":".1%"}

def ic(body,col=IEEE,fill="none",sw=2.1):
    return "data:image/svg+xml;base64,"+b64(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{fill}" stroke="{col}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
IC_LAYERS='<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>'
IC_MERGE='<path d="M6 3v12"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>'
IC_ALERT='<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'
IC_SHIELD='<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>'
IC_GAUGE='<path d="M12 2a10 10 0 1 0 10 10"/><path d="M12 12l6-4"/>'
IC_CHECK='<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'
IC_LIST='<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>'
IC_USER='<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'

# authentic IEEE dark-blue banner with the real white master-brand logo
IEEE_DK="#00385E"  # IEEE deep blue
def _esc(t): return t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def timg(text,size,weight=700,col="#FFFFFF",font="Arial,Helvetica,sans-serif",w=900,h=90,ls=0):
    # bake light text as an SVG data-URI (text color is theme-driven, so on a dark band it must be an image)
    return ("data:image/svg+xml;base64,"+b64(
      f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMinYMid meet">'
      f'<text x="0" y="{int(h*0.72)}" font-family="{font}" font-weight="{weight}" font-size="{size}" '
      f'letter-spacing="{ls}" fill="{col}">{_esc(text)}</text></svg>'))
HEROBG="data:image/svg+xml;base64,"+b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 220" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#00629B"/><stop offset="0.65" stop-color="#00456e"/><stop offset="1" stop-color="#00385E"/></linearGradient></defs><rect width="1600" height="220" fill="url(#g)"/><rect x="0" y="0" width="1600" height="4" fill="#28c8c0"/></svg>')
try:
    logo_uri=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"ieee_logo_white.txt")).read().strip()
except Exception:
    logo_uri=timg("IEEE",64,900,"#FFFFFF",font="Georgia,serif",w=260,h=90,ls=3)

# ================= DATA (from er_data) =================
raw,pairs,rec_long,rec_wide,members=er_data.build()
mlabel={w["member_key"]: f'{w["member_key"]} · {w["display_name"] or "(no name)"}' for w in rec_wide}

def sq(v):  # sql string literal
    return "'"+str(v).replace("'","''")+"'"
def snum(v):
    return "NULL" if v is None or v=="" else str(v)
def values_table(rows):
    return "VALUES "+",".join("("+",".join(r)+")" for r in rows)

# ---- records table (source evidence) ----
rec_rows=[]
for r in sorted(raw,key=lambda x:(x['member_key'],er_data.auth_rank(x['source_system']),x['record_id'])):
    rec_rows.append([sq(r['member_key']),sq(mlabel[r['member_key']]),sq(r['record_id']),sq(r['source_system']),
        sq(r['name']),sq(r['email']),sq(r['phone']),sq(r['member_number']),sq(r['member_grade']),
        sq(r['society']),sq(r['section']),sq(r['address']),sq(r['record_created_date'])])
REC_SQL=("SELECT column1::string AS MEMBER_KEY, column2::string AS MEMBER_LABEL, column3::string AS RECORD_ID,"
 " column4::string AS SOURCE_SYSTEM, column5::string AS NAME, column6::string AS EMAIL, column7::string AS PHONE,"
 " column8::string AS MEMBER_NUMBER, column9::string AS MEMBER_GRADE, column10::string AS SOCIETY,"
 " column11::string AS SECTION, column12::string AS ADDRESS, column13::string AS RECORD_CREATED_DATE"
 " FROM ("+values_table(rec_rows)+")")
REC_COLS=[("r-mk","MEMBER_KEY","Member Key"),("r-lbl","MEMBER_LABEL","Member"),("r-rid","RECORD_ID","Record ID"),
 ("r-src","SOURCE_SYSTEM","Source System"),("r-name","NAME","Name"),("r-email","EMAIL","Email"),
 ("r-phone","PHONE","Phone"),("r-mnum","MEMBER_NUMBER","Member #"),("r-grade","MEMBER_GRADE","Grade"),
 ("r-soc","SOCIETY","Society"),("r-sec","SECTION","Section"),("r-addr","ADDRESS","Address"),("r-date","RECORD_CREATED_DATE","Created")]
records={"id":"records","kind":"table","name":"Records","visibleAsSource":True,
 "source":{"connectionId":CONN,"kind":"sql","statement":REC_SQL},
 "columns":[{"id":i,"formula":f"[Custom SQL/{s}]","name":n} for i,s,n in REC_COLS],"order":[c[0] for c in REC_COLS]}

# ---- rec_long table (recommendations to evaluate) ----
ATTR_ORDER={a:i for i,(a,_) in enumerate(er_data.ATTRS)}
rl_rows=[]
for rl in rec_long:
    if rl["value"]=="" and rl["n_candidates"]==0: continue  # skip attrs with no data at all
    rl_rows.append([sq(rl["member_key"]),sq(mlabel[rl["member_key"]]),str(ATTR_ORDER[rl["attr"]]),sq(rl["label"]),
        sq(rl["value"]),sq(rl["source_system"]),sq(rl["source_record"]),snum(rl["confidence"]),
        sq("Yes" if rl["conflict"] else "No"),str(rl["n_candidates"]),str(rl["n_distinct"])])
RL_SQL=("SELECT column1::string AS MEMBER_KEY, column2::string AS MEMBER_LABEL, column3::int AS ATTR_ORDER,"
 " column4::string AS ATTRIBUTE, column5::string AS RECOMMENDED_VALUE, column6::string AS SOURCE_SYSTEM,"
 " column7::string AS SOURCE_RECORD, column8::float AS CONFIDENCE, column9::string AS CONFLICT,"
 " column10::int AS CANDIDATES, column11::int AS DISTINCT_VALUES FROM ("+values_table(rl_rows)+")")
RL_COLS=[("l-mk","MEMBER_KEY","Member Key"),("l-lbl","MEMBER_LABEL","Member"),("l-ord","ATTR_ORDER","Ord"),
 ("l-attr","ATTRIBUTE","Attribute"),("l-val","RECOMMENDED_VALUE","Recommended Value"),
 ("l-src","SOURCE_SYSTEM","Survivor Source"),("l-rec","SOURCE_RECORD","Source Record"),
 ("l-conf","CONFIDENCE","Confidence"),("l-conf2","CONFIDENCE","Confidence"),
 ("l-conflict","CONFLICT","Conflict"),("l-cand","CANDIDATES","Candidates"),("l-dist","DISTINCT_VALUES","Distinct Values")]
def rlcol(i,s,n):
    c={"id":i,"formula":f"[Custom SQL/{s}]","name":n}
    if s=="CONFIDENCE": c["format"]=PCT0
    return c
reclong={"id":"reclong","kind":"table","name":"RecLong","visibleAsSource":True,
 "source":{"connectionId":CONN,"kind":"sql","statement":RL_SQL},
 "columns":[rlcol(i,s,n) for i,s,n in [("l-mk","MEMBER_KEY","Member Key"),("l-lbl","MEMBER_LABEL","Member"),
    ("l-ord","ATTR_ORDER","Ord"),("l-attr","ATTRIBUTE","Attribute"),("l-val","RECOMMENDED_VALUE","Recommended Value"),
    ("l-src","SOURCE_SYSTEM","Survivor Source"),("l-conf","CONFIDENCE","Confidence"),
    ("l-conflict","CONFLICT","Conflict?"),("l-cand","CANDIDATES","Candidates"),("l-dist","DISTINCT_VALUES","Distinct Values")]],
 "order":["l-attr","l-val","l-src","l-conf","l-conflict","l-cand","l-dist"]}

# ---- rec_wide table (member-level: picker source, KPIs, modal seeding) ----
def W_(w,k): return w.get(k)
WCOLS=[("member_key","MEMBER_KEY","Member Key","string",None),
 ("member_label","MEMBER_LABEL","Member","string",None),
 ("display_name","DISPLAY_NAME","Name","string",None),
 ("member_number","MEMBER_NUMBER","Member #","string",None),
 ("n_records","N_RECORDS","Source Records","int",NUM0),
 ("n_sources","N_SOURCES","Distinct Sources","int",NUM0),
 ("overall_conf","OVERALL_CONF","Confidence","float",PCT0),
 ("conflict_count","CONFLICT_COUNT","Conflicts","int",NUM0),
 ("needs_flag","NEEDS_RESOLUTION","Needs Resolution","string",None),
 ("name","REC_NAME","Golden Name","string",None),
 ("email","REC_EMAIL","Golden Email","string",None),
 ("phone","REC_PHONE","Golden Phone","string",None),
 ("member_grade","REC_GRADE","Golden Grade","string",None),
 ("society","REC_SOCIETY","Golden Society","string",None),
 ("section","REC_SECTION","Golden Section","string",None),
 ("address","REC_ADDRESS","Golden Address","string",None)]
wrows=[]
_wsort=sorted(rec_wide,key=lambda w:(0 if w["needs_resolution"] else 1, -w["conflict_count"],
                                     w["overall_conf"] if w["overall_conf"] is not None else 1.0, w["member_key"]))
for w in _wsort:
    w=dict(w); w["needs_flag"]="Yes" if w["needs_resolution"] else "No"
    w["member_label"]=mlabel[w["member_key"]]
    cells=[]
    for key,alias,_,typ,_ in WCOLS:
        v=w.get(key)
        if typ in ("int","float"): cells.append(snum(v))
        else: cells.append(sq("" if v is None else v))
    wrows.append(cells)
sel=", ".join(f"column{i+1}::{typ} AS {alias}" for i,(key,alias,_,typ,_) in enumerate(WCOLS))
WIDE_SQL="SELECT "+sel+" FROM ("+values_table(wrows)+")"
def wcol(key,alias,name,typ,fmt):
    c={"id":"w-"+key.replace("_","-"),"formula":f"[Custom SQL/{alias}]","name":name}
    if fmt: c["format"]=fmt
    return c
recwide={"id":"recwide","kind":"table","name":"Members","visibleAsSource":True,
 "source":{"connectionId":CONN,"kind":"sql","statement":WIDE_SQL},
 "columns":[wcol(*c) for c in WCOLS],
 "order":["w-member-label","w-n-records","w-n-sources","w-conflict-count","w-overall-conf","w-needs-flag"]}
def wid(key): return "w-"+key.replace("_","-")

# ---- golden record INPUT TABLE (writeback) ----
golden={"id":"golden","kind":"input-table","source":{"kind":"empty","connectionId":CONN},"inputMode":"edit","name":"Golden",
 "columns":[{"id":"g-mk","type":"text","name":"Member Key"},
    {"id":"g-name","type":"text","name":"Golden Name"},
    {"id":"g-email","type":"text","name":"Golden Email"},
    {"id":"g-phone","type":"text","name":"Golden Phone"},
    {"id":"g-grade","type":"text","name":"Golden Grade"},
    {"id":"g-society","type":"text","name":"Golden Society"},
    {"id":"g-section","type":"text","name":"Golden Section"},
    {"id":"g-address","type":"text","name":"Golden Address"},
    {"id":"g-decision","type":"text","name":"Decision","values":["Accepted","Edited","Rejected"],"pills":"color-by-option"},
    {"id":"CREATED_AT"},{"id":"CREATED_BY"}],
 "order":["g-mk","g-name","g-email","g-phone","g-grade","g-society","g-section","g-address","g-decision","CREATED_AT","CREATED_BY"]}
# normal table over golden for KPIs / display (input tables shouldn't source KPIs directly)
goldn={"id":"goldn","kind":"table","name":"GoldenBook","visibleAsSource":True,"source":{"elementId":"golden","kind":"table"},
 "columns":[{"id":"gn-mk","formula":"[Golden/Member Key]","name":"Member Key"},
    {"id":"gn-name","formula":"[Golden/Golden Name]","name":"Golden Name"},
    {"id":"gn-email","formula":"[Golden/Golden Email]","name":"Golden Email"},
    {"id":"gn-phone","formula":"[Golden/Golden Phone]","name":"Golden Phone"},
    {"id":"gn-grade","formula":"[Golden/Golden Grade]","name":"Golden Grade"},
    {"id":"gn-society","formula":"[Golden/Golden Society]","name":"Golden Society"},
    {"id":"gn-section","formula":"[Golden/Golden Section]","name":"Golden Section"},
    {"id":"gn-addr","formula":"[Golden/Golden Address]","name":"Golden Address"},
    {"id":"gn-dec","formula":"[Golden/Decision]","name":"Decision"},
    {"id":"gn-at","formula":"[Golden/CREATED_AT]","name":"Approved At"},
    {"id":"gn-by","formula":"[Golden/CREATED_BY]","name":"Approved By"}],
 "order":["gn-mk","gn-name","gn-email","gn-phone","gn-grade","gn-society","gn-section","gn-addr","gn-dec","gn-at","gn-by"]}

# ================= HEADER (authentic IEEE dark banner, white logo + baked white text) =================
def header(sfx,title,subtitle):
    c={"id":f"c-hdr{sfx}","kind":"container","style":{"borderRadius":"round","borderColor":IEEE_DK,"borderWidth":1},
       "backgroundImage":{"source":{"kind":"url","url":HEROBG},"style":{"fit":"cover"}}}
    lg={"id":f"logo{sfx}","kind":"image","source":{"kind":"url","url":logo_uri},"style":{"fit":"contain"}}
    tag={"id":f"tag{sfx}","kind":"image","source":{"kind":"url","url":timg("Advancing Technology for Humanity",26,600,"#bfe0f2",w=820,h=48)},"style":{"fit":"contain"}}
    tt={"id":f"ttl{sfx}","kind":"image","source":{"kind":"url","url":timg(title,40,800,"#FFFFFF",w=1400,h=64)},"style":{"fit":"contain"}}
    sb={"id":f"sub{sfx}","kind":"image","source":{"kind":"url","url":timg(subtitle,23,500,"#dbeef9",w=1500,h=40)},"style":{"fit":"contain"}}
    lay=(f'  <GridContainer elementId="c-hdr{sfx}" type="grid" gridColumn="1 / 25" gridRow="1 / 6" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(8,1fr)">\n'
         f'    <LayoutElement elementId="logo{sfx}" gridColumn="2 / 7" gridRow="2 / 5"/>\n'
         f'    <LayoutElement elementId="tag{sfx}" gridColumn="2 / 12" gridRow="5 / 7"/>\n'
         f'    <LayoutElement elementId="ttl{sfx}" gridColumn="9 / 24" gridRow="2 / 5"/>\n'
         f'    <LayoutElement elementId="sub{sfx}" gridColumn="9 / 24" gridRow="5 / 7"/>\n  </GridContainer>')
    return [c,lg,tag,tt,sb],lay

# ================= KPI CARD (clean light, comparison-delta optional) =================
def kpi(elid,src,icon,title,valf,fmt,rowband,compf=None,goodup=True):
    cid=f"c-{elid}"
    cont={"id":cid,"kind":"container","style":dict(GCARD)}
    ik={"id":f"i-{elid}","kind":"image","source":{"kind":"url","url":icon},"style":{"fit":"contain"}}
    ttl={"id":f"t-{elid}","kind":"text","body":f"**{title}**","verticalAlign":"middle","style":{"color":SLATE}}
    cols=[{"id":f"k-{elid}v","formula":valf,"name":title,"format":fmt}]
    kv={"id":f"k-{elid}","kind":"kpi-chart","source":{"elementId":src,"kind":"table"},
        "value":{"columnId":f"k-{elid}v","color":NAVY,"fontSize":30},
        "name":{"visibility":"hidden"},"layout":{"anchor":"middle"},"style":{"backgroundColor":"transparent","padding":"none"}}
    if compf is not None:
        cols.append({"id":f"k-{elid}c","formula":compf,"name":"Comparison","format":fmt})
        kv["comparisonColumn"]={"columnId":f"k-{elid}c"}
        kv["comparison"]={"display":"delta","colorGood":TEAL if goodup else CORAL,"colorBad":CORAL if goodup else TEAL,"fontSize":13}
    kv["columns"]=cols
    lay=(f'  <GridContainer elementId="{cid}" type="grid" gridColumn="{{col}}" gridRow="{rowband}" gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="repeat(12,1fr)">\n'
         f'    <LayoutElement elementId="i-{elid}" gridColumn="1 / 3" gridRow="1 / 3"/>\n'
         f'    <LayoutElement elementId="t-{elid}" gridColumn="3 / 13" gridRow="1 / 3"/>\n'
         f'    <LayoutElement elementId="k-{elid}" gridColumn="1 / 13" gridRow="3 / 11"/>\n  </GridContainer>')
    return [cont,ik,ttl,kv],lay

# ---------- PAGE 1: COMMAND CENTER ----------
h1e,h1l=header("1","Member Entity Resolution — Command Center","Collapse multi-source records into a governed golden record per member")
# KPIs source recwide (population) + goldn (live approvals)
NREC=len(raw); NMEM=len(rec_wide); NNEED=sum(1 for w in rec_wide if w["needs_resolution"])
K1=[("k1","recwide",ic(IC_LAYERS),"SOURCE RECORDS",f"Sum([Members/Source Records])",NUM0,None,True),
    ("k2","recwide",ic(IC_MERGE),"RESOLVED MEMBERS",f"CountDistinct([Members/Member Key])",NUM0,f"Sum([Members/Source Records])",False),
    ("k3","recwide",ic(IC_USER),"NEED REVIEW",f'CountDistinct(If([Members/Needs Resolution]="Yes",[Members/Member Key],Null))',NUM0,None,True),
    ("k4","recwide",ic(IC_ALERT,CORAL),"ATTRIBUTE CONFLICTS",f"Sum([Members/Conflicts])",NUM0,None,True),
    ("k5","recwide",ic(IC_GAUGE),"AVG CONFIDENCE",f"Avg([Members/Confidence])",PCT0,None,True),
    ("k6","goldn",ic(IC_SHIELD,TEAL),"GOLDEN APPROVED",f"CountDistinct([GoldenBook/Member Key])",NUM0,None,True)]
kpis1=[]; kpil1=[]
for i,(elid,src,icn,t,vf,fmt,cf,gu) in enumerate(K1):
    e,l=kpi(elid,src,icn,t,vf,fmt,"6 / 13",compf=cf,goodup=gu); kpis1+=e; kpil1.append(l.replace("{col}",f"{1+i*4} / {1+(i+1)*4}"))

# conflicts-by-attribute bar (from reclong)
cbar={"id":"cbar","kind":"bar-chart","source":{"elementId":"reclong","kind":"table"},
 "columns":[{"id":"cb-attr","formula":"[RecLong/Attribute]","name":"Attribute"},
            {"id":"cb-cat","formula":'"Conflicts"',"name":"Series"},
            {"id":"cb-cnt","formula":'Sum(If([RecLong/Conflict?]="Yes",1,0))',"name":"Conflicting members","format":NUM0}],
 "xAxis":{"columnId":"cb-attr","sort":{"by":"cb-cnt","direction":"descending"}},"yAxis":{"columnIds":["cb-cnt"]},
 "color":{"by":"category","column":"cb-cat","scheme":[IEEE]},
 "dataLabel":{"labels":"shown","anchor":"end","fontSize":11},
 "legend":{"visibility":"hidden"},"name":{"text":"Attribute conflicts across members — where sources disagree","fontWeight":"bold","fontSize":14,"color":INK},"style":dict(CARD)}
# confidence-band bar
bband={"id":"bband","kind":"bar-chart","source":{"elementId":"recwide","kind":"table"},
 "columns":[{"id":"bb-band","formula":'If([Members/Confidence]>=0.85,"High (≥85%)",If([Members/Confidence]>=0.6,"Medium (60-85%)","Low (<60%)"))',"name":"Confidence band"},
            {"id":"bb-band2","formula":'If([Members/Confidence]>=0.85,"High (≥85%)",If([Members/Confidence]>=0.6,"Medium (60-85%)","Low (<60%)"))',"name":"Band color"},
            {"id":"bb-cnt","formula":"CountDistinct([Members/Member Key])","name":"Members","format":NUM0}],
 "xAxis":{"columnId":"bb-band"},"yAxis":{"columnIds":["bb-cnt"]},
 "color":{"by":"category","column":"bb-band2","scheme":[TEAL,AMBER,CORAL]},
 "dataLabel":{"labels":"shown","anchor":"end","fontSize":11},
 "legend":{"visibility":"hidden"},"name":{"text":"Members by survivorship confidence","fontWeight":"bold","fontSize":14,"color":INK},"style":dict(CARD)}

# AI-ish narrative (static text — no AI connection assumed)
ov_c={"id":"c-ov","kind":"container","style":dict(TINT)}
ov_ic={"id":"ov-ic","kind":"image","source":{"kind":"url","url":ic(IC_LIST,IEEE)},"style":{"fit":"contain"}}
ov_hd={"id":"ov-hd","kind":"text","body":"**How resolution works**","verticalAlign":"middle","style":{"color":INK}}
ov_tx={"id":"ov-tx","kind":"text","verticalAlign":"middle","style":{"color":"#2b3b45"},
 "body":(f"**{NREC} source records** across 5 IEEE systems were clustered into **{NMEM} members** "
   f"(matched on member number + high-confidence pairwise scores). For each member we recommend a "
   f"**survivor value** per attribute — chosen by source authority, completeness and recency, and scored "
   f"for confidence and conflict. **{NNEED} members** have 2+ records needing review. Use the **Golden "
   f"Record Review** page to approve or edit each member's golden record.")}

# recommendation grid (reclong) + evidence (records), both filter by member picker
recgrid={"id":"recgrid","kind":"table","name":"Recommendation grid","source":{"elementId":"reclong","kind":"table"},
 "columns":[{"id":"rg-attr","formula":"[RecLong/Attribute]","name":"Attribute"},
            {"id":"rg-val","formula":"[RecLong/Recommended Value]","name":"Recommended survivor value"},
            {"id":"rg-src","formula":"[RecLong/Survivor Source]","name":"From source"},
            {"id":"rg-conf","formula":"[RecLong/Confidence]","name":"Confidence","format":PCT0},
            {"id":"rg-conf-band","formula":'If([RecLong/Confidence]>=0.85,"High",If([RecLong/Confidence]>=0.6,"Medium","Low"))',"name":"Band"},
            {"id":"rg-conflict","formula":"[RecLong/Conflict?]","name":"Conflict?"},
            {"id":"rg-cand","formula":"[RecLong/Candidates]","name":"# Records"},
            {"id":"rg-dist","formula":"[RecLong/Distinct Values]","name":"# Distinct"},
            {"id":"rg-ord","formula":"[RecLong/Ord]","name":"Ord"},
            {"id":"rg-mk","formula":"[RecLong/Member Key]","name":"Member Key"},
            {"id":"rg-lbl","formula":"[RecLong/Member]","name":"Member"}],
 "groupings":[{"id":"grp-attr","groupBy":["rg-ord","rg-attr"],"calculations":[],"sort":[{"columnId":"rg-ord","direction":"ascending"}]}],
 "conditionalFormats":[
    {"type":"single","columnIds":["rg-conf"],"condition":"<","value":0.6,"style":{"backgroundColor":"#fbe0e6"}},
    {"type":"single","columnIds":["rg-conf"],"condition":"Between","low":0.6,"high":0.85,"style":{"backgroundColor":"#fbeeda"}},
    {"type":"single","columnIds":["rg-conf"],"condition":">","value":0.85,"style":{"backgroundColor":"#dff3ee"}},
    {"type":"single","columnIds":["rg-conflict"],"condition":"=","value":"Yes","style":{"backgroundColor":"#fbe0e6"}}],
 "name":{"text":"Recommended survivor values — pick a member above to focus","fontWeight":"bold","fontSize":14,"color":INK},"style":dict(CARD),
 "order":["rg-attr","rg-val","rg-src","rg-conf","rg-conf-band","rg-conflict","rg-cand","rg-dist"]}

evid={"id":"evid","kind":"table","name":"Source records","source":{"elementId":"records","kind":"table"},
 "columns":[{"id":"ev-src","formula":"[Records/Source System]","name":"Source System"},
            {"id":"ev-rid","formula":"[Records/Record ID]","name":"Record ID"},
            {"id":"ev-name","formula":"[Records/Name]","name":"Name"},
            {"id":"ev-email","formula":"[Records/Email]","name":"Email"},
            {"id":"ev-phone","formula":"[Records/Phone]","name":"Phone"},
            {"id":"ev-grade","formula":"[Records/Grade]","name":"Grade"},
            {"id":"ev-soc","formula":"[Records/Society]","name":"Society"},
            {"id":"ev-sec","formula":"[Records/Section]","name":"Section"},
            {"id":"ev-addr","formula":"[Records/Address]","name":"Address"},
            {"id":"ev-date","formula":"[Records/Created]","name":"Created"},
            {"id":"ev-mk","formula":"[Records/Member Key]","name":"Member Key"},
            {"id":"ev-lbl","formula":"[Records/Member]","name":"Member"}],
 "name":{"text":"Source records feeding the selected member","fontWeight":"bold","fontSize":14,"color":INK},"style":dict(CARD),
 "order":["ev-src","ev-rid","ev-name","ev-email","ev-phone","ev-grade","ev-soc","ev-sec","ev-addr","ev-date"]}

# member picker (list, single) — domain = recwide member_label; filters the PAGE-2 elements only
picker={"kind":"control","controlId":"memberPick","id":"ctrl-pick","name":"Member","controlType":"list","selectionMode":"single","mode":"include","values":[],
 "filters":[{"source":{"kind":"table","elementId":"recwide2"},"columnId":"s2-lbl"},
            {"source":{"kind":"table","elementId":"goldgrid"},"columnId":"gg-lbl"},
            {"source":{"kind":"table","elementId":"evid2"},"columnId":"e2-lbl"}],
 "source":{"kind":"source","source":{"kind":"table","elementId":"recwide"},"columnId":"w-member-label"}}

# selected-member summary (page-2 KPIs source this; picker filters it)
recwide2={"id":"recwide2","kind":"table","name":"MemberSel","visibleAsSource":True,"source":{"elementId":"recwide","kind":"table"},
 "columns":[{"id":"s2-lbl","formula":"[Members/Member]","name":"Member"},
    {"id":"s2-mk","formula":"[Members/Member Key]","name":"Member Key"},
    {"id":"s2-name","formula":"[Members/Name]","name":"Name"},
    {"id":"s2-nrec","formula":"[Members/Source Records]","name":"Source Records","format":NUM0},
    {"id":"s2-nsrc","formula":"[Members/Distinct Sources]","name":"Sources","format":NUM0},
    {"id":"s2-conf","formula":"[Members/Confidence]","name":"Confidence","format":PCT0},
    {"id":"s2-confl","formula":"[Members/Conflicts]","name":"Conflicts","format":NUM0}],
 "order":["s2-lbl","s2-name","s2-nrec","s2-nsrc","s2-conf","s2-confl"]}

# page-1 member triage table (worst-first via pre-sorted recwide VALUES)
triage={"id":"triage","kind":"table","name":"Member triage","source":{"elementId":"recwide","kind":"table"},
 "columns":[{"id":"tg-lbl","formula":"[Members/Member]","name":"Member"},
    {"id":"tg-name","formula":"[Members/Name]","name":"Golden name (recommended)"},
    {"id":"tg-mnum","formula":"[Members/Member #]","name":"Member #"},
    {"id":"tg-nrec","formula":"[Members/Source Records]","name":"Source Records","format":NUM0},
    {"id":"tg-nsrc","formula":"[Members/Distinct Sources]","name":"Sources","format":NUM0},
    {"id":"tg-conf","formula":"[Members/Confidence]","name":"Confidence","format":PCT0},
    {"id":"tg-band","formula":'If([Members/Confidence]>=0.85,"High",If([Members/Confidence]>=0.6,"Medium","Low"))',"name":"Band"},
    {"id":"tg-confl","formula":"[Members/Conflicts]","name":"Conflicts","format":NUM0},
    {"id":"tg-need","formula":"[Members/Needs Resolution]","name":"Needs Review"},
    {"id":"tg-mk","formula":"[Members/Member Key]","name":"Member Key"}],
 "conditionalFormats":[
    {"type":"single","columnIds":["tg-conf"],"condition":"<","value":0.6,"style":{"backgroundColor":"#fbe0e6"}},
    {"type":"single","columnIds":["tg-conf"],"condition":"Between","low":0.6,"high":0.85,"style":{"backgroundColor":"#fbeeda"}},
    {"type":"single","columnIds":["tg-conf"],"condition":">","value":0.85,"style":{"backgroundColor":"#dff3ee"}},
    {"type":"single","columnIds":["tg-confl"],"condition":">","value":0,"style":{"backgroundColor":"#fbeeda"}}],
 "name":{"text":"Member triage — most-conflicting members first","fontWeight":"bold","fontSize":14,"color":INK},"style":dict(CARD),
 "order":["tg-lbl","tg-name","tg-mnum","tg-nrec","tg-nsrc","tg-conf","tg-band","tg-confl","tg-need"]}

def page1():
    elems=[records,reclong,recwide]+h1e+kpis1+[ov_c,ov_ic,ov_hd,ov_tx,cbar,bband,triage]
    lay=f"""<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pg1">
{h1l}
{chr(10).join(kpil1)}
  <GridContainer elementId="c-ov" type="grid" gridColumn="1 / 25" gridRow="13 / 17" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(4,1fr)"><LayoutElement elementId="ov-ic" gridColumn="1 / 2" gridRow="1 / 2"/><LayoutElement elementId="ov-hd" gridColumn="2 / 25" gridRow="1 / 2"/><LayoutElement elementId="ov-tx" gridColumn="2 / 25" gridRow="2 / 5"/></GridContainer>
  <LayoutElement elementId="cbar" gridColumn="1 / 14" gridRow="17 / 31"/>
  <LayoutElement elementId="bband" gridColumn="14 / 25" gridRow="17 / 31"/>
  <LayoutElement elementId="triage" gridColumn="1 / 25" gridRow="31 / 48"/>
</Page>"""
    return elems,lay

# ---------- PAGE 2: GOLDEN RECORD REVIEW ----------
h2e,h2l=header("2","Golden Record Review","Human-in-the-loop: compare, edit and approve one golden record per member")
# member summary card for selected member (recwide filtered by picker) — as KPIs
P2K=[("m1","recwide2",ic(IC_LAYERS),"SOURCE RECORDS",f"Sum([MemberSel/Source Records])",NUM0,None,True),
     ("m2","recwide2",ic(IC_ALERT,CORAL),"CONFLICTS",f"Sum([MemberSel/Conflicts])",NUM0,None,True),
     ("m3","recwide2",ic(IC_GAUGE),"CONFIDENCE",f"Avg([MemberSel/Confidence])",PCT0,None,True),
     ("m4","goldn",ic(IC_SHIELD,TEAL),"GOLDEN APPROVED",f"CountDistinct([GoldenBook/Member Key])",NUM0,None,True)]
kpis2=[]; kpil2=[]
for i,(elid,src,icn,t,vf,fmt,cf,gu) in enumerate(P2K):
    e,l=kpi(elid,src,icn,t,vf,fmt,"9 / 16",compf=cf,goodup=gu); kpis2+=e; kpil2.append(l.replace("{col}",f"{1+i*6} / {1+(i+1)*6}"))

# recommended golden card: reclong filtered by picker (attribute | recommended | source | confidence | conflict)
goldgrid=dict(recgrid); goldgrid=json.loads(json.dumps(recgrid))
goldgrid["id"]="goldgrid"; goldgrid["name"]="Golden recommendation"
for c in goldgrid["columns"]:
    c["id"]=c["id"].replace("rg-","gg-")
goldgrid["groupings"]=[{"id":"grp-gattr","groupBy":["gg-ord","gg-attr"],"calculations":[],"sort":[{"columnId":"gg-ord","direction":"ascending"}]}]
goldgrid["conditionalFormats"]=[
    {"type":"single","columnIds":["gg-conf"],"condition":"<","value":0.6,"style":{"backgroundColor":"#fbe0e6"}},
    {"type":"single","columnIds":["gg-conf"],"condition":"Between","low":0.6,"high":0.85,"style":{"backgroundColor":"#fbeeda"}},
    {"type":"single","columnIds":["gg-conf"],"condition":">","value":0.85,"style":{"backgroundColor":"#dff3ee"}},
    {"type":"single","columnIds":["gg-conflict"],"condition":"=","value":"Yes","style":{"backgroundColor":"#fbe0e6"}}]
goldgrid["name"]={"text":"Recommended golden values for the selected member","fontWeight":"bold","fontSize":14,"color":INK}
goldgrid["order"]=["gg-attr","gg-val","gg-src","gg-conf","gg-conflict","gg-cand","gg-dist"]

# evidence on page 2 too
evid2=json.loads(json.dumps(evid)); evid2["id"]="evid2"
for c in evid2["columns"]: c["id"]=c["id"].replace("ev-","e2-")
evid2["name"]={"text":"Source records for the selected member","fontWeight":"bold","fontSize":14,"color":INK}
evid2["order"]=[c.replace("ev-","e2-") for c in evid["order"]]

# approved golden records table
goldtbl={"id":"goldtbl","kind":"table","name":"Approved golden records","source":{"elementId":"goldn","kind":"table"},
 "columns":[{"id":"gt-mk","formula":"[GoldenBook/Member Key]","name":"Member Key"},
            {"id":"gt-name","formula":"[GoldenBook/Golden Name]","name":"Golden Name"},
            {"id":"gt-email","formula":"[GoldenBook/Golden Email]","name":"Golden Email"},
            {"id":"gt-phone","formula":"[GoldenBook/Golden Phone]","name":"Golden Phone"},
            {"id":"gt-grade","formula":"[GoldenBook/Golden Grade]","name":"Grade"},
            {"id":"gt-soc","formula":"[GoldenBook/Golden Society]","name":"Society"},
            {"id":"gt-sec","formula":"[GoldenBook/Golden Section]","name":"Section"},
            {"id":"gt-addr","formula":"[GoldenBook/Golden Address]","name":"Address"},
            {"id":"gt-dec","formula":"[GoldenBook/Decision]","name":"Decision"},
            {"id":"gt-at","formula":"[GoldenBook/Approved At]","name":"Approved At"},
            {"id":"gt-by","formula":"[GoldenBook/Approved By]","name":"Approved By"}],
 "name":{"text":"Golden records written back (grows as you approve)","fontWeight":"bold","fontSize":14,"color":INK},"style":dict(CARD),
 "order":["gt-mk","gt-name","gt-email","gt-phone","gt-grade","gt-soc","gt-sec","gt-addr","gt-dec","gt-at","gt-by"]}

# --- modal controls (text) + seeding ---
def tctrl(cid,name):
    return {"kind":"control","controlId":cid,"id":"ctrl-"+cid,"name":name,"controlType":"text","mode":"equals","case":"insensitive","includeNulls":"when-no-value-is-selected","showOperators":False}
mc_mk=tctrl("g_member","Member")
mc_name=tctrl("g_name","Name"); mc_email=tctrl("g_email","Email"); mc_phone=tctrl("g_phone","Phone")
mc_grade=tctrl("g_grade","Grade"); mc_society=tctrl("g_society","Society"); mc_section=tctrl("g_section","Section"); mc_addr=tctrl("g_address","Address")
mc_decision={"kind":"control","controlId":"g_decision","id":"ctrl-g_decision","name":"Decision","controlType":"segmented","value":"Accepted","source":{"kind":"manual","valueType":"text","values":["Accepted","Edited","Rejected"]}}

def seed(field, wcolname):
    # pull the recommended value for the currently-selected member from recwide
    return {"effect":"set-control-value","control":field,"value":{"type":"formula","formula":f'Text(Lookup([Members/{wcolname}],[memberPick],[Members/Member]))'}}
reviewbtn={"id":"reviewbtn","kind":"button","text":"Review & approve golden record","appearance":"filled","actions":[{"id":"rv","trigger":"on-click","effects":[
    {"effect":"set-control-value","control":"g_member","value":{"type":"formula","formula":"Text(Lookup([Members/Member Key],[memberPick],[Members/Member]))"}},
    seed("g_name","Golden Name"),seed("g_email","Golden Email"),seed("g_phone","Golden Phone"),
    seed("g_grade","Golden Grade"),seed("g_society","Golden Society"),seed("g_section","Golden Section"),seed("g_address","Golden Address"),
    {"effect":"set-control-value","control":"g_decision","value":{"type":"constant","value":{"type":"text","value":"Accepted"}}},
    {"effect":"open-overlay","overlayId":"reviewModal"}]}]}

savebtn={"id":"savebtn","kind":"button","text":"Save golden record","appearance":"filled","actions":[{"id":"sv","trigger":"on-click","effects":[
    {"effect":"insert-rows","table":"golden","values":{
        "g-mk":{"type":"control","control":"g_member"},
        "g-name":{"type":"control","control":"g_name"},
        "g-email":{"type":"control","control":"g_email"},
        "g-phone":{"type":"control","control":"g_phone"},
        "g-grade":{"type":"control","control":"g_grade"},
        "g-society":{"type":"control","control":"g_society"},
        "g-section":{"type":"control","control":"g_section"},
        "g-address":{"type":"control","control":"g_address"},
        "g-decision":{"type":"control","control":"g_decision"}}},
    {"effect":"clear-control","scope":{"type":"control","control":"g_member"}},
    {"effect":"clear-control","scope":{"type":"control","control":"g_name"}},
    {"effect":"clear-control","scope":{"type":"control","control":"g_email"}},
    {"effect":"clear-control","scope":{"type":"control","control":"g_phone"}},
    {"effect":"clear-control","scope":{"type":"control","control":"g_grade"}},
    {"effect":"clear-control","scope":{"type":"control","control":"g_society"}},
    {"effect":"clear-control","scope":{"type":"control","control":"g_section"}},
    {"effect":"clear-control","scope":{"type":"control","control":"g_address"}},
    {"effect":"close-overlay"}]}]}
cancelbtn={"id":"cancelbtn","kind":"button","text":"Cancel","appearance":"outline","actions":[{"id":"cx","trigger":"on-click","effects":[{"effect":"close-overlay"}]}]}
mtitle={"id":"mtitle","kind":"text","body":"### Confirm golden record\nThe fields below are pre-filled with the recommended survivor value for each attribute. Edit any value, set a decision, then **Save** to write the golden record. Leave **Decision = Accepted** to accept the recommendation as-is.","verticalAlign":"middle","style":{"color":INK}}
mnote={"id":"mnote","kind":"text","verticalAlign":"middle","style":{"color":SLATE},"body":"_Writeback appends an immutable row (with your user + timestamp). Re-approving a member appends a new version — the latest row wins._"}
modal={"id":"reviewModal","name":"Review Golden Record","type":"modal",
 "modal":{"width":"medium","header":{"title":"Golden record","showCloseIcon":"hidden"},"footer":{"primaryCta":{"visible":"hidden"},"secondaryCta":{"visible":"hidden"}}},
 "elements":[mtitle,mc_mk,mc_name,mc_email,mc_phone,mc_grade,mc_society,mc_section,mc_addr,mc_decision,mnote,savebtn,cancelbtn]}
modal_lay=('<Page type="grid" gridTemplateColumns="repeat(24,1fr)" gridTemplateRows="auto" id="reviewModal">'
 '<LayoutElement elementId="mtitle" gridColumn="1 / 25" gridRow="1 / 4"/>'
 '<LayoutElement elementId="ctrl-g_member" gridColumn="1 / 13" gridRow="4 / 6"/>'
 '<LayoutElement elementId="ctrl-g_decision" gridColumn="13 / 25" gridRow="4 / 6"/>'
 '<LayoutElement elementId="ctrl-g_name" gridColumn="1 / 13" gridRow="6 / 8"/>'
 '<LayoutElement elementId="ctrl-g_email" gridColumn="13 / 25" gridRow="6 / 8"/>'
 '<LayoutElement elementId="ctrl-g_phone" gridColumn="1 / 13" gridRow="8 / 10"/>'
 '<LayoutElement elementId="ctrl-g_grade" gridColumn="13 / 25" gridRow="8 / 10"/>'
 '<LayoutElement elementId="ctrl-g_society" gridColumn="1 / 13" gridRow="10 / 12"/>'
 '<LayoutElement elementId="ctrl-g_section" gridColumn="13 / 25" gridRow="10 / 12"/>'
 '<LayoutElement elementId="ctrl-g_address" gridColumn="1 / 25" gridRow="12 / 14"/>'
 '<LayoutElement elementId="mnote" gridColumn="1 / 25" gridRow="14 / 16"/>'
 '<LayoutElement elementId="cancelbtn" gridColumn="13 / 19" gridRow="16 / 18"/>'
 '<LayoutElement elementId="savebtn" gridColumn="19 / 25" gridRow="16 / 18"/>'
 '</Page>')

picker2={"kind":"control","controlId":"memberPick","id":"ctrl-pick2"}  # placeholder not used; picker declared on page1

instr2_c={"id":"c-in2","kind":"container","style":dict(TINT)}
instr2_ic={"id":"in2-ic","kind":"image","source":{"kind":"url","url":ic(IC_CHECK,IEEE)},"style":{"fit":"contain"}}
instr2_hd={"id":"in2-hd","kind":"text","body":"**Review workflow**","verticalAlign":"middle","style":{"color":INK}}
instr2={"id":"in2-tx","kind":"text","verticalAlign":"middle","style":{"color":"#2b3b45"},
 "body":"**1** Pick a member with the **Member** selector.  **2** Compare the **source records** (left) against the **recommended golden values** (right) — confidence is shaded green/amber/red, conflicts flagged.  **3** Click **Review & approve** — the form pre-fills with the recommended survivor per field.  **4** Edit anything, set a **Decision**, and **Save** to write the golden record. The Approved table below grows with each save."}
tbcard={"id":"c-tb2","kind":"container","style":dict(GCARD)}

gold_hd={"id":"gold-hd","kind":"text","body":"**Golden records — writeback input table**  ·  each Save appends an immutable, timestamped row","verticalAlign":"middle","style":{"color":INK}}
def page2():
    # picker control (memberPick) is DECLARED here and placed in this page's toolbar
    elems=[tbcard,picker,recwide2,goldn,golden]+h2e+kpis2+[instr2_c,instr2_ic,instr2_hd,instr2,goldgrid,evid2,gold_hd,reviewbtn]
    lay=f"""<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pg2">
{h2l}
  <GridContainer elementId="c-tb2" type="grid" gridColumn="1 / 25" gridRow="6 / 9" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <LayoutElement elementId="ctrl-pick" gridColumn="1 / 15" gridRow="1 / 3"/>
    <LayoutElement elementId="reviewbtn" gridColumn="15 / 25" gridRow="1 / 3"/>
  </GridContainer>
{chr(10).join(kpil2)}
  <GridContainer elementId="c-in2" type="grid" gridColumn="1 / 25" gridRow="16 / 20" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(4,1fr)"><LayoutElement elementId="in2-ic" gridColumn="1 / 2" gridRow="1 / 2"/><LayoutElement elementId="in2-hd" gridColumn="2 / 25" gridRow="1 / 2"/><LayoutElement elementId="in2-tx" gridColumn="2 / 25" gridRow="2 / 5"/></GridContainer>
  <LayoutElement elementId="evid2" gridColumn="1 / 13" gridRow="20 / 35"/>
  <LayoutElement elementId="goldgrid" gridColumn="13 / 25" gridRow="20 / 35"/>
  <LayoutElement elementId="gold-hd" gridColumn="1 / 25" gridRow="35 / 37"/>
  <LayoutElement elementId="golden" gridColumn="1 / 25" gridRow="37 / 51"/>
</Page>"""
    return elems,lay

# ================= THEME + BUILD =================
theme={"colors":{"text":INK,"highlight":IEEE,"success":TEAL,"warning":AMBER,"danger":CORAL,"darkMode":"hidden"},
 "colorOverrides":{"backgroundCanvas":"#FFFFFF","canvasBackground":"#eef3f7"},
 "categoricalScheme":[IEEE,TEAL,AMBER,CORAL,NAVY,SLATE,"#7a5ea8","#3e7c7b"],
 "fonts":{"textFont":"Inter","dataFont":"Inter"},"pageWidth":"large","tableStyles":{"preset":"presentation","cellSpacing":"small"}}

def build():
    p1e,p1l=page1(); p2e,p2l=page2()
    doc={"schemaVersion":1,"kind":"workbook",
       "pages":[{"id":"pg1","name":"Command Center","elements":p1e},
                {"id":"pg2","name":"Golden Record Review","elements":p2e},modal],
       "layout":'<?xml version="1.0" encoding="utf-8"?>\n'+p1l+p2l+modal_lay,"themeOverrides":theme}
    return {"name":"IEEE Entity Resolution","folderId":FOLDER,"document":doc}

def qa(s):
    def _walk(o):
        if isinstance(o,dict):
            for v in o.values(): yield from _walk(v)
        elif isinstance(o,list):
            for v in o: yield from _walk(v)
        elif isinstance(o,str): yield o
    bad=0
    for x in _walk(s):
        if x.startswith("data:image/svg+xml;base64,"):
            try: _MD.parseString(base64.b64decode(x.split(",",1)[1]))
            except Exception as e: bad+=1; print("INVALID SVG:",str(e)[:160])
    return bad

def post(s):
    r=urllib.request.Request(BASE+"/v2/workbooks/spec",data=json.dumps(s).encode(),headers=H,method="POST")
    resp=urllib.request.urlopen(r,timeout=180).read().decode()
    wid=None
    try: wid=json.loads(resp).get("workbookId")
    except Exception:
        for l in resp.splitlines():
            if "workbookId" in l: wid=l.split()[-1].strip()
    url=None
    if wid:
        meta=json.loads(urllib.request.urlopen(urllib.request.Request(BASE+f"/v2/workbooks/{wid}",headers=H),timeout=30).read().decode())
        url=meta.get("url")
    return bool(wid), url, resp, wid

if __name__=="__main__":
    spec=build()
    # write spec for inspection/validation
    open("spec.json","w").write(json.dumps(spec,indent=1))
    open("doc.json","w").write(json.dumps(spec["document"],indent=1))  # validate-spec.py checks pages/layout here
    print(f"members={len(rec_wide)} records={len(raw)} reclong_rows={len(rl_rows)}  spec_bytes={len(json.dumps(spec))}")
    if qa(spec): print("ABORT malformed SVG"); sys.exit(1)
    if os.environ.get("POST","1")=="1":
        try:
            ok,url,resp,wid=post(spec); print("POST:","ACCEPTED" if ok else "REJECTED"); print("workbookId:",wid); print("URL:",url)
            if not ok: print(resp[:600])
        except urllib.error.HTTPError as e:
            raw_e=e.read().decode()
            try: msg=json.loads(raw_e).get("message","")
            except Exception: msg=raw_e
            print(f"FAILED {e.code}: {msg[:400]}")
