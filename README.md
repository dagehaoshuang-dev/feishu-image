# Feishu Image Skill

**从飞书群聊中获取图片，供 AI 视觉模型识别和处理。**

---

## 核心特性

- **多模式获取**：支持按数量批量拉取、按消息 ID 精准定位、按 image_key 直接下载
- **富文本支持**：不仅识别纯图片消息，还能提取富文本（post）消息中的内嵌图片
- **智能缓存**：Token 自动缓存 2 小时，已下载图片自动跳过，避免重复请求
- **格式自适应**：根据 Content-Type 自动判断图片扩展名（jpg/png/gif/webp）
- **零外部依赖**：纯 Python 标准库实现，无需 pip install
- **结构化输出**：返回标准 JSON，包含本地路径、发送者、时间戳等元数据

---

## 安装

### 方法 A：使用 OpenClaw 原生命令（推荐）

```bash
openclaw skills install feishu-image
```

### 方法 B：使用 ClawHub CLI

```bash
clawhub install feishu-image
```

### 方法 C：手动集成

```bash
git clone git@github.com:dagehaoshuang-dev/feishu-image.git ~/.openclaw/skills/feishu-image
```

---

## 前置配置

在 `~/.openclaw/openclaw.json` 中配置飞书应用凭证：

```json
{
  "channels": {
    "feishu": {
      "appId": "cli_xxxxxxxxxx",
      "appSecret": "xxxxxxxxxxxxxxxxxxxxxxxx"
    }
  }
}
```

> 飞书应用需要开通 **消息与群组** 相关权限（`im:message:readonly`、`im:resource`）。

---

## 使用方式

### 获取群内最新 N 张图片

```bash
python3 scripts/fetch_feishu_image.py --chat-id <群ID> --limit 5
```

### 获取指定消息的图片

```bash
python3 scripts/fetch_feishu_image.py --chat-id <群ID> --message-id <消息ID>
```

### 按 image_key 下载

```bash
python3 scripts/fetch_feishu_image.py --chat-id <群ID> --image-key <图片key>
```

### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--chat-id` | 是 | - | 飞书群 ID |
| `--limit` | 否 | 5 | 获取图片数量 |
| `--message-id` | 否 | - | 指定消息 ID |
| `--image-key` | 否 | - | 指定图片 key |
| `--max-pages` | 否 | 3 | 最大翻页数（每页 50 条消息） |

---

## 输出格式

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

图片保存在 `~/.openclaw/workspace/feishu-images/` 目录下。

---

## 安全说明

- 飞书凭证从本地配置文件读取，不硬编码在代码中
- Token 缓存文件权限为 `600`，仅当前用户可读写
- 所有外部输入参数（chat-id、message-id、image-key）均做字符白名单校验，防止 URL 注入和路径穿越

---

## 典型场景

- 用户在飞书群发了一张作业照片，要求 AI 批改
- 用户提到"看看群里最新的图片"
- 从飞书群获取截图供 AI 分析

---

## License

MIT License
