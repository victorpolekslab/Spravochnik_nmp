"""Скачивает файл из реестра ЕАЭС (ОП-26) по oid записи и пути файла."""
import json, sys, time, urllib.request, urllib.parse
PLAT = 'https://pharma.eaeunion.org/platformsvc/nonauthorizedplatform'
PROC = '5f9495fb-6dd8-43b5-aa74-1e44cf219130'
PROXY = '/cdb/public/api/registry/P.MM.01/drug-monitoring-items/'

def req(url, data=None, raw=False, tries=4):
    for i in range(tries):
        try:
            r = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'} if data else {})
            with urllib.request.urlopen(r, timeout=60) as f:
                b = f.read()
                return b if raw else json.loads(b)
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(2 * (i + 1))

def get_file(oid, path):
    body = json.dumps({'uri': PROXY + oid + '/files?file=' + path, 'gp': 'g'}).encode()
    j = req(f'{PLAT}/executewithjson?jobid={PROC}&operation=update', body)
    inst = j['instanceid'] if isinstance(j, dict) else j
    for _ in range(120):
        s = req(f'{PLAT}/status?instanceid={inst}')
        if s.get('status') != 2: break
        time.sleep(0.5)
    t = req(f'{PLAT}/gettoken?instanceid={inst}')
    fid = [p.get('stringvalue') for p in t.get('parameters', []) if p.get('name') == 'fileid']
    if not fid: raise RuntimeError('no fileid: ' + json.dumps(t)[:300])
    return req(f'{PLAT}/filedownload?id={fid[-1]}&instanceid={inst}', raw=True)

if __name__ == '__main__':
    b = get_file(sys.argv[1], sys.argv[2]); open(sys.argv[3], 'wb').write(b); print(len(b))
