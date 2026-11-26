export const TOKEN_KEY = "posledu.token";

export function readStoredToken(storage) {
  try {
    return storage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function writeStoredToken(storage, token) {
  try {
    if (token) storage.setItem(TOKEN_KEY, token);
    else storage.removeItem(TOKEN_KEY);
  } catch {
    // A blocked storage must not keep the screen on «Загрузка…».
  }
}

export function screenFor({ user, token, loadError, config }) {
  if (!user && !token) return "login";
  if (loadError) return "error";
  if (!user || !config) return "loading";
  return "app";
}
