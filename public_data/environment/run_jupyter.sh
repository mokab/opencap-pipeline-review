#!/bin/bash
# ノートブック用の Docker 環境を構築して JupyterLab を起動する（リポジトリ全体を /work にマウント）。
# 使い方: public_data/environment/run_jupyter.sh [/path/to/LabValidation_withoutVideos]
#   引数に公開データの場所を与えると /data/LabValidation_withoutVideos に読み取り専用でマウントし、
#   環境変数 LABVALIDATION_DIR を設定する。省略した場合、ノートブックは同梱の results/*.csv を読む。
#   起動後 http://localhost:8888 を開く。
# ノートブックをまとめて実行だけしたい場合（出力を書き戻す）:
#   public_data/environment/run_jupyter.sh [/path/to/LabValidation_withoutVideos] --execute
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
IMAGE=${IMAGE:-opencap-pipeline-review-notebooks}
docker build -t "$IMAGE" "$ROOT/public_data/environment"
# 書き出すファイルの所有者をホストのユーザーに合わせる
ARGS=(-v "$ROOT:/work" --user "$(id -u):$(id -g)" -e HOME=/tmp)
EXEC=0
for a in "$@"; do
  if [ "$a" = "--execute" ]; then EXEC=1
  else ARGS+=(-v "$(cd "$a" && pwd):/data/LabValidation_withoutVideos:ro" -e LABVALIDATION_DIR=/data/LabValidation_withoutVideos)
  fi
done
if [ "$EXEC" = 1 ]; then
  docker run --rm "${ARGS[@]}" "$IMAGE" bash -c '
    set -e
    for nb in public_data/joint_angles.ipynb public_data/walking_kinetics.ipynb execution_example/reproduce_example.ipynb; do
      echo "== $nb"; (cd "$(dirname $nb)" && jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 "$(basename $nb)")
    done'
else
  docker run --rm -p 8888:8888 "${ARGS[@]}" "$IMAGE"
fi
