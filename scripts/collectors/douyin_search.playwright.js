async page => {
const risk=async()=>/验证码中间页/.test(await page.title())||/请完成下列验证|拖动完成上方拼图|接收短信验证码|扫码登录|验证码登录/.test(await page.locator('body').innerText());
if(await risk())return {blocked:true};
const kw=__KEYWORD__;
{
 await page.getByRole('textbox',{name:'搜索你感兴趣的内容'}).fill(kw);
 await page.getByRole('textbox',{name:'搜索你感兴趣的内容'}).press('Enter');
 await page.waitForTimeout(4000);
 if(await risk())return {blocked:true};
 await page.locator('span[data-key="video"]').click();
 await page.waitForTimeout(2000);
}
await page.locator('.StjIHdE0').hover();
await page.getByText('最多点赞',{exact:true}).click();
await page.waitForTimeout(1500);
await page.locator('.StjIHdE0').hover();
await page.getByText('一周内',{exact:true}).click();
await page.waitForTimeout(3000);
if(await risk())return {blocked:true};
await page.locator('.StjIHdE0').hover();
const sort=await page.getByText('最多点赞',{exact:true}).evaluate(e=>e.outerHTML);
const week=await page.getByText('一周内',{exact:true}).evaluate(e=>e.outerHTML);
if(!sort.includes('HjptjtzN')||!week.includes('HjptjtzN'))return {filter_failed:true,sort,week};
const rows=new Map();
for(let pass=0;pass<3;pass++){
 const found=await page.locator('a[href]').evaluateAll(es=>es.filter(e=>/\/video\/\d+/.test(e.href)).map(e=>({url:e.href,text:e.innerText})));
 for(const x of found)if(x.text.trim())rows.set(x.url,x);
 if(rows.size>=20||!found.length)break;
 await page.mouse.wheel(0,1200);await page.waitForTimeout(2500);
 if(await risk())return {blocked:true};
}
return {keyword:kw,sort,week,url:page.url(),items:[...rows.values()].slice(0,20)};
}
