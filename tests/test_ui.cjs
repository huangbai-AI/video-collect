// Exercise actual page logic without opening private browser sessions.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '../scripts/unified_library_template.html'), 'utf8');
const code = [...page.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g)].at(-1)[1];
class Element {
  constructor(tag) { this.tag = tag; this.tagName=tag.toUpperCase(); this.children = []; this.value = ''; this.textContent = ''; this.classList = {add(){}, remove(){}}; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute() {}
  removeAttribute(name){delete this[name]}
  getAttribute(name){return this[name]}
  load(){}
  pause(){}
  play(){return Promise.resolve()}
  remove(){}
  replaceWith(other){this.replaced=other}
  addEventListener() {}
  focus() {}
}
const elements = Object.fromEntries([...page.matchAll(/\bid="([^"]+)"/g)].map(m => [m[1], new Element(m[1])]));
for (const id of ['origin','kind','media']) elements[id].value = 'all';
elements.sort.value = 'captured';
const rows = Array.from({length:100}, (_, i) => ({id:String(i), title:'工具 '+i, url:'https://example.com/'+i, month:i<90?'2026-09':'2026-08', platform:'web', platform_label:'网页', origins:['import'], source_names:['导入'], contributors:['示例甲'], kind:'选题', captured_at:'2026-09-30', description:'仅本机正文', author:'作者', keyword:'', likes:null, status:'link', images:[], video:null, poster:null, published_at:''}));
elements.catalog.textContent = JSON.stringify(rows);
const document = {body:new Element("body"),getElementById(id){assert.ok(elements[id], 'missing '+id);return elements[id];}, createElement:tag=>new Element(tag), createTextNode:text=>String(text), addEventListener(){}};
const popupCalls=[],popup={closed:false,opener:'parent',location:{href:''},focus(){}};
const context = vm.createContext({document,URL,window:{location:{href:"http://127.0.0.1:8799/index.html",origin:"http://127.0.0.1:8799"},screen:{availWidth:1440,availHeight:900},open(...args){popupCalls.push(args);return popup},addEventListener(){}},Intl,JSON,console,setTimeout,clearTimeout,setInterval,clearInterval});
vm.runInContext(code, context);
assert.equal(elements.rows.children.length,81); // month separator + first 80 items
elements['show-more'].onclick();
assert.equal(elements.rows.children.length,102);
vm.runInContext("month='2026-08';render()",context);
assert.equal(elements.total.textContent,'10');
assert.equal(elements.rows.children.length,11);
elements.search.value = '工具 99';
vm.runInContext('render()',context);
assert.equal(elements.rows.children.length,2);
const shared = JSON.parse(vm.runInContext('JSON.stringify(shareRows())',context));
assert.equal(shared.length,1);
assert.equal(shared[0].title,'工具 99');
assert.deepEqual(Object.keys(shared[0]).sort(),['title','url','month','platform','origins','contributors','kind'].sort());
elements['clear-filters'].onclick();
assert.equal(elements.total.textContent,'100');
vm.runInContext("items[99].keyword='AI工具';items[99].origins=['search'];byId('origin').value='search';render()",context);
assert.equal(elements.rows.children.length,2);
assert.equal(elements.rows.children[1].children[5].textContent,'AI工具');
elements['clear-filters'].onclick();
vm.runInContext("visible[0].url='https://www.bilibili.com/video/demo0';visible[1].url='https://www.bilibili.com/video/demo1';openPost(visible[0])",context);
assert.equal(popupCalls.length,1);assert.equal(popupCalls[0][1],'video_collect_reference');assert.match(popupCalls[0][2],/popup=yes/);
assert.equal(popup.opener,'parent');assert.equal(popup.location.href,vm.runInContext('visible[0].url',context));
vm.runInContext('shiftPost(1)',context);
assert.equal(popupCalls.length,1);assert.equal(popup.location.href,vm.runInContext('visible[1].url',context));
assert.equal(elements['post-bar'].hidden,false);
elements['post-close'].onclick();assert.equal(elements['post-bar'].hidden,true);
console.log('月份、搜索、分页、关键词列、原帖浮窗复用、共享字段检查通过');

vm.runInContext("viewable=items.slice(0,8);for(const x of viewable){x.status='downloaded';x.video='videos/'+x.id+'.mp4'}index=0;prepareLocalSequence()",context);
assert.equal(vm.runInContext('localPrepared.size',context),5);
assert.equal(vm.runInContext('[...localPrepared.values()].every(v=>v.preload==="auto"&&v.muted)',context),true);
vm.runInContext('index=1;show()',context);
assert.equal(vm.runInContext('video.src',context),'videos/1.mp4');
assert.equal(vm.runInContext('localPrepared.size',context),5);
elements['sequence-preload'].checked=false;elements['sequence-preload'].onchange();
assert.equal(vm.runInContext('localPrepared.size',context),0);
console.log('后5条本地预加载、复用视频、关闭释放检查通过');
vm.runInContext('addSync(items[0]);addSync(items[0])',context);
assert.equal(vm.runInContext('syncQueue.length',context),1);
assert.equal(elements['sync-candidates'].textContent,'同步候选（1）');
vm.runInContext('syncRemote={configured:true,month:"2026-10",target:"https://demo.feishu.cn/docx/demo",synced:[]};renderSync()',context);
assert.equal(elements['sync-list'].children.length,1);
assert.equal(elements['sync-start'].disabled,false);
vm.runInContext('syncRemote.synced=[items[1].id];addSync(items[1])',context);
assert.equal(vm.runInContext('syncQueue.length',context),1);
console.log('候选加入、去重、分类、已同步提示检查通过');

vm.runInContext('selectedSync.add("2");selectedSync.add("3");updateBulk()',context);
assert.equal(elements['bulk-bar'].hidden,false);
assert.equal(elements['bulk-count'].textContent,'已选择 2 条');
assert.equal(elements['select-all'].indeterminate,true);
elements['select-all'].checked=true;elements['select-all'].onchange();
assert.equal(vm.runInContext('selectedSync.size',context),99); // includes unloaded rows, excludes synced item
assert.equal(elements['select-all'].checked,true);
vm.runInContext("month='2026-08';render()",context);
elements['select-all'].checked=false;elements['select-all'].onchange();
assert.equal(vm.runInContext('selectedSync.size',context),89); // other month selections survive
assert.equal(vm.runInContext('selectedSync.has("99")',context),false);
elements['bulk-clear'].onclick();
assert.equal(elements['bulk-bar'].hidden,true);
assert.match(page,/\.bulk-bar\[hidden\]\{display:none\}/);
assert.ok(!page.includes("syncButton.onclick=()=>addSync(x)"));
console.log('多选、未展开条目全选、已同步排除、跨筛选保留与取消选择检查通过');
(async()=>{
 vm.runInContext(`var sentBatches=[];syncApi=async(path,options)=>{if(options){const rows=JSON.parse(options.body).items;sentBatches.push(rows);return {state:'done',results:rows.map(x=>({id:x.id,screenshot:true}))}}return {configured:true,synced:[]}}`,context);
 await vm.runInContext('startSyncRows(Array.from({length:120},(_,i)=>({id:String(i),category:"AI Coding",content:"案例"})))',context);
 assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(sentBatches.map(x=>x.length))',context)),[50,50,20]);
 assert.equal(elements['sync-feedback'].textContent,'已处理 120 条。');
 assert.equal(vm.runInContext('syncBusy',context),false);
 console.log('一次点击分批同步全部120条检查通过');
})().catch(error=>{console.error(error);process.exitCode=1});

assert.match(page, /class="bottom-actions"><aside id="post-bar"/);
assert.match(page, /flex-direction:column;gap:10px/);
assert.match(page, /ResizeObserver\(updateActionSpace\)/);
