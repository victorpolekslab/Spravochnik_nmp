const id = /^[A-Za-z0-9:_-]{1,128}$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const enc = new TextEncoder();
const dec = new TextDecoder('utf-8', {fatal:true});
const transient = status => status===0 || status===408 || status===429 || status>=500;

function retryAfter(value, now) {
  if (!value) return 0;
  if (/^\d+$/.test(value)) return Number(value)*1000;
  return Math.max(0, Date.parse(value)-now) || 0;
}

function validateRows(rows) {
  if (!Array.isArray(rows) || rows.length>100) throw new Error('STORAGE_CORRUPT');
  for (const row of rows) {
    if (JSON.stringify(canonical(row.body))!==JSON.stringify(row.body) ||
        !Number.isInteger(row.retries) || row.retries<0 || row.retries>5 ||
        !Number.isFinite(row.next) ||
        !['pending','paused_permission','retake','needs_review','paused_retry_budget'].includes(row.state))
      throw new Error('STORAGE_CORRUPT');
  }
  return rows;
}

export function canonical(body) {
  if (!body || ![body.test_id,body.test_version,body.attempt_id].every(v=>typeof v==='string') ||
      !id.test(body.test_id) || !id.test(body.test_version) || !uuid.test(body.attempt_id) ||
      !Array.isArray(body.answers) || body.answers.length < 1 || body.answers.length > 150)
    throw new Error('INVALID_ATTEMPT');
  const answers = body.answers.map(row => {
    if (typeof row.question_id !== 'string' || !id.test(row.question_id) ||
        !Number.isInteger(row.choice) || row.choice < 0 || row.choice > 11)
      throw new Error('INVALID_ANSWER');
    return {question_id: row.question_id, choice: row.choice};
  }).sort((a,b) => a.question_id < b.question_id ? -1 : a.question_id > b.question_id ? 1 : 0);
  if (new Set(answers.map(row => row.question_id)).size !== answers.length) throw new Error('DUPLICATE_QUESTION');
  return {test_id: body.test_id, test_version: body.test_version, attempt_id: body.attempt_id, answers};
}

function tx(db, mode, fn) {
  return new Promise((resolve,reject) => {
    const t = db.transaction('records',mode);
    const req = fn(t.objectStore('records'));
    t.oncomplete = () => resolve(req.result);
    t.onabort = t.onerror = () => reject(t.error || req.error || Error('STORAGE_FAILURE'));
  });
}

export async function encryptedStore(indexedDB, crypto, locks) {
  if (!locks?.request) throw new Error('PILOT_REQUIRES_WEB_LOCKS');
  const db = await new Promise((resolve,reject) => {
    const req=indexedDB.open('medical-learning-pilot-v1',1);
    req.onupgradeneeded=()=>req.result.createObjectStore('records');
    req.onsuccess=()=>resolve(req.result);
    req.onerror=()=>reject(req.error);
    req.onblocked=()=>reject(new Error('STORAGE_BLOCKED'));
  });
  db.onversionchange=()=>db.close();
  const key = await locks.request('medical-pilot-key',async () => {
    const saved=await tx(db,'readonly',s=>s.get('key'));
    if (saved) return saved;
    const count=await tx(db,'readonly',s=>s.count());
    if (count) throw new Error('STORAGE_KEY_MISSING');
    const fresh=await crypto.subtle.generateKey({name:'AES-GCM',length:256},false,['encrypt','decrypt']);
    await tx(db,'readwrite',s=>s.put(fresh,'key'));
    return fresh;
  });
  return {
    close() { db.close(); },
    async load(partition) {
      const value=await tx(db,'readonly',s=>s.get(partition));
      if (!value) return [];
      const clear=await crypto.subtle.decrypt({name:'AES-GCM',iv:value.iv,additionalData:enc.encode(partition)},key,value.data);
      return validateRows(JSON.parse(dec.decode(clear)));
    },
    async save(partition, rows) {
      const iv=crypto.getRandomValues(new Uint8Array(12));
      const data=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:enc.encode(partition)},key,enc.encode(JSON.stringify(rows)));
      await tx(db,'readwrite',s=>s.put({iv,data},partition));
    },
  };
}

export function client({app, fetcher, locks, store, now=Date.now, random=Math.random}) {
  if (!['nmp','terapevt'].includes(app) || !locks?.request) throw new Error('PILOT_REQUIRES_WEB_LOCKS');
  let current;
  const lock = fn => locks.request('medical-pilot-auth-and-queue:'+app,fn);
  const partition = () => {
    if (!current) throw new Error('AUTH_REQUIRED');
    return 'queue:'+app+':'+current.user_id;
  };
  async function call(path, body, access) {
    const headers={'Content-Type':'application/json'};
    if (access) headers.Authorization='Bearer '+access;
    const response=await fetcher('/v1/'+app+'/'+path,{method:'POST',headers,
      credentials:'same-origin',redirect:'error',cache:'no-store',signal:AbortSignal.timeout(12000),
      body:JSON.stringify(body)});
    const data=await response.json().catch(()=>({}));
    return {status:response.status,data,retry:response.headers?.get('Retry-After')};
  }
  function identity() { return {user_id:current.user_id,session_id:current.session_id}; }
  function usable(value) {
    return typeof value.user_id==='string' && uuid.test(value.user_id) &&
      typeof value.session_id==='string' && uuid.test(value.session_id) &&
      typeof value.access_token==='string' && Number.isFinite(value.access_expires_at);
  }
  async function refresh() {
    const expected=identity();
    const {status,data}=await call('auth/refresh',expected);
    if (transient(status)) throw new Error('AUTH_TEMPORARY');
    if (status!==200 || !usable(data) || data.user_id!==expected.user_id || data.session_id!==expected.session_id) {
      current=undefined;
      throw new Error('AUTH_REQUIRED');
    }
    current=data;
  }
  return {
    resume() { return lock(async () => {
      if (current) throw new Error('ALREADY_AUTHENTICATED');
      const {status,data}=await call('auth/resume',{});
      if (transient(status)) throw new Error('AUTH_TEMPORARY');
      if (status!==200 || !usable(data)) return false;
      current=data;
      return true;
    }); },
    login(email,password) { return lock(async () => {
      current=undefined;
      const {status,data}=await call('auth/login',{email,password});
      if (status!==200 || !usable(data)) throw new Error('LOGIN_FAILED');
      current=data;
      return data.user_id;
    }); },
    logout() { return lock(async () => {
      if (!current) throw new Error('AUTH_REQUIRED');
      const {status}=await call('auth/logout',identity());
      if (status!==200 && status!==401) throw new Error('LOGOUT_NOT_CONFIRMED');
      current=undefined;
    }); },
    test(testId) { return lock(async () => {
      if (app!=='nmp' || typeof testId!=='string' || !id.test(testId) || !current) throw new Error('TEST_UNAVAILABLE');
      await refresh();
      const response=await fetcher('/v1/'+app+'/learning/tests/'+encodeURIComponent(testId),{
        headers:{Authorization:'Bearer '+current.access_token},credentials:'same-origin',
        redirect:'error',cache:'no-store',signal:AbortSignal.timeout(12000)});
      if (response.status!==200) throw new Error('TEST_UNAVAILABLE');
      return {test:await response.json(),owner:current.user_id};
    }); },
    enqueue(body, owner) { return lock(async () => {
      const p=partition();
      if (owner!==current.user_id) throw new Error("ACCOUNT_CHANGED");
      const clean=canonical(body), rows=await store.load(p);
      const prior=rows.find(row=>row.body.attempt_id===clean.attempt_id);
      if (prior) {
        if (JSON.stringify(prior.body)!==JSON.stringify(clean)) throw new Error('ATTEMPT_CONFLICT');
        return false;
      }
      if (rows.length>=100) throw new Error('QUEUE_FULL');
      rows.push({body:clean,state:'pending',retries:0,next:0});
      await store.save(p,rows);
      return true;
    }); },
    drain() { return lock(async () => {
      const p=partition(), rows=await store.load(p);
      for (const row of rows.slice()) {
        if (row.state!=='pending' || row.next>now()) continue;
        // Confirm the shared cookie still refers to this tab's authenticated identity.
        await refresh();
        const send=()=>call('learning/attempts',row.body,current.access_token);
        let result;
        try { result=await send(); }
        catch { result={status:0,data:{}}; }
        if (result.status===401) {
          try { await refresh(); result=await send(); }
          catch { break; }
        }
        const {status,data}=result;
        if (status===200 && ['test_id','test_version','attempt_id'].every(k=>data[k]===row.body[k])) {
          rows.splice(rows.indexOf(row),1);
        } else if (status===403) row.state='paused_permission';
        else if (status===409) row.state=data.error==='TEST_VERSION_UNAVAILABLE'?'retake':'needs_review';
        else if (status===401) {current=undefined; break;}
        else if (status===0 || status===200 || status===408 || status===429 || status>=500) {
          row.retries+=1;
          const delay=1000*2**row.retries*(0.75+random()*0.5);
          const serverDelay=retryAfter(result.retry,now());
          row.next=now()+Math.max(delay,Math.min(serverDelay,86_400_000));
          if (serverDelay>86_400_000) row.retries=5;
          if (row.retries>=5) row.state='paused_retry_budget';
        } else row.state='needs_review';
        await store.save(p,rows);
        if (status!==200 || rows.includes(row)) break;
      }
      return rows.map(({body,state})=>({attempt_id:body.attempt_id,state}));
    }); },
  };
}
