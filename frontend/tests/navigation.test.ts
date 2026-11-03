import test from "node:test";
import assert from "node:assert/strict";
import { parseRoute, routeHash, initialMode } from "../src/navigation.ts";

test("a saved article address retains its source list after reload", () => {
  assert.deepEqual(parseRoute("#/read/demo-003?from=saved"), {
    page: "Saved",
    itemId: "demo-003",
  });
  assert.equal(
    routeHash({ page: "Saved", itemId: "demo-003" }),
    "#/read/demo-003?from=saved",
  );
});
test("secondary pages can be linked and restored without article content", () => {
  assert.deepEqual(parseRoute("#/hidden"), { page: "Hidden" });
  assert.deepEqual(parseRoute("#/evaluation"), { page: "Evaluation" });
  assert.deepEqual(parseRoute("#/feed"), { page: "Discover" });
});
test("invalid or unknown addresses cannot become arbitrary item paths", () => {
  for (const hash of [
    "#/read/../../secret",
    "#/unknown",
    "#/read/<script>",
    "",
  ]) {
    assert.deepEqual(parseRoute(hash), { page: "Discover" });
  }
  assert.deepEqual(parseRoute("#/read/demo-001?from=untrusted"), {
    page: "Discover",
    itemId: "demo-001",
  });
});
test("missing, invalid or restricted storage falls back to the default method", () => {
  assert.equal(initialMode(), "personalized");
  Object.defineProperty(globalThis, "sessionStorage", {
    configurable: true,
    value: { getItem: () => "content" },
  });
  assert.equal(initialMode(), "content");
  Object.defineProperty(globalThis, "sessionStorage", {
    configurable: true,
    get() {
      throw new Error("Storage restricted");
    },
  });
  assert.equal(initialMode(), "personalized");
  delete (globalThis as Record<string, unknown>).sessionStorage;
});
