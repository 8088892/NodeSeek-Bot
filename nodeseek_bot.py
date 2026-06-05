# -*- coding: utf-8 -*-
"""
NodeSeek Bot — 自动签到 + 自动评论 + 多账号
整合自:
  - kafuneri/NodeSeek-Signin (API 签到 + 验证码 + 账号密码登录)
  - nova73x/nodeseek-AutoDaily-signin (Selenium 自动评论)
"""

import os
import re
import json
import time
import random
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from curl_cffi import requests as cffi_requests
from yescaptcha import YesCaptchaSolver, YesCaptchaSolverError
from turnstile_solver import TurnstileSolver, TurnstileSolverError

# ── 可选模块 ──────────────────────────────────────────
hadsend = False
send = None
try:
    from notify import send
    hadsend = True
except ImportError:
    print("未加载通知模块，跳过 Telegram 通知功能")

# ── 随机评论语料 ──────────────────────────────────────
# 出帖（卖东西）：尽量短、自然，像路人顺手回一嘴
COMMENT_SELLING = [
    "帮顶，祝早出",
    "路过帮顶",
    "价格不错，帮顶",
    "顺手顶一下",
    "祝顺利出",
    "帮顶支持",
    "看着可以，帮顶",
    "顶一下",
    "祝交易顺利",
    "蹲个有缘人",
    "帮顶，早出",
    "路过支持下",
]

# 收帖（买东西）：尽量像真人，不要太像统一模板
COMMENT_BUYING = [
    "帮顶，祝早收",
    "路过帮顶",
    "祝早收到",
    "顺手顶一下",
    "蹲个好价",
    "帮顶支持",
    "祝顺利收到",
    "顶一下",
    "路过支持下",
    "祝收到合适的",
]

# 状态已完成的帖子不评论
COMMENT_DONE = []

# ── 配置 ──────────────────────────────────────────────
SOLVER_TYPE = os.getenv("SOLVER_TYPE", "yescaptcha")
API_BASE_URL = os.getenv("API_BASE_URL", "")
CLIENT_KEY = os.getenv("CLIENTT_KEY") or os.getenv("YESCAPTCHA_CLIENT_KEY", "")
NS_RANDOM = os.getenv("NS_RANDOM", "true")
NS_TOTP_SECRET = os.getenv("NS_TOTP_SECRET", "").replace(" ", "")
NS_TOTP_FIELD = os.getenv("NS_TOTP_FIELD", "otp") or "otp"
NS_TOTP_FIELDS = [f.strip() for f in os.getenv("NS_TOTP_FIELDS", "otp,code,totp,twoFactorCode,two_factor_code,mfaCode").split(",") if f.strip()]

# 通知配置
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID") or os.getenv("TG_USER_ID", "")
TG_THREAD_ID = os.getenv("TG_THREAD_ID", "")

# 评论配置
NS_COMMENT = os.getenv("NS_COMMENT", "false").lower() != "false"
COMMENT_URL = os.getenv("NS_COMMENT_URL", "") or "https://www.nodeseek.com/categories/trade"
_delay_min_raw = os.getenv("NS_DELAY_MIN", "0") or "0"
_delay_max_raw = os.getenv("NS_DELAY_MAX", "10") or "10"
NS_DELAY_MIN = int(_delay_min_raw)
NS_DELAY_MAX = int(_delay_max_raw)


def tg_send(title, msg):
    """通过 notify 模块发送 Telegram 通知"""
    if hadsend:
        try:
            send(title, msg)
        except Exception as e:
            print(f"通知发送失败: {e}")


def tg_send_photo(path, caption=""):
    """发送图片到 Telegram"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    try:
        import requests as py_requests
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
        with open(path, "rb") as f:
            py_requests.post(url, data={"chat_id": TG_CHAT_ID, "caption": caption}, files={"photo": f}, timeout=15)
    except Exception as e:
        print(f"发送图片失败: {e}")


def detect_environment():
    """检测运行环境"""
    if os.path.exists("/ql/data/") or os.path.exists("/ql/config/"):
        return "qinglong"
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "github"
    return "local"


# ── GitHub 变量管理 ───────────────────────────────────
def save_cookie_to_github(var_name, cookie):
    """保存 Cookie 到 GitHub Actions Variables"""
    import requests as py_requests
    token = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("GH_PAT/GITHUB_REPOSITORY 未设置，跳过变量保存")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    url_check = f"https://api.github.com/repos/{repo}/actions/variables/{var_name}"
    url_create = f"https://api.github.com/repos/{repo}/actions/variables"
    data = {"name": var_name, "value": cookie}

    resp = py_requests.patch(url_check, headers=headers, json=data)
    if resp.status_code == 204:
        print(f"GitHub: {var_name} 更新成功")
        return True
    elif resp.status_code == 404:
        resp = py_requests.post(url_create, headers=headers, json=data)
        if resp.status_code == 201:
            print(f"GitHub: {var_name} 创建成功")
            return True
    print(f"GitHub 操作失败: {resp.status_code}")
    return False


def save_cookie_to_local_env(var_name, cookie):
    """本地/VPS 运行时把 Cookie 写回 .env，避免下次继续使用旧 Cookie"""
    env_path = os.environ.get("NS_ENV_FILE", ".env")
    if not os.path.exists(env_path):
        print(f"本地 .env 不存在，跳过 {var_name} 保存: {env_path}")
        return False

    def quote_env_value(value):
        value = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{value}"'

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        prefix = f"{var_name}="
        new_line = f"{var_name}={quote_env_value(cookie)}\n"
        updated = False
        for idx, line in enumerate(lines):
            if line.startswith(prefix):
                lines[idx] = new_line
                updated = True
                break
        if not updated:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(new_line)

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        try:
            os.chmod(env_path, 0o600)
        except Exception:
            pass
        print(f"本地 .env: {var_name} 更新成功")
        return True
    except Exception as e:
        print(f"本地 .env: {var_name} 更新失败: {e}")
        return False


def save_cookie(var_name, cookie):
    """根据环境保存 Cookie"""
    if detect_environment() == "github":
        return save_cookie_to_github(var_name, cookie)
    return save_cookie_to_local_env(var_name, cookie)


# ── API 签到 ───────────────────────────────────────────
def api_sign(ns_cookie):
    """通过 API 签到，返回 (status, message)"""
    if not ns_cookie:
        return "invalid", "无有效 Cookie"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        "origin": "https://www.nodeseek.com",
        "referer": "https://www.nodeseek.com/board",
        "Content-Type": "application/json",
        "Cookie": ns_cookie,
    }
    try:
        url = f"https://www.nodeseek.com/api/attendance?random={NS_RANDOM}"
        resp = cffi_requests.post(url, headers=headers, impersonate="chrome110")
        data = resp.json()
        msg = data.get("message", "")
        if "鸡腿" in msg or data.get("success"):
            return "success", msg
        elif "已完成签到" in msg:
            return "already", msg
        elif data.get("status") == 404:
            return "invalid", msg
        return "fail", msg
    except Exception as e:
        return "error", str(e)


# ── 账号密码登录 + 验证码 ─────────────────────────────
def get_totp_code():
    """根据 NS_TOTP_SECRET 生成当前 2FA/TOTP 数字验证码"""
    if not NS_TOTP_SECRET:
        return ""
    try:
        import pyotp
        return pyotp.TOTP(NS_TOTP_SECRET).now()
    except Exception as e:
        print(f"TOTP 生成失败: {e}")
        return ""


def _login_success_cookie(session):
    cookies = session.cookies.get_dict()
    if not cookies:
        return None
    return "; ".join([f"{k}={v}" for k, v in cookies.items()])


def _need_2fa(resp_json):
    text = json.dumps(resp_json, ensure_ascii=False).lower()
    markers = ["2fa", "totp", "otp", "mfa", "twofactor", "two_factor", "二步验证", "两步验证", "双重验证", "动态验证码"]
    return any(marker in text for marker in markers)


def _post_login(session, data, headers):
    resp = session.post(
        "https://www.nodeseek.com/api/account/signIn",
        json=data,
        headers=headers,
    )
    try:
        return resp.json()
    except Exception:
        return {"success": False, "message": resp.text[:300], "status_code": resp.status_code}


def session_login(user, password):
    """使用账号密码登录，返回 cookie 字符串"""
    try:
        if SOLVER_TYPE.lower() == "yescaptcha":
            solver = YesCaptchaSolver(
                api_base_url=API_BASE_URL or "https://api.yescaptcha.com",
                client_key=CLIENT_KEY,
            )
        else:
            solver = TurnstileSolver(
                api_base_url=API_BASE_URL,
                client_key=CLIENT_KEY,
            )

        token = solver.solve(
            url="https://www.nodeseek.com/signIn.html",
            sitekey="0x4AAAAAAAaNy7leGjewpVyR",
            verbose=True,
        )
        if not token:
            print("验证码解析失败")
            return None
    except Exception as e:
        print(f"验证码错误: {e}")
        return None

    session = cffi_requests.Session(impersonate="chrome110")
    session.get("https://www.nodeseek.com/signIn.html")

    data = {
        "username": user,
        "password": password,
        "token": token,
        "source": "turnstile",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        "sec-ch-ua": '"Not A(Brand";v="99", "Microsoft Edge";v="121", "Chromium";v="121"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "origin": "https://www.nodeseek.com",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://www.nodeseek.com/signIn.html",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
    }
    try:
        totp_code = get_totp_code()
        candidate_fields = []
        if NS_TOTP_FIELD:
            candidate_fields.append(NS_TOTP_FIELD)
        for field in NS_TOTP_FIELDS:
            if field not in candidate_fields:
                candidate_fields.append(field)

        # 如果配置了 TOTP，就逐个尝试候选字段；字段名不确定时更稳。
        if totp_code:
            resp_json = None
            for idx, field in enumerate(candidate_fields):
                login_data = dict(data)
                login_data[field] = totp_code
                print(f"已生成 2FA/TOTP 验证码，尝试字段: {field}")
                resp_json = _post_login(session, login_data, headers)
                if resp_json.get("success"):
                    return _login_success_cookie(session)
                # 如果服务端返回完全不像 2FA 问题，通常继续试字段也没意义，但多试几种字段成本很低。
                if idx == 0 and not _need_2fa(resp_json):
                    print(f"首个 2FA 字段未通过，继续尝试其它候选字段")
        else:
            resp_json = _post_login(session, data, headers)
            if resp_json.get("success"):
                return _login_success_cookie(session)

        msg = resp_json.get("message") or resp_json
        if _need_2fa(resp_json) and not totp_code:
            print("登录需要 2FA/TOTP，但未配置 NS_TOTP_SECRET")
        print(f"登录失败: {msg}")
        return None
    except Exception as e:
        print(f"登录异常: {e}")
        return None


# ── 签到统计 ──────────────────────────────────────────
def get_signin_stats(ns_cookie, days=30):
    """查询近 N 天签到统计"""
    if not ns_cookie:
        return None, "无有效 Cookie"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "origin": "https://www.nodeseek.com",
        "referer": "https://www.nodeseek.com/board",
        "Cookie": ns_cookie,
    }
    try:
        tz = ZoneInfo("Asia/Shanghai")
        now = datetime.now(tz)
        start = now - timedelta(days=days)

        all_records = []
        for page in range(1, 21):
            url = f"https://www.nodeseek.com/api/account/credit/page-{page}"
            resp = cffi_requests.get(url, headers=headers, impersonate="chrome110")
            data = resp.json()
            if not data.get("success") or not data.get("data"):
                break

            records = data["data"]
            if not records:
                break

            last_time = datetime.fromisoformat(records[-1][3].replace("Z", "+00:00"))
            if last_time.astimezone(tz) < start:
                all_records.extend(
                    r for r in records
                    if datetime.fromisoformat(r[3].replace("Z", "+00:00")).astimezone(tz) >= start
                )
                break
            all_records.extend(records)
            time.sleep(0.5)

        signin_records = []
        for record in all_records:
            amount, balance, description, timestamp = record
            rt = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(tz)
            if rt >= start and "签到收益" in description and "鸡腿" in description:
                signin_records.append({
                    "amount": amount,
                    "date": rt.strftime("%m-%d"),
                })

        if not signin_records:
            return {"total": 0, "avg": 0, "days": 0, "period": f"近{days}天"}, "无签到记录"

        total = sum(r["amount"] for r in signin_records)
        return {
            "total": total,
            "avg": round(total / len(signin_records), 1),
            "days": len(signin_records),
            "period": f"近{days}天",
        }, "ok"
    except Exception as e:
        return None, str(e)


# ── 随机延迟 ──────────────────────────────────────────
def random_delay():
    if NS_DELAY_MAX <= 0:
        return
    actual_min = min(NS_DELAY_MIN, NS_DELAY_MAX)
    actual_max = max(NS_DELAY_MIN, NS_DELAY_MAX)
    delay_minutes = random.randint(actual_min, actual_max)
    if delay_minutes > 0:
        print(f"⏳ 随机延迟 {delay_minutes} 分钟后执行...")
        time.sleep(delay_minutes * 60)


# ── Selenium 评论 ─────────────────────────────────────
def _normalize_trade_text(text):
    """清洗交易帖文本，去掉常见装饰符号，便于关键词/正则判断"""
    if not text:
        return ""
    text = text.lower()
    # 去掉常见中括号/书名号/emoji风格装饰，只保留关键信息
    text = re.sub(r"[\[\]【】()（）<>《》「」『』|｜~～·•✨🔥⭐️✅❌✔️✖️]+", " ", text)
    text = re.sub(r"\s+", "", text)
    return text


def _match_trade_patterns(text, patterns):
    """按顺序匹配正则/字符串规则，命中即返回 True"""
    for pattern in patterns:
        if pattern.startswith("re:"):
            if re.search(pattern[3:], text):
                return True
        elif pattern in text:
            return True
    return False


def _detect_post_type(driver):
    """检测帖子类型：selling / buying / sold / bought / done / unknown"""
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    except:
        return "unknown"

    title = ""
    try:
        title = driver.find_element(By.CSS_SELECTOR, "h1, .post-title, .topic-title").text.lower()
    except:
        pass

    title_norm = _normalize_trade_text(title)
    body_norm = _normalize_trade_text(page_text[:1800])

    sold_patterns = [
        "已出", "已售", "已无", "已转", "已处理", "出掉了", "出完了", "sold",
        "re:(全部|已经)?出完", "re:已出给", "re:已出勿念", "re:已出谢谢",
    ]
    bought_patterns = [
        "已收", "已求到", "已蹲到", "已买", "已购入", "收到了", "收到啦", "bought",
        "re:已经?收到", "re:已收到", "re:收到谢谢", "re:求到了",
    ]
    continue_selling_patterns = [
        "继续出", "还在出", "继续卖", "继续挂", "还剩", "还有", "补一台", "补一个",
        "re:已出.*还(有|剩)", "re:已售.*还(有|剩)", "re:继续出.*", "re:补.*(台|个|枚|只)",
    ]
    continue_buying_patterns = [
        "继续收", "还在收", "继续求", "继续蹲", "再收", "还收", "继续求购",
        "re:已收.*再收", "re:已收.*继续收", "re:继续收.*", "re:再收(一台|一个|一枚)?",
    ]
    selling_patterns = [
        "出售", "甩卖", "明盘", "改邮箱", "带邮箱", "转让", "出闲置", "出自用", "小甩", "清仓",
        "re:^(出|卖|转)[^租收求借换]", "re:出(一台|一个|自用|闲置)", "re:卖(一台|一个)",
    ]
    buying_patterns = [
        "求购", "想收", "收一个", "收个", "收台", "求一个", "求一台", "蹲一个", "蹲台", "来一台", "来一个",
        "re:^(收|求|蹲)[^出卖转租]", "re:求(一台|一个)", "re:收(一台|一个|个)",
    ]
    done_patterns = [
        "交易完成", "已完成交易", "已结帖", "结帖", "封贴", "完结",
    ]

    # 1. 标题优先：继续交易 > 已完成 > 正常交易
    if _match_trade_patterns(title_norm, continue_selling_patterns):
        return "selling"
    if _match_trade_patterns(title_norm, continue_buying_patterns):
        return "buying"
    if _match_trade_patterns(title_norm, sold_patterns):
        return "sold"
    if _match_trade_patterns(title_norm, bought_patterns):
        return "bought"
    if _match_trade_patterns(title_norm, selling_patterns):
        return "selling"
    if _match_trade_patterns(title_norm, buying_patterns):
        return "buying"
    if _match_trade_patterns(title_norm, done_patterns):
        return "done"

    # 2. 正文补充判断：只认非常明确的表达，避免把聊天内容误判成交易状态
    if _match_trade_patterns(body_norm, done_patterns):
        return "done"
    if _match_trade_patterns(body_norm, continue_selling_patterns):
        return "selling"
    if _match_trade_patterns(body_norm, continue_buying_patterns):
        return "buying"
    if _match_trade_patterns(body_norm, sold_patterns):
        return "sold"
    if _match_trade_patterns(body_norm, bought_patterns):
        return "bought"

    clear_buying_body_patterns = [
        "求购", "想收", "收一个", "收个", "收台", "求一台", "求一个",
        "re:(求购|想收|收个|收一台|求一台).{0,18}(预算|价格|明盘|配置|账号|机器|服务器|vps)",
    ]
    clear_selling_body_patterns = [
        "出售", "转让", "出闲置", "甩卖", "明盘出", "打包出",
        "re:(出售|转让|出闲置|打包出).{0,18}(明盘|价格|配置|账号|机器|服务器|vps)",
    ]
    if _match_trade_patterns(body_norm, clear_buying_body_patterns):
        return "buying"
    if _match_trade_patterns(body_norm, clear_selling_body_patterns):
        return "selling"

    # 3. 标题兜底也收紧：必须是明确交易短语，不再只凭“收/出/卖”单字判断
    strict_buying_title_patterns = ["求购", "想收", "收一个", "收个", "收台", "求一台", "求一个", "蹲一个", "蹲台"]
    strict_selling_title_patterns = ["出售", "转让", "出闲置", "出自用", "甩卖", "明盘出", "打包出"]
    if _match_trade_patterns(title_norm, strict_buying_title_patterns) and not _match_trade_patterns(title_norm, sold_patterns + bought_patterns):
        return "buying"
    if _match_trade_patterns(title_norm, strict_selling_title_patterns) and not _match_trade_patterns(title_norm, sold_patterns):
        return "selling"

    return "unknown"


def _pick_comment(post_type, title_text=""):
    """根据帖子类型选评论；已完成态不评论，unknown 做温和兜底"""
    if post_type == "buying":
        return random.choice(COMMENT_BUYING)
    if post_type == "selling":
        return random.choice(COMMENT_SELLING)
    if post_type in {"sold", "bought", "done"}:
        return ""

    title_norm = _normalize_trade_text(title_text)

    # unknown 时不再兜底评论，避免因为标题里单个“收/出/卖”误伤非交易帖
    skip_markers = ["已出", "已售", "已收", "已求到", "结帖", "完结", "封贴"]
    strict_buying_markers = ["求购", "想收", "收一个", "收个", "收台", "求一台", "求一个", "蹲一个", "蹲台"]
    strict_selling_markers = ["出售", "转让", "出闲置", "出自用", "甩卖", "明盘出", "打包出"]

    if any(marker in title_norm for marker in skip_markers):
        return ""
    if any(marker in title_norm for marker in strict_buying_markers):
        return random.choice(COMMENT_BUYING)
    if any(marker in title_norm for marker in strict_selling_markers):
        return random.choice(COMMENT_SELLING)

    return ""


def _wait_for_cloudflare(driver, max_wait=30):
    """等待 Cloudflare 验证通过"""
    for i in range(max_wait // 3):
        title = driver.title
        if "Just a moment" in title or "Attention Required" in title or "Checking" in title:
            print(f"等待 Cloudflare 验证... (已等待 {i*3} 秒)")
            time.sleep(3)
        else:
            return True
    print("Cloudflare 验证超时")
    return False


def selenium_comment(ns_cookie):
    """使用 Selenium 模拟浏览器评论 — 适配 nova73x 的 Cloudflare 绕过方案"""
    if not NS_COMMENT:
        print("评论功能已关闭")
        return 0

    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.action_chains import ActionChains
    except ImportError:
        print("Selenium 未安装，跳过评论")
        return 0

    try:
        import undetected_chromedriver as uc
    except ImportError:
        print("undetected-chromedriver 未安装，跳过评论")
        return 0

    driver = None
    comment_count = 0
    try:
        print("正在初始化浏览器 (非 headless + xvfb 虚拟显示器)...")

        # 自动检测 Chrome 版本
        chrome_major_version = None
        try:
            import subprocess
            result = subprocess.run(
                ["google-chrome", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                v = result.stdout.strip().split()[-1]
                chrome_major_version = int(v.split(".")[0])
                print(f"检测到 Chrome 版本: {v} (主版本: {chrome_major_version})")
        except Exception:
            print("Chrome 版本检测失败，使用 UC 默认版本")

        chrome_options = uc.ChromeOptions()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--lang=zh-CN,zh")
        chrome_options.add_argument("--window-size=1920,1080")

        use_headless = os.getenv("HEADLESS", "false").lower() == "true"
        if not use_headless:
            print("使用 xvfb 虚拟显示器模式 (非 headless)，可绕过 Cloudflare")

        driver = uc.Chrome(
            options=chrome_options,
            headless=use_headless,
            use_subprocess=True,
            version_main=chrome_major_version,
        )
        driver.set_window_size(1920, 1080)
        print("Chrome 启动成功")

        # 先访问网站再设 Cookie（绕过 Cloudflare 的关键）
        print("正在设置 Cookie...")
        driver.get("https://www.nodeseek.com")
        time.sleep(5)

        for item in ns_cookie.split(";"):
            try:
                name, value = item.strip().split("=", 1)
                driver.add_cookie({
                    "name": name,
                    "value": value,
                    "domain": ".nodeseek.com",
                    "path": "/",
                })
            except:
                continue

        driver.refresh()
        time.sleep(3)

        # 等待 Cloudflare 验证通过（关键步骤！）
        _wait_for_cloudflare(driver)
        time.sleep(3)

        # 打开评论区域
        print(f"正在访问评论区域: {COMMENT_URL}")
        driver.get(COMMENT_URL)
        time.sleep(5)

        # 等待 Cloudflare（页面切换可能再次触发）
        _wait_for_cloudflare(driver)
        time.sleep(3)

        # 获取帖子列表 — 支持多种 CSS 选择器
        post_selectors = [
            ".post-list-item",
            ".topic-list-item",
            "article.post",
            "tr.topic-item",
            "[data-tid]",
        ]
        posts = None
        for sel in post_selectors:
            try:
                posts = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, sel))
                )
                if posts:
                    print(f"使用选择器 '{sel}' 找到 {len(posts)} 个帖子")
                    break
            except:
                continue

        if not posts:
            driver.save_screenshot("no_posts_found.png")
            tg_send_photo("no_posts_found.png", caption="❌ 未找到帖子列表元素")
            print("未找到任何帖子，页面标题:", driver.title)
            body_text = driver.find_element(By.TAG_NAME, "body").text[:300]
            print("页面内容预览:", body_text)
            return 0

        # 过滤置顶帖
        valid_posts = [p for p in posts if not p.find_elements(By.CSS_SELECTOR, ".pined")]
        post_count = random.randint(3, 5)
        selected = random.sample(valid_posts, min(post_count, len(valid_posts)))

        selected_urls = []
        for post in selected:
            try:
                link = post.find_element(By.CSS_SELECTOR, ".post-title a")
                selected_urls.append(link.get_attribute("href"))
            except:
                continue

        consecutive_failures = 0
        visited_urls = set()  # 防止同一帖子重复评论
        for i, post_url in enumerate(selected_urls):
            if consecutive_failures >= 2:
                print("连续失败 2 次，停止评论")
                break

            # 去重检查
            if post_url in visited_urls:
                print(f"  跳过已评论帖子: {post_url}")
                continue
            visited_urls.add(post_url)

            try:
                print(f"  评论 [{i+1}/{len(selected_urls)}]: {post_url}")
                driver.get(post_url)
                time.sleep(3)
                _wait_for_cloudflare(driver)

                # 检测帖子类型，选对应评论语
                post_type = _detect_post_type(driver)
                post_title = ""
                try:
                    post_title = driver.find_element(By.CSS_SELECTOR, "h1, .post-title, .topic-title").text.strip()
                except:
                    pass
                input_text = _pick_comment(post_type, post_title)
                if not input_text:
                    print(f"  标题: {post_title or '（未取到标题）'}")
                    print(f"  帖子类型: {post_type} → 无安全评论模板，跳过")
                    continue
                print(f"  标题: {post_title or '（未取到标题）'}")
                print(f"  帖子类型: {post_type} → 评论: {input_text}")

                editor = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".CodeMirror"))
                )
                driver.execute_script("arguments[0].click();", editor)
                time.sleep(0.5)

                try:
                    driver.execute_script(
                        "var cm=arguments[0].CodeMirror;if(cm)cm.setValue(arguments[1]);",
                        editor, input_text,
                    )
                except:
                    actions = ActionChains(driver)
                    for char in input_text:
                        actions.send_keys(char)
                        actions.pause(random.uniform(0.1, 0.3))
                    actions.perform()

                time.sleep(2)
                submit = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//button[contains(@class,'submit') and contains(text(),'发布评论')]",
                    ))
                )
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", submit)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", submit)

                print(f"  ✅ 已评论: {input_text}")
                comment_count += 1
                consecutive_failures = 0

                wait_sec = random.uniform(60, 120)
                print(f"  等待 {wait_sec:.0f} 秒...")
                time.sleep(wait_sec)

            except Exception as e:
                print(f"  ⚠️ 评论失败: {e}")
                consecutive_failures += 1
                try:
                    driver.get("https://www.nodeseek.com")
                    time.sleep(2)
                except:
                    break

        print(f"评论任务完成，共 {comment_count} 条")
        return comment_count

    except Exception as e:
        print(f"评论模块异常: {e}")
        traceback.print_exc()
        return comment_count
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


# ── 主流程 ────────────────────────────────────────────
if __name__ == "__main__":
    env_type = detect_environment()
    print(f"运行环境: {env_type}")

    # ── 收集账号密码 ──
    accounts_pw = []
    user = os.getenv("USER")
    password = os.getenv("PASS")
    if user and password:
        accounts_pw.append({"user": user, "password": password})

    idx = 1
    while True:
        u = os.getenv(f"USER{idx}")
        p = os.getenv(f"PASS{idx}")
        if u and p:
            accounts_pw.append({"user": u, "password": p})
            idx += 1
        else:
            break

    # ── 收集已保存的 Cookie ──
    raw_cookie = os.getenv("NS_COOKIE", "")
    saved_cookies = [c.strip() for c in raw_cookie.split("|") if c.strip()]

    print(f"  密码账号: {len(accounts_pw)} 个")
    print(f"  已存 Cookie: {len(saved_cookies)} 个")

    if len(accounts_pw) == 0 and len(saved_cookies) == 0:
        print("未配置任何账号！请设置 USER+PASS 或 NS_COOKIE")
        exit(1)

    # ── 随机延迟 ──
    random_delay()

    # ── 逐账号执行：Cookie 优先，过期则用密码刷新 ──
    all_results = []
    cookies_updated = False
    cookie_refresh_events = []
    new_cookie_list = []

    # 确定要处理的总账号数 = max(密码账号数, 已存cookie数)
    total = max(len(accounts_pw), len(saved_cookies))

    for i in range(total):
        # 取密码（可能没有）
        pw_info = accounts_pw[i] if i < len(accounts_pw) else None
        display = pw_info["user"] if pw_info else f"Cookie账号{i+1}"

        # 取 Cookie（可能没有）
        saved_cookie = saved_cookies[i] if i < len(saved_cookies) else ""

        print(f"\n{'='*50}")
        print(f"账号: {display}")
        print(f"{'='*50}")

        result = {"name": display, "sign": "failed", "reward": "0", "comments": 0, "error": None, "cookie_refreshed": False, "refresh_reason": ""}
        active_cookie = ""
        cookie_invalid_msg = ""

        # 1. 先尝试用已保存的 Cookie 签到
        if saved_cookie:
            print("尝试 Cookie 签到...")
            status, msg = api_sign(saved_cookie)
            if status in ("success", "already"):
                active_cookie = saved_cookie
                result["sign"] = status
                if status == "already":
                    result["reward"] = "已签"
                else:
                    result["reward"] = re.search(r"(\d+)", msg).group(1) if re.search(r"(\d+)", msg) else "0"
                print(f"Cookie 签到: {status} — {msg}")
            else:
                cookie_invalid_msg = msg
                print(f"Cookie 失效: {msg}")

        # 2. Cookie 无效或无Cookie，尝试密码登录
        if not active_cookie and pw_info:
            print("Cookie 无效，使用密码登录...")
            new_cookie = session_login(pw_info["user"], pw_info["password"])
            if new_cookie:
                print("登录成功，使用新 Cookie 签到...")
                active_cookie = new_cookie
                cookies_updated = True
                refresh_reason = "Cookie 失效" if saved_cookie else "无已保存 Cookie"
                if cookie_invalid_msg:
                    refresh_reason = f"{refresh_reason}: {cookie_invalid_msg}"
                result["cookie_refreshed"] = True
                result["refresh_reason"] = refresh_reason
                cookie_refresh_events.append(f"⚠️ {display}: {refresh_reason}，已通过账号密码 + 验证码/2FA 重新登录并刷新 Cookie")
                status, msg = api_sign(new_cookie)
                if status in ("success", "already"):
                    result["sign"] = status
                    if status == "already":
                        result["reward"] = "已签"
                    else:
                        result["reward"] = re.search(r"(\d+)", msg).group(1) if re.search(r"(\d+)", msg) else "0"
                    print(f"签到: {status} — {msg}")
                else:
                    result["error"] = f"签到失败: {msg}"
            else:
                result["error"] = "登录失败"

        # 3. 既没有有效Cookie也没有密码
        if not active_cookie and not pw_info:
            result["error"] = "Cookie 过期且无密码配置"

        # 签到统计
        if active_cookie:
            stats, _ = get_signin_stats(active_cookie, 30)
            if stats:
                result["stats"] = stats
                print(f"  近30天: {stats['days']}天签到, 共{stats['total']}鸡腿")

        # 评论
        if NS_COMMENT and active_cookie:
            result["comments"] = selenium_comment(active_cookie)

        # 收集有效 Cookie
        if active_cookie:
            new_cookie_list.append(active_cookie)

        all_results.append(result)

    # ── Cookie 过期时才保存（密码登录刷新后）──
    if cookies_updated and new_cookie_list:
        all_cookies_new = "|".join([c for c in new_cookie_list if c.strip()])
        save_cookie("NS_COOKIE", all_cookies_new)

    # ── Cookie 刷新提醒 ──
    if cookie_refresh_events:
        tg_send("<b>NodeSeek Cookie 已刷新</b>", "\n".join(cookie_refresh_events))

    # ── 汇总通知 ──
    beijing_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    for r in all_results:
        name = r["name"]
        if r.get("error"):
            lines.append(f"  ❌ {name}: {r['error']}")
        else:
            sign_icon = "✅" if r["sign"] in ("success", "already") else "❌"
            reward_str = r["reward"] if r["reward"] == "已签" else f"+{r['reward']}🍗"
            stats_str = ""
            if r.get("stats") and r["stats"]["days"] > 0:
                stats_str = f" | 近30天 {r['stats']['days']}天 {r['stats']['total']}🍗"
            refresh_str = " | ⚠️Cookie已刷新" if r.get("cookie_refreshed") else ""
            lines.append(f"  {sign_icon} {name}: {reward_str} | 💬{r['comments']}条{stats_str}{refresh_str}")

    report_body = f"""━━━━━━━━━━━━━━━
{chr(10).join(lines)}
━━━━━━━━━━━━━━━
🕐 {beijing_time}"""

    print(f"\nNodeSeek 每日简报\n{report_body}")
    tg_send("<b>NodeSeek 每日简报</b>", report_body)
