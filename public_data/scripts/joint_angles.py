"""公開妥当化データ (Uhlrich et al., 2023) の関節角度の誤差の再分析。

使い方: LABVALIDATION_DIR=/path/to/LabValidation_withoutVideos python3 joint_angles.py [out_dir]
  （データの既定位置は public_data/data/LabValidation_withoutVideos、出力の既定位置は public_data/results）

設定: 被験者 10 名 (subject2〜subject11)、2 カメラ・HRNet 構成。
試行: walking{N}, DJ{N} (N は 1 桁; *TS*, *Asym*, *weakLegs* の変法課題は除外)、squats1, STS1
      → 被験者あたり 歩行 3 + スクワット 1 + 立ち座り 1 + ドロップジャンプ 3 = 8 試行。
関節角度 (6 つ): hip_flexion_{r,l}, knee_angle_{r,l}, ankle_angle_{r,l}。
参照値: マーカー式の逆運動学 (OpenSimData/Mocap/IK)。推定値: OpenSimData/Video/HRNet/2-cameras/IK。
組: 被験者 × 試行 × 関節角度 (480 組)。各組で、1 ms に丸めた共通時刻におけるフレームごとの差
d = 推定値 − 参照値 から バイアス = mean(d)、標準偏差 = sqrt(mean((d − bias)^2))（n で割る定義）、
RMSE = sqrt(mean(d^2)) を求める。この定義では RMSE^2 = bias^2 + SD^2 が恒等的に成り立つ。
試行の除外はなく、一方の系列にしかないフレーム (NaN) のみ除く。
集約: (a) 組ごとの RMSE・バイアス・標準偏差の平均と組間の標準偏差（全体・動作別・関節別）、
      (b) 全フレームをまとめた分解 RMSE^2 = bias^2 + SD^2。
"""
import io, os, re, sys
import numpy as np, pandas as pd
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BASE = Path(os.environ.get('LABVALIDATION_DIR', HERE / 'data' / 'LabValidation_withoutVideos'))
SUBJ = [f'subject{i}' for i in range(2, 12)]
JOINTS = ['hip_flexion_r', 'hip_flexion_l', 'knee_angle_r', 'knee_angle_l', 'ankle_angle_r', 'ankle_angle_l']
PAT = {'walking': re.compile(r'^walking\d$'), 'squats': re.compile(r'^squats1$'),
       'STS': re.compile(r'^STS1$'), 'DJ': re.compile(r'^DJ\d$')}

def read_mot(p):
    lines = open(p, encoding='latin-1').read().splitlines()
    i = [k for k, l in enumerate(lines) if l.strip() == 'endheader'][0]
    df = pd.read_csv(io.StringIO('\n'.join(lines[i + 1:])), sep='\t')
    return df.set_index(df['time'].round(3))

def analyze(base=None):
    """データを読み、組ごとの表 U (480 行)、全フレームの差 F、集約表 S を返す。"""
    base = Path(base) if base else BASE
    units, frames = [], []
    for s in SUBJ:
        mocap = base / s / 'OpenSimData' / 'Mocap' / 'IK'
        video = base / s / 'OpenSimData' / 'Video' / 'HRNet' / '2-cameras' / 'IK'
        for f in sorted(mocap.glob('*.mot')):
            t = f.stem
            if t.endswith('_ik_marker_errors'):
                continue
            act = next((a for a, p in PAT.items() if p.match(t)), None)
            if act is None or not (video / f'{t}.mot').exists():
                continue
            r, v = read_mot(f), read_mot(video / f'{t}.mot')
            ct = r.index.intersection(v.index); r, v = r.loc[ct], v.loc[ct]
            for j in JOINTS:
                d = (v[j] - r[j]).dropna().values
                units.append(dict(subject=s, activity=act, trial=t, joint=j, n=len(d), bias=d.mean(),
                                  sd=d.std(ddof=0), rmse=np.sqrt((d ** 2).mean()), mae=np.abs(d).mean()))
                frames.append(pd.DataFrame({'activity': act, 'joint': j, 'd': d}))
    U = pd.DataFrame(units); F = pd.concat(frames)
    rows = []
    def add(name, g, dd):
        rows.append(dict(group=name, n_units=len(g), n_frames=len(dd),
                         rmse_unit_mean=g.rmse.mean(), rmse_unit_sd=g.rmse.std(),
                         bias_unit_mean=g.bias.mean(), bias_unit_sd=g.bias.std(), absbias_unit_mean=g.bias.abs().mean(),
                         sd_unit_mean=g.sd.mean(), sd_unit_sd=g.sd.std(), mae_unit_mean=g.mae.mean(),
                         rmse_pooled=np.sqrt((dd ** 2).mean()), bias_pooled=dd.mean(), sd_pooled=dd.std(ddof=0)))
    add('all', U, F.d.values)
    for a, g in U.groupby('activity'): add(a, g, F[F.activity == a].d.values)
    for j, g in U.groupby('joint'): add(j, g, F[F.joint == j].d.values)
    S = pd.DataFrame(rows)
    return U, F, S

def main(out_dir):
    U, F, S = analyze()
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    U.to_csv(out / 'joint_angles_units.csv', index=False); S.to_csv(out / 'joint_angles_summary.csv', index=False)
    print(f'被験者 {U.subject.nunique()}  試行 {U.groupby(["subject","trial"]).ngroups}  組 {len(U)}  フレーム {len(F)}')
    print(S.round(3).to_string(index=False))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else HERE / 'results')
