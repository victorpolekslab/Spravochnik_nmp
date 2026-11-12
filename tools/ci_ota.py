"""Пакет обновления содержимого для Android при публикации сайта (GitHub Actions).

python3 tools/ci_ota.py web/dist
1. Кладёт файлы assets/www в <dist>/ota/files/.
2. Ищет подписанный манифест, который уже совпадает с этими файлами: сначала ota/ в репозитории,
   затем опубликованный на сайте. Если нашёлся — публикует его без изменений (телефоны ничего не скачивают).
3. Если файлы изменились и задан секрет OTA_KEY_PEM (содержимое закрытого ключа), подписывает
   новый манифест (tools/build_ota.py) — телефоны скачают изменившиеся файлы в фоне.
4. Без ключа — публикует сайт без нового манифеста: Android-приложения остаются на прежней версии.
"""
import hashlib, json, os, re, shutil, sys, tempfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WWW = os.path.join(ROOT, 'android/app/src/main/assets/www')
SITE = 'https://victorpolekslab.github.io/Spravochnik_nmp/ota/'
dist = sys.argv[1]
out = os.path.join(dist, 'ota')
os.makedirs(os.path.join(out, 'files'), exist_ok=True)

def current():
    files = []
    for f in sorted(os.listdir(WWW)):
        if f == 'ota_version.txt' or not re.fullmatch(r'[A-Za-z0-9_.-]+', f):
            continue
        b = open(os.path.join(WWW, f), 'rb').read()
        files.append([f, hashlib.sha256(b).hexdigest(), len(b)])
    return files

def publish(man, sig, why):
    open(os.path.join(out, 'manifest.json'), 'wb').write(man)
    open(os.path.join(out, 'manifest.sig'), 'wb').write(sig)
    print('OTA:', why, json.loads(man)['v'])

files = current()
for f, _, _ in files:
    shutil.copy(os.path.join(WWW, f), os.path.join(out, 'files', f))

cands = []
try:
    cands.append(('из репозитория', open(os.path.join(ROOT, 'ota/manifest.json'), 'rb').read(), open(os.path.join(ROOT, 'ota/manifest.sig'), 'rb').read()))
except OSError:
    pass
try:
    m = urllib.request.urlopen(SITE + 'manifest.json?t=1', timeout=30).read()
    s = urllib.request.urlopen(SITE + 'manifest.sig?t=1', timeout=30).read()
    cands.append(('с сайта', m, s))
except Exception as e:
    print('OTA: опубликованный манифест не прочитан:', e)
for why, m, s in cands:
    try:
        if [x[:2] for x in json.loads(m)['files']] == [x[:2] for x in files]:
            publish(m, s, 'файлы не менялись, манифест ' + why)
            sys.exit(0)
    except Exception:
        pass

pem = os.environ.get('OTA_KEY_PEM', '').strip()
if not pem:
    print('OTA: файлы изменились, но секрет OTA_KEY_PEM не задан — Android-приложения остаются на прежней версии')
    sys.exit(0)
with tempfile.NamedTemporaryFile('w', suffix='.pem', delete=False) as k:
    k.write(pem + '\n')
os.environ['OTA_KEY'] = k.name
try:
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import build_ota
    build_ota.main()
finally:
    os.unlink(k.name)
publish(open(os.path.join(ROOT, 'ota/manifest.json'), 'rb').read(), open(os.path.join(ROOT, 'ota/manifest.sig'), 'rb').read(),
        'новая версия подписана')
