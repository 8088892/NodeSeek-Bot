#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$(cd "$(dirname "$0")" && pwd)}"
DISPLAY_NUM="${NS_MANUAL_DISPLAY:-99}"
VNC_PORT="${NS_MANUAL_VNC_PORT:-5901}"
WEB_PORT="${NS_MANUAL_WEB_PORT:-6080}"
PROFILE="${NS_MANUAL_PROFILE:-$INSTALL_DIR/.manual-login-profile}"
BASE="${NS_MANUAL_TMP:-/tmp/nodeseek-manual-login}"
LOG="$BASE/session.log"
PIDS="$BASE/pids"
URL="https://www.nodeseek.com/signIn.html"

need_root_hint() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "提示：如果启动失败，请用 root 运行：sudo bash $INSTALL_DIR/manual_login.sh"
  fi
}

load_env() {
  cd "$INSTALL_DIR"
  if [ ! -f .env ]; then
    echo "未找到 $INSTALL_DIR/.env，请先运行 install_vps.sh 配置变量。"
    exit 1
  fi
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
  export NS_ENV_FILE="$INSTALL_DIR/.env"
}

check_deps() {
  local missing=()
  for c in Xvfb x11vnc websockify curl openssl; do
    command -v "$c" >/dev/null 2>&1 || missing+=("$c")
  done
  if ! command -v chromium >/dev/null 2>&1 && ! command -v /snap/bin/chromium >/dev/null 2>&1 && ! command -v google-chrome >/dev/null 2>&1; then
    missing+=("chromium")
  fi
  if [ "${#missing[@]}" -gt 0 ]; then
    echo "缺少依赖：${missing[*]}"
    echo "请先运行：bash $INSTALL_DIR/install_vps.sh --update"
    exit 1
  fi
}

chrome_bin() {
  for c in "${CHROME_BIN:-}" /snap/bin/chromium chromium google-chrome google-chrome-stable; do
    [ -n "$c" ] && command -v "$c" >/dev/null 2>&1 && { command -v "$c"; return; }
    [ -x "$c" ] && { echo "$c"; return; }
  done
  return 1
}

cleanup_old() {
  if [ -f "$PIDS" ]; then
    xargs -r kill < "$PIDS" 2>/dev/null || true
  fi
  pkill -f "Xvfb :$DISPLAY_NUM" 2>/dev/null || true
  pkill -f "x11vnc.*:$DISPLAY_NUM" 2>/dev/null || true
  pkill -f "websockify.*$WEB_PORT" 2>/dev/null || true
  rm -f "$PIDS"
}

cleanup() {
  echo
  echo "关闭临时远程浏览器入口..."
  cleanup_old
}

public_ip() {
  curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}'
}

send_tg() {
  local text="$1"
  if [ -n "${TG_BOT_TOKEN:-}" ] && [ -n "${TG_CHAT_ID:-${TG_USER_ID:-}}" ]; then
    curl -fsS -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TG_CHAT_ID:-${TG_USER_ID:-}}" \
      --data-urlencode "text=$text" >/dev/null 2>&1 || true
  fi
}

start_browser() {
  mkdir -p "$BASE" "$PROFILE"
  : > "$LOG"
  cleanup_old

  local pass ip cbin
  pass="$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9' | head -c 12)"
  ip="$(public_ip)"
  cbin="$(chrome_bin)"

  echo "启动临时显示器..."
  Xvfb ":$DISPLAY_NUM" -screen 0 1365x900x24 >>"$LOG" 2>&1 & echo $! >> "$PIDS"
  sleep 1

  echo "启动 Chromium..."
  DISPLAY=":$DISPLAY_NUM" "$cbin" \
    --no-sandbox \
    --disable-dev-shm-usage \
    --window-size=1365,900 \
    --user-data-dir="$PROFILE" \
    --remote-debugging-address=127.0.0.1 \
    --remote-debugging-port=9222 \
    "$URL" >>"$LOG" 2>&1 & echo $! >> "$PIDS"
  sleep 3

  echo "启动 VNC/noVNC..."
  x11vnc -display ":$DISPLAY_NUM" -localhost -rfbport "$VNC_PORT" -passwd "$pass" -forever -shared -noxdamage >>"$LOG" 2>&1 & echo $! >> "$PIDS"
  sleep 1
  websockify --web=/usr/share/novnc/ "$WEB_PORT" "127.0.0.1:$VNC_PORT" >>"$LOG" 2>&1 & echo $! >> "$PIDS"
  sleep 1

  local link="http://$ip:$WEB_PORT/vnc.html?host=$ip&port=$WEB_PORT"
  echo
  echo "临时远程浏览器已启动："
  echo "$link"
  echo "密码：$pass"
  echo
  echo "请用手机打开链接，手动完成 NodeSeek 登录。登录成功后回到这里按 Enter。"

  send_tg "NodeSeek 手动验证入口（临时）：
$link
密码：$pass

请登录完成后回到 VPS 终端按 Enter，脚本会提取 Cookie 并关闭入口。"
}

autofill_credentials() {
  if [ "${NS_MANUAL_AUTOFILL:-true}" != "true" ]; then
    return 0
  fi
  if [ -z "${USER:-}" ] || [ -z "${PASS:-}" ]; then
    return 0
  fi
  "$INSTALL_DIR/venv/bin/python" - <<'PY' || true
import os, time
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
except Exception as e:
    print(f"自动填账号密码依赖不可用，跳过: {e}")
    raise SystemExit(0)

opts = Options()
for b in [os.getenv('CHROME_BIN',''), '/snap/bin/chromium', 'chromium', 'google-chrome']:
    if b and (os.path.exists(b) or b in ['chromium','google-chrome']):
        opts.binary_location = b
        break
opts.add_experimental_option('debuggerAddress', '127.0.0.1:9222')
services = [os.getenv('CHROMEDRIVER_BIN',''), '/snap/bin/chromium.chromedriver', '/usr/bin/chromedriver', 'chromedriver']
last = None
for s in [x for x in services if x]:
    try:
        driver = webdriver.Chrome(service=Service(s), options=opts)
        break
    except Exception as e:
        last = e
else:
    print(f"无法连接浏览器自动填入，跳过: {last}")
    raise SystemExit(0)

def find(selectors):
    for sel in selectors:
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            if el.is_displayed() and el.is_enabled():
                return el
    return None

try:
    for h in driver.window_handles:
        driver.switch_to.window(h)
        if 'nodeseek.com' in driver.current_url:
            break
    time.sleep(1)
    u = find(['#stacked-email','input[name="username"]','input[name="email"]','input[type="email"]','input[type="text"]'])
    p = find(['#stacked-password','input[name="password"]','input[type="password"]'])
    if u and p:
        u.click(); u.clear(); u.send_keys(os.environ['USER'])
        p.click(); p.clear(); p.send_keys(os.environ['PASS'])
        print('已自动填入账号密码，请在远程浏览器里完成验证/点击登录。')
    else:
        print('未找到账号密码输入框，请手动填写。')
except Exception as e:
    print(f"自动填入失败，改为手动填写: {e}")
PY
}

extract_cookie() {
  echo "正在提取 NodeSeek Cookie..."
  "$INSTALL_DIR/venv/bin/python" - <<'PY'
import os, sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

opts = Options()
for b in [os.getenv('CHROME_BIN',''), '/snap/bin/chromium', 'chromium', 'google-chrome']:
    if b and (os.path.exists(b) or b in ['chromium','google-chrome']):
        opts.binary_location = b
        break
opts.add_experimental_option('debuggerAddress', '127.0.0.1:9222')
services = [os.getenv('CHROMEDRIVER_BIN',''), '/snap/bin/chromium.chromedriver', '/usr/bin/chromedriver', 'chromedriver']
last = None
for s in [x for x in services if x]:
    try:
        driver = webdriver.Chrome(service=Service(s), options=opts)
        break
    except Exception as e:
        last = e
else:
    print(f"连接浏览器失败: {last}")
    raise SystemExit(2)

cookies = []
for h in driver.window_handles:
    driver.switch_to.window(h)
    if 'nodeseek.com' in driver.current_url:
        break
for c in driver.get_cookies():
    domain = c.get('domain', '')
    name = c.get('name')
    value = c.get('value')
    if name and value and 'nodeseek.com' in domain:
        cookies.append(f'{name}={value}')

if not cookies:
    print('没有提取到 NodeSeek Cookie，请确认已经登录成功。')
    raise SystemExit(3)

cookie_header = '; '.join(cookies)
import nodeseek_bot as n
os.environ['NS_ENV_FILE'] = os.environ.get('NS_ENV_FILE', os.path.join(os.getcwd(), '.env'))
ok = n.save_cookie_to_local_env('NS_COOKIE', cookie_header)
print(f'Cookie 数量: {len(cookies)}')
print('写回 .env:', 'OK' if ok else 'FAIL')
try:
    status, msg = n.api_sign(cookie_header)
    print('签到接口验证:', status, str(msg)[:120])
except Exception as e:
    print(f'签到接口验证失败，但 Cookie 已保存: {e}')
PY
}

main() {
  need_root_hint
  load_env
  check_deps
  trap cleanup EXIT
  start_browser
  sleep 2
  autofill_credentials
  echo
  read -r -p "登录完成后按 Enter 提取 Cookie；输入 q 回车退出不提取: " ans || true
  if [ "${ans:-}" = "q" ]; then
    echo "已取消提取。"
    exit 0
  fi
  extract_cookie
  send_tg "NodeSeek 手动验证完成：Cookie 已写回 VPS .env。"
  echo "完成。"
}

main "$@"
