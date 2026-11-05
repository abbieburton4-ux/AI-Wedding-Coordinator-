import test from "node:test";
import assert from "node:assert/strict";
import { fetchSessionProfile } from "./sessionProfile.js";

const profile = { id: "fictional-user", role: "couple", email: "test@example.test" };
const respond = (body, status) => async () => new Response(JSON.stringify(body), { status });

test("a valid profile resolves and includes the bearer token", async () => {
  const result = await fetchSessionProfile("/api/v1/auth/me", "test-token", async (url, init) => {
    assert.equal(url, "/api/v1/auth/me");
    assert.equal(init.headers.Authorization, "Bearer test-token");
    return new Response(JSON.stringify(profile));
  });
  assert.deepEqual(result, { user: profile, denied: null, error: null });
});

test("401 is visible and is not confused with an access-list denial", async () => {
  const result = await fetchSessionProfile("/api/v1/auth/me", "test-token", respond({}, 401));
  assert.equal(result.user, null);
  assert.equal(result.denied, null);
  assert.match(result.error, /couldn't verify your sign-in/);
});

test("403 preserves the backend access or confirmation explanation", async () => {
  const message = "This email address hasn't been confirmed yet.";
  const result = await fetchSessionProfile("/api/v1/auth/me", "test-token", respond({ detail: message }, 403));
  assert.equal(result.denied, message);
  assert.equal(result.error, null);
});

test("malformed 403 responses still explain denied access", async () => {
  const result = await fetchSessionProfile("/api/v1/auth/me", "test-token",
    async () => new Response("<html>error</html>", { status: 403 }));
  assert.match(result.denied, /access list/);
});

test("server errors and network failures are visible without leaking details", async () => {
  const failed = await fetchSessionProfile("/api/v1/auth/me", "test-token",
    respond({ detail: "private internal details" }, 500));
  assert.match(failed.error, /couldn't complete sign-in/);
  assert.doesNotMatch(failed.error, /private internal details/);
  const offline = await fetchSessionProfile("/api/v1/auth/me", "test-token",
    async () => { throw new Error("network internals"); });
  assert.match(offline.error, /couldn't reach/);
  assert.equal(offline.denied, null);
});

test("incomplete successful responses are reported instead of silently stalling", async () => {
  const result = await fetchSessionProfile("/api/v1/auth/me", "test-token", respond({}, 200));
  assert.match(result.error, /incomplete/);
  assert.equal(result.user, null);
});

test("retrying after a rejected token clears the error when the profile succeeds", async () => {
  let attempts = 0;
  const request = async () => {
    attempts += 1;
    return attempts === 1
      ? new Response("{}", { status: 401 })
      : new Response(JSON.stringify(profile));
  };
  const first = await fetchSessionProfile("/api/v1/auth/me", "test-token", request);
  assert.ok(first.error);
  const retry = await fetchSessionProfile("/api/v1/auth/me", "new-test-token", request);
  assert.deepEqual(retry, { user: profile, denied: null, error: null });
});
