#!/usr/bin/env python3
"""OpenCap の逆運動学結果を OpenSimAD のトレッドミル追跡用に前処理する。

入力と同じディレクトリに <trial><suffix>.mot を書き出す。処理は次の 3 段階で、いずれも決定的である。
  1. 骨盤の並進・回旋を鉛直 (y) 軸まわりに ROT_DEG 回転し、進行方向を +x に揃える
     （OpenSimAD のトレッドミルベルトは x 軸方向に動く）
  2. pelvis_ty から DY を差し引く（OpenCap は床面を高さ 0 としており、トレッドミルのデッキは DY だけ高い）
  3. subtalar_angle_r/l を ±CLIP 度に丸め、OpenSimAD の 6 Hz ローパスフィルタ後に
     モデル可動域 (±35 度) を超えないようにする
変更する列は pelvis_tx, pelvis_tz, pelvis_rotation, pelvis_ty, subtalar_angle_r/l のみ。

使い方:
  python3 preprocess_ik.py <kinematics_dir> treadmill_walk01 --rot 90 --dy 0.19 --clip 33 --suffix _pre   # 主例
  python3 preprocess_ik.py <kinematics_dir> treadmill_walk02 --rot 90 --dy 0    --clip 33 --suffix _pre   # 別試行
"""
import argparse, io, numpy as np, pandas as pd
from pathlib import Path

def read_mot(p):
    lines = open(p, encoding='latin-1').read().splitlines()
    i = [k for k, l in enumerate(lines) if l.strip() == 'endheader'][0]
    return lines[:i+1], pd.read_csv(io.StringIO('\n'.join(lines[i+1:])), sep='\t')

def write_mot(header, df, p):
    with open(p, 'w', encoding='latin-1') as f:
        for l in header:
            if l.startswith('nColumns'): l = f'nColumns={df.shape[1]}'
            if l.startswith('nRows'): l = f'nRows={len(df)}'
            f.write(l + '\n')
        df.to_csv(f, sep='\t', index=False, float_format='%.8f', lineterminator='\n')

def rot_y(x, z, deg):
    th = np.deg2rad(deg); return x*np.cos(th) + z*np.sin(th), -x*np.sin(th) + z*np.cos(th)

ap = argparse.ArgumentParser(); ap.add_argument('kin_dir'); ap.add_argument('trial')
ap.add_argument('--rot', type=float, default=90.0); ap.add_argument('--dy', type=float, default=0.0)
ap.add_argument('--clip', type=float, default=33.0); ap.add_argument('--suffix', default='rcy')
a = ap.parse_args()
src = Path(a.kin_dir) / f'{a.trial}.mot'; dst = Path(a.kin_dir) / f'{a.trial}{a.suffix}.mot'
hdr, df = read_mot(src); out = df.copy()
out['pelvis_tx'], out['pelvis_tz'] = rot_y(df['pelvis_tx'].values, df['pelvis_tz'].values, a.rot)
out['pelvis_rotation'] = ((df['pelvis_rotation'].values + a.rot) + 180) % 360 - 180
out['pelvis_ty'] = df['pelvis_ty'] - a.dy
for c in ['subtalar_angle_r', 'subtalar_angle_l']:
    out[c] = df[c].clip(-a.clip, a.clip)
write_mot(hdr, out, dst)
clip_info = []
for c in ['subtalar_angle_r', 'subtalar_angle_l']:
    d = (out[c] - df[c]).abs(); n = int((d > 0).sum())
    clip_info.append(f'{c} 丸めたフレーム {n}/{len(df)} ({100*n/len(df):.1f}%)' + (f', 角度変化量 {d[d > 0].min():.2f}-{d.max():.2f} 度' if n else ''))
print(f'{src.name} -> {dst.name}: 回転 {a.rot:+.0f} 度, pelvis_ty {-a.dy:+.2f} m, 距骨下関節角を ±{a.clip} 度に丸め; '
      f'pelvis_rotation の中央値 {np.median(out.pelvis_rotation):+.1f} 度 (処理前 {np.median(df.pelvis_rotation):+.1f})')
print('  ' + '; '.join(clip_info))
