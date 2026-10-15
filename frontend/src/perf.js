// RAT criterion K2: time from navigation start to the moment all friend markers are painted.

const SERIES_KEY = "posledu.perf.series";
const SEQ_KEY = "posledu.perf.seq";

export function getSeries() {
  return localStorage.getItem(SERIES_KEY) ?? "";
}

export function startSeries(name) {
  localStorage.setItem(SERIES_KEY, name);
  localStorage.setItem(SEQ_KEY, "0");
}

export function stopSeries() {
  localStorage.removeItem(SERIES_KEY);
  localStorage.removeItem(SEQ_KEY);
}

function nextSeq() {
  const seq = Number(localStorage.getItem(SEQ_KEY) ?? "0");
  localStorage.setItem(SEQ_KEY, String(seq + 1));
  return seq;
}

export function afterPaint() {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}

function feedRequestMs() {
  const entry = performance.getEntriesByType("resource").find((e) => e.name.includes("/api/feed"));
  return entry ? entry.responseEnd - entry.startTime : 0;
}

/** Called once per page load, after the markers of the first feed response are painted. */
export function measureFirstRender(markers, serverMs) {
  const navigation = performance.getEntriesByType("navigation")[0];
  const feedMs = feedRequestMs();
  const series = getSeries();
  return {
    series,
    seq: series ? nextSeq() : 0,
    total_ms: Math.round(performance.now()),
    dom_ready_ms: Math.round(navigation?.domContentLoadedEventEnd ?? 0),
    feed_ms: Math.round(feedMs),
    server_ms: serverMs === null ? null : Math.round(serverMs * 10) / 10,
    markers,
    navigation_type: navigation?.type ?? "unknown",
  };
}
