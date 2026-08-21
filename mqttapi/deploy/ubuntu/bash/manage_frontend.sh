#!/usr/bin/env bash
# Milesight IOT Console 前端管理脚本
# 存放位置: /opt/milesight/bash/manage_frontend.sh
# 用法: bash manage_frontend.sh {start|stop|restart|status}
# 示例:
#   bash manage_frontend.sh start      # 启动前端 (npm run dev, vite :3000)
#   bash manage_frontend.sh stop       # 停止前端
#   bash manage_frontend.sh restart    # 重启前端
#   bash manage_frontend.sh status     # 查看状态

set -u

# ===== 路径（按实际部署修改）=====
PROJECT_ROOT="/opt/milesight/project/MilesightIOTDemo"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"

# ===== 脚本自身目录（/opt/milesight/bash）=====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${SCRIPT_DIR}/run"
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "${RUN_DIR}" "${LOG_DIR}"

FE_PID="${RUN_DIR}/frontend.pid"
FE_LOG="${LOG_DIR}/frontend.log"

if [ ! -d "${FRONTEND_DIR}" ]; then
  echo "[错误] 前端目录不存在: ${FRONTEND_DIR}"
  exit 1
fi

# ===== 定位 npm =====
# 依次尝试: 当前 PATH -> nvm 常见路径 -> /usr/local/bin -> /usr/bin
NPM_CMD="$(command -v npm 2>/dev/null || true)"
if [ -z "${NPM_CMD}" ] && [ -s "${HOME}/.nvm/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "${HOME}/.nvm/nvm.sh"
  NPM_CMD="$(command -v npm 2>/dev/null || true)"
fi
if [ -z "${NPM_CMD}" ] && [ -x "/usr/local/bin/npm" ]; then
  NPM_CMD="/usr/local/bin/npm"
fi
if [ -z "${NPM_CMD}" ] && [ -x "/usr/bin/npm" ]; then
  NPM_CMD="/usr/bin/npm"
fi
if [ -z "${NPM_CMD}" ]; then
  echo "[错误] 未找到 npm。请先在服务器执行: command -v npm"
  echo "       然后把下面的 NPM_CMD 改成 npm 的绝对路径"
  exit 1
fi

if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
  echo "[提示] 未找到 node_modules，请先执行: cd ${FRONTEND_DIR} && ${NPM_CMD} install"
fi

start_fe() {
  if [ -f "${FE_PID}" ] && kill -0 "$(cat "${FE_PID}")" 2>/dev/null; then
    echo "[frontend] 已在运行 (PID $(cat "${FE_PID}"))"
    return 0
  fi

  rm -f "${FE_PID}"
  cd "${FRONTEND_DIR}"
  echo "[frontend] 执行: ${NPM_CMD} run dev"
  nohup "${NPM_CMD}" run dev >> "${FE_LOG}" 2>&1 &
  echo $! > "${FE_PID}"
  sleep 3
  if kill -0 "$(cat "${FE_PID}")" 2>/dev/null; then
    echo "[frontend] 已启动 (PID $(cat "${FE_PID}"), 日志 ${FE_LOG})"
    echo "[frontend] 访问: http://<服务器IP>:3000"
  else
    echo "[frontend] 启动失败，请查看日志: ${FE_LOG}"
    tail -20 "${FE_LOG}" 2>/dev/null || true
    rm -f "${FE_PID}"
    return 1
  fi
}

stop_fe() {
  local killed=0
  if [ -f "${FE_PID}" ] && kill -0 "$(cat "${FE_PID}")" 2>/dev/null; then
    local pid
    pid="$(cat "${FE_PID}")"
    kill "${pid}" 2>/dev/null
    for _ in $(seq 1 20); do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.5
    done
    if kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null || true
      echo "[frontend] 已强制终止 (PID ${pid})"
    else
      echo "[frontend] 已停止 (PID ${pid})"
    fi
    killed=1
  fi
  rm -f "${FE_PID}"

  # 兜底：清理残留的 vite / npm run dev 进程
  local leftover
  leftover="$(pgrep -f "vite|npm run dev" 2>/dev/null || true)"
  if [ -n "${leftover}" ]; then
    for p in ${leftover}; do
      if [ "${p}" != "$$" ] && [ "${p}" != "${PPID}" ]; then
        kill "${p}" 2>/dev/null || true
        echo "[frontend] 清理残留进程 PID ${p}"
      fi
    done
    killed=1
  fi

  if [ "${killed}" = "0" ]; then
    echo "[frontend] 未在运行"
  fi
}

status_fe() {
  if [ -f "${FE_PID}" ] && kill -0 "$(cat "${FE_PID}")" 2>/dev/null; then
    echo "[frontend] 运行中 (PID $(cat "${FE_PID}"))"
  else
    local leftover
    leftover="$(pgrep -f "vite|npm run dev" 2>/dev/null || true)"
    if [ -n "${leftover}" ]; then
      echo "[frontend] 运行中（PID 文件失效，实际进程: ${leftover}）"
    else
      echo "[frontend] 未运行"
    fi
  fi
}

usage() {
  echo "用法: bash manage_frontend.sh {start|stop|restart|status}"
  exit 1
}

CMD="${1:-}"

case "${CMD}" in
  start)
    start_fe
    ;;
  stop)
    stop_fe
    ;;
  restart)
    stop_fe
    sleep 1
    start_fe
    ;;
  status)
    status_fe
    ;;
  *)
    usage
    ;;
esac
