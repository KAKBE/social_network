import assert from "node:assert/strict";
import test from "node:test";
import { friendRecommendations } from "./feedList.js";

function post(id, { own = false, city = "Москва", author = "anya" } = {}) {
  return { id, is_own: own, place: { city }, author: { username: author } };
}

test("the list keeps a friend's post after it has been opened", () => {
  const opened = post(1);
  const fresh = post(2, { author: "sasha" });
  assert.deepEqual(
    friendRecommendations([opened, fresh, post(3, { own: true })]).map((item) => item.id),
    [1, 2],
  );
});

test("an empty friend list is the only empty feed", () => {
  assert.deepEqual(friendRecommendations([post(1, { own: true })]), []);
  assert.deepEqual(friendRecommendations([]), []);
});

test("city and author filters are exact and keep the remaining posts", () => {
  const items = [
    post(1, { city: "Москва", author: "anya" }),
    post(2, { city: "", author: "anya" }),
    post(3, { city: "Москва", author: "sasha" }),
  ];
  assert.deepEqual(friendRecommendations(items, { city: "Москва" }).map((item) => item.id), [1, 3]);
  assert.deepEqual(friendRecommendations(items, { city: "Моск" }), []);
  assert.deepEqual(friendRecommendations(items, { author: "anya" }).map((item) => item.id), [1, 2]);
  assert.deepEqual(friendRecommendations(items, { city: "Москва", author: "sasha" }).map((item) => item.id), [3]);
});
