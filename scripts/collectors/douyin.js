// 抖音 喜欢/收藏 采集。在任意 douyin.com 页面运行；不在列表页会自动跳转，返回 rerun。
// 原理：滚动页面真正的滚动容器（非 window），读取 [data-e2e=scroll-list] 内的卡片。
const CFG = { list: 'like', mode: 'inc', budgetMs: 30000, max: 0, delayMs: 2600, port: 8765, ...(window.__vc_cfg || {}) }; // list: like|favorite_collection
const sleep = ms => new Promise(r => setTimeout(r, ms));
const post = async items => (await (await fetch(`http://127.0.0.1:${CFG.port}/ingest`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ platform: 'douyin', list: CFG.list, items }) })).json());
const run = async () => {
  const challenged = () => /请完成安全验证|请完成验证|访问过于频繁|操作过于频繁|验证码/.test(document.body?.innerText?.slice(0, 500) || '');
  if (challenged()) return { error: 'verification or rate limit shown; stop collection' };
  const want = '/user/self?showTab=' + CFG.list;
  if (location.pathname + location.search !== want) { location.href = want; return { rerun: true, reason: 'navigating to list page' }; }
  let list; for (let k = 0; k < 20 && !(list = document.querySelector('[data-e2e="scroll-list"]'))?.querySelector('a[href]'); k++) await sleep(500);
  if (!list) return { error: 'list not found (not logged in / private?)' };
  let sc = list; while (sc && !(sc.scrollHeight > sc.clientHeight + 10 && /auto|scroll/.test(getComputedStyle(sc).overflowY))) sc = sc.parentElement;
  sc ||= document.scrollingElement;
  const st = (window.__vc_dy ||= {})[CFG.list] ||= { seen: new Set(), zero: 0, stall: 0 };
  const t0 = Date.now(); let added = 0;
  while (Date.now() - t0 < CFG.budgetMs) {
    if (challenged()) return { error: 'verification or rate limit shown; stop collection', added, total: st.seen.size };
    const fresh = [];
    list.querySelectorAll('a[href*="/video/"], a[href*="/note/"]').forEach(a => {
      if (CFG.max && st.seen.size >= CFG.max) return;
      const m = a.href.match(/\/(video|note)\/(\d+)/); if (!m || st.seen.has(m[2])) return; st.seen.add(m[2]);
      const card = a.closest('li') || a, lines = card.innerText.split('\n').map(s => s.trim()).filter(Boolean);
      fresh.push({ vid: m[2], url: `https://www.douyin.com/${m[1]}/${m[2]}`, type: m[1], likes: lines[0], title: lines.slice(1).join(' ') || null, cover: card.querySelector('img')?.src });
    });
    if (fresh.length) {
      const r = await post(fresh); if (!r.ok) return { error: r.error };
      added += r.new; st.zero = r.new === 0 ? st.zero + 1 : 0; st.stall = 0;
      if (CFG.mode === 'inc' && st.zero >= 2) return { done: true, reason: 'caught up', added, total: st.seen.size };
      if (CFG.max && st.seen.size >= CFG.max) return { done: true, reason: 'max reached', added, total: st.seen.size };
    } else if (++st.stall >= 6) return { done: true, reason: 'end of list', added, total: st.seen.size };
    sc.scrollTop = sc.scrollHeight; sc.dispatchEvent(new Event('scroll')); await sleep(Math.max(2000, CFG.delayMs));
  }
  return { rerun: true, reason: 'time budget', added, total: st.seen.size };
};
return await run();
