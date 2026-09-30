# 导入与媒体格式

## 标题与链接

CSV 用 UTF-8 编码，支持中文或下方对应的英文列名。JSON 示例：

```json
[
  {
    "title": "示例：制作一个随机工具",
    "url": "https://example.com/topics/demo",
    "month": "2026-09",
    "origins": ["knowledge"],
    "contributors": ["示例同学"],
    "kind": "选题"
  }
]
```

| 字段 | 中文列名 | 说明 |
|---|---|---|
| title | 标题 | 缺少标题时用链接代替 |
| url | 链接、原帖链接、参考链接 | 必须为 http / https 链接 |
| month | 月份 | YYYY-MM；可使用“未标月份” |
| platform | 平台 | 省略时按域名识别 |
| origins / source_type | 来源、获取来源 | like 点赞、favorite 收藏、search 搜索、knowledge 知识库、import 导入 |
| contributors / contributor | 收录人 | JSON 可填多人数组 |
| kind | 类型 | 媒体、选题、参考链接、文档、排期 |
| description | 文案 | 参与搜索；不包含在网页的共享导出里 |
| author | 作者 | 原帖作者 |
| likes | 点赞数 | 数字或原始数量文字 |
| published_at | 发布时间 | 原帖发布，不是收藏时间 |
| captured_at | 抓取时间、入库时间 | 不填则记录本次时间 |

每条记录一个链接。CSV 有多个链接时先拆成多行。重复帖子保持首次导入的标题和月份，合并收录人与来源；更新标题可编辑自己的导入归档后重新生成。不会擅自抓取原帖补标题或翻译。

导入文件整批校验；遇到错误会报出条目序号，不写入半批数据。进程异常留下 `.import.lock` 时，先确认没有导入正在运行，再删除该锁文件重试。

## 已下载媒体

媒体归档目录里的 `catalog.json` 示例：

```json
[
  {
    "platform": "web",
    "vid": "demo-video",
    "url": "https://example.com/topics/demo-video",
    "title": "示例视频",
    "month": "2026-09",
    "source_type": "favorite",
    "video": "demo-video/video.mp4",
    "poster": "demo-video/cover.jpg"
  }
]
```

`video`、`poster`、`images` 必须指向该归档目录内实际存在的文件。图文使用 `images` 数组。媒体缺失时显示仅链接，不能把链接当作已下载文件。普通 CSV / JSON 导入只收链接；媒体请走 `--archive`，防止导入文件擅自引用电脑里的其他文件。

导入归档和网页输出必须是不同目录，避免覆盖原始记录。多个归档同一帖会合并来源，并保留首先读到的非空月份。
