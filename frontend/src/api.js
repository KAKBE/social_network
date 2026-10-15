const TOKEN_KEY = "posledu.token";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function parseServerTiming(header) {
  const match = /app;dur=([\d.]+)/.exec(header ?? "");
  return match ? Number(match[1]) : null;
}

async function send(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, data?.detail ?? `Ошибка ${response.status}`);
  }
  // Read from the header, not from Resource Timing: serverTiming there is only exposed on HTTPS.
  return { data, serverMs: parseServerTiming(response.headers.get("Server-Timing")) };
}

async function request(method, path, body) {
  return (await send(method, path, body)).data;
}

export const api = {
  config: () => request("GET", "/api/config"),
  login: (username, password) => request("POST", "/api/auth/login", { username, password }),
  me: () => request("GET", "/api/me"),
  feedWithTiming: () => send("GET", "/api/feed?limit=100"),
  createRecommendation: (body) => request("POST", "/api/recommendations", body),
  geocode: (query) => request("POST", "/api/geocode", { query }),
  lists: () => request("GET", "/api/lists"),
  createList: (title) => request("POST", "/api/lists", { title }),
  addToList: (listId, placeId) => request("POST", `/api/lists/${listId}/places`, { place_id: placeId }),
  removeFromList: (listId, placeId) => request("DELETE", `/api/lists/${listId}/places/${placeId}`),
  sendPerf: (sample) => request("POST", "/api/perf", sample),
};
