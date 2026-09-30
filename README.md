# Video Collect

把自己在抖音、小红书、Instagram、X 的点赞或收藏内容收进本地资料库，按平台和来源浏览，增量导出新链接。支持小红书图文链接和按需保存图文原图。

这是一个供本地智能助手使用的技能，也可以单独运行脚本。**仓库不包含任何账号数据、Cookie、下载的视频或图片。**

## 安装

需要 Python 3.10+。列表采集需要已登录的浏览器；保存小红书图文时另需 `yt-dlp` 和 `curl`。

```bash
git clone https://github.com/huangbai-AI/video-collect.git
cd video-collect
sh scripts/start.sh
```

在支持技能目录的助手中，可把本仓库链接或复制到其 `video-collect` 技能目录。具体采集方法见 [SKILL.md](SKILL.md)。

## 本地数据

默认写入 `~/.local/share/video-collect/`。可通过环境变量更改：

```bash
export VC_DATA_DIR="$HOME/MyVideoCollectData"
python3 scripts/store.py stats
```

数据库以“平台＋帖子 ID”去重，同一帖子同时出现在点赞和收藏时会合并来源。`export-new` 另记导出历史，避免下次重复交付。

```bash
python3 scripts/store.py export-new
python3 scripts/store.py export
python3 scripts/build_unified_library.py --output "$HOME/video-collect-site"
```

打开 `~/video-collect-site/index.html` 即可看本地选题网页。网页里只有链接的条目需要联网打开原帖。已有媒体归档可用 `--archive` 添加，例如：

```bash
python3 scripts/build_unified_library.py \
  --output "$HOME/video-collect-site" \
  --archive "$HOME/video-archives/instagram"
```

媒体目录中的 `catalog.json` 应为条目数组。每条至少有 `platform`、`vid`、`url`；可选 `title`、`author`、`likes`、`published_at`、`captured_at`，以及指向同一归档目录内文件的相对路径 `video`、`poster`、`images`。生成器只引用原文件，不复制。

## 现有支持

| 平台 | 列表 | 状态 |
|---|---|---|
| 抖音 | 点赞、收藏 | 页面脚本 |
| 小红书 | 点赞、收藏，含图文 | 页面脚本 |
| Instagram | 已保存、点赞 | 页面脚本或可见卡片解析 |
| X | 点赞视频 | 浏览器读取后用 JSON 入库 |
| TikTok | 点赞、收藏 | 暂未实现 |

页面结构可能变化。只处理自己账号可见的列表；碰到验证或访问限制时停止，不尝试绕过。请尊重平台规则和原作者权益。

## 检查

```bash
python3 -m unittest discover -s tests -v
```

代码采用 [MIT 许可证](LICENSE)。
