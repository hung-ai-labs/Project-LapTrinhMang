import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const code = ts.transpileModule(readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const context = { exports: {}, AbortSignal, AbortController, JSON, Math, Number, Object, Error, TypeError, Promise };
vm.runInNewContext(code, context);
const { ApiError, networkError, isConnectionError, withTimeout } = context.exports;

test('a dropped connection reports a Vietnamese network error', () => {
  const error = networkError(new TypeError('Failed to fetch'));
  assert.equal(error.status, 0);
  assert.equal(error.message, 'Không kết nối được tới máy chủ.');
});

test('only network failures count as a connection problem', () => {
  assert.equal(isConnectionError(networkError(new TypeError('Failed to fetch'))), true);
  assert.equal(isConnectionError(new ApiError('Không tìm thấy phường/xã đang hoạt động.', 404)), false);
  assert.equal(isConnectionError(new ApiError('Chưa tải được danh mục tỉnh/thành.', 503)), false);
  assert.equal(isConnectionError(undefined), false);
});

test('a timeout is reported separately from a dropped connection', () => {
  const timeout = new Error('aborted');
  timeout.name = 'TimeoutError';
  assert.equal(networkError(timeout).message, 'Máy chủ không phản hồi. Kiểm tra kết nối mạng.');
});

test('API errors keep their original status', () => {
  const original = new ApiError('Không tìm thấy phường/xã đang hoạt động.', 404);
  assert.equal(networkError(original), original);
  assert.equal(original.status, 404);
});

test('requests abort when the server stays silent', async () => {
  const signal = withTimeout(undefined, 20);
  assert.equal(signal.aborted, false);
  await new Promise((resolve) => setTimeout(resolve, 60));
  assert.equal(signal.aborted, true);
});

test('a caller abort still cancels the request', async () => {
  const controller = new AbortController();
  const signal = withTimeout(controller.signal, 5000);
  controller.abort();
  assert.equal(signal.aborted, true);
});
