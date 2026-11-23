const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {chromium}=require('playwright');
const origin=process.env.MP_ORIGIN, app=process.env.MP_ANDROID_APP;
const url=new URL(origin), port=url.port, tls=url.protocol==='https:';
const pkg=app==='nmp'?'ru.klinrek.feldsher':'ru.klinrek.terapevt';
const adb=(...args)=>execFileSync('adb',args,{encoding:'utf8',timeout:20000}).trim();
const pause=ms=>new Promise(done=>setTimeout(done,ms));


async function start(){
 adb('shell','am','force-stop',pkg);
 const launched=adb('shell','am','start','-W','-n',pkg+'/'+(app==='nmp'?'ru.klinrek.app':'ru.klinrek.terapevt')+'.PilotAuditActivity','--ei','pilotPort',port,'--ez','pilotHttps',String(tls));
 assert.match(launched,/Status: ok/,launched);
 let last;
 for(let i=0;i<40;i++){
  let debug,keep=false;
  try{
   const pid=adb('shell','pidof',pkg).split(/\s+/)[0];
   assert.match(pid,/^\d+$/);
   debug=adb('forward','tcp:0','localabstract:webview_devtools_remote_'+pid);
   const endpoint='http://127.0.0.1:'+debug;
   const response=await fetch(endpoint+'/json/list',{signal:AbortSignal.timeout(1000)});
   const targets=await response.json();
   last=targets.map(({type,url})=>type+' '+new URL(url).origin).join(', ');
   if(targets.some(t=>t.type==='page')){
    const connection=await chromium.connectOverCDP(endpoint,{timeout:3000,noDefaults:true});
    const page=connection.contexts().flatMap(context=>context.pages())[0];
    if(page){
     keep=true;
     await page.waitForURL(url=>url.origin===origin,{timeout:10000});
     return {connection,page,debug};
    }
    await connection.close();
   }
  }catch(error){last=error.message}
  finally{if(debug&&!keep)adb('forward','--remove','tcp:'+debug)}
  await pause(250);
 }
 throw Error('Android WebView DevTools target unavailable: '+last);
}
function traceResume(page, phase) {
 page.on('response',async response=>{
  if (!response.url().endsWith('/auth/resume')) return;
  try {
   const header=await response.request().headerValue('cookie');
   const present=Boolean(header?.split(';').some(part=>part.trim().startsWith('__Host-medical_'+app+'=')));
   console.log('ANDROID_RESUME '+JSON.stringify({phase,status:response.status(),cookieSent:present}));
  } catch {
   console.log('ANDROID_RESUME '+JSON.stringify({phase,status:response.status(),cookieSent:null}));
  }
 });
 page.on('pageerror',()=>console.log('ANDROID_JS_ERROR phase='+phase));
}
async function panelFor(page){
 await page.evaluate(()=>sessionStorage.setItem('medical-platform-pilot','1'));
 await page.reload();
 const panel=page.locator('[data-medical-platform='+app+']');
 await panel.waitFor({timeout:12000});
 return panel;
}
async function login(panel,email){
 await panel.locator('[name=email]').fill(email);
 await panel.locator('[name=password]').fill(process.env.MP_PASSWORD);
 await panel.getByRole('button',{name:'Войти',exact:true}).click();
 await panel.getByText('Вход выполнен.').waitFor({timeout:10000});
}
async function main(){
 adb('reverse','tcp:'+port,'tcp:'+port);
 let handle;
 try{
  handle=await start();
  traceResume(handle.page,'initial');
  let panel=await panelFor(handle.page);
  assert.ok(await handle.page.evaluate(()=>!window.Native && typeof window.App?.krUpload !== 'function'));
  await login(panel,process.env.MP_EMAIL);
  const status=await handle.page.evaluate(app=>fetch('/v1/'+app+'/auth/resume',{
   method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:'{}'
  }).then(r=>r.status),app);
  console.log('ANDROID_CONTROL tls='+tls+' resume='+status);
  if(process.env.MP_HTTP_CONTROL==='1') return;
  assert.equal(status,200);
  adb('shell','input','keyevent','KEYCODE_HOME');
  await pause(1000);
  await handle.connection.close();
  adb('forward','--remove','tcp:'+handle.debug);
  handle=await start();
  traceResume(handle.page,'after-force-stop');
  panel=await panelFor(handle.page);
  await panel.getByText('Сессия восстановлена.').waitFor({timeout:10000});
  if(app==='nmp'){
   await panel.locator('[name=test]').fill('quiz');
   await panel.getByRole('button',{name:'Загрузить'}).click();
   await panel.locator('input[name=q1][value="1"]').check({timeout:10000});
   await panel.locator('input[name=q2][value="0"]').check();
   await panel.getByRole('button',{name:'Сохранить попытку'}).click();
   await panel.getByText('Попытка сохранена на устройстве.').waitFor();
   await panel.getByRole('button',{name:'Синхронизировать'}).click();
   await panel.getByText('Результат: 2 / 2 · зачёт').waitFor({timeout:10000});
  }
  await panel.getByRole('button',{name:'Выйти'}).click();
  await panel.getByText('Вы вышли.').waitFor({timeout:10000});
  const revoked=await handle.page.evaluate(app=>fetch('/v1/'+app+'/auth/resume',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.status),app);
  assert.equal(revoked,401);
  console.log('ANDROID_WEBVIEW_E2E PASS '+app+' documented opt-in, login, process restart/resume, logout'+(app==='nmp'?', server score':''));
 } finally {
  if(handle){
   await handle.connection.close().catch(()=>{});
   adb('forward','--remove','tcp:'+handle.debug);
  }
  adb('reverse','--remove','tcp:'+port);
 }
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
