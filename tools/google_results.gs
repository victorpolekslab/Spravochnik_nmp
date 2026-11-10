/**
 * «Справочник НМП» — сбор результатов обучения в Google Таблицу.
 *
 * Установка: Таблица → Расширения → Apps Script → вставить этот код целиком → Сохранить →
 * Развернуть → Новое развёртывание → Тип: Веб-приложение; Запуск от имени: Я; Доступ: Все → Развернуть →
 * разрешить доступ → скопировать URL веб-приложения (…/exec).
 *
 * В таблицу пишутся только код учётки (обезличенный), материал, баллы и дата — без фамилий.
 * Принимаются только коды учёток из learn.json на сайте справочника.
 * Чтение результатов (экран «Отчёт по обучению» в приложении) — только с ключом READ_KEY.
 */
const READ_KEY = 'ВСТАВЬТЕ_СВОЙ_КЛЮЧ';  // ключ организатора: длинная случайная строка
const USERS_URL = 'https://victorpolekslab.github.io/Spravochnik_nmp/learn.json';
const HEAD = ['Получено', 'Пройдено', 'Код учётки', 'Материал', 'Событие', 'Баллы', 'Из', 'Ответы', 'Версия', 'Платформа', 'ID события'];

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName('Результаты');
  if (!sh) { sh = ss.insertSheet('Результаты'); sh.appendRow(HEAD); sh.setFrozenRows(1); sh.getRange(1, 1, 1, HEAD.length).setFontWeight('bold'); }
  return sh;
}

function validUids_() {
  const c = CacheService.getScriptCache();
  let s = c.get('uids');
  if (!s) {
    const r = UrlFetchApp.fetch(USERS_URL + '?t=' + Date.now(), { muteHttpExceptions: true });
    s = JSON.stringify(Object.keys((JSON.parse(r.getContentText()) || {}).users || {}));
    c.put('uids', s, 600);
  }
  return JSON.parse(s);
}

const clean_ = (v, re, n) => { v = String(v == null ? '' : v); return re.test(v) ? v.slice(0, n) : ''; };

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    const list = (Array.isArray(d) ? d : [d]).slice(0, 50);
    const ok = validUids_(), sh = sheet_();
    const lock = LockService.getScriptLock(); lock.waitLock(10000);
    const seen = new Set(sh.getLastRow() > 1 ? sh.getRange(Math.max(2, sh.getLastRow() - 499), 11, Math.min(500, sh.getLastRow() - 1), 1).getValues().map(r => r[0]) : []);
    let n = 0;
    list.forEach(x => {
      const uid = clean_(x.uid, /^[0-9a-f]{24}$/, 24), id = clean_(x.id, /^[\w-]{6,40}$/, 40);
      if (!uid || ok.indexOf(uid) < 0 || (id && seen.has(id))) return;
      sh.appendRow([new Date(), x.ts ? new Date(x.ts) : '', uid, clean_(x.item, /^[\w:-]{1,40}$/, 40), clean_(x.ev, /^[\w-]{1,20}$/, 20),
        Math.max(0, Math.min(100, Number(x.score) || 0)), Math.max(0, Math.min(100, Number(x.total) || 0)),
        clean_(x.ans, /^[01]{0,40}$/, 40), clean_(x.v, /^[\d.]{1,10}$/, 10), clean_(x.p, /^[a-z]{1,10}$/, 10), id]);
      if (id) seen.add(id); n++;
    });
    lock.releaseLock();
    return out_({ ok: true, n: n });
  } catch (err) { return out_({ ok: false }); }
}

function doGet(e) {
  if (((e && e.parameter && e.parameter.key) || '') !== READ_KEY) return out_({ ok: false, err: 'key' });
  const v = sheet_().getDataRange().getValues(); v.shift();
  return out_({ ok: true, rows: v.map(r => ({ at: r[0], ts: r[1], uid: r[2], item: r[3], ev: r[4], score: r[5], total: r[6], ans: r[7] })) });
}

function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
