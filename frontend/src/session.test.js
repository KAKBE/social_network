import assert from "node:assert/strict";
import test from "node:test";
import { readStoredToken, screenFor, writeStoredToken, TOKEN_KEY } from "./session.js";

function memory() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

test("a cleared token with no loaded user is the login screen", () => {
  assert.equal(screenFor({ user: null, token: "", loadError: "", config: null }), "login");
});

test("a saved token stays on the loading screen until the profile arrives", () => {
  assert.equal(screenFor({ user: null, token: "old", loadError: "", config: null }), "loading");
});

test("a failed load with a still valid token offers a retry", () => {
  assert.equal(screenFor({ user: null, token: "old", loadError: "Сеть", config: null }), "error");
});

test("a rejected token does not leave the retry message in front of the login form", () => {
  assert.equal(screenFor({ user: null, token: "", loadError: "Сеть", config: null }), "login");
});

test("the app opens only when the profile and config are both loaded", () => {
  assert.equal(screenFor({ user: { id: 1 }, token: "ok", loadError: "", config: null }), "loading");
  assert.equal(screenFor({ user: { id: 1 }, token: "ok", loadError: "", config: {} }), "app");
});

test("writing and clearing the token round-trips through storage", () => {
  const storage = memory();
  writeStoredToken(storage, "abc");
  assert.equal(readStoredToken(storage), "abc");
  assert.equal(storage.getItem(TOKEN_KEY), "abc");
  writeStoredToken(storage, "");
  assert.equal(readStoredToken(storage), "");
  assert.equal(storage.getItem(TOKEN_KEY), null);
});

test("blocked storage reads as signed out", () => {
  const storage = {
    getItem() {
      throw new Error("denied");
    },
    setItem() {
      throw new Error("denied");
    },
    removeItem() {
      throw new Error("denied");
    },
  };
  assert.equal(readStoredToken(storage), "");
  assert.doesNotThrow(() => writeStoredToken(storage, "abc"));
});

test("setToken updates the value Vue renders", async () => {
  const values = new Map();
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  const { getToken, setToken, sessionToken } = await import("./api.js");
  setToken("stale");
  assert.equal(getToken(), "stale");
  assert.equal(sessionToken.value, "stale");
  assert.equal(
    screenFor({ user: null, token: sessionToken.value, loadError: "", config: null }),
    "loading",
  );
  setToken(null);
  assert.equal(getToken(), "");
  assert.equal(values.has(TOKEN_KEY), false);
  assert.equal(
    screenFor({ user: null, token: sessionToken.value, loadError: "", config: null }),
    "login",
  );
});
