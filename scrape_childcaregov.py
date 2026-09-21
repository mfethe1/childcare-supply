#!/usr/bin/env python3
"""Scrape childcare.gov state-resource pages -> find each state's official provider
search/registry URL. Output: state_registries.json"""
import json, re, ssl, sys, time, urllib.parse, urllib.request

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "cc/0.1 (open-data research)"}

STATES = ["alabama","alaska","arizona","arkansas","colorado","connecticut","florida",
    "georgia","hawaii","idaho","illinois","indiana","iowa","kansas","kentucky",
    "louisiana","maine","maryland","massachusetts","michigan","minnesota","mississippi",
    "missouri","montana","nebraska","nevada","new-hampshire","new-jersey","new-mexico",
    "north-carolina","north-dakota","ohio","oklahoma","oregon","pennsylvania","rhode-island",
    "south-carolina","south-dakota","tennessee","texas","utah","vermont","virginia",
    "washington","west-virginia","wisconsin","wyoming","district-of-columbia"]

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30, context=ctx).read().decode("utf-8", "replace")

def main():
    out = {}
    for st in STATES:
        url = f"https://childcare.gov/state-resources/{st}"
        try:
            html = fetch(url)
        except Exception as e:
            out[st] = {"error": str(e)[:100]}
            continue
        links = re.findall(r'href="(https?://[^"]+)"', html)
        # score links: prefer ones that look like official state provider searches
        scored = []
        for l in set(links):
            low = l.lower()
            if any(d in low for d in [".gov", ".us", ".org", ".edu"]) and \
               any(k in low for k in ["childcare", "child-care", "child_care", "daycare",
                                      "day-care", "provider", "licens", "facilities"]):
                scored.append(l)
        out[st] = {"registry_urls": sorted(scored)[:8]}
        print(st, len(scored))
        time.sleep(0.4)
    json.dump(out, open("state_registries.json", "w"), indent=1)
    print("states scraped:", len(out))

if __name__ == "__main__":
    main()
