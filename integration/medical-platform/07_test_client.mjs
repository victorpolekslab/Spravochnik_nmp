import assert from 'node:assert/strict';
import {test} from 'node:test';
import {randomUUID} from 'node:crypto';
import {client} from './07_client.mjs';
function fixture() {
  let queue=Promise.resolve(), session, requests=0, max=0, refreshes=0;
  const users={one:randomUUID(),two:randomUUID()}, saved=new Map(), written=[];
  const locks={request(_name,fn) {const next=queue.then(fn);queue=next.catch(()=>{});return next;}};
  const store={load:async key=>structuredClone(saved.get(key)||[]),
               save:async (key,rows)=>{saved.set(key,structuredClone(rows));}};
  let send=body=>[200,body], now=10;
  const response=(status,data)=>({status,json:async()=>data});
  const fetcher=async (url,req)=>{
    const body=JSON.parse(req.body);
    if (url.endsWith('/login')) {
      session={user_id:users[body.email],session_id:randomUUID(),access_token:randomUUID(),access_expires_at:300};
      return response(200,session);
    }
    if (url.endsWith('/resume')) return session?response(200,session):response(401,{});
    if (url.endsWith('/refresh')) {
      if (!session || session.user_id!==body.user_id || session.session_id!==body.session_id)
        return response(401,{});
      refreshes++; requests++; max=Math.max(max,requests);
      await new Promise(resolve=>setTimeout(resolve,1));
      requests--;
      return response(200,session);
    }
    if (url.endsWith('/logout')) {session=null;return response(200,{});}
    assert.equal(req.headers.Authorization,'Bearer '+session.access_token);
    written.push(body);
    const [status,data]=send(body);
    return response(status,data);
  };
  const make=()=>client({app:'nmp',fetcher,locks,store,now:()=>now});
  return {make,users,saved,written,setSend:fn=>send=fn,tick:()=>now+=20000,
    max:()=>max,refreshes:()=>refreshes};
}
const attempt=()=>({test_id:'course:gbn',test_version:'v1',attempt_id:randomUUID(),
                     answers:[{question_id:'q1',choice:0}]});
test('lost response preserves immutable payload and resumes across client creation',async()=>{
  const f=fixture(), a=f.make(), body=attempt();
  await a.login('one','synthetic');
  await a.enqueue(body,f.users.one);
  body.answers[0].choice=1;
  f.setSend(()=>{throw Error('network loss');});
  assert.equal((await a.drain())[0].state,'pending');
  const b=f.make();
  await b.login('one','synthetic');
  f.tick();f.setSend(p=>[200,p]);
  assert.deepEqual(await b.drain(),[]);
  assert.equal(f.written.length,2);
  assert.deepEqual(f.written[0],f.written[1]);
  assert.equal(f.written[1].answers[0].choice,0);
});
test('old tab and stale form cannot submit as another account',async()=>{
  const f=fixture(), a=f.make(), b=f.make(), body=attempt();
  await a.login('one','synthetic');await a.enqueue(body,f.users.one);
  await b.login('two','synthetic');
  await assert.rejects(()=>b.enqueue(body,f.users.one),/ACCOUNT_CHANGED/);
  await assert.rejects(()=>a.drain(),/AUTH_REQUIRED/);
  assert.equal(f.written.length,0);
  assert.equal(f.saved.get('queue:nmp:'+f.users.one).length,1);
});
test('expiration refreshes once on 401 and deny preserves row',async()=>{
  const f=fixture(), a=f.make();await a.login('one','synthetic');
  await a.enqueue(attempt(),f.users.one);
  let rejected=false;
  f.setSend(()=>{if (!rejected) {rejected=true;return [401,{}];} return [403,{}];});
  assert.equal((await a.drain())[0].state,'paused_permission');
  assert.equal(f.refreshes(),2);
});
test('shared lock serializes refresh and matching acknowledgement clears one row',async()=>{
  const f=fixture(), a=f.make(), b=f.make();await a.login('one','synthetic');
  assert.equal(await b.resume(),true);
  const body=attempt();
  assert.equal(await a.enqueue(body,f.users.one),true);
  assert.equal(await a.enqueue(body,f.users.one),false);
  f.setSend(()=>[200,{attempt_id:'mismatch'}]);
  await Promise.all([a.drain(),b.drain()]);
  assert.equal(f.max(),1);
  assert.equal(f.written.length,1);
  f.tick();f.setSend(p=>[200,p]);await a.drain();
  assert.equal(f.saved.get('queue:nmp:'+f.users.one).length,0);
});
