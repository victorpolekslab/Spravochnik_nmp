import json,sys,collections
d=json.load(open(sys.argv[1],encoding='utf-8'))
cnt=collections.Counter(); ex={}
def walk(x,p):
    if isinstance(x,dict):
        for k,v in x.items(): walk(v,p+'.'+k)
    elif isinstance(x,list):
        for v in x: walk(v,p+'[]')
    else:
        cnt[p]+=1
        if p not in ex and x not in (None,'',False): ex[p]=str(x)[:70]
for r in d: walk(r,'')
for p,c in sorted(cnt.items()):
    if '_sys' in p or 'subjectAddress' in p or 'communication' in p: continue
    print(c,p,'=',ex.get(p,''))
