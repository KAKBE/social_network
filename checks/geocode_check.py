"""RAT criterion K1: geocoding accuracy of 30 Moscow addresses against manual reference points.

Run from the repository root:  .venv\\Scripts\\python checks\\geocode_check.py

Nominatim policy for one-time bulk tasks: single thread, at most 1 request per second, results cached
on our side and never re-requested. Raw responses are stored in checks/geocode_raw.json; a second run
reuses them unless --refetch is passed.
"""

import argparse
import csv
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.geocoding import NominatimGeocoder  # noqa: E402  (needs the sys.path entry above)

ADDRESSES = ROOT / "checks" / "addresses.csv"
RAW = ROOT / "checks" / "geocode_raw.json"
RESULTS = ROOT / "checks" / "geocode_results.csv"
THRESHOLD_M = 100.0
REQUIRED_HITS = 27


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_addresses() -> list[dict[str, str]]:
    with ADDRESSES.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    missing = [r["id"] for r in rows if not r["ref_lat"].strip() or not r["ref_lon"].strip()]
    if missing:
        sys.exit(f"Нет эталонных координат для адресов: {', '.join(missing)}. Заполните checks/addresses.csv.")
    outside = [r["id"] for r in rows if not (55.14 <= float(r["ref_lat"]) <= 56.02 and 36.80 <= float(r["ref_lon"]) <= 38.00)]
    if outside:
        sys.exit(f"Эталон вне Москвы у адресов: {', '.join(outside)}. Проверьте, не перепутаны ли широта и долгота.")
    return rows


def warn_if_references_uncommitted() -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", str(ADDRESSES)], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    if status:
        print("ВНИМАНИЕ: эталоны в checks/addresses.csv не закоммичены. Закоммитьте их до запуска,")
        print("чтобы было видно, что эталон снят до получения результатов геокодера.\n")


def fetch_raw(rows: list[dict[str, str]], refetch: bool) -> dict:
    if RAW.exists() and not refetch:
        return json.loads(RAW.read_text(encoding="utf-8"))
    geocoder = NominatimGeocoder()
    raw = {"fetched_at": datetime.now().isoformat(timespec="seconds"), "responses": {}}
    for row in rows:
        print(f"[{row['id']:>2}] {row['address']}")
        results = geocoder.fetch(row["address"])
        raw["responses"][row["id"]] = [r.__dict__ for r in results]
    RAW.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refetch", action="store_true", help="запросить Nominatim заново")
    args = parser.parse_args()

    rows = load_addresses()
    warn_if_references_uncommitted()
    raw = fetch_raw(rows, args.refetch)

    hits = 0
    out = []
    for row in rows:
        results = raw["responses"].get(row["id"], [])
        if results:
            first = results[0]
            distance = haversine_m(float(row["ref_lat"]), float(row["ref_lon"]), first["lat"], first["lon"])
            hit = distance <= THRESHOLD_M
        else:
            first, distance, hit = None, None, False
        hits += hit
        out.append(
            {
                "id": row["id"],
                "object": row["object"],
                "address": row["address"],
                "ref_lat": row["ref_lat"],
                "ref_lon": row["ref_lon"],
                "nominatim_lat": first["lat"] if first else "",
                "nominatim_lon": first["lon"] if first else "",
                "nominatim_name": first["display_name"] if first else "нет результата",
                "distance_m": f"{distance:.0f}" if distance is not None else "",
                "hit": "да" if hit else "нет",
            }
        )

    with RESULTS.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)

    print(f"\nОтветы Nominatim получены: {raw['fetched_at']}")
    for r in out:
        print(f"[{r['id']:>2}] {r['hit']:>3}  {r['distance_m'] or '—':>6} м  {r['object']}")
    verdict = "ВЫПОЛНЕН" if hits >= REQUIRED_HITS else "НЕ ВЫПОЛНЕН"
    print(f"\nК1: {hits} из {len(rows)} в пределах {THRESHOLD_M:.0f} м (порог {REQUIRED_HITS}) — {verdict}")
    print(f"Подробно: {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
