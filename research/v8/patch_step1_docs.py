from pathlib import Path
def edit(path, fn):
    p = Path(path); s = p.read_text(encoding="utf-8"); p.write_text(fn(s), encoding="utf-8")

def reg(s):
    anchor = "| **Road routing** |"
    assert s.count(anchor) == 1
    new = ("| **Fire stations (state list)** | TGRAC `TCUR` layer 61 'Fire Stations' — `p33` → `web/data/fire.json` | 71 records for the Hyderabad metro districts: 32 Existing, 39 Proposed; service created 2025-05-24 | compared with OpenStreetMap at 10 places: nearest Existing station matched at 4; OSM maps only 10 stations in the area, so it cannot confirm the rest; 6 of the 8 OSM stations in the study box sit on a listed station (2 do not). The source's remarks (24 Moved, 7 not found accurate, 1 Correct) did not separate matching from non-matching stations | Verify (no licence text published) | status and remark are the source's words and are unexplained; Proposed and Moved are never treated as confirmed; distance is straight-line, not response time; never says a station operates |\n"
           "| **Seismic zone (state layer)** | TGRAC `TCUR` layer 90 'Sesismic Zones' — `p33` → `web/data/seismic.json` | 3 polygons (Zone II x2, Zone III); the whole map region (2,392 grid points) is Zone II, nearest Zone III at least 102 km away; service created 2025-05-24 | agrees with the Zone II reference everywhere in the map region; edition of the zoning not published; not the BIS standard itself | Verify (no licence text published) | a regional hazard zone: says nothing about a building's structural safety |\n")
    s = s.replace(anchor, new + anchor)
    s += ("- **Fire stations vs OpenStreetMap (25 Oct 2026, 10 places, `research/v8/validate_fire.py`):** nearest Existing station on the state list matched OSM's nearest at 4 of 10 places (Secunderabad, Charminar, Kukatpally, Miyapur). The 6 mismatches (Gachibowli, LB Nagar, Uppal, Shamshabad, Medchal, Banjara Hills) are mostly places where OSM has no nearby station mapped (OSM has only 10 fire stations in the whole area), so they show OSM's gaps more than the state list's errors, but that cannot be proven. 7 of the 32 Existing stations have an OSM station within 300 m; 6 of the 8 OSM stations inside the study box have a listed Existing station within 300 m; 2 OSM stations ('Fire St.' near 17.4507, 78.4664 and an unnamed one near 17.5516, 78.5227) are not on the state list. None of the 39 Proposed sites has an OSM station within 300 m.\n"
          "- **Seismic:** the whole map region reads Zone II in the state layer (2,392 grid points), agreeing with the secondary-source reference. An earlier note that a strip near Ghatkesar might be Zone III was wrong: the Zone III polygon's bounding box starts at 78.655 E but the polygon itself is more than 100 km away.\n")
    return s
edit("docs/DATA_REGISTER.md", reg)

def inv(s):
    s = s.replace("| Seismic zone | Partial | \"Zone II\" per secondary sources, IS 1893:2016 | not checked against the standard; a newer edition may differ |",
                  "| Seismic zone | Partial | \"Zone II\" per secondary sources, IS 1893:2016 | not checked against the standard; a newer edition may differ |\n| Earthquake zone (state GIS layer) | Implemented | TGRAC TCUR seismic layer: Zone II across the whole map region | regional zone only; says nothing about a building's structure; zoning edition unpublished |")
    s = s.replace("| Landfills (by size) | Implemented |", "| Fire station on the state list | Implemented | TGRAC TCUR fire layer (32 Existing, 39 Proposed) | straight-line; positions flagged uncertain by the source; never says a station operates |\n| Landfills (by size) | Implemented |")
    return s
edit("docs/FACTOR_INVENTORY.md", inv)

def val(s):
    return s.rstrip("\n") + """

## 8. Step 1 (fire stations, seismic zone), 25 Oct 2026
- **Fire list vs OpenStreetMap, 10 places:** the nearest Existing station matched at 4. See DATA_REGISTER section E for the full account. OSM maps only 10 stations in the area, so it is **not** ground truth and cannot confirm 25 of the 32 Existing stations; the source's remarks ("Moved", "not found accurate") do not predict agreement. The finding therefore carries low confidence and quotes the source's words.
- **Seismic:** state layer = Zone II at all 2,392 grid points of the map region; no disagreement with the reference anywhere.
- **Tests (4,774 pass):** 71 records and statuses and remarks preserved verbatim; a Proposed station is never the headline station and never counted as present; the fire finding is information or unknown only, low confidence, never claims a station operates; the seismic finding is information only and never a safety claim; conflicting sources are both shown; near a zone boundary confidence drops; removing either file gives "data not loaded".
- **Not validated:** positional accuracy of the fire points; the edition and date of the seismic zoning; the meaning of the source's remarks.
"""
edit("docs/VALIDATION_SAMPLE.md", val)
print("step 1 docs written")
