"""Cloud generation engine: runs a queued Maestro job on MiniMax API, fal or MuAPI.

Sits beside the native (wgp) and ComfyUI engines inside ``launch._run_generation``.
Keys and the active provider live in the repo-root ``.env``; nothing here imports
torch or loads local weights, so cloud jobs work on a machine without a GPU.
"""
from __future__ import annotations

import base64
import io
import mimetypes
import os
import time
import uuid
from pathlib import Path

import requests

from .job_lifecycle import finish_job, is_cancel_requested, update_job

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
PROVIDERS = {
    "minimax": ("MINIMAX_API_KEY",),
    "fal": ("FAL_KEY",),
    "muapi": ("MUAPI_API_KEY",),
}
# Every .env key the settings endpoint may write; values are never echoed back.
SECRET_KEYS = ("MINIMAX_API_KEY", "FAL_KEY", "MUAPI_API_KEY", "LLM_API_KEY")
PLAIN_KEYS = ("CLOUD_PROVIDER", "LLM_BASE_URL", "LLM_MODEL")
# fal video engines: Wan 2.2 (open model, default) and MiniMax H3 (fallback). Read-only override via the
# CLOUD_VIDEO_ENGINE environment variable (not written from the UI).
VIDEO_ENGINES = ("wan22", "h3")
DEFAULT_WAN_SECONDS = 5  # default clip length on Wan 2.2 (fal bills per second of video)


class CloudError(RuntimeError):
    pass


# ---------------------------------------------------------------- settings

def load_env(path: Path = ENV_PATH) -> None:
    """KEY=VALUE parser; the real process environment wins over the file."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or "").strip() or default


def save_env(updates: dict, path: Path = ENV_PATH) -> None:
    """Update or append keys in .env, keeping every other line untouched."""
    allowed = set(SECRET_KEYS) | set(PLAIN_KEYS)
    updates = {k: str(v or "").strip().replace("\n", "") for k, v in updates.items() if k in allowed}
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in updates and "=" in line and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={updates.pop(key)}"
    lines += [f"{k}={v}" for k, v in updates.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:  # keep the running process in sync with the file
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            if k.strip() in allowed:
                os.environ[k.strip()] = v.strip()


def ready(name: str) -> bool:
    return name in PROVIDERS and all(env(k) for k in PROVIDERS[name])


def active_provider() -> str | None:
    """The cloud provider chosen in .env, or None for local generation."""
    name = env("CLOUD_PROVIDER", "local").lower()
    return name if name in PROVIDERS else None


def public_config() -> dict:
    return {
        "provider": env("CLOUD_PROVIDER", "local").lower(),
        "providers": [{"name": n, "ready": ready(n)} for n in PROVIDERS],
        "keys": {k: bool(env(k)) for k in SECRET_KEYS},
        "video_engine": video_engine(),
        "llm_base_url": env("LLM_BASE_URL"),
        "llm_model": env("LLM_MODEL"),
    }


def video_engine() -> str:
    value = env("CLOUD_VIDEO_ENGINE", "wan22").lower()
    return value if value in VIDEO_ENGINES else "wan22"


def llm_override() -> dict | None:
    """Cloud LLM for Director/Studio planners when cloud mode and LLM keys are set."""
    if not active_provider() or not (env("LLM_BASE_URL") and env("LLM_API_KEY")):
        return None
    url = env("LLM_BASE_URL").rstrip("/")
    if url.endswith("/v1"):  # llm_service appends /v1/chat/completions itself
        url = url[:-3]
    return {"provider": "remote", "remote_url": url, "api_key": env("LLM_API_KEY"),
            "model_id": env("LLM_MODEL", "MiniMax-M2")}


# ---------------------------------------------------------------- HTTP

def _check(r: requests.Response, url: str) -> dict:
    if r.status_code >= 400:
        error = CloudError(f"{url} -> HTTP {r.status_code}: {r.text[:400]}")
        error.status = r.status_code
        raise error
    return r.json()


def post_json(url, headers, body, timeout=120):
    return _check(requests.post(url, json=body, headers=headers, timeout=timeout), url)


def get_json(url, headers, timeout=60):
    return _check(requests.get(url, headers=headers, timeout=timeout), url)


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or ("video/mp4" if str(path).lower().endswith((".mp4", ".mov")) else "image/png")
    return f"data:{mime};base64,{base64.b64encode(Path(path).read_bytes()).decode()}"


def download(url: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("data:"):
        out.write_bytes(base64.b64decode(url.split(",", 1)[1]))
        return out
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    return out


def poll(check, cancelled=lambda: False, interval=5.0, timeout=1200.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cancelled():
            raise InterruptedError("Cancelled")
        result = check()
        if result is not None:
            return result
        time.sleep(interval)
    raise CloudError("cloud provider timed out")


# ---------------------------------------------------------------- request shape

def _ratio(w: int, h: int) -> str:
    options = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1.0, "4:3": 4 / 3, "3:4": 3 / 4}
    return min(options, key=lambda k: abs(options[k] - w / max(h, 1)))


# Inputs the H3 cloud APIs cannot take; such jobs fail clearly instead of silently losing them.
UNSUPPORTED_PARAMS = {
    "video_guide": "source video", "video_source": "source video", "image_mask": "mask",
    "video_mask": "mask", "audio_guide": "audio guide", "viggle_character": "Viggle character",
    "sfx_mode": "sound effects", "edit_repaint_shot_aware": "repaint", "edit_outpaint_shot_aware": "outpaint",
    "_blend_mode": "blend",
}


# fal Wan 2.2 has a video-to-video endpoint, so a source video (Extend / Control video) runs in the cloud.
WAN_VIDEO_PARAMS = ("video_source", "video_guide")
WAN_VIDEO_MAX_BYTES = 40 * 1024 * 1024


def unsupported_reason(params: dict, model_def: dict | None, provider: str | None = None) -> str | None:
    if (model_def or {}).get("audio_only"):
        return "audio generation"
    skip = WAN_VIDEO_PARAMS if provider == "fal" and video_engine() == "wan22" else ()
    return next((label for key, label in UNSUPPORTED_PARAMS.items() if key not in skip and params.get(key)), None)


def _first_video(params: dict) -> Path | None:
    for key in WAN_VIDEO_PARAMS:
        value = params.get(key)
        value = value[0] if isinstance(value, (list, tuple)) and value else value
        if isinstance(value, str) and value and Path(value).is_file():
            return Path(value)
    return None


def request_from_params(params: dict, model_def: dict | None, work_dir: Path) -> dict:
    """Map wgp job params to a provider-neutral request."""
    try:
        w, h = (int(x) for x in str(params.get("resolution") or "1280x720").lower().split("x"))
    except ValueError:
        w, h = 1280, 720
    fps = float((model_def or {}).get("fps") or 24)
    frames = int(params.get("video_length") or 0)
    is_image = int(params.get("image_mode") or 0) > 0 or (model_def or {}).get("image_outputs", False)
    image = _first_image(params.get("image_start"), work_dir) or _first_image(params.get("image_refs"), work_dir)
    return {
        "kind": "image" if is_image else "video",
        "prompt": str(params.get("prompt") or "").strip(),
        "image": image,
        "image_end": None if is_image else _first_image(params.get("image_end"), work_dir),
        "video": None if is_image else _first_video(params),
        "width": w, "height": h, "ratio": _ratio(w, h),
        # MiniMax H3 and fal H3 both accept 768P (native) and 2K (upscaled); 1080P is not valid.
        "resolution": "2K" if min(w, h) >= 1080 else "768P",
        "duration": max(4, min(15, round(frames / fps))) if frames else 6,
    }


def _first_image(value, work_dir: Path) -> Path | None:
    """wgp params hold a path, a list of paths, or a PIL image after preparation."""
    if isinstance(value, (list, tuple)):
        for item in value:
            found = _first_image(item, work_dir)
            if found:
                return found
        return None
    if isinstance(value, str) and value and Path(value).is_file():
        return Path(value)
    if hasattr(value, "save"):  # PIL.Image
        work_dir.mkdir(parents=True, exist_ok=True)
        path = work_dir / f"cloud_ref_{uuid.uuid4().hex}.png"
        buf = io.BytesIO()
        value.save(buf, format="PNG")
        path.write_bytes(buf.getvalue())
        return path
    return None


# ---------------------------------------------------------------- providers

class MiniMax:
    @property
    def base(self):
        return env("MINIMAX_BASE_URL", "https://api.minimax.io").rstrip("/")

    @property
    def headers(self):
        return {"Authorization": f"Bearer {env('MINIMAX_API_KEY')}", "Content-Type": "application/json"}

    def video_body(self, req: dict) -> dict:
        model = env("MINIMAX_VIDEO_MODEL", "MiniMax-H3")
        content = [{"type": "text", "text": req["prompt"][:7000]}]
        body = {"model": model, "content": content, "resolution": req["resolution"],
                "duration": max(5 if model.endswith("-Max") else 4, req["duration"])}
        if req["image"]:
            content.append({"type": "image_url", "role": "first_frame",
                            "image_url": {"url": data_uri(req["image"])}})
        if req.get("image_end"):
            content.append({"type": "image_url", "role": "last_frame",
                            "image_url": {"url": data_uri(req["image_end"])}})
        if not (req["image"] or req.get("image_end")):
            body["ratio"] = req["ratio"]
        return body

    def image_body(self, req: dict) -> tuple[str, dict]:
        """H3-Image: /v1/images/generations, or /v1/images/edits with a reference image."""
        body = {"model": env("MINIMAX_IMAGE_MODEL", "MiniMax-H3-Image"), "prompt": req["prompt"][:32000],
                "aspect_ratio": req["ratio"], "area": "2K", "output_format": "png",
                "response_format": "url", "n": 1}
        if req["image"]:
            body["images"] = [{"image_url": data_uri(req["image"])}]
            return "/v1/images/edits", body
        return "/v1/images/generations", body

    def run(self, req, out, cancelled):
        if req["kind"] == "image":
            path, body = self.image_body(req)
            # Not idempotent and may take minutes: one call, long timeout, no retry.
            data = post_json(f"{self.base}{path}", self.headers, body, timeout=600)
            item = (data.get("data") or [{}])[0]
            if not item.get("url"):
                raise CloudError(f"MiniMax image: {item.get('error') or data.get('error') or data}")
            return download(item["url"], out)
        created = post_json(f"{self.base}/v2/video_generation", self.headers, self.video_body(req))
        task_id = created.get("task_id") or (created.get("task") or {}).get("id") or created.get("id")
        if not task_id:
            raise CloudError(f"MiniMax returned no task_id: {created}")

        def check():
            task = get_json(f"{self.base}/v2/query/video_generation/{task_id}", self.headers)
            task = task.get("task", task)
            state = task.get("status")
            if state == "succeeded":
                return (task.get("content") or {}).get("url")
            if state in ("failed", "cancelled"):
                raise CloudError(f"MiniMax H3 task {state}: {task.get('error') or ''}")
            return None

        return download(poll(check, cancelled, interval=10), out)


class Fal:
    @property
    def headers(self):
        return {"Authorization": f"Key {env('FAL_KEY')}", "Content-Type": "application/json"}

    # Wan 2.2 A14B on fal (checked against fal.ai docs 2026-11-14): text-to-video takes aspect_ratio
    # 16:9|9:16|1:1; image-to-video takes image_url (+ end_image_url); both take num_frames 17..161 at
    # frames_per_second (default 16) and resolution 480p|580p|720p; output video.url. The /turbo i2v
    # variant has no num_frames. fal lists these models for removal on 2027-01-04 -> H3 fallback.
    WAN_FPS = 16
    WAN_MAX_SECONDS = (161 - 1) // WAN_FPS  # 10 s

    def endpoint_and_body(self, req: dict, engine: str | None = None) -> tuple[str, dict]:
        if req["kind"] == "image":
            body = {"prompt": req["prompt"], "num_images": 1, "output_format": "png",
                    "image_size": {"width": req["width"], "height": req["height"]}}
            return env("FAL_IMAGE_MODEL", "fal-ai/moss-image"), body
        if (engine or req.get("engine") or video_engine()) == "wan22" and self.wan_fits(req):
            return self.wan_endpoint_and_body(req)
        return self.h3_endpoint_and_body(req)

    def wan_fits(self, req: dict) -> bool:
        """Wan needs a start frame for i2v and caps clips at 10 s; otherwise H3 takes the job."""
        if req.get("video"):
            return True
        return req["duration"] <= self.WAN_MAX_SECONDS and not (req.get("image_end") and not req["image"])

    def wan_endpoint_and_body(self, req: dict) -> tuple[str, dict]:
        short = min(req["width"], req["height"])
        body = {"prompt": req["prompt"], "resolution": "480p" if short < 540 else "580p" if short < 680 else "720p"}
        if req.get("negative_prompt"):
            body["negative_prompt"] = req["negative_prompt"]
        if req.get("video"):
            if Path(req["video"]).stat().st_size > WAN_VIDEO_MAX_BYTES:
                raise CloudError("Исходное видео больше 40 МБ — укоротите или сожмите его для облака.")
            model = env("FAL_WAN_V2V_MODEL", "fal-ai/wan/v2.2-a14b/video-to-video")
            body["video_url"] = data_uri(req["video"])
            body["aspect_ratio"] = "auto"
        elif req["image"]:
            model = env("FAL_WAN_I2V_MODEL", "fal-ai/wan/v2.2-a14b/image-to-video")
            body["image_url"] = data_uri(req["image"])
            body["aspect_ratio"] = "auto"
            if req.get("image_end"):
                body["end_image_url"] = data_uri(req["image_end"])
        else:
            model = env("FAL_WAN_T2V_MODEL", "fal-ai/wan/v2.2-a14b/text-to-video")
            body["aspect_ratio"] = req["ratio"] if req["ratio"] in ("16:9", "9:16", "1:1") else (
                "16:9" if req["width"] > req["height"] else "9:16" if req["height"] > req["width"] else "1:1")
        if not model.endswith("/turbo"):  # turbo has a fixed length
            body["num_frames"] = req["duration"] * self.WAN_FPS + 1
            body["frames_per_second"] = self.WAN_FPS
        return model, body

    def h3_endpoint_and_body(self, req: dict) -> tuple[str, dict]:
        body = {"prompt": req["prompt"], "duration": max(5, req["duration"]), "resolution": req["resolution"]}
        if req["image"] or req.get("image_end"):
            if req["image"]:
                body["image_url"] = data_uri(req["image"])
            if req.get("image_end"):
                body["end_image_url"] = data_uri(req["image_end"])
            return env("FAL_VIDEO_MODEL", "minimax/h3/image-to-video"), body
        body["aspect_ratio"] = req["ratio"]
        return env("FAL_T2V_MODEL", "minimax/h3/text-to-video"), body

    def submit(self, req: dict) -> tuple[str, dict]:
        model, body = self.endpoint_and_body(req)
        try:
            return model, post_json(f"https://queue.fal.run/{model}", self.headers, body)
        except CloudError as error:
            # Wan endpoint gone or rejecting the input (nothing was generated, nothing billed): use H3 once.
            if "/wan/" not in model or req.get("video") or getattr(error, "status", None) not in (404, 410, 422):
                raise
            model, body = self.endpoint_and_body(req, engine="h3")
            return model, post_json(f"https://queue.fal.run/{model}", self.headers, body)

    def run(self, req, out, cancelled):
        model, sub = self.submit(req)
        result = self.wait(model, sub, cancelled)
        url = ((result.get("images") or [{}])[0].get("url") if req["kind"] == "image"
               else (result.get("video") or {}).get("url"))
        if not url:
            raise CloudError(f"fal {model}: no output url in {list(result)}")
        return download(url, out)

    def call(self, model: str, body: dict, cancelled=lambda: False) -> dict:
        """Any fal queue model (background removal, upscaling, ...): submit, poll, return the result JSON."""
        return self.wait(model, post_json(f"https://queue.fal.run/{model}", self.headers, body), cancelled)

    def wait(self, model: str, sub: dict, cancelled) -> dict:
        status_url, response_url = sub.get("status_url"), sub.get("response_url")
        if not (status_url and response_url):
            raise CloudError(f"fal: unexpected queue response: {sub}")

        def check():
            state = get_json(status_url, self.headers).get("status")
            if state == "COMPLETED":
                return True
            if state in ("FAILED", "ERROR", "CANCELLED"):
                raise CloudError(f"fal {model}: {state}")
            return None

        poll(check, cancelled, interval=4)
        return get_json(response_url, self.headers)


class MuApi:
    BASE = "https://api.muapi.ai/api/v1"

    @property
    def headers(self):
        return {"x-api-key": env("MUAPI_API_KEY"), "Content-Type": "application/json"}

    def slug_and_body(self, req: dict) -> tuple[str, dict]:
        # Checked against muapi.ai docs: minimax-h3-text-to-video, minimax-h3-image-to-video (image_url),
        # qwen2-1-image-to-image (images_list). shortcut: minimax-h3-image fields are undocumented;
        # if it returns 4xx, change MUAPI_IMAGE_MODEL in .env.
        body = {"prompt": req["prompt"], "aspect_ratio": req["ratio"]}
        if req["kind"] == "image":
            if req["image"]:
                body["images_list"] = [data_uri(req["image"])]  # qwen2-1-image-to-image takes a list
                return env("MUAPI_EDIT_MODEL", "qwen2-1-image-to-image"), body
            return env("MUAPI_IMAGE_MODEL", "minimax-h3-image"), body
        body["duration"] = max(5, req["duration"])
        if req["image"]:
            body["image_url"] = data_uri(req["image"])
            if req.get("image_end"):
                body["last_image_url"] = data_uri(req["image_end"])
            return env("MUAPI_VIDEO_MODEL", "minimax-h3-image-to-video"), body
        return env("MUAPI_T2V_MODEL", "minimax-h3-text-to-video"), body

    def run(self, req, out, cancelled):
        slug, body = self.slug_and_body(req)
        rid = post_json(f"{self.BASE}/{slug}", self.headers, body).get("request_id")
        if not rid:
            raise CloudError(f"MuAPI {slug}: no request_id")

        def check():
            data = get_json(f"{self.BASE}/predictions/{rid}/result", self.headers)
            if data.get("status") == "completed":
                outputs = data.get("outputs") or []
                if not outputs:
                    raise CloudError(f"MuAPI {slug}: empty outputs")
                return outputs[0]
            if data.get("status") == "failed":
                raise CloudError(f"MuAPI {slug}: {data.get('error')}")
            return None

        return download(poll(check, cancelled), out)


CLIENTS = {"minimax": MiniMax, "fal": Fal, "muapi": MuApi}


# ---------------------------------------------------------------- job bridge

def execute(job: dict, provider: str, model_def: dict | None, *, finalize: bool = True) -> bool:
    """Run one queued job in the cloud and finish it like a native job."""
    if not ready(provider):
        raise CloudError(f"Нет ключа облака '{provider}'. Впишите его: Settings → Integrations → Cloud.")
    params = job["params"]
    reason = unsupported_reason(params, model_def, provider)
    if reason:
        raise CloudError(f"Cloud generation does not support {reason}. Switch Generation backend to Local models for this job.")
    out_dir = Path(job.get("out_dir") or "outputs")
    req = request_from_params(params, model_def, out_dir / ".cloud_refs")
    if not req["prompt"]:
        raise CloudError("Нужен текст задания (промпт) для облачной генерации.")
    seconds = int(params.get("video_length") or 0) / float((model_def or {}).get("fps") or 24)
    shortened = False
    if req["kind"] == "video" and provider == "fal" and video_engine() == "wan22" and req["duration"] > Fal.WAN_MAX_SECONDS:
        # Wan 2.2 makes up to 10 s per clip. Longer requests (Studio's "Auto" length) get the default
        # 5 s on Wan instead of silently going to MiniMax H3; H3 only when CLOUD_VIDEO_ENGINE=h3.
        req["duration"] = DEFAULT_WAN_SECONDS
        shortened = True
    elif req["kind"] == "video" and seconds > 15.5:
        raise CloudError(f"Cloud H3 makes clips up to 15 s; this job asks for {seconds:.1f} s. "
                         "Shorten it or switch Generation backend to Local models.")
    started = time.monotonic()
    update_job(job, phase="cloud", message=(f"Генерация · {provider} Wan 2.2 · {DEFAULT_WAN_SECONDS} с (Wan делает до 10 с за раз)"
                                            if shortened else f"Генерация · {provider} {req['kind']}"))
    ext = ".png" if req["kind"] == "image" else ".mp4"
    name = f"{time.strftime('%Y-%m-%d-%Hh%Mm%Ss')}_cloud_{provider}_{job['id']}{ext}"
    CLIENTS[provider]().run(req, out_dir / name, lambda: is_cancel_requested(job))
    params["generation_engine"] = f"cloud:{provider}"
    job["generation_time"] = time.monotonic() - started
    if finalize:
        return bool(finish_job(job, "completed", output_files=[name], progress=100, step=0,
                               total_steps=0, phase="", message=f"Done · {provider}"))
    update_job(job, output_files=[name], progress=100, phase="", message="Cloud output ready.")
    return True


load_env()
