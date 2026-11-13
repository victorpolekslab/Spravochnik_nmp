# База клинических рекомендаций (КР) Минздрава России — для любых приложений

В базе собраны все **действующие** КР рубрикатора cr.minzdrav.gov.ru. База выгружена для «Справочника НМП», но подходит для любых медицинских приложений и чатов.
Дата выгрузки — в `meta.built` (сейчас 2026-11-13).

## Где лежит

| Что | Где | Для чего |
|---|---|---|
| Полная база SQLite (`kr_full.db.gz` в двух частях, 91 МБ → 118 МБ) | ветка **`kr-data`** репозитория `victorpolekslab/Spravochnik_nmp` | приложения: поиск, разделы, МКБ |
| Тексты в Markdown по одному файлу | ветка **`kr`**: `kr/<ID>.md`, оглавление `INDEX.md` | чтение и написание материалов |
| Исходный список рубрикатора (`kr_list.json.gz`) | ветка `kr-data` | метаданные в исходном виде |

Скачать и собрать базу:
```
B=https://raw.githubusercontent.com/victorpolekslab/Spravochnik_nmp/kr-data
curl -sSLO $B/kr_full.db.gz.part1 -sSLO $B/kr_full.db.gz.part2 -sSLO $B/SHA256SUMS
cat kr_full.db.gz.part1 kr_full.db.gz.part2 > kr_full.db.gz && sha256sum -c --ignore-missing SHA256SUMS && gunzip kr_full.db.gz
```
Или `git clone --depth 1 -b kr-data https://github.com/victorpolekslab/Spravochnik_nmp`.

## Схема `kr_full.db`

- `meta(k, v)` — `built` (дата выгрузки), `ncr` (число КР), `cr_src`, `mkb_src` (МКБ-10: НСИ Минздрава, OID 1.2.643.5.1.13.13.11.1005).
- `cr(id, code, version, name, age, ass, pub, mkb, cls, q)` — одна строка на действующую КР:
  - `id` — `"<code>_<version>"`, например `162_3`;
  - `age` — 1 взрослые, 2 дети, 3 все;
  - `ass` — разработчики;
  - `pub` — дата публикации;
  - `mkb` — коды через запятую;
  - `q` — нормализованный текст для поиска по названию.
- `sec(id, cr, ord, sid, title, lvl, len, html)` — разделы КР по порядку (`ord`):
  - `sid` — идентификатор раздела рубрикатора (`doc_1`, `doc_3_1`, `doc_crat_info`, `doc_a3` …);
  - `lvl` — уровень вложенности;
  - `html` — **zlib** от UTF-8 HTML (Python: `zlib.decompress(html).decode()`). Рисунки удалены. Таблицы и списки сохранены.
- `summ(cr, data)` — **zlib** от JSON с дословными фрагментами КР по разделам: `cls`, `diag`, `treat` и т. п. Это краткая выжимка для карточки КР.
- `mkb(id, code, name, parent, lvl, sort, nchild, ncr, q, orig)` — дерево МКБ-10 (14 937 узлов); `ncr` — число КР на узел.
- `cr_mkb(cr, code)` — связь КР ↔ код МКБ.
- `fts` — полнотекстовый индекс FTS4 по разделам (`rowid` = `sec.id`, `content=""`). Поиск: `SELECT rowid FROM fts WHERE fts MATCH 'слово*'`.

## Правила использования

- Это официальные документы Минздрава. В материалах указывайте ID КР (`КР162_3`) и ссылку на оригинал: `https://cr.minzdrav.gov.ru/preview-cr/<ID>`.
- Дозы берите только из текста КР. Если в КР дозы нет — «по инструкции». Применение вне инструкции в КР помечено «#».
- База — снимок на дату `meta.built`. КР обновляются: показывайте дату базы пользователю.

## Живые данные с сайта Минздрава

`apicr.minzdrav.gov.ru` не отвечает зарубежным серверам: облаку Claude, GitHub Actions. С телефонов в России он доступен.
- Текст одной КР: `GET https://apicr.minzdrav.gov.ru/api.ashx?op=GetClinrec2&id=<ID>`, заголовок `Accept: application/json`. Ответ — JSON, разделы в `obj.sections[]` `{id, title, content(HTML)}`. Рабочий код — `Downloader.java` в этом репозитории.
- Список КР (`GetJsonClinrecs`, `GetJsonSpecialityClinrecs`) на 11.11.2026 отвечает «Ошибка выполнения» (HTTP 500) всем, включая телефоны.

## Как обновляется

Новые и обновлённые КР передаёт телефон организатора «Справочника НМП» (экран «Новое в КР» → «Скачать и передать»). Чат разработки забирает их (`tools/kr_pull.py`), пересобирает базу (`tools/build_db.py`, `tools/add_summ.py`) и обновляет ветки `kr-data` и `kr`. Свежая база — всегда в ветке `kr-data`, дата — в `meta.built` и в `VERSION`.

## Образец приложения

Код «Справочника НМП» в ветке `main` открыт, его можно взять за основу:
- `android/` — Android-оболочка на Java + WebView: база `cr.db` в assets, `Api.java` — запросы к SQLite для страницы, `Downloader.java` — тексты КР с сайта, `Ota.java` — фоновые обновления содержимого с подписью;
- `android/app/src/main/assets/www/` — интерфейс (HTML/JS/CSS), он же PWA-версия (`web/build.py`, GitHub Pages);
- `tools/build_db.py`, `tools/add_summ.py`, `tools/kr_export.py` — сборка базы и Markdown из выгрузки рубрикатора.
