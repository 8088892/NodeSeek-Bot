# NodeSeek Bot — 自动签到 + 评论 + 通知【已维护适配最新版登录方式】

[![NodeSeek 签到](https://github.com/8088892/NodeSeek-Bot/actions/workflows/bot.yml/badge.svg)](https://github.com/8088892/NodeSeek-Bot/actions/workflows/bot.yml)

NodeSeek 论坛全自动工具：每日签到 + 随机评论 + 多账号 + 多平台通知。专为 GitHub Actions 设计，Fork 即用，零服务器成本。

---

## ✨ 功能

| 功能 | 说明 |
|------|------|
| ✅ 自动签到 | API 直连（`curl_cffi`），免浏览器，支持一试手气 & 鸡腿 ×5 |
| 💬 自动评论 | Selenium 模拟浏览器，随机 3-5 条评论，绕 Cloudflare |
| 🔐 双登录模式 | 账号密码 + 验证码 / Cookie 直登，自动择优 |
| 👥 多账号 | 最多 6 组密码 + 不限量 Cookie 账号，`|` 分隔 |
| 🔄 Cookie 智能管理 | Cookie 优先签到 → 过期自动密码刷新 → 存回 GitHub Variables |
| 📊 签到统计 | 查询近 30 天鸡腿收益，每次推送汇总 |
| 📱 多平台通知 | Telegram / Bark / 钉钉 / 飞书 / Server酱 / PushPlus / 企业微信 / SMTP 邮件等 15+ 渠道 |
| 📅 GitHub Actions | 每天两次自动运行（00:05 / 12:05 北京时间），支持手动触发 |

---

## 🚀 部署步骤

### 1️⃣ Fork 本仓库

点击右上角 **Fork** → 勾选 **Copy the `main` branch only** → Create fork。

> ⚠️ **必须是自己的仓库**（非 fork 内部可见），否则 GitHub Actions 的定时任务默认禁用且无法通过 API 开启。
> 如果你的仓库页面显示 `forked from xxx`，进 Settings → General → 拉到底 → **Template repository** 勾上，或直接用「Import repository」导入。

### 2️⃣ 获取 Telegram Bot Token 和 Chat ID

| 变量 | 获取方法 |
|------|----------|
| `TG_BOT_TOKEN` | 找 [@BotFather](https://t.me/BotFather) 创建 Bot → 拿到形如 `123456:ABC-DEF1234gh` 的 token |
| `TG_CHAT_ID` | 给你的 Bot 发条消息 → 访问 `https://api.telegram.org/bot<TOKEN>/getUpdates` → 找到 `"chat":{"id":123456}` |

### 3️⃣ 配置验证码服务

NodeSeek 使用 Turnstile 验证码，推荐 **YesCaptcha**（最低充值 $1，按次计费）：新人可领1000积分 够使用很久了

👉 [注册 YesCaptcha（推广链接）](https://yescaptcha.com/i/fyzjbA)

注册后进入后台 → 复制 **Client Key**。

### 4️⃣ 获取 GitHub Personal Access Token

用于脚本自动保存 Cookie 到 GitHub Variables。

1. GitHub → 右上角头像 → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. 点 **Generate new token** → 选择仓库 `NodeSeek-Bot`
3. Repository permissions 勾选：
   - `Actions` → **Read and write**
   - `Variables` → **Read and write**
4. 生成后复制 token（只显示一次！）

### 5️⃣ 配置 Secrets 和 Variables

进入你的仓库 → **Settings** → **Secrets and variables** → **Actions**：

#### 🔑 Secrets（密钥，不可读取）

**账号密码登录（至少配一组）：**

| 变量 | 说明 | 必填 |
|------|------|:---:|
| `USER` | NodeSeek 用户名 | 是 |
| `PASS` | NodeSeek 密码 | 是 |
| `USER1` ~ `USER5` | 额外账号用户名 | 否 |
| `PASS1` ~ `PASS5` | 额外账号密码 | 否 |

> 注意：`USER`/`PASS` 是主账号，额外账号从 `USER1` 开始连续编号，不要跳号。

**验证码（账号密码登录必须）：**

| 变量 | 说明 | 值示例 |
|------|------|--------|
| `SOLVER_TYPE` | 验证码平台 | `yescaptcha` |
| `CLIENTT_KEY` / `YESCAPTCHA_CLIENT_KEY` | YesCaptcha Client Key | 从后台复制，两个变量名二选一即可 |
| `API_BASE_URL` | YesCaptcha API 地址 | `https://api.yescaptcha.com` |
| `NS_TOTP_SECRET` | NodeSeek 两步验证/TOTP 密钥 | 开启 2FA 时扫码页的 secret，非 6 位数字 |
| `NS_TOTP_FIELD` | 2FA 登录字段名 | 默认 `otp`，一般不用填 |
| `NS_TOTP_FIELDS` | 2FA 字段名候选列表 | 默认 `otp,code,totp,twoFactorCode,two_factor_code,mfaCode` |

**GitHub API（Cookie 自动保存需要）：**

| 变量 | 说明 |
|------|------|
| `GH_PAT` | 上一步创建的 GitHub Personal Access Token |

**Telegram 通知：**

| 变量 | 说明 |
|------|------|
| `TG_BOT_TOKEN` | 从 @BotFather 获取 |
| `TG_CHAT_ID` | 从 getUpdates 获取 |

**评论模块：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NS_COMMENT` | `false` | `false` 关闭评论 |
| `NS_COMMENT_URL` | 交易区 | 自定义评论区域 URL |
| `NS_DELAY_MIN` | `0` | 运行前随机延迟下限（分钟） |
| `NS_DELAY_MAX` | `0` | 运行前随机延迟上限（分钟） |

#### 📦 Variables（变量，可读取）

| 变量 | 说明 |
|------|------|
| `NS_COOKIE` | **不需要手动填**。脚本首次密码登录后自动创建并更新 |

> `NS_COOKIE` 由脚本自动管理：登录成功 → 自动保存 → 下次优先用 Cookie 签到（免验证码）→ Cookie 过期 → 自动密码刷新。

> 如果 NodeSeek 开启了两步验证，密码登录刷新 Cookie 需要额外配置 `NS_TOTP_SECRET`。注意这里填的是 TOTP 密钥/secret，不是当前 6 位动态验证码；脚本会运行时自动生成 6 位码。

### 6️⃣ 验证运行

进入 **Actions** 标签 → 选择 **NodeSeek 签到+评论** → **Run workflow** → 点绿色按钮手动触发一次。

运行完后检查 Telegram 是否收到通知。

---


## 🖥️ VPS 一键部署

适合不想用 GitHub Actions 随机 IP 的情况。VPS 负责日常签到；Cookie 失效时，再手动跑一次验证脚本。

### 首次安装

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/vmenzo/NodeSeek-Bot/main/install_vps.sh)
```

安装脚本会做这些：

- 安装系统依赖
- 下载仓库到 `/opt/NodeSeek-Bot`
- 创建 Python 虚拟环境
- 生成 `.env` 配置文件
- 创建 `/opt/NodeSeek-Bot/run.sh`
- 写入每天 `00:05` 和 `12:05` 的 cron 定时任务

### 日常命令

手动跑一次签到：

```text
/opt/NodeSeek-Bot/run.sh
```

Cookie 失效时，手机手动验证并自动写回 Cookie：

```text
bash /opt/NodeSeek-Bot/manual_login.sh
```

查看日志：

```text
tail -f /opt/NodeSeek-Bot/run.log
```

重新配置变量：

```text
bash /opt/NodeSeek-Bot/install_vps.sh
```

只更新代码和依赖，不改 `.env` / cron：

```text
bash /opt/NodeSeek-Bot/install_vps.sh --update
```

远程一键更新：

```text
bash <(curl -fsSL https://raw.githubusercontent.com/vmenzo/NodeSeek-Bot/main/install_vps.sh) --update
```

### 变量怎么填

| 变量 | 怎么填 |
|------|--------|
| `USER` | NodeSeek 用户名 |
| `PASS` | NodeSeek 密码 |
| `NS_COOKIE` | 可以留空；如果你已经有浏览器 Cookie，可以粘贴，最稳 |
| `SOLVER_TYPE` | 默认 `yescaptcha` |
| `CLIENTT_KEY` | YesCaptcha 的 Client Key |
| `YESCAPTCHA_CLIENT_KEY` | YesCaptcha Client Key，和 `CLIENTT_KEY` 二选一 |
| `API_BASE_URL` | 默认 `https://api.yescaptcha.com` |
| `NS_TOTP_SECRET` | 没开 2FA 就留空；开了就填二维码背后的字母 secret，不是 6 位数字 |
| `NS_TOTP_FIELD` | 不懂就回车，默认 `otp` |
| `NS_TOTP_FIELDS` | 不懂就回车 |
| `TG_BOT_TOKEN` | Telegram Bot Token，用来推送通知和手动验证链接 |
| `TG_CHAT_ID` | Telegram 接收通知的 chat id |
| `NS_COMMENT` | 默认 `false`，也就是不自动评论 |
| `RUN_TIMES` | 默认 `00:05,12:05` |

### Cookie 失效怎么办

日常 cron 只跑：

```text
/opt/NodeSeek-Bot/run.sh
```

如果 Cookie 失效，需要你手动跑：

```text
bash /opt/NodeSeek-Bot/manual_login.sh
```

这个脚本会：

1. 临时启动 VPS 上的 Chromium + noVNC
2. 终端和 Telegram 发一个临时浏览器链接和密码
3. 你用手机打开链接，在 VPS 浏览器里手动登录 NodeSeek
4. 回到 VPS 终端按 Enter
5. 脚本自动提取 Cookie，写回 `/opt/NodeSeek-Bot/.env`
6. 自动关闭临时浏览器入口

说明：

- `manual_login.sh` 只在 VPS 手动执行
- GitHub Actions 不会调用它
- cron 不会调用它
- 它不是绕过 Cloudflare，只是让你本人在 VPS 浏览器里完成验证

## 📱 多平台通知（可选）

`notify.py` 内置了 15+ 种通知渠道，**只需在 `.github/workflows/bot.yml` 的 `env` 段添加对应变量**即可同时启用多条渠道：

| 渠道 | 变量名 | 获取方式 |
|------|--------|----------|
| **Telegram** | `TG_BOT_TOKEN` `TG_USER_ID` | @BotFather |
| **Bark** (iOS) | `BARK_PUSH` | App Store 下载 Bark → 复制 URL |
| **钉钉机器人** | `DD_BOT_TOKEN` `DD_BOT_SECRET` | 钉钉群 → 机器人 → Webhook |
| **飞书机器人** | `FSKEY` | 飞书群 → 机器人 → Webhook |
| **Server酱** | `PUSH_KEY` | [sct.ftqq.com](https://sct.ftqq.com) |
| **PushPlus** | `PUSH_PLUS_TOKEN` | [pushplus.plus](http://www.pushplus.plus) |
| **企业微信应用** | `QYWX_AM` | 企业微信管理后台 |
| **企业微信机器人** | `QYWX_KEY` | 群聊 → 机器人 → Webhook |
| **SMTP 邮件** | `SMTP_SERVER` `SMTP_EMAIL` `SMTP_PASSWORD` 等 | 你的邮箱 SMTP 配置 |
| **PushDeer** | `DEER_KEY` | [pushdeer.com](https://www.pushdeer.com) |
| **PushMe** | `PUSHME_KEY` | [push.i-i.me](https://push.i-i.me) |
| **iGot** | `IGOT_PUSH_KEY` | [hellyw.com](https://push.hellyw.com) |
| **Gotify** | `GOTIFY_URL` `GOTIFY_TOKEN` | 自建 Gotify 服务 |
| **go-cqhttp** | `GOBOT_URL` `GOBOT_QQ` | 自建 QQ 机器人 |
| **Qmsg酱** | `QMSG_KEY` `QMSG_TYPE` | [qmsg.zendee.cn](https://qmsg.zendee.cn) |
| **智能微秘书** | `AIBOTK_KEY` `AIBOTK_TYPE` `AIBOTK_NAME` | [wechat.aibotk.com](http://wechat.aibotk.com) |

**示例：同时用 Telegram + 钉钉**

在 `bot.yml` 的 `env:` 段追加：

```yaml
DD_BOT_TOKEN: ${{ secrets.DD_BOT_TOKEN }}
DD_BOT_SECRET: ${{ secrets.DD_BOT_SECRET }}
```

然后在 Secrets 里添加对应的值即可。

---

## 🍪 Cookie 获取方法（手动）

如果你想跳过密码登录直接用 Cookie：

1. 浏览器打开 [NodeSeek](https://www.nodeseek.com) 并登录
2. F12 → Application → Cookies → `nodeseek.com`
3. 复制所有 `Name=Value`，拼成字符串如：`key1=val1; key2=val2`
4. 粘贴到 GitHub Variables → `NS_COOKIE`

多账号用 `|` 分隔：`cookie1|cookie2|cookie3`

---

## ⏰ 定时运行

| 时间 | 北京时间 | UTC |
|------|----------|-----|
| 第 1 次 | 00:05 | 16:05 |
| 第 2 次 | 12:05 | 04:05 |

修改频率：编辑 `.github/workflows/bot.yml` → `schedule` → `cron` 表达式。

> ⚠️ GitHub Actions 的定时任务有约 5-15 分钟的延迟，不是精确到秒。

---

## 🧠 工作原理

```
运行触发
    │
    ├─ 收集所有账号（密码 + Cookie）
    ├─ 随机延迟（可选）
    │
    └─ 逐账号处理 ──────────────────────┐
         │                              │
         ├─ 有 Cookie？                  │
         │   ├─ 是 → Cookie 签到        │
         │   │   ├─ 成功 → 评论 → 统计  │
         │   │   └─ 失效 ──────────┐     │
         │   └─ 无                 │     │
         │                        ↓     │
         │   密码登录 → 新Cookie → 签到  │
         │                  ↓           │
         │          保存到 GitHub       │
         │                  ↓           │
         │            评论 → 统计       │
         │                              │
         └─ 汇总 → 多平台通知 ──────────┘
```

---

## 🔧 环境变量全表

下面列出 `bot.yml` 中所有可用的环境变量，按需在 `env:` 段添加/删除：

| 变量 | 用途 | 来源 |
|------|------|------|
| `USER` `PASS` | 主账号密码 | Secrets |
| `USER1~5` `PASS1~5` | 额外账号 | Secrets |
| `NS_COOKIE` | Cookie（自动管理） | Variables |
| `SOLVER_TYPE` | 验证码平台 | Secrets |
| `CLIENTT_KEY` | YesCaptcha Key | Secrets |
| `API_BASE_URL` | YesCaptcha API | Secrets |
| `NS_TOTP_SECRET` | 2FA/TOTP 密钥 | Secrets |
| `NS_TOTP_FIELD` | 2FA 字段名，默认 `otp` | Secrets |
| `NS_TOTP_FIELDS` | 2FA 字段名候选列表 | Secrets |
| `GH_PAT` | GitHub Token | Secrets |
| `GITHUB_REPOSITORY` | 仓库名（自动注入） | Actions |
| `TG_BOT_TOKEN` | Telegram Bot | Secrets |
| `TG_CHAT_ID` | Telegram Chat | Secrets |
| `TG_USER_ID` | Telegram User | Secrets |
| `TG_THREAD_ID` | Telegram 话题 | Secrets |
| `NS_COMMENT` | 开关评论 | Secrets |
| `NS_COMMENT_URL` | 评论区域 | Secrets |
| `NS_DELAY_MIN/MAX` | 随机延迟 | `0` |
| `HEADLESS` | 评论模式 | `false` |
| `NS_RANDOM` | 签到随机 | `true` |
| 任意通知变量 | 多平台通知 | Secrets |

---

## 📄 License

MIT
