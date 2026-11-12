/* Препараты: поиск по инструкциям (ОХЛП ЕАЭС / ГРЛС) и проверка взаимодействий по разделу 4.5.
   Общий модуль «Справочника НМП» и «Справочника терапевта». Данные — ветка drugs репозитория Spravochnik_nmp.
   Подключение: DrugsModule({ view, setTitle(t, back), go(hash), fetchText(url) }) → { route(parts, params) }.
   Маршруты: #drugs[?q=…] — поиск, #drug/<строка> — карточка, #ix — проверка взаимодействий. */
(function () {
  'use strict';
  var BASE = 'https://raw.githubusercontent.com/victorpolekslab/Spravochnik_nmp/drugs/app/';

  var CSS = '\
.dg-wrap{padding:12px;display:flex;flex-direction:column;gap:10px;max-width:820px;margin:0 auto}\
.dg-field{display:flex;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:0 10px}\
.dg-field svg{width:20px;height:20px;fill:none;stroke:var(--muted);stroke-width:1.8}\
.dg-field input{flex:1;border:0;background:transparent;color:var(--fg);font:inherit;padding:11px 0;outline:none;min-width:0}\
.dg-field button{border:0;background:none;color:var(--muted);font-size:22px;padding:0 4px;cursor:pointer}\
.dg-list{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden}\
.dg-row{display:flex;align-items:center;gap:10px;padding:10px 12px;border-top:1px solid var(--line);color:inherit;text-decoration:none}\
.dg-row:first-child{border-top:0}\
.dg-row .dg-t{flex:1;min-width:0}\
.dg-row b{display:block;font-weight:600}\
.dg-sub{color:var(--muted);font-size:13px;line-height:1.35}\
.dg-tag{display:inline-block;font-size:12px;line-height:18px;padding:0 7px;border-radius:9px;background:var(--surface2);color:var(--muted);margin:2px 4px 0 0;white-space:nowrap}\
.dg-tag.lv{background:#FDF0D9;color:#7A4A00}.dg-tag.ocr{background:#E3EEFB;color:#1F5FA8}\
.dg-add{flex:none;width:36px;height:36px;border-radius:18px;border:1px solid var(--line);background:var(--surface);color:var(--accent);font-size:22px;line-height:1;cursor:pointer}\
.dg-add.on{background:var(--accent);border-color:var(--accent);color:#fff}\
.dg-card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:8px}\
.dg-card h2{font-size:19px;margin:0;line-height:1.25}\
.dg-meta{font-size:13px;color:var(--muted);display:flex;flex-direction:column;gap:2px}\
.dg-note{font-size:14px;border-radius:10px;padding:9px 11px;background:#FDF0D9;color:#7A4A00}\
.dg-note.info{background:var(--surface2);color:var(--fg)}\
.dg-jump{display:flex;gap:6px;overflow-x:auto;padding-bottom:2px}\
.dg-jump button{flex:none;border:1px solid var(--line);background:var(--surface);color:var(--fg);border-radius:16px;padding:5px 11px;font:inherit;font-size:14px;cursor:pointer}\
.dg-sec{background:var(--surface);border:1px solid var(--line);border-radius:12px}\
.dg-sec>summary{padding:11px 14px;font-weight:600;cursor:pointer;list-style:none;display:flex;gap:8px}\
.dg-sec>summary::-webkit-details-marker{display:none}\
.dg-sec>summary .n{color:var(--accent);min-width:28px}\
.dg-sec .dg-body{padding:0 14px 12px;font-size:15px;line-height:1.5}\
.dg-body p{margin:0 0 6px}\
.dg-body img{max-width:100%;border:1px solid var(--line);border-radius:6px;background:#fff;margin:4px 0 10px}\
.dg-btns{display:flex;gap:8px;flex-wrap:wrap}\
.dg-btn{border:1px solid var(--accent);background:var(--surface);color:var(--accent);border-radius:10px;padding:9px 12px;font:inherit;font-weight:600;cursor:pointer;text-decoration:none}\
.dg-btn.p{background:var(--accent);color:#fff}\
.dg-chips{display:flex;flex-wrap:wrap;gap:6px}\
.dg-chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--surface);border-radius:16px;padding:5px 6px 5px 11px;font-size:14px}\
.dg-chip button{border:0;background:var(--surface2);border-radius:10px;width:20px;height:20px;line-height:18px;cursor:pointer;color:var(--muted)}\
.dg-pair{background:var(--surface);border:1px solid var(--line);border-left:5px solid var(--line);border-radius:12px;padding:10px 12px;display:flex;flex-direction:column;gap:6px}\
.dg-pair.s3{border-left-color:#C0392B}.dg-pair.s2{border-left-color:#E07B00}.dg-pair.s1{border-left-color:#A07800}.dg-pair.s0{border-left-color:#1F5FA8}\
.dg-pair h3{margin:0;font-size:16px}\
.dg-sev{font-size:12px;font-weight:700;border-radius:9px;padding:1px 8px;margin-left:6px;vertical-align:2px;white-space:nowrap}\
.dg-sev.s3{background:#FBE3E0;color:#A12A1E}.dg-sev.s2{background:#FDEBD7;color:#9A5200}.dg-sev.s1{background:#FDF3D3;color:#7A5C00}.dg-sev.s0{background:#E3EEFB;color:#1F5FA8}\
.dg-from{font-size:13px;color:var(--muted);margin-top:4px}\
.dg-para{font-size:14.5px;line-height:1.45;padding:6px 9px;background:var(--surface2);border-radius:8px}\
.dg-para mark{background:var(--mark,#FFE58A);color:inherit;border-radius:2px;padding:0 1px}\
.dg-disc{font-size:13px;color:var(--muted);line-height:1.4}\
.dg-empty{padding:22px 12px;text-align:center;color:var(--muted)}\
.dg-more{border:0;background:none;color:var(--accent);font:inherit;padding:8px 12px;cursor:pointer;text-align:left}\
@media (prefers-color-scheme: dark){.dg-tag.lv,.dg-note{background:#3A2E14;color:#F2C266}.dg-tag.ocr{background:#1B2A3D;color:#9CC3F5}\
.dg-sev.s3{background:#3A1E1B;color:#F0827A}.dg-sev.s2{background:#3A2A14;color:#F2B266}.dg-sev.s1{background:#33300F;color:#E2C64B}.dg-sev.s0{background:#1B2A3D;color:#9CC3F5}}';

  var ROUTE_ORDER = ['внутрь', 'парентерально', 'под язык/за щеку', 'ингаляц', 'нос', 'глаза', 'уши', 'наружно', 'ректально', 'вагинально', 'прочее'];
  var KEY_SECS = [['4.1', 'Показания'], ['4.2', 'Дозы'], ['4.3', 'Противопоказания'], ['4.4', 'Особые указания'], ['4.5', 'Взаимодействия'], ['4.6', 'Беременность'], ['4.8', 'Нежелательные'], ['4.9', 'Передозировка']];
  var SEV = ['Упоминание', 'С осторожностью', 'Не рекомендуется', 'Противопоказано'];

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function norm(s) { return String(s || '').toLowerCase().replace(/ё/g, 'е').replace(/[®™*]/g, '').replace(/[^0-9a-zа-я]+/g, ' ').trim(); }
  var LAYOUT = { q: 'й', w: 'ц', e: 'у', r: 'к', t: 'е', y: 'н', u: 'г', i: 'ш', o: 'щ', p: 'з', '[': 'х', ']': 'ъ', a: 'ф', s: 'ы', d: 'в', f: 'а', g: 'п', h: 'р', j: 'о', k: 'л', l: 'д', ';': 'ж', "'": 'э', z: 'я', x: 'ч', c: 'с', v: 'м', b: 'и', n: 'т', m: 'ь', ',': 'б', '.': 'ю' };
  function clean(name) { return String(name || '').replace(/\s*[(—–,].*$/, '').replace(/\s+(в\/[вм]|внутрь|ДАИ|небулы|свечи|назальный|суспензия|ретард|MB)\b.*$/i, '').trim(); }
  function relayout(s) { return String(s).toLowerCase().split('').map(function (c) { return LAYOUT[c] || c; }).join(''); }
  function sevOf(p) {
    if (/противопоказан|недопустим|запрещ/i.test(p)) return 3;
    if (/не рекомендуется|не следует|следует избегать|избегать|нежелательн|не применя/i.test(p)) return 2;
    if (/с осторожностью|осторожн|контрол|мониторинг|коррекци\S* доз|снижени\S* доз|подбор\S* доз|увеличива\S* риск|повыша\S* риск/i.test(p)) return 1;
    return 0;
  }

  // ---------- хранилище: IndexedDB (работает без интернета), иначе память
  var mem = {};
  function idb() {
    return new Promise(function (res) {
      try {
        var r = indexedDB.open('drugs-cache', 1);
        r.onupgradeneeded = function () { r.result.createObjectStore('kv'); };
        r.onsuccess = function () { res(r.result); };
        r.onerror = function () { res(null); };
      } catch (e) { res(null); }
    });
  }
  var dbp = null;
  function cget(k) {
    if (k in mem) return Promise.resolve(mem[k]);
    dbp = dbp || idb();
    return dbp.then(function (db) {
      if (!db) return null;
      return new Promise(function (res) {
        try { var q = db.transaction('kv').objectStore('kv').get(k); q.onsuccess = function () { res(q.result || null); }; q.onerror = function () { res(null); }; }
        catch (e) { res(null); }
      });
    });
  }
  function cset(k, v) {
    mem[k] = v;
    dbp = dbp || idb();
    return dbp.then(function (db) {
      if (!db) return;
      try { db.transaction('kv', 'readwrite').objectStore('kv').put(v, k); } catch (e) {}
    });
  }
  function lsGet(k, d) { try { var v = localStorage.getItem('drugs.' + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem('drugs.' + k, JSON.stringify(v)); } catch (e) {} }

  window.DrugsModule = function (host) {
    var view = host.view, D = null, IX = null, loading = null, CLS = {};
    if (!document.getElementById('dg-style')) { var st = document.createElement('style'); st.id = 'dg-style'; st.textContent = CSS; document.head.appendChild(st); }
    function getJSON(url) { return host.fetchText(url).then(function (t) { return JSON.parse(t); }); }

    // основные данные: из кэша сразу, свежую версию — с сервера, если есть сеть
    function load() {
      if (loading) return loading;
      loading = Promise.all([cget('search'), cget('ix'), cget('ver')]).then(function (c) {
        var fresh = getJSON(BASE + 'version.json?t=' + Date.now()).then(function (v) {
          if (c[2] && c[0] && c[1] && v.v === c[2]) return null;
          return Promise.all([getJSON(BASE + 'search.json?v=' + v.v), getJSON(BASE + 'ix.json?v=' + v.v)]).then(function (x) {
            cset('search', x[0]); cset('ix', x[1]); cset('ver', v.v); return x;
          });
        });
        if (c[0] && c[1]) { fresh.then(function (x) { if (x) setData(x[0], x[1]); }).catch(function () {}); return setData(c[0], c[1]); }
        return fresh.then(function (x) { return setData(x[0], x[1]); });
      }).catch(function (e) { loading = null; throw e; });
      return loading;
    }
    function setData(s, ix) {
      D = s; IX = ix; CLS = {};
      ix.classes.forEach(function (c) { CLS[c[0]] = { name: c[1], rx: c[2], broad: !!c[3] }; });
      D.n = D.rows.map(function (r) { return { tn: norm(r[0]), inn: norm(r[1]) }; });
      return D;
    }
    function doc(id) {
      return cget('doc:' + id).then(function (c) {
        if (c) return c;
        return getJSON(BASE + 'doc/' + id + '.json').then(function (d) { cset('doc:' + id, d); return d; });
      });
    }
    function wait(fn) {
      if (D) return fn();
      view.innerHTML = '<div class="dg-empty">Загружаю справочник препаратов…</div>';
      load().then(fn).catch(function (e) {
        view.innerHTML = '<div class="dg-wrap"><div class="dg-note">Справочник препаратов ещё не загружен, а связи нет (' + esc(e.message || e) +
          '). Подключитесь к интернету один раз — после этого поиск будет работать и без сети.</div><button class="dg-btn" id="dgRetry">Повторить</button></div>';
        var b = document.getElementById('dgRetry'); if (b) b.onclick = function () { wait(fn); };
      });
    }

    // ---------- поиск
    function search(q, limit) {
      var nq = norm(q); if (!nq) return [];
      var words = nq.split(' '), seen = {}, out = [];
      function score(i) {
        var n = D.n[i], s = 0;
        for (var w = 0; w < words.length; w++) {
          var x = words[w];
          if (n.tn.indexOf(x) === 0) s += 40; else if ((' ' + n.tn).indexOf(' ' + x) >= 0) s += 25;
          else if (n.inn.indexOf(x) === 0) s += 30; else if ((' ' + n.inn).indexOf(' ' + x) >= 0) s += 18;
          else if (n.tn.indexOf(x) >= 0 || n.inn.indexOf(x) >= 0) s += 5; else return 0;
        }
        if (D.rows[i][6] >= 0) s += 3;
        if (D.rows[i][1].indexOf('+') < 0) s += 2;
        return s;
      }
      for (var i = 0; i < D.rows.length; i++) {
        var sc = score(i); if (!sc) continue;
        var r = D.rows[i], k = r[0] + '|' + r[3] + '|' + r[6];
        if (seen[k] != null) { out[seen[k]].n++; continue; }
        seen[k] = out.length; out.push({ i: i, s: sc, n: 1 });
      }
      out.sort(function (a, b) { return b.s - a.s || D.rows[a.i][0].length - D.rows[b.i][0].length || ROUTE_ORDER.indexOf(D.rows[a.i][3]) - ROUTE_ORDER.indexOf(D.rows[b.i][3]); });
      return out.slice(0, limit || 60);
    }
    function inList(i) { var d = D.rows[i][6]; return list().some(function (x) { return x.r === i || (d >= 0 && x.d === D.docs[d][0]); }); }
    function list() { return lsGet('ix', []); }
    function toggle(i) {
      var l = list(), r = D.rows[i], d = r[6] >= 0 ? D.docs[r[6]][0] : null;
      var at = l.findIndex(function (x) { return x.r === i || (d && x.d === d); });
      if (at >= 0) l.splice(at, 1); else l.push({ r: i, d: d, tn: r[0], inn: r[1], route: r[3] });
      lsSet('ix', l); return at < 0;
    }
    function rowH(o, addBtn) {
      var r = D.rows[o.i], d = r[6] >= 0 ? D.docs[r[6]] : null;
      var tags = '<span class="dg-tag">' + esc(r[3]) + '</span>' + (d ? (d[1] === 'lv' ? '<span class="dg-tag lv">листок-вкладыш</span>' : '') : '<span class="dg-tag">нет инструкции</span>');
      return '<a class="dg-row" href="#drug/' + o.i + '"><div class="dg-t"><b>' + esc(r[0]) + '</b><div class="dg-sub">' + esc(r[1] || '—') + ' · ' + esc(r[2]) + '</div>' + tags + '</div>' +
        (addBtn ? '<button class="dg-add' + (inList(o.i) ? ' on' : '') + '" data-add="' + o.i + '" aria-label="Добавить к проверке взаимодействий" title="К проверке взаимодействий">' + (inList(o.i) ? '✓' : '+') + '</button>' : '') + '</a>';
    }
    function bindAdd(root, after) {
      root.querySelectorAll('[data-add]').forEach(function (b) {
        b.onclick = function (e) { e.preventDefault(); e.stopPropagation(); var on = toggle(+b.dataset.add); b.classList.toggle('on', on); b.textContent = on ? '✓' : '+'; if (after) after(); };
      });
    }
    function searchPage(q0) {
      host.setTitle('Препараты', false);
      var q = q0 != null ? q0 : lsGet('q', '');
      view.innerHTML = '<div class="dg-wrap"><div class="dg-field"><svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/></svg>' +
        '<input id="dgq" type="search" placeholder="Торговое название или МНН" autocomplete="off" spellcheck="false" value="' + esc(q) + '"><button id="dgclr" aria-label="Очистить"' + (q ? '' : ' hidden') + '>×</button></div>' +
        '<div id="dgix"></div><div id="dgres"></div>' +
        '<p class="dg-disc">Инструкции: ОХЛП из Единого реестра ЕАЭС и инструкции из ГРЛС. Не заменяют инструкцию к конкретной упаковке. Кнопка «+» добавляет препарат к проверке взаимодействий.</p></div>';
      var inp = document.getElementById('dgq'), clr = document.getElementById('dgclr'), t = null;
      function ixBar() {
        var n = list().length;
        document.getElementById('dgix').innerHTML = n ? '<a class="dg-btn p" href="#ix" style="display:block;text-align:center">Проверить взаимодействия: ' + n + ' ' + (n === 1 ? 'препарат' : n < 5 ? 'препарата' : 'препаратов') + '</a>' : '';
      }
      function run() {
        lsSet('q', inp.value); clr.hidden = !inp.value;
        var res = search(inp.value), alt = '';
        if (!res.length && /[a-z]/i.test(inp.value)) { var rl = relayout(inp.value); res = search(rl); if (res.length) alt = rl; }
        var box = document.getElementById('dgres');
        if (!inp.value.trim()) { box.innerHTML = recent(); bindAdd(box, ixBar); return; }
        box.innerHTML = res.length ? (alt ? '<div class="dg-disc">Показаны результаты для «' + esc(alt) + '»</div>' : '') + '<div class="dg-list">' + res.map(function (o) { return rowH(o, true); }).join('') + '</div>'
          : '<div class="dg-empty">Ничего не найдено. Попробуйте МНН или начало торгового названия.</div>';
        bindAdd(box, ixBar);
      }
      inp.addEventListener('input', function () { clearTimeout(t); t = setTimeout(run, 120); });
      clr.onclick = function () { inp.value = ''; run(); inp.focus(); };
      ixBar(); run();
    }
    function recent() {
      var r = lsGet('recent', []).filter(function (i) { return D.rows[i]; });
      return r.length ? '<div class="dg-from">Недавно открытые</div><div class="dg-list">' + r.map(function (i) { return rowH({ i: i }, true); }).join('') + '</div>' : '<div class="dg-empty">Начните вводить название препарата.</div>';
    }

    // ---------- карточка
    function textH(t) {
      return t.split('\n').filter(function (l) { return l.trim(); }).map(function (l) { return '<p>' + esc(l) + '</p>'; }).join('');
    }
    function cardPage(i) {
      var r = D.rows[i];
      if (!r) { host.go('#drugs'); return; }
      var rec = lsGet('recent', []).filter(function (x) { return x !== i; }); rec.unshift(i); lsSet('recent', rec.slice(0, 12));
      host.setTitle(r[0], true);
      var d = r[6] >= 0 ? D.docs[r[6]] : null;
      var head = '<div class="dg-card"><h2>' + esc(r[0]) + '</h2><div class="dg-sub">' + esc(r[1] || '—') + '<br>' + esc(r[2]) + '</div><div>' +
        '<span class="dg-tag">' + esc(r[3]) + '</span>' + (r[4] ? '<span class="dg-tag">АТХ ' + esc(r[4]) + '</span>' : '') + (r[5] ? '<span class="dg-tag">' + esc(r[5]) + '</span>' : '') + '</div>' +
        '<div class="dg-btns"><button class="dg-btn' + (inList(i) ? ' p' : '') + '" id="dgadd">' + (inList(i) ? '✓ В списке взаимодействий' : '+ К проверке взаимодействий') + '</button>' +
        (list().length ? '<a class="dg-btn" href="#ix">Проверить список</a>' : '') + '</div></div>';
      if (!d) {
        view.innerHTML = '<div class="dg-wrap">' + head + '<div class="dg-note">Для этого препарата не нашлось ни ОХЛП в реестре ЕАЭС, ни инструкции в ГРЛС. Сверьтесь с инструкцией в упаковке.</div></div>';
        bindCardAdd(i); return;
      }
      view.innerHTML = '<div class="dg-wrap">' + head + '<div class="dg-empty">Загружаю инструкцию…</div></div>';
      bindCardAdd(i);
      doc(d[0]).then(function (x) {
        if (location.hash !== '#drug/' + i) return;
        var notes = '';
        if (d[1] === 'lv') notes += '<div class="dg-note">Это листок-вкладыш для пациента: полной инструкции по медицинскому применению и ОХЛП в открытом доступе нет. Дозы и взаимодействия в нём изложены короче.</div>';
        if (x.c && x.c.length) notes += '<div class="dg-note info">Часть страниц распознана со скана. В ' + x.c.length + ' строках цифры могли распознаться с ошибкой — они отмечены в конце, с картинкой оригинала.</div>';
        var other = D.rows.map(function (rr, k) { return rr[6] === r[6] && rr[0] !== r[0] ? rr[0] : null; }).filter(function (v, k, a) { return v && a.indexOf(v) === k; });
        // сначала клинические разделы (4.x), затем состав и свойства, служебные — в конце
        function rank(s) { var n = s[0]; if (/^4\./.test(n)) return parseFloat(n.slice(2)); if (n === '2') return 20; if (/^5/.test(n)) return 30 + (parseFloat(n.split('.')[1]) || 0);
          if (/^6/.test(n)) return 40 + (parseFloat(n.split('.')[1]) || 0); if (n === '3') return 19; return 60; }
        var secs = x.s.filter(function (s) { return s[2] && s[0] !== '4' && s[0] !== '5' && s[0] !== '6'; }).sort(function (a, b) { return rank(a) - rank(b); });
        var jump = '<div class="dg-jump">' + KEY_SECS.filter(function (k) { return secs.some(function (s) { return s[0] === k[0]; }); })
          .map(function (k) { return '<button data-j="' + k[0] + '">' + k[1] + '</button>'; }).join('') + (x.c && x.c.length ? '<button data-j="ocr">Проверка OCR</button>' : '') + '</div>';
        var body = secs.map(function (s, k) {
          var tail = rank(s) >= 60 && (k === 0 || rank(secs[k - 1]) < 60) ? '<div class="dg-from">Прочие сведения из документа</div>' : '';
          return tail + '<details class="dg-sec" id="dgs-' + esc(s[0] || 'x') + '"' + (s[0] === '4.2' ? ' open' : '') + '><summary><span class="n">' + esc(s[0]) + '</span><span>' + esc(s[1]) + '</span></summary><div class="dg-body">' + textH(s[2]) + '</div></details>';
        }).join('');
        if (x.c && x.c.length) body += '<details class="dg-sec" id="dgs-ocr"><summary><span class="n">!</span><span>Проверка распознавания</span></summary><div class="dg-body">' +
          x.c.map(function (c) { return '<p><b>Стр. ' + c[0] + ':</b> «' + esc(c[1]) + '»<br><span class="dg-sub">' + esc(c[2]) + '</span></p><img loading="lazy" alt="Фрагмент оригинала, стр. ' + c[0] + '" src="' + esc(c[3]) + '">'; }).join('') + '</div></details>';
        var src = '<div class="dg-meta">' + x.m.map(function (m) { return '<span>' + esc(m.replace(/(https?:\/\/\S+)/, '')) + '</span>'; }).join('') + '</div>';
        view.querySelector('.dg-wrap').innerHTML = head + notes + jump + body + '<div class="dg-card"><b>Источник</b>' + src +
          (other.length ? '<div class="dg-sub">Та же инструкция использована для: ' + esc(other.slice(0, 15).join(', ')) + (other.length > 15 ? ' и др.' : '') + '</div>' : '') + '</div>' +
          '<p class="dg-disc">Справочная информация. Не заменяет инструкцию к конкретной упаковке и решение врача.</p>';
        bindCardAdd(i);
        view.querySelectorAll('[data-j]').forEach(function (b) {
          b.onclick = function () { var s = document.getElementById('dgs-' + b.dataset.j); if (s) { s.open = true; s.scrollIntoView({ behavior: 'smooth', block: 'start' }); } };
        });
      }).catch(function (e) {
        var w = view.querySelector('.dg-wrap'); if (w) w.innerHTML = head + '<div class="dg-note">Не удалось загрузить инструкцию (' + esc(e.message || e) + '). Нужен интернет: открытые инструкции сохраняются и потом доступны без сети.</div>';
        bindCardAdd(i);
      });
    }
    function bindCardAdd(i) {
      var b = document.getElementById('dgadd');
      if (b) b.onclick = function () { var on = toggle(i); b.classList.toggle('p', on); b.textContent = on ? '✓ В списке взаимодействий' : '+ К проверке взаимодействий'; };
    }

    // ---------- взаимодействия
    function jsrx(p) { return p.replace(/\\w/g, '[\\p{L}\\p{N}_]').replace(/\\b/g, ''); }
    function hlRx(keys) {
      var parts = [];
      keys.forEach(function (k) {
        if (k.indexOf('i:') === 0) parts.push(k.slice(2).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[\\p{L}]*');
        else if (CLS[k.slice(2)]) CLS[k.slice(2)].rx.forEach(function (p) { parts.push(jsrx(p)); });
      });
      try { return parts.length ? new RegExp('(' + parts.join('|') + ')', 'giu') : null; } catch (e) { return null; }
    }
    function keyName(k) { return k.indexOf('i:') === 0 ? k.slice(2) : (CLS[k.slice(2)] || {}).name || k; }
    function para45(x) {
      for (var j = 0; j < x.s.length; j++) if (x.s[j][0] === '4.5') return x.s[j][2].split('\n').map(function (p) { return p.trim(); }).filter(function (p) { return p.length > 2; });
      return [];
    }
    function pairHits(a, b) {   // абзацы 4.5 документа a, где упомянут препарат b
      var men = IX.men[a] || {}, own = IX.own[b] || [], out = [];
      own.forEach(function (k) { if (men[k]) out.push([k, men[k]]); });
      return out;
    }
    function ixPage() {
      host.setTitle('Взаимодействия', true);
      var l = list();
      var chips = l.map(function (x, k) { return '<span class="dg-chip">' + esc(x.tn) + ' <span class="dg-sub">' + esc(x.route) + '</span><button data-del="' + k + '" aria-label="Убрать">×</button></span>'; }).join('');
      view.innerHTML = '<div class="dg-wrap"><div class="dg-chips">' + (chips || '<span class="dg-sub">Список пуст.</span>') + '</div>' +
        '<div class="dg-field"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg><input id="dgq2" type="search" placeholder="Добавить препарат" autocomplete="off" spellcheck="false"></div><div id="dgadd2"></div>' +
        (l.length > 1 ? '<div class="dg-btns"><button class="dg-btn" id="dgclear">Очистить список</button></div>' : '') +
        '<p class="dg-disc">Совпадения ищутся автоматически в разделе 4.5 «Взаимодействие» обеих инструкций: по названию действующего вещества и по группе (например, «ингибиторы АПФ», «ингибиторы CYP3A4»). Цветом отмечено, что сказано в найденном абзаце. Если совпадений нет, это не значит, что взаимодействия нет: инструкция может описывать его иначе.</p>' +
        '<div id="dgout"></div></div>';
      view.querySelectorAll('[data-del]').forEach(function (b) { b.onclick = function () { var x = list(); x.splice(+b.dataset.del, 1); lsSet('ix', x); ixPage(); }; });
      var c = document.getElementById('dgclear'); if (c) c.onclick = function () { lsSet('ix', []); ixPage(); };
      var inp = document.getElementById('dgq2'), t = null;
      inp.addEventListener('input', function () {
        clearTimeout(t); t = setTimeout(function () {
          var box = document.getElementById('dgadd2');
          var res = inp.value.trim() ? search(inp.value, 8) : [];
          box.innerHTML = res.length ? '<div class="dg-list">' + res.map(function (o) { return rowH(o, true); }).join('') + '</div>' : '';
          bindAdd(box, function () { ixPage(); });
        }, 120);
      });
      if (l.length < 2) { document.getElementById('dgout').innerHTML = '<div class="dg-empty">Добавьте хотя бы два препарата.</div>'; return; }
      var ids = l.map(function (x) { return x.d; });
      document.getElementById('dgout').innerHTML = '<div class="dg-empty">Загружаю инструкции…</div>';
      Promise.all(ids.map(function (d) { return d ? doc(d).catch(function () { return null; }) : Promise.resolve(null); })).then(function (docs) {
        var pairs = [], quiet = [], missing = [];
        l.forEach(function (x, k) { if (!x.d) missing.push(x.tn); });
        for (var a = 0; a < l.length; a++) for (var b = a + 1; b < l.length; b++) {
          var A = l[a], B = l[b];
          if (!A.d || !B.d) continue;
          var same = (IX.own[A.d] || []).filter(function (k) { return k.indexOf('i:') === 0 && (IX.own[B.d] || []).indexOf(k) >= 0; });
          var blocks = [], sev = -1, broadOnly = true;
          if (same.length) { blocks.push('<div class="dg-para"><b>Одно и то же действующее вещество</b> (' + esc(same.map(keyName).join(', ')) + '): при совместном приёме — риск превышения дозы.</div>'); sev = 2; broadOnly = false; }
          [[A, B, docs[a]], [B, A, docs[b]]].forEach(function (z) {
            var X = z[0], Y = z[1], dx = z[2];
            var hits = pairHits(X.d, Y.d); if (!hits.length) return;
            var ps = dx ? para45(dx) : [];
            var spec = hits.filter(function (h) { return h[0].indexOf('i:') === 0 || !(CLS[h[0].slice(2)] || {}).broad; });
            var use = spec.length ? spec : hits;
            if (spec.length) broadOnly = false;
            var idx = []; use.forEach(function (h) { h[1].forEach(function (n) { if (idx.indexOf(n) < 0) idx.push(n); }); }); idx.sort(function (p, q) { return p - q; });
            var rx = hlRx(use.map(function (h) { return h[0]; }));
            var html = idx.slice(0, 8).map(function (n) {
              var p = ps[n] || ''; var s = sevOf(p); if (!(spec.length === 0)) sev = Math.max(sev, s); else sev = Math.max(sev, 0);
              return '<div class="dg-para">' + (rx ? esc(p).replace(rx, '<mark>$1</mark>') : esc(p)) + '</div>';
            }).join('');
            if (!dx) html = '<div class="dg-para">Нет связи: текст инструкции не загружен.</div>';
            blocks.push('<div class="dg-from">В инструкции «' + esc(X.tn) + '» — ' + esc(use.map(function (h) { return keyName(h[0]); }).join(', ')) + ':</div>' + html + (idx.length > 8 ? '<div class="dg-sub">…и ещё ' + (idx.length - 8) + ' абз. — откройте карточку, раздел 4.5</div>' : ''));
          });
          if (!blocks.length) { quiet.push(A.tn + ' + ' + B.tn); continue; }
          if (broadOnly) sev = 0;
          pairs.push({ sev: sev, html: '<div class="dg-pair s' + sev + '"><h3>' + esc(A.tn) + ' + ' + esc(B.tn) + '<span class="dg-sev s' + sev + '">' + SEV[sev] + '</span></h3>' + (broadOnly ? '<div class="dg-sub">Только общие формулировки (например, «гипотензивные средства»).</div>' : '') + blocks.join('') + '</div>' });
        }
        pairs.sort(function (p, q) { return q.sev - p.sev; });
        document.getElementById('dgout').innerHTML = pairs.map(function (p) { return p.html; }).join('') +
          (quiet.length ? '<div class="dg-card"><b>Совпадений в разделе 4.5 не найдено</b><div class="dg-sub">' + esc(quiet.join('; ')) + '</div></div>' : '') +
          (missing.length ? '<div class="dg-note">Нет инструкции, проверить нельзя: ' + esc(missing.join(', ')) + '</div>' : '');
      });
    }

    return {
      route: function (parts, params) {
        params = params || new URLSearchParams('');
        if (parts[0] === 'drugs') wait(function () { searchPage(params.get('q')); });
        else if (parts[0] === 'drug') wait(function () { cardPage(+parts[1]); });
        else if (parts[0] === 'ix') wait(ixPage);
      },
      // открыть поиск по названию из других экранов (схемы, КР)
      href: function (name) { return '#drugs?q=' + encodeURIComponent(clean(name)); },
      // есть ли такой препарат в справочнике (для ссылок «Инструкция» в схемах); false, пока данные не загружены
      has: function (name) { if (!D) return false; var r = search(clean(name), 1); return !!(r.length && r[0].s >= 30 && D.rows[r[0].i][6] >= 0); },
      preload: function () { load().catch(function () {}); }
    };
  };
})();
