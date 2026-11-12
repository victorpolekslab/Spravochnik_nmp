"""Шаг 4. Проверка чисел на страницах-сканах.

python3 check_ocr.py jobs.json out_dir [--workers 2]
jobs.json: [{"pdf": путь к PDF, "id": имя документа}, ...]

1. Каждая страница-скан распознаётся с оценкой уверенности по каждому слову (Tesseract, TSV).
   Текст страницы сохраняется рядом с PDF (<pdf>.ocr.json) — из него потом собирается md без повторного OCR.
2. В каждой строке ищутся дозировки: число + единица (мг, мкг, мл, ЕД, %, капли…).
   Строка сомнительна, если
   • у числа низкая уверенность распознавания, или
   • при повторном чтении вырезки этой строки (режим «одна строка») число получилось другим, или
   • единица измерения искажена («мr», «rр»).
3. Для сомнительной строки сохраняется вырезка из скана (crops/), список — в check.jsonl.
"""
import json, os, re, sys, subprocess, argparse, io, concurrent.futures as cf
import pymupdf
from PIL import Image

ap = argparse.ArgumentParser(); ap.add_argument('jobs'); ap.add_argument('out')
ap.add_argument('--workers', type=int, default=2); ap.add_argument('--conf', type=float, default=80)
ap.add_argument('--dpi', type=int, default=300)
a = ap.parse_args()
os.makedirs(os.path.join(a.out, 'crops'), exist_ok=True)
env = dict(os.environ, OMP_THREAD_LIMIT='1')

UNITS = r'(?:мкг|мг|нг|г|кг|мл|л|ЕД|МЕ|ммоль|мкмоль|%|капл\w*|таблет\w*|доз\w*|раз\w*|ч|мин|сут\w*)'
NUM = r'\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?'
DOSE = re.compile(r'(?<![\w,.])(' + NUM + r')\s*(' + UNITS + r')(?![а-яё])', re.I)
BADUNIT = re.compile(r'\d\s*(?:мr|rр|rp|mг|м\s+г\b|мкr)', re.I)

def nn(s):
    return re.sub(r'\s+', '', s.replace('–', '-').replace('.', ','))

def doses(text):
    return [(nn(m.group(1)), m.group(2).lower()[:3]) for m in DOSE.finditer(text)]

def tess(png, psm, tsv=False):
    cmd = ['tesseract', 'stdin', 'stdout', '-l', 'rus+eng', '--psm', str(psm)] + (['tsv'] if tsv else [])
    return subprocess.run(cmd, input=png, capture_output=True, timeout=300, env=env).stdout.decode('utf-8', 'replace')

def page_lines(tsv):
    lines, order = {}, []
    for row in tsv.splitlines()[1:]:
        p = row.split('\t')
        if len(p) < 12:
            continue
        key = (int(p[2]), int(p[3]), int(p[4]))   # блок, абзац, строка
        if not p[11].strip():
            continue
        if key not in lines:
            lines[key] = []; order.append(key)
        lines[key].append({'t': p[11], 'conf': float(p[10]), 'x': int(p[6]), 'y': int(p[7]), 'w': int(p[8]), 'h': int(p[9])})
    return [(k, lines[k]) for k in order]

def work(job):
    res = {'id': job['id'], 'pages': 0, 'flags': []}
    cache_path = job['pdf'] + '.ocr.json'
    cache = {}
    try:
        doc = pymupdf.open(job['pdf'])
        for pno, pg in enumerate(doc):
            if len(pg.get_text().strip()) >= 300:
                continue
            res['pages'] += 1
            png = pg.get_pixmap(dpi=a.dpi, colorspace=pymupdf.csGRAY).tobytes('png')
            lines = page_lines(tess(png, 6, tsv=True))
            # текст страницы: строки по порядку, пустая строка между абзацами
            out, prev = [], None
            for k, words in lines:
                if prev and k[:2] != prev[:2]:
                    out.append('')
                out.append(' '.join(w['t'] for w in words)); prev = k
            cache[str(pno)] = '\n'.join(out)
            img = None
            for k, words in lines:
                text = ' '.join(w['t'] for w in words)
                found = doses(text)
                bad = bool(BADUNIT.search(text))
                if not found and not bad:
                    continue
                reasons = []
                numw = [w for w in words if re.search(r'\d', w['t'])]
                low = [w for w in numw if w['conf'] < a.conf]
                if low:
                    reasons.append('низкая уверенность: ' + ', '.join(f'«{w["t"]}» ({w["conf"]:.0f})' for w in low[:4]))
                if img is None:
                    img = Image.open(io.BytesIO(png))
                x0 = max(0, min(w['x'] for w in words) - 15); y0 = max(0, min(w['y'] for w in words) - 12)
                x1 = min(img.width, max(w['x'] + w['w'] for w in words) + 15)
                y1 = min(img.height, max(w['y'] + w['h'] for w in words) + 12)
                crop = img.crop((x0, y0, x1, y1))
                if found:   # повторное чтение строки отдельно
                    buf = io.BytesIO(); crop.save(buf, 'PNG')
                    second = tess(buf.getvalue(), 7).strip()
                    if [d[0] for d in doses(second)] != [d[0] for d in found]:
                        reasons.append(f'повторное чтение: «{second[:120]}»')
                if bad:
                    reasons.append('искажённая единица измерения')
                if not reasons:
                    continue
                name = f'{job["id"]}_p{pno + 1}_{len(res["flags"]) + 1}.png'
                crop.resize((max(1, crop.width // 2), max(1, crop.height // 2))).save(
                    os.path.join(a.out, 'crops', name), optimize=True)
                res['flags'].append({'page': pno + 1, 'line': text[:240], 'why': reasons, 'crop': name})
        json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception as e:
        res['error'] = repr(e)[:200]
    return res

jobs = json.load(open(a.jobs, encoding='utf-8'))
jl = os.path.join(a.out, 'check.jsonl')
done = set()
if os.path.exists(jl):
    for l in open(jl, encoding='utf-8'):
        x = json.loads(l)
        if 'error' not in x: done.add(x['id'])
todo = [j for j in jobs if j['id'] not in done]
print('документов', len(jobs), 'осталось', len(todo), flush=True)
with cf.ThreadPoolExecutor(a.workers) as ex, open(jl, 'a', encoding='utf-8') as jf:
    for x in ex.map(work, todo):
        jf.write(json.dumps(x, ensure_ascii=False) + '\n'); jf.flush()
