const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {chromium}=require('playwright');
const port=process.env.MP_A, app=process.env.MP_ANDROID_APP;
const pkg=app==='nmp'?'ru.klinrek.feldsher':'ru.klinrek.terapevt';
const adb=(...args)=>execFileSync('adb',args,{encoding:'utf8',timeout:20000}).trim();
const pause=ms=>new Promise(done=>setTimeout(done,ms));
const origin='http://localhost:'+port;

async function start(){
 adb('shell','am','force-stop',pkg);
 adb('shell','am','start','-W','-n',pkg+'/'+(app==='nmp'?'ru.klinrek.app':'ru.klinrek.terapevt')+'.PilotAuditActivity','--ei','pilotPort',port);
 for(let i=0;i<80;i++){
  try{
   const pid=adb('shell','pidof',pkg).split(/\s+/)[0];
   const debug=adb('forward','tcp:0','localabstract:webview_devtools_remote_'+pid);
   try{
    const endpoint='http://127.0.0.1:'+debug;
    const r=await fetch(endpoint+'/json/list');
    if(r.ok&&(await r.json()).some(x=>x.url.startsWith(origin+'/'))){
     const connection=await chromium.connectOverCDP(endpoint);
     const page=connection.contexts()[0].pages().find(x=>x.url().startsWith(origin+'/'));
     if(page)return {connection,page,debug};
     await connection.close();
    }
   }finally{
    // Keep only the successful binding; the process-specific socket disappears on force-stop.
   }
   adb('forward','--remove','tcp:'+debug);
  }catch{ /* WebView is still launching. */ }
  await pause(250);
 }
 throw Error('Android WebView DevTools target unavailable');
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
  let panel=await panelFor(handle.page);
  assert.ok(await handle.page.evaluate(()=>!window.Native));
  await login(panel,process.env.MP_EMAIL);
  adb('shell','input','keyevent','KEYCODE_HOME');
  await pause(1000);
  await handle.connection.close();
  adb('forward','--remove','tcp:'+handle.debug);
  handle=await start();
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
