"""逆運動学ファイルと時間窓に対し、スケーリング済み OpenSim モデルを用いて足部接触球の地面からの
最小高さ（球中心の y から半径を引いた値）を計算する。OpenSimAD の Docker イメージ内で実行する。
使い方: python3 contact_height.py <session_dir> <model.osim> <trial> <t0> <t1> [<out.csv>]
"""
import sys, io, numpy as np, pandas as pd, opensim
session, model_file, trial, t0, t1 = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
motfile = trial if trial.endswith('.mot') else f'{session}/OpenSimData/Kinematics/{trial}.mot'
lines = open(motfile, encoding='latin-1').read().splitlines()
i = [k for k, l in enumerate(lines) if l.strip() == 'endheader'][0]
df = pd.read_csv(io.StringIO('\n'.join(lines[i+1:])), sep='\t'); df = df[(df.time >= t0) & (df.time <= t1)]
model = opensim.Model(model_file); state = model.initSystem()
coords = {c.getName(): c for c in model.getCoordinateSet()}
spheres = []
for k in range(model.getContactGeometrySet().getSize()):
    g = model.getContactGeometrySet().get(k); s = opensim.ContactSphere.safeDownCast(g)
    if s: spheres.append((g.getName(), s.getFrame(), s.get_location(), s.getRadius()))
rows = []
for _, r in df.iterrows():
    for name, c in coords.items():
        if name in r:
            v = r[name]; c.setValue(state, np.deg2rad(v) if c.getMotionType() == 1 else v, False)
    model.realizePosition(state)
    per = {}
    for n, fr, loc, rad in spheres:
        p = fr.findStationLocationInGround(state, loc); per[n] = p.get(1) - rad
        per[n + '_x'] = p.get(0); per[n + '_z'] = p.get(2)
    rows.append(per)
H = pd.DataFrame(rows); H.insert(0, 'time', df.time.values)
Hh = H[[c for c in H.columns if not (c.endswith('_x') or c.endswith('_z'))]]
if len(sys.argv) > 6: H.to_csv(sys.argv[6], index=False)
Hn = Hh.drop(columns=['time'])
print(f'{trial} [{t0}-{t1}] 接触球下端の最小高さ (m): 全体 {Hn.min().min():+.4f}; 右 {Hn[[c for c in Hn if c.endswith("_r")]].min().min():+.4f} 左 {Hn[[c for c in Hn if c.endswith("_l")]].min().min():+.4f}')
print('  球ごとの最小値: ' + ', '.join(f'{c} {Hn[c].min():+.3f}' for c in Hn.columns))
print(f'  いずれかの球が 0 より下にあるフレームの割合: {(Hn.min(axis=1) < 0).mean():.2f}; 最下球の高さの中央値 {Hn.min(axis=1).median():+.4f}')
