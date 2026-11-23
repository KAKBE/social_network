import assert from "node:assert/strict";
import test from "node:test";
import { canOpenProfileMap, postsForChip } from "./profileMap.js";

const published = { id: 1, status: "published", category: "walk" };
const draft = { id: 2, status: "draft", category: "food" };

test("a viewer with no visible posts cannot open the profile map", () => {
  assert.equal(canOpenProfileMap([], "all"), false);
});

test("published posts can be opened on the map, drafts stay off the all chip", () => {
  assert.equal(canOpenProfileMap([published, draft], "all"), true);
  assert.deepEqual(postsForChip([published, draft], "all"), [published]);
});

test("an empty category hides the map", () => {
  assert.equal(canOpenProfileMap([published], "food"), false);
  assert.equal(canOpenProfileMap([published], "walk"), true);
});

test("the author can map drafts only while that chip is open", () => {
  assert.equal(canOpenProfileMap([draft], "all"), false);
  assert.equal(canOpenProfileMap([draft], "drafts"), true);
});
