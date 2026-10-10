# Prompts to give ChatGPT (rates for every ward)
Use ChatGPT with **browsing / search turned on** (GPT-5 or the best model you have). Send the prompt for ONE batch at a time (25 wards each), save each CSV reply, and paste them all into `data/rates_input.csv` (keep only one header line). Then run:

```
.venv/Scripts/python pipeline/p10_rates_import.py
```

The importer flags impossible rows (low>high), rows with no source, and outliers, and marks everything as *AI-compiled estimate* in the app so nobody mistakes it for a verified rate.
**After each batch, sanity-check 3 rows you personally know** (e.g. Kukatpally 2BHK up to about Rs 1 crore). If ChatGPT is off by a lot, tell it which rows are wrong and ask it to redo them with sources.
## Master prompt (same for every batch — the importer expects exactly this CSV format)
```text
You are a Hyderabad real-estate data analyst. I am building a tool that shows buyers and agents a SANITY BAND of typical ASKING prices for each area. Accuracy and honesty matter more than completeness.

TASK: For each GHMC ward / locality I list, give typical residential asking-price bands, as of the most recent data you can find (state the month/year).

STRICT RULES
1. Use web browsing/search if you have it. Prefer these sources: Housing.com price-trends pages, Square Yards, MagicBricks, 99acres, NoBroker, Anarock/Knight Frank/PropEquity reports, Telangana registration department (guidance / market values).
2. NEVER invent a number. If you cannot find a credible figure for an area, leave its price cells EMPTY and set confidence=none. An empty cell is far better than a guess.
3. Give RANGES, not single numbers: apartments in Rs per sq ft (low = typical lower end, high = typical upper end; also the narrower "typical" band where most listings sit). Independent plots/land in Rs per sq yard if you can find it. Official guidance value (Rs per sq yd) if you can find it.
4. Where portals disagree, take the overall low and high across sources and list every source.
5. For EVERY row give at least one source name AND URL. No source = confidence none.
6. These are asking prices, not registered deal prices. Do not adjust them.
7. Give approximate latitude and longitude of the locality centre (4 decimals).
8. If a ward contains several well-known localities, give ONE row for the ward (area = ward name) and extra rows for the big localities inside it.

OUTPUT FORMAT: one CSV block only, no commentary before or after, with exactly these columns in this order:
area,ward,lat,lon,apt_low_psf,apt_high_psf,apt_typ_low_psf,apt_typ_high_psf,plot_low_psy,plot_high_psy,guidance_psy,as_of,confidence,sources,notes
- sources = semicolon-separated entries of name|url
- confidence = high / medium / low / none
- as_of = YYYY-MM
- numbers must be plain integers (no commas, no currency symbols)

AREAS FOR THIS BATCH:
```

## Batch 1 of 6 — paste after the master prompt

```text
Ward 1 Kapra
Ward 2 Dr A S Rao Nagar
Ward 5 Mallapur
Ward 6 Nacharam
Ward 7 Chilka Nagar
Ward 8 Habsiguda
Ward 9 Ramanthapur
Ward 10 Uppal
Ward 12 Mansoorabad
Ward 14 BN Reddy Nagar
Ward 15 Vanasthalipuram
Ward 16 Hasthinapuram
Ward 17 Champapet
Ward 18 Lingojiguda
Ward 19 Saroornagar
Ward 20 RK Puram
Ward 21 Kothapet
Ward 22 Chaitanyapuri
Ward 23 Gaddiannaram
Ward 24 Saidabad
Ward 25 Moosarambagh
Ward 26 Old Malakpet
Ward 27 Akbarbagh
Ward 28 Azampura
Ward 29 Chawni
```

## Batch 2 of 6 — paste after the master prompt

```text
Ward 30 Dabeerpura
Ward 32 Patthergatti
Ward 33 Moghalpura
Ward 34 Talab Chanchalam
Ward 35 Gowlipura
Ward 36 Lalithabagh
Ward 37 Rein Bazar
Ward 37 Kurmaguda
Ward 38 IS Sadan
Ward 39 Santhosh Nagar
Ward 40 Riyasat Nagar
Ward 41 Kanchanbagh
Ward 42 Barkas
Ward 43 Chandrayangutta
Ward 44 Uppuguda
Ward 45 Jangammet
Ward 46 Falaknuma
Ward 47 Nawab Saheb Kunta
Ward 48 Shalibanda
Ward 49 Ghansi Bazar
Ward 50 Begum Bazar
Ward 51 Goshamahal
Ward 52 Puranapool
Ward 53 Doodh Bowli
Ward 54 Jahanuma
```

## Batch 3 of 6 — paste after the master prompt

```text
Ward 55 Ramnaspura
Ward 56 Kishanbagh
Ward 57 Suleman Nagar
Ward 58 Shastripuram
Ward 59 Mailardevpally
Ward 60 Rajendra Nagar
Ward 61 Attapur
Ward 62 Ziaguda
Ward 63 Mangalhat
Ward 64 Dattatreya Nagar
Ward 65 Karwan
Ward 66 Langar Houz
Ward 67 Golconda
Ward 68 Tolichowki
Ward 69 Nanal Nagar
Ward 70 Mehdipatnam
Ward 71 Gudimalkapur
Ward 72 Asif Nagar
Ward 73 Vijay Nagar Colony
Ward 74 Ahmed Nagar
Ward 75 Red Hills
Ward 76 Mallepally
Ward 77 Jambagh
Ward 78 Gunfoundry
Ward 79 Himayath Nagar
```

## Batch 4 of 6 — paste after the master prompt

```text
Ward 80 Kachiguda
Ward 81 Nallakunta
Ward 82 Golnaka
Ward 83 Amberpet
Ward 84 Bagh Amberpet
Ward 85 Adikmet
Ward 86 Musheerabad
Ward 87 Ramnagar
Ward 88 Bholakpur
Ward 89 Gandhinagar
Ward 90 Kavadiguda
Ward 91 Khairatabad
Ward 92 Venkateshwara Colony
Ward 93 Banjara Hills
Ward 94 Shaikpet
Ward 95 Jubilee Hills
Ward 96 Yousufguda
Ward 97 Somajiguda
Ward 98 Ameerpet
Ward 99 Vengal Rao Nagar
Ward 100 Sanath Nagar
Ward 101 Erragadda
Ward 102 Rahmath Nagar
Ward 103 Borabanda
Ward 104 Kondapur
```

## Batch 5 of 6 — paste after the master prompt

```text
Ward 105 Gachibowli
Ward 106 Serilingampally
Ward 107 Madhapur
Ward 108 Miyapur
Ward 109 Hafeezpet
Ward 110 Chandanagar
Ward 111 Bharati Nagar
Ward 112 Ramachandrapuram
Ward 114 KPHB Colony
Ward 115 Balaji Nagar
Ward 116 Allapur
Ward 117 Moosapet
Ward 118 Fateh Nagar
Ward 119 Old Bowenpally
Ward 120 Balanagar
Ward 121 Kukatpally
Ward 122 Vivekananda Nagar Colony
Ward 123 Hydernagar
Ward 124 Alwyn Colony
Ward 125 Gajularamaram
Ward 126 Jagathgirigutta
Ward 127 Rangareddy Nagar
Ward 128 Chintal
Ward 129 Suraram
Ward 130 Subash Nagar
```

## Batch 6 of 6 — paste after the master prompt

```text
Ward 131 Quthbullapur
Ward 132 Jeedimetla
Ward 133 Macha Bolarum
Ward 134 Alwal
Ward 135 Venkatapuram
Ward 136 Neredmet
Ward 137 Vinayak Nagar
Ward 138 Moula Ali
Ward 139 East Anand Bagh
Ward 140 Malkajgiri
Ward 141 Gautham Nagar
Ward 142 Addagutta
Ward 143 Tarnaka
Ward 144 Mettuguda
Ward 145 Seethaphalmandi
Ward 146 Boudha Nagar
Ward 147 Bansilapet
Ward 148 Ramgopalpet
Ward 149 Begumpet
Ward 150 Monda Market
```

## Extra batch — popular localities buyers actually search for (beyond the ward names)

```text
Hitec City / Madhapur
Kondapur
Gachibowli
Financial District
Nanakramguda
Kokapet
Narsingi
Manikonda
Puppalguda
Tellapur
Miyapur
Bachupally
Nizampet
KPHB Colony
Kukatpally
Pragathi Nagar
Kompally
Alwal
Bowenpally
Secunderabad
Begumpet
Ameerpet
Sanath Nagar
Banjara Hills
Jubilee Hills
Film Nagar
Khairatabad
Mehdipatnam
Tolichowki
Attapur
Rajendranagar
Shamshabad
Uppal
LB Nagar
Dilsukhnagar
Kothapet
Hayathnagar
Nagole
Malkajgiri
Tarnaka
Habsiguda
Sainikpuri
ECIL
Charminar
Old City
Santoshnagar
Saidabad
Gandipet
Chandanagar
Lingampally
Patancheru
Medchal
Maisammaguda
Dundigal
Ghatkesar
Pocharam
Bandlaguda Jagir
Budvel
Kismatpur
```
