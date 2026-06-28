---
name: xiaohongshu-auto-reply
description: "小红书评论自动回复 — 连接已有Chrome，拉取通知页最新评论，模板/关键词匹配自动回复。支持预览模式，安全不封号。"
version: 1.0.0
author: yekaifan
platforms: [windows, macos, linux]
prerequisites:
  python_packages: [DrissionPage]
setup:
  help: "首次使用运行 python scripts/auto_reply.py --setup 进入设置向导"
triggers:
  - "回复小红书评论"
  - "自动回复评论"
  - "检查小红书通知"
  - "auto reply xiaohongshu comments"
  - "xhs comment reply"
---

# 小红书评论自动回复

## 触发条件

当用户需要：
- 自动检查小红书新评论并回复
- 批量回复未读评论
- 设置评论自动回复规则

## 使用流程

### 首次设置
```bash
python scripts/auto_reply.py --setup
```

### 预览模式（推荐先用）
```bash
python scripts/auto_reply.py --dry-run
```

### 正式运行
```bash
python scripts/auto_reply.py --port 9222 --max-replies 5
```

## 前置条件

1. **Chrome 远程调试已启动**
   ```bash
   chrome.exe --remote-debugging-port=9222
   ```
2. **已登录 www.xiaohongshu.com**
3. **DrissionPage 已安装** `pip install DrissionPage`

## 配置关键词回复

编辑 `~/.xhs_auto_reply/config.json` 的 `reply_templates.keywords`：

```json
{
  "reply_templates": {
    "default": "感谢关注🙏",
    "keywords": {
      "多少钱": "具体看车型膜的型号，留车型我帮你参考~",
      "推荐": "评论区留车型我帮你看看什么方案合适~",
      "ET5T": "ET5T原厂玻璃隔热还行，侧窗加陶瓷膜更舒服，新能源别用金属膜~"
    }
  }
}
```

## 安全规则

| 规则 | 说明 |
|------|------|
| ❌ 永不 kill Chrome | `taskkill` 和 `p.quit()` 绝对禁止 |
| ⏱ 随机延迟 | 每次操作间隔 3-7 秒 |
| 📊 限频 | `max_replies_per_run` 控制上限 |
| 🔐 只连接不创建 | 只通过 `ChromiumPage(addr_or_opts=PORT)` 连接 |

## 定时运行

配合 Hermes cron 或其他调度工具：

```bash
# 每30分钟检查并回复最多3条
python scripts/auto_reply.py --port 9222 --max-replies 3
```

## 注意事项

- 回复文本中的 `#标签` 在通知页回复时不生效（需要进入笔记详情页才能添加话题）
- 通知页只显示评论和@，不显示赞和收藏
- 已回复的评论记录在 `~/.xhs_auto_reply/reply_log.json`，不会重复回复
- 建议先用 `--dry-run` 预览，确认无误后再正式运行

## 踩坑记录

- **文本框输入**: 小红书使用React SPA，必须用 `nativeInputValueSetter` + `dispatchEvent('input')` 才能正确填入文字
- **发送按钮**: 部分版本的发送按钮是 `<span>` 而非 `<button>`，需要同时查询两种元素
- **cookie隔离**: `creator.xiaohongshu.com` 和 `www.xiaohongshu.com` cookie不互通，评论通知需在 www 端查看
- **页面刷新**: 回复后页面不会自动刷新，需要主动 refresh 或重新拉取评论列表
