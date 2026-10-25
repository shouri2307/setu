"""One-off: bring the three docs in line with the rainfall rebuild, the heat/GIS-date/seismic validation, and the comparison feature."""

def edit(path, fn):
    s = open(path, encoding="utf-8").read(); s2 = fn(s); open(path, "w", encoding="utf-8").write(s2)

# ---------------- DATA_REGISTER ----------------
def reg(s):
    a = s.index("| **Heavy-rain statistics** |"); b = s.index("\n", a)
    s = s[:a] + ("| **Heavy-rain statistics** | Open Data Telangana (TSDPS) daily weather files, June–October 2018–2025 (`p29` fetch) — `p28` → `rainstats.json` | 27 mandals, 5–7 complete monsoons each (2018–2024; 2025 is excluded because the June 2025 file has only 63% of its days) | "
                 "VERIFIED: recomputed independently at 4 places (28 yearly counts); matches the older files on 4,104 shared mandal-days (99.4% within 0.1 mm, 125 vs 125 heavy days) | **Restricted: NON-COMMERCIAL** | "
                 "about 1.4 heavy days (>64.5 mm) per monsoon; 2018 lists several stations per mandal (averaged); 6,831 out-of-month stray rows dropped |") + s[b:]
    old = "| **Surface heat / greenness** | Landsat 8/9 L2 via Microsoft Planetary Computer — `p25` → `heat.json` | 19 clear scenes Mar–May 2024–26, 150 m grid | VERIFIED (lake 30 °C, park 38 °C, old city 43 °C) | OK (USGS open) | surface not air temperature |"
    new = ("| **Surface heat / greenness** | Landsat 8/9 L2 via Microsoft Planetary Computer — `p25` → `heat.json` | 19 clear scenes Mar–May 2024–26, 150 m grid | physically consistent (lake 30 °C, park 38 °C, old city 43 °C) but **NOT validated**: "
           "across 27 mandals its ranking did not agree with weather-station air temperature (Spearman −0.09, p = 0.66; stations differ by only ~2 °C) | OK (USGS open) | surface not air temperature; reported with low confidence |")
    assert old in s; s = s.replace(old, new, 1)
    anchor = "| TGRAC `Pollution_Category_Boundaries`"
    assert anchor in s
    s = s.replace(anchor, "| TGRAC layer dates | each service's metadata `CreaDate` (when the ArcGIS map document was created): nalas 2025-04-16, water bodies and stream order 2025-04-22, TCUR (forest, transmission, substations) 2025-05-24, groundwater potential 2025-12-06, HYDRAA FTL tanks 2025-05-03, endowment lands 2026-07-28. Abstract and purpose fields are placeholders (\"test\", \"aa\") and layer edit dates are not published, so the date of the underlying survey is **unknown** | VERIFIED |\n" + anchor, 1)
    s += ("- **Heavy-rain statistics:** the older event-month counts (7–12 heavy days) were inflated by selecting flood months; the complete-monsoon figure is about 1.4 a year. The two TSDPS file series agree on 4,104 shared mandal-days "
          "(correlation 1.0000, 99.4% within 0.1 mm, same 125 heavy days). The 2025 monsoon is not in the counts (June 2025 file incomplete), so the recent big storms are missing from them.\n"
          "- **Heat (negative result):** the Landsat composite ranks the old city (Charminar, Bahadurpura) hottest, which is physically plausible, but the 27-mandal rank correlation with station air temperature on the same 15 scene dates is −0.09, so it is reported as unvalidated, low confidence.\n"
          "- **State GIS layer dates:** only the ArcGIS document creation date is published (2025–2026); the survey dates of the underlying data are not.\n"
          "- **Seismic zone:** secondary sources list Hyderabad in Zone II of IS 1893 (Part 1):2016; a possible newer edition could not be confirmed. The report says so and asks the reader to verify.\n")
    return s
edit("docs/DATA_REGISTER.md", reg)

# ---------------- VALIDATION_SAMPLE ----------------
def val(s):
    s = s.replace("Days > 64.5 mm in Oct 2020 + Jul 2021 + Jul 2023 (app / raw) |", "Heavy days per monsoon, 2018–2024 (app / raw) |")
    rows = {"| Hussain Sagar |": "| Hussain Sagar | 1 / 1 | 22.95 / 22.95 | 104, order 4 / 104, order 4 | 0/0 2/2 3/3 1/1 1/1 2/2 1/1 |",
            "| Gachibowli |": "| Gachibowli | 17 / 17 | 0.43 / 0.43 | none within 500 m / none | 1/1 0/0 1/1 0/0 2/2 2/2 2/2 |",
            "| Charminar |": "| Charminar | 3 / 3 | 0.02 / 0.02 | none / none | 1/1 1/1 3/3 2/2 0/0 1/1 1/1 |",
            "| Saroornagar lake |": "| Saroornagar lake | 6 / 6 | 2.25 / 2.25 | 120, order 3 / 120, order 3 | 0/0 0/0 3/3 3/3 0/0 1/1 1/1 |"}
    L = s.split("\n")
    for i, l in enumerate(L):
        for k, v in rows.items():
            if l.startswith(k): L[i] = v
    s = "\n".join(L)
    s = s.replace("No mismatches. This confirms the calculations and the de-duplication;", "No mismatches (including all 28 yearly heavy-day counts). This confirms the calculations and the de-duplication;")
    a = s.index("- Rainfall: the held files"); b = s.index("\n", a)
    s = s[:a] + ("- Rainfall: complete June–October seasons are now used (2018–2025 files). 6,831 out-of-month stray rows were dropped; 2018 lists several stations per mandal (averaged); a mandal-year counts only if every month has ≥90% of its days, "
                 "which excludes 2025 everywhere (June 2025 file: 63%). The result, about 1.4 heavy days per monsoon, replaces the event-months-only figure (7–12) that was inflated by selecting flood months. "
                 "Cross-check against the older file series: 4,104 shared mandal-days, 99.4% within 0.1 mm, max difference 5.3 mm, same heavy-day count (125 vs 125).") + s[b:]
    s = s.replace("## 5. Implemented but NOT independently verified", """## 5. Validation items finished on 24 Oct 2026
- **State GIS layer dates:** the server publishes only an ArcGIS document creation date per service (nalas 2025-04-16, water bodies and streams 2025-04-22, TCUR 2025-05-24, groundwater potential 2025-12-06, HYDRAA FTL tanks 2025-05-03, endowments 2026-07-28). Abstracts are placeholders and layer edit dates are not published, so the dates of the surveys behind the layers remain unknown. Accuracy is not published either.
- **Heat vs station temperatures: not validated.** Landsat composite per mandal vs mean station daily maximum air temperature on the same 15 scene dates: Spearman −0.09 (p = 0.66) over 27 mandals; satellite spread 3.4 °C, station spread 2.3 °C. Different quantities and a narrow station range make this a weak test, but the layer cannot be called validated, so it is shown with low confidence and says so.
- **Seismic zone:** secondary sources put Hyderabad in Zone II (IS 1893 Part 1:2016); a possible newer edition could not be confirmed. The report says "per secondary sources" and "a newer edition may change the zones".
- **Comparison feature:** symmetric (swapping A and B flips every verdict), self-comparison finds no differences, no winner/score/rank field exists, "unknown on one side" is labelled not comparable, and 24 ward pairs render without undefined/NaN or winner wording.

## 6. Implemented but NOT independently verified""")
    s = s.replace("- **Heat grid** against ground truth: physically consistent (lake 30 °C, park 38 °C, old city 43 °C) but not compared with weather-station temperatures.", "- **Heat grid:** compared with station temperatures and found NOT to agree in ranking (section 5); low confidence.")
    s = s.replace("- **Seismic zone** text is a reference line to be verified against the current BIS map.", "- **Seismic zone** has not been checked against the BIS standard itself.")
    return s
edit("docs/VALIDATION_SAMPLE.md", val)

# ---------------- FACTOR_INVENTORY ----------------
def inv(s):
    s = s.replace("| Heavy-rain days per mandal (months held) | Implemented | TSDPS mandal rainfall, months with ≥90% coverage | flood months only, not annual; mandal not plot |",
                  "| Heavy-rain days per monsoon (mandal) | Implemented | TSDPS daily files, 5–7 complete June–October seasons 2018–2024 | about 1.4 a year; 2025 excluded (incomplete file); mandal not plot; too few seasons for a return period |")
    s = s.replace("| Surface heat, greenness | Implemented | Landsat 8/9, 150 m | surface ≠ air temperature |",
                  "| Surface heat | Partial | Landsat 8/9, 150 m | **not validated** (no rank agreement with station air temperature); low confidence |\n| Greenness (NDVI) | Implemented | Landsat 8/9, 150 m | dry-season greenness |")
    s = s.replace("| Seismic zone | Partial | reference text \"Zone II\" | **verify** against the current BIS map |", "| Seismic zone | Partial | \"Zone II\" per secondary sources, IS 1893:2016 | not checked against the standard; a newer edition may differ |")
    s = s.replace("| Rainfall deficit / drought | Planned | TSDPS monthly rainfall available 2005–2026 | not built |", "| Rainfall deficit / drought | Planned | complete monsoon rainfall 2018–2024 now in hand | not built |")
    s = s.replace("| Compare two addresses | Planned | next |", "| Compare two addresses | Implemented | same engine for both; evidence and coverage side by side; no winner or score; unknown on one side is \"not comparable\"; shareable link `#/c/…` |")
    return s
edit("docs/FACTOR_INVENTORY.md", inv)
print("docs updated")
