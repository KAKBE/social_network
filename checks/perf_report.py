"""RAT criterion K2: report on a series of map-open measurements exported from /api/perf.csv.

Run from the repository root:  .venv\\Scripts\\python checks\\perf_report.py <series>
Sample №0 of a series warms the browser cache and is excluded; the next 20 samples are evaluated.
"""

import csv
import statistics
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORT = ROOT / "checks" / "замеры_скорости.csv"
URL = "http://localhost:8000/api/perf.csv"
LIMIT_MS = 2000
SERIES_SIZE = 20
REQUIRED_WITHIN = 19


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Укажите название серии: python checks/perf_report.py phone-wifi-1")
    series = sys.argv[1]

    EXPORT.write_bytes(urllib.request.urlopen(URL).read())
    with EXPORT.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["series"] == series]

    warmup = [r for r in rows if r["seq"] == "0"]
    samples = sorted((r for r in rows if r["seq"] != "0"), key=lambda r: int(r["seq"]))[:SERIES_SIZE]
    if len(samples) < SERIES_SIZE:
        sys.exit(f"В серии «{series}» {len(samples)} замеров после прогрева, нужно {SERIES_SIZE}.")

    totals = [float(r["total_ms"]) for r in samples]
    within = sum(t <= LIMIT_MS for t in totals)
    print(f"Серия «{series}», устройство: {samples[0]['user_agent']}")
    if warmup:
        print(f"Прогрев (№0, не учитывается): {float(warmup[0]['total_ms']):.0f} мс")
    print(f"{'№':>3} {'всего':>7} {'страница':>9} {'лента':>7} {'сервер':>7} {'меток':>6}")
    for r in samples:
        print(
            f"{r['seq']:>3} {float(r['total_ms']):>7.0f} {float(r['dom_ready_ms']):>9.0f} "
            f"{float(r['feed_ms']):>7.0f} {r['server_ms'] or '—':>7} {r['markers']:>6}"
        )
    print(
        f"\nМедиана {statistics.median(totals):.0f} мс, максимум {max(totals):.0f} мс, "
        f"19-е значение по возрастанию {sorted(totals)[REQUIRED_WITHIN - 1]:.0f} мс"
    )
    markers = {r["markers"] for r in samples}
    if markers != {"50"}:
        print(f"ВНИМАНИЕ: число меток в серии {sorted(markers)}, по протоколу должно быть 50.")
    verdict = "ВЫПОЛНЕН" if within >= REQUIRED_WITHIN else "НЕ ВЫПОЛНЕН"
    print(f"К2: {within} из {SERIES_SIZE} не дольше {LIMIT_MS} мс (порог {REQUIRED_WITHIN}) — {verdict}")
    print(f"Выгрузка: {EXPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
