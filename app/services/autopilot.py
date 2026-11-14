"""Assistant autopilot: run a recipe from docs/assistant-knowledge end to end on the server.

photo_to_film: background removal (fal birefnet) -> upscale to 4K (fal clarity-upscaler, local
Pillow if fal fails) -> JPEG -> LLM storyboard (storyboard_prompt, JSON) -> keyframes for scenes
without a photo -> scenes on fal (Wan 2.2 default, MiniMax H3 fallback, at most 2 retries per
scene) -> ffmpeg concat to mp4 1080x1920 H.264.

viral_remake (frame): yt-dlp download -> ffmpeg scene stills -> multimodal LLM turns stills into
scene prompts (optionally replacing the subject with the person's photo) -> scenes -> concat.

Reuses Режиссёр 2.0's cloud backend (cloud_generation.Fal), the assistant's LLM settings
(assistant_chat.complete) and Режиссёр 2.0's ffmpeg resolver. Keys come only from .env settings.
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
             "_cancel": False, "_options": options}
    with _LOCK:
        RUNS[run_id] = state
    runner = Runner(state, options, out_dir=Path(out_dir), work_dir=Path(work_root) / f"autopilot_{run_id}",
                    deps=deps or Deps())
    if background:
        threading.Thread(target=runner.run, name=f"autopilot-{run_id}", daemon=True).start()
    else:
        runner.run()
    return get_run(run_id)


def regenerate_scene(run_id: str, index: int, prompt: str = "", *, out_dir: Path, work_root: Path,
                     deps: "Deps | None" = None, background: bool = True) -> dict:
    """Re-shoot one scene of a finished one_prompt_film run and re-assemble (other scenes reused)."""
    with _LOCK:
        state = RUNS.get(run_id)
        if not state:
            raise AutopilotError("Нет такого запуска.")
        if state["status"] == "running":
            raise AutopilotError("Запуск ещё идёт.")
        if not state.get("_project"):
            raise AutopilotError("Перегенерация сцены есть только у ролика «Одной фразой».")
        state.update(status="running", error=None, _cancel=False, progress=0)
    options = dict(state["_options"], regenerate_scene=int(index), prompt=str(prompt or ""))
    runner = Runner(state, options, out_dir=Path(out_dir), work_dir=Path(work_root) / f"autopilot_{run_id}",
                    deps=deps or Deps())
    if background:
        threading.Thread(target=runner.run, name=f"autopilot-{run_id}-scene{index}", daemon=True).start()
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
        from services.title_cards import _resolve_ffmpeg  # Режиссёр 2.0's bundled-first ffmpeg lookup
        return _resolve_ffmpeg(None)

    def fetch_video(self, url: str, work_dir: Path) -> Path:
        import yt_dlp
        work_dir.mkdir(parents=True, exist_ok=True)
        options = {"outtmpl": str(work_dir / "source.%(ext)s"), "format": "mp4/bestvideo*+bestaudio/best",
                   "merge_output_format": "mp4", "quiet": True, "noplaylist": True,
                   "ffmpeg_location": str(Path(self.ffmpeg()).parent)}
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
        files = sorted(p for p in work_dir.glob("source.*") if p.suffix != ".part")
        if not files:
            raise AutopilotError(f"Не удалось скачать ролик: {info.get('title') if info else url}")
        return files[0]


    def tts(self, text: str, language: str, out: Path, cancelled, voice: dict | None = None) -> Path:
        """Kokoro on fal for English (it has no Russian); free edge-tts for Russian and as the fallback.

        voice: profile from the request (voice_profile): gender male/female, edge rate/pitch shifts."""
        out.parent.mkdir(parents=True, exist_ok=True)
        voice = voice or {}
        male = voice.get("gender") == "male"
        if language != "ru":
            try:
                result = self.fal_call("fal-ai/kokoro/american-english",
                                       {"prompt": text, "voice": "am_adam" if male else "af_heart"}, cancelled)
                url = (result.get("audio") or {}).get("url")
                if url:
                    return self.download(url, out.with_suffix(".wav"))
            except (cg.CloudError, AutopilotError):
                pass
        import asyncio
        import edge_tts
        if language == "ru":
            name = "ru-RU-DmitryNeural" if male else "ru-RU-SvetlanaNeural"
        else:
            name = "en-US-GuyNeural" if male else "en-US-AriaNeural"
        target = out.with_suffix(".mp3")
        shifts = {k: voice[k] for k in ("rate", "pitch") if voice.get(k)}
        # The free Edge service now and then answers "no audio" (busy, or rate+pitch together):
        # retry with a pause, then without the pitch shift (tone lowered by ffmpeg instead), then plain.
        no_pitch = {k: v for k, v in shifts.items() if k != "pitch"}
        tries = [shifts] * 4 + ([no_pitch] * 4 if "pitch" in shifts else []) + [{}] * 4
        error = None
        for attempt, kwargs in enumerate(tries):
            if cancelled():
                raise InterruptedError("Cancelled")
            if attempt:
                time.sleep(min(8.0, 2.0 * attempt))
            raw = target if "pitch" in kwargs or "pitch" not in shifts else out.with_name(out.stem + "_plain.mp3")
            try:
                asyncio.run(edge_tts.Communicate(text, name, **kwargs).save(str(raw)))
            except Exception as exc:  # edge_tts.exceptions.NoAudioReceived and network hiccups
                error = exc
                if raw.is_file() and raw.stat().st_size == 0:
                    raw.unlink()  # an empty half-written file must not pass for a voice
                continue
            if raw != target:  # same speed, about −1.5 semitones
                result = subprocess.run([self.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                                         "-af", "asetrate=24000*0.92,aresample=24000,atempo=1/0.92", str(target)],
                                        capture_output=True, text=True)
                if result.returncode != 0 or not target.is_file():
                    raw.replace(target)
            return target
        raise AutopilotError(f"Озвучка не получилась (Edge): {error}")

    def music(self, seconds: float, out: Path) -> Path:
        """Royalty-free bed: a track from app/data/music if the owner put one there, else a synthesized ambient pad."""
        library = Path(__file__).resolve().parents[1] / "data" / "music"
        tracks = sorted(p for p in library.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")) \
            if library.is_dir() else []
        if tracks:
            return tracks[0]  # shortcut: first track regardless of mood; pick by mood when a library exists
        # Soft A-minor chord with slow tremolo, low-passed, faded in/out: generated here, so no rights issues.
        expr = ("0.10*sin(2*PI*220*t)*(0.7+0.3*sin(2*PI*0.13*t))+0.07*sin(2*PI*261.63*t)*(0.7+0.3*sin(2*PI*0.09*t))"
                "+0.06*sin(2*PI*329.63*t)*(0.7+0.3*sin(2*PI*0.11*t))+0.05*sin(2*PI*110*t)")
        length = max(1.0, seconds)
        cmd = [self.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
               "-i", f"aevalsrc={expr}:s=44100:d={length:.2f}",
               "-af", f"lowpass=f=1800,afade=t=in:d=1.5,afade=t=out:st={max(0.0, length - 2):.2f}:d=2", str(out)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise AutopilotError(f"Музыка не собралась: {result.stderr.strip()[-300:]}")
        return out

    def duration(self, path: Path) -> float:
        from services.title_cards import _resolve_ffprobe
        probe = _resolve_ffprobe(self.ffmpeg())
        result = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True)
        try:
            return float(result.stdout.strip())
        except ValueError as error:
            raise AutopilotError(f"Не удалось узнать длительность {Path(path).name}") from error


# ---------------------------------------------------------------- runner

class Runner:
    def __init__(self, state: dict, options: dict, *, out_dir: Path, work_dir: Path, deps: Deps):
        # Absolute paths: the final mix runs ffmpeg with cwd=work_dir (subs, fonts), so a relative out_dir
        # such as "outputs" would resolve inside the work folder and the last step would fail.
        out_dir, work_dir = Path(out_dir).resolve(), Path(work_dir).resolve()
        self.state, self.options, self.out_dir, self.work_dir, self.deps = state, options, out_dir, work_dir, deps
        self.recipes = kb.recipes()
        self.aspect = options.get("aspect") if options.get("aspect") in FRAME else "9:16"
        self.cancelled = lambda: bool(state.get("_cancel"))

    def label(self, index: int, **values) -> str:
        # viral_remake has no labels of its own and shares photo_to_film's.
        own = kb.recipe(self.state["recipe"]).get("progress_labels")
        labels = own or kb.recipe("photo_to_film")["progress_labels"]
        text = labels[index]
        for key, value in values.items():
            text = text.replace("{" + key + "}", str(value))
        return text

    def run(self) -> None:
        try:
            self.work_dir.mkdir(parents=True, exist_ok=True)
            if self.options.get("regenerate_scene"):
                output = self.regenerate(int(self.options["regenerate_scene"]))
            elif self.state["recipe"] == "photo_to_film":
                output = self.photo_to_film()
            elif self.state["recipe"] == "one_prompt_film":
                output = self.one_prompt_film()
            else:
                output = self.viral_remake()
            with _LOCK:
                self.state.update(status="done", output={"filename": output.name, "url": f"/api/v1/file/{output.name}"})
            _progress(self.state, self.label(-1), 100, "done")
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

    def keyframe(self, scene: dict, index: int, tag: str = "") -> Path:
        w, h = FRAME[self.aspect]
        req = {"kind": "image", "prompt": scene["prompt"], "image": None, "width": w, "height": h,
               "ratio": self.aspect, "resolution": "2K", "duration": 0}
        return self.deps.fal_media(req, self.work_dir / f"key_{index}{tag}.png", self.cancelled)

    def scene(self, scene: dict, image: Path | None, size: tuple[int, int], index: int, tag: str = "") -> Path:
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
                out = self.work_dir / f"scene_{index:02d}{tag}_try{attempt}.mp4"
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

    # ------------------------------------------------------------ one_prompt_film

    XFADE = 0.3  # seconds of crossfade between scenes

    @staticmethod
    def fill(template: str, **values) -> str:
        for key, value in values.items():  # str.format would trip on the JSON braces in the templates
            template = template.replace("{" + key + "}", str(value))
        return template

    def ask(self, template: str, **values) -> dict:
        return parse_json(self.deps.llm([{"role": "user", "content": self.fill(template, **values)}]))

    @staticmethod
    def product_note(products: list[str]) -> str:
        """Beautyart products in the phrase: their hard rules and product file go into every LLM step."""
        if not products:
            return ""
        texts = [kb.read(kb.BEAUTYART_RULES)["text"]] + [kb.read(p)["text"] for p in products]
        return ("В ролике товар Beautyart — соблюдай эти правила и факты, ничего не выдумывай. Упаковку не генерировать "
                "и не описывать её надписи: в сценах с товаром будет реальное фото.\n" + "\n\n".join(texts) + "\n")

    def one_prompt_film(self) -> Path:
        phrase = (self.options.get("request") or "").strip()
        if not phrase:
            raise AutopilotError("Нужна фраза: о чём ролик.")
        total = max(10, min(180, int(self.options.get("total_seconds") or 30)))
        prompts = kb.recipe("one_prompt_film")["prompts"]
        products = kb.product_in_text(phrase)
        common = {"phrase": phrase, "total_seconds": total, "aspect": self.aspect, "product_note": self.product_note(products)}

        given = parse_user_scenes(phrase)
        voice = voice_profile(phrase)
        if given:
            # The person already wrote the scenes with timing and voiceover: no script writer, no doctor,
            # the scene count, seconds and voiceover text stay exactly as written.
            total = max(10, min(180, int(round(given[-1]["end"]))))
            common["total_seconds"] = total
            _progress(self.state, self.label(0), 3, "write_script")
            script = {"title": "", "hook": "", "language": "ru" if re.search("[а-яё]", phrase.lower()) else "en",
                      "scenes": [{"index": i, "seconds": g["seconds"], "description": g["description"],
                                  "voiceover": g["voiceover"]} for i, g in enumerate(given, 1)]}
            draft, doctored = {}, {}
            _progress(self.state, self.label(1), 8, "script_doctor")
        else:
            _progress(self.state, self.label(0), 3, "write_script")
            draft = self.ask(prompts["script"], **common)
            _progress(self.state, self.label(1), 8, "script_doctor")
            doctored = self.ask(prompts["doctor"], **common, script=json.dumps(draft, ensure_ascii=False))
            fixed = doctored.get("script") if isinstance(doctored.get("script"), dict) else doctored
            script = fixed if isinstance(fixed.get("scenes"), list) and fixed["scenes"] else draft
        with _LOCK:
            self.state["script"] = {"title": script.get("title", ""), "hook": script.get("hook", ""),
                                    "ideas": draft.get("ideas", []), "grade": doctored.get("grade"),
                                    "issues": doctored.get("issues", []), "products": products,
                                    "verbatim": bool(given), "voice": voice}
        script_json = json.dumps(script, ensure_ascii=False)

        _progress(self.state, self.label(2), 12, "extract_assets")
        assets = self.ask(prompts["assets"], **common, script=script_json).get("assets") or []
        images = []
        photo = kb.product_photo(products[0]) if products else None
        if photo:  # the real product photo; packaging is never generated
            images.append(self.to_jpeg(photo, 1))

        _progress(self.state, self.label(3), 16, "write_storyboard")
        board = self.ask(prompts["storyboard"], **common, script=script_json, rules=kb.rules(),
                         assets=json.dumps(assets, ensure_ascii=False))
        for scene in board.get("scenes", []) if isinstance(board, dict) else []:
            scene["photo_index"] = 1 if scene.get("product") and images else None
        negative = self.recipes.get("negative_prompt_default", "")
        if given:
            scenes = verbatim_scenes(given, board, phrase, negative)
            self.pick_keywords(scenes)
        else:
            scenes = normalize_scenes(board, len(images), total, negative,
                                      keep=("voiceover", "product", "shot", "camera", "keyword"))
        language = "ru" if re.search("[а-яё]", phrase.lower()) else str(script.get("language") or "en")[:2]
        return self.produce(scenes, images, language, voice)

    def pick_keywords(self, scenes: list[dict]) -> None:
        """One word per voiceover line to paint red in the subtitles (cheap text call; heuristic if it fails)."""
        lines = [s.get("voiceover", "") for s in scenes]
        if not any(lines):
            return
        ask = ("Для каждой строки озвучки выбери ОДНО ключевое слово — самое страшное или важное, ровно как оно "
               "написано в строке. Его выделим красным в субтитрах. Верни только JSON: {\"keywords\": [\"...\"]} — "
               "по одному слову на строку, в том же порядке.\n"
               + "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1)))
        try:
            words = parse_json(self.deps.llm([{"role": "user", "content": ask}])).get("keywords") or []
        except Exception:  # keywords are a nicety: never fail the film over them
            words = []
        for scene, word in zip(scenes, words):
            if isinstance(word, str) and word.strip() and not scene.get("keyword"):
                scene["keyword"] = word.strip()

    def produce(self, scenes: list[dict], images: list[Path], language: str, voice: dict | None = None) -> Path:
        n = len(scenes)
        size = (FINAL if self.options.get("quality") == "final" else DRAFT)[self.aspect]
        keyframes = {}
        for i, scene in enumerate(scenes, 1):  # cheap stills first, video only after the look is fixed
            self.check()
            if not scene["photo_index"]:
                _progress(self.state, self.label(4, i=i, n=n), 20 + 15 * (i - 1) / n, "generate_keyframe")
                keyframes[i] = self.keyframe(scene, i)
        clips = []
        for i, scene in enumerate(scenes, 1):
            self.check()
            _progress(self.state, self.label(5, i=i, n=n), 35 + 40 * (i - 1) / n, "generate_scene")
            image = images[scene["photo_index"] - 1] if scene["photo_index"] else keyframes[i]
            clips.append(self.scene(scene, image, size, i))
        _progress(self.state, self.label(6), 77, "voiceover")
        voices = {}
        for i, scene in enumerate(scenes, 1):
            self.check()
            if scene.get("voiceover", "").strip():
                path = self.work_dir / f"voice_{i:02d}"
                voices[i] = (self.deps.tts(scene["voiceover"].strip(), language, path, self.cancelled, voice=voice)
                             if voice else self.deps.tts(scene["voiceover"].strip(), language, path, self.cancelled))
        self.fit_voices(scenes, voices)
        project = {"scenes": scenes, "images": [str(p) for p in images], "language": language, "size": list(size),
                   "keyframes": {str(k): str(v) for k, v in keyframes.items()}, "clips": [str(c) for c in clips],
                   "voices": {str(k): str(v) for k, v in voices.items()}, "version": 0}
        with _LOCK:
            self.state.update(_project=project, scenes=n, scenes_detail=_scene_details(scenes))
        return self.assemble(project)

    def fit_voices(self, scenes: list[dict], voices: dict) -> None:
        """Written timing wins: a line longer than its written scene is sped up (at most ×1.3) to fit it."""
        for i, scene in enumerate(scenes, 1):
            target = float(scene.get("target_seconds") or 0)
            if i not in voices or target <= 0:
                continue
            length = self.deps.duration(voices[i])
            room = max(1.0, target - 0.3)
            if length <= room * 1.03:
                continue
            tempo = min(1.3, length / room)
            fitted = Path(voices[i]).with_name(Path(voices[i]).stem + "_fit.mp3")
            result = subprocess.run([self.deps.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i",
                                     str(voices[i]), "-af", f"atempo={tempo:.3f}", str(fitted)],
                                    capture_output=True, text=True)
            if result.returncode == 0 and fitted.is_file() and fitted.stat().st_size:
                voices[i] = fitted

    def regenerate(self, index: int) -> Path:
        """Re-shoot one scene (new keyframe if the prompt changed) and re-assemble; other scenes are reused."""
        project = self.state.get("_project")
        if not project or not 1 <= index <= len(project["scenes"]):
            raise AutopilotError("Такой сцены нет.")
        scene = project["scenes"][index - 1]
        prompt = (self.options.get("prompt") or "").strip()
        if prompt:
            scene["prompt"] = prompt
        project["version"] += 1
        tag = f"_v{project['version']}"
        _progress(self.state, f"Перегенерирую сцену {index}", 10, "generate_scene")
        if scene["photo_index"]:
            image = Path(project["images"][scene["photo_index"] - 1])
        elif prompt or str(index) not in project["keyframes"]:
            image = self.keyframe(scene, index, tag)
            project["keyframes"][str(index)] = str(image)
        else:
            image = Path(project["keyframes"][str(index)])
        project["clips"][index - 1] = str(self.scene(scene, image, tuple(project["size"]), index, tag))
        with _LOCK:
            self.state["scenes_detail"] = _scene_details(project["scenes"])
        return self.assemble(project)

    def assemble(self, project: dict) -> Path:
        clips = [Path(c) for c in project["clips"]]
        raw = [self.deps.duration(c) for c in clips]
        voices = {int(k): Path(v) for k, v in project["voices"].items()}
        voice_len = {i: self.deps.duration(v) for i, v in voices.items()}
        # A clip shorter than its line holds its last frame so the voice never runs into the next scene.
        durations = [max(d, voice_len.get(k + 1, 0) + 0.4) for k, d in enumerate(raw)]
        pads = [max(0.0, d - r) for d, r in zip(durations, raw)]
        fade = min(self.XFADE, min(durations) / 3)
        starts = [sum(durations[:k]) - k * fade for k in range(len(clips))]
        total = sum(durations) - (len(clips) - 1) * fade
        _progress(self.state, self.label(7), 85, "music")
        music = self.deps.music(total, self.work_dir / "music.wav")
        _progress(self.state, self.label(8), 89, "subtitles")
        cues, lines = [], []
        for i, scene in enumerate(project["scenes"], 1):
            if i in voices:
                cues += subtitle_cues(scene["voiceover"], starts[i - 1], voice_len[i])
                lines.append((scene["voiceover"], starts[i - 1], voice_len[i], scene_keyword(scene)))
        (self.work_dir / "subs.srt").write_text(to_srt(cues), encoding="utf-8")  # plain copy for players
        w, h = FRAME[self.aspect]
        (self.work_dir / "subs.ass").write_text(karaoke_ass(lines, w, h), encoding="utf-8")
        _progress(self.state, self.label(9), 93, "concat_clips")
        suffix = f"_v{project['version']}" if project["version"] else ""
        name = f"{time.strftime('%Y-%m-%d-%Hh%Mm%Ss')}_autopilot_one_prompt_film_{self.state['id']}{suffix}.mp4"
        return self.mix(clips, starts, fade, total, voices, music, self.out_dir / name, pads)

    def mix(self, clips, starts, fade, total, voices, music, out: Path, pads=None) -> Path:
        """Scenes with xfade, burned-in subtitles, voice per scene, music −18 dB under it -> H.264 + AAC."""
        w, h = FRAME[self.aspect]
        out.parent.mkdir(parents=True, exist_ok=True)
        fonts = self.work_dir / "fonts"
        fonts.mkdir(exist_ok=True)
        system_font = Path("C:/Windows/Fonts/arial.ttf")
        if system_font.is_file() and not (fonts / "arial.ttf").is_file():
            # shortcut: Windows Arial (has Cyrillic); on other systems libass falls back to fontconfig fonts.
            (fonts / "arial.ttf").write_bytes(system_font.read_bytes())
        voice_items = sorted(voices.items())
        cmd = [self.deps.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error"]
        for clip in clips:
            cmd += ["-i", str(clip)]
        for _, voice in voice_items:
            cmd += ["-i", str(voice)]
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        graph = [f"[{k}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
                 f"setsar=1,fps=30,format=yuv420p,"
                 + (f"tpad=stop_mode=clone:stop_duration={pads[k]:.3f}," if pads and pads[k] > 0 else "")
                 + f"settb=AVTB[v{k}]" for k in range(len(clips))]
        last = "v0"
        for k in range(1, len(clips)):
            graph.append(f"[{last}][v{k}]xfade=transition=fade:duration={fade:.3f}:offset={starts[k]:.3f}[x{k}]")
            last = f"x{k}"
        # Karaoke subtitles (subs.ass): large, centred, current word yellow, the key word red.
        graph.append(f"[{last}]subtitles=subs.ass:fontsdir=fonts[vout]")
        base = len(clips)
        stereo = "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo"
        for j, (i, _) in enumerate(voice_items):
            ms = int(starts[i - 1] * 1000)
            graph.append(f"[{base + j}:a]{stereo},adelay={ms}|{ms}[a{j}]")
        music_index = base + len(voice_items)
        graph.append(f"[{music_index}:a]{stereo},volume=-18dB,atrim=0:{total:.3f}[bgm]")
        if voice_items:
            graph.append("".join(f"[a{j}]" for j in range(len(voice_items)))
                         + f"amix=inputs={len(voice_items)}:normalize=0:duration=longest[voice]")
            graph.append(f"[voice][bgm]amix=inputs=2:normalize=0:duration=longest,atrim=0:{total:.3f}[aout]")
        else:
            graph.append("[bgm]anull[aout]")
        cmd += ["-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
                "-c:v", "libx264", "-preset", "medium", "-b:v", "16M", "-maxrate", "20M", "-bufsize", "32M",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.work_dir)  # cwd: subs.srt, fonts/
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

def _scene_details(scenes: list[dict]) -> list[dict]:
    return [{k: s.get(k) for k in ("index", "seconds", "prompt", "voiceover", "product", "keyword")} for s in scenes]


def subtitle_cues(text: str, start: float, duration: float, max_words: int = 6) -> list[tuple[float, float, str]]:
    """Split a scene's voiceover into short cues timed by the real audio length (word count proportional)."""
    words = (text or "").split()
    if not words or duration <= 0:
        return []
    cues, t = [], start
    for k in range(0, len(words), max_words):
        chunk = words[k:k + max_words]
        length = duration * len(chunk) / len(words)
        cues.append((t, t + length, " ".join(chunk)))
        t += length
    return cues


_SCENE_LINE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*[–—-]\s*(\d+(?:[.,]\d+)?)\s*(?:с|сек|s|sec)\b\.?\s*(.+)$",
                         re.IGNORECASE)
_QUOTED = re.compile(r"«([^«»]+)»|“([^“”]+)”|\"([^\"]+)\"")


def parse_user_scenes(text: str) -> list[dict]:
    """Scenes the person already wrote: lines like «0–8 с. Что в кадре. «Текст озвучки.»».

    Voiceover = quoted parts that end like a sentence (. ! ? …); short labels such as «НОЧЬ 5» or «23:48»
    stay in the picture description. Fewer than two such lines -> [] (a normal one-phrase request)."""
    scenes = []
    for line in (text or "").splitlines():
        match = _SCENE_LINE.match(line)
        if not match:
            continue
        start, end = (float(x.replace(",", ".")) for x in match.group(1, 2))
        if end <= start:
            continue
        body = match.group(3).strip()
        quoted = [next(g for g in m.groups() if g is not None) for m in _QUOTED.finditer(body)]
        spoken = [q.strip() for q in quoted if re.search(r"[.!?…]\s*$", q.strip())]
        voiceover = " ".join(spoken)
        description = body
        for q in spoken:
            description = description.replace(f"«{q}»", "").replace(f"“{q}”", "").replace(f'"{q}"', "")
        scenes.append({"start": start, "end": end, "seconds": end - start, "voiceover": voiceover,
                       "description": re.sub(r"\s+", " ", description).strip(" .")})
    return scenes if len(scenes) >= 2 else []


def _style_note(phrase: str) -> str:
    """The look described before the scene list (first paragraph), for prompts the storyboard did not cover."""
    head = re.split(r"\n\s*\n", (phrase or "").strip())[0]
    return head if not _SCENE_LINE.match(head) else ""


def verbatim_scenes(given: list[dict], board: dict, phrase: str, negative: str) -> list[dict]:
    """One scene per written scene, in order; picture prompts from the storyboard, text and timing untouched."""
    raw = board.get("scenes") if isinstance(board, dict) else None
    raw = [s for s in raw if isinstance(s, dict)] if isinstance(raw, list) else []
    by_index = {s.get("index"): s for s in raw}
    style = _style_note(phrase)
    scenes = []
    for i, item in enumerate(given, 1):
        drawn = by_index.get(i) or (raw[i - 1] if i - 1 < len(raw) else {})
        prompt = str(drawn.get("prompt") or "").strip() or f"{item['description']}. {style}".strip()
        scenes.append({"index": i, "seconds": max(5, min(10, int(math.ceil(item["seconds"])))), "photo_index": None,
                       "prompt": prompt, "negative_prompt": str(drawn.get("negative_prompt") or negative),
                       "caption": "", "voiceover": item["voiceover"], "description": item["description"],
                       "keyword": str(drawn.get("keyword") or ""), "verbatim": True,
                       "target_seconds": float(item["seconds"])})
    return scenes


def voice_profile(phrase: str) -> dict:
    """Voice wishes from the request («Озвучка: низкий грубый мужской голос, медленно»): gender + edge shifts."""
    text = (phrase or "").lower()
    match = re.search(r"(озвучк\w*|голос\w*|диктор\w*|voice[- ]?over|voice|narrat\w*)\s*[:—-]?\s*([^\n]{0,200})", text)
    if not match:
        return {}
    part = match.group(0)
    profile: dict = {}
    if re.search(r"мужск|мужчин|\bmale\b|\bman\b|бас|баритон", part):
        profile["gender"] = "male"
    elif re.search(r"женск|девуш|female|woman", part):
        profile["gender"] = "female"
    if re.search(r"низк|груб|глух|бас|deep|low", part):
        profile["pitch"] = "-12Hz"
    elif re.search(r"высок|звонк|high", part):
        profile["pitch"] = "+10Hz"
    if re.search(r"медлен|не спеша|slow", part):
        profile["rate"] = "-15%"
    elif re.search(r"быстр|fast", part):
        profile["rate"] = "+15%"
    return profile


_STOP = {"который", "которая", "которые", "потому", "только", "теперь", "всё", "когда", "больше"}


def scene_keyword(scene: dict) -> str:
    """Word to paint red: the storyboard's keyword if it is in the line, else CAPS / a time / the longest word."""
    words = [w.strip(".,!?…:;«»\"()—-") for w in (scene.get("voiceover") or "").split()]
    words = [w for w in words if w]
    wanted = str(scene.get("keyword") or "").strip().strip(".,!?…:;«»\"()—-").lower()
    if wanted and any(w.lower() == wanted for w in words):
        return wanted
    caps = [w for w in words if len(w) > 1 and w.isupper()]
    if caps:
        return caps[0].lower()
    times = [w for w in words if re.fullmatch(r"\d{1,2}[:.]\d{2}", w)]
    if times:
        return times[0].lower()
    candidates = [w for w in words if w.lower() not in _STOP]
    return max(candidates, key=len).lower() if candidates else ""


def _ass_time(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def karaoke_ass(lines: list[tuple[str, float, float, str]], width: int = 1080, height: int = 1920,
                max_words: int = 4) -> str:
    """ASS subtitles: big centred words in short groups; the word being spoken is yellow, the key word red.

    lines: (voiceover, start, audio_length, keyword). Word timing ∝ word length inside the real audio length."""
    size = round(min(width, height) * 0.08)
    head = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 0",
            "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding",
            f"Style: Karaoke,Arial,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,"
            f"{max(3, size // 14)},2,5,80,80,0,1", "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    events = []
    clean = lambda w: w.replace("\\", "").replace("{", "").replace("}", "")  # noqa: E731
    key_of = lambda w: w.strip(".,!?…:;«»\"()—-").lower()  # noqa: E731
    for text, start, length, keyword in lines:
        words = [clean(w) for w in (text or "").split() if clean(w)]
        if not words or length <= 0:
            continue
        weights = [len(w) + 2 for w in words]
        unit = length / sum(weights)
        t, stamps = start, []
        for wgt in weights:
            stamps.append((t, t + wgt * unit))
            t += wgt * unit
        for g in range(0, len(words), max_words):
            group = list(range(g, min(g + max_words, len(words))))
            for j in group:
                parts = []
                for k in group:
                    word, is_key = words[k], bool(keyword) and key_of(words[k]) == keyword
                    if k == j and is_key:
                        parts.append("{\\c&H0000FF&\\fscx115\\fscy115}" + word + "{\\r}")
                    elif is_key:
                        parts.append("{\\c&H0000FF&}" + word + "{\\r}")
                    elif k == j:
                        parts.append("{\\c&H00FFFF&\\fscx110\\fscy110}" + word + "{\\r}")
                    else:
                        parts.append(word)
                a, b = stamps[j]
                events.append(f"Dialogue: 0,{_ass_time(a)},{_ass_time(b)},Karaoke,,0,0,0,,{' '.join(parts)}")
    return "\n".join(head + events) + "\n"


def to_srt(cues: list[tuple[float, float, str]]) -> str:
    def stamp(seconds: float) -> str:
        ms = int(round(seconds * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n" for i, (a, b, text) in enumerate(cues, 1))


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

