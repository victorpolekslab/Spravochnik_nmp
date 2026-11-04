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
window.addEventListener('hashchange', () => {
  if (cur) S.scroll[cur] = window.scrollY;
  const h = location.hash || '#home';
  if (stack.length > 1 && stack[stack.length - 2] === h) stack.pop(); else stack.push(h);
  route();
});
function setTitle(t, isRoot) { $('#title').textContent = t; $('#backBtn').hidden = !!isRoot; }
function setTab(t) { document.querySelectorAll('#tabs a').forEach(a => a.classList.toggle('on', a.dataset.tab === t)); }
function route() {
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
    case 'cr': setTab(''); crPage(parts[1]); break;
    case 'about': setTab(''); about(); break;
    case 'doc': doc(parts[1], parts[2], params.get('h') || ''); return;
    default: setTab('home'); home();
  }
  window.scrollTo(0, S.scroll[h] || 0);
}

// ---------------------------------------------------------------- data
const TOPICS = [
  { k: 'shock', t: 'Шоки', ids: ['shock', 'angio'], c: 'red', i: 'shock' },
  { k: 'cardio', t: 'Кардиология', ids: ['ag', 'oks', 'ibs', 'ar', 'hsn'], c: 'rose', i: 'oks' },
  { k: 'neuro', t: 'Неврология', ids: ['onmk', 'bol'], c: 'violet', i: 'onmk' },
  { k: 'pulm', t: 'Пульмонология', ids: ['astma', 'hobl'], c: 'blue', i: 'astma' },
  { k: 'inf', t: 'Инфекционные болезни', ids: ['pnevm', 'orvi', 'sinus', 'angina'], c: 'green', i: 'inf' },
  { k: 'preg', t: 'Беременные', ids: ['agb', 'preg_back', 'preg_orvi', 'preg_pnevm', 'preg_uti'], c: 'pink', i: 'agb' },
  { k: 'uro', t: 'Урология', ids: ['uti', 'colic'], c: 'teal', i: 'uro' },
  { k: 'endo', t: 'Эндокринология', ids: ['sd'], c: 'amber', i: 'sd' }
];
const TICON = { uro: 'M9 3c-3 0-5 3-5 7s2 7 5 7c1.5 0 2-1 2-2.5V12c0-1-.5-1.5-1.5-1.5M15 3c3 0 5 3 5 7s-2 7-5 7c-1.5 0-2-1-2-2.5V12c0-1 .5-1.5 1.5-1.5M11 17v4M13 17v4', inf: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1' };
const plural = (n, f) => n + ' ' + (n % 10 === 1 && n % 100 !== 11 ? f[0] : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? f[1] : f[2]);
const ORDER = TOPICS.flatMap(x => x.ids);
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
  colic: 'M13 2L4 14h7l-1 8 9-12h-7z'
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
  view.innerHTML = `
    <a class="mkbcard" href="#mkb">
      <div class="mk-h"><svg viewBox="0 0 24 24"><path d="M5 4h10l4 4v12H5z"/><path d="M9 12h6M9 16h6M9 8h3"/></svg>
        <div><div class="tt">Классификатор МКБ-10</div><div class="ts">рубрики, поиск по коду и нозологии, клинические рекомендации по коду</div></div></div>
    </a>
    <div class="searchbar inl"><div class="field">
      <svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/></svg>
      <input id="hq" type="search" placeholder="Поиск по коду или нозологии" autocomplete="off" spellcheck="false" enterkeyhint="search">
    </div></div>
    <div class="sec-h">Калькуляторы и шкалы</div>
    <div class="tools">${TOOLS.map(x => `<a class="tool" href="${x.h}"><svg viewBox="0 0 24 24"><path d="${x.i}"/></svg><div class="tt">${esc(x.t)}</div><div class="ts">${esc(x.s)}</div></a>`).join('')}</div>
    <a class="recbanner" href="#rec"><span>Справочник</span><small>${DIS.length} разделов по темам</small><span class="chev">›</span></a>
    <a class="aboutlink" href="#about">О справочнике</a>`;
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
}

function topicPage(k) {
  const tp = TOPICS.find(x => x.k === k);
  if (!tp) return go('#rec');
  setTitle(tp.t, false);
  view.innerHTML = `<div class="topic t-${tp.c} solo">${tp.ids.map(i => byId[i]).filter(Boolean).map(d =>
    `<a class="trow" href="#d/${d.id}"><span class="ti"><svg viewBox="0 0 24 24"><path d="${ICON[d.id] || ICON.bol}"/></svg></span>
      <span class="nm"><b>${esc(d.title)}</b><small>${esc(d.sub)}</small></span><span class="chev">›</span></a>`).join('')}</div>`;
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
    <div class="dsrc">${srcBadge(x.src)}</div></div>`;
}
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
    case 'note':
      return `<section class="b note"><p>${esc(b.text)}</p>${src}</section>`;
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
function stepTable(steps, defs, head) {
  const list = (steps || []).map(x => typeof x === 'string' ? (defs || {})[x] : x).filter(Boolean);
  if (!list.length) return '';
  return `<table class="tx"><thead><tr><th>${esc(head || 'Шаг')}</th><th>Что назначить</th></tr></thead><tbody>${list.map(x =>
    `<tr><td>${md(x.s)}</td><td><div class="combo">${md(x.combo)}</div>${x.ex ? `<div class="ex">${md(x.ex)}</div>` : ''}${altList(x.alt)}${x.note ? `<div class="ex ${/(^не\s|нельзя|риск|не при)/i.test(x.note) ? 'warnline' : 'noteline'}">${md(x.note)}</div>` : ''}<div class="tsrc">${srcBadge(x.src)}</div></td></tr>`).join('')}</tbody></table>`;
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
const APP_VERSION = '2.2';
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
    <div class="card"><b style="font-size:17px">Справочник фельдшера неотложной медицинской помощи</b><p>Версия ${APP_VERSION} · клинические рекомендации от 03.11.2026</p>
      ${window.App ? '<button class="lnkbtn" id="updChk">Проверить обновления</button><span class="updres" id="updRes"></span>' : ''}</div>
    <div class="card"><b>Поделиться с коллегами</b><p>iPhone и любой браузер: <a href="${SITE}">${SITE.replace('https://', '')}</a> — открыть в Safari → «Поделиться» → «На экран Домой».</p>
      <p>Android: <a href="${SITE}download/SpravochnikNMP.apk">скачать приложение (APK)</a>. Новые версии приложение предлагает само.</p></div>
    <div class="card"><b>Что это</b><p>Справочник фельдшера неотложной медицинской помощи по действующим клиническим рекомендациям Минздрава России. Во вкладках «Неотложно» — помощь до приезда СМП: без кислородотерапии, тромболизиса, наркотических анальгетиков и инфузомата. <span class="onebadge" style="margin:0">ОДИН ИЗ</span> — взаимозаменяемые препараты, выбирается один.</p>
      <p><span class="src kr">КР</span> — доза или положение из текста рекомендации (сверено автоматически); <span class="src ins">инстр.</span> — доза из инструкции к препарату, в КР её нет.</p></div>
    <div class="card"><b>МКБ-10 и рекомендации</b><p>Классификатор МКБ-10 (НСИ Минздрава, версия 2.27) и перечень всех действующих рекомендаций (${Object.keys(names).length}). Полные тексты ${bundled.length} рекомендаций встроены в приложение; остальные можно загрузить на телефон из карточки рекомендации (нужен интернет), дальше они открываются без сети. Загружено: ${dlSet().size}.</p></div>
    <div class="card"><b>Важно</b><p>Справочник не заменяет инструкцию к препарату и решение врача. В КР «Бронхиальная астма» (359_3) для преднизолона у взрослых указано «20–30 мг/кг/сут» — это опечатка в единицах, в схеме приведено 20–30 мг/сут.</p></div>
    <div class="card"><b>Встроенные рекомендации</b>${bundled.sort((x, y) => x.name.localeCompare(y.name)).map(x => `<p><a href="#doc/${x.id}">КР${esc(x.id)}</a> — ${esc(x.name)}</p>`).join('')}</div>
  </div>`;
  const b = $('#updChk');
  if (b) b.onclick = () => { $('#updRes').textContent = 'Проверяю…'; try { window.App.checkUpdate(); } catch (e) { onUpdateFail(); } };
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
