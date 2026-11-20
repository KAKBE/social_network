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

function messageFrom(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const text = detail
      .map((item) => (typeof item === "string" ? item : item?.msg?.replace(/^Value error,\s*/, "")))
      .filter(Boolean)
      .join(" ");
    if (text) return text;
  }
  return `Ошибка ${status}`;
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
    throw new ApiError(response.status, messageFrom(data, response.status));
  }
  // Read from the header, not from Resource Timing: serverTiming there is only exposed on HTTPS.
  return { data, serverMs: parseServerTiming(response.headers.get("Server-Timing")) };
}

async function request(method, path, body) {
  return (await send(method, path, body)).data;
}

async function sendForm(method, path, body) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { method, headers, body });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, messageFrom(data, response.status));
  return data;
}

async function requestBlob(path) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { headers });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, messageFrom(data, response.status));
  }
  return response.blob();
}

export const api = {
  config: () => request("GET", "/api/config"),
  login: (login, password) => request("POST", "/api/auth/login", { login, password }),
  register: (body) => request("POST", "/api/auth/register", body),
  me: () => request("GET", "/api/me"),
  updateMe: (body) => request("PATCH", "/api/me", body),
  changePassword: (body) => request("POST", "/api/me/password", body),
  uploadAvatar: (file) => {
    const body = new FormData();
    body.append("file", file);
    return sendForm("POST", "/api/me/avatar", body);
  },
  avatarBlob: () => requestBlob("/api/me/avatar"),
  searchUsers: (q) => request("GET", `/api/users/search?q=${encodeURIComponent(q)}`),
  profile: (publicId) => request("GET", `/api/users/${publicId}`),
  friendRequests: () => request("GET", "/api/friend-requests"),
  sendFriendRequest: (username) => request("POST", "/api/friend-requests", { username }),
  acceptFriendRequest: (id) => request("POST", `/api/friend-requests/${id}/accept`),
  rejectFriendRequest: (id) => request("POST", `/api/friend-requests/${id}/reject`),
  friends: () => request("GET", "/api/friends"),
  setCloseFriend: (username, close) => request("PUT", `/api/friends/${encodeURIComponent(username)}/close`, { close }),
  feedWithTiming: () => send("GET", "/api/feed?limit=100"),
  unseenFeed: ({ city = "", author = "" } = {}) => {
    const params = new URLSearchParams({ limit: "100", unseen: "true" });
    if (city) params.set("city", city);
    if (author) params.set("author", author);
    return request("GET", `/api/feed?${params}`);
  },
  recommendation: (id) => request("GET", `/api/recommendations/${id}`),
  publishRecommendation: (id) => request("POST", `/api/recommendations/${id}/publish`),
  toggleLike: (id) => request("POST", `/api/recommendations/${id}/like`),
  uploadRecommendationPhoto: (id, file) => {
    const body = new FormData();
    body.append("file", file);
    return sendForm("POST", `/api/recommendations/${id}/photos`, body);
  },
  recommendationPhotoBlob: (id, photoId) => requestBlob(`/api/recommendations/${id}/photos/${photoId}`),
  createRecommendation: (body) => request("POST", "/api/recommendations", body),
  geocode: (query) => request("POST", "/api/geocode", { query }),
  reverse: (lat, lon) => request("POST", "/api/geocode/reverse", { lat, lon }),
  lists: () => request("GET", "/api/lists"),
  createList: (title) => request("POST", "/api/lists", { title }),
  addToList: (listId, placeId) => request("POST", `/api/lists/${listId}/places`, { place_id: placeId }),
  removeFromList: (listId, itemId) => request("DELETE", `/api/lists/${listId}/items/${itemId}`),
  sendPerf: (sample) => request("POST", "/api/perf", sample),
};
