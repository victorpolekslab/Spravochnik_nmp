"""Учётные записи раздела «Обучение и опросы».
   python3 tools/learn_users.py add 20 [--prefix f] [--csv путь.csv]   — создать 20 учёток, пароли — в CSV (раздать лично, в репозиторий не класть)
   python3 tools/learn_users.py names список.txt --csv путь.csv         — учётки по ФИО: «Иванов П.А.» (по строке на человека)
   python3 tools/learn_users.py reset "Иванов П.А." --csv путь.csv      — новый пароль
   python3 tools/learn_users.py block "Иванов П.А."                      — отключить
   Логин = фамилия и инициалы; регистр, точки и пробелы при вводе не важны.
   python3 tools/learn_users.py org                                        — пересобрать зашифрованный блок организатора
   Блок организатора (ключ чтения отчёта + список ФИО) шифруется ключом из пароля организатора; исходники —
   вне репозитория: $LEARN_PRIVATE/org.json {admin, pw, readKey} и names.txt (по умолчанию ../learn_private).
   В learn/learn.json хранятся только хэш логина и соль+хэш пароля (2000 итераций SHA-256): ни фамилий, ни паролей в открытом файле нет."""
import argparse, base64, csv, hashlib, json, os, re, secrets, sys
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'learn', 'learn.json')
ALPH = 'abcdefghjkmnpqrstuvwxyz23456789'  # без похожих символов (l/1, o/0)

def h(salt, pw):
    x = hashlib.sha256((salt + ':' + pw).encode()).hexdigest()
    for _ in range(1999):
        x = hashlib.sha256((x + pw).encode()).hexdigest()
    return salt + '$' + x

def norm(login):
    return re.sub(r'[^0-9a-zа-я]', '', login.lower().replace('ё', 'е'))

def ukey(login):
    return hashlib.sha256(('u:' + norm(login)).encode()).hexdigest()[:24]

PRIV = os.environ.get('LEARN_PRIVATE', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'learn_private'))

def derive(salt, pw):
    x = hashlib.sha256((salt + ':' + pw).encode()).hexdigest()
    for _ in range(1999):
        x = hashlib.sha256((x + pw).encode()).hexdigest()
    return x

def org_block(d):
    """Шифрует {readKey, names} ключом из пароля организатора (SHA-256 keystream + MAC; расшифровка — в app.js)."""
    of, nf = os.path.join(PRIV, 'org.json'), os.path.join(PRIV, 'names.txt')
    if not os.path.exists(of): return
    o = json.load(open(of, encoding='utf-8'))
    names = [l.strip() for l in open(nf, encoding='utf-8')] if os.path.exists(nf) else []
    names = [n for n in names if n and ukey(n) in d.get('users', {})]
    if not o.get('salt'):   # постоянная соль: ключ организатора на телефоне остаётся верным при обновлении списка
        o['salt'] = secrets.token_hex(8); json.dump(o, open(of, 'w', encoding='utf-8'), ensure_ascii=False)
    salt, nonce = o['salt'], secrets.token_hex(8); K = derive(salt, o['pw'])
    pt = json.dumps({'readKey': o['readKey'], 'names': names}, ensure_ascii=False).encode()
    ks = b''; i = 0
    while len(ks) < len(pt): ks += hashlib.sha256((K + ':' + nonce + ':' + str(i)).encode()).digest(); i += 1
    ct = base64.b64encode(bytes(x ^ y for x, y in zip(pt, ks))).decode()
    d['org'] = {'k': ukey(o['admin']), 'salt': salt, 'nonce': nonce, 'ct': ct, 'mac': hashlib.sha256((K + ':mac:' + nonce + ':' + ct).encode()).hexdigest()}

def names_edit(add=(), remove=()):
    nf = os.path.join(PRIV, 'names.txt')
    if not os.path.isdir(PRIV): return
    cur = [l.strip() for l in open(nf, encoding='utf-8')] if os.path.exists(nf) else []
    cur = [n for n in cur if n and norm(n) not in {norm(r) for r in remove}]
    for n in add:
        if norm(n) not in {norm(c) for c in cur}: cur.append(n)
    open(nf, 'w', encoding='utf-8').write('\n'.join(cur) + '\n')

def newpw(n=8):
    return ''.join(secrets.choice(ALPH) for _ in range(n))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd'); ap.add_argument('args', nargs='*')
    ap.add_argument('--prefix', default='f'); ap.add_argument('--csv')
    a = ap.parse_args()
    d = json.load(open(P, encoding='utf-8'))
    users = d.setdefault('users', {}); out = []
    if a.cmd == 'add':
        n = int(a.args[0]); i = 1
        while len(out) < n:
            lg = f'{a.prefix}{i:03d}'; i += 1
            if ukey(lg) in users: continue
            pw = newpw(); users[ukey(lg)] = h(secrets.token_hex(8), pw); out.append((lg, pw))
    elif a.cmd in ('names', 'add-named', 'reset'):
        names = [l.strip() for l in open(a.args[0], encoding='utf-8-sig')] if a.cmd == 'names' else a.args
        for lg in filter(None, names):
            lg = re.sub(r'\s+', ' ', lg)
            if a.cmd == 'reset' and ukey(lg) not in users: sys.exit('нет такого логина: ' + lg)
            if a.cmd != 'reset' and ukey(lg) in users: print('уже есть, пропускаю:', lg); continue
            pw = newpw(); users[ukey(lg)] = h(secrets.token_hex(8), pw); out.append((lg, pw))
            if a.cmd != 'reset': names_edit(add=[lg])
    elif a.cmd == 'block':
        for lg in a.args: print('отключён' if users.pop(ukey(lg), None) else 'не найден', lg)
        names_edit(remove=a.args)
    elif a.cmd == 'org':
        pass
    else:
        sys.exit(__doc__)
    org_block(d)
    json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if out:
        if not a.csv: sys.exit('укажите --csv для паролей')
        with open(a.csv, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f, delimiter=';'); w.writerow(['Логин (Фамилия И.О.)', 'Пароль', 'Подстанция'])
            for lg, pw in out: w.writerow([lg, pw, ''])
    print('учёток в списке:', len(users), '; выдано:', len(out))

if __name__ == '__main__':
    main()
