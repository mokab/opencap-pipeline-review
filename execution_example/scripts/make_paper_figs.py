#!/usr/bin/env python3
"""1 つの実行結果から床反力・関節モーメント・筋活動・ヒラメ筋の 4 図 (PDF と PNG) を生成する。
使い方: python3 make_paper_figs.py <run_name> <out_dir> <suffix> [rel]
  rel を付けると解析区間の開始を 0 s とする相対時刻で描く。
  <run_name> はパッケージの results/<run_name>（outputs/ を含む）。
  出力: fig_grf_<suffix>, fig_joint_moments_<suffix>, fig_muscle_activations_<suffix>, fig_soleus_<suffix> (.pdf と .png)
"""
import sys, os, io, glob
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read_mot(path):
    lines = open(path, encoding='latin-1').read().splitlines(); i = [k for k, l in enumerate(lines) if l.strip() == 'endheader'][0]
    df = pd.read_csv(io.StringIO('\n'.join(lines[i+1:])), sep='\t'); return df[[c for c in df.columns if not c.startswith('Unnamed')]]
run_name, out, suf = sys.argv[1], sys.argv[2], sys.argv[3]; os.makedirs(out, exist_ok=True)
rel = len(sys.argv) > 4 and sys.argv[4] == 'rel'
dyn = run_name if os.path.isdir(os.path.join(run_name, 'outputs')) else os.path.join(PKG, 'results', run_name)
dyn = os.path.join(dyn, 'outputs')
kin_file = glob.glob(os.path.join(dyn, 'kinematics_activations_*.mot'))[0]
stem = os.path.basename(kin_file)[len('kinematics_activations_'):-4]   # <trial>_<case>
case = os.path.basename(os.path.dirname(dyn)); trial = stem[:-len(case)-1]
grf = read_mot(f'{dyn}/GRF_resultant_{trial}_{case}.mot'); kin = read_mot(f'{dyn}/kinematics_activations_{trial}_{case}.mot'); kt = read_mot(f'{dyn}/kinetics_{trial}_{case}.mot')
t0 = grf.time.values[0] if rel else 0.0   # 相対時刻の原点
t = grf.time.values - t0; tk = kt.time.values - t0; ta = kin.time.values - t0
plt.rcParams.update({'font.size': 9, 'axes.titlesize': 10, 'axes.labelsize': 9})
def save(fig, name):
    fig.tight_layout(); fig.savefig(os.path.join(out, f'{name}_{suf}.pdf')); fig.savefig(os.path.join(out, f'{name}_{suf}.png'), dpi=150); plt.close(fig)
# 床反力 3 成分, 右 (黒) と左 (灰)
fig, ax = plt.subplots(1, 3, figsize=(10, 3.0))
for i, (comp, lab) in enumerate([('vy', 'Vertical'), ('vx', 'Anterior-posterior'), ('vz', 'Medio-lateral')]):
    ax[i].plot(t, grf[f'ground_force_right_{comp}'], 'k', lw=1.1, label='Right'); ax[i].plot(t, grf[f'ground_force_left_{comp}'], 'k', ls='--', lw=1.1, label='Left')
    ax[i].set_title(lab); ax[i].set_xlabel('Time (s)'); ax[i].set_ylabel('Force (N)'); ax[i].grid(alpha=.3)
    if i == 0: ax[i].legend(fontsize=8, loc='lower right')
save(fig, 'fig_grf')
# 関節モーメント, 上段 右脚, 下段 左脚
fig, ax = plt.subplots(2, 3, figsize=(10, 5.6))
for r, side in enumerate(['r', 'l']):
    for c, (j, lab) in enumerate([('hip_flexion', 'Hip flexion'), ('knee_angle', 'Knee'), ('ankle_angle', 'Ankle')]):
        ax[r, c].plot(tk, kt[f'{j}_{side}_moment'], 'k', lw=1.1); ax[r, c].axhline(0, ls='--', color='0.7', lw=.8)
        ax[r, c].set_title(f'{lab} ({"R" if side == "r" else "L"})'); ax[r, c].set_xlabel('Time (s)'); ax[r, c].set_ylabel('Moment (Nm)'); ax[r, c].grid(alpha=.3)
# 左右で縦軸の範囲を関節ごとに揃える
for c in range(3):
    lo = min(ax[r, c].get_ylim()[0] for r in range(2)); hi = max(ax[r, c].get_ylim()[1] for r in range(2))
    for r in range(2): ax[r, c].set_ylim(lo, hi)
save(fig, 'fig_joint_moments')
# 右脚 9 筋 (モノクロ: 灰色の塗りと黒線)
M9 = [('soleus_r', 'Soleus (R)'), ('gasmed_r', 'Gastrocnemius Med (R)'), ('tibant_r', 'Tibialis Ant (R)'),
      ('vasmed_r', 'Vastus Med (R)'), ('recfem_r', 'Rectus Femoris (R)'), ('bflh_r', 'Biceps Femoris LH (R)'),
      ('glmed1_r', 'Gluteus Med (R)'), ('glmax1_r', 'Gluteus Max (R)'), ('psoas_r', 'Psoas (R)')]
fig, ax = plt.subplots(3, 3, figsize=(10, 7.5))
for i, (m, lab) in enumerate(M9):
    a = ax[i//3, i%3]; y = kin[f'{m}/activation']
    a.fill_between(ta, 0, y, color='0.85'); a.plot(ta, y, color='k', lw=.9)
    a.set_ylim(0, 1); a.set_title(lab); a.set_xlabel('Time (s)'); a.set_ylabel('Activation'); a.grid(alpha=.3)
save(fig, 'fig_muscle_activations')
# ヒラメ筋 左右
fig, a = plt.subplots(figsize=(5.2, 2.8))
a.plot(ta, kin['soleus_r/activation'], 'k', lw=1.1, label='Soleus (R)'); a.plot(ta, kin['soleus_l/activation'], 'k', ls='--', lw=1.1, label='Soleus (L)')
a.set_ylim(0, 1); a.set_xlabel('Time (s)'); a.set_ylabel('Activation'); a.legend(fontsize=8); a.grid(alpha=.3)
save(fig, 'fig_soleus')
print('図を書き出しました:', out, '(実行', case + ')')
