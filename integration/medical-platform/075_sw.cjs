const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createServer}=require('node:http');
const {readFile}=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..'), app=process.env.MEDICAL_UI_APP||'nmp';
const assets=path.join(root,app==='nmp'?'android/app/src/main/assets/www':'web');

test('production SW template: install, update, offline and API bypass',async()=>{
 const html=await readFile(path.join(assets,'index.html'),'utf8');
 const scripts=[...html.matchAll(/<script[^>]+src="([\w.-]+)"/g)].map(x=>x[1]);
 const names=['index.html','app.css',...scripts];
 const template=app==='nmp'?await readFile(path.join(root,'web/sw.js'),'utf8'):
   (await readFile(path.join(root,'tools/build_app.py'),'utf8')).split("SW_JS = r'''")[1].split("'''")[0];
 let version='one', requests=0;
 const server=createServer(async(req,res)=>{
  const name=new URL(req.url,'http://localhost').pathname.slice(1)||'index.html';
  if(name==='sw.js'){
   const files=app==='nmp'?names.map(x=>[x,'verified-fixture']):['./',...names];
   res.writeHead(200,{'Content-Type':'text/javascript','Cache-Control':'no-store'});
   res.end(template.replace('__VERSION__',version).replace('__FILES__',JSON.stringify(files)));
   return;
  }
  if(name.startsWith('v1/')||name.startsWith('pilot/')){
   res.writeHead(200,{'Cache-Control':'no-store'});res.end(String(++requests));return;
  }
  if(!names.includes(name)){res.writeHead(404).end();return;}
  try{
   let body;
   try{body=await readFile(path.join(assets,name));}
   catch(err){
    if(app!=='terapevt'||!name.endsWith('.js'))throw err;
    body=name==='data_meta.js'?'const META={v:"synthetic"};':'';
   }
   res.writeHead(200,{'Content-Type':name.endsWith('.html')?'text/html':name.endsWith('.css')?'text/css':'text/javascript'}).end(body);
  }catch{res.writeHead(404).end();}
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://localhost:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM,headless:true,args:['--no-sandbox']});
 try{
  const context=await browser.newContext();
  await context.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():r.abort());
  const page=await context.newPage();
  await page.goto(origin+'/index.html'+(app==='nmp'?'#learn':'#about'));
  await page.evaluate(async()=>{localStorage.setItem('audit-preserve','yes');await navigator.serviceWorker.register('/sw.js');await navigator.serviceWorker.ready;});
  await page.waitForFunction(()=>navigator.serviceWorker.controller);
  const probe=()=>page.evaluate(async()=>Promise.all(['/v1/cache-probe','/pilot/cache-probe'].map(x=>fetch(x).then(r=>r.text()))));
  assert.notDeepEqual(await probe(),await probe());
  assert.equal(await page.evaluate(async()=>{
    const sets=await Promise.all((await caches.keys()).map(async k=>(await caches.open(k)).keys()));
    return sets.flat().some(x=>/\/(?:v1|pilot)\//.test(x.url));
  }),false);
  const switchVersion=async next=>{
   version=next;
   await page.evaluate(async()=>{const reg=await navigator.serviceWorker.ready;await reg.update();});
   await page.waitForFunction(async()=>!!(await navigator.serviceWorker.ready).waiting);
   await page.evaluate(async()=>{(await navigator.serviceWorker.ready).waiting.postMessage('skipWaiting');});
   await page.waitForFunction(async name=>{
    const keys=await caches.keys();
    return keys.length===1&&keys[0].endsWith(name);
   },next);
  };
  await switchVersion('two');
  await switchVersion('one');
  await context.setOffline(true);
  await page.reload();
  await page.locator('#view').waitFor();
  assert.equal(await page.evaluate(()=>localStorage.getItem('audit-preserve')),'yes');
  await assert.rejects(probe());
  console.log('PWA_REAL_SW PASS '+app+' initial/update/rollback/offline/private-cache-exclusion');
 }finally{await browser.close();server.close();}
});
