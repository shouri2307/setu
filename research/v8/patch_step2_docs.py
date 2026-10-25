from pathlib import Path
def edit(path, fn):
    p = Path(path); s = p.read_text(encoding="utf-8"); p.write_text(fn(s), encoding="utf-8")

def reg(s):
    anchor = "| **Road routing** |"
    assert s.count(anchor) == 1
    new = ("| **Tank survey numbers + the parcels carrying them** | TGRAC HYDRAA `Second_Window` 'ORR Tanks' field `Base_Syno`, matched to `Bhunaksha_Cadastral` layer 0 and `Hydra_Folder/Fourth_Window` layer 0 — `p18` (adds `id`, `syn` to `hydraa_tanks.json`) + `p34` → `web/data/tank_syn.json` | 313 of 1,192 tank records carry a usable survey number (26%); a same-numbered parcel was found within 150 m for 271 and it touches the tank outline for 253 | checked at 20 lakes chosen by a fixed rule: parcel with the tank's number found nearby at 16, touching the outline at 14; village spellings differ in 6 of 16, so matched on number + position. Not checked against revenue records | Verify (no licence text published) | a parcel carrying a tank's number is NOT the legal Full Tank Level and is not evidence of encroachment; official FTL polygons are not retrievable; placeholder numbers (88805, 99905, 'Not Visible') are dropped |\n")
    s = s.replace(anchor, new + anchor)
    s += ("- **Step 2, tank survey numbers at 20 lakes (25 Oct 2026, `research/v8/step2_validate.py`, log `step2_validate.log`):** lakes = named tanks with a survey number, 20 at evenly spaced ranks by size. A parcel with the tank's number was found next to the lake at 16 of 20 and touches the outline at 14 (the cadastral layer alone: 13). The first run matched on village name and wrongly reported 8 matches; village spellings differ (Qutubullapur / Quthbullapur), so matching now uses number + position. Lakes with no match: Rawiral Cheruvu, Dammai Cheruvu, Vaddervani Kunta, Kummari Kunta (Ameenpur). A parcel carrying the number can cover as little as 2% or as much as 100% of the outline.\n"
          "- **Step 2, HYDRAA parcel layer vs the main cadastral layer (`step2_coverage.py`, `step2_agree.py`):** over 154 map tiles the two layers hold about the same number of numbered parcels in total (49,831 vs 47,249), but not in the same places: 9 tiles have parcels in the HYDRAA layer and none in the main layer, 30 have more than 25% extra, 13 the reverse. At 300 random points where both have a parcel, 199 of 208 (96%) give the same number (197 identical, 2 with a different village spelling); 9 (4%) give a different, often neighbouring, number. The earlier discovery note that the HYDRAA layer returns '31 parcels where the main layer returns 3' at Saroornagar was a one-off count and is not typical; at 900 m it is 135 vs 64 numbered parcels. The HYDRAA parcels are NOT merged into plot matching: a 4% number mismatch would put some pins on a neighbouring survey number.\n")
    return s
edit("docs/DATA_REGISTER.md", reg)

def inv(s):
    return s.replace("| Fire station on the state list | Implemented |", "| Tank survey number near this pin | Implemented | state water-body layer's recorded survey number + the parcel carrying it | 26% of tanks have a number; not the legal FTL; not evidence of encroachment |\n| Fire station on the state list | Implemented |")
edit("docs/FACTOR_INVENTORY.md", inv)

def val(s):
    return s.rstrip("\n") + """

## 9. Step 2 (tank survey numbers, lake-side parcels), 25 Oct 2026
- **20 lakes:** a parcel with the tank's own survey number was found nearby at 16 and touches the outline at 14. Four lakes had no match (number may belong to another village or numbering, or be mistyped in the layer). Matching by village name alone missed half of them because spellings differ; the finding matches on number and position.
- **All 313 numbered tanks:** a same-numbered parcel within 150 m for 271 (87%), touching the outline for 253 (81%).
- **Parcel coverage, HYDRAA layer vs main layer:** similar totals, different places; 96% agreement on the number where both have a parcel. Not merged into plot matching (see DATA_REGISTER section E).
- **Wording rule, tested:** the finding never says inside the legal FTL, encroached, illegal or safe to buy; it says a survey number matches and that this is a reason to check the title.
- **Tests (4,790 pass):** placeholders dropped; every stored parcel carries the tank's number and no personal fields; counts in the file header match the file; statuses info/watch/unknown only, low confidence; an incomplete parcel search reads unknown, never "none found"; removing the file reads "data not loaded".
- **Not validated:** the tank survey numbers against revenue records; the legal FTL (not retrievable); whether a numbered parcel is still a water body today.
"""
edit("docs/VALIDATION_SAMPLE.md", val)
print("step 2 docs written")
