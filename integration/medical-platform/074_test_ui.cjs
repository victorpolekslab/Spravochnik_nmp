const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createServer}=require('node:http');
const {randomUUID}=require('node:crypto');
const {readFile}=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require('playwright');

const root=path.resolve(__dirname,'../..');
const app=process.env.MEDICAL_UI_APP || 'nmp';
const dir=path.join(root,app==='nmp'?'android/app/src/main/assets/www':'web');
const target=app==='nmp'?'#learn':'#about';

test('actual application route: default off, embedded opt-in and auth', {timeout:45000},async()=>{
 const uid=randomUUID(), sessions=new Map(), stored=new Map();
 const get=async res=>Buffer.concat(await Array.fromAsync(res)).toString();
 let posts=0, dropAck=true, legacyPosts=0;
 const send=(res,status,data)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
 const server=createServer(async(req,res)=>{
  try{
   const url=new URL(req.url,'http://localhost');
   const part=url.pathname;
   const current=sessions.get(req.headers.cookie?.split('=')[1]);
   if(part===`/v1/${app}/auth/login`){
    const body=JSON.parse(await get(req));
    if(body.password!=='fixture'){ send(res,401,{});return; }
    const handle=randomUUID(), pair={user_id:uid,session_id:randomUUID(),access_token:randomUUID(),access_expires_at:9999999999};
    sessions.set(handle,pair);
    res.setHeader('Set-Cookie',`__Host-medical_${app}=${handle}; Path=/; Secure; HttpOnly; SameSite=Strict`);
    send(res,200,pair);return;
   }
   if(part.startsWith(`/v1/${app}/auth/`)){
    if(!current){send(res,401,{});return;}
    const body=JSON.parse(await get(req));
    if(!part.endsWith('/resume')&&(body.user_id!==current.user_id || body.session_id!==current.session_id)){
     send(res,401,{});return;
    }
    if(part.endsWith('/logout')){
     sessions.delete(req.headers.cookie.split('=')[1]);
     res.setHeader('Set-Cookie',`__Host-medical_${app}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0`);
     send(res,200,{});return;
    }
    send(res,200,current);return;
   }
   if(part.startsWith('/v1/nmp/learning/')){
    if(req.headers.authorization!==('Bearer '+current?.access_token)){send(res,401,{});return;}
    if(req.method==='GET'){
     send(res,200,{test_id:'course:gbn',test_version:'fixture-v1',questions:[{question_id:'q1',prompt:'<b>Вопрос</b>',options:['A','B']}]});return;
    }
    const body=JSON.parse(await get(req));
    assert.deepEqual(Object.keys(body).sort(),['answers','attempt_id','test_id','test_version']);
    posts++;
    if(stored.has(body.attempt_id))assert.deepEqual(stored.get(body.attempt_id),body);
    else stored.set(body.attempt_id,body);
    if(dropAck){dropAck=false;req.socket.destroy();return;}
    send(res,200,body);return;
   }
   const fixed=part==='/'?'index.html':part.slice(1);
   const fromPilot=fixed.startsWith('pilot/');
   if(!/^(?:pilot\/)?[\w.-]+$/.test(fixed)){res.writeHead(404).end();return;}
   if(app==='terapevt'&&fixed==='data_meta.js'){
    res.writeHead(200,{'Content-Type':'text/javascript'}).end('const META={v:"synthetic"};');return;
   }
   const data=await readFile(path.join(fromPilot?__dirname:dir,fromPilot?fixed.slice(6):fixed));
   res.writeHead(200,{'Content-Type':fixed.endsWith('.html')?'text/html':fixed.endsWith('.css')?'text/css':'text/javascript'}).end(data);
  }catch{if(!res.headersSent)res.writeHead(404);res.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://localhost:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const context=await browser.newContext({serviceWorkers:'block'});
  await context.route('**/*',route=>{
   if(route.request().url().startsWith(origin+'/'))return route.continue();
   if(route.request().method()==='POST')legacyPosts++;
   return route.abort();
  });
  const page=await context.newPage();
  page.on('pageerror',error=>console.error('pageerror:',error.message));
  await page.goto(origin+'/'+target);
  assert.equal(await page.locator('[data-medical-platform]').count(),0);
  await page.evaluate(()=>sessionStorage.setItem('medical-platform-pilot','1'));
  await page.reload();
  const panel=page.locator('[data-medical-platform='+app+']');
  await panel.waitFor();
  await panel.locator('[name=email]').fill('fixture@example.invalid');
  await panel.locator('[name=password]').fill('fixture');
  await panel.getByRole('button',{name:'Войти',exact:true}).click();
  await panel.getByText('Вход выполнен.').waitFor();
  await page.reload();
  await panel.getByText('Сессия восстановлена.').waitFor();
  if(app==='nmp'){
   assert.ok(await page.locator('#lLogin').isVisible());
   await panel.getByRole('button',{name:'Загрузить'}).click();
   await panel.getByText('<b>Вопрос</b>',{exact:true}).waitFor();
   await panel.locator('input[type=radio]').first().check();
   await context.setOffline(true);
   await panel.getByRole('button',{name:'Сохранить попытку'}).click();
   await panel.getByText('Попытка сохранена на устройстве.').waitFor();
   assert.equal(posts,0);
   await context.setOffline(false);
   for(let i=0;i<25 && posts<1;i++)await new Promise(resolve=>setTimeout(resolve,100));
   assert.equal(posts,1);
   await new Promise(resolve=>setTimeout(resolve,2700));
   await panel.getByRole('button',{name:'Синхронизировать'}).click();
   await panel.getByText('Очередь пуста.').waitFor();
   assert.equal(posts,2); assert.equal(stored.size,1);assert.equal(legacyPosts,0);
  } else assert.equal(await panel.locator('[data-load]').count(),0);
  await panel.getByRole('button',{name:'Выйти'}).click();
  await panel.getByText('Вы вышли.').waitFor();
  await panel.getByRole('button',{name:'Отключить пилот'}).click();
  await panel.waitFor({state:'detached'});
 }finally{await browser.close();server.close();}
});
