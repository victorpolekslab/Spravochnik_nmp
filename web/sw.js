/* Service worker: keeps the whole reference offline and updates it file by file. */
const VERSION = '__VERSION__';
const FILES = __FILES__; // [path, revision]
const CACHE = 'nmp-' + VERSION;
const BASE = new URL('./', self.location).href;
const keyed = {}; FILES.forEach(([p, r]) => { keyed[new URL(p, BASE).href] = new URL(p, BASE).href + '?rev=' + r; });
keyed[BASE] = keyed[new URL('index.html', BASE).href];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    for (const [p, r] of FILES) {
      const k = new URL(p, BASE).href + '?rev=' + r;
      const old = await caches.match(k); // unchanged files are reused from the previous version
      if (old) { await c.put(k, old); continue; }
      const res = await fetch(new URL(p, BASE).href, { cache: 'no-cache' });
      if (!res.ok) throw new Error(p + ' ' + res.status);
      await c.put(k, res);
    }
  })());
});
self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== CACHE && k.startsWith('nmp-')) await caches.delete(k);
    await self.clients.claim();
  })());
});
self.addEventListener('message', e => { if (e.data === 'skipWaiting') self.skipWaiting(); });
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const u = new URL(e.request.url);
  if (u.origin !== self.location.origin) return; // apicr.minzdrav.gov.ru etc. go straight to the network
  const k = keyed[u.origin + u.pathname];
  if (!k) return;
  e.respondWith(caches.open(CACHE).then(c => c.match(k)).then(r => r || fetch(e.request)));
});
