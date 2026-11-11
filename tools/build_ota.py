"""Пакет обновления содержимого для Android (без переустановки APK).

   python3 tools/build_ota.py            — новая версия содержимого: ota/manifest.json + ota/manifest.sig,
                                           номер версии записывается в assets/www/ota_version.txt
   Файлы пакета — сами файлы assets/www (их кладёт на сайт workflow), в манифесте — их sha256.
   Подпись — ECDSA P-256 ключом $OTA_KEY (по умолчанию ../keys/ota_ec_private.pem); публичный ключ зашит в Ota.java.
"""
import base64, datetime, hashlib, json, os, re
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WWW = os.path.join(ROOT, 'android/app/src/main/assets/www')
OUT = os.path.join(ROOT, 'ota')
KEY = os.environ.get('OTA_KEY', os.path.join(ROOT, '..', 'keys', 'ota_ec_private.pem'))
MIN_NATIVE = 32          # первая версия APK с механизмом обновления (4.1); поднимать, если новый JS требует нового Java-кода

def main():
    v = int(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5))).strftime('%Y%m%d%H%M'))
    old = 0
    try: old = int(open(os.path.join(WWW, 'ota_version.txt')).read().strip())
    except Exception: pass
    if v <= old: v = old + 1
    open(os.path.join(WWW, 'ota_version.txt'), 'w').write(str(v) + '\n')
    files = []
    for f in sorted(os.listdir(WWW)):
        if f == 'ota_version.txt' or not re.fullmatch(r'[A-Za-z0-9_.-]+', f): continue
        b = open(os.path.join(WWW, f), 'rb').read()
        files.append([f, hashlib.sha256(b).hexdigest(), len(b)])
    app = re.search(r"APP_VERSION = '([^']+)'", open(os.path.join(WWW, 'app.js'), encoding='utf-8').read()).group(1)
    man = json.dumps({'v': v, 'minNative': MIN_NATIVE, 'app': app, 'files': files}, ensure_ascii=False, separators=(',', ':')).encode()
    key = serialization.load_pem_private_key(open(KEY, 'rb').read(), None)
    sig = key.sign(man, ec.ECDSA(hashes.SHA256()))
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, 'manifest.json'), 'wb').write(man)
    open(os.path.join(OUT, 'manifest.sig'), 'w').write(base64.b64encode(sig).decode() + '\n')
    print('ota', v, 'app', app, 'files', len(files), 'size %.0f KB' % (sum(x[2] for x in files) / 1024))

if __name__ == '__main__':
    main()
