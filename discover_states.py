#!/usr/bin/env python3
"""Discover childcare provider datasets across state open-data portals.

Strategy:
 1. Socrata discovery catalog: query each known state portal domain for
    "child care" datasets, filter to likely provider registries.
 2. ArcGIS Hub catalog: same via opendata.arcgis.com/api/v3.
Output: candidates.json (unverified URLs for manual curl verification).
"""
import json, time, urllib.parse, urllib.request

UA = {"User-Agent": "childcare-supply/0.1 (open-data research)"}

SODOMAINS = [
    "data.alaska.gov", "data.az.gov", "opendata.utah.gov", "data.iowa.gov",
    "data.opi.mt.gov", "opendata.maryland.gov", "data.pa.gov", "data.wa.gov",
    "data.oregon.gov", "data.nh.gov", "data.nj.gov", "data.rm.ks.gov",
    "data.mo.gov", "opendata.nc.gov", "data.illinois.gov", "data.michigan.gov",
    "data.ohio.gov", "data.tn.gov", "data.wv.gov", "data.nebraska.gov",
    "data.hawaii.gov", "data.colorado.gov", "data.ct.gov", "data.ri.gov",
    "data.sc.gov", "data.ok.gov", "data.nd.gov", "data.vermont.gov",
    "data.usa.gov", "demo-data.socrata.com",
]

def q(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return {"error": str(e)[:120]}

def socrata(domain):
    p = urllib.parse.urlencode({"domains": domain, "q": "child care",
                                "limit": 10})
    d = q(f"https://api.us.socrata.com/api/catalog/v1?{p}")
    out = []
    for r in d.get("results", []):
        res = r.get("resource", {})
        name = res.get("name", "")
        if any(k in name.lower() for k in ["child care", "childcare", "day care", "daycare",
                                           "early care", "child development", "ccrc"]):
            out.append({"domain": domain, "id": res.get("id"),
                        "name": name,
                        "endpoint": f"https://{domain}/resource/{res.get('id')}.json?$limit=3",
                        "desc": (res.get("description") or "")[:150]})
    return out

def arcgis():
    hits = []
    for term in ["child care providers licensed", "licensed child care facilities"]:
        p = urllib.parse.urlencode({"q": term, "page[size]": 30})
        d = q(f"https://opendata.arcgis.com/api/v3/datasets?{p}")
        for r in d.get("data", []):
            a = r.get("attributes", {})
            org = (a.get("orgName") or "")
            if any(s in org for s in ["State", "Department", "Health", "Human Services", "DHS", "DCYF"]):
                hits.append({"org": org, "name": a.get("name"),
                             "endpoint": (a.get("layerUrl") or a.get("url")) or
                                         (r.get("relationships", {}) or {}).get("self", ""),
                             "desc": ""})
        time.sleep(1)
    return hits

def main():
    cand = {"socrata": [], "arcgis": []}
    for dom in SODOMAINS:
        r = socrata(dom)
        if r:
            cand["socrata"].extend(r)
        print(f"{dom}: {len(r)}")
        time.sleep(0.6)
    cand["arcgis"] = arcgis()
    with open("candidates.json", "w") as f:
        json.dump(cand, f, indent=1)
    print("socrata candidates:", len(cand["socrata"]),
          "arcgis candidates:", len(cand["arcgis"]))

if __name__ == "__main__":
    main()
