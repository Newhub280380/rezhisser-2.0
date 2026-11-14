"""Assistant autopilot: "5 photos -> finished film" with fal and the LLM mocked; ffmpeg and Pillow are real."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from services import assistant_chat  # noqa: E402
from services import assistant_knowledge as kb  # noqa: E402
from services import autopilot  # noqa: E402
from services import cloud_generation as cg  # noqa: E402


def _ffmpeg():
    try:
        return autopilot.Deps().ffmpeg()
    except Exception:
        pytest.skip("ffmpeg is needed to render clips")


def _probe(ffmpeg: str, path: Path) -> str:
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    return result.stderr


class FakeDeps(autopilot.Deps):
    """Records every cloud call; fal and the LLM never touch the network."""

    def __init__(self, tmp: Path, storyboard: str, scene_failures: dict):
        self.tmp, self.storyboard, self.scene_failures = tmp, storyboard, scene_failures
        self.calls, self.llm_prompts, self.video_reqs = [], [], []

    def fal_call(self, model, body, cancelled):
        self.calls.append((model, sorted(body)))
        self.bodies = getattr(self, "bodies", []) + [(model, body)]
        assert body["image_url"].startswith("data:image/")
        return {"image": {"url": f"https://fal.mock/{model}/{len(self.calls)}.png"}}

    def download(self, url, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        if "birefnet" in url:  # transparent cut-out
            Image.new("RGBA", (600, 900), (200, 50, 50, 0)).save(out)
        else:  # clarity upscaler x factor
            Image.new("RGB", (2400, 3600), (40, 120, 200)).save(out)
        return out

    def llm(self, messages):
        self.llm_prompts.append(messages[0]["content"])
        return "Вот раскадровка:\n```json\n" + self.storyboard + "\n```"

    def fal_media(self, req, out, cancelled):
        self.video_reqs.append(dict(req, image=str(req["image"]) if req.get("image") else None))
        if req["kind"] == "image":  # keyframe for a scene without a photo
            Image.new("RGB", (req["width"], req["height"]), (10, 200, 10)).save(out)
            return out
        key = (Path(out).name.split("_try")[0], req.get("engine"))
        if self.scene_failures.get(key, 0) > 0:
            self.scene_failures[key] -= 1
            raise cg.CloudError("fal mock: FAILED")
        size = "480x854" if req["width"] < req["height"] else "854x480"
        subprocess.run([self.ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"testsrc=size={size}:rate=16:duration=1", "-pix_fmt", "yuv420p", str(out)], check=True)
        return out


def _photos(tmp: Path, n=5):
    uploads = tmp / "uploads"
    uploads.mkdir()
    paths = []
    for i in range(1, n + 1):
        path = uploads / f"product_{i}.png"
        Image.new("RGB", (1200, 1600), (30 * i, 80, 160)).save(path)
        paths.append(path)
    return paths


STORYBOARD = {
    "scenes": [
        {"index": 1, "seconds": 5, "photo_index": 1, "camera": "slow dolly push in", "action": "a",
         "prompt": "slow dolly push in, perfume bottle on black marble", "negative_prompt": "", "caption": "Хук"},
        {"index": 2, "seconds": 12, "photo_index": 2, "prompt": "orbit left, bottle, soft rim light"},
        {"index": 3, "seconds": 3, "photo_index": 3, "prompt": "tilt up, bottle, steam rising"},
        {"index": 4, "seconds": 7, "photo_index": None, "prompt": "macro, gel texture, studio light"},
        {"index": 5, "seconds": 5, "photo_index": 99, "prompt": "pull back, bottle and box, CTA"},
        {"index": 6, "prompt": ""},
    ],
    "music_mood": "calm", "voiceover": "",
}


def test_five_photos_to_finished_film(tmp_path):
    ffmpeg = _ffmpeg()
    photos = _photos(tmp_path)
    # scene 2: Wan fails once (retry on Wan); scene 3: Wan fails twice -> MiniMax H3 fallback
    deps = FakeDeps(tmp_path, json.dumps(STORYBOARD, ensure_ascii=False),
                    {("scene_02", None): 1, ("scene_03", None): 2})
    deps.ffmpeg = lambda: ffmpeg
    out_dir = tmp_path / "outputs"
    state = autopilot.start(
        "photo_to_film",
        {"photos": [str(p) for p in photos], "request": "вот 5 фото, сделай мини-ролик на 2–3 минуты",
         "total_seconds": 150, "aspect": "9:16"},
        out_dir=out_dir, work_root=tmp_path / "work", deps=deps, background=False)

    assert state["status"] == "done", state["error"]
    labels = kb.recipe("photo_to_film")["progress_labels"]
    log = state["log"]
    # every step of recipes.json/photo_to_film, in order, with its progress label
    order = [next(i for i, line in enumerate(log) if line.startswith(prefix)) for prefix in
             (labels[0], labels[1], labels[2], labels[3], "Генерирую сцену 1 из 5", "Генерирую сцену 5 из 5",
              labels[5], labels[6])]
    assert order == sorted(order)
    assert "Убираю фон (5 из 5)" in log and "Генерирую сцену 3 из 5" in log

    # 1) background removal and 2) 4K upscale on fal, once per photo
    models = [m for m, _ in deps.calls]
    assert models.count("fal-ai/birefnet/v2") == 5 and models.count("fal-ai/clarity-upscaler") == 5
    # transparent cut-out is flattened to white before it goes to the upscaler
    import base64, io
    sent = next(b for m, b in deps.bodies if m == "fal-ai/clarity-upscaler")
    with Image.open(io.BytesIO(base64.b64decode(sent["image_url"].split(",", 1)[1]))) as up_in:
        assert up_in.mode == "RGB" and up_in.getpixel((5, 5)) == (255, 255, 255)
    assert sent["upscale_factor"] == 4.0  # 900 px cut-out needs 4.27x: capped at 4, the JPEG step tops up to 3840
    # 3) JPEG 4K
    jpgs = sorted((tmp_path / "work").glob("autopilot_*/photo_*.jpg"))
    assert len(jpgs) == 5
    with Image.open(jpgs[0]) as im:
        assert im.format == "JPEG" and max(im.size) == autopilot.TARGET_LONG_SIDE and im.mode == "RGB"
    # 4) storyboard prompt from recipes.json, filled in
    prompt = deps.llm_prompts[0]
    assert "5 фото" in prompt and "150 с" in prompt and "9:16" in prompt and "{n_photos}" not in prompt
    # 5) keyframe for the scene without a photo, 6) scenes on Wan with retries and H3 fallback
    assert state["scenes"] == 5
    videos = [r for r in deps.video_reqs if r["kind"] == "video"]
    assert [r["engine"] for r in videos] == [None, None, None, None, None, "h3", None, None]
    assert videos[1]["duration"] == 10 and videos[3]["duration"] == 5  # 12 s and 3 s clamped to 5–10
    assert all(r["negative_prompt"] for r in videos) and videos[0]["width"] == 480
    keyframes = [r for r in deps.video_reqs if r["kind"] == "image"]
    assert len(keyframes) == 2  # scene 4 (null) and scene 5 (photo 99 does not exist)
    assert videos[-1]["image"].endswith("key_5.png")
    # 7) final mp4: H.264, 1080x1920, in the gallery output folder
    out = out_dir / state["output"]["filename"]
    assert out.suffix == ".mp4" and out.is_file() and state["output"]["url"] == f"/api/v1/file/{out.name}"
    info = _probe(ffmpeg, out)
    assert "h264" in info and "1080x1920" in info and "Duration: 00:00:05" in info


def test_scene_fails_after_two_retries_and_run_reports_it(tmp_path):
    ffmpeg = _ffmpeg()
    photos = _photos(tmp_path, 1)
    board = json.dumps({"scenes": [{"seconds": 5, "photo_index": 1, "prompt": "push in, bottle"}]})
    deps = FakeDeps(tmp_path, board, {("scene_01", None): 9, ("scene_01", "h3"): 9})
    deps.ffmpeg = lambda: ffmpeg
    state = autopilot.start("photo_to_film", {"photos": [str(photos[0])], "remove_background": False},
                            out_dir=tmp_path / "o", work_root=tmp_path / "w", deps=deps, background=False)
    assert state["status"] == "failed" and "3 попыток" in state["error"]
    assert len([r for r in deps.video_reqs if r["kind"] == "video"]) == 3  # 1 + 2 retries, last on H3
    assert not any(m == "fal-ai/birefnet/v2" for m, _ in deps.calls)


def test_viral_remake_frame(tmp_path):
    """Link -> (mocked) download -> real ffmpeg stills -> multimodal LLM -> replace subject -> scenes -> mp4."""
    ffmpeg = _ffmpeg()
    photos = _photos(tmp_path, 1)
    source = tmp_path / "viral.mp4"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x568:rate=10:duration=7",
                    "-pix_fmt", "yuv420p", str(source)], check=True)
    board = json.dumps({"scenes": [{"frame": 1, "seconds": 5, "prompt": "handheld, woman holds bottle", "replace": True},
                                   {"frame": 2, "seconds": 5, "prompt": "close up, bottle"}]})
    deps = FakeDeps(tmp_path, board, {})
    deps.ffmpeg = lambda: ffmpeg
    fetched = []
    deps.fetch_video = lambda url, work: fetched.append(url) or source
    state = autopilot.start("viral_remake", {"source_url": "https://www.tiktok.com/@x/video/1",
                                             "replace_photo": str(photos[0])},
                            out_dir=tmp_path / "o", work_root=tmp_path / "w", deps=deps, background=False)
    assert state["status"] == "done", state["error"]
    assert fetched == ["https://www.tiktok.com/@x/video/1"]
    content = deps.llm_prompts[0]
    assert content[0]["type"] == "text" and "[ОБЪЕКТ]" in content[0]["text"]
    assert sum(1 for part in content if part["type"] == "image_url") >= 3  # stills + replacement photo
    videos = [r for r in deps.video_reqs if r["kind"] == "video"]
    assert videos[0]["image"].endswith(".jpg") and len(videos) == 2
    assert "1080x1920" in _probe(ffmpeg, tmp_path / "o" / state["output"]["filename"])


def test_resolve_upload_is_a_trust_boundary(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "a.png").write_bytes(b"x")
    (tmp_path / "secret.txt").write_text("no")
    assert autopilot.resolve_upload("a.png", uploads) == (uploads / "a.png").resolve()
    for bad in ("../secret.txt", str(tmp_path / "secret.txt"), "missing.png"):
        with pytest.raises(autopilot.AutopilotError):
            autopilot.resolve_upload(bad, uploads)


def test_parse_and_normalize_storyboard():
    data = autopilot.parse_json('ok ```json {"scenes":[{"prompt":"a","seconds":"30","photo_index":2}]} ```')
    scenes = autopilot.normalize_scenes(data, 1, 60, "neg")
    assert scenes == [{"index": 1, "seconds": 10, "photo_index": None, "prompt": "a",
                       "negative_prompt": "neg", "caption": ""}]
    with pytest.raises(autopilot.AutopilotError):
        autopilot.parse_json("no json here")
    many = {"scenes": [{"prompt": f"s{i}"} for i in range(100)]}
    assert len(autopilot.normalize_scenes(many, 1, 10, "")) == 4  # 10 s -> at most ceil(10/5)+2 scenes


def test_knowledge_comes_from_the_folder(monkeypatch):
    summary = kb.summary()
    ids = [c["id"] for c in summary["categories"]]
    assert ids == ["photo_to_film", "photo_to_video", "text_to_video", "face_swap", "viral_remake", "talking_head"]
    assert len(summary["commands"]) == 19 and summary["commands"][0]["command"].startswith("/")
    assert [c["id"] for c in summary["categories"] if c["autopilot"]] == ["photo_to_film", "viral_remake"]
    # the chat system prompt is built from the folder, and a slash command pulls in its template
    monkeypatch.setattr(assistant_chat.cloud_generation, "env",
                        lambda name: {"LLM_API_KEY": "k", "LLM_BASE_URL": "https://openrouter.ai/api/v1"}.get(name, ""))
    sent = []
    monkeypatch.setattr(assistant_chat, "_post_json", lambda url, payload, key, timeout=90: sent.append(payload) or
                        {"choices": [{"message": {"role": "assistant", "content": "ok"}}]})
    first = summary["commands"][0]["command"]
    assistant_chat.chat({"messages": [{"role": "user", "content": f"{first} духи на мраморе"}],
                         "context": {"category": "photo_to_film"}})
    system = sent[0]["messages"][0]["content"]
    assert "photo_to_film" in system and "Выбранный рецепт" in system and f"Человек вызвал команду {first}" in system
    assert "storyboard_prompt" not in system or "progress_labels" in system
    # pipeline completions skip the persona and tools
    assert assistant_chat.complete([{"role": "user", "content": "x"}]) == "ok"
    assert sent[1]["messages"] == [{"role": "user", "content": "x"}]


def test_launch_exposes_autopilot_routes():
    source = (Path(__file__).resolve().parents[1] / "app" / "launch.py").read_text(encoding="utf-8")
    for route in ('@api.get("/api/v1/assistant/knowledge")', '@api.post("/api/v1/assistant/autopilot")',
                  '@api.get("/api/v1/assistant/autopilot/{run_id}")',
                  '@api.post("/api/v1/assistant/autopilot/{run_id}/cancel")'):
        assert route in source
    assert "autopilot.resolve_upload(" in source
