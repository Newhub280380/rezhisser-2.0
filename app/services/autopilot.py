"""Assistant autopilot: run a recipe from docs/assistant-knowledge end to end on the server.

photo_to_film: background removal (fal birefnet) -> upscale to 4K (fal clarity-upscaler, local
Pillow if fal fails) -> JPEG -> LLM storyboard (storyboard_prompt, JSON) -> keyframes for scenes
without a photo -> scenes on fal (Wan 2.2 default, MiniMax H3 fallback, at most 2 retries per
scene) -> ffmpeg concat to mp4 1080x1920 H.264.

viral_remake (frame): yt-dlp download -> ffmpeg scene stills -> multimodal LLM turns stills into
scene prompts (optionally replacing the subject with the person's photo) -> scenes -> concat.

Reuses Maestro's cloud backend (cloud_generation.Fal), the assistant's LLM settings
(assistant_chat.complete) and Maestro's ffmpeg resolver. Keys come only from .env settings.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from PIL import Image

from services import assistant_knowledge as kb
from services import cloud_generation as cg

TARGET_LONG_SIDE = 3840
MAX_SCENE_RETRIES = 2
FRAME = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
# Scene request size per quality; Fal maps the short side to Wan 480p / 720p.
DRAFT = {"9:16": (480, 854), "16:9": (854, 480), "1:1": (480, 480)}
FINAL = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (720, 720)}

RUNS: dict[str, dict] = {}
_LOCK = threading.Lock()


class AutopilotError(RuntimeError):
    pass


# ---------------------------------------------------------------- run state

def _public(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.startswith("_")}


def get_run(run_id: str) -> dict | None:
    with _LOCK:
        state = RUNS.get(run_id)
        return _public(state) if state else None


def cancel_run(run_id: str) -> bool:
    with _LOCK:
        state = RUNS.get(run_id)
        if not state:
            return False
        state["_cancel"] = True
        return True


def _progress(state: dict, label: str, progress: float, step: str) -> None:
    with _LOCK:
        state.update(label=label, progress=round(progress), step=step)
        if not state["log"] or state["log"][-1] != label:
            state["log"].append(label)


def start(recipe_id: str, options: dict, *, out_dir: Path, work_root: Path,
          deps: "Deps | None" = None, background: bool = True) -> dict:
    """Create a run and execute it (in a thread by default). Returns the public state."""
    if recipe_id not in kb.AUTOPILOT_RECIPES:
        raise AutopilotError(f"Автопилот не умеет рецепт {recipe_id}.")
    run_id = uuid.uuid4().hex[:12]
    state = {"id": run_id, "recipe": recipe_id, "status": "running", "step": "", "label": "",
             "progress": 0, "log": [], "scenes": 0, "warnings": [], "output": None, "error": None,
             "_cancel": False}
    with _LOCK:
        RUNS[run_id] = state
    runner = Runner(state, options, out_dir=Path(out_dir), work_dir=Path(work_root) / f"autopilot_{run_id}",
                    deps=deps or Deps())
    if background:
        threading.Thread(target=runner.run, name=f"autopilot-{run_id}", daemon=True).start()
    else:
        runner.run()
    return get_run(run_id)


# ---------------------------------------------------------------- external calls (mockable)

class Deps:
    """Cloud and tool calls in one place so tests can replace them."""

    def fal(self) -> cg.Fal:
        if not cg.ready("fal"):
            raise AutopilotError("Нет ключа fal. Настройки → Integrations → Cloud.")
        return cg.Fal()

    def fal_call(self, model: str, body: dict, cancelled) -> dict:
        return self.fal().call(model, body, cancelled)

    def fal_media(self, req: dict, out: Path, cancelled) -> Path:
        return self.fal().run(req, out, cancelled)

    def llm(self, messages: list[dict]) -> str:
        from services import assistant_chat
        return assistant_chat.complete(messages)

    def download(self, url: str, out: Path) -> Path:
        return cg.download(url, out)

    def ffmpeg(self) -> str:
        from services.title_cards import _resolve_ffmpeg  # Maestro's bundled-first ffmpeg lookup
        return _resolve_ffmpeg(None)

    def fetch_video(self, url: str, work_dir: Path) -> Path:
        import yt_dlp
        work_dir.mkdir(parents=True, exist_ok=True)
        options = {"outtmpl": str(work_dir / "source.%(ext)s"), "format": "mp4/bestvideo*+bestaudio/best",
                   "merge_output_format": "mp4", "quiet": True, "noplaylist": True,
                   "ffmpeg_location": str(Path(self.ffmpeg()).parent)}
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
        files = sorted(work_dir.glob("source.*"))
        if not files:
            raise AutopilotError(f"Не удалось скачать ролик: {info.get('title') if info else url}")
        return files[0]


# ---------------------------------------------------------------- runner

class Runner:
    def __init__(self, state: dict, options: dict, *, out_dir: Path, work_dir: Path, deps: Deps):
        self.state, self.options, self.out_dir, self.work_dir, self.deps = state, options, out_dir, work_dir, deps
        self.recipes = kb.recipes()
        self.aspect = options.get("aspect") if options.get("aspect") in FRAME else "9:16"
        self.cancelled = lambda: bool(state.get("_cancel"))

    def label(self, index: int, **values) -> str:
        labels = kb.recipe("photo_to_film")["progress_labels"]
        text = labels[index]
        for key, value in values.items():
            text = text.replace("{" + key + "}", str(value))
        return text

    def run(self) -> None:
        try:
            self.work_dir.mkdir(parents=True, exist_ok=True)
            if self.state["recipe"] == "photo_to_film":
                output = self.photo_to_film()
            else:
                output = self.viral_remake()
            with _LOCK:
                self.state.update(status="done", output={"filename": output.name, "url": f"/api/v1/file/{output.name}"})
            _progress(self.state, self.label(6), 100, "done")
        except InterruptedError:
            with _LOCK:
                self.state.update(status="cancelled", error="Остановлено.")
        except Exception as error:  # surfaced to the chat as the run's error
            with _LOCK:
                self.state.update(status="failed", error=str(error) or error.__class__.__name__)

    def check(self) -> None:
        if self.cancelled():
            raise InterruptedError("Cancelled")

    # ------------------------------------------------------------ photo_to_film

    def photo_to_film(self) -> Path:
        photos = [Path(p) for p in self.options.get("photos") or []]
        if not photos:
            raise AutopilotError("Нужно хотя бы одно фото.")
        if len(photos) > 20:
            raise AutopilotError("Не больше 20 фото за раз.")
        total = int(self.options.get("total_seconds") or 60)
        total = max(5, min(300, total))
        prepared = []
        n = len(photos)
        for i, photo in enumerate(photos, 1):
            image = photo
            if self.options.get("remove_background", True):
                _progress(self.state, f"{self.label(0)} ({i} из {n})", 2 + 8 * i / n, "remove_background")
                image = self.remove_background(image, i)
            _progress(self.state, f"{self.label(1)} ({i} из {n})", 10 + 8 * i / n, "upscale_image")
            image = self.upscale(image, i)
            _progress(self.state, f"{self.label(2)} ({i} из {n})", 18 + 4 * i / n, "convert_jpeg")
            prepared.append(self.to_jpeg(image, i))
        _progress(self.state, self.label(3), 24, "write_storyboard")
        notes = ", ".join(f"фото {i}: {p.stem}" for i, p in enumerate(photos, 1))
        scenes = self.storyboard(len(prepared), notes, total)
        return self.render(scenes, prepared, "photo_to_film")

    def remove_background(self, image: Path, index: int) -> Path:
        tools = self.recipes["tools"]["remove_background"]
        body = {"image_url": cg.data_uri(image), "output_format": "png"}
        try:
            result = self.deps.fal_call(tools.get("fal_model_hint", "fal-ai/birefnet/v2"), body, self.cancelled)
        except cg.CloudError:
            # shortcut: bria fallback assumed to return image.url like birefnet; verify if it ever 4xx's.
            result = self.deps.fal_call(tools.get("fallback", "fal-ai/bria/background/remove"),
                                        {"image_url": body["image_url"]}, self.cancelled)
        return self.deps.download(_image_url(result), self.work_dir / f"nobg_{index}.png")

    def upscale(self, image: Path, index: int) -> Path:
        with Image.open(image) as im:
            long_side = max(im.size)
            if _has_alpha(im):  # upscalers drop alpha unpredictably: fill the cut-out background white first
                flat = self.work_dir / f"flat_{index}.png"
                _flatten(im).save(flat)
                image = flat
        factor = min(4.0, TARGET_LONG_SIDE / max(long_side, 1))
        if factor <= 1.01:
            return image
        model = self.recipes["tools"]["upscale_image"].get("fal_model_hint", "fal-ai/clarity-upscaler")
        try:
            result = self.deps.fal_call(model, {"image_url": cg.data_uri(image),
                                                "upscale_factor": round(factor, 2)}, self.cancelled)
            return self.deps.download(_image_url(result), self.work_dir / f"up_{index}{image.suffix or '.png'}")
        except cg.CloudError as error:
            self.state["warnings"].append(f"Фото {index}: облачный апскейл не удался ({error}); увеличено локально.")
            return image  # to_jpeg resizes to 4K with Lanczos

    def to_jpeg(self, image: Path, index: int) -> Path:
        out = self.work_dir / f"photo_{index}.jpg"
        with Image.open(image) as im:
            im = _flatten(im)
            scale = TARGET_LONG_SIDE / max(im.size)
            if abs(scale - 1) > 0.01:
                im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
            im.save(out, "JPEG", quality=95)
        return out

    def storyboard(self, n_photos: int, notes: str, total: int) -> list[dict]:
        template = self.recipes["storyboard_prompt"]
        values = {"n_photos": n_photos, "photo_notes": notes, "total_seconds": total, "aspect": self.aspect,
                  "user_request": self.options.get("request") or "мини-ролик из фото"}
        for key, value in values.items():  # str.format would trip on the JSON braces in the template
            template = template.replace("{" + key + "}", str(value))
        text = self.deps.llm([{"role": "user", "content": template}])
        return normalize_scenes(parse_json(text), n_photos, total, self.recipes.get("negative_prompt_default", ""))

    # ------------------------------------------------------------ shared tail

    def render(self, scenes: list[dict], images: list[Path], tag: str) -> Path:
        n = len(scenes)
        with _LOCK:
            self.state["scenes"] = n
        clips = []
        size = (FINAL if self.options.get("quality") == "final" else DRAFT)[self.aspect]
        for i, scene in enumerate(scenes, 1):
            self.check()
            _progress(self.state, self.label(4, i=i, n=n), 28 + 64 * (i - 1) / n, "generate_scene")
            image = images[scene["photo_index"] - 1] if scene["photo_index"] else self.keyframe(scene, i)
            clips.append(self.scene(scene, image, size, i))
        _progress(self.state, self.label(5), 94, "concat_clips")
        name = f"{time.strftime('%Y-%m-%d-%Hh%Mm%Ss')}_autopilot_{tag}_{self.state['id']}.mp4"
        return self.concat(clips, self.out_dir / name)

    def keyframe(self, scene: dict, index: int) -> Path:
        w, h = FRAME[self.aspect]
        req = {"kind": "image", "prompt": scene["prompt"], "image": None, "width": w, "height": h,
               "ratio": self.aspect, "resolution": "2K", "duration": 0}
        return self.deps.fal_media(req, self.work_dir / f"key_{index}.png", self.cancelled)

    def scene(self, scene: dict, image: Path | None, size: tuple[int, int], index: int) -> Path:
        w, h = size
        req = {"kind": "video", "prompt": scene["prompt"], "negative_prompt": scene["negative_prompt"],
               "image": image, "image_end": None, "width": w, "height": h, "ratio": self.aspect,
               "resolution": "768P", "duration": scene["seconds"]}
        # Wan 2.2 first; the last retry goes to MiniMax H3 (recipes.json fallback_engine).
        engines = [None] * MAX_SCENE_RETRIES + ["h3"]
        errors = []
        for attempt, engine in enumerate(engines):
            self.check()
            try:
                out = self.work_dir / f"scene_{index:02d}_try{attempt}.mp4"
                return self.deps.fal_media(dict(req, engine=engine), out, self.cancelled)
            except cg.CloudError as error:
                errors.append(str(error))
        raise AutopilotError(f"Сцена {index} не получилась после {len(engines)} попыток: {errors[-1]}")

    def concat(self, clips: list[Path], out: Path) -> Path:
        w, h = FRAME[self.aspect]
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [self.deps.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error"]
        for clip in clips:
            cmd += ["-i", str(clip)]
        chains = "".join(
            f"[{k}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,fps=30,format=yuv420p[v{k}];" for k in range(len(clips)))
        graph = chains + "".join(f"[v{k}]" for k in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[out]"
        cmd += ["-filter_complex", graph, "-map", "[out]", "-c:v", "libx264", "-preset", "medium",
                "-b:v", "16M", "-maxrate", "20M", "-bufsize", "32M", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(out)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not out.is_file():
            raise AutopilotError(f"Склейка не удалась: {result.stderr.strip()[-400:]}")
        return out

    # ------------------------------------------------------------ viral_remake (frame)

    def viral_remake(self) -> Path:
        source = self.options.get("source_video")
        if source:
            video = Path(source)
        else:
            url = self.options.get("source_url") or ""
            if not re.match(r"https?://", url):
                raise AutopilotError("Нужна ссылка на ролик (http/https) или загруженный файл.")
            _progress(self.state, "Скачиваю ролик", 3, "fetch_video")
            video = self.deps.fetch_video(url, self.work_dir)
        _progress(self.state, "Нарезаю стоп-кадры", 8, "extract_frames")
        frames = self.extract_frames(video)
        _progress(self.state, "Разбираю ролик в промпт", 15, "video_to_prompt")
        replace = Path(self.options["replace_photo"]) if self.options.get("replace_photo") else None
        scenes = self.video_to_prompt(frames, replace)
        images = [self.to_jpeg(f, i) for i, f in enumerate(frames, 1)]
        if replace:
            images.append(self.to_jpeg(replace, len(images) + 1))
            for scene in scenes:  # replacement subject drives every scene marked for it
                if scene.pop("replace", False):
                    scene["photo_index"] = len(images)
        return self.render(scenes, images, "viral_remake")

    def extract_frames(self, video: Path, limit: int = 12) -> list[Path]:
        frames_dir = self.work_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        base = [self.deps.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(video)]
        for vf in ("select='eq(n\\,0)+gt(scene\\,0.3)',scale=720:-2", "fps=1/3,scale=720:-2"):
            for old in frames_dir.glob("*.jpg"):
                old.unlink()
            subprocess.run(base + ["-vf", vf, "-fps_mode", "vfr", "-frames:v", str(limit),
                                   str(frames_dir / "frame_%03d.jpg")], capture_output=True, text=True)
            frames = sorted(frames_dir.glob("frame_*.jpg"))
            if len(frames) >= 2 or (frames and vf.startswith("fps")):
                return frames
        if not frames:
            raise AutopilotError("Не удалось достать кадры из ролика.")
        return frames

    def video_to_prompt(self, frames: list[Path], replace: Path | None) -> list[dict]:
        recipe = kb.recipe("viral_remake")
        step = next(s for s in recipe["steps"] if s.get("tool") == "video_to_prompt")
        text = (step["params"]["prompt"] + "\n" + "\n".join(recipe.get("rules", []))
                + f"\nЗадача человека: {self.options.get('request') or 'ремейк этого ролика'}."
                + f"\nКадров: {len(frames)} (по порядку)." + (" Последнее изображение — фото для замены [ОБЪЕКТ]."
                                                              if replace else "")
                + ' Верни JSON: {"scenes":[{"index":1,"frame":1,"seconds":5,"prompt":"...","negative_prompt":"...",'
                  '"replace":true}]} — одна сцена на кадр, prompt тегами для Wan 2.2, глагол камеры первым.')
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for path in frames[:8] + ([replace] if replace else []):
            content.append({"type": "image_url", "image_url": {"url": cg.data_uri(path)}})
        data = parse_json(self.deps.llm([{"role": "user", "content": content}]))
        for scene in data.get("scenes", []):
            scene.setdefault("photo_index", scene.get("frame"))
        scenes = normalize_scenes(data, len(frames), 5 * len(frames), self.recipes.get("negative_prompt_default", ""),
                                  keep=("replace",))
        return scenes


# ---------------------------------------------------------------- helpers

def _has_alpha(im: Image.Image) -> bool:
    return im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)


def _flatten(im: Image.Image) -> Image.Image:
    """RGB without alpha; transparent background -> white (recipes.json convert_jpeg)."""
    im.load()
    if not _has_alpha(im):
        return im.convert("RGB")
    rgba = im.convert("RGBA")
    flat = Image.new("RGB", rgba.size, (255, 255, 255))
    flat.paste(rgba, mask=rgba.split()[-1])
    return flat


def _image_url(result: dict) -> str:
    url = (result.get("image") or {}).get("url") or ((result.get("images") or [{}])[0] or {}).get("url")
    if not url:
        raise cg.CloudError(f"fal: no image url in {list(result)}")
    return url


def parse_json(text: str) -> dict:
    """LLM answers often wrap JSON in prose or ``` fences: take the outermost object."""
    start, end = (text or "").find("{"), (text or "").rfind("}")
    if start < 0 or end <= start:
        raise AutopilotError("Модель не вернула раскадровку в JSON.")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as error:
        raise AutopilotError(f"Раскадровка — не JSON: {error}") from error


def normalize_scenes(data: dict, n_photos: int, total: int, negative: str, keep: tuple = ()) -> list[dict]:
    raw = data.get("scenes") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        raise AutopilotError("В раскадровке нет сцен.")
    limit = max(1, math.ceil(total / 5) + 2)  # guard against runaway scene counts (cost)
    scenes = []
    for item in raw[:limit]:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            continue
        try:
            seconds = int(round(float(item.get("seconds") or 5)))
        except (TypeError, ValueError):
            seconds = 5
        photo = item.get("photo_index")
        photo = photo if isinstance(photo, int) and 1 <= photo <= n_photos else None
        scene = {"index": len(scenes) + 1, "seconds": max(5, min(10, seconds)), "photo_index": photo,
                 "prompt": prompt, "negative_prompt": str(item.get("negative_prompt") or negative),
                 "caption": str(item.get("caption") or "")}
        for key in keep:
            if key in item:
                scene[key] = item[key]
        scenes.append(scene)
    if not scenes:
        raise AutopilotError("В раскадровке нет сцен с промптом.")
    return scenes


def resolve_upload(name: str, uploads_dir: Path) -> Path:
    """Trust boundary: only files inside the uploads folder may be fed to the pipeline."""
    base = uploads_dir.resolve()
    path = (base / Path(str(name)).name).resolve()
    if path.parent != base or not path.is_file():
        raise AutopilotError(f"Файл {Path(str(name)).name} не найден среди загрузок.")
    return path

