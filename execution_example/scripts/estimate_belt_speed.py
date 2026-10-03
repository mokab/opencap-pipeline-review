#!/usr/bin/env python3
"""OpenCap のマーカーデータ (TRC) からトレッドミルのベルト速度と進行方向を推定する。
ベルト速度 = 立脚期（踵・つま先キーポイントの高さが移動最小値の近くにあるフレーム）の水平速度の中央値。
使い方: python3 estimate_belt_speed.py <trc_file> <t0> <t1>
"""
import sys, numpy as np, pandas as pd
p, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
L = open(p, encoding='latin-1').read().splitlines(); hdr = L[3].split('\t')
names = {h.strip(): k for k, h in enumerate(hdr) if h.strip() and k >= 2}
rows = [l.split('\t') for l in L[6:] if l.strip()]
arr = np.array([[float(x) if x.strip() else np.nan for x in r] for r in rows]); t = arr[:, 1]
w = (t >= t0) & (t <= t1)
R = arr[:, names['RHip']:names['RHip']+3]; Lh = arr[:, names['LHip']:names['LHip']+3]
fwd = np.cross(np.array([0, 1, 0]), R - Lh); heading = np.degrees(np.arctan2(-fwd[w, 2], fwd[w, 0]))
print(f'進行方向 (y 軸まわりの回転, 0 = +x) の中央値 {np.median(heading):+.1f} 度')
for n in ['RHeel', 'LHeel', 'RBigToe', 'LBigToe']:
    P = arr[:, names[n]:names[n]+3]; v = np.gradient(P, t, axis=0); y = P[:, 1]
    ymin = pd.Series(y).rolling(120, center=True, min_periods=10).min().values; st = w & (y < ymin + 0.03)
    vh = np.hypot(v[st, 0], v[st, 2])
    print(f'{n:8s} 立脚フレーム {st.sum():4d}: ベルト速度 {np.nanmedian(vh):.3f} m/s (四分位範囲 {np.nanpercentile(vh,25):.3f}-{np.nanpercentile(vh,75):.3f}), vx {np.nanmedian(v[st,0]):+.3f} vz {np.nanmedian(v[st,2]):+.3f}')
for s in range(int(t0), int(t1)):
    ws = (t >= s) & (t < s+1); vals = []
    for n in ['RHeel', 'LHeel', 'RBigToe', 'LBigToe']:
        P = arr[:, names[n]:names[n]+3]; v = np.gradient(P, t, axis=0); y = P[:, 1]
        ymin = pd.Series(y).rolling(120, center=True, min_periods=10).min().values; st = ws & (y < ymin + 0.03)
        vals += list(np.hypot(v[st, 0], v[st, 2]))
    if len(vals) > 5: print(f'  {s:2d}-{s+1:2d} s: {np.nanmedian(vals):.2f} m/s (n={len(vals)})')
