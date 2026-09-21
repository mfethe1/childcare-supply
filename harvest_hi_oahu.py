#!/usr/bin/env python3
"""Harvest Oahu (AG) by district to bypass the 100-provider result cap, with details."""
import urllib.request, json, ssl, subprocess, time, re

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

SEARCH_URL = ("https://prod-06.usgovtexas.logic.azure.us:443/workflows/179f51f14f6a4837b49e82a3099bc3c3"
              "/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=V2SJOS2DthZkevCZtKQR-6GAHNVv1p57XZKIYJKewYo")

DISTRICTS = ["AGAX", "AGAY", "AGAZ", "AGBA", "AGBB", "AGBD", "AGBE"]


def search(area):
    BODY = {"ProviderName": "", "ZipCode": "", "ZipCodePlusFour": "", "Areas": area,
            "Type": {"Center": "true", "Center1": "true", "Center2": "true", "Center3": "true",
                     "Home": "true", "Home1": "true", "Home2": "true"},
            "Ages": {"InfantandToddler": "false", "Preschool": "false", "School-aged": "false"},
            "Others": {"Accredited": "false", "WeekendCare": "false",
                       "MealsProvided": "false", "SnacksProvided": "false"}}
    req = urllib.request.Request(SEARCH_URL, data=json.dumps(BODY).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, context=CTX, timeout=45) as r:
        return json.load(r)["hanaResponse"]["results"] or []


def parse_detail(html):
    m = re.search(r"const response = `", html)
    if not m:
        return None
    start = m.end()
    depth = 0
    i = start
    instr = False
    esc = False
    while i < len(html):
        ch = html[i]
        if instr:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
        else:
            if ch == '"':
                instr = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        i += 1
    return None


def main():
    d = json.load(open("data/hi.json"))
    have = {r["service"]["serviceId"] for r in d}
    missing = []
    seen = set()
    for code in DISTRICTS:
        for p in search(code):
            for s in p.get("services", []):
                sid = s.get("serviceId")
                if sid in seen:
                    continue
                seen.add(sid)
                if sid not in have:
                    s["_providerName"] = p.get("name")
                    s["_providerId"] = p.get("providerId")
                    s["_providerType"] = p.get("providerType")
                    missing.append(s)
        time.sleep(0.5)
    print(f"AG district universe: {len(seen)} | new: {len(missing)}", flush=True)
    for i, s in enumerate(missing):
        try:
            html = subprocess.run(
                ["curl", "-sk", "--max-time", "40",
                 f"https://childcareprovidersearch.dhs.hawaii.gov/details/?serviceId={s['serviceId']}"],
                capture_output=True).stdout.decode("utf-8", "replace")
            raw = parse_detail(html)
            d.append({"service": s,
                      "detail": {"summary": (raw or {}).get("summary", {}).get("hanaResponse", {}),
                                 "details": (raw or {}).get("details", {}).get("hanaResponse", {})} if raw else None})
        except Exception:
            d.append({"service": s, "detail": None})
        if (i + 1) % 25 == 0:
            json.dump(d, open("data/hi.json", "w"))
            print(f"  {i + 1}/{len(missing)}", flush=True)
        time.sleep(0.3)
    json.dump(d, open("data/hi.json", "w"))
    from collections import Counter
    print("final:", len(d), dict(Counter(str(r["service"].get("area", ""))[:2] for r in d)))


if __name__ == "__main__":
    main()
