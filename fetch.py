"""Выгрузка адресов г. Тюмени из OpenStreetMap (Overpass) с привязкой к административному округу."""
import json, time, urllib.request, urllib.parse, sys
EPS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
def q(s):
    for n in range(6):
        for ep in EPS:
            try:
                d = urllib.parse.urlencode({"data": s}).encode()
                r = urllib.request.urlopen(urllib.request.Request(ep, d, {"User-Agent": "spravochnik-nmp-addr/1.0"}), timeout=400)
                return json.load(r)
            except Exception as e:
                print("fail", ep, e, file=sys.stderr); time.sleep(10)
    raise SystemExit("overpass unavailable")
out = {}
BB = "56.95,65.25,57.35,65.85"
b = q(f'[out:json][timeout:300];rel["boundary"="administrative"]({BB});out tags;')
rels = [{"id": e["id"], "name": e["tags"].get("name"), "lvl": e["tags"].get("admin_level")} for e in b["elements"]]
out["boundaries"] = rels
for r in rels: print("REL", r)
ao = [r for r in rels if r["name"] and "административный округ" in r["name"].lower()]
out["addr"] = {}
for r in ao:
    d = q(f'[out:json][timeout:900];area({3600000000 + r["id"]})->.a;nwr(area.a)["addr:housenumber"];out tags center;')
    rows = []
    for e in d["elements"]:
        t = e.get("tags", {}); c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        rows.append([t.get("addr:street") or t.get("addr:place") or "", t.get("addr:housenumber"), t.get("addr:city") or "", t.get("addr:suburb") or "",
                     round(c["lat"], 5) if c.get("lat") else None, round(c["lon"], 5) if c.get("lon") else None])
    out["addr"][r["name"]] = rows
    print(r["name"], len(rows))
if not ao:  # запасной вариант: все адреса в рамке, округ определим позже по координатам/границам
    d = q(f'[out:json][timeout:900];nwr["addr:housenumber"]({BB});out tags center;')
    out["all"] = [[e.get("tags", {}).get("addr:street") or e.get("tags", {}).get("addr:place") or "", e["tags"].get("addr:housenumber"), e["tags"].get("addr:city") or "",
                   round((e.get("center") or e)["lat"], 5), round((e.get("center") or e)["lon"], 5)] for e in d["elements"]]
    print("all", len(out["all"]))
g = q(f'[out:json][timeout:300];(way["highway"]["name"~"Мельникайте|Закалужская|Окружн"]({BB});way["railway"="rail"]["usage"="main"]({BB}););out tags geom;')
out["roads"] = [{"name": e["tags"].get("name"), "rw": e["tags"].get("railway"), "g": [[round(p["lat"], 5), round(p["lon"], 5)] for p in e.get("geometry", [])]} for e in g["elements"]]
print("roads", len(out["roads"]))
# геометрия границ округов (для определения по координатам)
if ao:
    gg = q('[out:json][timeout:300];(' + ''.join(f'rel({r["id"]});' for r in ao) + ');out geom;')
    out["geom"] = [{"name": e["tags"].get("name"), "m": [{"role": m.get("role"), "g": [[round(p["lat"], 5), round(p["lon"], 5)] for p in m.get("geometry", [])]} for m in e.get("members", []) if m.get("type") == "way"]} for e in gg["elements"]]
json.dump(out, open("tmn_addr.json", "w"), ensure_ascii=False)
