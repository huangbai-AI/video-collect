---
name: video-collect
description: 从自己在抖音、小红书、Instagram、X 的点赞或收藏列表收集视频与图文链接，增量去重，导出新增记录，并生成可筛选的本地选题网页。用户要求同步点赞、收藏或更新选题库时使用。
---

# Video Collect

本技能把**自己账号**的点赞和收藏内容收进本地资料库。拿到可打开的帖子链接就算完成链接采集；只有确实下载了媒体文件，网页才标为可离线播放。默认不下载全部媒体。

## 准备

项目目录就是本文件所在目录。`scripts/store.py` 使用 Python 标准库，默认把数据库和导出文件放在 `~/.local/share/video-collect/`；可用 `VC_DATA_DIR` 改位置。数据目录不要提交到 Git。

在已登录的平台浏览器中操作。只读取自己的列表，不点赞、不取消点赞、不发消息、不代替用户登录。页面出现验证码、访问频繁或登录异常时停止。对可能触发风控的批量搜索，应使用用户另外提供的小号浏览器。

启动接收器：

```bash
sh scripts/start.sh
```

## 采集列表

- **抖音**：打开 `https://www.douyin.com/user/self?showTab=like`，运行 `scripts/collectors/douyin.js`；收藏使用 `window.__vc_cfg={list:'favorite_collection'}` 后运行同一脚本。脚本可能返回 `rerun:true`，等待页面加载后重复执行。
- **小红书**：打开 `https://www.xiaohongshu.com/explore`，运行 `scripts/collectors/xhs.js`；收藏为默认 `fav`，点赞设 `window.__vc_cfg={list:'liked'}`。`type: normal` 图文与视频都收。脚本使用页面自己的列表加载过程；页面结构变化时先核实，不高频重试。
- **Instagram 已保存**：打开已登录的 `https://www.instagram.com/`，把 `scripts/collectors/instagram.js` 整段在页面执行。其返回值中的 `items` 保存为本地 JSON，再运行 `python3 scripts/store.py ingest instagram saved items.json`。部分浏览器限制页面访问本地接收器，因此这里经 JSON 文件入库。
- **Instagram 点赞**：打开 `https://www.instagram.com/your_activity/interactions/likes/`。从已渲染的视频卡片读取 `aria-label` 与图片 URL 的 `ig_cache_key`，保存为 JSON 数组，运行 `python3 scripts/instagram_likes_from_dom.py raw.json > items.json`，再运行 `python3 scripts/store.py ingest instagram liked items.json`。需抽样点开卡片核对生成链接；加载圈未结束时只能报告已抓到的部分。
- **X 点赞**：打开 `https://x.com/i/history/likes`，只收可确认的视频帖链接。把 `{vid,url,title,author,likes}` 条目写成 JSON 数组，再运行 `python3 scripts/store.py ingest x liked items.json`。X 页面不一定提供点赞时间；按“最近一月”筛选时，不能拿发帖时间或本地抓取时间冒充点赞时间。

页面脚本的配置可加 `mode:'full'` 做全量，或加 `max:N` 限制条数。默认增量，在连续两批都是已知内容后停止。脚本一次约运行 30 秒；返回 `rerun:true` 时继续，返回 `done:true` 时结束。

## 导出与选题网页

```bash
python3 scripts/store.py stats
python3 scripts/store.py export-new
python3 scripts/store.py export
python3 scripts/store.py export-history
python3 scripts/build_unified_library.py --output ~/video-collect-site
```

`export-new` 只导出从未导出过的平台＋帖子 ID；`export` 刷新完整快照。网页按平台、来源、月份和抓取时间筛选。首次收录时间是**抓取时间**，不是点赞或收藏时间。

已有逐帖媒体归档时，可多次加 `--archive '<目录>'`，目录内需有 `catalog.json`，记录每条的 `platform`、`vid`、`url` 及相对目录的 `video`、`poster` 或 `images` 文件路径。网页只引用原文件，不复制媒体；移动归档目录后要重新生成网页。

小红书图文需要离线保存时，逐帖运行 `python3 scripts/xhs_images.py --url '<完整帖子链接>' --out '<每帖目录>/images'`。该脚本依赖 `yt-dlp` 和 `curl`，保存全部图片和正文；视频下载器提示没有视频格式，不代表图文无法归档。

## 范围

采集脚本依赖各平台现有网页结构，改版后可能需要更新。TikTok 暂无列表采集脚本。浏览器登录态始终留在本机；不要将 Cookie、真实数据目录、视频文件或带访问令牌的链接提交到公开仓库。
