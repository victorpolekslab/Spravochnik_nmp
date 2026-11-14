"""Проверка орфографии в распознанных (OCR) текстах — осторожная, без изменения цифр.

python3 spell_ocr.py <ветка drugs> --map out/spell_map.json --log out/spell_changes.tsv [--apply]
Словарь: все слова инструкций с текстовым слоем (2,5 тыс. ОХЛП и инструкций — медицинская лексика),
названия и МНН препаратов из индекса и общий русский словарь (pyspellchecker).
Исправляются только слова с буквами (цифры не трогаются), которых нет в словаре:
  1) латинские буквы-двойники внутри русского слова: «pa3a» → «раза», «Ha» → «На», «cyTки» → «сутки»;
  2) одна типовая ошибка OCR (замена, пропуск или лишняя буква) — если в словаре ровно один
     явный кандидат и слово не короче 6 букв.
Названия препаратов в словаре, поэтому не «исправляются» в другие препараты.
"""
import json, os, re, sys, argparse, collections

ap = argparse.ArgumentParser(); ap.add_argument('branch')
ap.add_argument('--map', required=True); ap.add_argument('--log', required=True); ap.add_argument('--apply', action='store_true')
a = ap.parse_args()
MD = os.path.join(a.branch, 'md')

LAT2CYR = str.maketrans({'A': 'А', 'B': 'В', 'C': 'С', 'E': 'Е', 'H': 'Н', 'K': 'К', 'M': 'М', 'O': 'О', 'P': 'Р', 'T': 'Т', 'X': 'Х',
                         'Y': 'У', 'a': 'а', 'c': 'с', 'e': 'е', 'o': 'о', 'p': 'р', 'x': 'х', 'y': 'у', 'k': 'к', 'm': 'м',
                         'r': 'г', 'n': 'п', 'u': 'и', 'b': 'Ь', '3': 'з', '0': 'о', '6': 'б'})
TOK = re.compile(r'[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё]+)*')
CYR = re.compile(r'[А-Яа-яЁё]')
ALPHA = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'

def is_ocr(t):
    return 'Распознано автоматически (OCR)' in t

def body(t):
    return t.split('\n## Проверка распознавания\n')[0]

# --- словарь
vocab = collections.Counter()
files = sorted(os.listdir(MD))
for f in files:
    t = open(os.path.join(MD, f), encoding='utf-8').read()
    if is_ocr(t):
        continue
    for w in TOK.findall(body(t)):
        if CYR.search(w) and not re.search(r'[A-Za-z0-9]', w):
            vocab[w.lower()] += 1
idx = json.load(open(os.path.join(a.branch, 'drugs_index.json'), encoding='utf-8'))
for i in idx:
    for w in TOK.findall(i['tn'] + ' ' + i['inn'] + ' ' + i['form']):
        vocab[w.lower()] += 3
try:
    from spellchecker import SpellChecker
    for w, c in SpellChecker(language='ru').word_frequency.dictionary.items():
        vocab[w] += 1
except Exception as e:
    print('общий словарь недоступен:', e)
print('словарь: %d слов' % len(vocab))

import pymorphy3
MORPH = pymorphy3.MorphAnalyzer()
# латинские слова и сокращения, которые встречаются в текстовых инструкциях (Cmax, AUC, CYP3A4, ATX…), — не трогать
latin_ok = collections.Counter()
for f in files:
    t = open(os.path.join(MD, f), encoding='utf-8').read()
    if not is_ocr(t):
        for w in TOK.findall(body(t)):
            if re.fullmatch(r'[A-Za-z0-9-]+', w) and re.search(r'[A-Za-z]', w):
                latin_ok[w.lower()] += 1
LATIN_OK = {w for w, c in latin_ok.items() if c >= 3}
CYR2LAT = str.maketrans({'А': 'A', 'В': 'B', 'С': 'C', 'Е': 'E', 'Н': 'H', 'К': 'K', 'М': 'M', 'О': 'O', 'Р': 'P', 'Т': 'T', 'Х': 'X',
                         'а': 'a', 'с': 'c', 'е': 'e', 'о': 'o', 'р': 'p', 'х': 'x', 'у': 'y'})
KAZ = re.compile(r'[әғқңөұүһіӘҒҚҢӨҰҮҺІ]')

def known(w):
    lw = w.lower()
    return lw in vocab or (CYR.search(lw) and not re.search(r'[A-Za-z0-9]', lw) and MORPH.word_is_known(lw))

def inflected(lw, cand):
    if len(lw) == len(cand) and lw[:-2] == cand[:-2]:
        return True                                              # отличается только окончание
    # «фебуксостата» при словаре «фебуксостат» — это падежная форма, а не ошибка
    if cand.startswith(lw) or lw.startswith(cand):
        return True
    return any(lw[:-k] in vocab for k in (1, 2, 3) if len(lw) - k >= 5)

SHORT = set('на не но во от по до из за ко со то их ее её ей он ни мы вы ты же ли бы или все как так при для без над под про том тем оно они это его ему нет раз два три год уже еще ещё сам всё ту те та та'.split())
PREP_CASE = {'у': {'gent'}, 'в': {'accs', 'loct', 'loc2'}, 'с': {'ablt', 'gent'}, 'к': {'datv'}, 'и': None}

def match_case(src, dst):
    letters = [ch for ch in src if ch.isalpha()]
    if len(letters) > 1 and sum(ch.isupper() for ch in letters) * 2 > len(letters):
        return dst.upper()
    if src[:1].isupper():
        return dst[:1].upper() + dst[1:]
    return dst

# только типичные для OCR путаницы букв (а не любые замены)
CONF = {}
for grp in ('нпилй', 'шщ', 'ьъы', 'зэ', 'ецсо', 'тгп', 'вз', 'ае', 'лд', 'хж', 'бв', 'чу'):
    for x in grp:
        CONF.setdefault(x, set()).update(set(grp) - {x})

def edits1(w):
    out = set()
    for i in range(len(w)):
        out.add(w[:i] + w[i + 1:])                               # лишняя буква
        for c in CONF.get(w[i], ()):
            out.add(w[:i] + c + w[i + 1:])                       # перепутанная буква
    for c in ALPHA:
        out.add(c + w)                                           # потерянная первая буква («ихорадка»)
    return out

def fix(w):
    """Возвращает (исправление, способ) или (None, None)."""
    if known(w) or not re.search(r'[A-Za-zА-Яа-яЁё]', w):
        return None, None
    has_cyr, has_lat = bool(CYR.search(w)), bool(re.search(r'[A-Za-z]', w))
    if re.fullmatch(r'[0-9]+', w) or (re.search(r'\d', w) and not has_cyr and not has_lat):
        return None, None
    # 1) двойники
    if '-' in w and all(not (CYR.search(x) and re.search('[A-Za-z]', x)) for x in w.split('-')):
        return None, None                                        # «анти-Xa», «B-лимфоцитов» — части в своей азбуке
    if has_lat:
        lat = w.translate(CYR2LAT)
        cyr_alt = w.translate(LAT2CYR).lower()
        if lat.lower() in LATIN_OK and vocab.get(cyr_alt, 0) <= latin_ok[lat.lower()] * 3:                              # «Сmах» → «Cmax»: латинское сокращение
            return (lat, 'двойники') if lat != w else (None, None)
        if not has_cyr and (w.lower() in LATIN_OK or not re.fullmatch(r'[ABCEHKMOPTXYaceopxykmrnub3]+', w)):
            return None, None                                    # обычное латинское слово
    if has_lat or (has_cyr and re.search(r'(?<=[A-Za-zА-Яа-яЁё])[306](?=[A-Za-zА-Яа-яЁё])', w)):
        if re.search(r'\d', w) and not re.fullmatch(r'(?:[A-Za-zА-Яа-яЁё]+[306])+[A-Za-zА-Яа-яЁё]+', w):
            return None, None                                    # цифра в конце или в начале: «мм3», «CYP3A4» — не трогать
        c = w.translate(LAT2CYR)
        cl = c.lower()
        if (not has_cyr or len(cl) <= 2) and len(cl) <= 3 and cl not in SHORT:
            return None, None                                    # «Mn», «XY», «CE» — скорее латиница
        if not has_cyr and not MORPH.word_is_known(cl):
            return None, None
        if not (MORPH.word_is_known(cl) or vocab.get(cl, 0) >= 3):
            return None, None
        if CYR.search(c) and not re.search(r'[A-Za-z0-9]', c) and known(c) and len(c) >= 2:
            return c, 'двойники'
        return None, None
    # 2) одна ошибка OCR в русском слове
    lw = w.lower()
    if len(lw) < 6 or re.search(r'[^а-яё-]', lw) or known(lw):
        return None, None
    # «упациентов» → «у пациентов»
    rest = lw[1:]
    if lw[0] in PREP_CASE and vocab.get(rest, 0) >= 5 and len(lw) >= 7 and not w[1:2].isupper() or (
            lw[0] in PREP_CASE and w.isupper() and vocab.get(rest, 0) >= 5 and len(lw) >= 7):
        cases = PREP_CASE[lw[0]]
        if not MORPH.word_is_known(rest):
            pass
        elif cases is None or any(pp.tag.case in cases for pp in MORPH.parse(rest)):
            return w[0] + ' ' + w[1:], 'слитно'
    def seg_ok(c):
        # правка внутри короткой части через дефис («ВПЧ-…» → «ВИЧ-…») — не трогать
        a, b = lw.split('-'), c.split('-')
        if len(a) != len(b):
            return False
        return all(x == y or ((len(x) >= 5 or lw == 'хс-линп') and not inflected(x, y)) for x, y in zip(a, b))
    cands = [(vocab[c], c) for c in edits1(lw)
             if c in vocab and len(c) >= 6 and not inflected(lw, c) and seg_ok(c)
             and (vocab[c] >= 10 or MORPH.word_is_known(c))]
    if not cands:
        return None, None
    cands.sort(reverse=True)
    best = cands[0]
    if best[0] < 3 or (len(cands) > 1 and cands[1][0] * 3 > best[0]):
        return None, None
    return match_case(w, best[1]), 'одна буква'

# --- проход по OCR-документам
mapping, log, stat = {}, [], collections.Counter()
for f in files:
    p = os.path.join(MD, f)
    t = open(p, encoding='utf-8').read()
    if not is_ocr(t):
        continue
    b, sep, rest = t.partition('\n## Проверка распознавания\n')
    head, s2, main = b.partition('\n\n## ')     # шапку (название, источник) не трогаем
    out, last = [], 0
    toks = list(TOK.finditer(main))
    kaz_spans = [(lm.start(), lm.end()) for lm in re.finditer(r'[^\n]+', main) if KAZ.search(lm.group(0))]
    def in_kaz(pos):
        return any(a0 <= pos < a1 for a0, a1 in kaz_spans)
    for ti, m in enumerate(toks):
        w = m.group(0)
        if kaz_spans and in_kaz(m.start()):
            continue                                             # строки на казахском не проверяем
        if not CYR.search(w):                                    # целиком латинское слово — только между русскими словами
            prev = toks[ti - 1].group(0) if ti else ''
            nxt = toks[ti + 1].group(0) if ti + 1 < len(toks) else ''
            if not (CYR.search(prev) and CYR.search(nxt)):
                continue
        if w not in mapping:
            mapping[w] = fix(w)
        r, how = mapping[w]
        if r and r != w:
            out.append(main[last:m.start()]); out.append(r); last = m.end()
            stat[how] += 1
            if len(log) < 200000:
                log.append((f, w, r, how, main[max(0, m.start() - 30):m.end() + 30].replace('\n', ' ').replace('\t', ' ')))
    if out:
        out.append(main[last:])
        new = head + s2 + ''.join(out) + (sep + rest if sep else '')
        stat['документов'] += 1
        if a.apply:
            open(p, 'w', encoding='utf-8').write(new)
json.dump({k: v[0] for k, v in mapping.items() if v[0] and v[0] != k}, open(a.map, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
with open(a.log, 'w', encoding='utf-8') as lf:
    lf.write('файл\tбыло\tстало\tспособ\tконтекст\n')
    for row in log:
        lf.write('\t'.join(row) + '\n')
print(dict(stat), '| разных замен:', sum(1 for v in mapping.values() if v[0]), '|', 'записано' if a.apply else 'пробный прогон (без --apply)')
