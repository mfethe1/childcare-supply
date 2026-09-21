#!/usr/bin/env python3
"""Fetch Hawaii licensed childcare providers.

Two-step: (1) PowerAutomate search endpoint per island area code -> provider/service list;
(2) details page per serviceId embeds a server-rendered JSON with capacity/address/license.
"""
import json, os, re, ssl, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "hi.json")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

SEARCH_URL = ("https://prod-06.usgovtexas.logic.azure.us:443/workflows/179f51f14f6a4837b49e82a3099bc3c3"
              "/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=V2SJOS2DthZkevCZtKQR-6GAHNVv1p57XZKIYJKewYo")
DETAIL_URL = "https://childcareprovidersearch.dhs.hawaii.gov/details/?serviceId={}"

# island top-level area codes (children of 'AA' = State of Hawaii)
AREAS = ["AB", "AC", "AD", "AE", "AF", "AG"]

SEARCH_BODY = {
    "ProviderName": "", "ZipCode": "", "Areas": "",
    "Type": {"Center": "true", "Center1": "true", "Center2": "true", "Center3": "true",
             "Home": "true", "Home1": "true", "Home2": "true"},
    "Ages": {"InfantandToddler": "false", "Preschool": "false", "School-aged": "false"},
    "Others": {"Accredited": "false", "WeekendCare": "false", "MealsProvided": "false",
               "SnacksProvided": "false"},
}


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, context=CTX, timeout=90) as r:
        return json.load(r)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 childcare-supply/0.2"})
    with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def fetch_services():
    services = []
    for area in AREAS:
        body = dict(SEARCH_BODY)
        body["Areas"] = area
        d = post(SEARCH_URL, body)
        res = d.get("hanaResponse", {}).get("results") or []
        print(f"area {area}: {len(res)} providers")
        for p in res:
            for s in p.get("services", []):
                s["_providerName"] = p.get("name")
                s["_providerId"] = p.get("providerId")
                s["_providerType"] = p.get("providerType")
                services.append(s)
        time.sleep(1.0)
    return services


def parse_detail(html):
    # server-embedded: const response = `{...}`;
    m = re.search(r"const response = `(\{.*?\})`;", html, re.S)
    if not m:
        return None
    try:
        raw = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    out = {"summary": raw.get("summary", {}).get("hanaResponse", {}),
           "details": raw.get("details", {}).get("hanaResponse", {}),
           "history": (raw.get("history", {}) or {}).get("hanaResponse", {})}
    return out


def main():
    services = fetch_services()
    print(f"total services: {len(services)}")
    out = []
    for i, s in enumerate(services):
        try:
            html = get(DETAIL_URL.format(s["serviceId"]))
            d = parse_detail(html)
        except Exception as e:
            print(f"  {s['serviceId']} FAIL {e}")
            d = None
        rec = {"service": s, "detail": d}
        out.append(rec)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(services)} details fetched")
        time.sleep(0.4)
    with open(OUT, "w") as f:
        json.dump(out, f)
    n_cap = sum(1 for r in out if r["detail"] and r["detail"]["summary"].get("capacity") is not None)
    print(f"wrote {len(out)} records to {OUT}; {n_cap} with capacity")


if __name__ == "__main__":
    main()
