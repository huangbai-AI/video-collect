#!/bin/sh
# 幂等启动本地接收器（已在运行则直接返回）。空闲 30 分钟自动退出。
DIR="$(cd "$(dirname "$0")" && pwd)"
curl -sf http://127.0.0.1:8765/ping >/dev/null && { echo "receiver already running"; exit 0; }
nohup python3 "$DIR/store.py" serve --idle 1800 >"${TMPDIR:-/tmp}/video-collect.log" 2>&1 &
for i in 1 2 3 4 5 6 7 8 9 10; do sleep 0.3; curl -sf http://127.0.0.1:8765/ping >/dev/null && { echo "receiver started"; exit 0; }; done
echo "receiver failed to start, see ${TMPDIR:-/tmp}/video-collect.log" >&2; exit 1
