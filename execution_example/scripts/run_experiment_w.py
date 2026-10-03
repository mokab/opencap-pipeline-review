#!/usr/bin/env python3
"""
実行例の OpenSimAD 実行ランナー

使い方 (コンテナ内):
  python3 run_experiment_w.py <id> <trial> <treadmill_speed_m_s> <mesh> <t0> <t1> [--prep-only]

出力: /workspace/runs/<id>/ に versions, settings, ipopt_options, decisions, stdout, run_metadata, outputs_index
結果ファイル: Data/<session>/OpenSimData/Dynamics/<trial>/*_<case>.*  (case = <id>_<trial>_v<speed>_w<t0>-<t1>_m<mesh>)
"""
import os, sys, time, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logger as L

SESSION_ID = "session01"   # data/ をこの名前で Data/ 配下にマウントする (run_docker.sh)
MOTION_TYPE = "walking"
CONTACT_SIDE = "all"
DATA_DIR = "/app/opencap-processing/Data"
SESSION_DIR = os.path.join(DATA_DIR, SESSION_ID)
BASE_DIR = "/app/opencap-processing"
EXP_ROOT = "/workspace/runs"

def patch_for_local():
    utils_path = "/app/opencap-processing/utils.py"
    with open(utils_path) as f: content = f.read()
    if "API_TOKEN = get_token()" in content:
        content = content.replace("API_TOKEN = get_token()", "API_TOKEN = os.environ.get('API_TOKEN', 'local_mode')")
        with open(utils_path, "w") as f: f.write(content)

def run(eid, trial, speed, mesh, t0, t1, prep_only=False):
    output_dir = os.path.join(EXP_ROOT, eid)
    case = f"{eid}_{trial}_v{speed:.3f}_w{t0:g}-{t1:g}_m{mesh}".replace('.', 'p')
    window = [float(t0), float(t1)]
    rationale = {"trial": trial, "treadmill_speed_m_s": speed,
                 "time_window": f"[{t0}, {t1}] s (sync 後の時刻)。進行方向を +x に回転した {trial} を使用。",
                 "mesh_density": f"{mesh}", "ipopt_tolerance": "OpenSimAD 既定 (walking: 10^-3)。"}
    L.setup_run(eid, output_dir, mesh, window, trial, BASE_DIR, rationale)
    print(f"\n{'='*70}\n  EXPERIMENT {eid}: trial={trial} speed={speed} m/s mesh={mesh} window={window} case={case}\n{'='*70}\n", flush=True)
    sys.path.insert(0, BASE_DIR); sys.path.insert(0, os.path.join(BASE_DIR, "UtilsDynamicSimulations", "OpenSimAD"))
    from utilsOpenSimAD import processInputsOpenSimAD
    from mainOpenSimAD import run_tracking
    ts = time.time()
    settings = processInputsOpenSimAD(BASE_DIR, DATA_DIR, SESSION_ID, trial, MOTION_TYPE, window,
                                      repetition=None, treadmill_speed=speed, contact_side=CONTACT_SIDE)
    settings["meshDensity"] = mesh
    t_prep = time.time() - ts
    print(f"\n  >>> Prep: {t_prep:.1f}s (treadmill_speed={settings.get('treadmill_speed')})", flush=True)
    L.dump_settings(settings, os.path.join(output_dir, "settings_full.yaml"))
    with open(os.path.join(output_dir, "ipopt_options.txt"), "w") as f:
        yaml.safe_dump(L.get_ipopt_options_used(settings), f, default_flow_style=False)
    L.write_decisions_md(output_dir, eid, mesh, window, trial, settings, rationale)
    if prep_only:
        print("  >>> prep-only: external function built, skipping solve", flush=True); return
    ts = time.time()
    run_tracking(BASE_DIR, DATA_DIR, SESSION_ID, settings, case=case, solveProblem=True, analyzeResults=True)
    t_solve = time.time() - ts
    print(f"\n  >>> Solve: {t_solve:.1f}s ({t_solve/60:.1f} min)", flush=True)
    dynamics_dir = os.path.join(SESSION_DIR, "OpenSimData", "Dynamics", trial)
    stats_path = os.path.join(dynamics_dir, f"stats_{case}.npy"); solver_stats = None
    if os.path.exists(stats_path):
        import numpy as np
        try:
            stats = np.load(stats_path, allow_pickle=True).item()
            solver_stats = {k: (str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v) for k, v in stats.items()}
            for k in ["iter_count", "return_status", "success", "t_proc_total", "t_wall_total"]:
                if k in stats: solver_stats[f"_extracted_{k}"] = stats[k]
        except Exception as e:
            solver_stats = {"error": f"Failed to load stats: {e}"}
    meta = L.finalize_run(output_dir, t_prep, t_solve, solver_stats)
    print(f"\n  >>> Total: {meta['total_time_min']:.1f} min\n  >>> Solver status: {solver_stats.get('return_status', 'unknown') if solver_stats else 'no_stats'}", flush=True)
    if os.path.exists(dynamics_dir):
        outputs = [{"file": fn, "size_kb": round(os.path.getsize(os.path.join(dynamics_dir, fn))/1024, 1)} for fn in sorted(os.listdir(dynamics_dir)) if case in fn]
        with open(os.path.join(output_dir, "outputs_index.yaml"), "w") as f: yaml.safe_dump(outputs, f, default_flow_style=False)
    print(f"\n  >>> {eid} COMPLETE\n", flush=True)

if __name__ == "__main__":
    if len(sys.argv) < 7:
        print(__doc__); sys.exit(1)
    patch_for_local()
    prep_only = "--prep-only" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(args[0], args[1], float(args[2]), int(args[3]), float(args[4]), float(args[5]), prep_only)
