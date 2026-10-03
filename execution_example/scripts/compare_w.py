#!/usr/bin/env python3
"""複数の OpenSimAD 実行を共通の時間格子 (100 Hz) 上で比較する（読み取り専用）。

使い方: python3 compare_w.py --out <dir> <label>=<outputs_dir>:<trial>:<case> <label>=<outputs_dir>:<trial>:<case> [...]
  最初の実行を基準とし、鉛直床反力 (左右)、前後床反力 (右)、右脚の矢状面関節モーメント、右脚 6 筋の活動について
  RMS 差（基準のピークに対する割合）と相関を表にし、重ね描きの図を出力する。
  例: python3 compare_w.py --out cmp main=results/main_mesh50/outputs:treadmill_walk01_pre:main_mesh50 \
                             mesh100=results/mesh100/outputs:treadmill_walk01_pre:mesh100
"""
import sys, os, io, argparse, yaml
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

def read_mot(path):
    lines = open(path, encoding='latin-1').read().splitlines()
    i = [k for k, l in enumerate(lines) if l.strip() == 'endheader'][0]
    df = pd.read_csv(io.StringIO('\n'.join(lines[i+1:])), sep='\t')
    return df[[c for c in df.columns if not c.startswith('Unnamed')]]

def find_col(df, key):
    if key in df.columns: return key
    c = [x for x in df.columns if x.endswith('/' + key) or x.startswith(key + '/') or key in x]
    return c[0] if c else None

SIGNALS = [('vGRF_R', 'grfr', 'ground_force_right_vy'), ('vGRF_L', 'grfr', 'ground_force_left_vy'),
           ('apGRF_R', 'grfr', 'ground_force_right_vx'),
           ('hip_r_moment', 'kt', 'hip_flexion_r_moment'), ('knee_r_moment', 'kt', 'knee_angle_r_moment'), ('ankle_r_moment', 'kt', 'ankle_angle_r_moment'),
           ('soleus_r', 'kin', 'soleus_r'), ('gasmed_r', 'kin', 'gasmed_r'), ('tibant_r', 'kin', 'tibant_r'),
           ('vasmed_r', 'kin', 'vasmed_r'), ('recfem_r', 'kin', 'recfem_r'), ('glmed1_r', 'kin', 'glmed1_r')]

def load(dyn, trial, case):
    d = {k: read_mot(os.path.join(dyn, f'{f}_{trial}_{case}.mot')) for k, f in [('grfr', 'GRF_resultant'), ('kt', 'kinetics'), ('kin', 'kinematics_activations')]}
    return d

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('runs', nargs='+'); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    runs = []
    for r in a.runs:
        label, spec = r.split('=', 1); dyn, trial, case = spec.split(':'); runs.append((label, load(dyn, trial, case)))
    ref_label, ref = runs[0]
    t0 = max(d['grfr'].time.min() for _, d in runs); t1 = min(d['grfr'].time.max() for _, d in runs)
    tg = np.arange(t0, t1, 0.01)
    rows = []; series = {}
    for name, kind, key in SIGNALS:
        series[name] = {}
        for label, d in runs:
            df = d[kind]; col = find_col(df, key)
            if col is None: continue
            series[name][label] = np.interp(tg, df.time.values, df[col].values)
        if ref_label not in series[name]: continue
        y0 = series[name][ref_label]; p0 = np.max(np.abs(y0))
        for label, y in series[name].items():
            if label == ref_label: continue
            diff = y - y0; rows.append({'signal': name, 'run': label, 'rms_diff': float(np.sqrt(np.mean(diff**2))), 'rms_diff_pct_of_ref_peak': float(100*np.sqrt(np.mean(diff**2))/p0) if p0 > 0 else None,
                                        'ref_peak': float(p0), 'run_peak': float(np.max(np.abs(y))), 'corr': float(np.corrcoef(y0, y)[0, 1]) if np.std(y) > 0 and np.std(y0) > 0 else None})
    tab = pd.DataFrame(rows); tab.to_csv(os.path.join(a.out, 'compare.csv'), index=False)
    md = ['# 基準 ' + ref_label + ' との比較', '', f'共通格子 {t0:.2f}-{t1:.2f} s, 100 Hz', '', tab.round(3).to_markdown(index=False)]
    open(os.path.join(a.out, 'compare.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
    # 重ね描きの図
    keys = [s[0] for s in SIGNALS]; fig, ax = plt.subplots(4, 3, figsize=(14, 12))
    for i, name in enumerate(keys):
        A = ax[i//3, i%3]
        for label, y in series.get(name, {}).items(): A.plot(tg, y, lw=1, label=label)
        A.set_title(name); A.grid(alpha=.3)
        if i == 0: A.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(a.out, 'compare_overlay.png'), dpi=120)

if __name__ == '__main__': main()
