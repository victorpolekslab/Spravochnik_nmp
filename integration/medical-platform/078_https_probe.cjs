const {chromium}=require('playwright');
const assert=require('node:assert/strict');

(async()=>{
  const [url,expected,profile,pin]=process.argv.slice(2);
  const context=await chromium.launchPersistentContext(profile,{
    executablePath:process.env.CHROMIUM||undefined,
    args:['--no-proxy-server','--host-resolver-rules=MAP *.test 127.0.0.1',
          '--ignore-certificate-errors-spki-list='+pin],
  });
  try {
    const page=context.pages()[0];
    await page.goto(url);
    const result=page.locator('body');
    await page.waitForFunction(()=>['allowed','denied'].includes(document.body.dataset.result));
    assert.equal(await result.getAttribute('data-result'),expected);
  } finally {
    await context.close();
  }
})().catch(error=>{console.error(error.message);process.exitCode=1;});
