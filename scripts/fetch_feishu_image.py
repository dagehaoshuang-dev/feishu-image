#!/usr/bin/env python3
"""
Fetch images from Feishu group chat messages.
Saves images to ~/.openclaw/workspace/feishu-images/
Returns JSON with image paths and metadata.
"""

import argparse
import json
import os
import re
import stat
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
SAVE_DIR = Path.home() / ".openclaw" / "workspace" / "feishu-images"
TOKEN_CACHE_PATH = SAVE_DIR / ".token_cache.json"

API_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 60

EXT_MAP = {
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}

# Only allow safe characters in IDs to prevent URL injection and path traversal
SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]+$')


def log_error(msg: str):
    """Write error message to stderr for debugging."""
    print(f"[feishu-image] {msg}", file=sys.stderr)


def validate_id(value: str, name: str):
    """Validate that an ID parameter contains only safe characters."""
    if not SAFE_ID_PATTERN.match(value):
        print(json.dumps({"ok": False, "error": f"Invalid {name}: contains unsafe characters"}))
        sys.exit(1)


def load_feishu_credentials():
    """Load Feishu app credentials from openclaw.json."""
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        feishu = config.get("channels", {}).get("feishu", {})
        app_id = feishu.get("appId") or feishu.get("app_id")
        app_secret = feishu.get("appSecret") or feishu.get("app_secret")
        if not app_id or not app_secret:
            return None, None
        return app_id, app_secret
    except FileNotFoundError:
        log_error(f"配置文件不存在: {CONFIG_PATH}")
        return None, None
    except (json.JSONDecodeError, KeyError) as e:
        log_error(f"配置文件解析失败: {e}")
        return None, None


def get_tenant_token(app_id: str, app_secret: str) -> str:
    """Get tenant access token from Feishu, with local file cache (2h TTL)."""
    # Check cache first
    if TOKEN_CACHE_PATH.exists():
        try:
            cache = json.loads(TOKEN_CACHE_PATH.read_text())
            if time.time() < cache.get("expires_at", 0):
                return cache["token"]
        except (json.JSONDecodeError, KeyError):
            pass

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            result = json.loads(resp.read())
            if result.get("code") == 0:
                token = result.get("tenant_access_token", "")
                if token:
                    SAVE_DIR.mkdir(parents=True, exist_ok=True)
                    TOKEN_CACHE_PATH.write_text(json.dumps({
                        "token": token,
                        "expires_at": time.time() + 7000,  # 2h TTL, 200s margin
                    }))
                    os.chmod(TOKEN_CACHE_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 600
                return token
            else:
                log_error(f"获取 token 失败, code={result.get('code')}, msg={result.get('msg')}")
    except Exception as e:
        log_error(f"获取 token 请求异常: {e}")
    return ""


def get_chat_messages(token: str, chat_id: str, page_size: int = 50, max_pages: int = 3) -> list:
    """Fetch recent messages from a Feishu chat with pagination support."""
    base_url = "https://open.feishu.cn/open-apis/im/v1/messages"
    all_items = []
    page_token = ""

    for page in range(max_pages):
        params = f"container_id_type=chat&container_id={chat_id}&page_size={page_size}&sort_type=ByCreateTimeDesc"
        if page_token:
            params += f"&page_token={page_token}"
        url = f"{base_url}?{params}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                result = json.loads(resp.read())
                if result.get("code") != 0:
                    log_error(f"获取消息列表失败 (page {page}), code={result.get('code')}, msg={result.get('msg')}")
                    break
                data = result.get("data", {})
                items = data.get("items", [])
                all_items.extend(items)
                page_token = data.get("page_token", "")
                if not data.get("has_more") or not page_token:
                    break
        except Exception as e:
            log_error(f"获取消息列表请求异常 (page {page}): {e}")
            break

    return all_items


def download_image(token: str, message_id: str, image_key: str, save_dir: Path) -> tuple:
    """Download a single image from Feishu message resource API.

    Returns (success: bool, local_path: Path).
    Skips download if file already exists. Determines extension from Content-Type.
    """
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{image_key}?type=image"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

    base_name = image_key.replace("/", "_")

    # Check if already downloaded (any extension)
    existing = list(save_dir.glob(f"{base_name}.*"))
    if existing and existing[0].stat().st_size > 0:
        return True, existing[0]

    try:
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "")
            ext = EXT_MAP.get(content_type, ".jpg")
            save_path = save_dir / f"{base_name}{ext}"
            data = resp.read()
            with open(save_path, "wb") as f:
                f.write(data)
            return True, save_path
    except Exception as e:
        log_error(f"下载图片失败 message_id={message_id}, image_key={image_key}: {e}")
        return False, None


def extract_images_from_post(content_str: str) -> list:
    """Extract image_keys from a post (rich text) message body."""
    image_keys = []
    try:
        content = json.loads(content_str)
        post = content
        if "content" in post:
            post = post["content"]
        if isinstance(post, dict):
            for locale_val in post.values():
                if isinstance(locale_val, dict) and "content" in locale_val:
                    for line in locale_val["content"]:
                        for elem in line:
                            if elem.get("tag") == "img" and elem.get("image_key"):
                                image_keys.append(elem["image_key"])
        elif isinstance(post, list):
            for line in post:
                for elem in line:
                    if elem.get("tag") == "img" and elem.get("image_key"):
                        image_keys.append(elem["image_key"])
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return image_keys


def find_image_in_messages(messages: list, limit: int = None) -> list:
    """Find image messages from a list of messages, including rich text posts."""
    images = []
    for msg in messages:
        msg_type = msg.get("msg_type")
        msg_id = msg.get("message_id", "")
        sender = msg.get("sender", {}).get("id", "")
        timestamp = msg.get("create_time", "")
        body = msg.get("body", {}).get("content", "")

        if msg_type == "image":
            try:
                body_json = json.loads(body)
                image_key = body_json.get("image_key", "")
            except (json.JSONDecodeError, TypeError):
                continue
            if image_key:
                images.append({
                    "message_id": msg_id,
                    "image_key": image_key,
                    "sender": sender,
                    "timestamp": timestamp,
                })
        elif msg_type == "post":
            for image_key in extract_images_from_post(body):
                images.append({
                    "message_id": msg_id,
                    "image_key": image_key,
                    "sender": sender,
                    "timestamp": timestamp,
                })

        if limit and len(images) >= limit:
            images = images[:limit]
            break
    return images


def main():
    parser = argparse.ArgumentParser(description="Fetch images from Feishu group chat")
    parser.add_argument("--chat-id", required=True, help="Feishu chat ID")
    parser.add_argument("--limit", type=int, default=5, help="Number of images to fetch (default: 5)")
    parser.add_argument("--message-id", help="Download specific message by ID")
    parser.add_argument("--image-key", help="Download specific image by key (requires --chat-id)")
    parser.add_argument("--max-pages", type=int, default=3, help="Max pages to fetch (default: 3, each page up to 50 messages)")
    args = parser.parse_args()

    # Validate inputs
    validate_id(args.chat_id, "chat-id")
    if args.message_id:
        validate_id(args.message_id, "message-id")
    if args.image_key:
        validate_id(args.image_key, "image-key")

    app_id, app_secret = load_feishu_credentials()
    if not app_id or not app_secret:
        print(json.dumps({"ok": False, "error": "Feishu credentials not found in config"}))
        sys.exit(1)

    token = get_tenant_token(app_id, app_secret)
    if not token:
        print(json.dumps({"ok": False, "error": "Failed to get tenant access token"}))
        sys.exit(1)

    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    results = {"ok": True, "images": []}

    if args.image_key:
        messages = get_chat_messages(token, args.chat_id, max_pages=args.max_pages)
        image_msgs = find_image_in_messages(messages)
        target_msg = None
        for img in image_msgs:
            if img["image_key"] == args.image_key:
                target_msg = img
                break
        if not target_msg:
            print(json.dumps({"ok": False, "error": f"Image key {args.image_key} not found in recent messages"}))
            sys.exit(1)
        ok, path = download_image(token, target_msg["message_id"], args.image_key, SAVE_DIR)
        if ok:
            results["images"].append({
                "message_id": target_msg["message_id"],
                "image_key": args.image_key,
                "local_path": str(path),
                "sender": target_msg["sender"],
                "timestamp": target_msg["timestamp"],
            })
    elif args.message_id:
        messages = get_chat_messages(token, args.chat_id, max_pages=args.max_pages)
        image_msgs = find_image_in_messages(messages)
        target_msg = None
        for img in image_msgs:
            if img["message_id"] == args.message_id:
                target_msg = img
                break
        if not target_msg:
            print(json.dumps({"ok": False, "error": f"Message {args.message_id} not found or no image"}))
            sys.exit(1)
        ok, path = download_image(token, target_msg["message_id"], target_msg["image_key"], SAVE_DIR)
        if ok:
            results["images"].append({
                "message_id": target_msg["message_id"],
                "image_key": target_msg["image_key"],
                "local_path": str(path),
                "sender": target_msg["sender"],
                "timestamp": target_msg["timestamp"],
            })
    else:
        messages = get_chat_messages(token, args.chat_id, max_pages=args.max_pages)
        image_msgs = find_image_in_messages(messages, limit=args.limit)
        for img in image_msgs:
            ok, path = download_image(token, img["message_id"], img["image_key"], SAVE_DIR)
            if ok:
                results["images"].append({
                    "message_id": img["message_id"],
                    "image_key": img["image_key"],
                    "local_path": str(path),
                    "sender": img["sender"],
                    "timestamp": img["timestamp"],
                })

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
