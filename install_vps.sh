#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/vmenzo/NodeSeek-Bot.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/NodeSeek-Bot}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CRON_TIMEZONE="${CRON_TIMEZONE:-Asia/Shanghai}"
MODE="${1:-install}"

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "请用 root 运行：sudo bash install_vps.sh"
    exit 1
  fi
}

ask() {
  local var="$1"
  local prompt="$2"
  local default="${3:-}"
  local secret="${4:-false}"
  local value=""
  if [ "$secret" = "true" ]; then
    if [ -n "$default" ]; then
      read -r -s -p "$prompt [已存在，回车保留]: " value || true
    else
      read -r -s -p "$prompt: " value || true
    fi
    echo
  else
    if [ -n "$default" ]; then
      read -r -p "$prompt [$default]: " value || true
    else
      read -r -p "$prompt: " value || true
    fi
  fi
  if [ -z "$value" ]; then
    value="$default"
  fi
  printf -v "$var" '%s' "$value"
}

quote_env() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

load_existing_env() {
  if [ -f "$INSTALL_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$INSTALL_DIR/.env"
    set +a
  fi
}

install_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y git python3 python3-venv python3-pip curl ca-certificates xvfb fonts-wqy-zenhei

  if ! command -v google-chrome >/dev/null 2>&1 && ! command -v chromium >/dev/null 2>&1; then
    apt-get install -y chromium || true
  fi
}

install_repo() {
  mkdir -p "$(dirname "$INSTALL_DIR")"
  if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull --ff-only
  elif [ -e "$INSTALL_DIR" ]; then
    echo "$INSTALL_DIR 已存在但不是 git 仓库，请先处理后重试。"
    exit 1
  else
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
}

install_python_deps() {
  cd "$INSTALL_DIR"
  "$PYTHON_BIN" -m venv venv
  ./venv/bin/pip install --upgrade pip
  ./venv/bin/pip install -r requirements.txt
}

write_env() {
  local has_existing_env="false"
  [ -f "$INSTALL_DIR/.env" ] && has_existing_env="true"
  load_existing_env
  echo
  echo "开始填写 NodeSeek Bot 配置。已有 .env 时直接回车会保留原值。"
  echo

  local default_ns_user=""
  if [ "$has_existing_env" = "true" ]; then
    default_ns_user="${USER:-}"
  fi

  ask NS_USER "NodeSeek 用户名 USER" "$default_ns_user"
  ask NS_PASS "NodeSeek 密码 PASS" "${PASS:-}" true
  ask NS_COOKIE_VALUE "NS_COOKIE，可先留空，或粘贴当前 Cookie" "${NS_COOKIE:-}" true

  ask SOLVER_TYPE_VALUE "验证码平台 SOLVER_TYPE" "${SOLVER_TYPE:-yescaptcha}"
  ask API_BASE_URL_VALUE "验证码 API_BASE_URL" "${API_BASE_URL:-https://api.yescaptcha.com}"
  ask CLIENTT_KEY_VALUE "验证码 CLIENTT_KEY" "${CLIENTT_KEY:-}" true

  ask NS_TOTP_SECRET_VALUE "两步验证 NS_TOTP_SECRET，填二维码背后的字母 secret，不是6位数字；没有就留空" "${NS_TOTP_SECRET:-}" true
  ask NS_TOTP_FIELD_VALUE "2FA 字段 NS_TOTP_FIELD，不懂就回车" "${NS_TOTP_FIELD:-otp}"
  ask NS_TOTP_FIELDS_VALUE "2FA 候选字段 NS_TOTP_FIELDS，不懂就回车" "${NS_TOTP_FIELDS:-otp,code,totp,twoFactorCode,two_factor_code,mfaCode}"

  ask TG_BOT_TOKEN_VALUE "Telegram Bot Token" "${TG_BOT_TOKEN:-}" true
  ask TG_CHAT_ID_VALUE "Telegram Chat ID" "${TG_CHAT_ID:-${TG_USER_ID:-}}"

  ask NS_COMMENT_VALUE "是否开启自动评论 NS_COMMENT，建议先 false" "${NS_COMMENT:-false}"
  ask NS_COMMENT_URL_VALUE "评论区 URL" "${NS_COMMENT_URL:-https://www.nodeseek.com/categories/trade}"
  ask RUN_TIMES_VALUE "每天运行时间，逗号分隔，24小时制" "00:05,12:05"

  cat > "$INSTALL_DIR/.env" <<EOF
USER=$(quote_env "$NS_USER")
PASS=$(quote_env "$NS_PASS")
NS_COOKIE=$(quote_env "$NS_COOKIE_VALUE")

SOLVER_TYPE=$(quote_env "$SOLVER_TYPE_VALUE")
API_BASE_URL=$(quote_env "$API_BASE_URL_VALUE")
CLIENTT_KEY=$(quote_env "$CLIENTT_KEY_VALUE")

NS_TOTP_SECRET=$(quote_env "$NS_TOTP_SECRET_VALUE")
NS_TOTP_FIELD=$(quote_env "$NS_TOTP_FIELD_VALUE")
NS_TOTP_FIELDS=$(quote_env "$NS_TOTP_FIELDS_VALUE")

TG_BOT_TOKEN=$(quote_env "$TG_BOT_TOKEN_VALUE")
TG_CHAT_ID=$(quote_env "$TG_CHAT_ID_VALUE")
TG_USER_ID=$(quote_env "$TG_CHAT_ID_VALUE")

GH_PAT=""
GITHUB_REPOSITORY="vmenzo/NodeSeek-Bot"

NS_COMMENT=$(quote_env "$NS_COMMENT_VALUE")
NS_COMMENT_URL=$(quote_env "$NS_COMMENT_URL_VALUE")
NS_DELAY_MIN="0"
NS_DELAY_MAX="0"
HEADLESS="false"
NS_RANDOM="true"
EOF
  chmod 600 "$INSTALL_DIR/.env"
  printf '%s' "$RUN_TIMES_VALUE" > "$INSTALL_DIR/.run_times"
}

write_runner() {
  cat > "$INSTALL_DIR/run.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export NS_ENV_FILE="$(pwd)/.env"
set -a
. ./.env
set +a
. ./venv/bin/activate
if [ "${NS_COMMENT:-false}" = "false" ]; then
  python nodeseek_bot.py
else
  xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python nodeseek_bot.py
fi
EOF
  chmod +x "$INSTALL_DIR/run.sh"
}

install_cron() {
  timedatectl set-timezone "$CRON_TIMEZONE" 2>/dev/null || true
  local times
  times="$(cat "$INSTALL_DIR/.run_times")"
  local tmp
  tmp="$(mktemp)"
  crontab -l 2>/dev/null | grep -v '# NodeSeek-Bot' | grep -v "$INSTALL_DIR/run.sh" > "$tmp" || true

  IFS=',' read -ra parts <<< "$times"
  for t in "${parts[@]}"; do
    t="${t// /}"
    [ -z "$t" ] && continue
    local hh mm
    hh="${t%%:*}"
    mm="${t##*:}"
    if ! [[ "$hh" =~ ^[0-9]{1,2}$ && "$mm" =~ ^[0-9]{1,2}$ ]] || [ "$hh" -gt 23 ] || [ "$mm" -gt 59 ]; then
      echo "跳过非法时间: $t"
      continue
    fi
    echo "$mm $hh * * * $INSTALL_DIR/run.sh >> $INSTALL_DIR/run.log 2>&1 # NodeSeek-Bot" >> "$tmp"
  done
  crontab "$tmp"
  rm -f "$tmp"
}

show_usage() {
  cat <<EOF
用法：
  bash install_vps.sh              安装/重配，交互填写变量并写入 cron
  bash install_vps.sh --update     仅更新代码和 Python 依赖，不修改 .env/cron
  bash install_vps.sh --help       显示帮助
EOF
}

main() {
  case "$MODE" in
    install|--install)
      need_root
      install_packages
      install_repo
      install_python_deps
      write_env
      write_runner
      install_cron

      echo
      echo "安装完成。"
      ;;
    update|--update)
      need_root
      install_packages
      install_repo
      install_python_deps
      write_runner

      echo
      echo "更新完成。未修改 .env 和 cron。"
      ;;
    help|-h|--help)
      show_usage
      exit 0
      ;;
    *)
      echo "未知参数: $MODE"
      show_usage
      exit 1
      ;;
  esac

  echo "目录: $INSTALL_DIR"
  echo "配置: $INSTALL_DIR/.env"
  echo "日志: $INSTALL_DIR/run.log"
  echo
  echo "手动测试命令："
  echo "  $INSTALL_DIR/run.sh"
  echo
  echo "看日志："
  echo "  tail -f $INSTALL_DIR/run.log"
  echo
  echo "当前定时任务："
  crontab -l | grep 'NodeSeek-Bot' || true
}

main "$@"
