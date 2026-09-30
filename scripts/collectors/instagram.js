// Instagram 已保存(Saved) 采集。IG 的 CSP 禁止页面连 127.0.0.1，所以本脚本需整段粘贴执行，
// 结果以 {items} 返回，再由 `store.py ingest instagram saved <file>` 入库。
// 原理：用页面登录态读取自己的 saved feed（与网页"已保存"页相同的数据），按 max_id 翻页。
// 增量：CFG.known 传入库里最近的 code（store.py known instagram saved），整页都已知即停。
const CFG = { list: 'saved', max: 300, known: [], budgetMs: 30000, ...(window.__vc_cfg || {}) };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const run = async () => {
  if (location.hostname !== 'www.instagram.com') return { error: 'open https://www.instagram.com/ first' };
  const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
  if (!csrf) return { error: 'not logged in' };
  const h = { 'X-IG-App-ID': '936619743392459', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' };
  const known = new Set(CFG.known), items = [], t0 = Date.now(); let next = null;
  while (Date.now() - t0 < CFG.budgetMs) {
    const r = await fetch('/api/v1/feed/saved/posts/' + (next ? '?max_id=' + encodeURIComponent(next) : ''), { headers: h, credentials: 'include' });
    if (!r.ok) return { error: 'saved feed HTTP ' + r.status, items };
    const j = await r.json();
    const page = (j.items || []).map(x => x.media || x).filter(m => m?.code).map(m => ({
      vid: m.code, url: `https://www.instagram.com/${m.product_type === 'clips' ? 'reel' : 'p'}/${m.code}/`,
      type: m.product_type || String(m.media_type), title: m.caption?.text?.replace(/\s+/g, ' ').slice(0, 120) || null,
      author: m.user?.username, likes: m.like_count ?? null, published_at: m.taken_at ? new Date(m.taken_at * 1000).toISOString().slice(0, 10) : null }));
    const fresh = page.filter(p => !known.has(p.vid));
    items.push(...fresh);
    if (page.length && !fresh.length) return { done: true, reason: 'caught up', items };
    if (items.length >= CFG.max) return { done: true, reason: 'max reached', items };
    if (!j.more_available || !j.next_max_id) return { done: true, reason: 'end of list', items };
    next = j.next_max_id; await sleep(1200);
  }
  return { done: false, reason: 'time budget', items };
};
await run();
