/**
 * «Справочник НМП» — сбор результатов обучения в Google Таблицу.
 *
 * Установка: script.google.com → Новый проект (или Таблица → Расширения → Apps Script) → вставить этот код целиком → Сохранить →
 * Развернуть → Новое развёртывание → Тип: Веб-приложение; Запуск от имени: Я; Доступ: Все → Развернуть →
 * разрешить доступ → скопировать URL веб-приложения (…/exec).
 *
 * В таблицу пишутся только код учётки (обезличенный), материал, баллы и дата — без фамилий.
 * Принимаются только коды учёток из learn.json на сайте справочника.
 * Чтение результатов (экран «Отчёт по обучению» в приложении) — только с ключом READ_KEY.
 *
 * КР с телефона организатора: сайт Минздрава недоступен с зарубежных серверов, поэтому телефон скачивает новые КР
 * и присылает их сюда (op: 'kr', с ключом READ_KEY). Файлы лежат на Google Диске в папке
 * «Справочник НМП — КР с телефона»; чат разработки забирает их через doGet (op=kr_list / kr_get).
 */
const READ_KEY = 'ВСТАВЬТЕ_СВОЙ_КЛЮЧ';  // ключ организатора: длинная случайная строка
const USERS_URL = 'https://victorpolekslab.github.io/Spravochnik_nmp/learn.json';
const HEAD = ['Получено', 'Пройдено', 'Код учётки', 'Материал', 'Событие', 'Баллы', 'Из', 'Ответы', 'Версия', 'Платформа', 'ID события'];

function book_() {   // работает и как отдельный проект: таблица создаётся сама при первом запуске
  const bound = SpreadsheetApp.getActiveSpreadsheet();
  if (bound) return bound;
  const pr = PropertiesService.getScriptProperties(), id = pr.getProperty('SHEET_ID');
  if (id) { try { return SpreadsheetApp.openById(id); } catch (e) {} }
  const ss = SpreadsheetApp.create('Справочник НМП — результаты обучения');
  pr.setProperty('SHEET_ID', ss.getId());
  return ss;
}

/** Запустите один раз вручную (кнопка «Выполнить»), чтобы выдать разрешения и создать таблицу. */
function setup() { const sh = sheet_(); Logger.log('Таблица: ' + sh.getParent().getUrl()); }

function sheet_() {
  const ss = book_();
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
    if (d && d.op === 'kr') return krPut_(d);
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
  const op = e.parameter.op || '';
  if (op === 'kr_list') {
    const res = [], it = krFolder_().getFiles();
    while (it.hasNext()) { const f = it.next(); res.push({ name: f.getName(), size: f.getSize(), at: f.getLastUpdated(), src: f.getDescription() }); }
    return out_({ ok: true, files: res });
  }
  if (op === 'kr_get') {
    const it = krFolder_().getFilesByName(String(e.parameter.name || ''));
    if (!it.hasNext()) return out_({ ok: false, err: 'nofile' });
    const f = it.next();
    return out_({ ok: true, name: f.getName(), data: Utilities.base64Encode(f.getBlob().getBytes()) });
  }
  const v = sheet_().getDataRange().getValues(); v.shift();
  return out_({ ok: true, sheet: sheet_().getParent().getUrl(), rows: v.map(r => ({ at: r[0], ts: r[1], uid: r[2], item: r[3], ev: r[4], score: r[5], total: r[6], ans: r[7] })) });
}

function krFolder_() {
  const pr = PropertiesService.getScriptProperties(), id = pr.getProperty('KR_FOLDER');
  if (id) { try { return DriveApp.getFolderById(id); } catch (e) {} }
  const f = DriveApp.createFolder('Справочник НМП — КР с телефона');
  pr.setProperty('KR_FOLDER', f.getId());
  return f;
}

function krPut_(d) {
  if (String(d.key || '') !== READ_KEY) return out_({ ok: false, err: 'key' });
  const name = String(d.name || '');
  if (!/^(list|\d+_\d+)\.json\.gz$/.test(name)) return out_({ ok: false, err: 'name' });
  const bytes = Utilities.base64Decode(String(d.data || ''));
  if (!bytes.length) return out_({ ok: false, err: 'empty' });
  const folder = krFolder_(), old = folder.getFilesByName(name);
  while (old.hasNext()) old.next().setTrashed(true);
  const f = folder.createFile(Utilities.newBlob(bytes, 'application/gzip', name));
  f.setDescription(String(d.src || '').slice(0, 40));
  return out_({ ok: true, name: name, size: bytes.length });
}

/** Запустите один раз вручную, чтобы выдать доступ к Google Диску (для приёма КР с телефона). */
function setupKr() { Logger.log('Папка КР: ' + krFolder_().getUrl()); }

function out_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
