global.window = {};
for (const f of ['content_a.js','content_b.js','content_c.js','content_d.js','content_e.js','content_f.js']) require('./' + f);
const out = [];
const isSrc = s => typeof s === 'string' && /^(КР|инстр)/.test(s);
const walk = (o, dis) => {
  if (Array.isArray(o)) {
    if (o.length === 4 && typeof o[1] === 'string' && isSrc(o[3])) { (Array.isArray(o[2]) ? o[2] : [o[2]]).forEach(x => out.push({ dis, n: o[1], d: x.replace(/\*\*/g, ''), src: o[3] })); return; }
    return o.forEach(x => walk(x, dis));
  }
  if (o && typeof o === 'object') {
    if (o.n && o.d) out.push({ dis, n: o.n, d: o.d, src: o.src || '' });
    if (o.combo && o.ex) out.push({ dis, n: o.combo, d: o.ex.replace(/\*\*/g, ''), src: o.src || '' });
    if (o.combo && o.alt) for (const a of o.alt) out.push({ dis, n: o.combo, d: a.replace(/\*\*/g, ''), src: o.src || '' });
    if (o.s && o.drugs === undefined && !o.combo && /\d/.test(o.s) && o.src) out.push({ dis, n: '', d: o.s, src: o.src });
    for (const k of Object.keys(o)) if (typeof o[k] === 'object') walk(o[k], dis);
  }
};
for (const d of window.FELD) walk(d.sections, d.id);
console.log(JSON.stringify(out));
