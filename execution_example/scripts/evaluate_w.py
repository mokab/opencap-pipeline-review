#!/usr/bin/env python3
"""OpenSimAD の 1 実行を評価する（読み取り専用）。

使い方:
  python3 evaluate_w.py <run_name>                     # パッケージの results/<run_name>/ を評価 (出力は results/<run_name>/eval/)
  python3 evaluate_w.py --dyn <outputs_dir> --trial <trial> --case <case> --out <dir> [--log <stdout.log>] [--belt <m/s>] [--mass <kg>] [--ik <ik.mot>]

<out>/eval.yaml（数値）、<out>/eval.md（要約）、および fig_grf.png, fig_joint_moments.png, fig_muscle_activations.png,
fig_soleus.png を書き出す。出力ディレクトリ (outputs/) には書き込まない。
評価項目: IPOPT の収束指標、床反力と体重の整合、立脚・遊脚の事象、荷重中の接触点速度とベルト速度の差（滑り）、
逆運動学との追跡誤差、関節モーメントと筋活動のピーク、筋活動の飽和、両脚支持の割合。
"""
import sys, os, re, io, glob, yaml, argparse
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASS_DEFAULT = 83.0
MUSCLES9 = [('soleus_r','Soleus (R)'),('gasmed_r','Gastrocnemius Med (R)'),('tibant_r','Tibialis Ant (R)'),
            ('vasmed_r','Vastus Med (R)'),('recfem_r','Rectus Femoris (R)'),('bflh_r','Biceps Femoris LH (R)'),
            ('glmed1_r','Gluteus Med (R)'),('glmax1_r','Gluteus Max (R)'),('psoas_r','Psoas (R)')]

def read_mot(path):
    lines = open(path, encoding='latin-1').read().splitlines()
    i = [k for k, l in enumerate(lines) if l.strip() == 'endheader'][0]
    df = pd.read_csv(io.StringIO('\n'.join(lines[i+1:])), sep='\t')
    return df[[c for c in df.columns if not c.startswith('Unnamed')]]

def find_col(df, key):
    if key in df.columns: return key
    c = [x for x in df.columns if x == key or x.endswith('/' + key) or x.startswith(key + '/') or key in x]
    return c[0] if c else None

def ipopt_stats(log):
    if not log or not os.path.exists(log): return {}
    s = open(log, encoding='latin-1', errors='ignore').read()
    g = lambda pat: (re.findall(pat, s) or [None])[-1]
    out = {'iterations': g(r'Number of Iterations\.+:\s+(\d+)'),
           'objective': g(r'Objective\.+:\s+([-\d.e+]+)\s+([-\d.e+]+)'),
           'dual_infeasibility': g(r'Dual infeasibility\.+:\s+([-\d.e+]+)\s+([-\d.e+]+)'),
           'constraint_violation': g(r'Constraint violation\.+:\s+([-\d.e+]+)\s+([-\d.e+]+)'),
           'complementarity': g(r'Complementarity\.+:\s+([-\d.e+]+)\s+([-\d.e+]+)'),
           'nlp_error': g(r'Overall NLP error\.+:\s+([-\d.e+]+)\s+([-\d.e+]+)'),
           'exit': g(r'EXIT: (.*)'), 'ipopt_seconds': g(r'Total seconds in IPOPT\s+=\s+([\d.]+)'),
           'solve_min': g(r'Solve: [\d.]+s \(([\d.]+) min\)')}
    for k in ['objective','dual_infeasibility','constraint_violation','complementarity','nlp_error']:
        if out[k]: out[k] = {'scaled': float(out[k][0]), 'unscaled': float(out[k][1])}
    for k in ['iterations']:
        if out[k]: out[k] = int(out[k])
    for k in ['ipopt_seconds','solve_min']:
        if out[k]: out[k] = float(out[k])
    return out

def contact_events(t, fy, thr=20.0):
    on = fy > thr
    hs = t[1:][(~on[:-1]) & on[1:]]; to = t[1:][on[:-1] & (~on[1:])]
    return hs, to

def evaluate(dyn, trial, case, out, log=None, belt=None, mass=MASS_DEFAULT, ik_path=None):
    os.makedirs(out, exist_ok=True)
    f = lambda kind: read_mot(os.path.join(dyn, f'{kind}_{trial}_{case}.mot'))
    grfr, grf, kin, kt = f('GRF_resultant'), f('GRF'), f('kinematics_activations'), f('kinetics')
    t = grfr.time.values; dt = np.median(np.diff(t)); BW = mass * 9.81
    R = {'vx': grfr.ground_force_right_vx.values, 'vy': grfr.ground_force_right_vy.values, 'vz': grfr.ground_force_right_vz.values}
    L = {'vx': grfr.ground_force_left_vx.values, 'vy': grfr.ground_force_left_vy.values, 'vz': grfr.ground_force_left_vz.values}
    res = {'trial': trial, 'case': case, 'window': [float(t[0]), float(t[-1])], 'n_mesh': int(len(t)), 'ipopt': ipopt_stats(log)}
    # 1. 床反力と体重
    tot = R['vy'] + L['vy']
    res['grf'] = {'mean_total_vy_over_BW': float(tot.mean()/BW), 'min_total_vy_over_BW': float(tot.min()/BW), 'max_total_vy_over_BW': float(tot.max()/BW),
                  'peak_vy_R_over_BW': float(R['vy'].max()/BW), 'peak_vy_L_over_BW': float(L['vy'].max()/BW),
                  'ap_range_R_over_BW': [float(R['vx'].min()/BW), float(R['vx'].max()/BW)], 'ap_range_L_over_BW': [float(L['vx'].min()/BW), float(L['vx'].max()/BW)]}
    # 1b. 整数周期 (右踵接地から次の右踵接地まで; 0.3 s 以下の短い接触は除く) の鉛直床反力の平均
    onR = R['vy'] > 20; starts = []; s0 = None
    for k in range(len(t)):
        if onR[k] and s0 is None: s0 = k
        if ((not onR[k]) or k == len(t) - 1) and s0 is not None:
            if t[k] - t[s0] > 0.3: starts.append(t[s0])
            s0 = None
    if len(starts) >= 2:
        m_ = (t >= starts[0]) & (t < starts[-1])
        res['grf'].update({'integer_cycle_window': [float(starts[0]), float(starts[-1])], 'integer_cycle_count': len(starts) - 1,
                           'integer_cycle_mean_total_vy_over_BW': float(tot[m_].mean()/BW)})
    # 2. 接地・離地の事象とストライド周期
    ev = {}
    for side, S in [('R', R), ('L', L)]:
        hs, to = contact_events(t, S['vy'])
        per = np.diff(hs) if len(hs) > 1 else np.array([])
        ev[side] = {'heel_strikes': [round(float(x), 2) for x in hs], 'toe_offs': [round(float(x), 2) for x in to],
                    'stride_period_mean': float(per.mean()) if len(per) else None, 'stride_period_sd': float(per.std()) if len(per) > 1 else None,
                    'stance_fraction': float((S['vy'] > 20).mean())}
    res['events'] = ev
    # 3. ベルトに対する滑り: 荷重中の接触球の接触点速度とベルト速度
    slip = {}
    for side in ['r', 'l']:
        vs = []
        for k in range(1, 7):
            fy = find_col(grf, f's{k}_{side}_vy'); px = find_col(grf, f's{k}_{side}_px')
            if fy is None or px is None: continue
            fy = grf[fy].values; px = grf[px].values; vx = np.gradient(px, t)
            m = fy > 50
            if m.sum() > 5: vs.append(vx[m])
        if vs:
            v = np.concatenate(vs); slip[side] = {'median_contact_point_vx': float(np.median(v)), 'iqr': [float(np.percentile(v, 25)), float(np.percentile(v, 75))], 'n': int(len(v))}
            if belt is not None: slip[side]['median_slip_vs_belt'] = float(np.median(v) + belt)
    res['contact_slip'] = slip
    # 4. 逆運動学との追跡誤差
    if ik_path and os.path.exists(ik_path):
        ik = read_mot(ik_path); ik = ik[(ik.time >= t[0]-1e-6) & (ik.time <= t[-1]+1e-6)]
        tr = {}
        for j in ['hip_flexion_r','knee_angle_r','ankle_angle_r','hip_flexion_l','knee_angle_l','ankle_angle_l','pelvis_tx','pelvis_ty','pelvis_tz','pelvis_tilt']:
            cj = find_col(kin, j)
            if cj is None or j not in ik.columns: continue
            a = np.interp(t, kin.time.values, kin[cj].values); b = np.interp(t, ik.time.values, ik[j].values)
            tr[j] = {'rms': float(np.sqrt(np.mean((a-b)**2))), 'max_abs': float(np.max(np.abs(a-b)))}
        res['tracking_error'] = tr
    # 5. ピーク値
    pk = {}
    for j in ['hip_flexion_r_moment','knee_angle_r_moment','ankle_angle_r_moment','hip_flexion_l_moment','knee_angle_l_moment','ankle_angle_l_moment']:
        if j in kt.columns: pk[j] = {'min': float(kt[j].min()), 'max': float(kt[j].max())}
    for m, _ in MUSCLES9:
        cm = find_col(kin, m)
        if cm: pk[m] = {'max': float(kin[cm].max()), 'mean': float(kin[cm].mean())}
    res['peaks'] = pk
    # 6. 筋活動の飽和と両脚支持
    sat = {}
    act_cols = [c for c in kin.columns if c.endswith('/activation')]
    for c in act_cols:
        fr = float((kin[c] >= 0.99).mean())
        if fr > 0: sat[c.replace('/activation', '')] = round(fr, 4)
    res['activation_saturation'] = {'muscles_with_any_saturation': sat, 'n_muscle_columns': len(act_cols)}
    both = (R['vy'] > 20) & (L['vy'] > 20); neither = (R['vy'] <= 20) & (L['vy'] <= 20)
    res['support'] = {'double_support_fraction': float(both.mean()), 'no_support_fraction': float(neither.mean()), 'single_support_fraction': float(1 - both.mean() - neither.mean())}
    yaml.safe_dump(res, open(os.path.join(out, 'eval.yaml'), 'w'), default_flow_style=False, allow_unicode=True)
    # --- 図 ---
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
    for i, (comp, lab) in enumerate([('vy', 'Vertical'), ('vx', 'Anterior-posterior'), ('vz', 'Medio-lateral')]):
        ax[i].plot(t, R[comp], 'k', label='Right'); ax[i].plot(t, L[comp], color='0.55', label='Left')
        ax[i].set_title(f'{lab} GRF'); ax[i].set_xlabel('Time (s)'); ax[i].set_ylabel('Force (N)'); ax[i].grid(alpha=.3)
        if i == 0: ax[i].axhline(BW, ls='--', color='0.7', lw=.8); ax[i].legend(fontsize=8)
    fig.suptitle(f'Ground reaction forces ({trial}, {case})', fontsize=10); fig.tight_layout(); fig.savefig(os.path.join(out, 'fig_grf.png'), dpi=130); plt.close(fig)
    fig, ax = plt.subplots(2, 3, figsize=(13, 6.5))
    for r, side in enumerate(['r', 'l']):
        for c, (j, lab) in enumerate([('hip_flexion', 'Hip flexion'), ('knee_angle', 'Knee'), ('ankle_angle', 'Ankle')]):
            col = f'{j}_{side}_moment'
            if col in kt.columns: ax[r, c].plot(kt.time, kt[col], 'k')
            ax[r, c].set_title(f'{lab} ({side.upper()})'); ax[r, c].set_xlabel('Time (s)'); ax[r, c].set_ylabel('Moment (Nm)'); ax[r, c].axhline(0, ls='--', color='0.7', lw=.8); ax[r, c].grid(alpha=.3)
    fig.suptitle('Joint moments: top row right leg, bottom row left leg', fontsize=10); fig.tight_layout(); fig.savefig(os.path.join(out, 'fig_joint_moments.png'), dpi=130); plt.close(fig)
    fig, ax = plt.subplots(3, 3, figsize=(13, 9))
    for i, (m, lab) in enumerate(MUSCLES9):
        a = ax[i//3, i%3]; cm = find_col(kin, m)
        if cm: a.fill_between(kin.time, 0, kin[cm], color='#7fa7c9', alpha=.6); a.plot(kin.time, kin[cm], color='#1f4e79', lw=.8)
        a.set_ylim(0, 1); a.set_title(lab); a.set_xlabel('Time (s)'); a.set_ylabel('Activation'); a.grid(alpha=.3)
    fig.suptitle('Estimated muscle activations (right leg)', fontsize=10); fig.tight_layout(); fig.savefig(os.path.join(out, 'fig_muscle_activations.png'), dpi=130); plt.close(fig)
    fig, a = plt.subplots(figsize=(6.5, 3.2))
    for side, colr in [('r', 'k'), ('l', '0.55')]:
        cm = find_col(kin, f'soleus_{side}')
        if cm: a.plot(kin.time, kin[cm], color=colr, label=f'Soleus ({side.upper()})')
    a.set_ylim(0, 1); a.set_xlabel('Time (s)'); a.set_ylabel('Activation'); a.legend(fontsize=8); a.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(out, 'fig_soleus.png'), dpi=130); plt.close(fig)
    # --- 要約 (markdown) ---
    ip = res['ipopt']; g = res['grf']
    md = [f"# {case}", '', f"- 時間窓 {res['window']} s, メッシュ点数 {res['n_mesh']}",
          f"- IPOPT: {ip.get('exit')} | 反復 {ip.get('iterations')} | 目的関数値 {ip.get('objective',{}).get('unscaled') if ip.get('objective') else None} | 制約違反 (unscaled) {ip.get('constraint_violation',{}).get('unscaled') if ip.get('constraint_violation') else None} | 双対不可行性 {ip.get('dual_infeasibility',{}).get('unscaled') if ip.get('dual_infeasibility') else None} | NLP 全体誤差 {ip.get('nlp_error',{}).get('unscaled') if ip.get('nlp_error') else None} | 所要 {ip.get('solve_min')} 分",
          f"- 両足の鉛直床反力の和 / 体重: 平均 {g['mean_total_vy_over_BW']:.3f}, 最小 {g['min_total_vy_over_BW']:.2f}, 最大 {g['max_total_vy_over_BW']:.2f}; 片脚ピーク 右 {g['peak_vy_R_over_BW']:.2f} 左 {g['peak_vy_L_over_BW']:.2f}",
          (f"- 整数周期 (右踵接地から次の右踵接地, {g['integer_cycle_count']} 周期, {g['integer_cycle_window'][0]:.2f}-{g['integer_cycle_window'][1]:.2f} s) の鉛直床反力の和 / 体重: 平均 {g['integer_cycle_mean_total_vy_over_BW']:.3f}" if 'integer_cycle_count' in g else "- 整数周期の鉛直床反力の平均: 算出不可 (0.3 s を超える右の立脚期が 2 回未満)"),
          f"- ストライド周期 右 {ev['R']['stride_period_mean']} s (SD {ev['R']['stride_period_sd']}), 左 {ev['L']['stride_period_mean']} s; 立脚率 右 {ev['R']['stance_fraction']:.2f} 左 {ev['L']['stance_fraction']:.2f}",
          f"- 踵接地時刻 右 {ev['R']['heel_strikes']} 左 {ev['L']['heel_strikes']}",
          f"- 荷重中の接触点速度 (x, m/s): " + ', '.join(f"{s}: {v['median_contact_point_vx']:+.3f} (ベルト速度との差 {v.get('median_slip_vs_belt', float('nan')):+.3f})" for s, v in slip.items())]
    if 'tracking_error' in res: md.append('- 追跡誤差 RMS (度 または m): ' + ', '.join(f"{k} {v['rms']:.2f}" for k, v in res['tracking_error'].items()))
    md.append(f"- 支持: 両脚 {res['support']['double_support_fraction']:.2f}, 単脚 {res['support']['single_support_fraction']:.2f}, なし {res['support']['no_support_fraction']:.2f}; 活動 >= 0.99 のフレーム割合: " + (', '.join(f'{k} {v}' for k, v in sorted(res['activation_saturation']['muscles_with_any_saturation'].items(), key=lambda x: -x[1])[:8]) or 'なし'))
    md.append('- ピーク: ' + ', '.join(f"{k} [{v.get('min', '')}, {v.get('max', '')}]" if 'min' in v else f"{k} 最大 {v['max']:.2f}" for k, v in pk.items()))
    open(os.path.join(out, 'eval.md'), 'w').write('\n'.join(md) + '\n'); print('\n'.join(md))
    return res

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('run_id', nargs='?'); ap.add_argument('--dyn'); ap.add_argument('--trial'); ap.add_argument('--case'); ap.add_argument('--out'); ap.add_argument('--log'); ap.add_argument('--belt', type=float); ap.add_argument('--mass', type=float, default=MASS_DEFAULT); ap.add_argument('--ik')
    a = ap.parse_args()
    if a.run_id:
        # パッケージ構成: results/<run_name>/{outputs, settings_full.yaml, stdout.log}, data/OpenSimData/Kinematics/<trial>.mot
        rd = a.run_id if os.path.isdir(os.path.join(a.run_id, 'outputs')) else os.path.join(PKG, 'results', a.run_id)
        case = os.path.basename(os.path.normpath(rd)); dyn = os.path.join(rd, 'outputs')
        st = yaml.safe_load(open(os.path.join(rd, 'settings_full.yaml'))); log = os.path.join(rd, 'stdout.log')
        kin_file = glob.glob(os.path.join(dyn, 'kinematics_activations_*.mot'))[0]
        trial = os.path.basename(kin_file)[len('kinematics_activations_'):-4][:-len(case)-1]
        ik = os.path.join(PKG, 'data', 'OpenSimData', 'Kinematics', f'{trial}.mot')
        evaluate(dyn, trial, case, os.path.join(rd, 'eval'), log=log, belt=float(st.get('treadmill_speed', 0)), mass=a.mass, ik_path=ik)
    else:
        evaluate(a.dyn, a.trial, a.case, a.out, log=a.log, belt=a.belt, mass=a.mass, ik_path=a.ik)
