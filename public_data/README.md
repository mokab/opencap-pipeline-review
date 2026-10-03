# 公開データの再分析

Uhlrich et al. (2023) の公開妥当化データセットを用いた 2 つの再分析を再現するノートブック、スクリプト、集約結果です。

| ノートブック | 内容 |
|---|---|
| `joint_angles.ipynb` | 関節角度の誤差を「試行内で一定の偏り」と「試行内のばらつき」に分けて動作別・関節別に集計する（10 名、80 試行、480 組） |
| `walking_kinetics.ipynb` | 歩行試行について、公開されている OpenSimAD の出力（床反力・底屈モーメント・筋活動）をフォースプレート・逆動力学・筋電図と対置する（10 名、37 歩） |

各ノートブックは、データの場所の指定、解析の実行（データがある場合）または同梱結果の読み込み、表の再構成、報告値との照合を順に行います。

## 構成

| ディレクトリ / ファイル | 内容 |
|---|---|
| `joint_angles.ipynb`, `walking_kinetics.ipynb` | ノートブック（実行済みの出力つき） |
| `scripts/joint_angles.py` | 関節角度の再分析（`analyze()` をノートブックから呼ぶ。コマンドラインでも実行可） |
| `scripts/walking_kinetics.py` | 歩行の力学量・筋活動の再分析（同上） |
| `results/joint_angles_units.csv` | 480 組それぞれの n、bias、sd、rmse、mae |
| `results/joint_angles_summary.csv` | 全体・動作別・関節別の集約値 |
| `results/walking_kinetics_stances.csv` | 立脚期ごとの指標（37 行） |
| `results/walking_kinetics_summary.csv` | 平均・SD・n（実行例のノートブックがメッシュ密度の比較の参照値として読む） |
| `environment/` | ノートブック用の計算環境（`Dockerfile`, `requirements.txt`, `run_jupyter.sh`） |

## データ

Uhlrich et al. (2023, PLOS Computational Biology, doi:10.1371/journal.pcbi.1011462) の Data Availability に従い、https://simtk.org/projects/opencap から `LabValidation_withoutVideos` を取得してください（本リポジトリには含みません）。`subject2` 〜 `subject11` の各フォルダに次が含まれる状態で配置し、環境変数 `LABVALIDATION_DIR` でその場所を指定します（既定は `public_data/data/LabValidation_withoutVideos`）。

- `OpenSimData/Mocap/IK/*.mot`（光学式モーションキャプチャの逆運動学、参照値）と `OpenSimData/Video/HRNet/2-cameras/IK/*.mot`（OpenCap、2 カメラ・HRNet）: `joint_angles.ipynb` が使用
- `OpenSimData/Video/HRNet/2-cameras/Dynamics/walking_results.npy`（OpenSimAD の出力と参照値）と `EMGData/*_EMG.sto`（筋電図）: `walking_kinetics.ipynb` が使用

## 実行

```bash
# pip 環境
pip install -r environment/requirements.txt
LABVALIDATION_DIR=/path/to/LabValidation_withoutVideos jupyter lab        # ノートブック
LABVALIDATION_DIR=/path/to/LabValidation_withoutVideos python3 scripts/joint_angles.py results      # コマンドライン
LABVALIDATION_DIR=/path/to/LabValidation_withoutVideos python3 scripts/walking_kinetics.py results

# Docker 環境（リポジトリのルートから）
public_data/environment/run_jupyter.sh /path/to/LabValidation_withoutVideos
```

データが手元にない場合、ノートブックは同梱の `results/*.csv` を読み込んで表を再構成します。

## 方法の要点

**関節角度**

- 被験者 10 名 × 8 試行（歩行 3、スクワット 1、立ち座り 1、ドロップジャンプ 3）× 左右の股関節屈曲・膝屈曲・足関節背屈の 6 つの関節角度 = 480 組。
- 各組で、参照値と推定値の時刻を 1 ms 刻みに丸めて同じ時刻のフレームを対応づけ（一方の系列にしかない 132 フレーム、全体の 0.4% を除外）、差 d = OpenCap − MoCap から バイアス = mean(d)、標準偏差 = SD(d)、RMSE = sqrt(mean(d²)) を算出する。標準偏差と RMSE は n で割る定義（`ddof=0`）なので RMSE² = バイアス² + 標準偏差² が恒等的に成り立つ。
- 集約は (a) 組ごとの値の平均と組間の SD（全体・動作別・関節別）、(b) 全フレームをまとめた分解の 2 通り。

**歩行の力学量と筋活動**

- 10 名の通常歩行各 3 試行（体幹動揺条件を除く）の公開出力（メッシュ密度 100、ローパスフィルタ 6 Hz）を用いる。
- 歩行周期の事象は歩行分析で標準とされるフォースプレートの閾値法（Zeni et al. (2008, Gait & Posture 27: 710–714)）で定める。踵接地は鉛直床反力が 20 N を上回った最初の時刻、離地はその後 20 N を下回った最初の時刻、立脚期は踵接地から離地まで（20 N は同文献がトレッドミル歩行で用いた値。各被験者の体重で %BW に換算）。各試行・各脚の最長の立脚期のうち、全体が記録に含まれる（試行の両端に接しない）ものを用いる（29 試行 37 歩: 右 8、左 29）。
- 指標は鉛直床反力の立脚期内平均絶対差とピーク、足関節底屈モーメントの極小の時刻（立脚期の %）と値、ヒラメ筋・腓腹筋内側頭・前脛骨筋（左脚のみ）の活動ピーク時刻、および筋電図と出力の活性化の時系列の試行全体にわたるピアソン相関係数。
- 股関節屈曲モーメントの 10 ms 当たりの変化量の最大値（試行全体。出力と逆動力学）と、その時刻が支持脚の交代（いずれかの足の接地または離地）から 0.1 s 以内にある割合（支持脚の交代時に現れる股関節モーメントのピークの検討に使用）。
