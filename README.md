# opencap-pipeline-review

OpenCap と OpenSimAD によるマーカーレス動作計測と筋骨格動力学推定のパイプラインに関する総説の補足資料です。著者のトレッドミル歩行データに対する実行例と、公開妥当化データセットの再分析を再現するためのデータ・スクリプト・ノートブック・結果・計算環境を収めています。

## 構成

| ディレクトリ | 内容 | ノートブック |
|---|---|---|
| `execution_example/` | 実行例（著者のトレッドミル歩行データに対する direct collocation）。入力データ、前処理・実行・評価・作図スクリプト、OpenSimAD の計算環境（Docker）、各実行の設定・ログ・出力、SHA-256 マニフェスト | `reproduce_example.ipynb` |
| `public_data/` | 公開妥当化データセット（Uhlrich et al., 2023）の再分析。スクリプト、集約結果、ノートブック用の計算環境（Docker） | `joint_angles.ipynb`: 関節角度の誤差の偏りとばらつき<br>`walking_kinetics.ipynb`: 歩行の力学量と筋活動の妥当性検討 |

3 つのノートブックはそれぞれ単独で実行できます（実行例のノートブックはメッシュ密度の比較の参照値として `public_data/results/walking_kinetics_summary.csv` を読みます）。いずれも実行済みの出力を含めて保存しているため、データや Docker がなくても結果を閲覧できます。詳細は各ディレクトリの `README.md` を参照してください。

## 計算環境

| 用途 | 環境 |
|---|---|
| ノートブックの実行（公開データの再分析、実行例の評価・作図） | Python 3 と `numpy`, `pandas`, `matplotlib`, `pyyaml`, `jupyterlab`（`public_data/environment/requirements.txt`）。同じ環境を `public_data/environment/Dockerfile` で構築でき、`public_data/environment/run_jupyter.sh` が JupyterLab を起動します。リポジトリ全体をマウントするため、実行例のノートブックも同じ環境で動きます |
| 実行例の最適化（OpenSimAD）の再実行 | `execution_example/environment/Dockerfile`（`stanfordnmbl/opensim-python:4.5` に opencap-processing を導入）。`execution_example/scripts/run_docker.sh` で 1 実行を起動します。実行済みの出力を同梱しているため、評価と作図だけなら不要です |

公開データは Uhlrich et al. (2023) の Data Availability に記載の https://simtk.org/projects/opencap から `LabValidation_withoutVideos` を取得し、環境変数 `LABVALIDATION_DIR` で場所を指定します（本リポジトリには含みません）。データがない場合、ノートブックは同梱の `results/*.csv` を読み込みます。

```bash
# ノートブック環境を Docker で起動する例（公開データの場所を引数に与える。省略可）
public_data/environment/run_jupyter.sh /path/to/LabValidation_withoutVideos
# 3 つのノートブックを順に実行して出力を書き戻す
public_data/environment/run_jupyter.sh /path/to/LabValidation_withoutVideos --execute
```

## データとライセンス

| 対象 | ライセンス |
|---|---|
| 著者が作成したスクリプト・ノートブック・README、および著者自身を被験者として取得した動作データ（`execution_example/data/` の逆運動学結果・マーカー・`sessionMetadata.yaml`・`videos/`）と各実行の設定・ログ・出力・評価 | MIT License（`LICENSE`） |
| 筋骨格モデル `execution_example/data/OpenSimData/Model/LaiUhlrich2022_scaled*.osim` と `Geometry/` | OpenCap が配布する LaiUhlrich2022 モデル（stanfordnmbl/opencap-core、Apache License 2.0）を被験者にスケーリングし接触球を付加した派生物。Apache License 2.0 のまま再配布し、ライセンスの写し `LICENSE-opencap-core.txt` と出所・変更点を記した `NOTICE.md` を同じディレクトリに置く。元になった Rajagopal et al. (2016) と Lai et al. (2017) のモデルは SimTK で MIT Use Agreement の下に配布されている |
| `public_data/results/` の集約結果 | Uhlrich et al. (2023, PLOS Computational Biology, doi:10.1371/journal.pcbi.1011462) が SimTK で Apache 2.0 Use Agreement の下に公開する妥当化データセットから著者が算出した結果の値。MIT License で提供するが、元データの出典を明記すること。元データ自体は本リポジトリに含まない。 |
| `execution_example/environment/Dockerfile` | ビルド時に opencap-processing（Stanford Neuromuscular Biomechanics Lab、Apache License 2.0）と公開パッケージを取得する。本リポジトリにはそれらのコードを含まない |

MIT License は著者の著作物に適用され、上記の第三者の著作物にはそれぞれのライセンスが適用されます。
