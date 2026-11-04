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
b = q('[out:json][timeout:300];area["name"="Тюмень"]["boundary"="administrative"]->.c;'
      'rel(area.c)["boundary"="administrative"];out tags;')
rels = [{"id": e["id"], "name": e["tags"].get("name"), "lvl": e["tags"].get("admin_level")} for e in b["elements"]]
out["boundaries"] = rels
print(json.dumps(rels, ensure_ascii=False))
ao = [r for r in rels if r["name"] and "административный округ" in r["name"]]
out["addr"] = {}
for r in ao:
    d = q(f'[out:json][timeout:600];area({3600000000 + r["id"]})->.a;nwr(area.a)["addr:housenumber"];out tags center;')
    rows = []
    for e in d["elements"]:
        t = e.get("tags", {}); c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        rows.append([t.get("addr:street") or t.get("addr:place") or "", t.get("addr:housenumber"), t.get("addr:city") or "", t.get("addr:suburb") or "",
                     round(c["lat"], 5) if c.get("lat") else None, round(c["lon"], 5) if c.get("lon") else None])
    out["addr"][r["name"]] = rows
    print(r["name"], len(rows))
# дороги — границы зоны ПСО № 4 (Транссиб, Мельникайте, Закалужская, Окружная)
g = q('[out:json][timeout:300];area["name"="Тюмень"]["boundary"="administrative"]["admin_level"="6"]->.c;'
      '(way(area.c)["highway"]["name"~"Мельникайте|Закалужская"];way(area.c)["railway"="rail"]["usage"="main"];way(area.c)["highway"]["name"~"Окружн"];);out tags geom;')
out["roads"] = [{"name": e["tags"].get("name"), "rw": e["tags"].get("railway"), "g": [[round(p["lat"], 5), round(p["lon"], 5)] for p in e.get("geometry", [])]} for e in g["elements"]]
print("roads", len(out["roads"]))
json.dump(out, open("tmn_addr.json", "w"), ensure_ascii=False)
