import assert from "node:assert/strict";
import test from "node:test";
import { bellCount, bellLabel } from "./bell.js";

test("the bell is quiet when there are no places and no requests", () => {
  assert.equal(bellCount(0, []), 0);
  assert.equal(bellLabel(0), "Уведомления");
});

test("unread places and incoming requests add up", () => {
  assert.equal(bellCount(3, []), 3);
  assert.equal(bellCount(0, [{ id: 1 }, { id: 2 }]), 2);
  assert.equal(bellCount(3, [{ id: 1 }]), 4);
  assert.equal(bellLabel(4), "Уведомления, 4");
});

test("a missing or negative place count does not invent a badge", () => {
  assert.equal(bellCount(undefined, null), 0);
  assert.equal(bellCount(-2, undefined), 0);
});
