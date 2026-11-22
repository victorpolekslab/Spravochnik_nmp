const assert=require('node:assert/strict');
const { chromium }=require('playwright');

async function main(){
 const origin='http://localhost:'+process.env.MP_A, second='http://localhost:'+process.env.MP_B;
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM,headless:true,args:['--no-sandbox']});
 try{
  const context=await browser.newContext({serviceWorkers:'block'});
  await context.route('**/*',r=>[origin,second].some(x=>r.request().url().startsWith(x+'/'))?r.continue():r.abort());
  const page=await context.newPage();
  await page.goto(origin+'/#learn');
  await page.evaluate(()=>sessionStorage.setItem('medical-platform-pilot','1'));
  await page.reload();
  const panel=page.locator('[data-medical-platform=nmp]');
  const login=async email=>{
   const done=page.waitForResponse(r=>r.url().endsWith('/auth/login'));
   await panel.locator('[name=email]').fill(email);
   await panel.locator('[name=password]').fill(process.env.MP_PASSWORD);
   await panel.getByRole('button',{name:'Войти',exact:true}).click();
   const response=await done;
   assert.equal(response.status(),200);
   await panel.getByText('Вход выполнен.').waitFor();
   return response.json();
  };
  const first=await login(process.env.MP_EMAIL);
  async function call(tab,url,token,data){
   return tab.evaluate(async ({url,token,data})=>{
    const headers={};
    if(token)headers.Authorization=token;
    if(data)headers['Content-Type']='application/json';
    const res=await fetch(url,{headers,method:data?'POST':'GET',body:data?JSON.stringify(data):undefined});
    return {status:res.status, body:await res.json()};
   },{url,token,data});
  }
  const alternate=await context.newPage();
  await alternate.goto(second);
  const shared=await call(alternate,'/v1/nmp/auth/resume',null,{});
  assert.equal(shared.status,200);
  assert.ok(shared.body.session_id===first.session_id);
  await panel.locator('[name=test]').fill('quiz');
  await panel.getByRole('button',{name:'Загрузить'}).click();
  await panel.locator('input[name=q1][value="1"]').check();
  await panel.locator('input[name=q2][value="0"]').check();
  await panel.getByRole('button',{name:'Сохранить попытку'}).click();
  await panel.getByText('Попытка сохранена на устройстве.').waitFor();
  const ack=page.waitForResponse(r=>r.url().endsWith('/learning/attempts')&&r.request().method()==='POST');
  await panel.getByRole('button',{name:'Синхронизировать'}).click();
  const response=await ack;
  assert.equal(response.status(),200);
  const body=response.request().postDataJSON();
  const authorization=(await response.request().allHeaders()).authorization;
  await panel.getByText('Результат: 2 / 2 · зачёт').waitFor();
  const endpoint=origin+'/v1/nmp/learning/attempts';
  const get=token=>call(page,endpoint,token);
  const results=await get(authorization);
  assert.equal(results.status,200);
  assert.equal(results.body.items[0].score,2);
  const send=data=>call(page,endpoint,authorization,data);
  assert.equal((await send(body)).status,200);
  const changed=structuredClone(body);changed.answers[0].choice^=1;
  assert.equal((await send(changed)).status,409);
  const other=await login(process.env.MP_SECOND);
  assert.equal((await get(authorization)).status,401);
  const own=await get('Bearer '+other.access_token);
  assert.equal(own.status,200);
  assert.equal(own.body.items.length,0);
  console.log('FULL_E2E_NMP PASS login; shared worker; UI=2/2; replay=200; conflict=409; stale bearer=401; second user attempts=0');
 }finally{await browser.close();}
}
main().catch(err=>{console.error(err.message);process.exitCode=1;});
