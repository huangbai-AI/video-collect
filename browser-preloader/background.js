// Only the local library can ask to prepare known social post pages.
const LIMIT=5, GAP=7000;
let state={windowId:null,owner:null,current:null,previous:null,tabs:{},planned:[]},generation=0,queue=Promise.resolve();
const initialized=chrome.storage.session.get('cache').then(v=>{if(v.cache)state=v.cache});
function allowedSender(sender){try{const u=new URL(sender.url);return ['127.0.0.1','localhost'].includes(u.hostname)&&u.protocol==='http:'&&u.port==='8799'}catch{return false}}
function allowedPost(value){try{const u=new URL(value);if(u.protocol!=='https:')return false;const h=u.hostname.replace(/^www\./,'');return [
 ['instagram.com',/^\/(p|reel|reels)\/[\w-]+\/?$/],['x.com',/^\/[^/]+\/status\/\d+\/?$/],['twitter.com',/^\/[^/]+\/status\/\d+\/?$/],
 ['xiaohongshu.com',/^\/(?:explore\/[\w]+|discovery\/item\/[\w]+|user\/profile\/[0-9a-f]{24}\/[0-9a-f]{24})\/?$/],
 ['douyin.com',/^\/(video|note)\/\d+\/?$/],['tiktok.com',/^\/@[^/]+\/video\/\d+\/?$/],['bilibili.com',/^\/video\/[\w]+\/?$/],
 ['youtube.com',/^\/(shorts\/[\w-]+|watch)\/?$/]
 ].some(([host,path])=>host===h&&path.test(u.pathname))}catch{return false}}
const save=()=>chrome.storage.session.set({cache:state});
async function getTab(url){const id=state.tabs[url];if(!id)return null;try{return await chrome.tabs.get(id)}catch{delete state.tabs[url];return null}}
async function ensureWindow(url){try{if(state.windowId)await chrome.windows.get(state.windowId);else throw Error()}catch{
 const w=await chrome.windows.create({url,type:'popup',width:1280,height:900,focused:true});state.windowId=w.id;state.tabs={};state.tabs[url]=w.tabs[0].id;await save();
}}
async function prepare(url){let tab=await getTab(url);if(!tab){tab=await chrome.tabs.create({windowId:state.windowId,url,active:false});state.tabs[url]=tab.id;await chrome.tabs.update(tab.id,{muted:true});await save()}return tab}
async function snapshot(){let ready=0,pending=0;for(const url of state.planned){const t=await getTab(url);if(t?.status==='complete')ready++;else pending++}return {ok:true,ready,pending,total:state.planned.length,limit:LIMIT}}
async function warm(version){for(const url of [...state.planned]){await new Promise(r=>setTimeout(r,GAP));if(version!==generation||!state.windowId)return;try{const tab=await prepare(url);if(version!==generation&&!new Set([state.current,state.previous,...state.planned]).has(url)){await chrome.tabs.remove(tab.id);delete state.tabs[url];await save()}}catch{return}}}
async function open(message,sender){await initialized;
 if(!allowedPost(message.current))throw Error('仅支持社媒帖子');
 const urls=[...new Set((message.next||[]).filter(allowedPost))].filter(u=>u!==message.current).slice(0,LIMIT);
 generation++;const version=generation;
 // Different library pages share one small, bounded browsing window.
 state.previous=state.current;state.current=message.current;state.owner=sender.tab?.id;state.planned=urls;
 await ensureWindow(message.current);const current=await prepare(message.current);
 for(const [url,id] of Object.entries(state.tabs)){if(url===message.current)continue;try{await chrome.tabs.update(id,{muted:true})}catch{}}
 await chrome.tabs.update(current.id,{active:true,muted:false});await chrome.windows.update(state.windowId,{focused:true});
 const keep=new Set([state.current,state.previous,...urls]);for(const [url,id] of Object.entries(state.tabs)){if(!keep.has(url)){try{await chrome.tabs.remove(id)}catch{}delete state.tabs[url]}}
 await save();void warm(version);return snapshot();
}
chrome.runtime.onMessageExternal.addListener((message,sender,reply)=>{
 if(!allowedSender(sender)){reply({ok:false,error:'仅允许本机资料库使用'});return false}
 if(message?.action==='hello'){reply({ok:true,limit:LIMIT});return false}
 if(message?.action==='status'){initialized.then(snapshot).then(reply).catch(()=>reply({ok:false}));return true}
 if(message?.action==='open'){queue=queue.catch(()=>{}).then(()=>open(message,sender));queue.then(reply).catch(e=>reply({ok:false,error:e.message}));return true}
 if(message?.action==='stop'){queue=queue.catch(()=>{}).then(async()=>{await initialized;generation++;state.planned=[];await save();return {ok:true}});queue.then(reply).catch(()=>reply({ok:false}));return true}
 reply({ok:false,error:'未知操作'});return false;
});
chrome.windows.onRemoved.addListener(id=>{if(state.windowId===id){generation++;state={windowId:null,owner:null,current:null,previous:null,tabs:{},planned:[]};void save()}});
