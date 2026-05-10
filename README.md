# NodeSeek Bot — 自动签到 + 评论

Fork 即用的 NodeSeek 论坛自动化工具，支持 **自动签到** + **自动评论** + **多账号**。

## ✨ 功能

- ✅ **自动签到** — API 直连，无需浏览器，支持「试试手气」和「鸡腿 x 5」
- 💬 **自动评论** — 随机评论交易帖（3-5 条，间隔 1-2 分钟）
- 🔐 **两种登录方式** — 账号密码 + 验证码 / 直接 Cookie
- 👥 **多账号** — 最多 6 个密码登录账号 + 无限 Cookie 账号
- 📊 **签到统计** — 近 30 天鸡腿收益
- 📱 **Telegram 通知** — 签到 + 评论结果推送
- 🔄 **Cookie 自动保存** — 登录后的 Cookie 自动存到 GitHub Variables

## 🚀 快速开始

1. Fork 本仓库
2. 配置 Secrets（见下方）
3. 自动每天执行两次：
   - **北京时间 00:05**（签到 + 评论）
   - **北京时间 12:05**（签到 + 评论）

## ⚙️ Secrets 配置

在 `Settings → Secrets and variables → Actions → Secrets` 添加：

### 账号密码登录（至少配一组）

| 变量 | 说明 |
|------|------|
| `USER` / `PASS` | 主账号 |
| `USER1` / `PASS1` | 额外账号 1 |
| ... | 最多到 USER5/PASS5 |

### Cookie 登录（可选，与密码登录二选一或共存）

| 变量 | 说明 |
|------|------|
| `NS_COOKIE` | Cookie 字符串，多账号用 `&` 或 `\|` 分隔 |

### 🧩 验证码（账号密码登录必须）

推荐使用 **YesCaptcha**（最低充值 $1 起，按次计费，便宜好用）：

👉 [注册 YesCaptcha](https://yescaptcha.com/i/fyzjbA)

| 变量 | 说明 |
|------|------|
| `SOLVER_TYPE` | 填 `yescaptcha` |
| `API_BASE_URL` | `https://api.yescaptcha.com` |
| `CLIENTT_KEY` | YesCaptcha 后台的 Client Key |

### GitHub（Cookie 自动保存需要）

| 变量 | 说明 |
|------|------|
| `GH_PAT` | GitHub Personal Access Token（需 `actions:write` 权限） |

### 通知（可选）

| 变量 | 说明 |
|------|------|
| `TG_BOT_TOKEN` | Telegram Bot Token |
| `TG_CHAT_ID` | Telegram Chat ID |

### 评论（可选，默认开启）

| 变量 | 说明 |
|------|------|
| `NS_COMMENT` | `true`(默认) / `false` 关闭评论 |
| `NS_COMMENT_URL` | 评论区域 URL（默认交易区） |
| `NS_DELAY_MIN/MAX` | 随机延迟分钟（默认 0-10） |

## 📋 手动运行

进入 Actions 页面 → 选择 workflow → **Run workflow**

## 🍪 获取 Cookie

1. 浏览器登录 [NodeSeek](https://www.nodeseek.com)
2. F12 → Application → Cookies → 复制所有 cookie
3. 或 Network 标签 → 任意请求 → Headers → Cookie

## License

MIT
