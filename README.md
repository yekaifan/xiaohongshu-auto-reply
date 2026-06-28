# 小红书评论自动回复

连接已有Chrome浏览器，自动检查小红书评论通知并智能回复。

## 功能

- 🔌 通过DrissionPage连接已有Chrome（继承登录态，安全不封号）
- 📬 自动拉取小红书通知页最新评论
- 🤖 支持模板匹配 + 关键词触发回复
- 🕐 可配置回复时间窗口（只回复N小时内的新评论）
- 📝 已回复记录防重复
- 🏃 预览模式（--dry-run）先看再发
- 🔧 一键设置向导（--setup）

## 快速开始

### 1. 安装依赖
```bash
pip install DrissionPage
```

### 2. 启动Chrome远程调试
```bash
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222

# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

### 3. 登录小红书
在Chrome中打开 `www.xiaohongshu.com` 并扫码登录。

### 4. 首次设置
```bash
python scripts/auto_reply.py --setup
```

### 5. 预览模式（推荐首用）
```bash
python scripts/auto_reply.py --dry-run
```

### 6. 正式运行
```bash
python scripts/auto_reply.py
```

## 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--port` | Chrome调试端口 | `--port 9224` |
| `--dry-run` | 预览模式，不实际回复 | `--dry-run` |
| `--max-replies` | 本次最多回复数 | `--max-replies 5` |
| `--setup` | 运行设置向导 | `--setup` |

## 配置说明

配置文件：`~/.xhs_auto_reply/config.json`

```json
{
  "port": 9222,
  "min_delay": 3,
  "max_delay": 7,
  "max_replies_per_run": 10,
  "reply_within_hours": 48,
  "reply_templates": {
    "default": "感谢关注🙏 有问题可以评论区交流~",
    "keywords": {
      "多少钱": "价格私信你了~",
      "推荐": "看你的车型和预算，评论区留车型我帮你看看~"
    }
  }
}
```

### 关键词匹配

在 `keywords` 中配置触发词和对应回复，命中优先级高于默认模板：

```json
"keywords": {
  "et5t": "ET5T可以的，原厂玻璃隔热不差，侧窗加层陶瓷膜更舒服。新能源别用金属膜~",
  "贴膜": "看你的需求~ 隔热膜和车衣都可以聊",
  "价格": "具体看车型和膜的类型，评论区留车型我帮你参考~"
}
```

## 安全规则

| 规则 | 说明 |
|------|------|
| ❌ 禁止kill Chrome | 永不执行 taskkill 或 p.quit() |
| ⏱ 操作间隔 | 每次回复间隔3-7秒 |
| 📊 频率控制 | 通过 max_replies_per_run 限制 |
| 🔐 登录态 | 只连接已有Chrome，不新建会话 |

## 定时运行（Cron）

可配合系统定时任务定期检查：

```bash
# 每30分钟检查一次
*/30 * * * * cd ~/projects/xiaohongshu-auto-reply && python scripts/auto_reply.py --max-replies 3
```

## 项目结构

```
xiaohongshu-auto-reply/
├── README.md
├── requirements.txt
├── SKILL.md                    # Hermes Agent skill 文件
└── scripts/
    └── auto_reply.py           # 主脚本
```
