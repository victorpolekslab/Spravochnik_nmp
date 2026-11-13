/* Проверка свободных ответов для части "exam" (course.json). Без ИИ, без сети, без зависимостей.
   Работает в браузере (window.ExamChecker) и в Node (module.exports). */
(function (root) {
  "use strict";

  // 1. Нормализация: строчные, ё→е, всё кроме букв и цифр → пробел, пробелы по краям.
  //    «СТ» кириллицей в токенах вида ст / пст / импст / имбпст / окспст → латинское st.
  function norm(s) {
    var t = " " + String(s || "").toLowerCase().replace(/ё/g, "е")
      .replace(/[^a-zа-я0-9]+/g, " ").trim() + " ";
    return t.replace(/ ((?:им|окс)?б?п?)ст(?= )/g, " $1st");
  }

  function lev(a, b) {
    var d = [], i, j, p, t;
    for (j = 0; j <= b.length; j++) d[j] = j;
    for (i = 1; i <= a.length; i++) {
      p = d[0]; d[0] = i;
      for (j = 1; j <= b.length; j++) {
        t = d[j];
        d[j] = Math.min(d[j] + 1, d[j - 1] + 1, p + (a[i - 1] === b[j - 1] ? 0 : 1));
        p = t;
      }
    }
    return d[b.length];
  }

  // 2. Термин совпал, если с него начинается слово ответа (корень: «нижн» → «нижней»).
  //    Термин из одних букв длиной от 6 — допускается одна опечатка (замена, пропуск или лишняя буква).
  function hit(t, term) {
    var s = norm(term).trim();
    if (!s) return false;
    if (t.indexOf(" " + s) !== -1) return true;
    if (/^[a-zа-я]{6,}$/.test(s)) {
      var w = t.trim().split(" ");
      for (var i = 0; i < w.length; i++) {
        for (var L = s.length - 1; L <= s.length + 1; L++) {
          if (w[i].length >= L && lev(w[i].slice(0, L), s) <= 1) return true;
        }
      }
    }
    return false;
  }
  function group(t, g) { for (var i = 0; i < g.length; i++) if (hit(t, g[i])) return true; return false; }

  // 3. Запреты: r — регулярное выражение по нормализованному тексту.
  //    neg: true — совпадение не считается, если рядом (±2 слова) стоит отрицание.
  var NEG = /^(не|нельзя|без|ни|нет|противопоказ\S*|запрещ\S*|исключ\S*)$/;
  function banHit(t, b) {
    var re = new RegExp(b.r);
    if (!b.neg) return re.test(t);
    var w = t.trim().split(" ");
    for (var i = 0; i < w.length; i++) {
      if (!re.test(" " + w[i] + " ")) continue;
      var near = w.slice(Math.max(0, i - 2), i).concat(w.slice(i + 1, i + 3));
      var negated = false;
      for (var k = 0; k < near.length; k++) if (NEG.test(near[k])) negated = true;
      if (!negated) return true;
    }
    return false;
  }

  function numbers(raw) {
    var m = String(raw || "").match(/\d+(?:[.,]\d+)?/g) || [];
    return m.map(function (x) { return parseFloat(x.replace(",", ".")); });
  }

  // 4. Итог по полю: ok — верно (1 балл), almost — почти (0,5), error — есть ошибка (0), wrong — неверно (0).
  function grade(f, raw) {
    if (!String(raw || "").trim()) return { v: "empty", score: 0, msg: "Введите ответ" };
    var t = norm(raw);
    if (f.num) {
      var nums = numbers(raw), inRange = nums.some(function (x) { return x >= f.num[0] && x <= f.num[1]; });
      if (inRange || (f.alt && group(t, f.alt))) return { v: "ok", score: 1, msg: "" };
      return { v: "wrong", score: 0, msg: nums.length ? (f.nm || "значение неверное") : "нужно число" };
    }
    var bans = (f.ban || []).filter(function (b) { return banHit(t, b); });
    var miss = (f.need || []).filter(function (g) { return !group(t, g); });
    if (miss.length) return { v: "wrong", score: 0, msg: bans.length ? bans[0].m : (f.nm || "нет ключевого понятия") };
    if (bans.length) return { v: "error", score: 0, msg: bans[0].m };
    if (f.want && f.want.some(function (g) { return !group(t, g); })) return { v: "almost", score: 0.5, msg: f.wm || "ответ неполный" };
    var bonus = f.bonus && f.bonus.some(function (g) { return group(t, g); });
    return { v: "ok", score: 1, msg: bonus ? (f.bm || "") : "" };
  }

  // 5. Итог занятия: доля баллов от числа полей; «Мой ответ верный» — 1 балл (self: true).
  function total(results, pass) {
    var n = results.length, s = 0;
    results.forEach(function (r) { s += r.self ? 1 : r.score; });
    var share = n ? s / n : 0;
    return { score: s, of: n, share: share, passed: share >= (pass || 0.75) };
  }

  var api = { norm: norm, hit: hit, grade: grade, total: total };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ExamChecker = api;
})(this);
