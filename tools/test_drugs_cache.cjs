'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('android/app/src/main/assets/www/content_drugs.js', 'utf8');
const start = source.indexOf('  var mem = {};');
const end = source.indexOf('  function lsGet(', start);
assert(start >= 0 && end > start, 'Cannot locate cache implementation');
const cacheSource = source.slice(start, end);
const context = { Promise, Error, indexedDB: null };
vm.createContext(context);

function fakeDB({fail = false} = {}) {
  const records = new Map();
  const db = {
    transaction() {
      const tx = {
        error: new Error('simulated write failure'),
        objectStore() {
          return {
            put(value, key) {
              if (fail) queueMicrotask(() => tx.onerror?.());
              else queueMicrotask(() => { records.set(key, value); tx.oncomplete?.(); });
            },
            get(key) {
              const req = {};
              queueMicrotask(() => { req.result = records.get(key); req.onsuccess?.(); });
              return req;
            }
          };
        }
      };
      return tx;
    }
  };
  return {db, records};
}
async function test() {
  const success = fakeDB();
  context.indexedDB = {open() {
    const req = {result: success.db};
    queueMicrotask(() => req.onsuccess?.());
    return req;
  }};
  vm.runInContext(cacheSource, context);
  await vm.runInContext("cset('doc:2:drugA', {text:'new'})", context);
  assert.equal(success.records.get('doc:2:drugA')?.text, 'new');
  assert.equal((await vm.runInContext("cget('doc:2:drugA')", context)).text, 'new');

  const failed = fakeDB({fail: true});
  context.dbp = Promise.resolve(failed.db);
  await assert.rejects(vm.runInContext("cset('doc:3:drugA', {text:'bad'})", context));
  assert.equal(context.mem['doc:3:drugA'], undefined, 'Failed write must not appear cached');

  assert(source.includes("'doc:' + String(version || 'unknown') + ':' + id"), 'Document reader must use versioned keys');
  assert(source.includes("'doc:' + String(offlineVersion) + ':' + id"), 'Offline writer must use versioned keys');
  assert(source.includes("return cset('ver', v.v)"), 'Version marker must wait for cache writes');
  console.log('Drug cache behavior and version-key checks passed');
}
test().catch(e => {console.error(e); process.exitCode = 1;});
