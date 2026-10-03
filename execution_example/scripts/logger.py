"""
実行記録のロガー

各実験で以下を捕捉:
- 環境バージョン (Python, CasADi, IPOPT, OpenSim, NumPy, SciPy, pandas)
- opencap-processing の git hash
- processInputsOpenSimAD 出力の settings 辞書全件
- IPOPT options 全件
- 実行メタデータ (日時, ホスト, container, 所要時間)
- stdout/stderr 全件
"""
import os
import sys
import yaml
import json
import time
import socket
import subprocess
import platform
from datetime import datetime


def capture_versions():
    """主要パッケージのバージョンを取得"""
    versions = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    pkgs = ["casadi", "scipy", "numpy", "pandas", "matplotlib", "joblib", "opensim"]
    for pkg in pkgs:
        try:
            mod = __import__(pkg)
            versions[pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[pkg] = "NOT_INSTALLED"
    return versions


def capture_ipopt_version():
    """CasADi 同梱 IPOPT のバージョンを取得する。小さな問題を 1 回解き、IPOPT が C レベルの標準出力に
    書く "This is Ipopt version X" を一時ファイルに捕捉して読み取る。"""
    import re, tempfile
    try:
        import casadi as ca
        x = ca.MX.sym("x")
        solver = ca.nlpsol("solver", "ipopt", {"x": x, "f": (x - 1) ** 2}, {"ipopt.print_level": 5, "print_time": False})
        with tempfile.TemporaryFile(mode="w+") as tmp:
            saved = os.dup(1); os.dup2(tmp.fileno(), 1)
            try:
                solver(x0=0.0)
            finally:
                sys.stdout.flush(); os.dup2(saved, 1); os.close(saved)
            tmp.seek(0); text = tmp.read()
        m = re.search(r"This is Ipopt version ([0-9.]+)", text)
        return m.group(1) if m else {"error": "version string not found", "casadi_version": ca.__version__}
    except Exception as e:
        return {"error": str(e)}


def capture_git_hash(repo_path):
    """Git リポジトリの commit hash を取得"""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "-1", "--format=%H"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def capture_metadata(experiment_id, output_dir):
    """実行メタデータを取得"""
    return {
        "experiment_id": experiment_id,
        "timestamp_start": datetime.now().isoformat(),
        "hostname": socket.gethostname(),
        "container_id": os.environ.get("HOSTNAME", "n/a"),
        "output_dir": str(output_dir),
        "user": os.environ.get("USER", "n/a"),
        "pwd": os.getcwd(),
    }


try:
    import numpy as np
    _has_numpy = True
except ImportError:
    _has_numpy = False


def _to_basic(x):
    """YAML安全な型へ再帰変換 (numpy scalar/array 含む)"""
    if _has_numpy and isinstance(x, np.generic):
        return x.item()
    if hasattr(x, "tolist") and not isinstance(x, (str, bytes)):
        return _to_basic(x.tolist())
    if isinstance(x, dict):
        return {str(k): _to_basic(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_basic(v) for v in x]
    if isinstance(x, (int, float, str, bool, type(None))):
        return x
    return str(x)


def dump_settings(settings, output_path):
    """processInputsOpenSimAD の出力 settings を YAML にダンプ"""
    safe_settings = _to_basic(settings)
    with open(output_path, "w") as f:
        yaml.safe_dump(safe_settings, f, default_flow_style=False, sort_keys=True)


def get_ipopt_options_used(settings):
    """settings から実際に使われる IPOPT 関連設定を抽出"""
    keys_of_interest = [
        "ipopt_tolerance", "meshDensity", "timeInterval",
        "treadmill_speed", "contact_side", "filter_Qs_toTrack",
        "cutoff_freq_Qs", "enableLimitTorques",
        "useExpressionGraphFunction", "weights",
        "coordinates_toTrack", "coordinate_constraints",
    ]
    return _to_basic({k: settings.get(k, "NOT_SET") for k in keys_of_interest})


def write_decisions_md(output_dir, experiment_id, mesh_density, time_window,
                       trial_name, settings, rationale):
    """設定選択の根拠を人が読める形式で記述"""
    path = os.path.join(output_dir, "decisions.md")
    with open(path, "w") as f:
        f.write(f"# 設定根拠ノート — {experiment_id}\n\n")
        f.write(f"**実験ID**: {experiment_id}\n")
        f.write(f"**試行**: {trial_name}\n")
        f.write(f"**時間窓**: {time_window} s\n")
        f.write(f"**メッシュ密度**: {mesh_density}\n\n")
        f.write("## 設定選択の根拠\n\n")
        for key, reason in rationale.items():
            f.write(f"### {key}\n{reason}\n\n")
        f.write("## 重み設定（OpenSimAD既定 + 上書き分）\n\n")
        if "weights" in settings:
            for k, v in sorted(settings["weights"].items()):
                f.write(f"- `{k}`: {v}\n")
        f.write("\n## 追跡対象座標と重み\n\n")
        if "coordinates_toTrack" in settings:
            for k, v in sorted(settings["coordinates_toTrack"].items()):
                w = v.get("weight", "?") if isinstance(v, dict) else v
                f.write(f"- `{k}`: weight={w}\n")


def setup_run(experiment_id, output_dir, mesh_density, time_window,
              trial_name, base_dir, rationale):
    """実験開始時の共通セットアップ — 環境情報を全て保存"""
    os.makedirs(output_dir, exist_ok=True)

    # 1. versions
    versions = capture_versions()
    versions["ipopt"] = capture_ipopt_version()
    with open(os.path.join(output_dir, "versions.yaml"), "w") as f:
        yaml.safe_dump(versions, f, default_flow_style=False)

    # 2. git hashes
    git_info = {
        "opencap-processing": capture_git_hash(base_dir),
    }
    with open(os.path.join(output_dir, "git_hashes.yaml"), "w") as f:
        yaml.safe_dump(git_info, f, default_flow_style=False)

    # 3. metadata
    meta = capture_metadata(experiment_id, output_dir)
    meta["mesh_density"] = mesh_density
    meta["time_window"] = list(time_window)
    meta["trial_name"] = trial_name
    with open(os.path.join(output_dir, "run_metadata.yaml"), "w") as f:
        yaml.safe_dump(meta, f, default_flow_style=False)

    return meta


def finalize_run(output_dir, t_prep_s, t_solve_s, solver_stats=None):
    """実験終了時の共通処理"""
    meta_path = os.path.join(output_dir, "run_metadata.yaml")
    with open(meta_path) as f:
        meta = yaml.safe_load(f)
    meta["timestamp_end"] = datetime.now().isoformat()
    meta["prep_time_s"] = round(t_prep_s, 2)
    meta["solve_time_s"] = round(t_solve_s, 2)
    meta["total_time_s"] = round(t_prep_s + t_solve_s, 2)
    meta["total_time_min"] = round((t_prep_s + t_solve_s) / 60.0, 2)
    if solver_stats is not None:
        meta["solver_stats"] = solver_stats
    with open(meta_path, "w") as f:
        yaml.safe_dump(meta, f, default_flow_style=False)
    return meta
