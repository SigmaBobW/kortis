# Entity-resolution data prep: cluster raw records into members, compute
# survivorship recommendations + confidence. Pure/deterministic (no RNG).
import csv, collections, re, os

HERE=os.path.dirname(os.path.abspath(__file__))

AUTH=["IEEE Membership DB","Society Directory","Local Section Roster",
      "IEEE Conference Registration","IEEE Xplore Access"]
def auth_rank(sys): return AUTH.index(sys)+1 if sys in AUTH else 9

ATTRS=[("name","Name"),("email","Email"),("phone","Phone"),
       ("member_grade","Member Grade"),("society","Society"),
       ("section","Section"),("address","Address")]
TOKENS={"name":{"name_exact","name_fuzzy"},
        "email":{"email_exact","email_domain_fuzzy"},
        "phone":{"phone_exact"},"address":{"address_fuzzy"},
        "society":{"society_exact"}}

def norm(attr,v):
    v=(v or "").strip()
    if not v: return ""
    if attr=="phone":
        d=re.sub(r"\D","",v); return d[-10:] if len(d)>=10 else d
    if attr=="email": return v.lower()
    if attr=="name":
        s=v.lower()
        if "," in s:  # "Davis, William" -> "william davis"
            a,b=[x.strip() for x in s.split(",",1)]; s=b+" "+a
        return re.sub(r"[^a-z ]","",s).strip()
    return re.sub(r"\s+"," ",v.lower()).strip()

def load(threshold=0.70):
    raw=list(csv.DictReader(open(os.path.join(HERE,"raw_source_records.csv"))))
    pairs=list(csv.DictReader(open(os.path.join(HERE,"pairwise_match_scores.csv"))))
    byid={r['record_id']:r for r in raw}
    parent={r['record_id']:r['record_id'] for r in raw}
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb: parent[ra]=rb
    by_mn=collections.defaultdict(list)
    for r in raw:
        if r['member_number']: by_mn[r['member_number']].append(r['record_id'])
    for ids in by_mn.values():
        for i in ids[1:]: union(ids[0],i)
    cl_pairs=collections.defaultdict(list)  # cluster edges for corroboration
    for p in pairs:
        a,b=p['record_id_a'],p['record_id_b']
        if a in parent and b in parent and float(p['match_score'])>=threshold:
            union(a,b)
    # cluster members
    clusters=collections.defaultdict(list)
    for rid in parent: clusters[find(rid)].append(rid)
    # stable member key: sort clusters by min record_id, number M0001..
    ordered=sorted(clusters.values(), key=lambda v:min(v))
    member_key={}; members=[]
    for i,v in enumerate(ordered,1):
        mk=f"M{i:04d}"
        for rid in v: member_key[rid]=mk
        members.append((mk,sorted(v)))
    # within-cluster matched-field tokens + scores
    cl_tokens=collections.defaultdict(set); cl_scores=collections.defaultdict(list)
    for p in pairs:
        a,b=p['record_id_a'],p['record_id_b']
        if a in member_key and b in member_key and member_key[a]==member_key[b]:
            mk=member_key[a]
            cl_tokens[mk]|=set(p['matched_fields'].split("|"))
            cl_scores[mk].append(float(p['match_score']))
    return raw,pairs,byid,member_key,members,cl_tokens,cl_scores

def recommend_attr(recs, attr, tokens):
    """recs: list of raw dicts in the cluster. returns dict or None."""
    cands=[r for r in recs if (r.get(attr) or "").strip()]
    if not cands: return None
    # choose survivor: best authority, then newest date, then record_id
    def keyf(r): return (auth_rank(r['source_system']),
                         "" if not r['record_created_date'] else r['record_created_date'],
                         r['record_id'])
    # min authority rank, max date
    best=sorted(cands,key=lambda r:(auth_rank(r['source_system']),
              # newest first: invert date by using negative sort via reverse tuple
              ), )
    # sort: authority asc, then date desc, then id
    best=sorted(cands,key=lambda r:(auth_rank(r['source_system']),
                                    _date_key(r['record_created_date']),
                                    r['record_id']))
    winner=best[0]
    val=winner[attr].strip()
    nval=norm(attr,val)
    vals=[norm(attr,r[attr]) for r in cands]
    distinct=sorted(set(vals))
    agreement=vals.count(nval)/len(vals)
    corrob=1.0 if (attr in TOKENS and tokens & TOKENS[attr]) else 0.0
    aw=(6-auth_rank(winner['source_system']))/5.0
    conf=round(0.5*agreement+0.3*aw+0.2*corrob,2)
    conf=max(0.0,min(1.0,conf))
    return {"value":val,"source_system":winner['source_system'],
            "source_record":winner['record_id'],"confidence":conf,
            "conflict": len(distinct)>1,"n_candidates":len(cands),
            "n_distinct":len(distinct)}

def _date_key(d):
    # newest date should sort FIRST -> return negative-ish string via inverse
    # simplest: return a string that sorts DESC by negating year via 9999-comp
    if not d: return "0000"
    y,m,dd=d.split("-")
    inv="".join(str(9-int(c)) if c.isdigit() else c for c in f"{y}{m}{dd}")
    return inv

def build():
    raw,pairs,byid,member_key,members,cl_tokens,cl_scores=load()
    for r in raw: r['member_key']=member_key[r['record_id']]
    rec_long=[]; rec_wide=[]
    for mk,ids in members:
        recs=[byid[i] for i in ids]
        wide={"member_key":mk,"n_records":len(ids),
              "n_sources":len({r['source_system'] for r in recs}),
              "avg_score": round(sum(cl_scores[mk])/len(cl_scores[mk]),2) if cl_scores[mk] else None,
              "member_number": next((r['member_number'] for r in sorted(recs,key=lambda r:auth_rank(r['source_system'])) if r['member_number']),"")}
        confs=[]; conflicts=0
        for attr,label in ATTRS:
            rec=recommend_attr(recs,attr,cl_tokens[mk])
            if rec is None:
                wide[attr]=""; wide[attr+"_src"]=""; wide[attr+"_conf"]=None; wide[attr+"_conflict"]=False
                rec_long.append({"member_key":mk,"attr":attr,"label":label,"value":"",
                    "source_system":"","source_record":"","confidence":None,
                    "conflict":False,"n_candidates":0,"n_distinct":0})
                continue
            wide[attr]=rec["value"]; wide[attr+"_src"]=rec["source_system"]
            wide[attr+"_conf"]=rec["confidence"]; wide[attr+"_conflict"]=rec["conflict"]
            confs.append(rec["confidence"]); conflicts+=1 if rec["conflict"] else 0
            rec_long.append({"member_key":mk,"attr":attr,"label":label,**rec})
        wide["overall_conf"]=round(sum(confs)/len(confs),2) if confs else None
        wide["conflict_count"]=conflicts
        wide["needs_resolution"]= len(ids)>1
        wide["display_name"]=wide["name"]
        rec_wide.append(wide)
    return raw,pairs,rec_long,rec_wide,members

if __name__=="__main__":
    raw,pairs,rec_long,rec_wide,members=build()
    print("members:",len(rec_wide),"records:",len(raw),"rec_long rows:",len(rec_long))
    need=[w for w in rec_wide if w["needs_resolution"]]
    print("need resolution:",len(need))
    import statistics
    print("avg overall_conf (need):",round(statistics.mean(w["overall_conf"] for w in need if w["overall_conf"]),3))
    print("total conflicts to review:",sum(w["conflict_count"] for w in rec_wide))
    print("records collapsed (raw-members):",len(raw)-len(rec_wide))
    # show a multi-record member with conflicts
    ex=sorted(need,key=lambda w:-w["conflict_count"])[0]
    print("\n=== example member",ex["member_key"],"records",ex["n_records"],"sources",ex["n_sources"],"conflicts",ex["conflict_count"],"===")
    for r in raw:
        if r['member_key']==ex['member_key']:
            print(" ",r['record_id'],r['source_system'],"|",r['name'],"|",r['email'],"|",r['phone'],"|",r['member_grade'],"|",r['section'])
    print("  --- recommendations ---")
    for rl in rec_long:
        if rl['member_key']==ex['member_key']:
            print(f"   {rl['label']:14} -> {str(rl['value'])[:40]:40} src={rl['source_system'][:22]:22} conf={rl['confidence']} conflict={rl['conflict']} ({rl['n_distinct']} distinct)")
