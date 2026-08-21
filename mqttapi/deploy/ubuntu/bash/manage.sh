#!/usr/bin/env bash
# Milesight IOT - subscriber.py / api_server.py 手动管理脚本
# 存放位置: /opt/milesight/bash/manage.sh
# 用法: bash manage.sh {start|stop|restart|status} [all|subscriber|api]
# 示例:
#   bash manage.sh start          # 启动 subscriber + api_server
#   bash manage.sh start api      # 只启动 api_server
#   bash manage.sh stop           # 停止全部
#   bash manage.sh restart        # 重启全部
#   bash manage.sh status         # 查看状态

set -u

# ===== 路径（按实际部署修改）=====
PROJECT_ROOT="/opt/milesight/project/MilesightIOTDemo"
MQTTAPI_DIR="${PROJECT_ROOT}/mqttapi"
VENV_BIN="/opt/milesight/venv/bin"

# ===== 脚本自身目录 =====
# 脚本放 /opt/milesight/bash 下，日志与 PID 也放这里
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${SCRIPT_DIR}/run"
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "${RUN_DIR}" "${LOG_DIR}"

SUB_PID="${RUN_DIR}/subscriber.pid"
API_PID="${RUN_DIR}/api_server.pid"
SUB_LOG="${LOG_DIR}/subscriber.log"
API_LOG="${LOG_DIR}/api_server.log"

PYTHON_BIN="${VENV_BIN}/python"

if [ ! -x "${PYTHON_BIN}" ]; then
  echo "[错误] 未找到 ${PYTHON_BIN}，请修改脚本中的 VENV_BIN 路径"
  exit 1
fi

if [ ! -d "${MQTTAPI_DIR}" ]; then
  echo "[错误] 项目目录不存在: ${MQTTAPI_DIR}"
  exit 1
fi

start_one() {
  local name="$1" pid_file="$2" log_file="$3" script="$4"

  if [ -f "${pid_file}" ] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    echo "[${name}] 已在运行 (PID $(cat "${pid_file}"))"
    return 0
  fi

  rm -f "${pid_file}"
  cd "${MQTTAPI_DIR}"
  nohup "${PYTHON_BIN}" -u "${script}" >> "${log_file}" 2>&1 &
  echo $! > "${pid_file}"
  sleep 1
  if kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    echo "[${name}] 已启动 (PID $(cat "${pid_file}"), 日志 ${log_file})"
  else
    echo "[${name}] 启动失败，请查看日志: ${log_file}"
    rm -f "${pid_file}"
    return 1
  fi
}

stop_one() {
  local name="$1" pid_file="$2" match="$3"

  if [ -f "${pid_file}" ] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    local pid
    pid="$(cat "${pid_file}")"
    kill "${pid}" 2>/dev/null
    for _ in $(seq 1 20); do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.5
    done
    if kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null || true
      echo "[${name}] 已强制终止 (PID ${pid})"
    else
      echo "[${name}] 已停止 (PID ${pid})"
    fi
    rm -f "${pid_file}"
  else
    rm -f "${pid_file}"
    echo "[${name}] PID 文件中无运行进程"
  fi

  # 兜底：清理不受本脚本管理的残留同名进程
  local leftover
  leftover="$(pgrep -f "${match}" 2>/dev/null || true)"
  if [ -n "${leftover}" ]; then
    for p in ${leftover}; do
      if [ "${p}" != "$$" ] && [ "${p}" != "${PPID}" ]; then
        kill "${p}" 2>/dev/null || true
        echo "[${name}] 清理残留进程 PID ${p}"
      fi
    done
  fi
}

status_one() {
  local name="$1" pid_file="$2"

  if [ -f "${pid_file}" ] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    echo "[${name}] 运行中 (PID $(cat "${pid_file}"))"
  else
    echo "[${name}] 未运行"
  fi
}

usage() {
  echo "用法: bash manage.sh {start|stop|restart|status} [all|subscriber|api]"
  exit 1
}

CMD="${1:-}"
TARGET="${2:-all}"

case "${TARGET}" in
  all|subscriber|api) ;;
  *) usage ;;
esac

case "${CMD}" in
  start)
    if [ "${TARGET}" = "all" ] || [ "${TARGET}" = "subscriber" ]; then
      start_one "subscriber" "${SUB_PID}" "${SUB_LOG}" "subscriber.py"
    fi
    if [ "${TARGET}" = "all" ] || [ "${TARGET}" = "api" ]; then
      start_one "api_server" "${API_PID}" "${API_LOG}" "api_server.py"
    fi
    ;;
  stop)
    if [ "${TARGET}" = "all" ] || [ "${TARGET}" = "subscriber" ]; then
      stop_one "subscriber" "${SUB_PID}" "subscriber.py"
    fi
    if [ "${TARGET}" = "all" ] || [ "${TARGET}" = "api" ]; then
      stop_one "api_server" "${API_PID}" "api_server.py"
    fi
    ;;
  restart)
    if [ "${TARGET}" = "all" ] || [ "${TARGET}" = "subscriber" ]; then
      stop_one "subscriber" "${SUB_PID}" "subscriber.py"
    fi
    if [ "${TARGET}" = "all" ] || [ "${TARGET}" = "api" ]; then
      stop_one "api_server" "${API_PID}" "api_server.py"
    fi
    sleep 1
    if [ "${TARGET}" = "all" ] || [ "${TARGET}" = "subscriber" ]; then
      start_one "subscriber" "${SUB_PID}" "${SUB_LOG}" "subscriber.py"
    fi
    if [ "${TARGET}" = "all" ] || [ "${TARGET}" = "api" ]; then
      start_one "api_server" "${API_PID}" "${API_LOG}" "api_server.py"
    fi
    ;;
  status)
    if [ "${TARGET}" = "all" ] || [ "${TARGET}" = "subscriber" ]; then
      status_one "subscriber" "${SUB_PID}"
    fi
    if [ "${TARGET}" = "all" ] || [ "${TARGET}" = "api" ]; then
      status_one "api_server" "${API_PID}"
    fi
    ;;
  *)
    usage
    ;;
esac
