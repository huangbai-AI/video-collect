// Exercise actual page logic without opening private browser sessions.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '../scripts/unified_library_template.html'), 'utf8');
const code = [...page.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g)].at(-1)[1];
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ''; this.textContent = ''; this.classList = {add(){}, remove(){}}; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute() {}
  addEventListener() {}
  focus() {}
}
const elements = Object.fromEntries([...page.matchAll(/\bid="([^"]+)"/g)].map(m => [m[1], new Element(m[1])]));
for (const id of ['origin','kind','media']) elements[id].value = 'all';
elements.sort.value = 'captured';
const rows = Array.from({length:100}, (_, i) => ({id:String(i), title:'工具 '+i, url:'https://example.com/'+i, month:i<90?'2026-09':'2026-08', platform:'web', platform_label:'网页', origins:['import'], source_names:['导入'], contributors:['示例甲'], kind:'选题', captured_at:'2026-09-30', description:'仅本机正文', author:'作者', keyword:'', likes:null, status:'link', images:[], video:null, poster:null, published_at:''}));
elements.catalog.textContent = JSON.stringify(rows);
const document = {getElementById(id){assert.ok(elements[id], 'missing '+id);return elements[id];}, createElement:tag=>new Element(tag), createTextNode:text=>String(text), addEventListener(){}};
const popupCalls=[],popup={closed:false,opener:'parent',location:{href:''},focus(){}};
const context = vm.createContext({document,URL,window:{screen:{availWidth:1440,availHeight:900},open(...args){popupCalls.push(args);return popup},addEventListener(){}},Intl,JSON,console,setTimeout,clearTimeout});
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
