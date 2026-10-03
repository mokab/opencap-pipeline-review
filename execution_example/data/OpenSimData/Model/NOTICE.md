# 筋骨格モデルと形状ファイルの出所

このディレクトリの `LaiUhlrich2022_scaled*.osim` は、OpenCap が配布する筋骨格モデル LaiUhlrich2022（stanfordnmbl/opencap-core の `opensimPipeline/Models/LaiUhlrich2022.osim`、Apache License 2.0。同梱の `LICENSE-opencap-core.txt`）を、OpenCap のクラウド処理で被験者にスケーリングし、OpenSimAD の処理で接触球を付加したものです。Apache License 2.0 の下で再配布し、同梱の `LICENSE-opencap-core.txt` が適用されます。

元のモデルからの変更点: (1) 被験者の身長・体重とニュートラルポーズのマーカー位置によるスケーリング（`LaiUhlrich2022_scaled.osim`）、(2) OpenSimAD の前処理による筋腱パラメータの調整（`*_adjusted.osim`、`*_mtParameters_*.npy`）、(3) 足部への接触球の付加（`*_adjusted_contacts.osim`）。

モデルの credits は次のとおりです。

- Rajagopal, A., Dembia, C. L., DeMers, M. S., Delp, D. D., Hicks, J. L., Delp, S. L. (2016). Full-body musculoskeletal model for muscle-driven simulation of human gait. IEEE Transactions on Biomedical Engineering, 63(10), 2068–2079. モデルは SimTK（https://simtk.org/projects/full_body）で MIT Use Agreement の下に配布されている。
- Lai, A. K. M., Arnold, A. S., Wakeling, J. M. (2017). Why are antagonist muscles co-activated in my simulation? A musculoskeletal model for analysing human locomotor tasks. Annals of Biomedical Engineering, 45(12), 2762–2774. モデルは SimTK（https://simtk.org/projects/model-high-flex）で MIT Use Agreement の下に配布されている。
- Uhlrich, S. D., Jackson, R. W., Seth, A., Kolesar, J. A., Delp, S. L. (2022). Muscle coordination retraining inspired by musculoskeletal simulations reduces knee contact force. Scientific Reports, 12, 9842.（股関節外転筋の経路の修正）

`Geometry/` の .vtp ファイルは、OpenCap のクラウド処理がモデルとともに出力した骨の表示用メッシュで、OpenSim の配布物および上記モデルのパッケージに含まれるものです。表示にのみ用いられ、本リポジトリの計算結果には影響しません。
