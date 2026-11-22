import {client, encryptedStore} from './07_client.mjs';

// Opt-in adapter for an independently served pilot UI. Never enters the legacy
// rendering or native bridge path. The host can keep its local UI on null.
export async function attachMedicalPilot({enabled, app, fetcher=globalThis.fetch?.bind(globalThis)}) {
  const loopback = ['localhost','127.0.0.1'].includes(globalThis.location?.hostname);
  if (!enabled || !loopback || !globalThis.isSecureContext || !globalThis.navigator?.locks ||
      !globalThis.indexedDB || !globalThis.crypto?.subtle || !fetcher) return null;
  const locks = globalThis.navigator.locks;
  const store = await encryptedStore(globalThis.indexedDB, globalThis.crypto, locks);
  const pilot = client({app, locks, store, fetcher});
  const onOnline = async () => {
    try { await pilot.resume(); } catch { /* Try the current identity. */ }
    if (app === 'nmp') {
      try { await pilot.drain(); } catch { /* Retain the durable queue. */ }
    }
  };
  globalThis.addEventListener('online', onOnline);
  return {
    login: (email,password) => pilot.login(email,password),
    resume: () => pilot.resume(),
    logout: () => pilot.logout(),
    ...(app === 'nmp' ? {test: id => pilot.test(id),
      enqueue: (attempt,owner) => pilot.enqueue(attempt,owner), drain: () => pilot.drain()} : {}),
    close() { globalThis.removeEventListener('online', onOnline); store.close(); },
  };
}
