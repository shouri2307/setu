"""Water-body union helper (restored from the earlier p3_flood.py so feature building stays reproducible)."""
import json
from pathlib import Path
import geopandas as gpd
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def _load_water_union(metric_crs):
    """Return a shapely geometry of all water bodies in METRIC_CRS, or None.

    Reads config.OSM_WATER (raw Overpass JSON or a FeatureCollection). Fully
    wrapped: any problem returns None and the model runs on terrain alone.
    """
    try:
        from shapely.geometry import Polygon, shape
        from shapely.ops import unary_union
        raw = json.loads(Path(config.OSM_WATER).read_text())
        polys = []
        if isinstance(raw, dict) and "elements" in raw:          # Overpass JSON
            for el in raw["elements"]:
                etype = el.get("type")
                if etype == "way":
                    g = el.get("geometry")
                    if not g or len(g) < 4:
                        continue
                    coords = [(pt["lon"], pt["lat"]) for pt in g]
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    try:
                        p = Polygon(coords)
                        if p.is_valid and p.area > 0:
                            polys.append(p)
                    except Exception:
                        continue
                elif etype == "relation":
                    # multipolygon lakes (e.g. Hussain Sagar, Gurram Cheruvu) are
                    # relations with member ways, not a flat 'geometry' list —
                    # without this branch they are silently dropped entirely.
                    for m in el.get("members", []):
                        if m.get("role") != "outer":
                            continue
                        g = m.get("geometry")
                        if not g or len(g) < 4:
                            continue
                        coords = [(pt["lon"], pt["lat"]) for pt in g]
                        if coords[0] != coords[-1]:
                            coords.append(coords[0])
                        try:
                            p = Polygon(coords)
                            if p.is_valid and p.area > 0:
                                polys.append(p)
                        except Exception:
                            continue
        elif isinstance(raw, dict) and raw.get("type") == "FeatureCollection":
            for f in raw["features"]:
                try:
                    polys.append(shape(f["geometry"]))
                except Exception:
                    continue
        if not polys:
            return None
        gs = gpd.GeoSeries(polys, crs="EPSG:4326").to_crs(metric_crs)
        return unary_union(list(gs.geometry))
    except Exception:
        return None
