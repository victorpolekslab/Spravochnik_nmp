"""Assembles the PWA (web version for iPhone/any browser) from the Android app's web assets.

   python3 build.py   ->  dist/   (upload the contents of dist/ to any static hosting, e.g. GitHub Pages)
"""
import gzip, hashlib, json, os, re, shutil, sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
WWW = os.path.join(HERE, '../android/app/src/main/assets/www')
DB = os.path.join(HERE, '../android/app/src/main/assets/cr.db')
SRC = HERE
VEN = os.path.join(HERE, 'node_modules')
OUT = os.path.join(HERE, 'dist')


def rev(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:10]


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT + '/lib'); os.makedirs(OUT + '/data')
    # shared UI
    content = sorted(f for f in os.listdir(WWW) if re.match(r'content_\w+\.js$', f))
    for f in content + ['app.js', 'app.css']:
        shutil.copy(os.path.join(WWW, f), OUT)
    for f in ['pwa.js', 'pwa.css', 'sw.js', 'manifest.webmanifest']:
        shutil.copy(os.path.join(SRC, f), OUT)
    shutil.copytree(os.path.join(SRC, 'icons'), OUT + '/icons')
    shutil.copy(VEN + '/sql.js/dist/sql-wasm.js', OUT + '/lib/')
    shutil.copy(VEN + '/sql.js/dist/sql-wasm.wasm', OUT + '/lib/')
    shutil.copy(VEN + '/fflate/umd/index.js', OUT + '/lib/fflate.js')
    # database: same as Android, without the (unused) full-text index; gzip for transfer
    tmp = os.path.join(OUT, '..', 'cr_pwa.tmp.db')
    shutil.copy(DB, tmp)
    c = sqlite3.connect(tmp)
    c.execute('DROP TABLE IF EXISTS fts'); c.commit(); c.execute('VACUUM'); c.close()
    with open(tmp, 'rb') as f, gzip.GzipFile(OUT + '/data/cr.db.gz', 'wb', 9, mtime=0) as g:
        g.write(f.read())
    # index.html
    h = open(os.path.join(SRC, 'index.tpl.html'), encoding='utf-8').read()
    h = h.replace('__CONTENT_SCRIPTS__', '\n'.join(f'<script src="{f}?v={rev(os.path.join(OUT, f))}"></script>' for f in content))
    h = (h.replace('__REV_CSS__', rev(OUT + '/app.css')).replace('__REV_PCSS__', rev(OUT + '/pwa.css'))
          .replace('__REV_APP__', rev(OUT + '/app.js')).replace('__REV_PWA__', rev(OUT + '/pwa.js')))
    open(OUT + '/index.html', 'w', encoding='utf-8').write(h)
    open(OUT + '/.nojekyll', 'w').close()
    os.remove(tmp)
    # service worker precache list with per-file revisions
    files = []
    for root, _, fs in os.walk(OUT):
        for f in fs:
            p = os.path.relpath(os.path.join(root, f), OUT).replace(os.sep, '/')
            if p in ('sw.js', '.nojekyll'):
                continue
            files.append([p, rev(os.path.join(root, f))])
    files.sort()
    version = hashlib.sha256(json.dumps(files).encode()).hexdigest()[:12]
    sw = open(OUT + '/sw.js', encoding='utf-8').read()
    sw = sw.replace('__VERSION__', version).replace('__FILES__', json.dumps(files, ensure_ascii=False))
    open(OUT + '/sw.js', 'w', encoding='utf-8').write(sw)
    open(OUT + '/version.json', 'w').write(json.dumps({'version': version}))
    total = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(OUT) for f in fs)
    print('version', version, 'files', len(files), 'size %.1f MB' % (total / 1e6))


if __name__ == '__main__':
    main()
