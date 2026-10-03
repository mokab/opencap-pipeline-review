#!/bin/bash
# OpenSimAD の 1 実行を Docker で起動する（パッケージ内のデータを使用）
# 使い方: scripts/run_docker.sh <run_name> <trial> <belt_speed_m_s> <mesh> <t0> <t1>
# 例    : scripts/run_docker.sh main_mesh50 treadmill_walk01_pre 0.333 50 2 8
set -eu
PKG=$(cd "$(dirname "$0")/.." && pwd)
SESSION=session01   # opencap-processing の Data/ 配下のセッション名 (data/ をこの名前でマウント)
IMAGE=${IMAGE:-bjscs-opencap-opensimad:m1-3}
name=$1; shift
mkdir -p "$PKG/runs/$name"
docker run --rm --name "repro-$name" --cpus 8 -e OPENBLAS_NUM_THREADS=8 -e OMP_NUM_THREADS=8 \
  -v "$PKG/data:/app/opencap-processing/Data/$SESSION" \
  -v "$PKG/scripts:/workspace/scripts" -v "$PKG/runs:/workspace/runs" \
  "$IMAGE" \
  bash -c "python3 -u /workspace/scripts/run_experiment_w.py $name $* > /workspace/runs/$name/stdout.log 2> /workspace/runs/$name/stderr.log"
echo "done: $PKG/runs/$name (outputs in $PKG/data/OpenSimData/Dynamics/<trial>/)"
