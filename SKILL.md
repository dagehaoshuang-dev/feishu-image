---
name: feishu-image
description: 当用户发送飞书群图片、或者提到飞书群里的图片时，使用本技能获取图片。触发场景包括：用户发送图片并要求批改/识别/查看、用户提到某张飞书群里的图片要求读取。
metadata:
  openclaw:
    homepage: https://github.com/dagehaoshuang-dev/feishu-image
---

# 飞书群图片获取技能

## 功能说明

从飞书群消息中获取图片，下载到本地供 AI 视觉模型识别。

## 工作流程

1. 从飞书 API 获取群消息列表（按时间倒序，支持自动翻页）
2. 筛选出 `image` 和 `post`（富文本）消息中的图片
3. 用正确的 message_id 下载图片资源
4. 返回图片本地路径，交给 AI 处理

## 使用方式

当用户要求读取飞书群图片时，调用 `scripts/fetch_feishu_image.py`

### 方式一：获取群内最新的 N 张图片
```bash
python3 scripts/fetch_feishu_image.py --chat-id <群ID> --limit <数量>
```

### 方式二：获取指定消息 ID 的图片
```bash
python3 scripts/fetch_feishu_image.py --chat-id <群ID> --message-id <消息ID>
```

### 方式三：根据 image_key 下载
```bash
python3 scripts/fetch_feishu_image.py --chat-id <群ID> --image-key <图片key>
```

### 可选参数
- `--max-pages <N>`：最大翻页数（默认 3，每页 50 条消息，即最多扫描 150 条消息）

所有图片默认保存到 `~/.openclaw/workspace/feishu-images/` 目录，返回的是本地绝对路径。

## 输出格式

脚本返回 JSON：
```json
{
  "ok": true,
  "images": [
    {
      "message_id": "om_xxx",
      "image_key": "img_v3_xxx",
      "local_path": "~/.openclaw/workspace/feishu-images/img_xxx.jpg",
      "sender": "ou_xxx",
      "timestamp": "1774360338124"
    }
  ]
}
```

## 注意事项

- 图片凭证据群 ID 和消息列表 API 获取，不依赖 reply 链
- 下载后的图片用 `image` 工具识别
- 飞书 App 凭证从 OpenClaw 配置中读取（`~/.openclaw/openclaw.json`）
- 支持纯图片消息和富文本（post）消息中的内嵌图片
- Token 自动缓存 2 小时，避免重复请求
- 已下载的图片会自动跳过，不重复下载
- 图片扩展名根据 Content-Type 自动判断（jpg/png/gif/webp）
- 错误信息输出到 stderr，不影响 JSON 结果解析
