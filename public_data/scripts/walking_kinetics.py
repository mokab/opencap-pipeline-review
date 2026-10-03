#!/usr/bin/env python3
"""公開妥当化データ (Uhlrich et al., 2023) の歩行試行について、OpenCap のパイプライン出力（床反力・関節モーメント・筋活動）と
参照計測（フォースプレート、光学式の逆動力学、筋電図）の対応を集計する。

使い方: LABVALIDATION_DIR=/path/to/LabValidation_withoutVideos python3 walking_kinetics.py [out_dir]
  （データの既定位置は public_data/data/LabValidation_withoutVideos、出力の既定位置は public_data/results）

入力: LABVALIDATION_DIR（LabValidation_withoutVideos）配下の subject2〜subject11。
  - OpenSimData/Video/HRNet/2-cameras/Dynamics/walking_results.npy : OpenCap の力学シミュレーション出力 (sim) と参照値 (ref)
  - EMGData/<trial>_EMG.sto : 筋電図（帯域通過 30–500 Hz、整流、6 Hz 低域通過、最大活動試行で正規化; 原著 Methods）
対象: walking1〜walking4（体幹動揺条件 walkingTS* は除く）。
歩行周期の事象は歩行分析で標準とされるフォースプレートの閾値法 (Zeni et al., 2008, Gait Posture 27:710-714) で定める:
踵接地 = 鉛直床反力が 20 N を上回った最初の時刻、
離地 = その後 20 N を下回った最初の時刻、立脚期 = 踵接地から離地まで（閾値は sessionMetadata.yaml の体重で %BW に換算）。
各試行・各脚について最長の立脚期を用い、試行の両端に接しない（立脚期全体が記録に含まれる）ものだけを用いる。
指標（立脚期ごと）: 歩行速度（骨盤前後位置の変位/時間）、立脚時間、鉛直床反力の立脚期内平均絶対差とピーク、
足関節底屈モーメントの極小の時刻（立脚期の %）と値、立脚期内平均絶対差、
ヒラメ筋・腓腹筋内側頭・前脛骨筋の活動ピーク時刻（立脚期の %）とピーク値（筋電図と出力）、
筋電図と出力の活性化の時系列の試行全体にわたるピアソン相関係数、
股関節屈曲モーメントの 10 ms 当たりの変化量の最大値（試行全体。出力と逆動力学）とその時刻が支持脚の交代から 0.1 s 以内にある割合。
出力: results/walking_kinetics_stances.csv（立脚期ごと）, results/walking_kinetics_summary.csv（平均・SD・n）
"""
import os, sys, glob, io, re
import numpy as np, pandas as pd, yaml

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.environ.get('LABVALIDATION_DIR', os.path.join(HERE, 'data', 'LabValidation_withoutVideos'))
THR_N = 20.0          # 踵接地・離地の判定に用いる鉛直床反力の閾値 (N)
MIN_STANCE = 0.4      # 立脚期の最短長 (s)
MUSCLES = ['soleus', 'gasmed', 'tibant']

def read_sto(p):
    L = open(p, encoding='latin-1').read().split('\n'); i = [k for k, l in enumerate(L) if l.strip().lower() == 'endheader'][0]
    return pd.read_csv(io.StringIO('\n'.join(L[i+1:])), sep='\t').dropna(axis=1, how='all')

def load_trial(root, subject, trial):
    """1 試行の公開出力（床反力・関節モーメント・筋活動・骨盤位置）と筋電図を返す（図示用）。"""
    dyn = os.path.join(root, subject, 'OpenSimData', 'Video', 'HRNet', '2-cameras', 'Dynamics')
    r = np.load(os.path.join(dyn, 'walking_results.npy'), allow_pickle=True).item()
    emg_p = os.path.join(root, subject, 'EMGData', f'{trial}_EMG.sto')
    return r, (read_sto(emg_p) if os.path.exists(emg_p) else None)

def stance_window(t, ref_vy, thr_bw):
    """参照の鉛直床反力 (%BW) から、記録に全体が含まれる最長の立脚期を返す。
    返り値 (i0, i1): i0 は踵接地（閾値 thr_bw を上回った最初のフレーム）、i1 は離地（その後閾値を下回った最初のフレーム）。
    立脚期は t[i0] <= t < t[i1]。記録の両端に接する場合や短すぎる場合は None。"""
    on = ref_vy > thr_bw
    if on.sum() < 20: return None
    idx = np.where(on)[0]; seg = max(np.split(idx, np.where(np.diff(idx) > 1)[0] + 1), key=len); i0, i1 = seg[0], seg[-1] + 1
    if i0 == 0 or i1 > len(t) - 1 or t[i1] - t[i0] < MIN_STANCE: return None
    return i0, i1

def analyze(root=None):
    """全被験者・全歩行試行を集計し、立脚期ごとの表 df、要約表 summ、公開出力の設定 settings を返す。"""
    root = root or ROOT
    rows = []; settings = set()
    for s in sorted(glob.glob(os.path.join(root, 'subject*'))):
        sid = os.path.basename(s); dyn = os.path.join(s, 'OpenSimData', 'Video', 'HRNet', '2-cameras', 'Dynamics')
        mass = yaml.safe_load(open(os.path.join(s, 'sessionMetadata.yaml')))['mass_kg']; thr_bw = THR_N / (mass * 9.81) * 100
        p = os.path.join(dyn, 'walking_results.npy')
        if not os.path.exists(p): continue
        r = np.load(p, allow_pickle=True).item()
        for trial in sorted(r['GRFs_BW']):
            if 'TS' in trial: continue
            su = os.path.join(dyn, trial, 'Setup.yaml')
            if os.path.exists(su):
                y = open(su).read(); m = re.search(r'meshDensity:\s*(\d+)', y); c = re.search(r'cutoff_freq_coord:\s*(\d+)', y)
                settings.add((m.group(1) if m else '?', c.group(1) if c else '?'))
            g = r['GRFs_BW'][trial]; hg = g['headers']; t = g['ref'][0]
            pos = r['positions'][trial]; hp = pos['headers']; tx = pos['ref'][hp.index('pelvis_tx')]
            speed = abs(tx[-1] - tx[0]) / (t[-1] - t[0])
            q = r['torques'][trial]; hq = q['headers']; act = r['activations'][trial]; ha = act['headers']
            emg_p = os.path.join(s, 'EMGData', f'{trial}_EMG.sto'); E = read_sto(emg_p) if os.path.exists(emg_p) else None
            for side in ['r', 'l']:
                iy = hg.index(f'ground_force_{side}_vy'); ref_vy = g['ref'][iy]; sim_vy = g['sim'][iy]
                w = stance_window(t, ref_vy, thr_bw)
                if w is None: continue
                i0, i1 = w
                ts, te = t[i0], t[i1]; m = (t >= ts) & (t < te); pct = lambda j: 100 * (t[j] - ts) / (te - ts)
                ia = hq.index(f'ankle_angle_{side}'); ref_am = q['ref'][ia]; sim_am = q['sim'][ia]
                jref = np.argmin(np.where(m, ref_am, 1e9)); jsim = np.argmin(np.where(m, sim_am, 1e9))
                # 股関節屈曲モーメントの 10 ms 当たりの変化量の最大値（試行全体）と、その時刻が支持脚の交代
                # （いずれかの足の参照鉛直床反力が閾値を横切る時刻）から 0.1 s 以内にあるか
                ih = hq.index(f'hip_flexion_{side}'); dt = np.median(np.diff(t))
                ds, dr = np.abs(np.diff(q['sim'][ih])) * 0.01 / dt, np.abs(np.diff(q['ref'][ih])) * 0.01 / dt
                ev = [t[k + 1] for sd in ['r', 'l'] for k in np.where(np.diff((g['ref'][hg.index(f'ground_force_{sd}_vy')] > thr_bw).astype(int)) != 0)[0]]
                near = float(min(abs(t[int(np.argmax(ds))] - e) for e in ev) <= 0.1) if ev else np.nan
                row = dict(subject=sid, trial=trial, side=side, mass_kg=mass, thr_bw=thr_bw, speed_mps=speed, stance_s=te - ts,
                           hip_rate_sim_nm=ds.max(), hip_rate_ref_nm=dr.max(), hip_rate_sim_near_transition=near,
                           vgrf_mae_bw=np.mean(np.abs(sim_vy - ref_vy)[m]), vgrf_peak_ref_bw=ref_vy[m].max(), vgrf_peak_sim_bw=sim_vy[m].max(),
                           ankle_min_pct_ref=pct(jref), ankle_min_pct_sim=pct(jsim), ankle_min_ref_nm=ref_am[jref], ankle_min_sim_nm=sim_am[jsim],
                           ankle_mae_nm=np.mean(np.abs(sim_am - ref_am)[m]))
                if E is not None:
                    for mus in MUSCLES:
                        col = f'{mus}_{side}_activation'; name = f'{mus}_{side}'
                        if col not in E.columns or name not in ha: continue
                        e = np.interp(t, E.time.values, E[col].values); a = act['sim'][ha.index(name)]
                        je = np.argmax(np.where(m, e, -1e9)); ja = np.argmax(np.where(m, a, -1e9))
                        row.update({f'{mus}_peak_pct_emg': pct(je), f'{mus}_peak_pct_sim': pct(ja), f'{mus}_peak_emg': e[je], f'{mus}_peak_sim': a[ja],
                                    f'{mus}_corr': np.corrcoef(e, a)[0, 1]})
                rows.append(row)
    df = pd.DataFrame(rows)
    num = df.select_dtypes('number')
    summ = pd.DataFrame({'mean': num.mean(), 'sd': num.std(), 'n': num.count()}).round(3)
    return df, summ, sorted(settings)

def main(out_dir):
    df, summ, settings = analyze()
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(os.path.join(out_dir, 'walking_kinetics_stances.csv'), index=False)
    summ.to_csv(os.path.join(out_dir, 'walking_kinetics_summary.csv'))
    print(f'立脚期 {len(df)} 個（被験者 {df.subject.nunique()} 名、右 {(df.side=="r").sum()}、左 {(df.side=="l").sum()}）; 公開出力の設定 (meshDensity, cutoff):', settings)
    print(summ.to_string())

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results'))
