#!/usr/bin/env python3
"""2 つの実行結果（メッシュ密度の異なる解）を重ねて描く。
使い方: python3 make_mesh_overlay.py <run_a> <run_b> <out_dir> <suffix> [<label_a> <label_b>] [--shade t0 t1]
  <run_*> はパッケージの results/<run_name>（outputs/ を含む）。時刻は run_a の解析区間の開始を 0 s とする相対時刻。
  上段: 鉛直床反力の右足・左足・両足の和。下段: 右脚の股関節・膝関節・足関節のモーメント。run_a を実線、run_b を破線で描く。
  --shade を付けると t0〜t1 s を灰色の帯で示す（入力の接地が接触モデルと整合しない区間など）。
  --compact を付けると 2×2（右足・左足の鉛直床反力、右脚の膝・足関節モーメント）に絞る。
  出力: fig_mesh_overlay_<suffix>.pdf と .png
"""
import sys, os, io, glob
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read_mot(path):
    lines = open(path, encoding='latin-1').read().splitlines(); i = [k for k, l in enumerate(lines) if l.strip() == 'endheader'][0]
    df = pd.read_csv(io.StringIO('\n'.join(lines[i+1:])), sep='\t'); return df[[c for c in df.columns if not c.startswith('Unnamed')]]
def load(run_name):
    dyn = run_name if os.path.isdir(os.path.join(run_name, 'outputs')) else os.path.join(PKG, 'results', run_name)
    dyn = os.path.join(dyn, 'outputs'); kin_file = glob.glob(os.path.join(dyn, 'kinematics_activations_*.mot'))[0]
    stem = os.path.basename(kin_file)[len('kinematics_activations_'):-4]; case = os.path.basename(os.path.dirname(dyn)); trial = stem[:-len(case)-1]
    return read_mot(f'{dyn}/GRF_resultant_{trial}_{case}.mot'), read_mot(f'{dyn}/kinetics_{trial}_{case}.mot')
args = [a for a in sys.argv[1:]]; shade = None; compact = False
if '--compact' in args:
    args.remove('--compact'); compact = True
if '--shade' in args:
    i = args.index('--shade'); shade = (float(args[i+1]), float(args[i+2])); del args[i:i+3]
run_a, run_b, out, suf = args[:4]; lab_a, lab_b = (args[4], args[5]) if len(args) >= 6 else ('mesh = 50', 'mesh = 100')
os.makedirs(out, exist_ok=True)
(ga, ka), (gb, kb) = load(run_a), load(run_b); t0 = ga.time.values[0]
plt.rcParams.update({'font.size': 9, 'axes.titlesize': 10, 'axes.labelsize': 9})
ncol = 2 if compact else 3
fig, ax = plt.subplots(2, ncol, figsize=(7.2 if compact else 10, 5.6))
def band(a):
    if shade: a.axvspan(shade[0], shade[1], color='0.92', zorder=0)
tops = [('ground_force_right_vy', 'Vertical GRF (R)'), ('ground_force_left_vy', 'Vertical GRF (L)')] + ([] if compact else [(None, 'Vertical GRF (R + L)')])
for c, (col, lab) in enumerate(tops):
    a = ax[0, c]; band(a)
    for g, l, st in [(ga, lab_a, dict(color='k', lw=1.1)), (gb, lab_b, dict(color='k', ls='--', lw=1.1))]:
        y = g[col] if col else g['ground_force_right_vy'] + g['ground_force_left_vy']
        a.plot(g.time.values - t0, y, label=l, **st)
    a.set_title(lab); a.set_xlabel('Time (s)'); a.set_ylabel('Force (N)'); a.grid(alpha=.3)
    if c == 0: a.legend(fontsize=8, loc='upper right')
moms = [('knee_angle', 'Knee (R)'), ('ankle_angle', 'Ankle (R)')] if compact else [('hip_flexion', 'Hip flexion (R)'), ('knee_angle', 'Knee (R)'), ('ankle_angle', 'Ankle (R)')]
for c, (j, lab) in enumerate(moms):
    a = ax[1, c]; band(a)
    for k, st in [(ka, dict(color='k', lw=1.1)), (kb, dict(color='k', ls='--', lw=1.1))]:
        a.plot(k.time.values - t0, k[f'{j}_r_moment'], **st)
    a.axhline(0, ls='--', color='0.7', lw=.8); a.set_title(lab); a.set_xlabel('Time (s)'); a.set_ylabel('Moment (Nm)'); a.grid(alpha=.3)
fig.tight_layout(); fig.savefig(os.path.join(out, f'fig_mesh_overlay_{suf}.pdf')); fig.savefig(os.path.join(out, f'fig_mesh_overlay_{suf}.png'), dpi=150)
print('図を書き出しました:', os.path.join(out, f'fig_mesh_overlay_{suf}.pdf'))
