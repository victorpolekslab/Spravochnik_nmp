const {test} = require('node:test');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {mkdtemp, rm} = require('node:fs/promises');
const {tmpdir} = require('node:os');
const path = require('node:path');
const {chromium} = require('playwright');

test('Chromium: host cookie, two tabs, durable CryptoKey and cancellation', {timeout:45000}, async () => {
  const server=spawn(process.env.PYTHON || 'python',['-u',path.join(__dirname,'071_browser_fixture.py')],{stdio:['ignore','pipe','inherit']});
  const exited=once(server,'exit');
  const dir=await mkdtemp(path.join(tmpdir(),'medical071-'));
  let browser;
  try {
    const [data]=await Promise.race([once(server.stdout,'data'),exited.then(()=>{throw Error('Fixture exited');})]);
    const origin=data.toString().trim();
    const open=()=>chromium.launchPersistentContext(dir,{executablePath:process.env.CHROMIUM || '/usr/bin/chromium',
      headless:true,args:['--no-sandbox']});
    const make=async context=>{
      const page=await context.newPage();
      await page.goto(origin+'/fixture');
      await page.evaluate(async ()=>{
        const {client,encryptedStore}=await import('/07_client.mjs');
        const store=await encryptedStore(indexedDB,crypto,navigator.locks);
        window.pilot=client({app:'nmp',fetcher:fetch,locks:navigator.locks,store});
        window.store=store;
      });
      return page;
    };
    browser=await open();
    const a=await make(browser), b=await make(browser);
    const uid=await a.evaluate(()=>pilot.login('one@example.invalid','synthetic'));
    const cookies=await browser.cookies();
    assert.equal(cookies.length,1);
    assert.equal(cookies[0].name,'__Host-medical_nmp');
    assert.equal(cookies[0].secure,true);
    assert.equal(cookies[0].httpOnly,true);
    assert.equal(cookies[0].sameSite,'Strict');
    assert.equal(cookies[0].path,'/');
    assert.equal(await a.evaluate(()=>document.cookie),'');
    assert.equal(await b.evaluate(()=>pilot.resume()),true);
    const queue='queue:nmp:'+uid;
    const enqueue=page=>page.evaluate(owner=>pilot.enqueue({test_id:'quiz',test_version:'v1',
      attempt_id:crypto.randomUUID(),answers:[{question_id:'q1',choice:0}]},owner),uid);
    await Promise.all([enqueue(a),enqueue(b)]);
    assert.equal((await a.evaluate(p=>store.load(p),queue)).length,2);
    await browser.close();
    browser=await open();
    const c=await make(browser);
    assert.equal(await c.evaluate(()=>pilot.resume()),true);
    assert.equal((await c.evaluate(p=>store.load(p),queue)).length,2);
    const d=await make(browser);
    assert.equal(await d.evaluate(()=>pilot.resume()),true);
    await c.evaluate(()=>pilot.logout());
    assert.equal((await browser.cookies()).length,0);
    await assert.rejects(d.evaluate(()=>pilot.drain()),/AUTH_REQUIRED/);
    assert.equal((await c.evaluate(p=>store.load(p),queue)).length,2);
    // A committed corrupt snapshot is surfaced and never silently reset.
    await c.evaluate(p=>new Promise((resolve,reject)=>{
      const r=indexedDB.open('medical-learning-pilot-v1');
      r.onsuccess=()=>{
        const tx=r.result.transaction('records','readwrite');
        tx.objectStore('records').put({iv:new Uint8Array(12),data:new Uint8Array(32)},p);
        tx.oncomplete=()=>{r.result.close();resolve();};tx.onerror=()=>reject(tx.error);
      };
      r.onerror=()=>reject(r.error);
    }),queue);
    await assert.rejects(c.evaluate(p=>store.load(p),queue));
  } finally {
    await browser?.close();
    server.kill();
    await exited;
    await rm(dir,{recursive:true,force:true});
  }
});
