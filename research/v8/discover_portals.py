"""Source discovery, step 4: the non-GIS-server leads. Reachability, what each page offers (links to data, APIs, logins, captchas, terms), and whether HMDA's plan files carry georeferencing.
Only page text and small byte ranges of files are read (sample bytes go to the scratch folder passed as argv[1] and are not kept).   .venv/Scripts/python research/v8/discover_portals.py <scratch dir>"""
import requests, re, sys, time, html, zlib
from pathlib import Path
H = {"User-Agent": "Mozilla/5.0 SETU-sideproject/0.1"}
S = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
def page(u, n=250000):
    try:
        r = requests.get(u, headers=H, timeout=40, allow_redirects=True); return r.status_code, r.url, r.text[:n], r.headers.get("content-type", "")
    except Exception as e: return 0, u, str(e)[:80], ""
def text(h): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", h, flags=re.S)))
def links(h, rx): return sorted({m for m in re.findall(r'href=["\']([^"\']+)["\']', h) if re.search(rx, m, re.I)})[:12]
LEADS = {
 "HMDA lakes portal": ("https://lakes.hmda.gov.in/", r"api|geojson|kml|shp|json|download|ftl"),
 "HYDRAA asset protection": ("https://hydraa.telangana.gov.in/functions/asset-protection", r"ftl|lake|pdf|map|gis|list|notif"),
 "TGRAC water datasets": ("https://tgrac.telangana.gov.in/trac/water-datasets.php", r"download|zip|shp|kml|geojson|csv|pdf|dataset|api"),
 "TGRAC WebGIS": ("https://tgrac.telangana.gov.in/trac/webgis.php", r"arcgis|rest|wms|wfs|api|download|geojson"),
 "Bhu Bharati know land status": ("https://www.bhubharati.telangana.gov.in/knowLandStatus", r"captcha|login|otp|api|search"),
 "Bhuvan Telangana water resources (TWRIS)": ("https://bhuvan-app1.nrsc.gov.in/twris/geoportal/twris.php", r"wms|wfs|download|api|login|register"),
 "NRSC NDEM disaster documents": ("https://ndem.nrsc.gov.in/", r"disaster|flood|document|map|pdf|api|download"),
 "CPCB AQI portal": ("https://airquality.cpcb.gov.in/AQI_India/", r"api|download|csv|data|station|login"),
 "OGD India AQI catalogue": ("https://www.data.gov.in/catalog/real-time-air-quality-index", r"api|resource|key|licen|csv|json"),
 "India-WRIS": ("https://nwic.in/wris/", r"api|download|wms|data|groundwater|login"),
 "CGWB groundwater monitoring": ("https://cgwb.gov.in/en/ground-water-level-monitoring", r"csv|xls|pdf|download|data|api|dwlr"),
 "Telangana fire services station list": ("https://tgfireuat.cgg.gov.in/WebSite/knowurfstn.aspx", r"station|aspx|list|district"),
}
for name, (u, rx) in LEADS.items():
    c, fu, h, ct = page(u); t = text(h) if "html" in ct or c == 200 else h
    lic = re.findall(r"(licen[cs]e[^.]{0,90}|terms (?:of use|and conditions)[^.]{0,60}|open government data licen[^.]{0,60}|captcha|one[- ]time password|otp)", t, re.I)[:3]
    print(f"\n## {name}\n   {u}\n   -> {c} {'(redirected to ' + fu + ')' if fu.rstrip('/') != u.rstrip('/') else ''} {ct[:30]}  {len(h)//1000} KB text")
    if c == 200:
        print("   title:", (re.findall(r"<title[^>]*>(.*?)</title>", h, re.S | re.I) or [''])[0].strip()[:90])
        print("   data/api-ish links:", links(h, rx)[:8]); print("   licence/captcha/login hints:", [x[:80] for x in lic])
# NDEM: is there an index of Telangana flood maps? Try the documented path pattern
print("\n## NRSC NDEM flood map pattern")
ex = "https://ndem.nrsc.gov.in/documents/Disaster_Document/2024/TS/tsflood50dsc01092024_0600hrs/tsflood50dsc01092024_0600hrs_map.pdf"
r = requests.head(ex, headers=H, timeout=30, allow_redirects=True); print("   example map:", r.status_code, r.headers.get("content-length"), r.headers.get("last-modified"), r.headers.get("content-type"))
for y in (2020, 2021, 2023, 2024, 2025):
    r = requests.get(f"https://ndem.nrsc.gov.in/documents/Disaster_Document/{y}/TS/", headers=H, timeout=30); print(f"   directory {y}/TS/ ->", r.status_code, len(r.text), "| listing:" , re.findall(r'href="([^"?][^"]*)"', r.text)[:4])
# HMDA plan files: georeferenced? (JPEG header/EXIF + sidecar world files; PDF GeoPDF markers) — small byte ranges only
print("\n## HMDA plan files: georeferencing")
jpg = "https://masterplan.hmda.gov.in/Masterplan2031/Content/SHAMSHABAD.jpg"
r = requests.get(jpg, headers={**H, "Range": "bytes=0-65535"}, timeout=40); b = r.content
print("   SHAMSHABAD.jpg first 64 KB:", r.status_code, len(b), "bytes; starts", b[:4].hex(), "| EXIF GPS tag present:", b"GPS" in b, "| GeoTIFF/XMP geo tags:", bool(re.search(rb"ModelTiepoint|GeoKey|geotiff|xmp.*lat", b, re.I)))
m = re.search(rb"\xff[\xc0\xc2]\x00..(.)(..)(..)", b, re.S)
if m: print("   JPEG dimensions (h x w):", int.from_bytes(m.group(2), "big"), "x", int.from_bytes(m.group(3), "big"))
for ext in ("jgw", "jpgw", "wld", "xml", "aux.xml", "prj"):
    r = requests.head(jpg.replace(".jpg", "." + ext), headers=H, timeout=20); print(f"   sidecar .{ext}:", r.status_code)
pdf = "https://www.hmda.gov.in/wp-content/uploads/2022/06/GHMC_Circle_No-IV(Old_Circle_No-I).pdf"
hdr = requests.get(pdf, headers={**H, "Range": "bytes=0-3000000"}, timeout=90).content
tail = requests.get(pdf, headers={**H, "Range": "bytes=-1500000"}, timeout=90).content
blob = hdr + tail
print("   circle-I PDF sampled", len(hdr) // 1000, "KB head +", len(tail) // 1000, "KB tail | version", hdr[:8], "| GeoPDF markers (GPTS/LPTS/Measure/VP):", [k.decode() for k in (b"GPTS", b"LPTS", b"/Measure", b"/VP", b"/LGIDict") if k in blob])
# markers may sit in compressed object streams: inflate what we can and look again
hits = set()
for m in re.finditer(rb"stream\r?\n", hdr):
    try:
        d = zlib.decompressobj().decompress(hdr[m.end():m.end() + 400000])
        for k in (b"GPTS", b"LPTS", b"/Measure", b"/LGIDict"):
            if k in d: hits.add(k.decode())
    except Exception: pass
print("   after inflating streams in the sample:", sorted(hits) or "no georeferencing markers found")
