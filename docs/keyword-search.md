# 从平台搜索到选题中台

本功能连接已有的选题搜索项目，复用它的小红书、B站采集器。它不是公开网页搜索，外部项目没有抖音、X、Instagram、TikTok 搜索器；抖音另有下方独立浏览器试验入口。

## 搜索规则

默认选题词：AI 视频、AI、AI教程、AI工具、Coding、编程、Vibe Coding、AI 视频教程、AIGC、AI 设计。

在平台内按最多点赞排序、限定一周内，每个关键词每个平台最多取20条，至少2000赞。运行时读取外部项目已启用的关键词、平台及点赞门槛；审核时默认再次执行一周和2000赞门槛。若需调整，必须明确修改审核文件的 `rules` 并说明理由。

小红书有些列表不提供发布日期，只在采集器证明“一周内＋最多点赞”筛选生效时接受；网页显示发布日期未知，不能补造日期。B站缺少可确认发布日期时不收录。发布筛选与收藏时间筛选是两回事。

## 准备与运行

准备一个使用 `backend/config.py`、`backend/scrapers/registry.py`、`backend/data/topic_assistant.db` 结构的选题搜索项目，安装其依赖并完成登录、关键词和网络配置。这个仓库不提供该外部项目，也不携带账号或代理配置。需要兼容其 `prefetch`、`search_and_wrap` 及 `last_search_debug` 接口。

批量搜索使用独立小号，不能借用默认主号。保留既有代理设置，不切换全局网络。默认逐项搜索；遇到登录、验证码或访问异常立即停下该平台，不自动恢复或解验证码。禁用本轮飞书通知，输出只保存在本机。

```bash
python3 scripts/keyword_search.py run --project "/你的选题搜索项目" --out "./private-round"
python3 scripts/keyword_search.py prepare ./private-round/search_results.json --out ./private-round/review.json
```

`run` 会寻找该项目 `backend/.venv`，必要时用 `--python` 指定已经安装其依赖的解释器。`search_results.json` 是本次真实采集记录；失败、空结果和风险停止都有单独记录。历史缓存不能冒充本次采集。

## 审核后导入

打开 `review.json`，逐条判断实际内容与选题相关性。标题或文案不足以确认的留为 `pending`；纯日常、剧情、泛励志、纯带货、与选题无关的内容设为 `excluded`。不要只因标题含 AI 就收录。制作案例、创作方法、开发过程、具体工具教程可设为 `keep`，同时填写 `review_reason`，注明判断依据；没有观看视频就不能声称已观看。

只有 `keep` 会导入，且导入前再次核验点赞与时间依据：

```bash
python3 scripts/keyword_search.py import ./private-round/review.json --output "./我的选题网页"
```

生成网页具有月份、平台、来源及关键词筛选；来源标为搜索，抓取时间保留本次记录，重复帖子合并。默认只导入标题和链接，不下载、清理视频，不发外部消息。导入后打开输出目录的 `index.html` 即可。

真实搜索记录、审核文件和网页都不要上传公开仓库。建议把输出放在仓库之外，或放在已忽略的 `private-round/` 目录。

## 已验证范围

2026-10-06 使用兼容项目实测了小红书和B站的上述10个关键词，两平台都返回结果；小红书记录到筛选已生效，B站返回明确发布时间。在线实测使用同一套外部采集器；本仓库桥接入口的门槛核验和审核逻辑另有本地测试。平台可能改版，不能据此保证以后每轮成功。

## 抖音小号搜索（试验接入）

抖音使用独立的可见 Chrome 窗口，单独保存小号登录状态；不会读取默认 Chrome 的资料。先安装 `@playwright/cli`，再运行：

```bash
npm install -g @playwright/cli
python3 scripts/douyin_keyword_search.py login
```

在打开的专用窗口自行扫码登录小号、完成验证；不要把短信验证码发给助手。登录完成后：

```bash
python3 scripts/douyin_keyword_search.py run --out ./private-round
python3 scripts/keyword_search.py prepare ./private-round/search_results.json --out ./private-round/review.json
```

先试一个关键词可增加 `--keyword 'AI教程'`；省略则跑上面的10个词。默认每组间隔至少12秒，只读取前20条以内的可见结果，不追求全量。若使用其他安装位置，通过 `--cli` 指定浏览器工具路径。

每组重新确认“最多点赞”和“一周内”实际处于选中状态，失败或遇验证就停止。发布时间若只显示“1天前”等，保留原显示文字，不编造精确时间；据已生效的时间筛选核验范围。缩写点赞量如“3.8万”属于近似数据。结果仍须人工筛选相关性，只有审核后保留的项目才能用前述 `import` 命令导入。网页、账号目录和结果只留本机，媒体默认不下载。

此方式是独立浏览器操作入口，不属于外部搜索项目的采集器注册表；页面改版时可能失效。

2026-10-06 实测抖音小号：10组关键词取得90条结果，57条达到2000赞，按标题与卡片文案初筛保留6条。未逐条观看。出现同名“视频”入口冲突后修正分类选择，再继续完成；登录验证由用户自行完成。
