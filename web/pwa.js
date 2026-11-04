'use strict';
/* Веб-версия (PWA): реализует window.Native поверх sql.js (та же база, что и в Android-версии),
   загруженные КР хранятся в IndexedDB. После инициализации подгружает общий app.js. */
(function () {
  const VIEW = document.getElementById('view');
  const splash = t => { VIEW.innerHTML = `<div class="pwa-splash"><div class="pwa-logo"></div><b>Справочник фельдшера НМП</b><span>${t}</span></div>`; };
  splash('Загрузка справочника…');

  let db = null;
  const DL = new Map(); // cr -> {cr, at, bytes, secs:[{ord,sid,title,lvl,html}]}
  const td = new TextDecoder();

  // ---------------------------------------------------------------- SQL helpers
  function rows(sql, params) {
    const st = db.prepare(sql);
    try {
      if (params) st.bind(params.map(v => (typeof v === 'bigint' ? Number(v) : v)));
      const out = [];
      while (st.step()) out.push(st.getAsObject());
      return out;
    } finally { st.free(); }
  }
  const J = o => JSON.stringify(o);
  const err = e => J({ error: String(e) });
  const inflate = z => (z && z.length ? td.decode(fflate.unzlibSync(z)) : '');
  const isOffline = id => rows('SELECT 1 FROM sec WHERE cr=? LIMIT 1', [id]).length > 0;
  const norm = s => String(s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();

  const RU_KEYS = 'йцукенгшщзфывапролдячсмитьхъжэбю';
  const EN_KEYS = "qwertyuiopasdfghjklzxcvbnm[];',.";
  function asCode(q) {
    let s = String(q).trim().toLowerCase().replace(/,/g, '.').replace(/ /g, '');
    if (!s) return null;
    const i = RU_KEYS.indexOf(s[0]);
    if (i >= 0 && i < 26 && s.length > 1 && /\d/.test(s[1])) s = EN_KEYS[i] + s.slice(1);
    s = s.toUpperCase();
    if (!/^[A-Z][0-9]{0,2}(\.?[0-9]{0,2})?$/.test(s)) return null;
    if (s.length > 3 && s[3] !== '.') s = s.slice(0, 3) + '.' + s.slice(3);
    return s;
  }

  // ---------------------------------------------------------------- IndexedDB for downloaded guidelines
  let idb = null;
  function idbOpen() {
    return new Promise((res, rej) => {
      const r = indexedDB.open('nmp', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('dl', { keyPath: 'cr' });
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  }
  const idbTx = (mode, fn) => new Promise((res, rej) => {
    const tx = idb.transaction('dl', mode); const st = tx.objectStore('dl'); const r = fn(st);
    tx.oncomplete = () => res(r && r.result); tx.onerror = () => rej(tx.error);
  });

  // ---------------------------------------------------------------- HTML cleaning (same rules as Downloader.java)
  const IMG_PH = '<div class="imgph">Иллюстрация — см. оригинал (кнопка «Сайт» или «PDF»)</div>';
  const MARK = '\u0001IMG\u0001';
  const KEEP = new Set(['p', 'br', 'strong', 'b', 'em', 'i', 'u', 'sup', 'sub', 'ul', 'ol', 'li', 'table', 'thead', 'tbody',
    'tfoot', 'tr', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'caption', 'hr']);
  function clean(html) {
    if (!html || !html.trim()) return '';
    let s = html.replace(/<!--[\s\S]*?-->/g, '');
    s = s.replace(/<(script|style|xml|head|title|object|iframe|svg)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '');
    s = s.replace(/<img\b[^>]*>/gi, MARK);
    s = s.replace(/<\/?[a-zA-Z]+:[a-zA-Z]+\b[^>]*>/g, '');
    s = s.replace(/<(\/?)([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>/g, (m, close, name, attrs) => {
      name = name.toLowerCase();
      if (!KEEP.has(name)) return '';
      if (close) return '</' + name + '>';
      let a = '';
      for (const am of (attrs || '').matchAll(/([a-zA-Z-]+)\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/g)) {
        const k = am[1].toLowerCase(), v = am[2].replace(/^["']|["']$/g, '');
        if ((k === 'colspan' || k === 'rowspan') && /^\d+$/.test(v) && +v > 1) a += ` ${k}="${v}"`;
      }
      return '<' + name + a + (name === 'br' && (attrs || '').trim().endsWith('/') ? '/' : '') + '>';
    });
    for (let i = 0; i < 3; i++) s = s.replace(/<(p|li|strong|b|em|i|u|sup|sub)>(\s|&nbsp;| )*<\/\1>/g, '');
    s = s.split(MARK).join(IMG_PH);
    s = s.replace(/(\s*<br\/?>\s*){3,}/g, '<br/><br/>');
    return s.replace(/[ \t\r\n]+/g, ' ').trim();
  }
  const API = 'https://apicr.minzdrav.gov.ru/api.ashx?op=GetClinrec2&id=';
  async function fetchCr(id) {
    const r = await fetch(API + encodeURIComponent(id), { headers: { Accept: 'application/json' }, cache: 'no-store' });
    if (!r.ok) throw new Error('сервер ответил ' + r.status);
    let text;
    if (r.body && r.body.getReader) {
      const rd = r.body.getReader(), parts = []; let total = 0, last = 0;
      for (;;) {
        const { done, value } = await rd.read();
        if (done) break;
        parts.push(value); total += value.length;
        if (total - last > 256 * 1024) { last = total; window.onDlProgress && window.onDlProgress(id, total); }
      }
      const all = new Uint8Array(total); let o = 0;
      for (const p of parts) { all.set(p, o); o += p.length; }
      text = td.decode(all);
    } else text = await r.text();
    text = text.replace(/data:image\/[a-zA-Z+]+;base64,[A-Za-z0-9+/=\s]+/g, '');
    const d = JSON.parse(text);
    const secs = []; let ord = 0;
    for (const s of (d.obj && d.obj.sections) || []) {
      const sid = s.id || '';
      if (sid === 'doc_whole' || sid === 'doc_title') continue;
      const title = String(s.title || '').trim();
      secs.push({ ord: ord++, sid, title, lvl: /^\d+\.\d+/.test(title) ? 2 : 1, html: s.content == null ? '' : clean(String(s.content)) });
    }
    if (!secs.length) throw new Error('в ответе нет разделов');
    return secs;
  }

  // ---------------------------------------------------------------- window.Native
  const crMkb = id => rows('SELECT cm.code, (SELECT name FROM mkb WHERE code=cm.code LIMIT 1) AS name, ' +
    '(SELECT id FROM mkb WHERE code=cm.code LIMIT 1) AS mid FROM cr_mkb cm WHERE cr=? ORDER BY cm.code', [id]);
  const Native = {
    info() { try { const o = {}; rows('SELECT k, v FROM meta').forEach(r => o[r.k] = r.v); return J(o); } catch (e) { return err(e); } },
    mkbChildren(parent) {
      try {
        return J(+parent > 0
          ? rows('SELECT id, code, name, nchild, ncr FROM mkb WHERE parent=? ORDER BY sort', [+parent])
          : rows('SELECT id, code, name, nchild, ncr FROM mkb WHERE parent IS NULL ORDER BY sort'));
      } catch (e) { return err(e); }
    },
    mkbNode(id) {
      try {
        id = +id;
        const self = rows('SELECT id, code, name, parent, nchild, ncr, orig FROM mkb WHERE id=?', [id]);
        if (!self.length) return '{}';
        const n = self[0], path = [], anc = [];
        let p = n.parent;
        while (p != null) {
          const r = rows('SELECT id, code, name, parent FROM mkb WHERE id=?', [p]);
          if (!r.length) break;
          path.push(r[0]); anc.push(r[0].code); p = r[0].parent;
        }
        // guidelines are shown at the code they list and below it; a 3-character category (J45) also shows its subcodes' guidelines
        const own = [n.code, ...anc];
        const cat = /^[A-Z]\d\d$/.test(n.code || '') ? 1 : 0;
        const sql = 'SELECT cr.id, cr.code, cr.version, cr.name, cr.age, cr.pub, EXISTS(SELECT 1 FROM sec WHERE sec.cr=cr.id) AS off, ' +
          'group_concat(DISTINCT cm.code) AS via FROM cr_mkb cm JOIN cr ON cr.id=cm.cr ' +
          'WHERE cm.code IN (' + own.map(() => '?').join(',') + ') OR (? = 1 AND cm.code LIKE ?) GROUP BY cr.id ORDER BY cr.name';
        return J({ node: n, path: path.reverse(), children: JSON.parse(Native.mkbChildren(id)), cr: rows(sql, [...own, cat, (n.code || '') + '.%']) });
      } catch (e) { return err(e); }
    },
    mkbSearch(q) {
      try {
        const code = asCode(q);
        if (code) return J({ code, items: rows('SELECT id, code, name, nchild, ncr FROM mkb WHERE code LIKE ? ORDER BY length(code), code LIMIT 300', [code + '%']) });
        const words = norm(q).split(' ').filter(Boolean);
        if (!words.length) return J({ items: [] });
        return J({ items: rows('SELECT id, code, name, nchild, ncr FROM mkb WHERE ' + words.map(() => 'q LIKE ?').join(' AND ') +
          ' ORDER BY CASE WHEN code LIKE \'%-%\' OR parent IS NULL THEN 0 ELSE 1 END, sort LIMIT 300', words.map(w => '%' + w + '%')) });
      } catch (e) { return err(e); }
    },
    crList() {
      try {
        return J({
          items: rows('SELECT id, code, version, name, age, pub, mkb, cls, q, EXISTS(SELECT 1 FROM sec WHERE sec.cr=cr.id) AS off FROM cr ORDER BY name'),
          classes: rows('SELECT id, code, name FROM mkb WHERE parent IS NULL ORDER BY sort')
        });
      } catch (e) { return err(e); }
    },
    crInfo(id) {
      try {
        const m = rows('SELECT id, code, version, name, age, ass, pub, mkb FROM cr WHERE id=?', [id]);
        if (!m.length) return '{}';
        return J(Object.assign(m[0], { off: isOffline(id), dl: DL.has(id) }));
      } catch (e) { return err(e); }
    },
    crDoc(id) {
      try {
        const m = rows('SELECT id, code, version, name, age, ass, pub, mkb FROM cr WHERE id=?', [id]);
        if (!m.length) return '{}';
        const off = isOffline(id);
        let sections;
        if (off) sections = rows('SELECT id, ord, sid, title, lvl, html FROM sec WHERE cr=? ORDER BY ord', [id]).map(s => Object.assign(s, { html: inflate(s.html) }));
        else sections = ((DL.get(id) || {}).secs || []).map((s, i) => Object.assign({ id: 1e6 + i }, s));
        return J({ meta: m[0], sections, off, dl: DL.has(id), mkb: crMkb(id) });
      } catch (e) { return err(e); }
    },
    dlList() {
      return J([...DL.values()].map(x => ({ cr: x.cr, at: x.at, bytes: x.bytes })).sort((a, b) => (a.at < b.at ? 1 : -1)));
    },
    dlDelete(id) {
      DL.delete(id);
      idbTx('readwrite', st => st.delete(id)).catch(() => { });
      return '{}';
    },
    download(id) {
      (async () => {
        try {
          const secs = await fetchCr(id);
          const rec = { cr: id, at: new Date().toISOString().slice(0, 10), bytes: secs.reduce((n, s) => n + s.html.length, 0), secs };
          await idbTx('readwrite', st => st.put(rec));
          DL.set(id, rec);
          window.onDl && window.onDl(id, true, '');
        } catch (e) {
          const msg = e instanceof TypeError ? 'нет связи с сервером cr.minzdrav.gov.ru' : (e.message || String(e));
          window.onDl && window.onDl(id, false, msg);
        }
      })();
      return '';
    }
  };

  // ---------------------------------------------------------------- boot
  async function loadDb() {
    const r = await fetch('data/cr.db.gz');
    if (!r.ok) throw new Error('база не найдена (' + r.status + ')');
    const b = new Uint8Array(await r.arrayBuffer());
    return b[0] === 0x1f && b[1] === 0x8b ? fflate.gunzipSync(b) : b; // some servers already ungzip .gz
  }
  async function boot() {
    try {
      const [SQL, bytes] = await Promise.all([initSqlJs({ locateFile: f => 'lib/' + f }), loadDb()]);
      db = new SQL.Database(bytes);
      try {
        idb = await idbOpen();
        const all = await idbTx('readonly', st => st.getAll());
        (all || []).forEach(x => DL.set(x.cr, x));
      } catch (e) { console.warn('IndexedDB недоступна', e); }
      if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => { });
      window.Native = Native;
      const s = document.createElement('script');
      s.src = 'app.js?v=' + (window.APP_REV || '');
      document.body.appendChild(s);
    } catch (e) {
      splash('Не удалось загрузить справочник: ' + String(e.message || e) + '. Проверьте интернет при первом запуске.');
    }
  }
  boot();

  // links to other sites open outside the app
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    const h = a.getAttribute('href');
    if (/^https?:/i.test(h)) { e.preventDefault(); window.open(h, '_blank', 'noopener'); }
  }, true);

  // ---------------------------------------------------------------- install hint (iPhone, not installed yet)
  const standalone = window.navigator.standalone === true || matchMedia('(display-mode: standalone)').matches;
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  function toast(html, key) {
    const t = document.createElement('div'); t.className = 'pwa-toast'; t.innerHTML = html + '<button class="x" aria-label="Закрыть">×</button>';
    t.querySelector('.x').onclick = () => { t.remove(); if (key) try { localStorage.setItem(key, '1'); } catch (e) { } };
    let box = document.querySelector('.pwa-toasts');
    if (!box) { box = document.createElement('div'); box.className = 'pwa-toasts'; document.body.appendChild(box); }
    box.prepend(t); return t;
  }
  if (!standalone) {
    let seen = false; try { seen = !!localStorage.getItem('pwa-hint'); } catch (e) { }
    if (!seen) setTimeout(() => {
      const t = toast(ios
      ? 'Установите справочник на iPhone: нажмите <b>«Поделиться»</b> <svg viewBox="0 0 24 24" class="shr"><path d="M12 15V3M8 7l4-4 4 4M6 11H5v10h14V11h-1"/></svg> и выберите <b>«На экран Домой»</b>. Дальше он работает без интернета.'
      : /android/i.test(navigator.userAgent)
        ? 'Для Android есть приложение: <a href="download/SpravochnikNMP.apk">скачать APK</a>. Или установите эту версию: меню Chrome → <b>«Установить приложение»</b>.'
        : 'Установите справочник: меню браузера → <b>«Установить приложение»</b> или <b>«Добавить на главный экран»</b>. Дальше он работает без интернета.', 'pwa-hint');
      const sync = () => { t.hidden = !/^#?(home)?$/.test(location.hash); };
      sync(); window.addEventListener('hashchange', sync);
    }, 1200);
  }

  // ---------------------------------------------------------------- service worker: offline + updates
  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    navigator.serviceWorker.register('sw.js').then(reg => {
      const offer = w => {
        const t = toast('Доступна новая версия справочника. <a href="#" class="upd">Обновить</a>');
        t.querySelector('.upd').onclick = ev => { ev.preventDefault(); window.__swUpdating = true; w.postMessage('skipWaiting'); };
      };
      if (reg.waiting && navigator.serviceWorker.controller) offer(reg.waiting);
      reg.addEventListener('updatefound', () => {
        const w = reg.installing;
        w && w.addEventListener('statechange', () => { if (w.state === 'installed' && navigator.serviceWorker.controller) offer(w); });
      });
      // check for updates whenever the app is brought back to the screen
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') reg.update().catch(() => { }); });
    }).catch(e => console.warn('SW', e));
    let reloading = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => { if (!reloading && window.__swUpdating) { reloading = true; location.reload(); } });
  }
})();
