import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const clientRoot = new URL('../', import.meta.url);
const typescript = await import(new URL('./node_modules/typescript/lib/typescript.js', clientRoot).href);

function compile(file, context) {
  const code = typescript.transpileModule(readFileSync(new URL(file, clientRoot), 'utf8'), {
    compilerOptions: { module: typescript.ModuleKind.CommonJS, target: typescript.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(code, context);
  return context.exports;
}

function fakeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    map,
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
  };
}

function fakeWindow(storage) {
  const listeners = new Map();
  return {
    localStorage: storage,
    addEventListener: (type, fn) => listeners.set(type, [...(listeners.get(type) ?? []), fn]),
    removeEventListener: (type, fn) => listeners.set(type, (listeners.get(type) ?? []).filter((f) => f !== fn)),
    dispatch: (type) => { for (const fn of listeners.get(type) ?? []) fn(); },
  };
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const realtime = compile('src/lib/realtime.ts', { exports: {}, Math, Number, JSON });
const windowFake = fakeWindow(fakeStorage());
const connection = compile('src/lib/connection.ts', {
  exports: {}, window: windowFake, navigator: { onLine: false }, Set,
});
const catalogModule = compile('src/lib/catalog.ts', {
  exports: {},
  require: (name) => (name === './realtime' ? realtime : {}),
  AbortSignal,
  AbortController,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  JSON,
  Math,
  Number,
  Object,
  Error,
  TypeError,
  Promise,
  console,
});
const { ResourceLoader, readSelection, writeSelection } = catalogModule;

test('the cached value stays visible while the request fails', async () => {
  const storage = fakeStorage({ 'weather-stream.catalog.provinces': JSON.stringify([{ id: '01', name: 'Hà Nội' }]) });
  const values = [];
  const errors = [];
  const loader = new ResourceLoader({
    cache: {
      key: 'weather-stream.catalog.provinces',
      parse: (raw) => JSON.parse(raw),
      serialize: (value) => JSON.stringify(value),
    },
    storage,
    load: async () => { throw new TypeError('Failed to fetch'); },
    onValue: (value) => values.push(value),
    onError: (message) => errors.push(message),
    retryDelay: () => 5,
  });
  loader.start();
  await wait(30);

  assert.equal(values.length, 1);
  assert.equal(values[0].length, 1);
  assert.equal(values[0][0].name, 'Hà Nội');
  assert.equal(errors.length >= 1, true);
  loader.stop();
});

test('a refresh reloads the value as soon as the network is back', async () => {
  const storage = fakeStorage();
  let failing = true;
  const values = [];
  const loader = new ResourceLoader({
    storage,
    load: async () => {
      if (failing) throw new TypeError('Failed to fetch');
      return { ward_id: '00004' };
    },
    onValue: (value) => values.push(value),
    onError: () => {},
    retryDelay: () => 5000,
  });
  loader.start();
  await wait(20);
  assert.equal(values.length, 0);

  failing = false;
  loader.refresh();
  await wait(20);
  assert.equal(values.length, 1);
  assert.equal(values[0].ward_id, '00004');
  loader.stop();
});

test('the loader keeps retrying in the background until the network returns', async () => {
  const storage = fakeStorage();
  let attempts = 0;
  const values = [];
  const loader = new ResourceLoader({
    storage,
    load: async () => {
      attempts += 1;
      if (attempts < 3) throw new TypeError('Failed to fetch');
      return { ward_id: '00004' };
    },
    onValue: (value) => values.push(value),
    onError: () => {},
    retryDelay: () => 5,
  });
  loader.start();
  await wait(60);

  assert.equal(attempts >= 3, true);
  assert.equal(values.length, 1);
  loader.stop();
});

test('a successful load is cached and re-applied on the next start', async () => {
  const storage = fakeStorage();
  const loader = new ResourceLoader({
    cache: {
      key: 'weather-stream.forecast.00004',
      parse: (raw) => JSON.parse(raw),
      serialize: (value) => JSON.stringify(value),
    },
    storage,
    load: async () => ({ ward_id: '00004', predicted_temperature: 31 }),
    onValue: () => {},
    onError: () => {},
  });
  loader.start();
  await wait(20);
  assert.equal(storage.getItem('weather-stream.forecast.00004'), '{"ward_id":"00004","predicted_temperature":31}');
  loader.stop();
});

test('a connection failure produces one banner instead of many messages', async () => {
  const storage = fakeStorage();
  const api = compile('src/lib/api.ts', {
    exports: {}, AbortSignal, AbortController, JSON, Math, Number, Object, Error, TypeError, Promise, console,
    fetch: async () => { throw new TypeError('Failed to fetch'); },
  });
  const notices = [];
  let offline = false;
  const loader = new ResourceLoader({
    storage,
    load: async (signal) => api.api('/wards/00004/weather/current', signal),
    onValue: () => {},
    onError: (message, error) => {
      if (api.isConnectionError(error)) {
        offline = true;
        return;
      }
      notices.push(message);
    },
    retryDelay: () => 5,
  });
  loader.start();
  await wait(30);

  assert.equal(offline, true, 'the connection problem must be reported once');
  assert.equal(notices.length, 0, 'no extra message for a connection failure');
  loader.stop();
});

test('the last selection survives a reload', () => {  const storage = fakeStorage();
  const empty = readSelection(storage);
  assert.equal(empty.provinceId, null);
  assert.equal(empty.wardId, null);
  assert.equal(empty.wardName, null);
  writeSelection({ provinceId: '01', wardId: '00004', wardName: 'Ba Đình' }, storage);
  const restored = readSelection(storage);
  assert.equal(restored.provinceId, '01');
  assert.equal(restored.wardId, '00004');
  assert.equal(restored.wardName, 'Ba Đình');
});

test('the dashboard reloads everything when the network comes back', async () => {
  const storage = fakeStorage({
    'weather-stream.catalog.provinces': JSON.stringify([{ id: '01', name: 'Hà Nội' }]),
    'weather-stream.catalog.wards.01': JSON.stringify([{ id: '00004', name: 'Ba Đình', province_id: '01' }]),
    'weather-stream.forecast.00004': JSON.stringify({ ward_id: '00004', predicted_temperature: 30 }),
  });
  const window2 = fakeWindow(storage);
  const bus = compile('src/lib/connection.ts', {
    exports: {}, window: window2, navigator: { onLine: false }, Set,
  });

  let online = false;
  const calls = { provinces: 0, wards: 0, forecast: 0 };
  const failing = async () => { throw new TypeError('Failed to fetch'); };
  const provinces = new ResourceLoader({
    cache: { key: 'weather-stream.catalog.provinces', parse: (raw) => JSON.parse(raw), serialize: (v) => JSON.stringify(v) },
    storage,
    load: async () => { calls.provinces += 1; if (!online) return failing(); return [{ id: '01', name: 'Hà Nội' }]; },
    onValue: () => {},
    onError: () => {},
    retryDelay: () => 5,
  });
  const wards = new ResourceLoader({
    cache: { key: 'weather-stream.catalog.wards.01', parse: (raw) => JSON.parse(raw), serialize: (v) => JSON.stringify(v) },
    storage,
    load: async () => { calls.wards += 1; if (!online) return failing(); return [{ id: '00004', name: 'Ba Đình', province_id: '01' }]; },
    onValue: () => {},
    onError: () => {},
    retryDelay: () => 5,
  });
  const forecast = new ResourceLoader({
    cache: { key: 'weather-stream.forecast.00004', parse: (raw) => JSON.parse(raw), serialize: (v) => JSON.stringify(v) },
    storage,
    load: async () => { calls.forecast += 1; if (!online) return failing(); return { ward_id: '00004', predicted_temperature: 31 }; },
    onValue: () => {},
    onError: () => {},
    retryDelay: () => 5,
  });

  // The hooks refresh every loader when the browser reports that the network is back.
  bus.subscribe(() => {
    provinces.refresh();
    wards.refresh();
    forecast.refresh();
  });

  provinces.start();
  wards.start();
  forecast.start();
  await wait(40);
  assert.equal(calls.provinces >= 1, true);
  assert.equal(calls.wards >= 1, true);
  assert.equal(calls.forecast >= 1, true);

  const before = { ...calls };
  online = true;
  window2.dispatch('online');
  await wait(40);

  assert.equal(calls.provinces > before.provinces, true, 'provinces must be reloaded');
  assert.equal(calls.wards > before.wards, true, 'wards must be reloaded');
  assert.equal(calls.forecast > before.forecast, true, 'the forecast must be reloaded');
  provinces.stop();
  wards.stop();
  forecast.stop();
});
