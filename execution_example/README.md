# 実行例の再現パッケージ

実行例（トレッドミル歩行 6 秒間の direct collocation による筋活動・床反力推定）とその整合性確認・メッシュ密度の比較を再現するための資料一式です。

**主のエントリは `reproduce_example.ipynb` です。** 入力データの確認、前処理、OpenSimAD の実行手順、結果の評価と整合性確認、メッシュ密度の比較、図の再生成、ファイルの完全性確認をノートブック上で順に行えます。

## 構成

| ディレクトリ / ファイル | 内容 |
|---|---|
| `reproduce_example.ipynb` | 主ノートブック（実行済みの出力つき） |
| `environment/Dockerfile` | OpenSimAD の計算環境（`stanfordnmbl/opensim-python:4.5` に opencap-processing を導入） |
| `environment/git_hashes.yaml`, `versions.yaml` | 使用した opencap-processing のコミットとライブラリのバージョン |
| `data/sessionMetadata.yaml` | 被験者情報（身長 1.75 m、体重 83 kg）、モデル、姿勢推定器 |
| `data/OpenSimData/Model/` | スケーリング済みモデル（`LaiUhlrich2022_scaled*.osim`）と形状ファイル |
| `data/OpenSimData/Kinematics/treadmill_walk01.mot` | 逆運動学結果（OpenCap クラウド処理の出力）。0〜10 s で、解析区間はその 2〜8 s |
| `data/OpenSimData/Kinematics/treadmill_walk01_pre.mot` | 前処理後（`scripts/preprocess_ik.py` で再生成でき、同一であることをノートブックで確認） |
| `data/MarkerData/treadmill_walk01.trc` | 3D キーポイントと拡張マーカー（ベルト速度・進行方向の推定に使用）。0〜10 s |
| `videos/` | 同期後の動画（両カメラ、360×640、60 fps）。入力データと同じ 0〜10 s で、時刻は逆運動学の `time` 列と対応する |
| `scripts/` | 前処理・ベルト速度推定・実行・評価・比較・作図のスクリプト（下記） |
| `results/<run>/` | 各実行の設定（`settings_full.yaml`）、IPOPT オプション、バージョン、ログ（`stdout.log`）、出力（`outputs/`）、評価（`eval/`） |
| `figures/` | ノートブックが再生成した図（床反力、関節モーメント、筋活動、ヒラメ筋: `*_main`。mesh 50 と 100 の重ね描き: `fig_mesh_overlay_50_100`） |
| `MANIFEST.sha256` | `data/`, `results/`, `videos/`, `scripts/`, `environment/`, `README.md` の SHA-256 |

## 実行一覧（`results/`）

| 名前 | 内容 | 試行 | ベルト速度 | mesh | 窓 (s) |
|---|---|---|---|---|---|
| `main_mesh50` | 主の実行例（図と整合性確認の対象） | treadmill_walk01_pre | 0.333 m/s（表示 1.2 km/h） | 50 | 2–8 |
| `repeat_mesh50` | 同一設定の再実行（決定変数まで完全一致） | 同上 | 同上 | 50 | 2–8 |
| `mesh25`, `mesh100` | メッシュ密度の比較。`mesh25` は 3000 反復の時点で終了条件を満たさず停止（ログのみ） | 同上 | 同上 | 25, 100 | 2–8 |
| `control_belt0` | 対照: ベルト速度 0 で解いた場合。形式上は終了条件を満たすが、足を静止地面に止めた解で、追跡誤差が膝 27〜30°、鉛直床反力のピークが 2.4〜2.6 BW | 同上 | 0 | 50 | 2–6 |

## 手順の要点

1. **前処理**（Docker 不要）: `python3 scripts/preprocess_ik.py data/OpenSimData/Kinematics treadmill_walk01 --rot 90 --dy 0.19 --clip 33 --suffix _pre`
   - 進行方向を +x に回転（OpenSimAD のベルトは x 軸方向に動く）
   - 骨盤鉛直位置からデッキ高さ 0.19 m を差し引く（OpenCap の高さ基準が床面だったため）
   - 距骨下関節角を ±33° に丸める（6 Hz フィルタ後に可動域 ±35° を超えないため）
2. **最適化**（Docker）: `docker build -t bjscs-opencap-opensimad:m1-3 environment/` の後、`scripts/run_docker.sh main_mesh50 treadmill_walk01_pre 0.333 50 2 8`
   - 目安（8 コア割当、他の最適化と並列実行した場合）: mesh 50 で約 4 時間・メモリ約 17 GB、mesh 100 で約 5.5 時間・約 37 GB
3. **評価・作図**（Docker 不要。ノートブックの第 5〜9 節、または次のスクリプト）
   - `python3 scripts/evaluate_w.py main_mesh50`（`results/main_mesh50/eval/` に数値と図）
   - `python3 scripts/compare_w.py --out cmp main=results/main_mesh50/outputs:treadmill_walk01_pre:main_mesh50 mesh100=results/mesh100/outputs:treadmill_walk01_pre:mesh100`
   - `python3 scripts/make_paper_figs.py main_mesh50 figures main rel`（床反力・関節モーメント・筋活動・ヒラメ筋の図）
   - `python3 scripts/make_mesh_overlay.py main_mesh50 mesh100 figures 50_100 --shade 3.8 4.4 --compact`（mesh 50 を実線、100 を破線で重ね描き。灰色の帯は入力の接地が接触モデルの前提を満たさない 3.8–4.4 s。`--compact` なしで股関節と両足の和のパネルも出力）

ノートブックの第 7 節は、整合性確認の条件 (i)(ii)、追跡誤差、立脚期ごとの主要出力の範囲を各メッシュ密度について算出し、公開データの参照値（`../public_data/results/walking_kinetics_summary.csv`）と並べて表示します。

## 注意

- 同一環境（同じ Docker イメージ）では再実行で同一の解が得られます。環境（ソルバや線形代数ライブラリのバージョン）が異なると、反復経路と到達する局所解が変わりえます。
- `scripts/run_docker.sh` はコンテナを root で実行するため、`runs/` と `data/OpenSimData/Dynamics/` に root 所有のファイルが作られます。削除や編集には `sudo chown -R $(id -u):$(id -g) runs data` のように所有者を変更してください。
- 動画の時間軸は逆運動学の時刻と対応します。
- 接触球の高さの確認（`scripts/contact_height.py`）は OpenSim の Python API を使うため Docker 内で実行します。
- ノートブックの評価・作図部分は `../public_data/environment/Dockerfile` の環境（Python 3 と numpy, pandas, matplotlib, pyyaml）でも実行できます。
