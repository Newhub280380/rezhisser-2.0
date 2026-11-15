"""Руководитель (оркестратор): одна простая просьба клиента -> план из готовых Freefield-приложений и служебных
шагов -> цена всех платных вызовов fal -> подтверждение -> выполнение по шагам со статусами.

Один и тот же файл лежит в Режиссёре 2.0 (app/services/chief.py) и Режиссёре 1.0 (director/chief.py), как и
freefield_apps.py. Нужны только Pillow, ffmpeg/ffprobe и (для ссылок) yt-dlp; OpenCV — по возможности (поиск лиц).

Две фазы:
  plan()    — бесплатно: скачать, найти лучший отрезок, нарезать, оставить на фото одного человека, dry-run
              платных приложений, посчитать цену по ставкам из каталога. Статус «awaiting_confirmation».
  confirm() — только с confirm=True: платные шаги (fal) и служебные после них. Без подтверждения fal не вызывается.

Цены не выдумываются: ставки берутся из строки price приложения в каталоге freefield_apps.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps

from . import freefield_apps as ff

CLIP_MIN, CLIP_LEN, CLIP_MAX = 10.0, 13.0, 15.0
MAX_CLIP_MB = ff.MAX_VIDEO_MB
SMALL_PHOTO = 512  # short side below this -> SeedVR2 upscale x2
FILL = (235, 235, 235)  # plain light background behind the cut-out person (assumption: neutral, not brand colour)

CHAINS = [
    {"id": "recast_clip", "name": "Замена персонажа в клипе", "status": "ready",
     "summary": "Ссылка или файл видео + фото: отрезок 10–15 с, подготовка фото, Recast (Wan Animate), "
                "возврат оригинального звука.",
     "inputs": ["video", "photo"]},
    {"id": "app", "name": "Одно приложение из каталога", "status": "ready",
     "summary": "Просьба под одно готовое приложение (убрать фон, улучшить фото, дубляж, говорящее фото…): "
                "руководитель сам заполнит поля, покажет цену и запустит после подтверждения.",
     "inputs": ["video", "photo", "text"]},
    {"id": "viral_clone", "name": "Клон вирусного ролика под нишу (3 копии)", "status": "soon",
     "summary": "Изучить нишу, найти вирусное видео, подобрать аватар, голос, волосы, цвета и сделать три копии.",
     "needs": "Следующий этап после руководителя: поиск вирусных роликов по нише, подбор аватара и голоса, "
              "три варианта. Пока не подключено."},
]
CHAINS_BY_ID = {c["id"]: c for c in CHAINS}

RECAST_WORDS = ("замен", "вместо", "recast", "рекаст", "подстав", "поставь меня", "вставь меня")
VIRAL_WORDS = ("вирус", "клон", "три копии", "3 копии")
# request words -> app id (first match wins); (needs video, needs photo)
APP_WORDS = [
    (("scail", "sam 3"), "recast-scail2", False, False),
    (("переозвуч", "dubit"), "dub", True, False),
    (("дубляж", "перевед", "на английск", "на казахск"), "dub-cloud", True, False),
    (("фон",), "video-remove-bg", True, False),
    (("фон",), "remove-bg", False, True),
    (("4k", "4к", "улучш", "увелич", "апскейл", "upscale"), "upscale-video", True, False),
    (("4k", "4к", "улучш", "увелич", "апскейл", "upscale"), "upscale", False, True),
    (("движен", "оживи", "станцу", "танц"), "motion", True, True),
    (("скажи", "говорящ", "произнес", "озвучь фото"), "speak", False, True),
    (("песн", "музык"), "music", False, False),
    (("звуков", "шум", "sfx"), "sfx", False, False),
    (("нарисуй", "картинк", "изображени"), "create-image", False, False),
]


class ChiefError(RuntimeError):
    pass


# ---------------------------------------------------------------- tools (everything external, replaceable in tests)

class Tools:
    """client: object with ``call(endpoint, body, cancelled) -> dict`` (the host's fal queue) or None when no key.
    file_to_url: Path -> data URI. download: (url, Path) -> Path."""

    def __init__(self, client=None, file_to_url: Callable | None = None, download: Callable | None = None,
                 ffmpeg: str | None = None, ffprobe: str | None = None):
        self.client, self.file_to_url, self._download = client, file_to_url, download
        self.ffmpeg = ffmpeg or shutil.which("ffmpeg") or "ffmpeg"
        sibling = Path(self.ffmpeg).with_name("ffprobe" + Path(self.ffmpeg).suffix)
        self.ffprobe = ffprobe or (str(sibling) if sibling.is_file() else shutil.which("ffprobe") or "ffprobe")

    def fal(self, endpoint: str, body: dict, cancelled) -> dict:
        if self.client is None:
            raise ChiefError("Нет ключа fal — платный шаг не запущен.")
        return self.client.call(endpoint, body, cancelled)

    def download(self, url: str, out: Path) -> Path:
        return self._download(url, out)

    def run(self, args: list) -> None:
        result = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf-8",
                                errors="replace")
        if result.returncode:
            raise ChiefError(f"{Path(str(args[0])).stem}: {result.stderr.strip()[-400:]}")

    def probe(self, path: Path) -> dict:
        out = subprocess.run([self.ffprobe, "-v", "error", "-show_entries",
                              "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
                             capture_output=True, text=True)
        if out.returncode:
            raise ChiefError(f"ffprobe не прочитал {Path(path).name}")
        data = json.loads(out.stdout or "{}")
        video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        return {"duration": float((data.get("format") or {}).get("duration") or 0), "width": video.get("width"),
                "height": video.get("height"),
                "audio": any(s.get("codec_type") == "audio" for s in data.get("streams", []))}

    def fetch(self, url: str, work: Path) -> Path:
        """yt-dlp: best mp4 not above 1080p, with sound."""
        import yt_dlp
        options = {"outtmpl": str(work / "source.%(ext)s"), "noplaylist": True, "quiet": True,
                   "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b",
                   "merge_output_format": "mp4", "ffmpeg_location": str(Path(self.ffmpeg).parent)
                   if Path(self.ffmpeg).is_file() else None}
        with yt_dlp.YoutubeDL({k: v for k, v in options.items() if v is not None}) as ydl:
            ydl.extract_info(url, download=True)
        files = sorted(p for p in work.glob("source.*") if p.suffix not in (".part", ".ytdl"))
        if not files:
            raise ChiefError("Не удалось скачать видео по ссылке.")
        return files[0]


# ---------------------------------------------------------------- understanding the request

def understand(text: str, has_video: bool, has_photo: bool) -> dict:
    """-> {"chain": id, "app": app_id|None}. Raises ChiefError with what the руководитель can do."""
    low = (text or "").lower()
    if any(w in low for w in VIRAL_WORDS):
        return {"chain": "viral_clone", "app": None}
    if any(w in low for w in RECAST_WORDS) or (has_video and has_photo and not any(
            any(w in low for w in words) for words, *_ in APP_WORDS)):
        return {"chain": "recast_clip", "app": "recast"}
    for words, app_id, need_video, need_photo in APP_WORDS:
        if any(w in low for w in words) and (not need_video or has_video) and (not need_photo or has_photo):
            return {"chain": "app", "app": app_id}
    raise ChiefError("Не понял задачу. Руководитель умеет: " + "; ".join(
        f"{c['name']}{' (скоро)' if c['status'] == 'soon' else ''}" for c in CHAINS)
        + ". Пример: «замени человека в этом клипе на меня» + ссылка на видео + фото.")


TIME = r"(\d{1,2}):(\d{2})(?:[.,](\d+))?"


def time_range(text: str) -> tuple[float, float] | None:
    """«4:36–4:49» / «с 4:36 по 4:49» -> (276.0, 289.0)."""
    m = re.search(TIME + r"\s*(?:-|–|—|по|до)\s*" + TIME, text or "")
    if not m:
        return None
    g = m.groups()
    a = int(g[0]) * 60 + int(g[1]) + float("0." + (g[2] or "0"))
    b = int(g[3]) * 60 + int(g[4]) + float("0." + (g[5] or "0"))
    return (a, b) if b > a else None


def mmss(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def quoted(text: str) -> str:
    m = re.search(r"[«\"“](.+?)[»\"”]", text or "", re.S)
    return (m.group(1) if m else text or "").strip()


# ---------------------------------------------------------------- prices (only from catalog rates)

def recast_price(seconds: float, resolution: str, app_id: str = "recast") -> float:
    rates = {res: float(usd) for usd, res in re.findall(r"\$([\d.]+)/с при (\d+p)", ff.APPS_BY_ID[app_id]["price"])}
    return round(rates[resolution] * seconds, 2)


def upscale_price(width: int, height: int, scale: int) -> float:
    rate = float(re.search(r"\$([\d.]+) за мегапиксель", ff.APPS_BY_ID["upscale"]["price"]).group(1))
    return round(width * scale * height * scale / 1e6 * rate, 4)


# ---------------------------------------------------------------- clip choice

YUNET = Path(__file__).with_name("face_detection_yunet_2023mar.onnx")  # OpenCV Zoo YuNet, MIT licence


def face_boxes(image) -> list[tuple[int, int, int, int]]:
    """Faces as (x, y, w, h): OpenCV YuNet (OpenCV 4.8+/5), Haar on older OpenCV. [] without OpenCV.
    image: PIL image."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []
    if hasattr(cv2, "FaceDetectorYN") and YUNET.is_file():
        bgr = np.ascontiguousarray(np.array(image.convert("RGB"))[:, :, ::-1])
        detector = cv2.FaceDetectorYN.create(str(YUNET), "", (bgr.shape[1], bgr.shape[0]), 0.8)
        faces = detector.detect(bgr)[1]
        return [] if faces is None else [tuple(int(v) for v in f[:4]) for f in faces]
    if not hasattr(cv2, "CascadeClassifier"):
        return []
    gray = np.array(image.convert("L"))
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    side = max(24, int(min(gray.shape) * 0.04))
    return [tuple(int(v) for v in f) for f in cascade.detectMultiScale(gray, 1.1, 6, minSize=(side, side))]


def frame_score(faces: list, frame_h: int) -> float:
    """One frontal face in a medium/full shot is best; a crowd is worst."""
    if len(faces) >= 2:
        return -1.0 if len(faces) >= 3 else 0.0
    if not faces:
        return 0.1
    share = faces[0][3] / frame_h
    return 0.6 + (0.4 if 0.06 <= share <= 0.35 else 0.2 if share > 0.35 else 0.1)


def best_window(scores: list[float], length: int) -> int:
    """Start index (1 sample = 1 s) of the window with the highest mean; windows with a crowd frame lose."""
    if len(scores) <= length:
        return 0
    best, start = None, 0
    for i in range(len(scores) - length + 1):
        part = scores[i:i + length]
        value = sum(part) / length - (10 if min(part) < 0 else 0)
        if best is None or value > best:
            best, start = value, i
    return start


# ---------------------------------------------------------------- photo

def keep_one_person(src: Path, out: Path, hint: str = "") -> tuple[Path, str]:
    """If the photo has several faces, crop to one (largest, or «слева»/«справа» from the request)."""
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    faces = face_boxes(im)
    if len(faces) <= 1:
        im.save(out)
        return out, "Найден один человек — фото без изменений." if faces else \
            "Лицо не найдено автоматически — оставляю фото как есть, проверьте его."
    low = hint.lower()
    if "слева" in low or "левый" in low or "левая" in low:
        x, y, w, h = min(faces, key=lambda f: f[0])
    elif "справа" in low or "правый" in low or "правая" in low:
        x, y, w, h = max(faces, key=lambda f: f[0])
    else:
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    cx, half = x + w / 2, w * 1.9
    box = (int(max(0, cx - half)), int(max(0, y - h)), int(min(im.width, cx + half)), im.height)
    im.crop(box).save(out)
    return out, f"На фото {len(faces)} человек(а) — оставлен один (кадр {box[2] - box[0]}×{box[3] - box[1]})."


def fit_to_clip(cutout: Path, out: Path, clip_w: int, clip_h: int) -> Path:
    """Person (RGBA after BiRefNet) on a plain canvas with the clip's proportions, so fal's centre crop keeps
    the whole figure. Short side of the canvas >= 720."""
    im = Image.open(cutout)
    im = im.convert("RGBA")
    bbox = im.getchannel("A").getbbox() or (0, 0, im.width, im.height)
    person = im.crop(bbox)
    aspect = clip_w / clip_h
    ph = person.height * 1.08
    cw, ch = max(person.width * 1.15, ph * aspect), ph
    if cw / ch > aspect:
        ch = cw / aspect
    else:
        cw = ch * aspect
    k = max(1.0, 720 / min(cw, ch))
    cw, ch = int(cw * k), int(ch * k)
    person = person.resize((max(1, int(person.width * k)), max(1, int(person.height * k))), Image.LANCZOS)
    canvas = Image.new("RGB", (cw, ch), FILL)
    canvas.paste(person, ((cw - person.width) // 2, ch - person.height - int(ch * 0.03)), person)
    canvas.save(out)
    return out


# ---------------------------------------------------------------- jobs

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _public(job: dict) -> dict:
    return json.loads(json.dumps({k: v for k, v in job.items() if not k.startswith("_")}))


def get_job(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return _public(job) if job else None


def cancel(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        job["_cancel"] = True
        if job["status"] == "awaiting_confirmation":
            job["status"] = "cancelled"
    return get_job(job_id)


def job_file(job_id: str, name: str) -> Path | None:
    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        return None
    base = job["_work"].resolve()
    path = (base / Path(str(name)).name).resolve()
    return path if path.parent == base and path.is_file() else None


def chains() -> dict:
    return {"chains": CHAINS, "apps": [ff.public_app(a) for a in ff.APPS]}


def _step(id, label, kind, app=None):
    return {"id": id, "label": label, "kind": kind, "app": app, "status": "pending", "detail": "", "file": None,
            "price_usd": None, "price_text": ff.APPS_BY_ID[app]["price"] if app else None}


def recast_steps(from_url: bool) -> list[dict]:
    return [
        _step("fetch", "Скачать видео по ссылке (yt-dlp)", "free"),
        _step("pick", "Найти лучший отрезок 10–15 с с главным человеком", "free"),
        _step("cut", "Нарезать: H.264 MP4 со звуком, не выше 1080p, до 40 МБ", "free"),
        _step("person", "Оставить на фото одного человека", "free"),
        _step("upscale", "Увеличить маленькое фото (SeedVR2)", "paid", "upscale"),
        _step("remove_bg", "Убрать фон на фото (BiRefNet)", "paid", "remove-bg"),
        _step("fit", "Подогнать фото под пропорции клипа", "free"),
        _step("recast", "Замена персонажа (Recast, Wan 2.2 Animate)", "paid", "recast"),
        _step("audio", "Вернуть оригинальный звук", "free"),
        _step("save", "Сохранить и показать результат", "free"),
    ] if from_url else [s for s in recast_steps(True) if s["id"] != "fetch"]


def plan(request: dict, *, tools: Tools, work_root: Path, out_dir: Path, url_for: Callable[[str], str],
         notes: Callable[[str], list] | None = None, background: bool = True) -> dict:
    """Free phase. request: {text, video_url | video (Path), photo (Path), resolution, turbo, seed}."""
    text = str(request.get("text") or "").strip()[:4000]
    video_url = str(request.get("video_url") or "").strip()
    if video_url and not re.match(r"^https?://", video_url):
        raise ChiefError("Ссылка на видео должна начинаться с http:// или https://")
    has_video = bool(video_url or request.get("video"))
    intent = understand(text, has_video, bool(request.get("photo")))
    chain = CHAINS_BY_ID[intent["chain"]]
    job_id = uuid.uuid4().hex[:12]
    work = Path(work_root) / f"chief_{job_id}"
    work.mkdir(parents=True, exist_ok=True)
    job = {"id": job_id, "chain": chain["id"], "chain_name": chain["name"], "app": intent["app"], "text": text,
           "status": "planning", "steps": [], "cost": None, "warnings": [], "output": None, "error": None,
           "notes": (notes(f"{chain['name']} {text}") if notes else [])[:3], "created": time.time(),
           "_work": work, "_out": Path(out_dir), "_url_for": url_for, "_cancel": False, "_ctx": {
               "video_url": video_url, "video": request.get("video"), "photo": request.get("photo"),
               "resolution": request.get("resolution") or "480p", "turbo": request.get("turbo", True),
               "seed": request.get("seed", -1)}}
    if chain["status"] == "soon":
        job.update(status="soon", error=None, warnings=[chain["needs"]])
    elif chain["id"] == "recast_clip":
        if not has_video or not request.get("photo"):
            raise ChiefError("Для замены персонажа нужны видео (ссылка или файл) и фото.")
        if job["_ctx"]["resolution"] not in ff.RES_WAN:
            raise ChiefError(f"Качество Recast: {', '.join(ff.RES_WAN)}.")
        job["steps"] = recast_steps(bool(video_url))
    else:
        app = ff.APPS_BY_ID[intent["app"]]
        if app["status"] != "ready":
            job.update(status="soon", warnings=[f"«{app['name']}» — скоро: {app['needs']}"])
        else:
            job["steps"] = ([_step("fetch", "Скачать видео по ссылке (yt-dlp)", "free")] if video_url else []) + [
                _step("run_app", app["name"], "paid", app["id"]), _step("save", "Сохранить и показать результат", "free")]
    with _LOCK:
        _JOBS[job_id] = job
    if job["status"] == "planning":
        _go(job, tools, Runner.prepare, background)
    return get_job(job_id)


def confirm(job_id: str, *, tools: Tools, confirmed: bool, background: bool = True) -> dict:
    """PAID phase. Runs only with confirmed=True (the person saw the price). A failed job resumes from the
    first unfinished step; finished paid steps are never repeated."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise ChiefError("Нет такой задачи.")
        if job["status"] not in ("awaiting_confirmation", "failed"):
            raise ChiefError(f"Задача в статусе «{job['status']}», подтверждать нечего.")
        if job["cost"] is None:
            raise ChiefError("Подготовка не прошла — составьте план заново.")
        if not confirmed:
            raise ChiefError("Нужно подтверждение цены: повторите с confirm: true.")
        if tools.client is None and any(s["kind"] == "paid" and s["status"] == "pending" for s in job["steps"]):
            raise ChiefError("Нет ключа fal — платные шаги запустить нельзя.")
        job.update(status="running", error=None, _cancel=False)
        for s in job["steps"]:
            if s["status"] == "failed":
                s["status"] = "pending"
    _go(job, tools, Runner.execute, background)
    return get_job(job_id)


def _go(job, tools, method, background):
    runner = Runner(job, tools)
    if background:
        threading.Thread(target=method, args=(runner,), name=f"chief-{job['id']}", daemon=True).start()
    else:
        method(runner)


class Runner:
    def __init__(self, job: dict, tools: Tools):
        self.job, self.tools, self.ctx, self.work = job, tools, job["_ctx"], job["_work"]

    # -------- bookkeeping
    def step(self, step_id: str) -> dict | None:
        return next((s for s in self.job["steps"] if s["id"] == step_id), None)

    def set(self, step_id: str, **values) -> None:
        with _LOCK:
            s = self.step(step_id)
            if s:
                s.update(values)

    def warn(self, text: str) -> None:
        with _LOCK:
            self.job["warnings"].append(text)

    def cancelled(self) -> bool:
        return bool(self.job["_cancel"])

    def each(self, ids: list[str]) -> None:
        for step_id in ids:
            s = self.step(step_id)
            if not s or s["status"] in ("done", "skipped"):
                continue
            if self.cancelled():
                raise ChiefError("Отменено.")
            self.set(step_id, status="running")
            try:
                detail = getattr(self, "do_" + step_id)()
            except Exception as error:
                self.set(step_id, status="failed", detail=str(error)[:400])
                raise
            if s["status"] == "running":
                self.set(step_id, status="done", detail=detail or s["detail"])

    def finish(self, status: str, error: str | None = None) -> None:
        with _LOCK:
            self.job.update(status=status, error=error)

    # -------- phases
    def prepare(self) -> None:
        free = [s["id"] for s in self.job["steps"] if s["kind"] == "free" and s["id"] in ("fetch", "pick", "cut", "person")]
        try:
            self.each(free)
            self.price()
            self.finish("awaiting_confirmation")
        except Exception as error:
            self.finish("cancelled" if self.cancelled() else "failed", str(error)[:400])

    def execute(self) -> None:
        try:
            self.each([s["id"] for s in self.job["steps"]])
            self.finish("done")
        except Exception as error:
            self.finish("cancelled" if self.cancelled() else "failed", str(error)[:400])

    def price(self) -> None:
        """Dry-run every paid step (free) and add up what the catalog rates give."""
        items = []
        for s in self.job["steps"]:
            if s["kind"] != "paid" or s["status"] == "skipped":
                continue
            usd = None
            if s["id"] == "recast":
                seconds = self.ctx["clip_seconds"]
                usd = recast_price(seconds, self.ctx["resolution"])
                plan = ff.dry_run("recast", self.recast_inputs(self.ctx["photo_prepared"]), Path)
                s["detail"] = f"{seconds:.1f} с × {self.ctx['resolution']} → ${usd:.2f}. Запрос проверен (dry-run)."
                s["dry_run"] = plan
            elif s["id"] == "upscale":
                w, h = self.ctx["photo_size"]
                usd = upscale_price(w, h, self.ctx["upscale_scale"])
                s["detail"] = f"{w}×{h} × {self.ctx['upscale_scale']} → ${usd:.4f}"
            elif s["id"] == "run_app":
                s["dry_run"] = ff.dry_run(s["app"], self.app_inputs(), Path)
                s["detail"] = "Запрос проверен (dry-run). Цена по каталогу."
            elif s["id"] == "remove_bg":
                s["detail"] = "Цена по каталогу (не в сумме)."
            s["price_usd"] = usd
            items.append({"step": s["id"], "label": s["label"], "usd": usd, "text": s["price_text"]})
        known = [i["usd"] for i in items if i["usd"] is not None]
        with _LOCK:
            self.job["cost"] = {"items": items, "total_usd": round(sum(known), 2) if known else None,
                                "catalog_only": [i["label"] for i in items if i["usd"] is None]}

    # -------- recast inputs
    def recast_inputs(self, character: Path) -> dict:
        return {"clip": str(self.ctx["clip"]), "character": str(character), "resolution": self.ctx["resolution"],
                "turbo": self.ctx["turbo"], "seed": self.ctx["seed"]}

    def app_inputs(self) -> dict:
        app, values = ff.APPS_BY_ID[self.job["app"]], {}
        video = self.ctx.get("source") or self.ctx.get("video")
        for spec in app["inputs"]:
            if spec["type"] == "video" and video:
                values[spec["id"]] = str(video)
            elif spec["type"] == "image" and self.ctx.get("photo"):
                values[spec["id"]] = str(self.ctx["photo"])
            elif spec["type"] in ("text", "textarea") and spec["required"] and spec["id"] not in values:
                values[spec["id"]] = quoted(self.job["text"])
        return values

    def paid(self, app_id: str, inputs: dict, out: Path) -> Path:
        clean = ff.validate(app_id, inputs, Path)
        endpoint, body = ff.build_request(app_id, clean, self.tools.file_to_url)
        result = self.tools.fal(endpoint, body, self.cancelled)
        url = ff.output_url(result, ff.APPS_BY_ID[app_id]["output"])
        if not url:
            raise ChiefError(f"fal {endpoint}: в ответе нет ссылки на результат.")
        return self.tools.download(url, out)

    # -------- free steps
    def do_fetch(self) -> str:
        self.ctx["source"] = self.tools.fetch(self.ctx["video_url"], self.work)
        info = self.tools.probe(self.ctx["source"])
        return f"Скачано: {info['width']}×{info['height']}, {info['duration']:.1f} с."

    def do_pick(self) -> str:
        src = Path(self.ctx.get("source") or self.ctx["video"])
        self.ctx["source"] = src
        info = self.tools.probe(src)
        total = info["duration"]
        self.ctx["source_info"] = info
        asked = time_range(self.job["text"])
        if asked:
            start, length = asked[0], min(CLIP_MAX, max(CLIP_MIN, asked[1] - asked[0]))
            start = max(0.0, min(start, total - min(length, total)))
            self.ctx["span"] = (start, min(length, total - start))
            return f"Отрезок из просьбы: {start:.1f}–{start + self.ctx['span'][1]:.1f} с."
        if total <= CLIP_MAX:
            self.ctx["span"] = (0.0, total)
            if total < CLIP_MIN:
                self.warn(f"Видео короче {CLIP_MIN:.0f} с — беру его целиком ({total:.1f} с).")
            return f"Видео {total:.1f} с — беру целиком."
        frames = self.work / "frames"
        frames.mkdir(exist_ok=True)
        self.tools.run([self.tools.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
                        "-vf", "fps=1,scale=640:-2", str(frames / "%05d.jpg")])
        scores = []
        for path in sorted(frames.glob("*.jpg")):
            with Image.open(path) as im:
                scores.append(frame_score(face_boxes(im), im.height))
        if not any(s > 0.1 for s in scores):
            self.warn("Лица в видео не нашлись автоматически — беру отрезок из середины.")
        start = best_window(scores, int(CLIP_LEN)) if any(s > 0.1 for s in scores) else max(0, int(total / 2 - CLIP_LEN / 2))
        self.ctx["span"] = (float(start), min(CLIP_LEN, total - start))
        end = start + self.ctx["span"][1]
        return f"Лучший отрезок: {mmss(start)}–{mmss(end)} (один человек в кадре, средний/общий план)."

    def do_cut(self) -> str:
        start, length = self.ctx["span"]
        out = self.work / "clip.mp4"
        for crf, cap in ((20, 1080), (26, 1080), (28, 720)):
            scale = f"scale='if(gte(iw,ih),-2,min(iw,{cap}))':'if(gte(iw,ih),min(ih,{cap}),-2)'"
            self.tools.run([self.tools.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}",
                            "-i", self.ctx["source"], "-t", f"{length:.3f}", "-vf", scale, "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "aac",
                            "-b:a", "160k", "-ac", "2", "-movflags", "+faststart", out])
            if out.stat().st_size <= MAX_CLIP_MB * 1024 * 1024:
                break
        else:
            raise ChiefError(f"Клип больше {MAX_CLIP_MB} МБ даже после сжатия.")
        info = self.tools.probe(out)
        self.ctx.update(clip=out, clip_seconds=info["duration"], clip_size=(info["width"], info["height"]),
                        clip_audio=info["audio"])
        if not info["audio"]:
            self.warn("В исходном видео нет звука — возвращать будет нечего.")
        self.set("cut", file=out.name)
        return f"{info['width']}×{info['height']}, {info['duration']:.1f} с, {out.stat().st_size / 1048576:.1f} МБ, " \
               f"звук: {'есть' if info['audio'] else 'нет'}."

    def do_person(self) -> str:
        out, note = keep_one_person(Path(self.ctx["photo"]), self.work / "photo_person.png", self.job["text"])
        with Image.open(out) as im:
            size = im.size
        self.ctx.update(photo_prepared=out, photo_size=size)
        small = min(size) < SMALL_PHOTO
        self.ctx["upscale_scale"] = 4 if min(size) < SMALL_PHOTO / 2 else 2
        if not small:
            self.set("upscale", status="skipped", detail=f"Фото {size[0]}×{size[1]} — увеличивать не нужно.")
        self.set("person", file=out.name)
        return note + f" Размер {size[0]}×{size[1]}."

    def do_fit(self) -> str:
        w, h = self.ctx["clip_size"]
        out = fit_to_clip(self.ctx["cutout"], self.work / "character.png", w, h)
        self.ctx["character"] = out
        self.set("fit", file=out.name)
        with Image.open(out) as im:
            return f"Холст {im.width}×{im.height} под клип {w}×{h}: фигура целиком, fal ничего не обрежет."

    def do_audio(self) -> str:
        raw, out = self.ctx["recast_raw"], self.work / "result.mp4"
        if not self.ctx.get("clip_audio"):
            shutil.copyfile(raw, out)
            self.ctx["result"] = out
            return "Звука в исходнике нет — оставлено как есть."
        clip_s, raw_s = self.ctx["clip_seconds"], self.tools.probe(raw)["duration"]
        ratio = clip_s / raw_s if raw_s else 1.0
        video = ["-c:v", "copy"] if abs(ratio - 1) <= 0.02 else \
            ["-vf", f"setpts={ratio:.5f}*PTS", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
        self.tools.run([self.tools.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", raw, "-i",
                        self.ctx["clip"], "-map", "0:v:0", "-map", "1:a:0", *video, "-c:a", "aac", "-b:a", "160k",
                        "-shortest", "-movflags", "+faststart", out])
        self.ctx["result"] = out
        self.set("audio", file=out.name)
        return f"Звук из клипа наложен; видео {raw_s:.2f} с → {clip_s:.2f} с" + \
            (" (подогнано по длительности)." if abs(ratio - 1) > 0.02 else ".")

    def do_save(self) -> str:
        src = Path(self.ctx.get("result") or self.ctx["app_result"])
        name = f"{time.strftime('%Y-%m-%d-%Hh%Mm%Ss')}_chief_{self.job['chain']}_{self.job['id']}{src.suffix}"
        out_dir = self.job["_out"]
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out_dir / name)
        kind = ff.APPS_BY_ID[self.job["app"]]["output"]
        with _LOCK:
            self.job["output"] = {"filename": name, "url": self.job["_url_for"](name), "kind": kind}
        return f"Сохранено: {name}"

    # -------- paid steps
    def do_upscale(self) -> str:
        out = self.paid("upscale", {"image": str(self.ctx["photo_prepared"]), "scale": self.ctx["upscale_scale"]},
                        self.work / "photo_upscaled.png")
        self.ctx["photo_prepared"] = out
        self.set("upscale", file=out.name)
        with Image.open(out) as im:
            return f"Увеличено до {im.width}×{im.height}."

    def do_remove_bg(self) -> str:
        out = self.paid("remove-bg", {"image": str(self.ctx["photo_prepared"]), "model": "Portrait"},
                        self.work / "photo_cutout.png")
        self.ctx["cutout"] = out
        self.set("remove_bg", file=out.name)
        return "Фон убран."

    def do_recast(self) -> str:
        out = self.paid("recast", self.recast_inputs(self.ctx["character"]), self.work / "recast_raw.mp4")
        self.ctx["recast_raw"] = out
        return "Видео от fal получено (без пригодного звука — звук вернёт следующий шаг)."

    def do_run_app(self) -> str:
        app = ff.APPS_BY_ID[self.job["app"]]
        ext = {"image": ".png", "audio": ".mp3"}.get(app["output"], ".mp4")
        out = self.paid(app["id"], self.app_inputs(), self.work / f"result{ext}")
        self.ctx["app_result"] = out
        self.set("run_app", file=out.name)
        return "Готово."
