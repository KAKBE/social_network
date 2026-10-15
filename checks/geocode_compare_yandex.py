"""Alternative path for RAT risk R1: the same 30 addresses through the Yandex Geocoder, compared with K1.

Run from the repository root after geocode_check.py:  .venv\\Scripts\\python checks\\geocode_compare_yandex.py

Does not change K1: Nominatim answers are read from checks/geocode_raw.json and never re-requested.
The key is read from YANDEX_GEOCODER_API_KEY (environment or .env in the repository root).
Raw Yandex responses are stored in checks/geocode_yandex_raw.json; a second run reuses them unless --refetch.
"""

import argparse
import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime

import httpx

from geocode_check import RAW, REQUIRED_HITS, ROOT, THRESHOLD_M, haversine_m, load_addresses

YANDEX_URL = "https://geocode-maps.yandex.ru/v1"
# Same Moscow box as the Nominatim adapter, in Yandex bbox order: lon,lat of lower-left ~ lon,lat of upper-right.
MOSCOW_BBOX = "36.80,55.14~38.00,56.02"
YANDEX_RAW = ROOT / "checks" / "geocode_yandex_raw.json"
COMPARE = ROOT / "checks" / "geocode_compare.csv"


def read_api_key() -> str:
    key = os.environ.get("YANDEX_GEOCODER_API_KEY", "").strip()
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == "YANDEX_GEOCODER_API_KEY":
                key = value.strip()
    if not key:
        sys.exit("Нет ключа: впишите YANDEX_GEOCODER_API_KEY в файл .env в корне репозитория.")
    return key


def fetch_yandex(rows: list[dict[str, str]], refetch: bool) -> dict:
    if YANDEX_RAW.exists() and not refetch:
        return json.loads(YANDEX_RAW.read_text(encoding="utf-8"))
    key = read_api_key()
    raw = {"fetched_at": datetime.now().isoformat(timespec="seconds"), "responses": {}}
    with httpx.Client(timeout=10.0) as client:
        for row in rows:
            print(f"[{row['id']:>2}] {row['address']}")
            response = client.get(
                YANDEX_URL,
                params={
                    "apikey": key,
                    "geocode": row["address"],
                    "lang": "ru_RU",
                    "format": "json",
                    "results": 5,
                    "bbox": MOSCOW_BBOX,
                    "rspn": 1,
                },
            )
            if response.status_code != 200:
                sys.exit(f"Яндекс ответил {response.status_code}: {response.text[:300]}")
            members = response.json()["response"]["GeoObjectCollection"]["featureMember"]
            results = []
            for member in members:
                obj = member["GeoObject"]
                lon, lat = (float(v) for v in obj["Point"]["pos"].split())
                results.append({"display_name": obj["metaDataProperty"]["GeocoderMetaData"]["text"], "lat": lat, "lon": lon})
            raw["responses"][row["id"]] = results
            time.sleep(0.2)
    YANDEX_RAW.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return raw


def first_distance(row: dict[str, str], results: list[dict]) -> float | None:
    if not results:
        return None
    return haversine_m(float(row["ref_lat"]), float(row["ref_lon"]), results[0]["lat"], results[0]["lon"])


def fmt(distance: float | None) -> str:
    return f"{distance:.0f}" if distance is not None else ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refetch", action="store_true", help="запросить Яндекс заново")
    args = parser.parse_args()

    if not RAW.exists():
        sys.exit("Сначала выполните К1: checks/geocode_check.py (нужен checks/geocode_raw.json).")
    rows = load_addresses()
    nominatim = json.loads(RAW.read_text(encoding="utf-8"))
    yandex = fetch_yandex(rows, args.refetch)

    out = []
    for row in rows:
        n_results = nominatim["responses"].get(row["id"], [])
        y_results = yandex["responses"].get(row["id"], [])
        n_dist, y_dist = first_distance(row, n_results), first_distance(row, y_results)
        between = (
            haversine_m(n_results[0]["lat"], n_results[0]["lon"], y_results[0]["lat"], y_results[0]["lon"])
            if n_results and y_results
            else None
        )
        out.append(
            {
                "id": row["id"],
                "object": row["object"],
                "address": row["address"],
                "nominatim_distance_m": fmt(n_dist),
                "nominatim_hit": "да" if n_dist is not None and n_dist <= THRESHOLD_M else "нет",
                "yandex_distance_m": fmt(y_dist),
                "yandex_hit": "да" if y_dist is not None and y_dist <= THRESHOLD_M else "нет",
                "yandex_name": y_results[0]["display_name"] if y_results else "нет результата",
                "nominatim_to_yandex_m": fmt(between),
            }
        )

    with COMPARE.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)

    print(f"\nОтветы Nominatim: {nominatim['fetched_at']}; ответы Яндекса: {yandex['fetched_at']}")
    for r in out:
        print(
            f"[{r['id']:>2}] Nominatim {r['nominatim_distance_m'] or '—':>6} м {r['nominatim_hit']:>3} | "
            f"Яндекс {r['yandex_distance_m'] or '—':>6} м {r['yandex_hit']:>3}  {r['object']}"
        )
    for name in ("nominatim", "yandex"):
        hits = sum(r[f"{name}_hit"] == "да" for r in out)
        distances = [float(r[f"{name}_distance_m"]) for r in out if r[f"{name}_distance_m"]]
        median = f"{statistics.median(distances):.0f} м" if distances else "—"
        print(f"{name:>9}: {hits} из {len(out)} в пределах {THRESHOLD_M:.0f} м (порог К1 {REQUIRED_HITS}); медиана {median}")
    print(f"Подробно: {COMPARE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
