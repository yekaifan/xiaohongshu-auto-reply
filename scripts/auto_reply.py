#!/usr/bin/env python3
"""
Xiaohongshu Auto Reply - 小红书评论自动回复脚本
Connects to Chrome via DrissionPage, checks notifications for new comments,
replies automatically using configurable templates or AI-generated responses.

Usage:
  python auto_reply.py --port 9222 [--dry-run] [--max-replies 5]
"""

import os
import sys
import json
import time
import random
import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path

try:
    from DrissionPage import ChromiumPage
except ImportError:
    print("❌ DrissionPage not installed. Run: pip install DrissionPage")
    sys.exit(1)

# --- Configuration ---
CONFIG_DIR = Path.home() / ".xhs_auto_reply"
CONFIG_FILE = CONFIG_DIR / "config.json"
REPLY_LOG = CONFIG_DIR / "reply_log.json"

DEFAULT_CONFIG = {
    "port": 9222,
    "min_delay": 3,
    "max_delay": 7,
    "max_replies_per_run": 10,
    "reply_within_hours": 48,  # Only reply to comments within this many hours
    "dry_run": False,
    "reply_templates": {
        "default": "感谢关注🙏 有问题可以评论区交流~",
        "keywords": {}
    },
    "ai_reply": {
        "enabled": False,
        "prompt_template": "你是小红书博主，用户评论了'{comment}'，请用简短友好的语气回复（30字以内），不要推销。"
    }
}

NOTIFICATION_URL = "https://www.xiaohongshu.com/notification"


def load_config():
    """Load config, create default if not exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # Merge with defaults for any missing keys
        merged = {**DEFAULT_CONFIG, **cfg}
        if "reply_templates" in cfg:
            merged["reply_templates"] = {**DEFAULT_CONFIG["reply_templates"], **cfg.get("reply_templates", {})}
        return merged
    else:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        return DEFAULT_CONFIG


def load_reply_log():
    """Load log of already-replied comments."""
    if REPLY_LOG.exists():
        with open(REPLY_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"replied_ids": [], "last_check": None}


def save_reply_log(log):
    with open(REPLY_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def connect_chrome(port):
    """Connect to existing Chrome with remote debugging."""
    try:
        p = ChromiumPage(addr_or_opts=port)
        # Quick check
        p.get(f"http://localhost:{port}/json/version")
        return p
    except Exception as e:
        print(f"❌ Cannot connect to Chrome on port {port}: {e}")
        print(f"   Start Chrome with: chrome.exe --remote-debugging-port={port}")
        sys.exit(1)


def check_login(p):
    """Verify user is logged into xiaohongshu.com."""
    p.get("https://www.xiaohongshu.com/explore")
    time.sleep(random.uniform(2, 4))
    body = p.run_js("return document.body ? document.body.innerText.substring(0,300) : ''")
    if "手机号登录" in body or "扫码" in body:
        print("❌ Not logged into www.xiaohongshu.com. Please log in first.")
        return False
    print("✅ Logged in")
    return True


def get_comments(p, cfg):
    """Fetch recent comments from notification page."""
    p.get(NOTIFICATION_URL)
    time.sleep(random.uniform(3, 5))

    # Click "评论和@" tab
    p.run_js("""
    var all = document.querySelectorAll('*');
    for (var i=0; i<all.length; i++) {
        if (all[i].innerText && all[i].innerText.trim() === '评论和@' && all[i].offsetHeight < 60) {
            all[i].click();
            return;
        }
    }
    """)
    time.sleep(random.uniform(2, 3))

    # Extract comments
    comments = p.run_js("""
    var result = [];
    var items = document.querySelectorAll('[class*=notification], [class*=comment-item], [class*=msg-item]');
    // Fallback: parse the page text
    var text = document.body.innerText;
    var lines = text.split('\\n');
    var current = null;
    
    for (var i=0; i<lines.length; i++) {
        var line = lines[i].trim();
        // Match pattern: "username\\n评论了你的笔记...\\ncomment text\\n回复"
        if (line && !line.startsWith('评论和@') && !line.startsWith('赞和收藏') && 
            !line.includes('沪ICP备') && !line.includes('营业执照') &&
            line.length < 50 && line !== '回复') {
            // Check if next lines contain comment pattern
            var next = i+1 < lines.length ? lines[i+1].trim() : '';
            var next2 = i+2 < lines.length ? lines[i+2].trim() : '';
            var next3 = i+3 < lines.length ? lines[i+3].trim() : '';
            
            if (next && next.includes('评论了你的笔记')) {
                var timeMatch = next.match(/(\\d+)分钟前|(\\d+)小时前|(\\d+)天前|(\\d+-\\d+)/);
                var commentText = next2 !== '回复' ? next2 : '';
                result.push({
                    username: line,
                    note_info: next,
                    comment: commentText,
                    raw_time: next,
                    element_index: i
                });
            }
        }
    }
    return JSON.stringify(result);
    """)

    try:
        parsed = json.loads(comments)
        return parsed
    except:
        return []


def parse_time(raw_time):
    """Parse relative time from comment notification."""
    now = datetime.now()
    
    m = re.search(r'(\d+)分钟前', raw_time)
    if m:
        return now - timedelta(minutes=int(m.group(1)))
    
    m = re.search(r'(\d+)小时前', raw_time)
    if m:
        return now - timedelta(hours=int(m.group(1)))
    
    m = re.search(r'(\d+)天前', raw_time)
    if m:
        return now - timedelta(days=int(m.group(1)))
    
    m = re.search(r'(\d{2})-(\d{2})', raw_time)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        return datetime(now.year, month, day)
    
    return now  # Default to now for unknown format


def generate_reply(username, comment, cfg):
    """Generate reply text based on templates or AI."""
    templates = cfg.get("reply_templates", {})
    keywords = templates.get("keywords", {})
    
    # Check keyword matches first
    for keyword, template in keywords.items():
        if keyword.lower() in comment.lower():
            return template.format(username=username, comment=comment)
    
    # Use AI if enabled
    if cfg.get("ai_reply", {}).get("enabled"):
        # Note: AI reply requires integration; for now return template
        pass
    
    return templates.get("default", "感谢关注🙏")


def reply_to_comment(p, username, comment_text, reply_text, cfg):
    """Click reply and send response to a specific comment."""
    # Find and click "回复" near the username
    clicked = p.run_js(f"""
    var all = document.querySelectorAll('*');
    for (var i=0; i<all.length; i++) {{
        var el = all[i];
        if (el.innerText && el.innerText.trim() === '回复' && el.offsetParent !== null) {{
            var parent = el.parentElement;
            for (var j=0; j<5 && parent; j++) {{
                var txt = parent.innerText || '';
                if (txt.includes('{username}') && txt.includes('{comment_text[:20]}')) {{
                    el.click();
                    return 'clicked';
                }}
                parent = parent.parentElement;
            }}
        }}
    }}
    return 'not found';
    """)
    
    if clicked != 'clicked':
        return False
    
    time.sleep(random.uniform(1, 2))
    
    # Type reply
    escaped_reply = reply_text.replace("\\", "\\\\").replace("'", "\\'")
    p.run_js(f"""
    var ta = document.querySelector('textarea[placeholder*="回复"]');
    if (ta) {{
        ta.focus();
        var native = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        native.call(ta, '{escaped_reply}');
        ta.dispatchEvent(new Event('input', {{bubbles:true}}));
    }}
    """)
    
    time.sleep(random.uniform(0.5, 1))
    
    # Click send button
    p.run_js("""
    var btns = document.querySelectorAll('button, span');
    for (var i=0; i<btns.length; i++) {
        if ((btns[i].innerText||'').trim() === '发送' && btns[i].offsetParent !== null) {
            btns[i].click();
            return;
        }
    }
    """)
    
    time.sleep(random.uniform(1, 2))
    return True


def main():
    parser = argparse.ArgumentParser(description="小红书评论自动回复")
    parser.add_argument("--port", type=int, help="Chrome remote debugging port")
    parser.add_argument("--dry-run", action="store_true", help="Preview mode, don't actually reply")
    parser.add_argument("--max-replies", type=int, help="Max replies this run")
    parser.add_argument("--setup", action="store_true", help="Run first-time setup wizard")
    args = parser.parse_args()
    
    cfg = load_config()
    log = load_reply_log()
    
    # Override with CLI args
    if args.port:
        cfg["port"] = args.port
    if args.dry_run:
        cfg["dry_run"] = True
    if args.max_replies:
        cfg["max_replies_per_run"] = args.max_replies
    
    # Setup mode
    if args.setup:
        run_setup(cfg)
        return
    
    port = cfg["port"]
    print(f"🔌 Connecting to Chrome on port {port}...")
    p = connect_chrome(port)
    
    if not check_login(p):
        sys.exit(1)
    
    print(f"📬 Checking comments...")
    comments = get_comments(p, cfg)
    print(f"   Found {len(comments)} notification items")
    
    replied_count = 0
    for c in comments:
        if replied_count >= cfg["max_replies_per_run"]:
            print(f"   Reached max replies ({cfg['max_replies_per_run']}), stopping.")
            break
        
        username = c.get("username", "")
        comment_text = c.get("comment", "")
        raw_time = c.get("raw_time", "")
        
        # Skip if empty or already replied
        if not username or not comment_text:
            continue
        
        comment_id = f"{username}:{comment_text[:30]}"
        if comment_id in log["replied_ids"]:
            continue
        
        # Check time window
        comment_time = parse_time(raw_time)
        hours_ago = (datetime.now() - comment_time).total_seconds() / 3600
        if hours_ago > cfg.get("reply_within_hours", 48):
            continue
        
        # Generate reply
        reply_text = generate_reply(username, comment_text, cfg)
        
        print(f"\n💬 {username}: {comment_text[:60]}")
        print(f"   ⏰ {raw_time} ({hours_ago:.1f}h ago)")
        print(f"   ↩️  Reply: {reply_text}")
        
        if cfg.get("dry_run"):
            print("   🏃 Dry run - skipping")
            log["replied_ids"].append(comment_id)
            replied_count += 1
            continue
        
        # Random delay
        delay = random.uniform(cfg["min_delay"], cfg["max_delay"])
        print(f"   ⏳ Waiting {delay:.1f}s...")
        time.sleep(delay)
        
        # Send reply
        success = reply_to_comment(p, username, comment_text, reply_text, cfg)
        if success:
            print(f"   ✅ Replied!")
            log["replied_ids"].append(comment_id)
            replied_count += 1
        else:
            print(f"   ❌ Failed to reply")
    
    log["last_check"] = datetime.now().isoformat()
    save_reply_log(log)
    print(f"\n✅ Done. Replied to {replied_count} comments.")
    
    # 🚫 Never quit Chrome
    # p.quit()  # DO NOT CALL


def run_setup(cfg):
    """Interactive setup wizard."""
    print("\n🔧 小红书自动回复 - 首次设置向导\n")
    
    # 1. Chrome port
    port = input(f"Chrome远程调试端口 [{cfg['port']}]: ").strip()
    if port:
        cfg["port"] = int(port)
    
    # 2. Test connection
    print(f"\n🔌 测试连接端口 {cfg['port']}...")
    try:
        from DrissionPage import ChromiumPage
        p = ChromiumPage(addr_or_opts=cfg["port"])
        p.get(f"http://localhost:{cfg['port']}/json/version")
        print("✅ Chrome连接成功!")
    except:
        print(f"❌ 无法连接端口 {cfg['port']}")
        print(f"   请先启动Chrome: chrome.exe --remote-debugging-port={cfg['port']}")
    
    # 3. Login check
    print("\n🔐 检查登录状态...")
    p.get("https://www.xiaohongshu.com/explore")
    import time
    time.sleep(3)
    body = p.run_js("return document.body.innerText.substring(0,200);")
    if "手机号登录" in body:
        print("❌ 未登录! 请在Chrome中登录 www.xiaohongshu.com")
        print("   登录后重新运行此向导")
    else:
        print("✅ 已登录小红书!")
    
    # 4. Reply templates
    print("\n📝 配置默认回复模板:")
    default = input(f"  默认回复 [{cfg['reply_templates']['default']}]: ").strip()
    if default:
        cfg["reply_templates"]["default"] = default
    
    # 5. Save
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 配置已保存到 {CONFIG_FILE}")
    print(f"\n🚀 运行: python auto_reply.py --dry-run  (预览模式)")
    print(f"   python auto_reply.py                 (正式运行)")


if __name__ == "__main__":
    main()
