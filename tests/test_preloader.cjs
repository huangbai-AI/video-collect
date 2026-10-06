const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
let listener,removed,timers=[],tabs=new Map(),creates=0,nextId=1;
const chrome={storage:{session:{get:async()=>({}),set:async()=>{}}},runtime:{onMessageExternal:{addListener(fn){listener=fn}}},windows:{get:async id=>({id}),create:async o=>{const t={id:nextId++,status:'complete',url:o.url};tabs.set(t.id,t);return{id:1,tabs:[t]}},update:async()=>{},onRemoved:{addListener(fn){removed=fn}}},tabs:{get:async id=>{if(!tabs.has(id))throw Error();return tabs.get(id)},create:async o=>{creates++;const t={...o,id:nextId++,status:'complete'};tabs.set(t.id,t);return t},update:async(id,o)=>Object.assign(tabs.get(id),o),remove:async id=>tabs.delete(id)}};
const context=vm.createContext({chrome,URL,setTimeout(fn,ms){assert.equal(ms,7000);timers.push(fn)},console});
vm.runInContext(fs.readFileSync(__dirname+'/../browser-preloader/background.js','utf8'),context);
const send=(message,url='http://127.0.0.1:8799/index.html')=>new Promise(resolve=>listener(message,{url,tab:{id:100}},resolve));
const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve()};
(async()=>{
 assert.equal((await send({action:'hello'},'https://example.com')).ok,false);
 assert.equal((await send({action:'hello'},'http://localhost:9000')).ok,false);
 assert.equal((await send({action:'open',current:'https://x.com/home'})).ok,false);
 const urls=Array.from({length:9},(_,i)=>'https://x.com/demo/status/'+(100+i));
 let s=await send({action:'open',current:urls[0],next:urls.slice(1)});assert.equal(s.total,5);
 for(let i=0;i<5;i++){assert.ok(timers.length);timers.shift()();await flush()}
 s=await send({action:'status'});assert.equal(s.ready,5);assert.equal(tabs.size,6);
 assert.equal([...tabs.values()].filter(t=>t.muted).length,5);
 const before=creates;await send({action:'open',current:urls[1],next:urls.slice(2,7)});
 assert.equal(creates,before);assert.ok(tabs.size<=7);assert.equal([...tabs.values()].find(t=>t.url===urls[1]).muted,false);
 await send({action:'stop'});const count=creates;while(timers.length){timers.shift()();await flush()};assert.equal(creates,count);assert.equal((await send({action:'status'})).total,0);
 removed(1);await flush();assert.equal(vm.runInContext('state.windowId',context),null);
 console.log('来源限制、后5条、7秒间隔、静音、切换复用、停止取消检查通过');
})().catch(e=>{console.error(e);process.exitCode=1});
