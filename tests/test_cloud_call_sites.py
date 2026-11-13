"""Cloud call sites: the hooks in CLOUD_HOOKS.md are really wired.

Static source checks only — importing ``launch.py`` would pull torch and the whole UI.
Each assertion names the exact text it depends on, so a refactor that moves a hook
fails here instead of silently sending Director jobs to the local model.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
UI = ROOT / "ui" / "src" / "components"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(src: str, start: str, end: str) -> str:
    """Slice of ``src`` from ``start`` up to the next ``end``."""
    first = src.index(start)
    return src[first:src.index(end, first)]


def test_cloud_branch_runs_after_comfyui_and_before_viggle():
    src = _read(APP / "launch.py")
    comfy = src.index('if job["params"].get("_comfyui_submission"):')
    cloud = src.index("# Cloud engine: same queue/job contract, no local weights are loaded.")
    viggle = src.index('if (not _slot_owned and job["params"].get("viggle_character")')
    assert comfy < cloud < viggle

    hook = src[cloud:viggle]
    assert 'job.setdefault("cloud_provider", cloud_generation.active_provider())' in hook
    assert "return cloud_generation.execute(" in hook
    assert "wgp.get_model_def(job[\"params\"].get(\"model_type\"))" in hook
    assert "finalize=finalize" in hook


def test_cloud_provider_is_frozen_per_job():
    """setdefault, not assignment: switching provider mid-job must not reroute it."""
    hook = _between(_read(APP / "launch.py"), "cloud_provider = job.setdefault(", "\n")
    assert 'job.setdefault("cloud_provider", cloud_generation.active_provider())' in hook


def test_cloud_config_endpoints_are_registered():
    src = _read(APP / "launch.py")
    get_at = src.index('@api.get("/api/v1/cloud-config")')
    put_at = src.index('@api.put("/api/v1/cloud-config")')
    assert get_at < put_at

    get_block = _between(src, '@api.get("/api/v1/cloud-config")', '@api.put("/api/v1/cloud-config")')
    assert "cloud_generation.public_config()" in get_block

    put_block = _between(src, '@api.put("/api/v1/cloud-config")', "@api.get(")
    assert "cloud_generation.save_env(body)" in put_block
    assert "must be local, minimax, fal or muapi" in put_block
    assert "cloud_generation.public_config()" in put_block


def test_llm_override_only_when_local_provider_selected():
    src = _read(APP / "launch.py")
    anchor = src.index("from services.cloud_generation import llm_override")
    window = src[anchor:anchor + 600]
    assert 'llm_override() if desired_provider == "local" else None' in window
    assert 'desired_remote_url, desired_api_key = cloud_llm["remote_url"], cloud_llm["api_key"]' in window


def test_engine_exports_every_provider_and_job_bridge():
    cg = _read(APP / "services" / "cloud_generation.py")
    for symbol in ("class MiniMax", "class Fal", "class MuApi", "CLIENTS = {",
                   "def execute(", "def active_provider(", "def public_config(", "def llm_override("):
        assert symbol in cg, symbol
    assert "import torch" not in cg  # cloud jobs must run on a machine without a GPU


def test_engine_never_returns_key_values():
    cg = _read(APP / "services" / "cloud_generation.py")
    config = _between(cg, "def public_config(", "def llm_override(")
    assert '"keys": {k: bool(env(k)) for k in SECRET_KEYS}' in config


def test_save_env_whitelist_covers_only_writable_keys():
    cg = _read(APP / "services" / "cloud_generation.py")
    assert "allowed = set(SECRET_KEYS) | set(PLAIN_KEYS)" in cg
    assert "if k in allowed" in cg


def test_director_reuses_launch_worker_and_has_no_own_hook():
    dp = _read(APP / "services" / "director_pipeline.py")
    assert "_run_generation = run_gen_fn" in dp          # init() takes the worker
    assert "_run_generation(job_id)" in dp               # _submit_and_wait calls it
    assert "cloud_generation" not in dp                  # one hook, in launch.py

    launch = _read(APP / "launch.py")
    wiring = re.search(r"pipeline_init\(\s*_jobs,\s*_run_generation,", launch)
    assert wiring, "launch must hand _run_generation to director_pipeline.init"


def test_editor_services_have_no_cloud_hook():
    editor_files = sorted((APP / "services").glob("editor_*.py"))
    assert editor_files, "editor services are expected in app/services"
    for path in editor_files:
        text = _read(path)
        assert "cloud_generation" not in text, path.name
        assert "CLOUD_PROVIDER" not in text, path.name


def test_env_example_documents_every_writable_key():
    cg = _read(APP / "services" / "cloud_generation.py")
    keys = re.findall(r'"([A-Z][A-Z0-9_]+)"', _between(cg, "SECRET_KEYS = (", "\n"))
    keys += re.findall(r'"([A-Z][A-Z0-9_]+)"', _between(cg, "PLAIN_KEYS = (", "\n"))
    assert "CLOUD_PROVIDER" in keys and "FAL_KEY" in keys

    example = _read(ROOT / ".env.example")
    declared = {line.split("=", 1)[0].strip()
                for line in example.splitlines()
                if "=" in line and not line.lstrip().startswith("#")}
    assert set(keys) <= declared, sorted(set(keys) - declared)

    secrets = re.findall(r'"([A-Z][A-Z0-9_]+)"', _between(cg, "SECRET_KEYS = (", "\n"))
    for key in secrets:
        assert re.search(rf"^{key}=\s*$", example, re.M), key


def test_env_is_ignored_but_example_is_tracked():
    ignore = _read(ROOT / ".gitignore")
    assert "/.env" in ignore and "!/.env.example" in ignore


def test_cloud_control_is_mounted_in_studio_director_and_settings():
    for rel in ("Sidebar/Sidebar.tsx", "Sidebar/DirectorChat.tsx",
                "SettingsDrawer/ServicesSettingsPanel.tsx"):
        text = _read(UI / rel)
        assert "CloudEngineControl" in text, rel
        assert "from '../shared/CloudEngineControl'" in text, rel

    settings = _read(UI / "SettingsDrawer/ServicesSettingsPanel.tsx")
    assert "<CloudEngineControl full />" in settings  # keys are only editable in Settings


def test_cloud_control_never_renders_a_stored_key():
    control = _read(UI / "shared/CloudEngineControl.tsx")
    assert 'maskedValue="••••••••"' in control
    assert "config.keys[" in control  # reads booleans only


def test_no_cuda_start_guard_in_wgp():
    wgp = _read(APP / "wgp.py")
    assert "if torch.cuda.is_available() else (0, 0)" in wgp
