import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const code = ts.transpileModule(readFileSync(new URL('../src/lib/auth.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const key = 'weather-stream.auth';
const user = { id: 'user-1', name: 'Test', email: 'test@example.com' };
const token = { access_token: 'test-token', token_type: 'bearer', expires_in: 1800, user };
function load(storage, fetcher) {
  const timers = [];
  const events = [];
  const context = { exports: {}, Date, JSON, Number, Math, Event,
    fetch: fetcher,
    setTimeout: (fn, delay) => { timers.push({ fn, delay }); return timers.length; },
    clearTimeout: () => {},
    window: {
      sessionStorage: { getItem: k => storage.get(k) ?? null,
        setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
      dispatchEvent: event => events.push(event.type),
    },
  };
  vm.runInNewContext(code, context);
  return { ...context.exports, timers, events };
}
const ok = data => ({ ok: true, status: 200, json: async () => ({ success: true, data }) });

test('login survives reload without extending absolute expiry; logout removes storage', async () => {
  const storage = new Map();
  const first = load(storage, async () => ok(token));
  await first.auth.login({ email: user.email, password: 'test-only' });
  const deadline = JSON.parse(storage.get(key)).expiresAt;
  const reload = load(storage, async (url) => url.endsWith('/me') ? ok(user) : ok(null));
  assert.equal(reload.getAuthSession().user.id, user.id);
  await reload.restoreAuthSession();
  assert.equal(JSON.parse(storage.get(key)).expiresAt, deadline);
  await reload.auth.logout();
  assert.equal(storage.has(key), false);
  assert.equal(load(storage).getAuthSession(), null);
});

test('expired/corrupted sessions do not restore', () => {
  for (const value of ['{broken', JSON.stringify({ auth: token, expiresAt: Date.now() - 1000 })]) {
    const storage = new Map([[key, value]]);
    assert.equal(load(storage).getAuthSession(), null);
    assert.equal(storage.has(key), false);
  }
});

test('revoked token is cleared after server validation; network outage retains session', async () => {
  const stored = JSON.stringify({ auth: token, expiresAt: Date.now() + 100000 });
  const storage = new Map([[key, stored]]);
  const revoked = load(storage, async () => ({ ok: false, status: 401 }));
  assert.equal(await revoked.restoreAuthSession(), null);
  assert.equal(storage.has(key), false);
  assert.ok(revoked.events.includes('auth-expired'));
  storage.set(key, stored);
  const offline = load(storage, async () => { throw new Error('offline'); });
  assert.equal((await offline.restoreAuthSession()).user.id, user.id);
});

test('pending validation cannot resurrect a logged out session', async () => {
  const storage = new Map([[key, JSON.stringify({ auth: token, expiresAt: Date.now() + 100000 })]]);
  let finish;
  const state = load(storage, url => url.endsWith('/me') ? new Promise(resolve => { finish = resolve; }) : Promise.resolve(ok(null)));
  const pending = state.restoreAuthSession();
  await state.auth.logout();
  finish(ok(user));
  assert.equal(await pending, null);
  assert.equal(storage.has(key), false);
});
