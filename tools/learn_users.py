"""Учётные записи раздела «Обучение и опросы».
   python3 tools/learn_users.py add 20 [--prefix f] [--csv путь.csv]   — создать 20 учёток, пароли — в CSV (раздать лично, в репозиторий не класть)
   python3 tools/learn_users.py names список.txt --csv путь.csv         — учётки по ФИО: «Иванов П.А.» (по строке на человека)
   python3 tools/learn_users.py reset "Иванов П.А." --csv путь.csv      — новый пароль
   python3 tools/learn_users.py block "Иванов П.А."                      — отключить
   Логин = фамилия и инициалы; регистр, точки и пробелы при вводе не важны.
   В learn/learn.json хранятся только хэш логина и соль+хэш пароля (2000 итераций SHA-256): ни фамилий, ни паролей в открытом файле нет."""
import argparse, csv, hashlib, json, os, re, secrets, sys
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
    elif a.cmd == 'block':
        for lg in a.args: print('отключён' if users.pop(ukey(lg), None) else 'не найден', lg)
    else:
        sys.exit(__doc__)
    json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if out:
        if not a.csv: sys.exit('укажите --csv для паролей')
        with open(a.csv, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f, delimiter=';'); w.writerow(['Логин (Фамилия И.О.)', 'Пароль', 'Подстанция'])
            for lg, pw in out: w.writerow([lg, pw, ''])
    print('учёток в списке:', len(users), '; выдано:', len(out))

if __name__ == '__main__':
    main()
