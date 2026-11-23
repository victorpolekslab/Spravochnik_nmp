import {client, encryptedStore} from './07_client.mjs';

// Opt-in adapter for an independently served pilot UI. Never enters the legacy
// rendering or native bridge path. The host can keep its local UI on null.
export async function pilotOriginAllowed(fetcher=globalThis.fetch?.bind(globalThis)) {
  const url=globalThis.location;
  if (!globalThis.isSecureContext || !url || !fetcher) return false;
  if (url.protocol==='http:' && url.hostname==='localhost') return true;
  if (url.protocol!=='https:') return false;
  try {
    const response=await fetcher('/pilot/config.json',{
      credentials:'omit', redirect:'error', cache:'no-store',
      signal:AbortSignal.timeout(5000)
    });
    if (!response.ok) return false;
    const {origins}=await response.json();
    return Array.isArray(origins) && origins.includes(url.origin);
  } catch { return false; }
}

export async function attachMedicalPilot({enabled, app, onResult, fetcher=globalThis.fetch?.bind(globalThis)}) {
  if (!enabled || !globalThis.navigator?.locks || !globalThis.indexedDB ||
      !globalThis.crypto?.subtle || !await pilotOriginAllowed(fetcher)) return null;
  const locks = globalThis.navigator.locks;
  const store = await encryptedStore(globalThis.indexedDB, globalThis.crypto, locks);
  const pilot = client({app, locks, store, fetcher});
  const onOnline = async () => {
    try { await pilot.resume(); } catch { /* Try the current identity. */ }
    if (app === 'nmp') {
      try { await pilot.drain(onResult); } catch { /* Retain the durable queue. */ }
    }
  };
  globalThis.addEventListener('online', onOnline);
  return {
    login: (email,password) => pilot.login(email,password),
    resume: () => pilot.resume(),
    logout: () => pilot.logout(),
    ...(app === 'nmp' ? {test: id => pilot.test(id),
      enqueue: (attempt,owner) => pilot.enqueue(attempt,owner), drain: () => pilot.drain(onResult)} : {}),
    close() { globalThis.removeEventListener('online', onOnline); store.close(); },
  };
}
