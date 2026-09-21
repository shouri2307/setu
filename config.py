"""SETU — all tunable parameters in one place."""
from pathlib import Path

# ---- Paths ----
ROOT = Path(__file__).parent
DATA = ROOT / "data"
RAW = DATA / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# ---- Hyderabad bounding box (GHMC greater Hyderabad extent) ----
BBOX = {"south": 17.20, "north": 17.60, "west": 78.20, "east": 78.70}

# ---- DEM settings ----
DEM_TYPE = "SRTMGL1"   # 30m SRTM. Alternatives: "COP30", "AW3D30" (JAXA, Japanese)
DEM_FILE = RAW / "hyderabad_dem.tif"

# ---- OSM output files ----
OSM_ROADS = RAW / "hyderabad_roads.geojson"
OSM_HOSPITALS = RAW / "hyderabad_hospitals.geojson"
OSM_WATER = RAW / "hyderabad_water.geojson"

# ---- API endpoints ----
OPENTOPO_URL = "https://portal.opentopography.org/API/globaldem"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"