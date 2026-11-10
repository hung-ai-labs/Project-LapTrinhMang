import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const code = ts.transpileModule(readFileSync(new URL('../src/lib/realtime.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const context = { exports: {}, Math, Number };
vm.runInNewContext(code, context);
const { backoffDelay, heartbeatExpired, HEARTBEAT_TIMEOUT_MS } = context.exports;

test('backoff doubles per attempt and stops at the 15s cap', () => {
  assert.equal(backoffDelay(0), 1000);
  assert.equal(backoffDelay(1), 2000);
  assert.equal(backoffDelay(2), 4000);
  assert.equal(backoffDelay(3), 8000);
  assert.equal(backoffDelay(4), 15000);
  assert.equal(backoffDelay(20), 15000);
});

test('invalid attempts fall back to the base delay', () => {
  assert.equal(backoffDelay(-1), 1000);
  assert.equal(backoffDelay(Number.NaN), 1000);
});

test('heartbeat watchdog fires only after the silent window', () => {
  const now = 1_000_000;
  assert.equal(heartbeatExpired(now - 1000, now), false);
  assert.equal(heartbeatExpired(now - HEARTBEAT_TIMEOUT_MS, now), false);
  assert.equal(heartbeatExpired(now - HEARTBEAT_TIMEOUT_MS - 1, now), true);
  assert.equal(heartbeatExpired(Number.NaN, now), false);
});
