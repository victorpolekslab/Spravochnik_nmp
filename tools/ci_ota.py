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

def verify(man, sig_b64):
    """Подпись должна проверяться ключом, зашитым в приложение (Ota.java), иначе телефоны её отвергнут."""
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    src = open(os.path.join(ROOT, 'android/app/src/main/java/ru/klinrek/app/Ota.java'), encoding='utf-8').read()
    pub = serialization.load_der_public_key(base64.b64decode(re.search(r'PUBKEY = "([^"]+)"', src).group(1)))
    try:
        pub.verify(base64.b64decode(sig_b64), man, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False

def publish(man, sig, why):
    open(os.path.join(out, 'manifest.json'), 'wb').write(man)
    open(os.path.join(out, 'manifest.sig'), 'wb').write(sig)
    print('OTA:', why, json.loads(man)['v'])

def check_secret():
    """Сразу сообщает, подходит ли ключ из секрета к приложению (сравнение открытых ключей)."""
    pem = os.environ.get('OTA_KEY_PEM', '').strip()
    if not pem:
        return
    import base64
    from cryptography.hazmat.primitives import serialization
    try:
        mine = serialization.load_pem_private_key(pem.encode() + b'\n', None).public_key()
        src = open(os.path.join(ROOT, 'android/app/src/main/java/ru/klinrek/app/Ota.java'), encoding='utf-8').read()
        app = serialization.load_der_public_key(base64.b64decode(re.search(r'PUBKEY = "([^"]+)"', src).group(1)))
        fmt = (serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        print('OTA: ключ в секрете подходит к приложению' if mine.public_bytes(*fmt) == app.public_bytes(*fmt)
              else '::error::OTA: ключ в секрете OTA_KEY_PEM не подходит к приложению — замените секрет')
    except Exception as e:
        print('::error::OTA: секрет OTA_KEY_PEM не читается как закрытый ключ PEM:', type(e).__name__)

check_secret()
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
man, sig = open(os.path.join(ROOT, 'ota/manifest.json'), 'rb').read(), open(os.path.join(ROOT, 'ota/manifest.sig'), 'rb').read()
if not verify(man, sig):
    print('::error::Подпись не совпадает с ключом в приложении (Ota.java): в секрет OTA_KEY_PEM вставлен не тот ключ. '
          'Обновление для Android не опубликовано, телефоны остаются на прежней версии.')
    sys.exit(1)
publish(man, sig, 'новая версия подписана и проверена ключом приложения')
