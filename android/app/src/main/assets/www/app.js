'use strict';
/* КлинРек — UI. Data comes from window.Native (Java bridge, see Api.java). */

// ---------------------------------------------------------------- helpers
const $ = (s, r = document) => r.querySelector(s);
const view = $('#view');
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const call = (fn, ...a) => {
  try {
    if (!window.Native) return { error: 'no native' };
    return JSON.parse(window.Native[fn](...a));
  } catch (e) { return { error: String(e) }; }
};
const debounce = (f, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => f(...a), ms); }; };
const norm = s => String(s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
const ENDINGS = 'иями ями ами ого его ему ому ыми ими ая яя ое ее ые ие ый ий ой ей ую юю ых их ом ем ам ям ах ях ия ии ию ья ье ью ов ев а я о е ы и у ю ь й'
  .split(' ').sort((a, b) => b.length - a.length);
function stem(w) {
  if (w.length < 4 || !/^\p{L}+$/u.test(w)) return w;
  for (const e of ENDINGS) if (w.endsWith(e) && w.length - e.length >= 3) return w.slice(0, -e.length);
  return w;
}
const terms = s => [...new Set(norm(s).split(/[^\p{L}\p{N}]+/u).filter(w => w.length >= 2 || /^\d$/.test(w)).map(stem))];
const AGE = { 1: 'Взрослые', 2: 'Дети', 3: 'Взрослые и дети' };
const fmtDate = iso => { if (!iso) return ''; const [y, m, d] = iso.split('-'); return `${d}.${m}.${y}`; };
const LS = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } }
};
const RU_KEYS = 'йцукенгшщзфывапролдячсмить';
const EN_KEYS = 'qwertyuiopasdfghjklzxcvbnm';
function asCode(q) {
  let s = String(q || '').trim().toLowerCase().replace(/,/g, '.').replace(/\s/g, '');
  if (!s) return null;
  const i = RU_KEYS.indexOf(s[0]);
  if (i >= 0 && s.length > 1 && /\d/.test(s[1])) s = EN_KEYS[i] + s.slice(1);
  s = s.toUpperCase();
  if (!/^[A-Z]\d{0,2}(\.?\d{0,2})?$/.test(s)) return null;
  if (s.length > 3 && s[3] !== '.') s = s.slice(0, 3) + '.' + s.slice(3);
  return s;
}
function hlText(text, ts) {
  const t = esc(text);
  if (!ts || !ts.length) return t;
  if (ts.length > 1) { const pr = phraseRe(ts); if (pr.test(t)) return t.replace(phraseRe(ts), '<mark>$1</mark>'); }
  return t.replace(termRe(ts), '<mark>$1</mark>');
}
const reEsc = t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/е/g, '[её]');
function termRe(ts) {
  return new RegExp('(?<![\\p{L}\\p{N}])((?:' + ts.map(reEsc).join('|') + ')[\\p{L}\\p{N}]*)', 'giu');
}
function phraseRe(ts) {
  return new RegExp('(?<![\\p{L}\\p{N}])(' + ts.map(t => reEsc(t) + '[\\p{L}\\p{N}]*').join('[^\\p{L}\\p{N}]+') + ')', 'giu');
}

// ---------------------------------------------------------------- state
const S = { scroll: {}, q: '', tab: {}, mkbQ: '', open: {} };
let fs = LS.get('fs', 16);
document.documentElement.style.setProperty('--fs', fs + 'px');
let kgW = LS.get('kg', '');

// ---------------------------------------------------------------- navigation
const stack = [];
let cur = null;
function go(h) { if (location.hash === h) route(); else location.hash = h; }
window.appBack = function () {
  const toc = $('.toc'); if (toc) { toc.remove(); return true; }
  if (stack.length > 1) { history.back(); return true; }
  return false;
};
$('#backBtn').onclick = () => window.appBack() || go('#home');
$('#infoBtn').onclick = () => go('#about');
// Препараты: поиск по инструкциям и проверка взаимодействий (content_drugs.js, данные — ветка drugs)
const DM = window.DrugsModule ? window.DrugsModule({
  view, go,
  setTitle: t => setTitle(t, false),   // препараты открываются с главной — стрелка «назад» всегда
  fetchText: url => fetch(url).then(r => r.ok ? r.text() : Promise.reject(new Error('HTTP ' + r.status)))
}) : null;
if (DM) setTimeout(() => DM.preload(), 1500);
// состояние аналитики и экрана «Использование» (объявлено до первого route())
const AN = { last: '', lastAt: 0, sq: {} };
let USAGE_DAYS = 30;
window.addEventListener('hashchange', () => {
  if (cur) S.scroll[cur] = window.scrollY;
  const h = location.hash || '#home';
  if (stack.length > 1 && stack[stack.length - 2] === h) stack.pop(); else stack.push(h);
  route();
});
function setTitle(t, isRoot) { $('#title').textContent = t; $('#backBtn').hidden = !!isRoot; }
function setTab(t) { document.querySelectorAll('#tabs a').forEach(a => a.classList.toggle('on', a.dataset.tab === t)); }
function route() {
  if (typeof view !== 'undefined' && view) { view.ontouchstart = null; view.ontouchend = null; }
  if (window.LECT && !(location.hash || '').startsWith('#lecture/' + LECT.key + '?') && location.hash !== '#lecture/' + LECT.key) { LECT.audio.pause(); }
  const h = location.hash || '#home';
  cur = h;
  const [path, qs] = h.slice(1).split('?');
  const parts = path.split('/');
  const params = new URLSearchParams(qs || '');
  document.body.classList.toggle('doc', parts[0] === 'doc');
  document.body.classList.toggle('nohead', !parts[0] || parts[0] === 'home' || (parts[0] === 'rec' && !parts[1]));
  switch (parts[0]) {
    case 'rec': setTab('rec'); parts[1] ? topicPage(parts[1]) : recPage(); break;
    case 'd': setTab('rec'); disease(parts[1], parts[2]); break;
    case 'mkb': setTab('home'); parts[1] ? mkbNode(+parts[1]) : mkbRoot(params.get('q')); break;
    case 'calc': setTab('home'); calcPage(parts[1]); break;
    case 'route': setTab('home'); routeWizard(); break;
    case 'learn': setTab('learn'); learnPage(); break;
    case 'course': setTab('learn'); coursePage(parts[1], parts[2]); break;
    case 'report': setTab('stats'); LS.set('statsTab', 'report'); reportPage(); break;
    case 'stats': go('#' + (['usage', 'krnew', 'report'].includes(LS.get('statsTab', '')) ? LS.get('statsTab') : 'usage')); return;
    case 'lecture': setTab('learn'); parts[2] === 'test' ? lectureTest(parts[1]) : lecturePage(parts[1]); break;
    case 'cr': setTab(''); crPage(parts[1]); break;
    case 'about': setTab(''); about(); break;
    case 'krnew': setTab('stats'); LS.set('statsTab', 'krnew'); krPage(); break;
    case 'usage': setTab('stats'); LS.set('statsTab', 'usage'); usagePage(); break;
    case 'doc': doc(parts[1], parts[2], params.get('h') || ''); return;
    case 'drugs': case 'drug': case 'ix': setTab('home'); if (DM) DM.route(parts, params); else go('#home'); break;
    default: setTab('home'); home();
  }
  window.scrollTo(0, S.scroll[h] || 0);
  try { anView(parts); } catch (e) {}
  try { statsTabSync(); } catch (e) {}
}

// ---------------------------------------------------------------- data
const TOPICS = [
  { k: 'shock', t: 'Шоки', ids: ['shock', 'angio'], c: 'red', i: 'shock' },
  { k: 'cardio', t: 'Кардиология', ids: ['ag', 'oks', 'ibs', 'ar', 'hsn', 'dlp'], c: 'rose', i: 'oks' },
  { k: 'neuro', t: 'Неврология', ids: ['onmk', 'bol'], c: 'violet', i: 'onmk' },
  { k: 'pulm', t: 'Пульмонология', ids: ['astma', 'hobl'], c: 'blue', i: 'astma' },
  { k: 'inf', t: 'Инфекционные болезни', ids: ['pnevm', 'orvi', 'sinus', 'angina'], c: 'green', i: 'inf' },
  { k: 'preg', t: 'Беременные', ids: ['agb', 'preg_back', 'preg_orvi', 'preg_pnevm', 'preg_uti'], c: 'pink', i: 'agb' },
  { k: 'uro', t: 'Урология', ids: ['uti', 'colic'], c: 'teal', i: 'uro' },
  { k: 'endo', t: 'Эндокринология', ids: ['sd'], c: 'amber', i: 'sd' }
];
const ROUTE_TABLES = ['r_tmn', 'r_onmk', 'r_cardio', 'r_obst', 'r_kids'];
const TICON = { route: 'M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11zM12 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4z', uro: 'M9 3c-3 0-5 3-5 7s2 7 5 7c1.5 0 2-1 2-2.5V12c0-1-.5-1.5-1.5-1.5M15 3c3 0 5 3 5 7s-2 7-5 7c-1.5 0-2-1-2-2.5V12c0-1 .5-1.5 1.5-1.5M11 17v4M13 17v4', inf: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1' };
const plural = (n, f) => n + ' ' + (n % 10 === 1 && n % 100 !== 11 ? f[0] : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? f[1] : f[2]);
const ORDER = TOPICS.flatMap(x => x.ids).concat(ROUTE_TABLES);
const DIS = (window.FELD || []).slice().sort((a, b) => (ORDER.indexOf(a.id) + 1 || 99) - (ORDER.indexOf(b.id) + 1 || 99));
const byId = {}; DIS.forEach(d => byId[d.id] = d);
const SCHEME_BY_CR = {}; DIS.forEach(d => d.crs.forEach(c => (SCHEME_BY_CR[c] = SCHEME_BY_CR[c] || []).push(d.id)));
let CRN = null, CRM = null;
function crData() {
  if (!CRM) { CRM = {}; CRN = {}; const r = call('crList'); (r.items || []).forEach(x => { CRM[x.id] = x; CRN[x.id] = x.name; }); }
  return CRM;
}
function crNames() { crData(); return CRN; }
let DL = null;
function dlSet() { if (!DL) { DL = new Set(); const r = call('dlList'); (Array.isArray(r) ? r : []).forEach(x => DL.add(x.cr)); } return DL; }
const ICON = {
  ag: 'M3 12h4l2-5 4 10 2-5h6', oks: 'M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10z',
  ibs: 'M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10zM9 11h6',
  hsn: 'M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10zM12 8v6',
  astma: 'M12 3v8M8 11c-3 0-4 3-4 6 0 2 1 3 3 3s3-2 3-4v-5M16 11c3 0 4 3 4 6 0 2-1 3-3 3s-3-2-3-4v-5',
  hobl: 'M12 3v8M8 11c-3 0-4 3-4 6 0 2 1 3 3 3s3-2 3-4v-5M16 11c3 0 4 3 4 6 0 2-1 3-3 3s-3-2-3-4v-5',
  pnevm: 'M12 3v8M8 11c-3 0-4 3-4 6 0 2 1 3 3 3s3-2 3-4v-5M16 11c3 0 4 3 4 6 0 2-1 3-3 3s-3-2-3-4v-5',
  orvi: 'M14 4a5 5 0 0 1 0 10H8a4 4 0 0 1 0-8 5 5 0 0 1 6-2zM8 18l-1 2M12 18l-1 2M16 18l-1 2',
  sinus: 'M12 4v9c0 2-2 3-4 3M12 13c0 2 2 3 4 3M7 8h2M15 8h2',
  angina: 'M8 4h8l-1 7a3 3 0 0 1-6 0zM12 14v6M9 20h6',
  bol: 'M12 3v18M9 6h6M9 10h6M9 14h6M9 18h6',
  agb: 'M12 4a2 2 0 1 1 0 .1M10 8h4l1 5c2 1 3 3 3 5v2H6v-2c0-2 1-4 3-5zM3 12h3',
  sd: 'M12 3c3 4 6 7 6 11a6 6 0 0 1-12 0c0-4 3-7 6-11zM9 15h6',
  ar: 'M2 12h4l2-4 3 9 2-7 2 4h7',
  shock: 'M13 2L4 14h7l-1 8 9-12h-7z',
  onmk: 'M9 4a4 4 0 0 0-4 4 3 3 0 0 0-1 5 3 3 0 0 0 3 4 3 3 0 0 0 5 1V4a3 3 0 0 0-3 0zM15 4a4 4 0 0 1 4 4 3 3 0 0 1 1 5 3 3 0 0 1-3 4 3 3 0 0 1-5 1',
  angio: 'M12 3a7 8 0 0 1 7 8c0 5-3 9-7 9s-7-4-7-9a7 8 0 0 1 7-8zM9 11h.01M15 11h.01M9 15c2 1.5 4 1.5 6 0',
  preg_back: 'M12 4a2 2 0 1 1 0 .1M10 8h4l1 5c2 1 3 3 3 5v2H6v-2c0-2 1-4 3-5zM17 9c2 1 3 3 3 5',
  preg_orvi: 'M12 4a2 2 0 1 1 0 .1M10 8h4l1 5c2 1 3 3 3 5v2H6v-2c0-2 1-4 3-5zM19 4v5M17 6h4',
  preg_pnevm: 'M12 3v8M8 11c-3 0-4 3-4 6 0 2 1 3 3 3s3-2 3-4v-5M16 11c3 0 4 3 4 6 0 2-1 3-3 3s-3-2-3-4v-5',
  preg_uti: 'M9 3c-3 0-5 3-5 7s2 7 5 7c1.5 0 2-1 2-2.5V12c0-1-.5-1.5-1.5-1.5M15 3c3 0 5 3 5 7s-2 7-5 7c-1.5 0-2-1-2-2.5V12c0-1 .5-1.5 1.5-1.5M11 17v4M13 17v4',
  uti: 'M9 3c-3 0-5 3-5 7s2 7 5 7c1.5 0 2-1 2-2.5V12c0-1-.5-1.5-1.5-1.5M15 3c3 0 5 3 5 7s-2 7-5 7c-1.5 0-2-1-2-2.5V12c0-1 .5-1.5 1.5-1.5M11 17v4M13 17v4',
  colic: 'M13 2L4 14h7l-1 8 9-12h-7z',
  r_tmn: 'M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11zM12 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4z', r_onmk: 'M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11zM12 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4z', r_cardio: 'M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11zM12 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4z', r_obst: 'M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11zM12 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4z', r_kids: 'M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11zM12 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4z'
};

// ---------------------------------------------------------------- home (tools)
const TOOLS = [
  { h: '#calc/bmi', t: 'Индекс массы тела', s: 'ИМТ, степень ожирения', i: 'M6 20h12M8 20V9h8v11M12 9V5M9 5h6' },
  { h: '#calc/gcs', t: 'Шкала комы Глазго', s: 'уровень сознания E·V·M', i: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z' },
  { h: '#calc/shock', t: 'Индекс Альговера', s: 'шоковый индекс, кровопотеря', i: 'M12 3s6 7 6 11a6 6 0 0 1-12 0c0-4 6-11 6-11zM9 14h6' },
  { h: '#calc/vas', t: 'Шкала боли (ВАШ)', s: '0–10, интенсивность боли', i: 'M4 12h16M4 12l3-3M4 12l3 3M20 12l-3-3M20 12l-3 3' },
  { h: '#calc/skin', t: 'Кожные элементы', s: 'определитель морфологии сыпи', i: 'M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM20 20l-4.5-4.5M8 9h.01M12 8.5h.01M10.5 12.5h.01' }
];
function home() {
  setTitle('Справочник фельдшера НМП', true);
  view.innerHTML = `<div class="homefill">
    <a class="mkbcard routecard" href="#route">
      <div class="mk-h"><svg viewBox="0 0 24 24"><path d="M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z"/><path d="M12 7v6M9 10h6"/></svg>
        <div><div class="tt">Дежурные стационары</div><div class="ts">куда везти: повод, район или адрес</div></div><span class="chev">›</span></div>
    </a>
    ${DM ? `<div class="qrow">
      <a class="qtile" href="#drugs"><svg viewBox="0 0 24 24"><path d="M10.5 20.5l10-10a4.95 4.95 0 0 0-7-7l-10 10a4.95 4.95 0 0 0 7 7zM8.5 8.5l7 7"/></svg><span><b>Препараты</b><small>инструкции, дозы</small></span></a>
      <a class="qtile" href="#ix"><svg viewBox="0 0 24 24"><path d="M4 8h13l-3-3M20 16H7l3 3"/></svg><span><b>Взаимодействия</b><small>проверка пар</small></span></a>
    </div>` : ''}
    <div class="mkbmini">
      <a class="mm-h" href="#mkb"><svg viewBox="0 0 24 24"><path d="M5 4h10l4 4v12H5z"/><path d="M9 12h6M9 16h6M9 8h3"/></svg><b>МКБ-10</b><small>рубрики и КР по коду</small><span class="chev">›</span></a>
      <div class="field"><svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/></svg>
        <input id="hq" type="search" placeholder="Поиск по коду или нозологии" autocomplete="off" spellcheck="false" enterkeyhint="search"></div>
    </div>
    <div class="sec-h">Калькуляторы и шкалы</div>
    <div class="tools">${TOOLS.map(x => `<a class="tool" href="${x.h}"><svg viewBox="0 0 24 24"><path d="${x.i}"/></svg><span><span class="tt">${esc(x.t)}</span><span class="ts">${esc(x.s)}</span></span></a>`).join('')}</div>
  </div>`;
  homeFit();
  const inp = $('#hq');
  const goSearch = () => { const v = inp.value.trim(); if (v) { S.mkbQ = v; go('#mkb'); } };
  inp.addEventListener('keydown', e => { if (e.key === 'Enter') goSearch(); });
  inp.addEventListener('input', debounce(() => { if (inp.value.trim().length >= 2) goSearch(); }, 700));
}

// ---------------------------------------------------------------- recommendations (by topic)
function disText(d) {
  if (!d._t) d._t = norm(JSON.stringify(d.sections).replace(/"[a-z]+":/g, ' ') + ' ' + d.title + ' ' + d.sub);
  return d._t;
}
function recPage() {
  setTitle('Справочник', true);
  const q = S.q;
  view.innerHTML = `<div class="searchbar"><div class="field">
      <svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/></svg>
      <input id="rq" type="search" placeholder="Поиск: болезнь или препарат" value="${esc(q)}" autocomplete="off" spellcheck="false">
      <button class="clr" ${q ? '' : 'hidden'}>×</button></div></div>
    <div id="rres"></div>
    <p class="disc">Для фельдшера неотложной помощи: угроза жизни — вызов СМП. <span class="onebadge" style="margin:0">ОДИН ИЗ</span> — выбрать один препарат из группы. <span class="src kr">КР</span> — из текста клинической рекомендации, <span class="src ins">инстр.</span> — из инструкции к препарату. Перед назначением сверяйтесь с инструкцией и учитывайте противопоказания.</p>`;
  const inp = $('#rq'), clr = $('.clr');
  const run = () => { S.q = inp.value; clr.hidden = !inp.value; renderRec(); };
  inp.addEventListener('input', debounce(run, 150));
  clr.onclick = () => { inp.value = ''; run(); inp.focus(); };
  renderRec();
}
function renderRec() {
  const box = $('#rres'); if (!box) return;
  const ts = terms(S.q);
  if (!ts.length) {
    box.innerHTML = `<div class="tiles">${TOPICS.map(tp => `<a class="tile t-${tp.c}" href="#rec/${tp.k}">
      <span class="ti"><svg viewBox="0 0 24 24"><path d="${TICON[tp.i] || ICON[tp.i]}"/></svg></span>
      <b>${esc(tp.t)}</b>
      <small>${tp.ids.map(i => byId[i]).filter(Boolean).map(d => esc(d.title)).join(' · ')}</small>
      <span class="cnt">${plural(tp.ids.length, ['раздел', 'раздела', 'разделов'])}</span></a>`).join('')}</div>`;
    return;
  }
  const match = d => ts.every(t => disText(d).includes(t));
  let h = '';
  for (const tp of TOPICS) {
    const list = tp.ids.map(i => byId[i]).filter(Boolean).filter(match);
    if (!list.length) continue;
    h += `<div class="topic t-${tp.c}"><div class="th">${esc(tp.t)}</div>${list.map(d => {
      const hit = ts.length && !ts.every(t => norm(d.title + ' ' + d.sub).includes(t)) ? '<span class="hit">найдено в схеме</span>' : '';
      return `<a class="trow" href="#d/${d.id}"><span class="ti"><svg viewBox="0 0 24 24"><path d="${ICON[d.id] || ICON.bol}"/></svg></span>
        <span class="nm"><b>${esc(d.title)}</b><small>${esc(d.sub)}</small>${hit}</span><span class="chev">›</span></a>`;
    }).join('')}</div>`;
  }
  box.innerHTML = h || '<div class="empty">Ничего не найдено</div>';
  anSearch('rec', S.q, (h.match(/class="trow"/g) || []).length);
}

function topicPage(k) {
  const tp = TOPICS.find(x => x.k === k);
  if (!tp) return go('#rec');
  setTitle(tp.t, false);
  view.innerHTML = `<div class="topic t-${tp.c} solo">${tp.ids.map(i => byId[i]).filter(Boolean).map(d =>
    `<a class="trow" href="#d/${d.id}"><span class="ti"><svg viewBox="0 0 24 24"><path d="${ICON[d.id] || ICON.bol}"/></svg></span>
      <span class="nm"><b>${esc(d.title)}</b><small>${esc(d.sub)}</small></span><span class="chev">›</span></a>`).join('')}</div>`;
}

// ---------------------------------------------------------------- маршрутизация: мастер (данные и правила — content_route.js)
const RW_DAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'];
function dutyNow() {
  const n = new Date(); if (n.getHours() < 8) n.setDate(n.getDate() - 1);
  return { d: (n.getDay() + 6) % 7, date: n };
}
const RW = { st: null };
const RW_AO = { len: 'Ленинский АО', cen: 'Центральный АО', kal: 'Калининский АО', vos: 'Восточный АО' };
let ADDR_IX = null;
function addrIndex() {
  if (!ADDR_IX) ADDR_IX = (window.TMN_ADDR || []).map(([n, spec]) => {
    const parts = spec.includes(':') ? spec.split('|').map(x => { const [o, hs] = x.split(':'); return [o, hs.split(',')]; }) : null;
    return { n, w: rwNorm(n).split(' '), one: parts ? null : spec, parts };
  });
  return ADDR_IX;
}
const hnum = h => parseInt(h, 10) || 0;
function addrHouse(st, h) {
  if (st.one) return { t: st.one };
  const H = h.toUpperCase().replace(/КОРПУС|КОРП\.?/g, 'К').replace(/СТРОЕНИЕ|СТР\.?/g, 'С').replace(/\s+/g, '');
  for (const [o, hs] of st.parts) if (hs.includes(H)) return { t: o };
  const n = hnum(H); if (!n) return null;
  const same = new Set(); st.parts.forEach(([o, hs]) => hs.forEach(x => { if (hnum(x) === n) same.add(o); }));
  if (same.size === 1) return { t: [...same][0] };
  let best = null;
  st.parts.forEach(([o, hs]) => hs.forEach(x => { const m = hnum(x); if (m && m % 2 === n % 2) { const dd = Math.abs(m - n); if (!best || dd < best.d) best = { d: dd, t: o, h: x }; } }));
  return best && best.d <= 20 ? { t: best.t, near: best.h } : null;
}
function addrSearch(q) {
  const m = q.trim().match(/^(.*?)[,\s]+(?:д\.?|дом)?\s*(\d+\s*[а-яёa-z]?(?:\s*(?:\/|к|корп\.?|корпус|с|стр\.?)\s*\d+[а-яёa-z]?)?)$/i);
  const house = m ? m[2] : '';
  const words = rwNorm(m ? m[1] : q).split(' ').filter(w => w && !['ул', 'улица', 'пр', 'проезд', 'пер', 'переулок', 'д', 'дом', 'г', 'тюмень'].includes(w));
  if (!words.length) return [];
  const hits = addrIndex().filter(s => words.every(w => s.w.some(x => x.startsWith(w))))
    .sort((a, b) => (b.w.some(x => x === words[0]) - a.w.some(x => x === words[0])) || a.n.length - b.n.length).slice(0, 8);
  return hits.map(s => {
    if (house) {
      const r = addrHouse(s, house);
      if (r) return { s, h: house, t: r.t, sub: r.near ? `по соседнему дому № ${r.near} — проверьте` : '' };
      return { s, h: house, t: '', sub: 'дом на границе округов не найден — выберите район вручную' };
    }
    if (s.one) return { s, h: '', t: s.one, sub: '' };
    return { s, h: '', t: '', sub: 'улица в нескольких округах (' + s.parts.map(p => RW_AO[p[0]]).join(', ') + ') — введите номер дома' };
  });
}
const rwNorm = t => String(t).toLowerCase().replace(/ё/g, 'е').replace(/[^a-zа-я0-9]+/g, ' ').trim();
function routeWizard() {
  const R = window.ROUTE;
  setTitle('Дежурные стационары', false);
  if (!RW.st) { const sv = LS.get('route', {}); RW.st = { age: sv.age || 'ad', p: '', t: sv.t || '', x: {}, d: null, open: '' }; }
  const s = RW.st, now = dutyNow(), d = s.d == null ? now.d : s.d;
  const dd = dt => String(dt.getDate()).padStart(2, '0') + '.' + String(dt.getMonth() + 1).padStart(2, '0');
  const nx = new Date(now.date); nx.setDate(nx.getDate() + 1);
  const label = (list, k) => { for (const g of list) for (const o of g[1]) if (o[0] === k) return o[1]; return ''; };
  const kid = s.age !== 'ad';
  const plist = !kid ? R.P_AD : (s.age === 'ch' || s.age === 'kid' ? [...R.P_CH, R.P_GIRL] : R.P_CH);
  if (s.p && !label(plist, s.p)) s.p = '';
  const chip = (k, v, on, t, sub) => `<a class="rwc${on ? ' on' : ''}" data-k="${k}" data-v="${esc(v)}">${esc(t)}${sub ? `<small>${esc(sub)}</small>` : ''}</a>`;
  const q = (n, h, body, done) => `<div class="rwq${done ? ' done' : ''}"><div class="rwh"><span class="rwn">${n}</span>${h}</div>${body}</div>`;
  const summ = (k, t) => `<a class="rwsum" data-k="open" data-v="${k}"><b>${esc(t)}</b><span>изменить</span></a>`;
  let h = '';
  h += q(1, 'Пациент', `<div class="rwab">${chip('age', 'ad', !kid, 'Взрослые')}${chip('age', 'kid', kid, 'Дети')}</div>
    ${kid ? `<div class="rwsub"><div class="rwsubh">Возраст ребёнка</div><div class="rwcs rwkid">${R.AGES.slice(1).reverse().map(o => chip('age', o[0], s.age === o[0], o[1])).join('')}</div></div>` : ''}`, true);
  const ddBox = (k, groups, kw, ph) => `<div class="rwdd${s.open === k ? ' open' : ''}" data-dd="${k}"><div class="rwddf"><svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/></svg>
      <input class="rwddq" type="search" placeholder="${esc(ph)}" autocomplete="off" spellcheck="false"><span class="rwddar">▾</span></div>
      <div class="rwlist">${groups.map(g => `<div class="rwgrp"><div class="rwg">${esc(g[0])}</div>${g[1].map(o =>
        `<a class="rwli${s[k] === o[0] ? ' on' : ''}" data-k="${k}" data-v="${o[0]}" data-s="${esc(rwNorm([o[1], o[2] || '', g[0], kw[o[0]] || ''].join(' ')))}">${esc(o[1])}${o[2] ? `<small>${esc(o[2])}</small>` : ''}</a>`).join('')}</div>`).join('')}
        <div class="rwnone" hidden>Ничего не найдено — попробуйте другое слово</div></div></div>`;
  h += q(2, 'Повод', s.p && s.open !== 'p' ? summ('p', label(plist, s.p)) : ddBox('p', plist, R.KW, 'Поиск: инфаркт, инсульт, роды…'), !!s.p);
  h += q(3, 'Район вызова', s.t && s.open !== 't' ? summ('t', label(R.TER, s.t) + (s.addr && RW_AO[s.t] ? ' · ' + s.addr : '')) :
    `<div class="rwaddr"><div class="rwddf"><svg viewBox="0 0 24 24"><path d="M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2"/></svg>
      <input id="rwAddr" type="search" placeholder="Адрес в Тюмени: улица и дом" autocomplete="off" spellcheck="false"></div><div class="rwasug"></div></div>
     <div class="rwor">или район / муниципальный округ</div>` + ddBox('t', R.TER, R.KW_T, 'Поиск: Калининский, Ишим, тракт…'), !!s.t);
  let res = null;
  if (s.p && s.t) {
    res = R.find({ age: s.age, p: s.p, t: s.t, x: s.x, d });
    Object.keys(s.x).forEach(k => { const l = (s.xl || {})[k]; if (l) h += q('✓', esc(l.q), `<a class="rwsum" data-k="xdel" data-v="${k}"><b>${esc(l.a)}</b><span>изменить</span></a>`, true); });
    if (res.ask) h += q('?', esc(res.ask.q), `<div class="rwcs">${res.ask.opts.map(o => chip('x:' + res.ask.k, o[0], s.x[res.ask.k] === o[0], o[1])).join('')}</div>`);
  }
  const cap = d === now.d ? `Дежурные сутки: ${RW_DAYS[d]} ${dd(now.date)} 08:00 — ${RW_DAYS[(d + 1) % 7]} ${dd(nx)} 08:00`
    : `Выбран другой день: ${RW_DAYS[d]} 08:00 — ${RW_DAYS[(d + 1) % 7]} 08:00`;
  h += q(4, 'День', `<div class="rwdays">${RW_DAYS.map((x, i) => `<a class="rwc${i === d ? ' on' : ''}" data-k="d" data-v="${i}">${x}${i === now.d ? '<small>сейчас</small>' : ''}</a>`).join('')}</div>
    <div class="rwcap">${cap}${res && res.res && !res.ask && !res.day ? ' · <i>на этот повод день не влияет</i>' : ''}</div>`, true);
  if (res && res.res && !res.ask) {
    h += `<div class="rwres">${res.res.map(x => { const H = R.H[x.h] || ['?', '']; return `<div class="rwto"><div class="rwk">Везти</div><div class="rwnm">${esc(H[0])}</div>${H[1] ? `<div class="rwad">${esc(H[1])}</div>` : ''}${x.why ? `<div class="rwwhy">${esc(x.why)}</div>` : ''}</div>`; }).join('')}
      ${(res.warn || []).map(w => `<div class="rwwarn">${esc(w)}</div>`).join('')}
      ${(res.note || []).length ? `<ul class="rwnote">${res.note.map(n => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
      ${res.phone ? `<div class="rwph">${esc(res.phone)}</div>` : ''}
      ${res.src ? `<div class="csrc">Основание: ${esc(res.src)}</div>` : ''}</div>`;
  } else if (res && res.needAge) h += `<div class="rwempty">Укажите возраст ребёнка — от него зависит стационар.</div>`;
  else if (!res) h += `<div class="rwempty">Выберите повод и район — здесь появится стационар.</div>`;
  h += `<div class="sec-h">Таблицы приказов</div><div class="topic t-slate">${ROUTE_TABLES.map(i => byId[i]).filter(Boolean).map(x =>
    `<a class="trow" href="#d/${x.id}"><span class="nm"><b>${esc(x.title)}</b><small>${esc(x.sub)}</small></span><span class="chev">›</span></a>`).join('')}</div>
    <p class="disc">Маршруты — по приказам ДЗ Тюменской области, загруженным в справочник. Округ по адресу — по границам и адресам OpenStreetMap (© участники OpenStreetMap), возможны неточности на границах округов. При расхождении с распоряжением старшего врача или диспетчера — действует распоряжение.</p>`;
  view.innerHTML = `<div class="rw">${h}</div>`;
  view.querySelectorAll('.rw [data-k]').forEach(el => el.onclick = () => {
    const k = el.dataset.k, v = el.dataset.v;
    if (k === 'open') s.open = v;
    else if (k === 'age') { s.age = v; }
    else if (k === 'p') { s.p = v; s.open = ''; s.x = {}; }
    else if (k === 't') { s.t = v; s.open = ''; s.x = {}; s.addr = ''; }
    else if (k === 'd') s.d = +v === now.d ? null : +v;
    else if (k === 'xdel') delete s.x[v];
    else if (k.startsWith('x:')) { const kk = k.slice(2); s.x[kk] = v; s.xl = s.xl || {}; s.xl[kk] = { q: el.closest('.rwq').querySelector('.rwh').textContent.replace(/^\?/, ''), a: el.textContent }; }
    LS.set('route', { age: s.age, t: s.t });
    const y = window.scrollY; routeWizard(); window.scrollTo(0, y);
    if (k === 'p' || k === 't' || k.startsWith('x:')) { const r = $('.rwres') || $('.rwq:not(.done)'); if (r) r.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
  });
  const ai = $('#rwAddr');
  if (ai) {
    const box = $('.rwasug');
    const show = () => {
      const v = ai.value.trim();
      if (v.length < 2) { box.innerHTML = ''; return; }
      const L = addrSearch(v);
      box.innerHTML = L.length ? L.map((x, i) => `<a class="rwas${x.t ? '' : ' no'}" data-i="${i}"><b>${esc(x.s.n)}${x.h ? ', ' + esc(x.h) : ''}</b>${x.t ? `<span class="rwao">${RW_AO[x.t]}</span>` : ''}${x.sub ? `<small>${esc(x.sub)}</small>` : ''}</a>`).join('')
        : '<div class="rwnone">Улица не найдена — выберите район вручную</div>';
      box.querySelectorAll('.rwas').forEach(el => el.onclick = () => {
        const x = L[+el.dataset.i]; if (!x.t) { if (!x.h) { ai.value = x.s.n + ' '; ai.focus(); show(); } return; }
        s.t = x.t; s.addr = x.s.n + (x.h ? ', ' + x.h : ''); s.open = ''; s.x = {};
        LS.set('route', { age: s.age, t: s.t }); routeWizard();
        const r = $('.rwres') || $('.rwq:not(.done)'); if (r) r.scrollIntoView({ block: 'nearest' });
      });
    };
    ai.addEventListener('input', debounce(show, 120));
  }
  view.querySelectorAll('.rwdd').forEach(ddEl => {
    const pq = ddEl.querySelector('.rwddq'), none = ddEl.querySelector('.rwnone');
    const filt = () => {
      const ws = rwNorm(pq.value).split(' ').filter(Boolean);
      let any = false;
      ddEl.querySelectorAll('.rwgrp').forEach(g => {
        let n = 0;
        g.querySelectorAll('.rwli').forEach(li => { const hay = ' ' + li.dataset.s; const ok = ws.every(w => hay.includes(' ' + w)); li.hidden = !ok; if (ok) n++; });
        g.hidden = !n; if (n) any = true;
      });
      none.hidden = any;
    };
    pq.addEventListener('focus', () => ddEl.classList.add('open'));
    pq.addEventListener('input', () => { ddEl.classList.add('open'); filt(); });
    ddEl.querySelector('.rwddar').onclick = () => ddEl.classList.toggle('open');
    if (s.open === ddEl.dataset.dd) { s.open = ''; setTimeout(() => pq.focus(), 50); }
  });
}

// ---------------------------------------------------------------- обучение и опросы (лента: learn.json на сайте)
function sha256(s) {
  const K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
  const b = Array.from(new TextEncoder().encode(s)), l = b.length * 8;
  b.push(0x80); while (b.length % 64 !== 56) b.push(0);
  for (let i = 7; i >= 0; i--) b.push(i > 3 ? 0 : (l >>> (i * 8)) & 255);
  let [h0, h1, h2, h3, h4, h5, h6, h7] = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const w = new Array(64), r = (x, n) => (x >>> n) | (x << (32 - n));
  for (let o = 0; o < b.length; o += 64) {
    for (let i = 0; i < 16; i++) w[i] = (b[o + 4 * i] << 24) | (b[o + 4 * i + 1] << 16) | (b[o + 4 * i + 2] << 8) | b[o + 4 * i + 3];
    for (let i = 16; i < 64; i++) { const s0 = r(w[i - 15], 7) ^ r(w[i - 15], 18) ^ (w[i - 15] >>> 3), s1 = r(w[i - 2], 17) ^ r(w[i - 2], 19) ^ (w[i - 2] >>> 10); w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0; }
    let [A, B, C, D, E, F, G, H] = [h0, h1, h2, h3, h4, h5, h6, h7];
    for (let i = 0; i < 64; i++) {
      const t1 = (H + (r(E, 6) ^ r(E, 11) ^ r(E, 25)) + ((E & F) ^ (~E & G)) + K[i] + w[i]) | 0, t2 = ((r(A, 2) ^ r(A, 13) ^ r(A, 22)) + ((A & B) ^ (A & C) ^ (B & C))) | 0;
      H = G; G = F; F = E; E = (D + t1) | 0; D = C; C = B; B = A; A = (t1 + t2) | 0;
    }
    h0 = (h0 + A) | 0; h1 = (h1 + B) | 0; h2 = (h2 + C) | 0; h3 = (h3 + D) | 0; h4 = (h4 + E) | 0; h5 = (h5 + F) | 0; h6 = (h6 + G) | 0; h7 = (h7 + H) | 0;
  }
  return [h0, h1, h2, h3, h4, h5, h6, h7].map(x => (x >>> 0).toString(16).padStart(8, '0')).join('');
}
function pwCheck(rec, pw) {
  const [salt, hash] = String(rec || '').split('$'); if (!salt) return false;
  let x = sha256(salt + ':' + pw); for (let i = 0; i < 1999; i++) x = sha256(x + pw);
  return x === hash;
}
const LEARN = { busy: false, err: '' };
const hexBytes = h => Uint8Array.from(h.match(/../g).map(x => parseInt(x, 16)));
function orgDerive(salt, pw) { let x = sha256(salt + ':' + pw); for (let i = 0; i < 1999; i++) x = sha256(x + pw); return x; }
function orgOpen(o, K) {   // блок организатора из learn.json: {readKey, names}
  try {
    if (!o || !K || sha256(K + ':mac:' + o.nonce + ':' + o.ct) !== o.mac) return null;
    const ct = Uint8Array.from(atob(o.ct), c => c.charCodeAt(0)), pt = new Uint8Array(ct.length);
    for (let i = 0, blk = 0; i < ct.length; blk++) { const ks = hexBytes(sha256(K + ':' + o.nonce + ':' + blk)); for (let j = 0; j < 32 && i < ct.length; j++, i++) pt[i] = ct[i] ^ ks[j]; }
    return JSON.parse(new TextDecoder().decode(pt));
  } catch (e) { return null; }
}
function orgApply(d) {   // организатор: ключ отчёта и список ФИО — из зашифрованного блока
  const ac = learnAcc(), K = LS.get('orgK', '');
  if (!ac || !d || !d.org || d.org.k !== ac.k || !K) return false;
  const v = orgOpen(d.org, K); if (!v) return false;
  LS.set('orgKey', v.readKey); LS.set('orgNames', (v.names || []).join('\n')); return true;
}
const isOrg = () => { const ac = learnAcc(), d = learnData(); return !!(ac && d && d.org && d.org.k === ac.k && LS.get('orgK', '')); };
const learnData = () => LS.get('learn', null);
const learnAcc = () => { const v = LS.get('learnUser', null); return v && v.k ? v : null; };
const learnUser = () => (learnAcc() || {}).name || '';
const learnNorm = s => String(s).toLowerCase().replace(/ё/g, 'е').replace(/[^0-9a-zа-я]/g, '');
const learnKey = s => sha256('u:' + learnNorm(s)).slice(0, 24);
const learnPretty = s => {
  const m = s.trim().match(/^([A-Za-zА-Яа-яЁё-]+)[\s.,]+([A-Za-zА-Яа-яЁё.\s]{1,8})$/);
  if (!m) return s.trim();
  const sur = m[1].split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join('-');
  return sur + ' ' + m[2].replace(/[^A-Za-zА-Яа-яЁё]/g, '').toUpperCase().split('').map(c => c + '.').join('');
};
function learnNewCount() {
  const d = learnData(); if (!d || !learnUser()) return 0;
  const seen = LS.get('learnSeen', []);
  return (d.items || []).filter(x => x.new && !seen.includes(x.id) && !learnPast(x)).length;
}
const learnPast = x => x.until && new Date(x.until + 'T23:59:59') < new Date();
function learnFetch(cb) {
  LEARN.busy = true;
  fetch(SITE + 'learn.json?t=' + Date.now(), { cache: 'no-store' }).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(d => { LS.set('learn', d); LEARN.err = ''; const ac = learnAcc(); if (ac && !(d.users || {})[ac.k]) LS.set('learnUser', null); else orgApply(d); })
    .catch(e => { LEARN.err = 'Нет связи с сервером — показана сохранённая лента'; })
    .finally(() => { LEARN.busy = false; cb && cb(); });
}
// прогресс курсов и лекций — отдельно для каждой учётки (на одном телефоне могут входить разные люди)
function pk(name) {
  const ac = learnAcc(), id = ac ? ac.k : 'anon', key = name + '@' + id;
  if (ac && LS.get(key, null) === null) { const old = LS.get(name, null); if (old) { LS.set(key, old); LS.set(name, null); } }   // прогресс из версий ≤ 3.5 — первому вошедшему
  return key;
}
// результаты обучения → Google Таблица организатора (адрес — "report" в learn.json); очередь на случай отсутствия сети
function learnSend(ev) {
  const ac = learnAcc(); if (!ac) return;
  const q = LS.get('learnQueue', []);
  q.push(Object.assign({ id: Date.now().toString(36) + Math.random().toString(36).slice(2, 8), uid: ac.k, ts: new Date().toISOString(), v: APP_VERSION, p: window.App ? 'android' : 'web' }, ev));
  LS.set('learnQueue', q.slice(-200)); learnFlush();
}
function learnBackfill() {   // результаты, полученные до появления отправки (версии ≤ 3.4)
  if (!learnAcc()) return;
  [['course', window.COURSES], ['lecture', window.LECTURES]].forEach(([t, M]) => Object.keys(M || {}).forEach(k => {
    const s = LS.get(pk(t + '_' + k), {});
    if (s.done && !s.sent && s.score != null) { s.sent = true; LS.set(pk(t + '_' + k), s); learnSend({ item: t + ':' + k, ev: 'quiz', score: s.score, total: M[k].quiz.length, ts: new Date(s.at || Date.now()).toISOString() }); }
  }));
}
function learnFlush() {
  const q = LS.get('learnQueue', []), d = learnData(), url = d && d.report;
  if (!q.length || !url || !/^https:\/\/script\.google\.com\/macros\/s\/[\w-]+\/exec$/.test(url) || LEARN.flushing) return;
  LEARN.flushing = true; const batch = q.slice(0, 50);
  fetch(url, { method: 'POST', mode: 'no-cors', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify(batch) })
    .then(() => { const ids = new Set(batch.map(x => x.id)); LS.set('learnQueue', LS.get('learnQueue', []).filter(x => !ids.has(x.id))); })
    .catch(() => {}).finally(() => { LEARN.flushing = false; });
}
let LEARN_TAB = 'course';   // вкладка ленты обучения: по умолчанию «Курсы»
function learnPage(noFetch) {
  setTitle('Обучение и опросы', false);
  const d = learnData(), u = learnUser();
  if (!noFetch) learnFetch(() => { learnBackfill(); learnFlush(); if (cur === '#learn') learnPage(true); });
  if (!u) {
    view.innerHTML = `<div class="calc-card lform">
      <h2>Вход</h2><p class="lhint">Логин и пароль выдаёт организатор обучения. Справочник работает и без входа.</p>
      <label class="lf"><span>Логин — фамилия и инициалы</span><input id="lLogin" placeholder="Иванов П.А." autocomplete="username" autocapitalize="words" spellcheck="false"></label>
      <label class="lf"><span>Пароль</span><span class="lpw"><input id="lPw" type="password" autocomplete="current-password" autocapitalize="none" autocorrect="off" spellcheck="false"><button type="button" class="lpeye" id="lEye">показать</button></span></label>
      <div class="lerr" id="lErr"></div>
      <button class="bigbtn" id="lGo">Войти</button></div>
      <p class="disc">Приложение запоминает вход на этом устройстве. Пароль не хранится и никуда не передаётся — проверяется на телефоне.</p>`;
    let LAST_PW = '';
    const check = (dd, lg, pw) => {
      const k = learnKey(lg), rec = (dd.users || {})[k], p2 = pw.replace(/\s+/g, '').toLowerCase();
      if (!rec) return null;
      if (pwCheck(rec, pw)) { LAST_PW = pw; return k; }
      if (p2 !== pw && pwCheck(rec, p2)) { LAST_PW = p2; return k; }
      return null;
    };
    const ok = (k, lg, pw) => {
      LS.set('learnUser', { k, name: learnPretty(lg) });
      const dd = learnData();
      if (dd && dd.org && dd.org.k === k) { const K = orgDerive(dd.org.salt, pw); if (orgOpen(dd.org, K)) { LS.set('orgK', K); orgApply(dd); krEnable(true); } }
      learnPage(true);
    };
    const go = () => {
      const lg = $('#lLogin').value.trim(), pw = $('#lPw').value, dd = learnData(), er = $('#lErr');
      if (!lg || !pw) { er.textContent = 'Введите логин и пароль'; return; }
      er.textContent = 'Проверка…';
      setTimeout(() => {
        const k = dd && check(dd, lg, pw);
        if (k) return ok(k, lg, LAST_PW);
        // список учёток мог устареть — перекачиваем и проверяем ещё раз
        learnFetch(() => {
          const d2 = learnData(), k2 = d2 && check(d2, lg, pw);
          if (k2) return ok(k2, lg, LAST_PW);
          er.textContent = !d2 ? 'Для первого входа нужен интернет' : LEARN.err ? 'Нет связи — список учётных записей не обновился. Проверьте интернет и попробуйте ещё раз' : 'Неверный логин или пароль';
        });
      }, 30);
    };
    $('#lEye').onclick = () => { const f = $('#lPw'), s = f.type === 'password'; f.type = s ? 'text' : 'password'; $('#lEye').textContent = s ? 'скрыть' : 'показать'; };
    $('#lGo').onclick = go;
    $('#lPw').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    return;
  }
  const seen = LS.get('learnSeen', []);
  const TY = { test: ['Тест', 'Пройти тест'], survey: ['Опрос', 'Пройти опрос'], material: ['Материал', 'Открыть'], course: ['Курс', 'Начать курс'] };
  const all = (d && d.items || []).slice().sort((a, b) => learnPast(a) - learnPast(b));
  const isLect = x => x.type === 'lecture';
  const items = all.filter(x => isLect(x) === (LEARN_TAB === 'lecture'));
  const newIn = f => all.filter(x => f(x) && x.new && !seen.includes(x.id) && !learnPast(x)).length;
  const nL = newIn(isLect), nC = newIn(x => !isLect(x));
  const tabs = d && all.length ? `<div class="seg n2 ltabs"><a class="${LEARN_TAB === 'course' ? 'on' : ''}" data-tab="course">Курсы${nC ? ` <i class="tnew">${nC}</i>` : ''}</a><a class="${LEARN_TAB === 'lecture' ? 'on' : ''}" data-tab="lecture">Лекции${nL ? ` <i class="tnew">${nL}</i>` : ''}</a></div>` : '';
  const fmt = s => s ? s.split('-').reverse().slice(0, 2).join('.') : '';
  view.innerHTML = `<div class="luser"><span>Вы вошли: <b>${esc(u)}</b>${isOrg() ? ' · организатор' : ''}</span><a id="lOut">Выйти</a></div>
    ${LEARN.err ? `<div class="lnote">${esc(LEARN.err)}</div>` : ''}
    ${tabs}
    ${!d ? '<div class="rwempty">Загрузка ленты…</div>' : !items.length ? `<div class="rwempty">${LEARN_TAB === 'lecture' ? 'Лекций пока нет.' : 'Курсов пока нет.'} Новые появятся здесь.</div>` : ''}
    ${items.map(x => { const t = TY[x.type] || TY.material, past = learnPast(x), isNew = x.new && !seen.includes(x.id) && !past;
      const url = x.url ? x.url.replace(/\{login\}/g, encodeURIComponent(u)) : '';
      const C = x.type === 'course' && window.COURSES && COURSES[x.course];
      const LC = x.type === 'lecture' && window.LECTURES && LECTURES[x.lecture];
      if (LC) {
        const st = LS.get(pk('lecture_' + x.lecture), {}), mm = s => Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0');
        const btn = st.done ? 'Слушать снова' : st.pos > 5 ? `Продолжить · ${mm(st.pos)}` : 'Слушать лекцию';
        return `<div class="litem"><div class="lhead"><span class="lty lecture">Лекция</span>${isNew ? '<span class="lnew">новое</span>' : ''}<span class="luntil">${Math.round(LC.dur / 60)} мин · ${LC.slides.length} слайдов · тест ${LC.quiz.length}</span></div>
          <h3>${esc(x.title || LC.title)}</h3><p>${esc(x.text || LC.sub)}</p>
          ${st.done ? `<div class="ldone">✓ Тест: ${st.score}/${LC.quiz.length}</div>` : ''}
          <div class="lbtns"><a class="bigbtn lgo" data-id="${esc(x.id)}" href="#lecture/${x.lecture}">${btn}</a>${st.heard || st.done ? `<a class="lread" href="#lecture/${x.lecture}/test">${st.done ? 'Пройти тест ещё раз' : 'К тесту'} ›</a>` : ''}</div></div>`;
      }
      if (C) {
        const st = LS.get(pk('course_' + x.course), {}), n = C.cards.length, pos = Math.min(st.pos || 0, n);
        const btn = st.done ? `Повторить` : pos ? `Продолжить · ${pos + 1}/${n + 1}` : t[1];
        return `<div class="litem"><div class="lhead"><span class="lty course">Курс</span>${isNew ? '<span class="lnew">новое</span>' : ''}<span class="luntil">${C.cards.length} карточек · ${C.quiz.length} вопросов · ~${C.min} мин</span></div>
          <h3>${esc(x.title || C.title)}</h3><p>${esc(x.text || C.sub)}</p>
          ${st.done ? `<div class="ldone">✓ Пройден · проверка ${st.score}/${C.quiz.length}</div>` : ''}
          <div class="lbtns"><a class="bigbtn lgo" data-id="${esc(x.id)}" href="#course/${x.course}/${st.done ? 0 : pos}">${btn}</a></div></div>`;
      }
      return `<div class="litem${past ? ' past' : ''}"><div class="lhead"><span class="lty ${x.type}">${t[0]}</span>${isNew ? '<span class="lnew">новое</span>' : ''}${x.until ? `<span class="luntil">${past ? 'завершено' : 'до ' + fmt(x.until)}</span>` : ''}</div>
        <h3>${esc(x.title)}</h3>${x.text ? `<p>${esc(x.text)}</p>` : ''}
        <div class="lbtns">${url && !past ? `<a class="bigbtn lgo" data-id="${esc(x.id)}" href="${esc(url)}" target="_blank" rel="noopener">${t[1]}</a>` : (!past && x.type !== 'material' ? '<span class="lsoon">ссылка появится позже</span>' : '')}
          ${x.read ? `<a class="lread" data-id="${esc(x.id)}" href="${esc(x.read)}">${x.type === 'material' ? 'Открыть в справочнике' : 'Повторить раздел'} ›</a>` : ''}</div></div>`; }).join('')}
    <p class="disc">Результаты тестов и опросов видит организатор обучения. Логин подставляется в форму автоматически.</p>`;
  $('#lOut').onclick = () => { if (isOrg()) { LS.set('orgK', ''); LS.set('orgKey', ''); LS.set('orgNames', ''); krEnable(false); } LS.set('learnUser', null); learnPage(true); statsTabSync(); };
  statsTabSync();
  view.querySelectorAll('.ltabs a').forEach(a => a.onclick = () => { LEARN_TAB = a.dataset.tab; learnPage(true); scrollTo(0, 0); });
  view.querySelectorAll('[data-id]').forEach(el => el.addEventListener('click', () => { const s = LS.get('learnSeen', []); if (!s.includes(el.dataset.id)) { s.push(el.dataset.id); LS.set('learnSeen', s); } }));
}

// ---------------------------------------------------------------- курс: карточки + проверка
function coursePage(key, idx) {
  const C = window.COURSES && COURSES[key];
  if (!C) return go('#learn');
  const n = C.cards.length, st = LS.get(pk('course_' + key), {});
  let i = Math.max(0, Math.min(parseInt(idx, 10) || 0, n));
  st.pos = Math.max(st.pos || 0, i); if (i === n && !st.done) st.pos = n; LS.set(pk('course_' + key), st);
  setTitle(C.title, false);
  const to = j => { history.replaceState(null, '', '#course/' + key + '/' + j); coursePage(key, j); window.scrollTo(0, 0); };
  const bar = `<div class="cvbar"><div class="cvprog"><i style="width:${Math.round((i + 1) / (n + 1) * 100)}%"></i></div><span>${i < n ? `${i + 1} / ${n}` : 'Проверка'}</span></div>`;
  if (i < n) {
    const c = C.cards[i];
    view.innerHTML = `<div class="cv">${bar}
      <article class="cvcard"><div class="cvk">${esc(c.k || '')}</div><h2>${esc(c.h)}</h2>${c.lead ? `<p class="cvlead">${esc(c.lead)}</p>` : ''}
        <div class="cvb">${(c.blocks || []).map(block).join('')}</div>
        ${i === 0 ? `<div class="csrc">Основано на: ${esc(C.srcName)}</div>` : ''}</article>
      <div class="cvnav"><button class="cvbtn sec" id="cvPrev"${i ? '' : ' disabled'}>‹ Назад</button><button class="cvbtn" id="cvNext">${i === n - 1 ? 'К проверке ›' : 'Далее ›'}</button></div></div>`;
    wireBlocks(view);
    $('#cvPrev').onclick = () => i && to(i - 1);
    $('#cvNext').onclick = () => to(i + 1);
  } else {
    const ans = {}; let sent = false;
    if (!st.cardsSent) { st.cardsSent = true; LS.set(pk('course_' + key), st); learnSend({ item: 'course:' + key, ev: 'cards', score: n, total: n }); }
    const render = () => {
      const done = Object.keys(ans).length === C.quiz.length, score = C.quiz.filter((q, k) => ans[k] === q.a).length;
      if (done && !st.done) { st.done = true; st.score = score; st.at = Date.now(); LS.set(pk('course_' + key), st); }
      if (done && !sent) { sent = true; st.sent = true; LS.set(pk('course_' + key), st); learnSend({ item: 'course:' + key, ev: 'quiz', score, total: C.quiz.length, ans: C.quiz.map((q, k) => ans[k] === q.a ? 1 : 0).join('') }); }
      view.innerHTML = `<div class="cv">${bar}
        <article class="cvcard"><div class="cvk">Проверка</div><h2>${C.quiz.length} вопросов по курсу</h2><p class="cvlead">Выберите ответ — сразу увидите разбор.</p>
        ${C.quiz.map((q, k) => `<div class="qz${k in ans ? (ans[k] === q.a ? ' ok' : ' bad') : ''}"><div class="qq"><b>${k + 1}.</b> ${esc(q.q)}</div>
          ${q.o.map((o, m) => `<button class="qo${k in ans ? (m === q.a ? ' right' : (m === ans[k] ? ' wrong' : '')) : ''}" data-q="${k}" data-o="${m}"${k in ans ? ' disabled' : ''}>${esc(o)}</button>`).join('')}
          ${k in ans ? `<div class="qe"><b>${ans[k] === q.a ? 'Верно.' : 'Не совсем.'}</b> ${esc(q.e)}</div>` : ''}</div>`).join('')}
        ${done ? `<div class="qres"><div class="qsc">${score} / ${C.quiz.length}</div><div>${score === C.quiz.length ? 'Отлично — курс пройден без ошибок.' : score >= C.quiz.length - 2 ? 'Курс пройден. Загляните в карточки, где были ошибки.' : 'Стоит пролистать карточки ещё раз.'}</div></div>` : ''}
        </article>
        <div class="cvnav"><button class="cvbtn sec" id="cvPrev">‹ К карточкам</button><a class="cvbtn" href="#learn">К ленте</a></div></div>`;
      view.querySelectorAll('.qo').forEach(b => b.onclick = () => { const y = window.scrollY; ans[+b.dataset.q] = +b.dataset.o; render(); window.scrollTo(0, y); });
      $('#cvPrev').onclick = () => to(n - 1);
    };
    render();
  }
  // свайп между карточками
  let x0 = null, y0 = null;
  view.ontouchstart = e => { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; };
  view.ontouchend = e => {
    if (x0 == null) return; const dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0; x0 = null;
    if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.5 && i < n) { if (dx < 0) to(i + 1); else if (i) to(i - 1); }
  };
}

// ---------------------------------------------------------------- лекция: аудио + слайды под голос, тест в конце
const fmtT = s => { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
const PLAY_I = '<svg viewBox="0 0 24 24"><path d="M8 5l11 7-11 7z"/></svg>', PAUSE_I = '<svg viewBox="0 0 24 24"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>';
function lecturePage(key) {
  const L = window.LECTURES && LECTURES[key];
  if (!L) return go('#learn');
  setTitle('Лекция', false);
  if (!L.metaLoaded) {   // тайминг слайдов и версия озвучки — с сайта (можно переозвучить без выпуска приложения)
    view.innerHTML = '<div class="rwempty">Загрузка лекции…</div>';
    const done = () => { L.metaLoaded = true; if (cur === '#lecture/' + key) lecturePage(key); };
    const tm = setTimeout(done, 4000);
    fetch(SITE + L.dir + 'meta.json?t=' + Date.now(), { cache: 'no-store' }).then(r => r.json()).then(m => {
      if (m && Array.isArray(m.t) && m.t.length === L.slides.length) { m.t.forEach((t, k) => { L.slides[k].t = t; }); L.dur = m.dur || L.dur; L.ver = m.v || 1; if (m.audio && /^[\w.-]+\.mp3$/.test(m.audio)) L.audioFile = m.audio; }
    }).catch(() => {}).finally(() => { clearTimeout(tm); if (!L.metaLoaded) done(); });
    return;
  }
  const st = LS.get(pk('lecture_' + key), {}), base = SITE + L.dir, n = L.slides.length;
  if (!window.LECT || LECT.key !== key) {
    if (window.LECT) LECT.audio.pause();
    const au = new Audio(); au.preload = 'metadata'; au.src = base + (L.audioFile || L.audio) + '?v=' + (L.ver || 1);
    window.LECT = { key, audio: au, rate: 1, lastSave: 0 };
    if (st.pos > 5 && !st.done) { const t = st.pos; au.addEventListener('loadedmetadata', () => { au.currentTime = t; }, { once: true }); }
  }
  const au = LECT.audio, idxAt = t => { let i = 0; L.slides.forEach((s, k) => { if (t >= s.t - 0.05) i = k; }); return i; };
  view.innerHTML = `<div class="lv">
    <div class="lslide" id="lvBox"><div class="lvframe"><img id="lvImg" alt=""><div id="lvAnim"></div></div><div class="lvmsg" id="lvMsg">Загрузка…</div><span class="lvfs">⤢</span></div>
    <div class="lvmeta"><span id="lvNum"></span><b id="lvTitle"></b></div>
    <input type="range" id="lvSeek" min="0" max="${L.dur}" step="0.5" value="0">
    <div class="lvtime"><span id="lvCur">0:00</span><span>${fmtT(L.dur)}</span></div>
    <div class="lvctl"><button class="lvb" id="lvPrev" aria-label="Предыдущий слайд"><svg viewBox="0 0 24 24"><path d="M6 5h2v14H6zM20 5v14L9 12z"/></svg></button>
      <button class="lvb play" id="lvPlay" aria-label="Слушать">${PLAY_I}</button>
      <button class="lvb" id="lvNext" aria-label="Следующий слайд"><svg viewBox="0 0 24 24"><path d="M16 5h2v14h-2zM4 5v14l11-7z"/></svg></button>
      <button class="lvb rate" id="lvRate">${LECT.rate}×</button></div>
    <div id="lvTest"></div>
    <div class="sec-h">Слайды</div><div class="lvlist">${L.slides.map((s, k) => `<a class="lvli" data-k="${k}"><span class="n">${k + 1}</span><span class="h">${esc(s.h)}</span><span class="t">${fmtT(s.t)}</span></a>`).join('')}</div>
    <p class="disc">Источники: ${esc(L.srcName)}. Озвучка — синтез речи. Для просмотра нужен интернет.</p></div>`;
  const img = $('#lvImg'), msg = $('#lvMsg'); let shown = -1;
  const show = i => {
    if (i === shown) return; shown = i;
    img.src = base + 's' + String(i + 1).padStart(2, '0') + '.jpg?v=' + (L.ver || 1);
    if (i + 1 < n) new Image().src = base + 's' + String(i + 2).padStart(2, '0') + '.jpg?v=' + (L.ver || 1);
    // анимация (GIF) поверх статичного кадра слайда — рамка задана в долях слайда
    $('#lvAnim').innerHTML = (L.slides[i].anim || []).map(a => `<img class="lvanim" alt="" src="${esc(SITE + a.src)}" onerror="this.remove()"
      style="left:${a.box[0] * 100}%;top:${a.box[1] * 100}%;width:${a.box[2] * 100}%;height:${a.box[3] * 100}%">`).join('');
    $('#lvNum').textContent = `${i + 1} / ${n}`; $('#lvTitle').textContent = L.slides[i].h;
    view.querySelectorAll('.lvli').forEach(el => el.classList.toggle('on', +el.dataset.k === i));
    if (i === n - 1) unlock();
  };
  const unlock = () => { const s = LS.get(pk('lecture_' + key), {}); if (!s.heard) { s.heard = true; LS.set(pk('lecture_' + key), s); } if (!s.heardSent) { s.heardSent = true; LS.set(pk('lecture_' + key), s); learnSend({ item: 'lecture:' + key, ev: 'heard', score: n, total: n }); } testBtn(); };
  const testBtn = () => { const s = LS.get(pk('lecture_' + key), {}); $('#lvTest').innerHTML = s.heard || s.done ? `<a class="bigbtn lvtest" href="#lecture/${key}/test">${s.done ? `Тест пройден: ${s.score}/${L.quiz.length} · пройти ещё раз` : `Пройти тест · ${L.quiz.length} вопросов`}</a>` : ''; };
  const sync = () => {
    const t = au.currentTime || 0;
    if (!seeking) $('#lvSeek').value = t;
    $('#lvCur').textContent = fmtT(t); show(idxAt(t));
    $('#lvPlay').innerHTML = au.paused ? PLAY_I : PAUSE_I;
    if (Date.now() - LECT.lastSave > 3000) { LECT.lastSave = Date.now(); const s = LS.get(pk('lecture_' + key), {}); s.pos = t; LS.set(pk('lecture_' + key), s); }
  };
  let seeking = false;
  img.onload = () => { msg.hidden = true; };
  img.onerror = () => { msg.hidden = false; msg.textContent = 'Нет связи — лекция загружается из интернета'; };
  au.onerror = () => {   // повтор в обход кэша, затем сообщение
    if (!LECT.retried) { LECT.retried = true; const t = au.currentTime || 0, wasPlaying = !au.paused; au.src = base + (L.audioFile || L.audio) + '?v=' + (L.ver || 1) + '&r=' + Date.now(); au.addEventListener('loadedmetadata', () => { au.currentTime = t; if (wasPlaying) au.play().catch(() => {}); }, { once: true }); return; }
    msg.hidden = false; msg.textContent = 'Не удалось загрузить звук — проверьте интернет';
  };
  au.ontimeupdate = () => { if (cur.startsWith('#lecture/' + key)) sync(); };
  au.onplay = au.onpause = au.ontimeupdate;
  au.onended = () => { const s = LS.get(pk('lecture_' + key), {}); s.pos = 0; s.heard = true; LS.set(pk('lecture_' + key), s); if (cur === '#lecture/' + key) go('#lecture/' + key + '/test'); };
  $('#lvPlay').onclick = () => { if (au.paused) { au.playbackRate = LECT.rate; const p = au.play(); if (p && p.catch) p.catch(() => { msg.hidden = false; msg.textContent = 'Не удалось воспроизвести — проверьте интернет'; }); } else au.pause(); };
  const jump = k => { k = Math.max(0, Math.min(n - 1, k)); au.currentTime = L.slides[k].t + (k ? 0.05 : 0); sync(); };
  $('#lvPrev').onclick = () => { const i = idxAt(au.currentTime); jump(au.currentTime - L.slides[i].t > 3 ? i : i - 1); };
  $('#lvNext').onclick = () => jump(idxAt(au.currentTime) + 1);
  $('#lvRate').onclick = () => { const R = [1, 1.25, 1.5]; LECT.rate = R[(R.indexOf(LECT.rate) + 1) % R.length]; au.playbackRate = LECT.rate; $('#lvRate').textContent = String(LECT.rate).replace('.', ',') + '×'; };
  const sk = $('#lvSeek');
  sk.oninput = () => { seeking = true; $('#lvCur').textContent = fmtT(+sk.value); show(idxAt(+sk.value)); };
  sk.onchange = () => { au.currentTime = +sk.value; seeking = false; sync(); };
  view.querySelectorAll('.lvli').forEach(el => el.onclick = () => { jump(+el.dataset.k); if (au.paused) $('#lvPlay').click(); window.scrollTo({ top: 0, behavior: 'smooth' }); });
  $('#lvBox').onclick = () => $('#lvBox').classList.toggle('full');
  show(idxAt(st.pos > 5 && !st.done ? st.pos : 0)); testBtn(); sync();
}
function lectureTest(key) {
  const L = window.LECTURES && LECTURES[key];
  if (!L) return go('#learn');
  if (window.LECT) LECT.audio.pause();
  setTitle('Тест по лекции', false);
  const ans = {}; let saved = false;
  const render = () => {
    const done = Object.keys(ans).length === L.quiz.length, score = L.quiz.filter((q, k) => ans[k] === q.a).length;
    if (done && !saved) { saved = true; const s = LS.get(pk('lecture_' + key), {}); s.done = true; s.score = score; s.heard = true; s.at = Date.now(); s.sent = true; LS.set(pk('lecture_' + key), s);
      learnSend({ item: 'lecture:' + key, ev: 'quiz', score, total: L.quiz.length, ans: L.quiz.map((q, k) => ans[k] === q.a ? 1 : 0).join('') }); }
    view.innerHTML = `<div class="cv"><article class="cvcard"><div class="cvk">Тест по лекции</div><h2>${esc(L.title.replace(/^Лекция:\s*/, '').replace(/^./, c => c.toUpperCase()))}</h2><p class="cvlead">${L.quiz.length} вопросов. Выберите ответ — сразу увидите разбор.</p>
      ${L.quiz.map((q, k) => `<div class="qz${k in ans ? (ans[k] === q.a ? ' ok' : ' bad') : ''}"><div class="qq"><b>${k + 1}.</b> ${esc(q.q)}</div>
        ${q.o.map((o, m) => `<button class="qo${k in ans ? (m === q.a ? ' right' : (m === ans[k] ? ' wrong' : '')) : ''}" data-q="${k}" data-o="${m}"${k in ans ? ' disabled' : ''}>${esc(o)}</button>`).join('')}
        ${k in ans ? `<div class="qe"><b>${ans[k] === q.a ? 'Верно.' : 'Не совсем.'}</b> ${esc(q.e)}</div>` : ''}</div>`).join('')}
      ${done ? `<div class="qres"><div class="qsc">${score} / ${L.quiz.length}</div><div>${score === L.quiz.length ? 'Отлично — все ответы верные.' : score >= L.quiz.length - 1 ? 'Хороший результат.' : 'Стоит переслушать лекцию — особенно клинические случаи.'}</div></div>` : ''}
      </article><div class="cvnav"><a class="cvbtn sec" href="#lecture/${key}">‹ К лекции</a><a class="cvbtn" href="#learn">К ленте</a></div></div>`;
    view.querySelectorAll('.qo').forEach(b => b.onclick = () => { const y = window.scrollY; ans[+b.dataset.q] = +b.dataset.o; render(); window.scrollTo(0, y); });
  };
  render();
}

// ---------------------------------------------------------------- отчёт организатора (ФИО хранятся только на этом телефоне)
function reportPage(edit) {
  setTitle('Отчёт по обучению', false);
  const d = learnData(), url = d && d.report, key = LS.get('orgKey', ''), names = LS.get('orgNames', '');
  if (!d) { learnFetch(() => { if (cur === '#report') reportPage(edit); }); view.innerHTML = statsSeg('report') + '<div class="rwempty">Загрузка…</div>'; return; }
  if (!url) { view.innerHTML = statsSeg('report') + '<div class="rwempty">Сбор результатов ещё не подключён: в настройках обучения нет адреса Google Таблицы.</div>'; return; }
  if (edit || !key || !names.trim()) {
    view.innerHTML = statsSeg('report') + `<div class="calc-card lform"><h2>Настройка отчёта</h2>
      <p class="lhint">Ключ и список ФИО сохраняются только на этом телефоне. В Google Таблице фамилий нет — только коды учёток; приложение сопоставит их со списком.</p>
      <label class="lf"><span>Ключ организатора</span><input id="oKey" value="${esc(key)}" autocapitalize="none" spellcheck="false"></label>
      <label class="lf"><span>Список ФИО — по одному в строке, как логины («Иванов П.А.»)</span><textarea id="oNames" rows="10">${esc(names)}</textarea></label>
      <div class="lerr" id="oErr"></div><button class="bigbtn" id="oSave">Сохранить и показать отчёт</button></div>`;
    $('#oSave').onclick = () => {
      const k = $('#oKey').value.trim(), nm = $('#oNames').value;
      if (!k || !nm.trim()) { $('#oErr').textContent = 'Заполните ключ и список'; return; }
      LS.set('orgKey', k); LS.set('orgNames', nm); reportPage();
    };
    return;
  }
  view.innerHTML = statsSeg('report') + '<div class="rwempty">Загрузка результатов…</div>';
  fetch(url + '?key=' + encodeURIComponent(key) + '&t=' + Date.now()).then(r => r.json()).then(res => {
    if (!res.ok) { view.innerHTML = statsSeg('report') + `<div class="rwempty">${res.err === 'key' ? 'Неверный ключ организатора.' : 'Таблица вернула ошибку.'}</div><div class="cvnav"><button class="cvbtn sec" id="oEdit">Изменить ключ и список</button></div>`; $('#oEdit').onclick = () => reportPage(true); return; }
    const people = names.split(/\n+/).map(s => s.trim()).filter(Boolean).map(s => ({ name: learnPretty(s), k: learnKey(s) }));
    const byK = new Map(people.map(p => [p.k, p]));
    const items = [];
    const title = it => { const [t, k] = it.split(':'); return t === 'lecture' ? 'Лекция: ' + ((window.LECTURES && LECTURES[k] || {}).title || k).replace(/^Лекция:\s*/, '').replace(/^./, c => c.toUpperCase()) : t === 'course' ? 'Курс: ' + ((window.COURSES && COURSES[k] || {}).title || k) : it; };
    const R = {}; let unknown = 0;
    (res.rows || []).forEach(r => {
      if (!byK.has(r.uid)) { unknown++; return; }
      if (!items.includes(r.item)) items.push(r.item);
      const c = ((R[r.uid] = R[r.uid] || {})[r.item] = R[r.uid][r.item] || { best: -1, total: 0, tries: 0, seen: false, at: '' });
      const at = r.ts || r.at;
      if (r.ev === 'quiz') { c.tries++; if (+r.score > c.best) { c.best = +r.score; c.total = +r.total; } if (!c.at || at > c.at) c.at = at; }
      else c.seen = true;
    });
    items.sort();
    const dd = s => { const x = new Date(s); return isNaN(x) ? '' : String(x.getDate()).padStart(2, '0') + '.' + String(x.getMonth() + 1).padStart(2, '0'); };
    const cell = c => !c ? '<span class="rq no">—</span>' : c.best >= 0 ? `<span class="rq ${c.best >= c.total - 1 ? 'ok' : c.best / c.total >= 0.6 ? 'mid' : 'low'}">${c.best}/${c.total}</span><small>${dd(c.at)}${c.tries > 1 ? ' · ' + c.tries + ' попыт.' : ''}</small>` : `<span class="rq seen">${/^lecture/.test('' + c.kind) ? 'слушал' : 'начал'}</span>`;
    const sum = items.map(it => { const n = people.filter(p => R[p.k] && R[p.k][it] && R[p.k][it].best >= 0).length; return `<div class="rsum"><b>${n}</b> из ${people.length}<span>${esc(title(it))} — тест пройден</span></div>`; }).join('');
    view.innerHTML = statsSeg('report') + `<div class="rep">${sum || '<div class="rwempty">Результатов пока нет.</div>'}
      ${items.length ? `<div class="tw rtab"><table><thead><tr><th>ФИО</th>${items.map(it => `<th>${esc(title(it))}</th>`).join('')}</tr></thead><tbody>
        ${people.slice().sort((a, b) => a.name.localeCompare(b.name, 'ru')).map(p => `<tr><th>${esc(p.name)}</th>${items.map(it => `<td>${cell(R[p.k] && R[p.k][it] && Object.assign(R[p.k][it], { kind: it }))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}
      ${unknown ? `<p class="disc">Ещё ${unknown} записей от учёток, которых нет в вашем списке.</p>` : ''}
      <div class="cvnav"><button class="cvbtn sec" id="oCopy">Скопировать для Excel</button><button class="cvbtn" id="oRef">Обновить</button></div>
      <p class="disc"><a id="oEdit">Изменить ключ и список ФИО</a> · «—» — не проходил; «слушал» / «начал» — открыл материал, но тест не сдавал.</p></div>`;
    $('#oRef').onclick = () => reportPage();
    $('#oEdit').onclick = () => reportPage(true);
    $('#oCopy').onclick = () => {
      const tsv = ['ФИО\t' + items.map(title).join('\t')].concat(people.map(p => p.name + '\t' + items.map(it => { const c = R[p.k] && R[p.k][it]; return !c ? '' : c.best >= 0 ? `${c.best}/${c.total} (${dd(c.at)})` : 'открыл'; }).join('\t'))).join('\n');
      const ta = document.createElement('textarea'); ta.value = tsv; document.body.appendChild(ta); ta.select();
      let ok = false; try { ok = document.execCommand('copy'); } catch (e) {} ta.remove();
      if (!ok && navigator.clipboard) navigator.clipboard.writeText(tsv).then(() => {}, () => {});
      $('#oCopy').textContent = 'Скопировано';
    };
  }).catch(() => { view.innerHTML = statsSeg('report') + '<div class="rwempty">Нет связи с Google Таблицей — проверьте интернет.</div>'; });
}

// ---------------------------------------------------------------- MKB-10
function mkbItem(x, ts) {
  return `<li><a href="#mkb/${x.id}"><span class="code">${esc(x.code)}</span>
    <span class="nm">${ts ? hlText(x.name, ts) : esc(x.name)}</span>
    ${x.ncr ? `<span class="badge">КР ${x.ncr}</span>` : ''}
    ${x.nchild ? '<span class="chev">›</span>' : ''}</a></li>`;
}
function crStateBadge(x) {
  if (x.off) return '<span class="st off">в приложении</span>';
  if (dlSet().has(x.id)) return '<span class="st dl">загружено</span>';
  return '<span class="st net">загрузить</span>';
}
function crItem(x, extra) {
  const sch = SCHEME_BY_CR[x.id];
  return `<li><a href="#cr/${esc(x.id)}"><span class="nm">${esc(x.name)}
    <div class="sub">КР${esc(x.id)} · ${AGE[x.age] || ''}${extra ? ' · ' + esc(extra) : ''}</div>
    <div class="crst">${crStateBadge(x)}${sch ? '<span class="st sch">есть схема</span>' : ''}</div></span>
    <span class="chev">›</span></a></li>`;
}
function mkbRoot(q) {
  setTitle('Классификатор МКБ-10', false);
  if (q != null) S.mkbQ = q;
  view.innerHTML = `<div class="searchbar"><div class="field">
      <svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/></svg>
      <input id="mq" type="search" placeholder="Поиск по коду или нозологии" value="${esc(S.mkbQ)}" autocomplete="off" spellcheck="false">
      <button class="clr" ${S.mkbQ ? '' : 'hidden'}>×</button></div></div><div id="mres"></div>`;
  const inp = $('#mq'), clr = $('.clr');
  inp.addEventListener('input', debounce(() => { S.mkbQ = inp.value; clr.hidden = !inp.value; mkbResults(); }, 200));
  clr.onclick = () => { inp.value = ''; S.mkbQ = ''; clr.hidden = true; mkbResults(); inp.focus(); };
  mkbResults();
}
function mkbResults() {
  const box = $('#mres'); if (!box) return;
  const q = S.mkbQ.trim();
  if (!q) {
    const r = call('mkbChildren', 0);
    box.innerHTML = '<div class="sec-h">Классы болезней</div><ul class="list">' + (r.map ? r.map(x => mkbItem(x)).join('') : '') + '</ul>';
    return;
  }
  const r = call('mkbSearch', q);
  const items = r.items || [];
  anSearch('mkb', q, items.length);
  const code = r.code;
  const ts = code ? null : terms(q);
  let h = `<div class="sec-h">${code ? 'Коды, начинающиеся на ' + esc(code) : 'Найдено'}: ${items.length}${items.length >= 300 ? '+' : ''}</div>`;
  if (!items.length) h += '<div class="empty">В МКБ-10 не найдено</div>';
  h += '<ul class="list">' + items.map(x => mkbItem(x, ts)).join('') + '</ul>';
  if (ts && ts.length) {
    const crs = Object.values(crData()).filter(x => ts.every(t => x.q.includes(t))).slice(0, 30);
    if (crs.length) h += `<div class="sec-h">Клинические рекомендации с таким названием: ${crs.length}</div><ul class="list">` + crs.map(x => crItem(x)).join('') + '</ul>';
  }
  box.innerHTML = h;
}
function mkbNode(id) {
  const r = call('mkbNode', id);
  if (!r.node) { view.innerHTML = '<div class="empty">Код не найден</div>'; return; }
  const n = r.node;
  setTitle(n.code + ' — МКБ-10', false);
  let h = '<div class="crumbs"><a href="#mkb">МКБ-10</a>' + r.path.map(p => ` › <a href="#mkb/${p.id}">${esc(p.code)}</a>`).join('') + '</div>';
  h += `<div class="nodehead"><div class="c">${esc(n.code)}</div><div class="n">${esc(n.name)}</div>
    ${n.orig ? `<div class="sub">Исправлена опечатка источника. В справочнике НСИ: «${esc(n.orig)}»</div>` : ''}</div>`;
  const schemes = [...new Set((r.cr || []).flatMap(x => SCHEME_BY_CR[x.id] || []))];
  if (schemes.length) h += `<div class="sec-h">Схемы для фельдшера</div><ul class="list">${schemes.map(s => `<li><a href="#d/${s}"><span class="ti sm"><svg viewBox="0 0 24 24"><path d="${ICON[s] || ICON.bol}"/></svg></span><span class="nm"><b>${esc(byId[s].title)}</b></span><span class="chev">›</span></a></li>`).join('')}</ul>`;
  const kids = r.children && r.children.length ? `<div class="sec-h">Входящие коды: ${r.children.length}</div><ul class="list">` + r.children.map(x => mkbItem(x)).join('') + '</ul>' : '';
  if (r.cr && r.cr.length) h += `<div class="sec-h">Клинические рекомендации: ${r.cr.length}</div><ul class="list">` + r.cr.map(x => crItem(x, 'коды: ' + x.via)).join('') + '</ul>' + kids;
  else if (kids) h += '<p class="mkbhint">Рекомендации привязаны к конкретным кодам. Число «КР» справа — сколько рекомендаций внутри рубрики.</p>' + kids;
  else h += '<div class="sec-h">Клинические рекомендации</div><div class="empty">Действующих рекомендаций с этим кодом нет</div>';
  view.innerHTML = h;
}

// ---------------------------------------------------------------- guideline card (offline / download)
const DLSTATE = {};
function crPage(id) {
  const x = call('crInfo', id);
  if (!x.id) { setTitle('Рекомендация', false); view.innerHTML = '<div class="empty">Рекомендация не найдена</div>'; return; }
  setTitle('КР' + x.id, false);
  const site = 'https://cr.minzdrav.gov.ru/preview-cr/' + encodeURIComponent(id);
  const pdf = 'https://apicr.minzdrav.gov.ru/api.ashx?op=GetClinrecPdf&id=' + encodeURIComponent(id);
  const sch = SCHEME_BY_CR[id] || [];
  const st = DLSTATE[id];
  let action;
  if (x.off) action = `<a class="bigbtn" href="#doc/${esc(id)}">Открыть полный текст</a><div class="note2">Текст встроен в приложение — работает без интернета.</div>`;
  else if (x.dl) action = `<a class="bigbtn" href="#doc/${esc(id)}">Открыть полный текст</a><div class="note2">Загружено на телефон — работает без интернета.</div><button class="lnkbtn" id="dlDel">Удалить загруженный текст</button>`;
  else if (st && st.busy) action = `<button class="bigbtn" disabled>Загрузка… ${st.kb ? Math.round(st.kb / 1024) + ' КБ' : ''}</button><div class="note2">Можно не ждать — загрузка продолжится в фоне.</div>`;
  else action = `<button class="bigbtn" id="dlGo">Загрузить текст на телефон</button>
    <div class="note2">${st && st.err ? `<span class="errline">Не удалось: ${esc(st.err)}</span><br>` : ''}Нужен интернет. Текст загружается с cr.minzdrav.gov.ru без иллюстраций и дальше открывается без сети.</div>`;
  view.innerHTML = `<div class="meta"><h2>${esc(x.name)}</h2>
      <div class="kv">КР${esc(x.id)} · <b>${AGE[x.age] || ''}</b> · опубликовано ${fmtDate(x.pub)}</div>
      <div class="kv">Разработчик: ${esc(x.ass)}</div>
      <div class="kv">Коды МКБ-10: ${esc(x.mkb)}</div></div>
    <div class="crbox">${action}</div>
    ${sch.length ? `<div class="sec-h">Схемы для фельдшера</div><ul class="list">${sch.map(s => `<li><a href="#d/${s}"><span class="ti sm"><svg viewBox="0 0 24 24"><path d="${ICON[s] || ICON.bol}"/></svg></span><span class="nm"><b>${esc(byId[s].title)}</b></span><span class="chev">›</span></a></li>`).join('')}</ul>` : ''}
    <div class="sec-h">Оригинал (нужен интернет)</div>
    <ul class="list"><li><a href="${site}"><span class="nm">Открыть на сайте cr.minzdrav.gov.ru</span><span class="chev">›</span></a></li>
      <li><a href="${pdf}"><span class="nm">Скачать PDF (с иллюстрациями)</span><span class="chev">›</span></a></li></ul>`;
  const b = $('#dlGo');
  if (b) b.onclick = () => { DLSTATE[id] = { busy: true }; call('download', id); crPage(id); };
  const del = $('#dlDel');
  if (del) del.onclick = () => { call('dlDelete', id); dlSet().delete(id); crPage(id); };
}
window.onDlProgress = (id, bytes) => {
  DLSTATE[id] = { busy: true, kb: bytes };
  if (cur === '#cr/' + id) { const btn = $('.bigbtn'); if (btn) btn.textContent = `Загрузка… ${Math.round(bytes / 1024)} КБ`; }
};
window.onDl = (id, ok, msg) => {
  DLSTATE[id] = ok ? {} : { err: msg || 'ошибка' };
  if (ok) dlSet().add(id);
  if (cur === '#cr/' + id) crPage(id);
};

// ---------------------------------------------------------------- calculators
function calcPage(k) {
  ({ bmi: calcBmi, gcs: calcGcs, shock: calcShock, vas: calcVas, skin: calcSkin }[k] || home)();
}
function numField(id, label, unit, val, ph) {
  return `<label class="nf"><span>${esc(label)}</span><input id="${id}" type="number" inputmode="decimal" value="${esc(val == null ? '' : val)}" placeholder="${esc(ph || '')}"><em>${esc(unit)}</em></label>`;
}
const num = id => { const v = parseFloat(String(($('#' + id) || {}).value || '').replace(',', '.')); return isFinite(v) ? v : NaN; };
const f1 = v => String(Math.round(v * 10) / 10).replace('.', ',');
const f2 = v => String(Math.round(v * 100) / 100).replace('.', ',');
function srcLine(list) { return `<div class="csrc">Источник: ${list.map(c => `<a href="#cr/${c}" class="src kr">КР${c}</a>`).join(' ')}</div>`; }

// ---------------------------------------------------------------- skin elements (data: content_skin.js)
function calcSkin() {
  setTitle('Кожные элементы', false);
  const T = window.SKIN || {};
  const qs = new URLSearchParams((location.hash.split('?')[1]) || '');
  const path = (qs.get('p') || 'start').split(',').filter(k => T[k]);
  if (!path.length || path[0] !== 'start') path.unshift('start');
  const id = path[path.length - 1], n = T[id];
  const to = next => '#calc/skin?p=' + [...path, next].join(',');
  // answers so far
  const trail = path.slice(0, -1).map((k, i) => {
    const o = (T[k].opts || []).find(x => x.go === path[i + 1]);
    return o ? `<a class="sktr" href="#calc/skin?p=${path.slice(0, i + 1).join(',')}">${esc(o.t)}</a>` : '';
  }).join('<span class="skar">›</span>');
  let h = trail ? `<div class="sktrail">${trail}</div>` : '';
  if (n.q) {
    h += `<div class="calc-card skq"><div class="skstep">Шаг ${path.length}</div><h2>${esc(n.q)}</h2>${n.hint ? `<div class="skhint">${esc(n.hint)}</div>` : ''}
      <div class="skopts">${n.opts.map(o => `<a class="skopt${o.red ? ' red' : ''}" href="${to(o.go)}"><b>${esc(o.t)}</b>${o.sub ? `<small>${esc(o.sub)}</small>` : ''}<span class="chev">›</span></a>`).join('')}</div></div>`;
  } else {
    const kr = c => ` <a href="#cr/${c}" class="src kr">КР${c}</a>`;
    h += `<div class="calc-card skres${n.urgent ? ' urgent' : ''}">
      ${n.kind ? `<div class="skkind">${esc(n.kind)}</div>` : ''}<h2>${esc(n.r)}</h2><p class="skdef">${esc(n.def)}</p>
      ${n.urgentIfFever ? '<div class="skalarm">Есть лихорадка или ребёнок/взрослый выглядит тяжело — вызов СМП немедленно (менингококковая инфекция).</div>' : ''}
      ${n.act ? `<h3>Что делать</h3><ol class="skact">${n.act.map(x => `<li>${esc(x)}</li>`).join('')}</ol>` : ''}
      ${n.think ? `<h3>О чём подумать</h3><ul class="skthink">${n.think.map(x => `<li>${esc(x.t)}${x.kr ? kr(x.kr) : ''}</li>`).join('')}</ul>` : ''}
      ${n.links ? `<div class="sklinks">${n.links.map(l => `<a href="${l.h}">${esc(l.t)} ›</a>`).join('')}</div>` : ''}
      ${n.kr ? `<div class="csrc">Источник:${n.kr.map(kr).join('')}</div>` : ''}
    </div>`;
    if (n.el) h += `<div class="calc-card skchart"><h3>Запись в карту</h3><p>Сыпь: <b>${esc(n.el)}</b>; локализация — …; размер — … мм; цвет — …; границы чёткие / нечёткие;
      единичные / множественные, склонность к слиянию / группировке; зуд, боль — …; когда появилась и как распространялась — …</p></div>`;
    h += `<div class="skbtns"><a class="bigbtn" href="#calc/skin">Определить другой элемент</a></div>`;
  }
  h += `<div class="disc">Определитель подсказывает морфологию элемента и направление поиска, диагноз не ставит. Морфология — общепринятая (пропедевтика дерматовенерологии); подсказки о болезнях — по клиническим рекомендациям, где они есть.</div>`;
  view.innerHTML = h;
  window.scrollTo(0, 0);
}

function calcBmi() {
  setTitle('Индекс массы тела', false);
  const B = [[0, 18.5, 'Дефицит массы тела', 't2', 'Низкий (повышен риск других заболеваний)'], [18.5, 25, 'Нормальная масса тела', 't0', 'Обычный'],
    [25, 30, 'Избыточная масса тела', 't2', 'Повышенный'], [30, 35, 'Ожирение I степени', 't3', 'Высокий'], [35, 40, 'Ожирение II степени', 't4', 'Очень высокий'], [40, 999, 'Ожирение III степени', 't5', 'Чрезвычайно высокий']];
  const c = LS.get('bmi', {});
  view.innerHTML = `<div class="calc-card">${numField('w', 'Масса тела', 'кг', c.w, '70')}${numField('h', 'Рост', 'см', c.h, '170')}
    <div class="res" id="res"></div></div>
    <div class="cls g2 static"><h3>Классификация по ИМТ (ВОЗ)</h3><div class="hd"><span>Масса тела</span><span>ИМТ, кг/м² · риск</span><span></span></div>
    ${B.map((b, i) => `<div class="crow ${b[3]}" data-i="${i}"><div class="r"><span class="nm"><span class="dot"></span>${b[2]}</span><span>${b[0] ? (b[1] < 999 ? `${f1(b[0])}–${f1(b[1] - 0.1)}` : `≥ ${b[0]}`) : '< 18,5'} · ${b[4]}</span><span></span></div></div>`).join('')}</div>
    <div class="disc">Окружность талии > 94 см у мужчин и > 80 см у женщин — абдоминальное ожирение (фактор риска, КР62_3).</div>${srcLine(['28_3'])}`;
  const upd = () => {
    const w = num('w'), h = num('h') / 100;
    LS.set('bmi', { w: $('#w').value, h: $('#h').value });
    document.querySelectorAll('.crow').forEach(r => r.classList.remove('hl'));
    if (!(w > 0 && h > 0.5)) { $('#res').innerHTML = '<span class="cmuted">Введите массу и рост</span>'; return; }
    const bmi = w / (h * h); const i = B.findIndex(b => bmi >= b[0] && bmi < b[1]);
    $('#res').innerHTML = `<div class="big ${B[i][3]}">${f1(bmi)}<small>кг/м²</small></div><div class="rl">${B[i][2]}</div><div class="rs">Риск сопутствующих заболеваний: ${B[i][4].toLowerCase()}</div>`;
    const row = document.querySelector(`.crow[data-i="${i}"]`); if (row) row.classList.add('hl');
  };
  view.querySelectorAll('input').forEach(x => x.addEventListener('input', upd)); upd();
}

const GCS = {
  adult: { E: [[4, 'Произвольное'], [3, 'На звук (голос)'], [2, 'На давление (боль)'], [1, 'Нет ответа']],
    V: [[5, 'Ориентирован (имя, место, время)'], [4, 'Дезориентирован, но общается'], [3, 'Отдельные слова'], [2, 'Нечленораздельные звуки'], [1, 'Нет ответа']],
    M: [[6, 'Выполняет инструкции'], [5, 'Локализует боль'], [4, 'Нормальное сгибание (отдёргивает)'], [3, 'Патологическое сгибание'], [2, 'Разгибание'], [1, 'Нет ответа']] },
  child: { E: [[4, 'Спонтанное'], [3, 'На звук'], [2, 'На боль'], [1, 'Нет']],
    V: [[5, 'Улыбается, ориентируется на звук, следит за объектами'], [4, 'При плаче можно успокоить, интерактивность неполная'], [3, 'При плаче успокаивается ненадолго, стонет'], [2, 'Не успокаивается при плаче, беспокоен'], [1, 'Отсутствует']],
    M: [[6, 'Выполнение инструкций'], [5, 'Локализация боли'], [4, 'Отдёргивание на боль'], [3, 'Патологическое сгибание на боль'], [2, 'Патологическое разгибание на боль'], [1, 'Отсутствует']] }
};
const GCS_KEY = [[15, 15, 'Ясное сознание', 't0'], [13, 14, 'Умеренное оглушение', 't2'], [10, 12, 'Глубокое оглушение', 't3'], [8, 9, 'Сопор', 't4'], [6, 7, 'Умеренная кома', 't5'], [4, 5, 'Глубокая кома', 't6'], [3, 3, 'Атоническая (терминальная) кома', 't6']];
function calcGcs() {
  setTitle('Шкала комы Глазго', false);
  const st = LS.get('gcs', { mode: 'adult', E: 0, V: 0, M: 0 });
  const render = () => {
    const sc = GCS[st.mode];
    const grp = (k, title) => `<div class="gq"><div class="gh">${title} <b>${k}</b></div>${sc[k].map(([v, t]) =>
      `<button class="gopt ${st[k] === v ? 'on' : ''}" data-k="${k}" data-v="${v}"><span class="gv">${v}</span>${esc(t)}</button>`).join('')}</div>`;
    const sum = st.E && st.V && st.M ? st.E + st.V + st.M : 0;
    let res = '<span class="cmuted">Выберите лучшую реакцию в каждой группе</span>';
    if (sum) {
      const k = GCS_KEY.find(x => sum >= x[0] && sum <= x[1]);
      res = `<div class="big ${k[3]}">${sum}<small>E${st.E} V${st.V} M${st.M}</small></div><div class="rl">${k[2]}</div>
        ${sum <= 8 ? '<div class="alarm">≤ 8 баллов — тяжёлое угнетение сознания (при ЧМТ — тяжёлая, КР732_2). Вызов СМП, положение на боку, контроль дыхания и проходимости дыхательных путей.</div>' : ''}`;
    }
    view.innerHTML = `<div class="seg n2 gm"><a class="${st.mode === 'adult' ? 'on' : ''}" data-m="adult">Взрослые</a><a class="${st.mode === 'child' ? 'on' : ''}" data-m="child">Дети до 4 лет</a></div>
      <div class="calc-card sticky"><div class="res">${res}</div></div>
      ${grp('E', 'Открывание глаз')}${grp('V', 'Речевая реакция')}${grp('M', 'Двигательная реакция')}
      <div class="disc">Оценивается лучшая реакция. Если фактор мешает оценке (интубация, отёк век, парез) — компонент «оценить невозможно», сумму не считать. В КР814_1 указано, что запись по компонентам (например, E2V3M4) корректнее, чем трактовка суммы. Градация — по КР734_2; ≤ 8 баллов — тяжёлое повреждение (КР732_2).</div>
      ${srcLine(['814_1', '734_2', '732_2'])}`;
    view.querySelectorAll('.gopt').forEach(b => b.onclick = () => { st[b.dataset.k] = +b.dataset.v; LS.set('gcs', st); render(); });
    view.querySelectorAll('.gm a').forEach(a => a.onclick = () => { st.mode = a.dataset.m; st.E = st.V = st.M = 0; LS.set('gcs', st); render(); });
  };
  render();
}

function calcShock() {
  setTitle('Индекс Альговера', false);
  const c = LS.get('shock', { sex: 'm' });
  const K = [[0, 0.8, 'Норма (около 0,54)', 0, 't0'], [0.8, 0.9, 'Кровопотеря около 10% ОЦК', 10, 't2'], [0.9, 1.3, 'Кровопотеря около 20% ОЦК', 20, 't3'], [1.3, 1.5, 'Кровопотеря около 30% ОЦК', 30, 't4'], [1.5, 99, 'Кровопотеря 40% ОЦК и более', 40, 't6']];
  view.innerHTML = `<div class="calc-card">${numField('hr', 'Пульс (ЧСС)', 'уд/мин', c.hr, '80')}${numField('sbp', 'Систолическое АД', 'мм рт. ст.', c.sbp, '120')}
    <div class="seg n2 sx"><a class="${c.sex === 'm' ? 'on' : ''}" data-s="m">Мужчина · ОЦК 5200</a><a class="${c.sex === 'f' ? 'on' : ''}" data-s="f">Женщина · ОЦК 3900</a></div>
    <div class="res" id="res"></div></div>
    <div class="cls g2 static"><h3>Интерпретация</h3><div class="hd"><span>Индекс = ЧСС / САД</span><span>Кровопотеря</span><span></span></div>
    ${[['< 0,8', 'норма (0,54)'], ['0,8', 'около 10%'], ['0,9–1,2', 'около 20%'], ['1,3–1,4', 'около 30%'], ['≥ 1,5', '40% и более']].map((r, i) => `<div class="crow ${K[i][4]}" data-i="${i}"><div class="r"><span class="nm"><span class="dot"></span>${r[0]}</span><span>${r[1]}</span><span></span></div></div>`).join('')}</div>
    <div class="disc">Ориентировочная оценка. Искажается при приёме β-блокаторов, кардиостимуляторе, у пожилых. Дети: тревожный индекс > 1,22 в 4–6 лет, > 1 в 6–12 лет, > 0,9 с 13 лет (КР938_1).</div>
    ${srcLine(['869_1', '700_3', '938_1'])}`;
  const upd = () => {
    const hr = num('hr'), sbp = num('sbp');
    LS.set('shock', { hr: $('#hr').value, sbp: $('#sbp').value, sex: c.sex });
    document.querySelectorAll('.crow').forEach(r => r.classList.remove('hl'));
    if (!(hr > 0 && sbp > 0)) { $('#res').innerHTML = '<span class="cmuted">Введите пульс и систолическое АД</span>'; return; }
    const si = hr / sbp; const i = K.findIndex(k => si >= k[0] && si < k[1]);
    const ocv = c.sex === 'm' ? 5200 : 3900;
    $('#res').innerHTML = `<div class="big ${K[i][4]}">${f2(si)}</div><div class="rl">${K[i][2]}</div>
      ${K[i][3] ? `<div class="rs">≈ ${Math.round(ocv * K[i][3] / 100 / 50) * 50} мл из ${ocv} мл</div>` : ''}
      ${si >= 1 ? '<div class="alarm">Индекс ≥ 1 — признак шока: вызов СМП, венозный доступ, остановка кровотечения (раздел «Шоки»).</div>' : ''}`;
    const row = document.querySelector(`.crow[data-i="${i}"]`); if (row) row.classList.add('hl');
  };
  view.querySelectorAll('input').forEach(x => x.addEventListener('input', upd));
  view.querySelectorAll('.sx a').forEach(a => a.onclick = () => { c.sex = a.dataset.s; view.querySelectorAll('.sx a').forEach(x => x.classList.toggle('on', x === a)); upd(); });
  upd();
}

function calcVas() {
  setTitle('Шкала боли (ВАШ)', false);
  let v = LS.get('vas', 0);
  const lab = x => x === 0 ? ['Боли нет', 't0'] : x <= 3 ? ['Слабая боль', 't1'] : x <= 6 ? ['Умеренная боль', 't3'] : ['Сильная боль', 't5'];
  const face = x => {
    const m = x <= 1 ? 'M8 14c2 2 6 2 8 0' : x <= 4 ? 'M8 15h8' : x <= 7 ? 'M8 16c2-1.5 6-1.5 8 0' : 'M8 17c2-2.5 6-2.5 8 0';
    const br = x >= 8 ? '<path d="M7 8l3 1.5M17 8l-3 1.5"/>' : '';
    return `<svg viewBox="0 0 24 24" class="face"><circle cx="12" cy="12" r="10"/><circle cx="9" cy="10.5" r=".8" fill="currentColor"/><circle cx="15" cy="10.5" r=".8" fill="currentColor"/>${br}<path d="${m}"/></svg>`;
  };
  view.innerHTML = `<div class="calc-card"><div class="res" id="res"></div>
      <input id="vs" class="vas" type="range" min="0" max="10" step="1" value="${v}">
      <div class="vasticks">${Array.from({ length: 11 }, (_, i) => `<span>${i}</span>`).join('')}</div>
      <div class="vasends"><span>боли нет</span><span>самая сильная боль</span></div></div>
      <div class="cls g2 static"><h3>Интенсивность</h3>
      ${[['0', 'нет боли', 't0'], ['1–3', 'слабая', 't1'], ['4–6', 'умеренная', 't3'], ['7–10', 'сильная', 't5']].map(r => `<div class="crow ${r[2]}" data-t="${r[2]}"><div class="r"><span class="nm"><span class="dot"></span>${r[0]}</span><span>${r[1]}</span><span></span></div></div>`).join('')}</div>
      <div class="disc">Пациент сам отмечает точку на линии 10 см (ВАШ) или называет число 0–10 (ЧРШ): 0 — боли нет, 5 — умеренная, 10 — самая сильная, какую можно представить (КР616_1). Оценивать при обращении и в динамике (КР778_1). Градация 1–3 / 4–6 / 7–10 — общепринятая.</div>
      ${srcLine(['616_1', '778_1'])}`;
  const upd = () => {
    const [t, c] = lab(v);
    $('#res').innerHTML = `<div class="vasface ${c}">${face(v)}</div><div class="big ${c}">${v}<small>из 10</small></div><div class="rl">${t}</div>`;
    document.querySelectorAll('.crow').forEach(r => r.classList.toggle('hl', r.dataset.t === c));
    $('#vs').style.setProperty('--p', (v * 10) + '%');
  };
  $('#vs').addEventListener('input', e => { v = +e.target.value; LS.set('vas', v); upd(); });
  upd();
}

// ---------------------------------------------------------------- disease
function disease(id, kind) {
  const d = byId[id];
  if (!d) { recPage(); return; }
  setTitle(d.title, false);
  let i = kind != null && kind !== '' && d.sections[+kind] ? +kind : (S.tab[id] || 0);
  if (!d.sections[i]) i = 0;
  S.tab[id] = i;
  const sec = d.sections[i];
  const hasKids = d.sections.some(x => x.kind === 'kids');
  const label = x => x.tab || (x.title && x.title.length <= 14 ? x.title :
    x.kind === 'urgent' ? 'Неотложно' : x.kind === 'kids' ? 'Дети' : x.kind === 'cls' ? 'Классификация' : (hasKids ? 'Взрослые' : 'Плановое'));
  let h = `<div class="dhead"><h2>${esc(d.title)}</h2><div class="sub">${esc(d.sub)}</div></div>
    <div class="seg n${d.sections.length}">${d.sections.map((x, j) => `<a class="${j === i ? 'on' : ''} k-${x.kind}" href="#d/${id}/${j}" data-k="${j}">${esc(label(x))}</a>`).join('')}</div>`;
  if (label(sec) !== sec.title) h += `<div class="sectitle">${esc(sec.title)}</div>`;
  if (sec.kind === 'kids' || JSON.stringify(sec.blocks).includes('"kg":')) {
    h += `<div class="kgbar"><label for="kg">${sec.kind === 'kids' ? 'Масса ребёнка' : 'Масса пациента'}</label><input id="kg" type="number" inputmode="decimal" min="1" max="150" step="0.5" value="${esc(kgW)}" placeholder="—"><span>кг</span></div><div class="kgwarn" id="kgwarn" hidden></div>`;
  }
  h += '<div class="blocks">' + sec.blocks.map(block).join('') + '</div>';
  const names = crNames();
  h += `<div class="srcs"><div class="sec-h">Источники</div>${d.crs.map(c => `<a class="srcrow" href="#cr/${c}"><span class="src kr">КР${esc(c)}</span><span>${esc(names[c] || '')}</span><span class="chev">›</span></a>`).join('')}</div>`;
  view.innerHTML = h;
  // keep tab switches from piling up history
  view.querySelectorAll('.seg a').forEach(a => a.onclick = e => {
    e.preventDefault(); S.tab[id] = +a.dataset.k; history.replaceState(null, '', '#d/' + id + '/' + a.dataset.k); stack[stack.length - 1] = location.hash; cur = location.hash; disease(id, a.dataset.k); window.scrollTo(0, 0);
  });
  wireBlocks(view);
  const kg = $('#kg');
  if (kg) kg.addEventListener('input', () => { kgW = kg.value; LS.set('kg', kgW); updateCalc(); });
  updateCalc();
}
function md(t) {
  return esc(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\*(.+?)\*/g, '<i>$1</i>').replace(/\n/g, '<br>');
}
function srcBadge(src) {
  if (!src) return '';
  return src.split(/[;+]/).map(x => x.trim()).filter(Boolean).map(x =>
    x.startsWith('КР') ? `<span class="src kr">${esc(x)}</span>` : `<span class="src ins">${esc(x)}</span>`).join('');
}
function drugItem(x) {
  if (x && x.one) {
    return `<div class="pick"><div class="ph"><span class="onebadge">ОДИН ИЗ</span>${esc(x.one)}</div>${x.opts.map(o => drugRow(o, true)).join('')}</div>`;
  }
  return drugRow(x);
}
const suspForms = k => (k && typeof SUSP !== 'undefined' && SUSP[k]) || null;
function suspBox(k) {
  const f = suspForms(k);
  if (!f) return '';
  const ready = f.every(x => x.ready);
  return `<details class="susp"><summary>${ready ? 'Готовая суспензия: сколько мл' : 'Суспензия: как приготовить и сколько мл'}</summary>
    ${f.map(x => `<div class="sf"><b>${esc(x.lbl)}</b> <span class="sb">${esc(x.brand || '')}</span><div class="sp">${esc(x.prep)}</div></div>`).join('')}
    <div class="sfoot">${srcBadge('инстр.')} ${ready ? 'Сверьте концентрацию на флаконе — от неё зависит объём.' : 'Объём воды и срок хранения — по инструкции конкретного препарата; сверьте концентрацию на флаконе.'}</div></details>`;
}
function drugRow(x, opt) {
  return `<div class="drug${opt ? ' opt' : ''}"${x.kg ? ` data-kg='${esc(JSON.stringify(x.kg))}'` : ''}${x.susp ? ` data-susp="${esc(x.susp)}"` : ''}${x.adult ? ` data-adult='${esc(JSON.stringify(x.adult))}'` : ''}>
    <div class="dn">${esc(x.n)}</div>
    <div class="dd">${esc(x.d)}</div>
    ${x.note ? `<div class="dnote">${esc(x.note)}</div>` : ''}
    ${x.kg ? '<div class="calc"></div>' : ''}
    ${suspBox(x.susp)}
    <div class="dsrc">${srcBadge(x.src)}${DM && DM.has(x.n) ? ` <a class="dlink" href="${DM.href(x.n)}">Инструкция ›</a>` : ''}</div></div>`;
}
const DOW = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];
const DOW_S = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
const isToday = c => { const s = String(c).toLowerCase(), d = new Date().getDay(); return s === DOW[d] || s === DOW_S[d]; };
function block(b) {
  const src = b.src ? `<div class="bsrc">${srcBadge(b.src)}</div>` : '';
  switch (b.t) {
    case 'flags':
      return `<section class="b flags"><h3><svg viewBox="0 0 24 24"><path d="M12 3l10 18H2zM12 10v5M12 18v.5"/></svg>${esc(b.h)}</h3>
        <ul>${b.items.map(i => `<li>${esc(i)}</li>`).join('')}</ul>${b.note ? `<div class="bnote">${esc(b.note)}</div>` : ''}${src}</section>`;
    case 'warn':
      return `<section class="b warn"><h3><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M6 6l12 12"/></svg>${esc(b.h)}</h3>
        <ul>${b.items.map(i => `<li>${esc(i)}</li>`).join('')}</ul>${src}</section>`;
    case 'exam':
      return `<section class="b exam"><h3><svg viewBox="0 0 24 24"><path d="M9 5h6M9 3h6v4H9zM6 5H5v16h14V5h-1M8 12l2 2 4-4"/></svg>${esc(b.h)}</h3>
        <ul class="check">${b.items.map(i => `<li>${esc(i)}</li>`).join('')}</ul>${b.note ? `<div class="bnote">${esc(b.note)}</div>` : ''}${src}</section>`;
    case 'targets':
      return `<section class="b targets"><h3><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r=".5"/></svg>${esc(b.h)}</h3>
        <ul>${b.items.map(i => `<li>${esc(i)}</li>`).join('')}</ul>${src}</section>`;
    case 'scheme':
      return `<section class="b scheme"><h3>${esc(b.h)}</h3><div class="ladder">${b.items.map(i =>
        `<div class="rung"><div class="rs">${esc(i.s)}</div><div class="rt">${esc(i.text)}</div></div>`).join('<div class="arrow">↓</div>')}</div>${src}</section>`;
    case 'steps':
      return `<section class="b steps"><h3>${esc(b.h)}</h3><ol class="flow">${b.items.map(i =>
        `<li><div class="st">${esc(i.s.replace(/^\d+\.\s*/, ''))}${i.src && !i.drugs ? ' ' + srcBadge(i.src) : ''}</div>
          ${i.drugs ? `<div class="drugs">${i.drugs.map(drugItem).join('')}</div>` : ''}
          ${i.note ? `<div class="dnote">${esc(i.note)}</div>` : ''}</li>`).join('')}</ol>${src}</section>`;
    case 'rx':
      return `<section class="b rx"><h3><svg viewBox="0 0 24 24"><rect x="3" y="9" width="18" height="7" rx="3.5" transform="rotate(-45 12 12.5)"/><path d="M9.5 10l5 5"/></svg>${esc(b.h)}</h3>
        <div class="drugs">${b.rows.map(drugItem).join('')}</div>${b.note ? `<div class="bnote">${esc(b.note)}</div>` : ''}${src}</section>`;
    case 'table':
      return `<section class="b ttab c${b.cols.length}${b.tones ? ' toned' : ''}"><h3>${esc(b.h)}</h3><div class="tw"><table><thead><tr>${b.cols.map((c, i) => `<th class="${b.tones ? 'tt' + (b.tones[i] || '') : ''}">${esc(c)}</th>`).join('')}</tr></thead>
        <tbody>${b.rows.map(r => `<tr${isToday(r[0]) ? ' class="today"' : ''}>${r.map((c, i) => i === 0 ? `<th>${esc(c)}</th>` : `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>${b.note ? `<div class="bnote">${esc(b.note)}</div>` : ''}${src}</section>`;
    case 'note':
      return `<section class="b note"><p>${esc(b.text)}</p>${src}</section>`;
    case 'img': {
      const u = /^https?:/.test(b.img) ? b.img : SITE + b.img;
      return `<figure class="b bimg">${b.h ? `<h3>${esc(b.h)}</h3>` : ''}<a href="${esc(u)}" target="_blank" rel="noopener"><img src="${esc(u)}" alt="${esc(b.caption || b.h || 'схема')}" loading="lazy"
        onerror="this.closest('figure').classList.add('noimg')"></a><div class="imgoff">Схема не загрузилась — нужен интернет.</div>${b.caption ? `<figcaption>${esc(b.caption)}</figcaption>` : ''}${src}</figure>`;
    }
    case 'classify': return classifyBlock(b);
    case 'tiles': return tilesBlock(b);
    case 'fold':
      return `<details class="fold"><summary>${esc(b.h)}<span>${esc(b.sub || '')}</span></summary><div class="in">${b.items.map(i => `<p>${md(i)}</p>`).join('')}${src}</div></details>`;
  }
  return '';
}
let BID = 0;
function altList(a) {
  if (!a || !a.length) return '';
  if (a.length === 1) return `<div class="ex">${md(a[0])}</div>`;
  return `<div class="alts"><div class="altsh">выберите один:</div>${a.map(t => `<div class="alt">${md(t)}</div>`).join('')}</div>`;
}
function moreList(m) {   // раскрывающиеся альтернативы внутри ступени лечения: [{h, items:[...]}]
  if (!m || !m.length) return '';
  return m.map(g => `<details class="more"><summary>${md(g.h)} <span>${g.items.length}</span></summary>${g.items.map(t => `<div class="alt">${md(t)}</div>`).join('')}</details>`).join('');
}
function stepTable(steps, defs, head) {
  const list = (steps || []).map(x => typeof x === 'string' ? (defs || {})[x] : x).filter(Boolean);
  if (!list.length) return '';
  return `<table class="tx"><thead><tr><th>${esc(head || 'Шаг')}</th><th>Что назначить</th></tr></thead><tbody>${list.map(x =>
    `<tr><td>${md(x.s)}</td><td><div class="combo">${md(x.combo)}</div>${x.ex ? `<div class="ex">${md(x.ex)}</div>` : ''}${altList(x.alt)}${moreList(x.more)}${x.note ? `<div class="ex ${/(^не\s|нельзя|риск|не при)/i.test(x.note) ? 'warnline' : 'noteline'}">${md(x.note)}</div>` : ''}<div class="tsrc">${srcBadge(x.src)}</div></td></tr>`).join('')}</tbody></table>`;
}
function classifyBlock(b) {
  const id = 'c' + (BID++);
  const n = b.cols.length;
  const grid = n === 4 ? (b.wide ? 'g4 g4w' : 'g4') : 'g2';
  let h = `<section class="cls ${grid}" id="${id}"><h3>${esc(b.h)}</h3>${b.hint ? `<div class="hint">${esc(b.hint)}</div>` : ''}
    <div class="hd">${b.cols.map(c => `<span>${esc(c)}</span>`).join('')}<span></span></div>`;
  b.rows.forEach((r, i) => {
    const has = (r.steps && r.steps.length) || (r.when && r.when.length) || r.lead;
    h += `<div class="crow t${r.tone || 0}" data-i="${i}"><div class="r">${r.c.map((c, j) => j === 0 ? `<span class="nm"><span class="dot"></span>${esc(c)}</span>` : `<span>${esc(c)}</span>`).join('')}<span class="ch">${has ? '›' : ''}</span></div>
      <div class="det" hidden>${r.lead ? `<div class="lead">${md(r.lead)}</div>` : ''}
        ${r.when && r.when.length ? `<div class="when">${r.when.map(([k, t]) => `<span class="${k}">${md(t)}</span>`).join('')}</div>` : ''}
        ${stepTable(r.steps, b.defs)}
        ${r.nb ? `<div class="nb">${md(r.nb)}</div>` : ''}<div class="tsrc">${srcBadge(r.src || b.src)}</div></div></div>`;
  });
  return h + '</section>';
}
function tilesBlock(b) {
  const id = 't' + (BID++);
  return `<div class="sec-h">${esc(b.h)}</div><div class="sit" id="${id}">${b.items.map((x, i) =>
    `<button class="sitb" data-i="${i}"${x.link ? ` data-link="${esc(x.link)}"` : ''}>${esc(x.n)}<small>${esc(x.s || '')}</small></button>`).join('')}</div>
    ${b.items.map((x, i) => `<div class="cls sitd" data-for="${id}" data-i="${i}" hidden><h3>${esc(x.n)}</h3><div class="det">
      <table class="tx"><thead><tr><th></th><th>Что назначить</th></tr></thead><tbody>${x.rows.map(r =>
        `<tr><td>${md(r[0])}</td><td><div class="combo">${md(r[1])}</div>${Array.isArray(r[2]) ? altList(r[2]) : r[2] ? `<div class="ex">${md(r[2])}</div>` : ''}<div class="tsrc">${srcBadge(r[3])}</div></td></tr>`).join('')}</tbody></table>
      ${x.nb ? `<div class="nb">${md(x.nb)}</div>` : ''}${x.link ? `<a class="golink" href="#d/${esc(x.link)}">Открыть раздел ›</a>` : ''}</div></div>`).join('')}`;
}
function scrollToEl(el) {
  const seg = $('.seg'); const off = 52 + (seg ? seg.offsetHeight + 12 : 0) + 6;
  window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - off, behavior: 'smooth' });
}
function wireBlocks(root) {
  root.querySelectorAll('.crow').forEach(row => {
    const r = row.querySelector('.r'), det = row.querySelector('.det');
    if (!row.querySelector('.ch').textContent) return;
    r.onclick = () => {
      const open = det.hidden;
      row.parentNode.querySelectorAll('.crow').forEach(o => { o.classList.remove('open'); o.querySelector('.det').hidden = true; });
      if (open) { row.classList.add('open'); det.hidden = false; setTimeout(() => scrollToEl(row), 30); }
    };
  });
  root.querySelectorAll('.sit').forEach(box => {
    box.querySelectorAll('.sitb').forEach(btn => btn.onclick = () => {
      const i = btn.dataset.i, on = !btn.classList.contains('on');
      box.querySelectorAll('.sitb').forEach(x => x.classList.remove('on'));
      root.querySelectorAll(`.sitd[data-for="${box.id}"]`).forEach(x => x.hidden = true);
      if (on) { btn.classList.add('on'); const d = root.querySelector(`.sitd[data-for="${box.id}"][data-i="${i}"]`); d.hidden = false; setTimeout(() => scrollToEl(d), 30); }
    });
  });
}
function fmtN(v, unit) {
  if (unit === 'капель') return String(Math.round(v));
  if (unit === 'ЕД') return String(Math.round(v / 100) * 100);
  if (v < 1) return String(Math.round(v * 100) / 100).replace('.', ',');
  if (v >= 100) return String(Math.round(v / 5) * 5);
  if (v >= 10) return String(Math.round(v));
  return String(Math.round(v * 10) / 10).replace('.', ',');
}
function rng(a, b, unit) { return a === b ? fmtN(a, unit) : `${fmtN(a, unit)}–${fmtN(b, unit)}`; }
function updateCalc() {
  const w = parseFloat(String(kgW).replace(',', '.'));
  const kids = /ребёнка/.test((document.querySelector('.kgbar label') || {}).textContent || '');
  const warn = $('#kgwarn');
  if (warn) {
    let t = '';
    if (w >= 200 || w <= 0) t = 'Проверьте массу тела.';
    else if (kids && w > 100) t = 'Проверьте массу: для ребёнка это необычно много. При массе ≥ 40 кг дозы — как для взрослых.';
    else if (kids && w >= 40) t = 'Масса ≥ 40 кг: антибиотики и жаропонижающие — в дозах для взрослых (КР313_3), расчёт на кг не применяется.';
    warn.textContent = t; warn.hidden = !t;
  }
  document.querySelectorAll('.drug[data-kg]').forEach(el => {
    const c = JSON.parse(el.dataset.kg), out = el.querySelector('.calc');
    if (!out) return;
    if (!(w > 0 && w < 200)) { out.innerHTML = '<span class="cmuted">Введите массу тела вверху — посчитаю дозу</span>'; return; }
    const ad = el.dataset.adult ? JSON.parse(el.dataset.adult) : null;
    if (ad && w >= ad.from) {
      out.innerHTML = `<span class="cw">${fmtN(w, 'мг')} кг:</span> масса ≥ ${ad.from} кг — <b>${esc(ad.lbl || 'доза для взрослых')}: ${esc(ad.d)}</b> ${srcBadge(ad.src)}`
        + (ad.lbl ? '' : '<br><span class="cap">Пересчёт на кг и детские суспензии не применяются.</span>');
      return;
    }
    const u = c.unit || 'мг';
    let lo = c.lo * w, hi = c.hi * w, capped = false, adultCap = false;
    // a child's dose never exceeds the adult one
    const capAdult = (v, m) => { if (m && v > m) { adultCap = true; return m; } return v; };
    let txt = '';
    if (c.per === 'сут') {
      if (c.max && hi > c.max) { hi = c.max; capped = true; } if (c.max && lo > c.max) lo = c.max;
      if (ad) { hi = capAdult(hi, ad.day); lo = Math.min(lo, hi); }
      txt = `<b>${rng(lo, hi, u)} ${u}/сут</b>`;
      if (c.div && c.div > 1) txt += ` → по <b>${rng(lo / c.div, hi / c.div, u)} ${u}</b> × ${c.div} р/сут`;
    } else {
      if (c.max && hi > c.max) { hi = c.max; capped = true; } if (c.max && lo > c.max) lo = c.max;
      if (ad) { hi = capAdult(hi, ad.dose); lo = Math.min(lo, hi); }
      txt = `<b>${rng(lo, hi, u)} ${u}</b> на приём`;
      if (c.maxDay) txt += `; не более <b>${fmtN(ad && ad.day ? capAdult(c.maxDay * w, ad.day) : c.maxDay * w, u)} ${u}/сут</b>`;
    }
    if (c.conc && c.per !== 'сут') txt += ` = <b>${rng(lo / c.conc, hi / c.conc, 'мл')} мл</b> <span class="cap">(${String(c.conc).replace('.', ',')} ${esc(c.concUnit || '')})</span>`;
    if (capped) txt += ` <span class="cap">(ограничено максимумом${c.maxNote ? ', ' + esc(c.maxNote) : ''})</span>`;
    if (adultCap) txt += ` <span class="cap">(не больше дозы для взрослых)</span>`;
    // pediatric forms: millilitres of suspension per dose / dispersible tablets
    const forms = suspForms(el.dataset.susp);
    if (forms && u === 'мг') {
      txt += forms.map(f => {
        const div = c.per === 'сут' ? (f.div || c.div || 1) : 1;
        const a1 = c.per === 'сут' ? lo / div : lo, b1 = c.per === 'сут' ? hi / div : hi;
        const times = c.per === 'сут' && div > 1 ? ` × ${div} р/сут` : '';
        if (f.tab) {
          let x1 = Math.ceil(a1 / f.tab) * f.tab, x2 = Math.floor(b1 / f.tab) * f.tab;
          if (x1 > x2) x1 = x2 = Math.max(f.tab, Math.round((a1 + b1) / 2 / f.tab) * f.tab);
          return `<div class="sml">${esc(f.brand)}: ≈ <b>${rng(x1, x2, 'мг')} мг</b>${times} <span class="cap">(таблетки 125/250/500 мг)</span></div>`;
        }
        const k = f.mg / f.ml;
        return `<div class="sml">${esc(f.lbl.replace(/ \(.*\)$/, ''))}: ${c.per === 'сут' ? 'по ' : ''}<b>${rng(a1 / k, b1 / k, 'мл')} мл</b>${times}</div>`;
      }).join('');
    }
    out.innerHTML = `<span class="cw">${fmtN(w, 'мг')} кг:</span> ${txt}`;
  });
}

// ---------------------------------------------------------------- updates (Android: MainActivity.checkUpdate)
const APP_VERSION = '4.5';
const SITE = 'https://victorpolekslab.github.io/Spravochnik_nmp/';
const updRes = t => { const el = $('#updRes'); if (el) el.textContent = t; };
window.onUpdateNone = () => updRes('У вас последняя версия');
window.onUpdateFail = () => updRes('Нет связи с сайтом — попробуйте позже');
window.onUpdateShown = () => updRes('Есть новая версия — см. внизу экрана');
window.onUpdate = info => {
  updRes('Есть новая версия — см. внизу экрана');
  if (!info || !info.url || $('.updbar')) return;
  const t = document.createElement('div');
  t.className = 'updbar';
  t.innerHTML = `<div class="tx"><b>Доступна версия ${esc(info.versionName || '')}</b>${info.notes ? `<small>${esc(info.notes)}</small>` : ''}</div>
    <a class="go" href="${esc(info.url)}">Скачать</a><button class="x" aria-label="Позже">×</button>`;
  t.querySelector('.x').onclick = () => t.remove();
  t.querySelector('.go').addEventListener('click', () => setTimeout(() => t.remove(), 500));
  document.body.appendChild(t);
};

// ---------------------------------------------------------------- about
function about() {
  setTitle('О справочнике', false);
  const names = crNames();
  const bundled = Object.values(crData()).filter(x => x.off);
  view.innerHTML = `<div class="about">
    <div class="card"><b style="font-size:17px">Справочник фельдшера неотложной медицинской помощи</b><p>Версия ${APP_VERSION}${contentLabel()} · клинические рекомендации от 03.11.2026</p>
      ${window.App ? '<button class="lnkbtn" id="updChk">Проверить обновления</button><span class="updres" id="updRes"></span>' : ''}</div>
    <div class="card"><b>Обучение</b><p><a href="#report">Отчёт по обучению</a> — для организатора: кто прослушал лекции и прошёл тесты.</p></div>
    <div class="card"><b>Поделиться с коллегами</b><p>iPhone и любой браузер: <a href="${SITE}">${SITE.replace('https://', '')}</a> — открыть в Safari → «Поделиться» → «На экран Домой».</p>
      <p>Android: <a href="${SITE}download/SpravochnikNMP.apk">скачать приложение (APK)</a>. Новые версии приложение предлагает само.</p></div>
    <div class="card"><b>Что это</b><p>Справочник фельдшера неотложной медицинской помощи по действующим клиническим рекомендациям Минздрава России. Во вкладках «Неотложно» — помощь до приезда СМП: без кислородотерапии, тромболизиса, наркотических анальгетиков и инфузомата. <span class="onebadge" style="margin:0">ОДИН ИЗ</span> — взаимозаменяемые препараты, выбирается один.</p>
      <p><span class="src kr">КР</span> — доза или положение из текста рекомендации (сверено автоматически); <span class="src ins">инстр.</span> — доза из инструкции к препарату, в КР её нет.</p></div>
    <div class="card"><b>МКБ-10 и рекомендации</b><p>Классификатор МКБ-10 (НСИ Минздрава, версия 2.27) и перечень всех действующих рекомендаций (${Object.keys(names).length}). Полные тексты ${bundled.length} рекомендаций встроены в приложение; остальные можно загрузить на телефон из карточки рекомендации (нужен интернет), дальше они открываются без сети. Загружено: ${dlSet().size}.</p></div>
    <div class="card"><b>Важно</b><p>Справочник не заменяет инструкцию к препарату и решение врача. В КР «Бронхиальная астма» (359_3) для преднизолона у взрослых указано «20–30 мг/кг/сут» — это опечатка в единицах, в схеме приведено 20–30 мг/сут.</p></div>
    <div class="card"><b>Встроенные рекомендации</b>${bundled.sort((x, y) => x.name.localeCompare(y.name)).map(x => `<p><a href="#doc/${x.id}">КР${esc(x.id)}</a> — ${esc(x.name)}</p>`).join('')}</div>
  </div>`;
  const b = $('#updChk');
  if (b) b.onclick = () => { $('#updRes').textContent = 'Проверяю…'; try { window.App.checkUpdate(); if (window.App.checkContent) window.App.checkContent(); } catch (e) { onUpdateFail(); } };
}
// ---------------------------------------------------------------- Document viewer
let docState = null;
function doc(id, ord, hq) {
  setTab('');
  const key = location.hash;
  const r = call('crDoc', id);
  if (!r.meta) { setTitle('Рекомендация', false); view.innerHTML = '<div class="empty">Документ не найден</div>'; return; }
  if (!r.sections || !r.sections.length) { history.replaceState(null, '', '#cr/' + id); stack[stack.length - 1] = location.hash; cur = location.hash; document.body.classList.remove('doc'); crPage(id); return; }
  const m = r.meta;
  setTitle(m.name, false);
  const rec = LS.get('recent', []).filter(x => x !== id); rec.unshift(id); LS.set('recent', rec.slice(0, 30));
  const isFav = LS.get('fav', []).includes(id);
  const site = 'https://cr.minzdrav.gov.ru/preview-cr/' + encodeURIComponent(id);
  const pdf = 'https://apicr.minzdrav.gov.ru/api.ashx?op=GetClinrecPdf&id=' + encodeURIComponent(id);
  let h = `<div class="doctools">
      <button class="tb" id="tTOC"><svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h10"/></svg>Содержание</button>
      <button class="tb" id="tFind" aria-label="Найти в документе"><svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/></svg></button>
      <button class="tb" id="tMinus" aria-label="Мельче">A−</button>
      <button class="tb" id="tPlus" aria-label="Крупнее">A+</button>
      <button class="tb ${isFav ? 'on' : ''}" id="tFav" aria-label="Избранное"><svg viewBox="0 0 24 24"><path d="M12 4l2.5 5.2 5.5.8-4 3.9.9 5.6L12 16.9 7.1 19.5 8 13.9 4 10l5.5-.8z"/></svg></button>
      <a class="tb" href="${site}">Сайт</a>
      <a class="tb" href="${pdf}">PDF</a>
    </div>
    <div class="findbar" id="findbar" hidden>
      <input id="fq" type="search" placeholder="Найти в документе" value="${esc(hq)}" autocomplete="off" enterkeyhint="search">
      <span class="cnt" id="fcnt"></span>
      <button class="tb" id="fPrev" aria-label="Предыдущее">↑</button>
      <button class="tb" id="fNext" aria-label="Следующее">↓</button>
      <button class="tb" id="fClose" aria-label="Закрыть">×</button>
    </div>
    <div class="meta">
      <h2>${esc(m.name)}</h2>
      <div class="kv">КР${esc(m.id)} · <b>${AGE[m.age] || ''}</b> · опубликовано ${fmtDate(m.pub)}</div>
      <div class="kv">Разработчик: ${esc(m.ass)}</div>
      <div class="mkbchips">${(r.mkb || []).map(c => `<a class="nolink" title="${esc(c.name || '')}">${esc(c.code)}</a>`).join('')}</div>
    </div>
    <div class="doc-body" id="db">`;
  r.sections.forEach(s => {
    const tag = s.lvl === 2 ? 'h3' : 'h2';
    h += `<${tag} class="sh" id="s${s.ord}" data-ord="${s.ord}">${esc(s.title)}</${tag}>`;
    if (s.html) h += `<div class="sb" data-ord="${s.ord}">${s.html}</div>`;
  });
  h += '</div>';
  view.innerHTML = h;
  view.querySelectorAll('#db table').forEach(t => {
    const w = document.createElement('div'); w.className = 'tw'; t.parentNode.insertBefore(w, t); w.appendChild(t);
  });
  docState = { id, secs: r.sections, marks: [], i: -1 };

  $('#tTOC').onclick = () => showToc();
  $('#tFind').onclick = () => { $('#findbar').hidden = false; $('#fq').focus(); };
  $('#fClose').onclick = () => { $('#findbar').hidden = true; clearMarks(); $('#fcnt').textContent = ''; };
  $('#tMinus').onclick = () => setFs(fs - 1);
  $('#tPlus').onclick = () => setFs(fs + 1);
  $('#tFav').onclick = e => {
    let f = LS.get('fav', []);
    if (f.includes(id)) f = f.filter(x => x !== id); else f.unshift(id);
    LS.set('fav', f); e.currentTarget.classList.toggle('on', f.includes(id));
  };
  const fq = $('#fq');
  const doFind = debounce(() => find(fq.value, null), 350);
  fq.addEventListener('input', doFind);
  fq.addEventListener('keydown', e => { if (e.key === 'Enter') { fq.blur(); stepMark(1); } });
  $('#fNext').onclick = () => stepMark(1);
  $('#fPrev').onclick = () => stepMark(-1);

  if (S.scroll[key] != null) { window.scrollTo(0, S.scroll[key]); if (hq) { $('#findbar').hidden = false; find(hq, null, true); } return; }
  if (hq) { $('#findbar').hidden = false; find(hq, ord != null ? +ord : null); }
  else if (ord != null) { const el = $('#s' + ord); el && el.scrollIntoView(); }
  else window.scrollTo(0, 0);
}
function setFs(v) {
  fs = Math.max(12, Math.min(26, v)); LS.set('fs', fs);
  document.documentElement.style.setProperty('--fs', fs + 'px');
}
function clearMarks() {
  const db = $('#db'); if (!db) return;
  db.querySelectorAll('mark').forEach(m => m.replaceWith(document.createTextNode(m.textContent)));
  db.normalize();
  if (docState) { docState.marks = []; docState.i = -1; }
}
function find(q, ord, noScroll) {
  clearMarks();
  const ts = terms(q);
  const cnt = $('#fcnt');
  if (!ts.length) { cnt.textContent = ''; return; }
  const db = $('#db');
  const walker = document.createTreeWalker(db, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  let marks = [];
  const tryRe = re => {
    marks = [];
    for (const n of nodes) {
      const t = n.nodeValue;
      re.lastIndex = 0;
      if (!re.test(t)) continue;
      re.lastIndex = 0;
      const frag = document.createDocumentFragment();
      let last = 0, mm;
      while ((mm = re.exec(t))) {
        if (mm.index > last) frag.appendChild(document.createTextNode(t.slice(last, mm.index)));
        const mk = document.createElement('mark'); mk.textContent = mm[0];
        frag.appendChild(mk); marks.push(mk);
        last = mm.index + mm[0].length;
        if (marks.length > 5000) break;
      }
      if (last < t.length) frag.appendChild(document.createTextNode(t.slice(last)));
      n.parentNode.replaceChild(frag, n);
      if (marks.length > 5000) break;
    }
  };
  // a phrase first; if it is split across formatting (bold etc.), fall back to separate words
  if (ts.length > 1) tryRe(phraseRe(ts));
  if (!marks.length) {
    nodes.length = 0;
    const w2 = document.createTreeWalker(db, NodeFilter.SHOW_TEXT);
    while (w2.nextNode()) nodes.push(w2.currentNode);
    tryRe(termRe(ts));
  }
  docState.marks = marks;
  cnt.textContent = marks.length ? `0 из ${marks.length}` : 'нет';
  if (!marks.length) {
    if (ord != null && !noScroll) { const el = $('#s' + ord); el && el.scrollIntoView(); }
    return;
  }
  if (noScroll) { cnt.textContent = `${marks.length}`; return; }
  let start = 0;
  if (ord != null) {
    const sec = $(`.sb[data-ord="${ord}"]`);
    if (sec) { const k = marks.findIndex(mk => sec.contains(mk)); if (k >= 0) start = k; }
  }
  docState.i = start - 1;
  stepMark(1);
}
function stepMark(d) {
  const st = docState; if (!st || !st.marks.length) return;
  if (st.i >= 0 && st.marks[st.i]) st.marks[st.i].classList.remove('cur');
  st.i = (st.i + d + st.marks.length) % st.marks.length;
  const mk = st.marks[st.i];
  mk.classList.add('cur');
  mk.scrollIntoView({ block: 'center' });
  $('#fcnt').textContent = `${st.i + 1} из ${st.marks.length}`;
}
function showToc() {
  const st = docState; if (!st) return;
  const hits = new Set(st.marks.map(mk => { const s = mk.closest('.sb'); return s ? s.dataset.ord : null; }));
  const el = document.createElement('div');
  el.className = 'toc';
  el.innerHTML = '<div class="panel">' + st.secs.map(s =>
    `<a href="javascript:void 0" data-ord="${s.ord}" class="l${s.lvl} ${hits.has(String(s.ord)) ? 'hit' : ''}">${esc(s.title)}</a>`).join('') + '</div>';
  el.addEventListener('click', e => {
    const a = e.target.closest('a[data-ord]');
    el.remove();
    if (a) { const h = $('#s' + a.dataset.ord); h && h.scrollIntoView(); }
  });
  document.body.appendChild(el);
}

// ---------------------------------------------------------------- start
stack.push(location.hash || '#home');
route();
// ---------------------------------------------------------------- обновление содержимого без переустановки (Android)
function contentVer() { try { return window.App && App.contentVersion ? String(App.contentVersion()) : ''; } catch (e) { return ''; } }
function contentLabel() {
  const v = contentVer(); if (!/^\d{12}$/.test(v)) return '';
  return ` · содержимое от ${v.slice(6, 8)}.${v.slice(4, 6)}.${v.slice(0, 4)}`;
}
function toast(text) {
  const t = document.createElement('div'); t.className = 'toast'; t.textContent = text; document.body.appendChild(t);
  setTimeout(() => t.classList.add('on'), 30); setTimeout(() => { t.classList.remove('on'); setTimeout(() => t.remove(), 400); }, 4500);
}
window.onContentReady = () => toast('Загружено обновление справочника — применится при следующем открытии');
setTimeout(() => {
  try { if (window.App && App.otaOk) App.otaOk(); } catch (e) {}
  try { if (krCan()) krEnable(isOrg()); } catch (e) {}
  try { anOpen(); } catch (e) {}
  const v = contentVer(), seen = LS.get('contentSeen', '');
  if (v && seen && v !== seen && v > seen) toast('Справочник обновлён');
  if (v) LS.set('contentSeen', v);
}, 1500);

// ---------------------------------------------------------------- новые КР в рубрикаторе (только организатор, Android)
function krCan() { return !!(window.App && App.krStatus); }
function krEnable(on) { try { if (krCan()) App.krWatch(!!on); } catch (e) {} }
function krState() { try { return krCan() ? JSON.parse(App.krStatus() || '{}') : {}; } catch (e) { return {}; } }
function krUnseen(st) {
  const r = st.res || {}, seen = new Set(LS.get('krSeen', []));
  return [...(r.new || []), ...(r.upd || [])].filter(x => !seen.has(x.id)).length;
}
function krBanner() {
  if (!krCan() || !isOrg()) return '';
  const st = krState(), n = krUnseen(st);
  if (!n) return '';
  return `<a class="learncard krcard" href="#krnew"><svg viewBox="0 0 24 24"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/></svg>
    <span><b>Новое в клинических рекомендациях</b><small>новые и обновлённые КР на сайте Минздрава</small></span><span class="lbadge">${n}</span><span class="chev">›</span></a>`;
}
function krPage() {
  setTitle('Новое в КР', false);
  if (!krCan()) { view.innerHTML = statsSeg('krnew') + '<div class="rwempty">Проверка новых КР работает в приложении для Android.</div>'; return; }
  if (!isOrg()) { view.innerHTML = statsSeg('krnew') + '<div class="rwempty">Раздел доступен организатору. Войдите в «Обучение и опросы».</div>'; return; }
  const st = krState(), r = st.res || {}, seen = new Set(LS.get('krSeen', []));
  const when = t => t ? new Date(t).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';
  const item = (x, k) => `<a class="kritem${seen.has(x.id) || k === 'gone' ? '' : ' fresh'}" href="https://cr.minzdrav.gov.ru/preview-cr/${esc(x.id)}">
      <span class="krn">${esc(x.name)}</span><span class="krm">КР${esc(x.id)}${x.date ? ' · ' + esc(x.date) : ''}${k === 'upd' && x.was ? ' · в справочнике версия ' + esc(x.was.split('_')[1]) : ''}</span></a>`;
  const sec = (k, h, note) => (r[k] || []).length ? `<div class="sec-h">${h} · ${r[k].length}</div>${note ? `<p class="krnote">${note}</p>` : ''}<div class="krlist">${r[k].map(x => item(x, k)).join('')}</div>` : '';
  const empty = st.ok && !(r.new || []).length && !(r.upd || []).length && !(r.gone || []).length;
  view.innerHTML = statsSeg('krnew') + `<div class="krpage">
    <div class="krstat"><div>Последняя проверка: <b>${when(st.at)}</b>${st.ok ? ` · на сайте ${r.remote || '?'} КР, в справочнике ${r.local || '?'}` : ''}</div>
      ${st.err ? `<div class="krerr">Не удалось проверить: ${esc(st.err)}</div>` : ''}
      <button class="cvbtn sec" id="krNow">Проверить сейчас</button></div>
    ${empty ? '<div class="rwempty">Справочник совпадает с рубрикатором Минздрава — новых и обновлённых КР нет.</div>' : ''}
    ${!st.ok && !st.err ? '<div class="rwempty">Проверка ещё не выполнялась.</div>' : ''}
    ${sec('new', 'Новые КР')}${sec('upd', 'Обновлённые КР')}${sec('gone', 'Сняты с рубрикатора', 'Есть в справочнике, но на сайте их больше нет среди действующих.')}
    ${krUpBox(r)}
    <p class="disc">Телефон проверяет сайт Минздрава раз в сутки и присылает уведомление о новых находках. Нажмите на КР, чтобы открыть её на сайте.</p></div>`;
  LS.set('krSeen', [...new Set([...seen, ...(r.new || []).map(x => x.id), ...(r.upd || []).map(x => x.id)])]);
  const sb = view.querySelector('.sseg .tnew'); if (sb) sb.remove(); statsTabSync();
  krUpWire(r);
  $('#krNow').onclick = () => { const b = $('#krNow'); b.disabled = true; b.textContent = 'Проверяю…'; try { App.krCheck(); } catch (e) {}
    setTimeout(() => { if (cur === '#krnew') krPage(); }, 40000); };   // если проверка уже шла в фоне, ответа может не быть — обновим экран сами
}
window.onKrStatus = () => { statsTabSync(); if (cur === '#krnew') krPage(); };

// передача КР в чат разработки: телефон скачивает тексты с сайта Минздрава и отправляет их на Google-скрипт организатора
function krUpIds(r) { const sent = LS.get('krSent', {}); return [...(r.new || []), ...(r.upd || [])].map(x => x.id).filter(id => !sent[id]); }
function krUpBox(r) {
  if (!(window.App && App.krUpload)) return '';
  const ids = krUpIds(r), sent = Object.keys(LS.get('krSent', {}));
  return `<div class="sec-h">Передать в справочник</div><div class="krstat krup">
    <div>Телефон скачает ${ids.length ? `<b>${ids.length} КР</b> (новые и обновлённые) и ` : ''}список действующих КР с сайта Минздрава и отправит их на ваш Google Диск через скрипт отчётов. Потом напишите в чате разработки: <b>«обнови базу КР»</b>.</div>
    <label class="kradd">Ещё КР по номеру (необязательно): <input id="krExtra" placeholder="например 400_2, 616_1" autocomplete="off" spellcheck="false"></label>
    <button class="cvbtn" id="krUp">Скачать и передать</button><div id="krUpLog" class="kruplog"></div>
    ${sent.length ? `<small class="krm">Уже передано: ${sent.length} КР. Последняя передача: ${esc(LS.get('krSentAt', ''))}</small>` : ''}</div>`;
}
function krUpWire(r) {
  const b = $('#krUp'); if (!b) return;
  b.onclick = () => {
    const d = learnData(), url = d && d.report, key = LS.get('orgKey', ''), log = $('#krUpLog');
    if (!url || !key) { log.textContent = 'Нет адреса скрипта или ключа организатора — войдите организатором заново.'; return; }
    const extra = ($('#krExtra').value.match(/\d+_\d+/g) || []);
    const ids = [...new Set([...krUpIds(r), ...extra])];
    b.disabled = true; b.textContent = 'Передаю…'; log.innerHTML = '';
    window.onKrUp = (name, ok, msg) => {
      log.insertAdjacentHTML('beforeend', `<div class="${ok ? 'ok' : 'bad'}">${ok ? '✓' : '✗'} ${esc(name)}${msg ? ' — ' + esc(msg) : ''}</div>`);
      if (ok && /^\d+_\d+$/.test(name)) { const s = LS.get('krSent', {}); s[name] = Date.now(); LS.set('krSent', s); }
    };
    window.onKrUpDone = (ok, total) => {
      LS.set('krSentAt', new Date().toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }));
      b.disabled = false; b.textContent = 'Скачать и передать';
      log.insertAdjacentHTML('beforeend', `<div class="sum">${ok === total ? `Готово: передано ${ok} из ${total}. Напишите в чате разработки «обнови базу КР».` : `Передано ${ok} из ${total}. Можно нажать ещё раз — повторятся только неудачные.`}</div>`);
    };
    try { App.krUpload(url, key, JSON.stringify(ids)); } catch (e) { onKrUpDone(0, 0); }
  };
}

// ---------------------------------------------------------------- аналитика использования (анонимно)
// Телефон получает случайный номер; события (открытие, просмотр раздела, поиск) копятся и раз в несколько часов
// уходят пачкой на Google-скрипт отчётов (лист «Использование»). ФИО и логины не отправляются.
function anDev() { let d = LS.get('anDev', ''); if (!/^[a-z0-9]{12}$/.test(d)) { d = ''; while (d.length < 12) d += Math.random().toString(36).slice(2); d = d.slice(0, 12); LS.set('anDev', d); } return d; }
function anPush(e, k, n) {
  const q = LS.get('anQ', []); q.push([Math.floor(Date.now() / 1000), e, String(k || '').slice(0, 60), n == null ? '' : n]);
  LS.set('anQ', q.slice(-1500));
  if (Date.now() - LS.get('anSent', 0) > 3 * 3600e3 || q.length >= 300) anFlush();
}
function anOpen() {
  anDev(); anPush('open', window.App ? 'android' : 'web');
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { LS.set('anHid', Date.now()); anFlush(); }
    else if (Date.now() - LS.get('anHid', Date.now()) > 30 * 60e3) anPush('open', window.App ? 'android' : 'web');
  });
}
function anView(parts) {
  const p0 = parts[0] || 'home', id = parts[1] || '';
  const M = { rec: id ? 'topic:' + id : 'rec', d: 'scheme:' + id, mkb: id ? 'mkb:node' : 'mkb', calc: 'calc:' + id, course: 'course:' + id,
    lecture: (parts[2] === 'test' ? 'lecture-test:' : 'lecture:') + id, cr: 'cr:' + id, doc: 'doc:' + id };
  const k = (M[p0] || p0).replace(/[^\w:.-]/g, '').slice(0, 60);
  if (k === AN.last && Date.now() - AN.lastAt < 30 * 60e3) return;
  AN.last = k; AN.lastAt = Date.now(); anPush('view', k);
}
function anSearch(scope, q, n) {   // записываем итоговый запрос, а не каждую букву
  q = String(q || '').trim().toLowerCase().replace(/\s+/g, ' ');
  clearTimeout(AN.sq[scope]);
  if (q.length < 2) return;
  AN.sq[scope] = setTimeout(() => anPush('search', scope + ':' + q.slice(0, 50), n), 2000);
}
function anFlush() {
  const q = LS.get('anQ', []), d = learnData(), url = d && d.report;
  if (!q.length || !url || !d.usage || !/^https:\/\/script\.google\.com\/macros\/s\/[\w-]+\/exec$/.test(url) || AN.busy) return;   // d.usage — скрипт умеет принимать события
  AN.busy = true; const batch = q.slice(0, 500);
  fetch(url, { method: 'POST', mode: 'no-cors', keepalive: batch.length < 150, headers: { 'Content-Type': 'text/plain;charset=utf-8' },
    body: JSON.stringify({ op: 'ev', dev: anDev(), v: APP_VERSION, p: window.App ? 'android' : 'web', lg: learnUser() ? 1 : 0, ev: batch }) })
    .then(() => { LS.set('anQ', LS.get('anQ', []).slice(batch.length)); LS.set('anSent', Date.now()); })
    .catch(() => {}).finally(() => { AN.busy = false; });
}

// экран организатора «Использование приложения»
function anTitle(k) {
  const [a, b] = k.split(':');
  const plain = { home: 'Главная', rec: 'Справочник (темы)', mkb: 'Поиск по МКБ', route: 'Дежурные стационары', learn: 'Обучение и опросы', about: 'О справочнике',
    report: 'Отчёт по обучению', krnew: 'Новое в КР', usage: 'Использование', 'mkb:node': 'МКБ: просмотр раздела' };
  if (plain[k]) return plain[k];
  if (a === 'scheme') return (byId[b] && byId[b].title) || 'Схема ' + b;
  if (a === 'topic') { const t = TOPICS.find(x => x.k === b); return 'Тема: ' + (t ? t.t : b); }
  if (a === 'calc') { const t = TOOLS.find(x => x.h === '#calc/' + b); return (t ? t.t : 'Калькулятор ' + b); }
  if (a === 'course') return 'Курс: ' + ((window.COURSES && COURSES[b] && COURSES[b].title) || b);
  if (a === 'lecture' || a === 'lecture-test') return (a === 'lecture' ? 'Лекция: ' : 'Тест к лекции: ') + ((window.LECTURES && LECTURES[b] && LECTURES[b].title.replace(/^Лекция: /, '')) || b);
  if (a === 'cr' || a === 'doc') { try { crData(); } catch (e) {} return 'КР: ' + ((CRN && CRN[b]) || b) + (a === 'doc' ? ' (текст)' : ''); }
  return k;
}
function usagePage() {
  setTitle('Использование приложения', false);
  if (!isOrg()) { view.innerHTML = statsSeg('usage') + '<div class="rwempty">Раздел доступен организатору. Войдите в «Обучение и опросы».</div>'; return; }
  const d = learnData(), url = d && d.report, key = LS.get('orgKey', '');
  view.innerHTML = statsSeg('usage') + `<div class="seg n3 utabs">${[7, 30, 90].map(n => `<a class="${n === USAGE_DAYS ? 'on' : ''}" data-d="${n}">${n} дней</a>`).join('')}</div><div id="ubox"><div class="rwempty">Загрузка…</div></div>`;
  view.querySelectorAll('.utabs a').forEach(a => a.onclick = () => { USAGE_DAYS = +a.dataset.d; usagePage(); });
  if (!url || !key) { $('#ubox').innerHTML = '<div class="rwempty">Нет адреса скрипта или ключа организатора — войдите организатором заново.</div>'; return; }
  anFlush();
  fetch(url + '?key=' + encodeURIComponent(key) + '&op=usage&days=' + USAGE_DAYS, { cache: 'no-store' }).then(r => r.json()).then(u => {
    const box = $('#ubox'); if (!box) return;
    if (u.ok && u.rows) { box.innerHTML = '<div class="rwempty">Скрипт ещё не умеет считать использование — обновите его код.</div>'; return; }
    if (!u.ok) { box.innerHTML = `<div class="rwempty">${u.err === 'key' ? 'Скрипт не принял ключ организатора.' : 'Скрипт ещё не умеет считать использование — обновите его код.'}</div>`; return; }
    if (!u.devices) { box.innerHTML = '<div class="rwempty">Данных пока нет. Телефоны начнут присылать статистику после обновления приложения — первые цифры появятся в течение дня.</div>'; return; }
    const bars = (rows, lab) => { const mx = Math.max(1, ...rows.map(r => r[1])); return `<div class="ubars">${rows.map((r, i) => `<div class="ubar" title="${esc(r[0])}: ${r[1]}"><i style="height:${Math.round(r[1] / mx * 100)}%"></i><span>${esc(lab(r[0], i))}</span></div>`).join('')}</div>`; };
    const list = (rows, f, empty) => rows.length ? `<div class="ulist">${rows.map(r => `<div class="urow"><span>${f(r)}</span><b>${r[1]}</b>${r[2] != null ? `<small>${r[2]} тел.</small>` : ''}</div>`).join('')}</div>` : `<div class="krnote">${empty}</div>`;
    const sq = s => { const i = s.indexOf(':'); return `<i class="usc">${s.slice(0, i) === 'mkb' ? 'МКБ' : 'справ.'}</i> ${esc(s.slice(i + 1))}`; };
    box.innerHTML = `<div class="ukpi">
        <div><b>${u.devices}</b><span>телефонов за ${USAGE_DAYS} дн.</span></div>
        <div><b>${u.today}</b><span>сегодня</span></div>
        <div><b>${u.avgDay}</b><span>в среднем в день</span></div>
        <div><b>${u.learnPct}%</b><span>вошли в обучение</span></div></div>
      <div class="sec-h">Телефонов по дням</div>${bars(u.daily, (s, i) => { const st = Math.ceil(u.daily.length / 7), j = u.daily.length - 1 - i; return j % st === 0 ? s.slice(8, 10) + '.' + s.slice(5, 7) : ''; })}
      <div class="sec-h">Что открывают</div>${list(u.views, r => esc(anTitle(r[0])), 'Пока нет данных.')}
      <div class="sec-h">Что ищут</div>${list(u.searches, r => sq(r[0]), 'Пока никто ничего не искал.')}
      <div class="sec-h">Искали, но не нашли</div><p class="krnote">Подсказка, чего не хватает в справочнике.</p>${list(u.empty, r => sq(r[0]), 'Таких поисков нет.')}
      <div class="sec-h">Время суток (по Тюмени)</div>${bars(u.hours.map((n, h) => [String(h), n]), s => +s % 3 === 0 ? s : '')}
      <div class="sec-h">Версии приложения</div>${list(u.versions, r => esc(r[0]), '—')}
      <p class="disc">Статистика анонимная: у каждого телефона случайный номер, ФИО и логины не передаются. Телефоны отправляют данные раз в несколько часов, поэтому сегодняшние цифры неполные. <a href="${esc(u.sheet || '#')}" target="_blank" rel="noopener">Открыть таблицу</a></p>`;
  }).catch(() => { const box = $('#ubox'); if (box) box.innerHTML = '<div class="rwempty">Нет связи со скриптом.</div>'; });
}

// ---------------------------------------------------------------- вкладка «Статистика» (только организатор)
function statsSeg(on) {
  const T = [['usage', 'Использование'], ['krnew', 'Новое в КР'], ['report', 'Обучение']];
  const n = krCan() ? krUnseen(krState()) : 0;
  return `<div class="seg n3 sseg">${T.map(([k, t]) => `<a class="${k === on ? 'on' : ''}" href="#${k}">${t}${k === 'krnew' && n ? ` <i class="tnew">${n}</i>` : ''}</a>`).join('')}</div>`;
}
function statsTabSync() {
  const lb = document.getElementById('tabLearnN');   // новое в «Обучении» — цифра на вкладке
  if (lb) { const n = learnNewCount(); lb.hidden = !n; lb.textContent = n || ''; }
  const t = document.getElementById('tabStats'); if (!t) return;
  const org = isOrg(); t.hidden = !org;
  const n = org && krCan() ? krUnseen(krState()) : 0, b = document.getElementById('tabStatsN');
  if (b) { b.hidden = !n; b.textContent = n || ''; }
}

// главная без прокрутки: высота блока = от его верха до вкладок (точнее, чем расчёт в CSS — учитывает шапку и вырез экрана)
function homeFit() {
  const f = document.querySelector('.homefill'), nav = document.getElementById('tabs');
  if (!f || !nav) return;
  const top = f.getBoundingClientRect().top + window.scrollY, pb = parseFloat(getComputedStyle(document.body).paddingBottom) || 0;
  const h = Math.min(nav.getBoundingClientRect().top - 6, window.innerHeight - pb) - top;
  f.style.height = Math.max(470, Math.floor(h)) + 'px';
}
window.addEventListener('resize', () => { if (document.querySelector('.homefill')) homeFit(); });
