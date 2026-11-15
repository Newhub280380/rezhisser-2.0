"""Руководитель (services/chief.py): план, цена, подтверждение, цепочка замены персонажа.
fal заменён заглушкой — ни одного сетевого запроса. Если рядом лежат тестовые входы миссии
(workspace/8mile-recast-clip.mp4, workspace/alex-recast.jpg), цепочка проверяется на них, иначе на синтетике."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from services import chief  # noqa: E402

WORKSPACE = Path(__file__).resolve().parents[2]
REAL_CLIP, REAL_PHOTO = WORKSPACE / "8mile-recast-clip.mp4", WORKSPACE / "alex-recast.jpg"
FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not FFMPEG, reason="ffmpeg not on PATH")


class MockFal:
    """Stands in for the fal queue: records every call, writes plausible outputs on download."""

    def __init__(self, fail_recast=0, recast_seconds=12.0):
        self.calls, self.fail_recast, self.recast_seconds, self.last = [], fail_recast, recast_seconds, {}

    def call(self, endpoint, body, cancelled):
        self.calls.append(endpoint)
        if "animate/replace" in endpoint and self.fail_recast:
            self.fail_recast -= 1
            raise RuntimeError("fal: mock failure")
        self.last[endpoint] = body
        key = "video" if "animate" in endpoint else "image"
        return {key: {"url": f"mock://{endpoint}"}}

    def download(self, url, out):
        endpoint = url[len("mock://"):]
        body = self.last[endpoint]
        if "seedvr" in endpoint:
            im = Image.open(body["image_url"][7:])
            im.resize((im.width * body["upscale_factor"], im.height * body["upscale_factor"])).save(out)
        elif "birefnet" in endpoint:
            im = Image.open(body["image_url"][7:]).convert("RGBA")
            mask = Image.new("L", im.size, 0)
            ImageDraw.Draw(mask).ellipse((im.width * .25, im.height * .05, im.width * .75, im.height * .98), fill=255)
            im.putalpha(mask)
            im.save(out)
        else:  # Wan Animate: silent video, a bit shorter than the clip (like fal's 16 fps output)
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"testsrc=size=854x480:rate=16:duration={self.recast_seconds}", "-c:v", "libx264",
                            "-pix_fmt", "yuv420p", str(out)], check=True)
        return out


def tools(fal):
    return chief.Tools(client=fal, file_to_url=lambda p: f"file://{p}", download=fal.download)


@pytest.fixture()
def inputs(tmp_path):
    if REAL_CLIP.is_file() and REAL_PHOTO.is_file():
        return REAL_CLIP, REAL_PHOTO
    clip, photo = tmp_path / "clip.mp4", tmp_path / "photo.jpg"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=24:duration=13",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=13", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(clip)], check=True)
    Image.new("RGB", (424, 992), (90, 120, 160)).save(photo)
    return clip, photo


def plan(tmp_path, fal, **request):
    return chief.plan(request, tools=tools(fal), work_root=tmp_path / "work", out_dir=tmp_path / "out",
                      url_for=lambda n: f"/files/{n}", background=False)


def probe(path):
    out = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    return float(data["format"]["duration"]), [s["codec_type"] for s in data["streams"]]


# ---------------------------------------------------------------- understanding and prices

def test_understand_routes_requests():
    assert chief.understand("замени человека в клипе на меня", True, True) == {"chain": "recast_clip", "app": "recast"}
    assert chief.understand("", True, True)["chain"] == "recast_clip"  # video + photo and nothing else
    assert chief.understand("убери фон", False, True) == {"chain": "app", "app": "remove-bg"}
    assert chief.understand("убери фон", True, False)["app"] == "video-remove-bg"
    assert chief.understand("улучши фото", False, True)["app"] == "upscale"
    assert chief.understand("сделай дубляж на английский", True, False)["app"] == "dub-cloud"
    assert chief.understand("сделай клон вирусного ролика", False, False)["chain"] == "viral_clone"
    with pytest.raises(chief.ChiefError, match="Руководитель умеет"):
        chief.understand("привет", False, False)


def test_prices_come_from_catalog_rates():
    assert chief.recast_price(13.0, "480p") == 0.52
    assert chief.recast_price(13.0, "580p") == 0.78
    assert chief.recast_price(13.0, "720p") == 1.04
    assert chief.upscale_price(424, 992, 2) == round(848 * 1984 / 1e6 * 0.001, 4)


def test_time_range_and_window_choice():
    assert chief.time_range("возьми 4:36–4:49") == (276.0, 289.0)
    assert chief.time_range("с 0:05 по 0:18") == (5.0, 18.0)
    assert chief.time_range("без времени") is None
    one, crowd, empty = chief.frame_score([(0, 0, 50, 50)], 480), chief.frame_score([(0, 0, 9, 9)] * 3, 480), \
        chief.frame_score([], 480)
    assert one == 1.0 and crowd < 0 < empty < one
    scores = [empty] * 5 + [one] * 13 + [crowd] + [one] * 12
    assert chief.best_window(scores, 13) == 5  # the run of single-person frames, not the one touching the crowd


# ---------------------------------------------------------------- the recast chain end to end (mock fal)

def test_recast_chain_plan_then_confirm(tmp_path, inputs):
    clip, photo = inputs
    fal = MockFal()
    job = plan(tmp_path, fal, text="замени человека в этом клипе на меня", video=clip, photo=photo)
    assert job["status"] == "awaiting_confirmation", job
    assert fal.calls == []  # planning is free
    steps = {s["id"]: s for s in job["steps"]}
    assert list(steps) == ["pick", "cut", "person", "upscale", "remove_bg", "fit", "recast", "audio", "save"]
    assert all(steps[k]["status"] == "done" for k in ("pick", "cut", "person"))
    assert steps["upscale"]["status"] == "pending"  # 424 px short side -> SeedVR2 x2
    assert steps["recast"]["dry_run"]["submitted"] is False
    assert steps["recast"]["dry_run"]["endpoint"] == "fal-ai/wan/v2.2-14b/animate/replace"
    assert job["cost"]["total_usd"] == round(chief.recast_price(13.0, "480p") + steps["upscale"]["price_usd"], 2)
    assert 0.50 <= job["cost"]["total_usd"] <= 0.54
    assert "Убрать фон" in job["cost"]["catalog_only"][0]
    cut = tmp_path / "work" / f"chief_{job['id']}" / "clip.mp4"
    seconds, streams = probe(cut)
    assert 12.9 <= seconds <= 13.1 and "audio" in streams and cut.stat().st_size < 40 * 1024 * 1024

    with pytest.raises(chief.ChiefError, match="подтверждение"):
        chief.confirm(job["id"], tools=tools(fal), confirmed=False, background=False)
    assert fal.calls == []

    done = chief.confirm(job["id"], tools=tools(fal), confirmed=True, background=False)
    assert done["status"] == "done", done
    assert fal.calls == ["fal-ai/seedvr/upscale/image", "fal-ai/birefnet/v2", "fal-ai/wan/v2.2-14b/animate/replace"]
    body = fal.last["fal-ai/wan/v2.2-14b/animate/replace"]
    assert body["resolution"] == "480p" and body["use_turbo"] is True
    character = Image.open(body["image_url"][7:])
    assert abs(character.width / character.height - 16 / 9) < 0.01  # fal's centre crop keeps the whole figure
    result = tmp_path / "out" / done["output"]["filename"]
    seconds, streams = probe(result)
    assert "audio" in streams and abs(seconds - 13.0) < 0.3  # original sound back, video stretched 12 s -> 13 s
    assert done["output"]["kind"] == "video" and done["output"]["url"].startswith("/files/")


def test_failed_paid_step_resumes_without_repeating(tmp_path, inputs):
    clip, photo = inputs
    fal = MockFal(fail_recast=1)
    job = plan(tmp_path, fal, text="замени персонажа", video=clip, photo=photo)
    failed = chief.confirm(job["id"], tools=tools(fal), confirmed=True, background=False)
    assert failed["status"] == "failed" and "mock failure" in failed["error"]
    assert {s["id"]: s["status"] for s in failed["steps"]}["recast"] == "failed"
    done = chief.confirm(job["id"], tools=tools(fal), confirmed=True, background=False)
    assert done["status"] == "done"
    assert fal.calls.count("fal-ai/seedvr/upscale/image") == 1 and fal.calls.count("fal-ai/birefnet/v2") == 1


def test_time_range_from_request_and_no_key(tmp_path, inputs):
    clip, photo = inputs
    job = plan(tmp_path, MockFal(), text="замени меня, отрезок 0:01-0:12", video=clip, photo=photo)
    assert "1.0–12.0" in job["steps"][0]["detail"]
    no_key = chief.Tools(client=None)
    with pytest.raises(chief.ChiefError, match="Нет ключа fal"):
        chief.confirm(job["id"], tools=no_key, confirmed=True, background=False)


def test_cancel_before_confirmation(tmp_path, inputs):
    clip, photo = inputs
    job = plan(tmp_path, MockFal(), text="замени", video=clip, photo=photo)
    assert chief.cancel(job["id"])["status"] == "cancelled"
    with pytest.raises(chief.ChiefError):
        chief.confirm(job["id"], tools=tools(MockFal()), confirmed=True, background=False)


def test_needs_both_inputs_and_soon_chains(tmp_path, inputs):
    clip, _ = inputs
    with pytest.raises(chief.ChiefError, match="нужны видео"):
        plan(tmp_path, MockFal(), text="замени человека", video=clip)
    soon = plan(tmp_path, MockFal(), text="сделай три копии вирусного ролика под мою нишу")
    assert soon["status"] == "soon" and soon["steps"] == [] and soon["warnings"]
    dubit = plan(tmp_path, MockFal(), text="переозвучь ролик", video=clip)
    assert dubit["status"] == "soon"
    with pytest.raises(chief.ChiefError, match="http"):
        plan(tmp_path, MockFal(), text="замени", video_url="file:///etc/passwd", photo=clip)


def test_single_app_chain(tmp_path, inputs):
    _, photo = inputs
    fal = MockFal()
    job = plan(tmp_path, fal, text="убери фон с фото", photo=photo)
    assert job["status"] == "awaiting_confirmation" and job["app"] == "remove-bg"
    assert [s["id"] for s in job["steps"]] == ["run_app", "save"]
    assert job["steps"][0]["dry_run"]["endpoint"] == "fal-ai/birefnet/v2" and fal.calls == []
    done = chief.confirm(job["id"], tools=tools(fal), confirmed=True, background=False)
    assert done["status"] == "done" and done["output"]["kind"] == "image" and fal.calls == ["fal-ai/birefnet/v2"]


def test_keep_one_person_and_fit(tmp_path):
    src = tmp_path / "tall.png"
    im = Image.new("RGBA", (300, 900), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle((100, 50, 200, 880), fill=(200, 50, 50, 255))
    im.save(src)
    out = chief.fit_to_clip(src, tmp_path / "fit.png", 1080, 1920)
    with Image.open(out) as fit:
        assert abs(fit.width / fit.height - 9 / 16) < 0.01 and min(fit.size) >= 720
    path, note = chief.keep_one_person(src, tmp_path / "one.png")
    assert path.is_file() and note


@pytest.mark.skipif(not REAL_CLIP.is_file(), reason="mission test clip not present")
def test_pick_finds_the_person_in_a_long_video(tmp_path):
    """15 s of empty test pattern + the 8 Mile clip + 12 s of pattern: the chosen 13 s must sit on the clip."""
    long = tmp_path / "long.mp4"
    pattern = "testsrc=size=1920x1080:rate=24:duration={}"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", pattern.format(15), "-i", str(REAL_CLIP),
                    "-f", "lavfi", "-i", pattern.format(12), "-filter_complex",
                    "[0:v]fps=24,format=yuv420p[a];[1:v]fps=24,format=yuv420p[b];[2:v]fps=24,format=yuv420p[c];"
                    "[a][b][c]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast",
                    str(long)], check=True)
    _, photo = REAL_CLIP, REAL_PHOTO
    job = plan(tmp_path, MockFal(), text="замени человека", video=long, photo=photo)
    pick = job["steps"][0]
    assert pick["id"] == "pick" and pick["status"] == "done", job
    start = int(pick["detail"].split("отрезок: ")[1].split("–")[0].split(":")[1])
    assert 12 <= start <= 16, pick["detail"]  # covers every second where the face is seen (clip s 2-10)
    assert any("нет звука" in w for w in job["warnings"])
