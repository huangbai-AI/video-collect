// 小红书 收藏/点赞 采集。在任意 xiaohongshu.com 页面运行；不在自己主页时会自动跳转，返回 rerun。
// 原理：调用页面自己的 pinia user store 的 fetchNotes()（签名由页面完成），不依赖有 bug 的标签切换。
const CFG = { list: 'fav', mode: 'inc', budgetMs: 30000, max: 0, delayMs: 2200, port: 8765, ...(window.__vc_cfg || {}) }; // list: fav|liked ; mode: inc|full ; max: 0=不限
const IDX = { fav: 1, liked: 2 }, SRC = { fav: 'pc_collect', liked: 'pc_like' };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const post = async items => (await (await fetch(`http://127.0.0.1:${CFG.port}/ingest`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ platform: 'xhs', list: CFG.list, items }) })).json());
const run = async () => {
  const challenged = () => /请完成安全验证|请完成验证|访问过于频繁|操作过于频繁|验证码/.test(document.body?.innerText?.slice(0, 500) || '');
  if (challenged()) return { error: 'verification or rate limit shown; stop collection' };
  let me, u;
  for (let k = 0; k < 20 && !(me && u); k++) {
    me = [...document.querySelectorAll('a[href*="/user/profile/"]')].find(a => /我/.test(a.innerText));
    u = document.querySelector('#app')?.__vue_app__?.config.globalProperties.$pinia?._s.get('user');
    if (!(me && u)) await sleep(500);
  }
  if (!u) return { error: 'not logged in or page not ready' };
  if (!me || !location.pathname.startsWith(new URL(me.href).pathname)) {
    if (!me) return { error: 'profile link not found (not logged in?)' };
    location.href = new URL(me.href).pathname + '?tab=' + CFG.list; return { rerun: true, reason: 'navigating to own profile' };
  }
  const i = IDX[CFG.list];
  u.activeTab = { feedType: 0, index: i, key: i, label: CFG.list === 'fav' ? '收藏' : '点赞', lock: false, query: CFG.list };
  const st = (window.__vc_xhs ||= {})[CFG.list] ||= { posted: 0, zero: 0, stall: 0 };
  const t0 = Date.now(); let added = 0, pages = 0;
  const map = n => { const c = n.noteCard || n, id = c.noteId || n.id; const tok = c.xsecToken || n.xsecToken;
    return id && { vid: id, url: `https://www.xiaohongshu.com/explore/${id}` + (tok ? `?xsec_token=${encodeURIComponent(tok)}&xsec_source=${SRC[CFG.list]}` : ''),
      type: c.type, title: c.displayTitle, author: c.user?.nickname || c.user?.nickName, cover: c.cover?.urlDefault || c.cover?.url, likes: c.interactInfo?.likedCount }; };
  while (Date.now() - t0 < CFG.budgetMs) {
    if (challenged()) return { error: 'verification or rate limit shown; stop collection', added, total: st.posted };
    const arr = u.notes[i] || [], len = arr.length;
    if (len > st.posted) {
      const end = CFG.max ? Math.min(len, CFG.max) : len;
      const r = await post(arr.slice(st.posted, end).map(map).filter(Boolean));
      if (!r.ok) return { error: r.error };
      st.posted = end; added += r.new; st.zero = r.new === 0 ? st.zero + 1 : 0;
      if (CFG.mode === 'inc' && st.zero >= 2) return { done: true, reason: 'caught up', added, total: st.posted };
    }
    if (CFG.max && st.posted >= CFG.max) return { done: true, reason: 'max reached', added, total: st.posted };
    if (u.noteQueries[i]?.hasMore === false && len) return { done: true, reason: 'end of list', added, total: st.posted };
    await Promise.race([u.fetchNotes(), sleep(8000)]); pages++; await sleep(Math.max(1800, CFG.delayMs));
    if ((u.notes[i] || []).length === len ? ++st.stall > 4 : (st.stall = 0)) return { done: true, reason: 'no more data', added, total: st.posted };
  }
  return { rerun: true, reason: 'time budget', added, total: st.posted, pages };
};
return await run();
