"""One-prompt film (Dreamina Drama Studio-style) and the knowledge graph memory. No network: fal, LLM and TTS mocked;
ffmpeg, Pillow and the real docs/assistant-knowledge folder are used."""
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from services import assistant_chat  # noqa: E402
from services import assistant_knowledge as kb  # noqa: E402
from services import autopilot  # noqa: E402
from services import cloud_generation as cg  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _ffmpeg():
    try:
        return autopilot.Deps().ffmpeg()
    except Exception:
        pytest.skip("ffmpeg is needed to render clips")


def _streams(ffmpeg: str, path: Path) -> str:
    return subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr


SCRIPT = {"ideas": ["врач и коробка", "крупные планы", "отзыв"], "chosen": 1, "title": "Черновик", "hook": "Стоп!",
          "language": "ru", "scenes": [{"index": 1, "seconds": 5, "description": "врач", "voiceover": "Стоп."}]}
DOCTORED = {"grade": "A", "issues": ["хук слабый — усилен"], "title": "ZISHÉL Glam для врачей", "hook": "Восемь лет.",
            "language": "ru", "scenes": [{"index": 1, "seconds": 5, "description": "врач", "voiceover": "Восемь лет."}]}
ASSETS = {"assets": [{"id": "doctor", "kind": "character", "name": "Врач",
                      "description": "female doctor, 35, white coat, dark hair in a bun"},
                     {"id": "glam", "kind": "product", "name": "ZISHÉL Glam", "description": "real photo"}]}
BOARD = {"scenes": [
    {"index": 1, "seconds": 5, "shot": "medium", "camera": "slow dolly push in", "action": "smiles",
     "prompt": "slow dolly push in, female doctor, 35, white coat, smiles, clinic, soft light, photorealistic",
     "negative_prompt": "blurry", "voiceover": "Восемь лет успешного применения.", "asset_ids": ["doctor"],
     "product": False},
    {"index": 2, "seconds": 5, "shot": "close-up", "camera": "slow orbit", "action": "light sweep",
     "prompt": "slow orbit 20 degrees around the box, pearl background, product geometry unchanged",
     "voiceover": "ZISHÉL Glam. Официальная регистрация в Казахстане.", "asset_ids": ["glam"], "product": True},
    {"index": 3, "seconds": 5, "camera": "static shot", "prompt": "static shot, female doctor, 35, white coat, nods",
     "voiceover": "", "product": False},
]}


class FakeDeps(autopilot.Deps):
    def __init__(self, ffmpeg, board=None):
        self._ffmpeg, self.board = ffmpeg, board or BOARD
        self.prompts, self.media, self.tts_calls = [], [], []

    def ffmpeg(self):
        return self._ffmpeg

    def llm(self, messages):
        text = messages[0]["content"]
        self.prompts.append(text)
        if text.startswith("Ты сценарист"):
            return json.dumps(SCRIPT, ensure_ascii=False)
        if text.startswith("Ты сценарный доктор"):
            return "Оценка:\n```json\n" + json.dumps(DOCTORED, ensure_ascii=False) + "\n```"
        if text.startswith("Выпиши из сценария"):
            return json.dumps(ASSETS, ensure_ascii=False)
        if text.startswith("Сделай раскадровку"):
            return json.dumps(self.board, ensure_ascii=False)
        raise AssertionError("unexpected LLM step: " + text[:60])

    def fal_media(self, req, out, cancelled):
        self.media.append(dict(req, image=str(req["image"]) if req.get("image") else None, out=Path(out).name))
        if req["kind"] == "image":
            Image.new("RGB", (req["width"], req["height"]), (20, 160, 90)).save(out)
            return out
        subprocess.run([self._ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc=size=480x854:rate=16:duration=2", "-pix_fmt", "yuv420p", str(out)], check=True)
        return out

    def tts(self, text, language, out, cancelled):
        self.tts_calls.append((text, language))
        target = out.with_suffix(".wav")
        subprocess.run([self._ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=440:d=1.2",
                        str(target)], check=True)
        return target


def _run(tmp_path, deps, phrase="ролик 15 секунд про ZISHÉL Glam для врачей"):
    return autopilot.start("one_prompt_film", {"request": phrase, "total_seconds": 15, "aspect": "9:16"},
                           out_dir=tmp_path / "out", work_root=tmp_path / "work", deps=deps, background=False)


def test_one_phrase_to_finished_film_with_beautyart_product(tmp_path):
    ffmpeg = _ffmpeg()
    deps = FakeDeps(ffmpeg)
    state = _run(tmp_path, deps)
    assert state["status"] == "done", state["error"]

    labels = kb.recipe("one_prompt_film")["progress_labels"]
    log = state["log"]
    expected = [labels[0], labels[1], labels[2], labels[3], "Рисую ключевой кадр 1 из 3", "Генерирую сцену 1 из 3",
                "Генерирую сцену 3 из 3", labels[6], labels[7], labels[8], labels[9], labels[10]]
    positions = [log.index(item) for item in expected]
    assert positions == sorted(positions)
    assert "Рисую ключевой кадр 2 из 3" not in log  # the product scene uses the real photo, no generated keyframe

    # 1) script with 3 ideas, 2) the doctor's fixed version is what the film uses
    assert len(deps.prompts) == 4
    script_prompt, doctor_prompt, assets_prompt, board_prompt = deps.prompts
    assert "«ролик 15 секунд про ZISHÉL Glam для врачей»" in script_prompt and "15 с" in script_prompt
    assert state["script"]["grade"] == "A" and state["script"]["title"] == "ZISHÉL Glam для врачей"
    assert state["script"]["ideas"] == SCRIPT["ideas"] and json.dumps(SCRIPT, ensure_ascii=False) in doctor_prompt
    # Beautyart product: hard rules + product file in every LLM step, Wan formula from rules.md in the storyboard
    for prompt in deps.prompts:
        assert "Правила карточек Beautyart" in prompt and "ZISHÉL Glam — флагман Beautyart" in prompt
    assert "Формула промпта для видео" in board_prompt and "female doctor" in board_prompt
    assert state["script"]["products"] == ["products/ours/zishel-glam.md"]

    # 3–5) keyframes only for scenes without the product; product scene starts from the REAL photo (JPEG of refs/ours)
    keyframes = [m for m in deps.media if m["kind"] == "image"]
    videos = [m for m in deps.media if m["kind"] == "video"]
    assert [k["out"] for k in keyframes] == ["key_1.png", "key_3.png"]
    assert videos[0]["image"].endswith("key_1.png") and videos[1]["image"].endswith("photo_1.jpg")
    assert videos[2]["image"].endswith("key_3.png")
    assert all(v["width"] == 480 and v["engine"] is None for v in videos)  # draft 480p on Wan 2.2
    with Image.open(Path(videos[1]["image"])) as product:
        assert max(product.size) == autopilot.TARGET_LONG_SIDE
    # 6) voiceover in Russian per scene (scene 3 has none)
    assert deps.tts_calls == [("Восемь лет успешного применения.", "ru"),
                              ("ZISHÉL Glam. Официальная регистрация в Казахстане.", "ru")]
    # 8) subtitles timed by the audio length, starting at each scene's start (2 s clips, 0.3 s crossfade)
    srt = next((tmp_path / "work").glob("autopilot_*/subs.srt")).read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:01,200\nВосемь лет успешного применения." in srt
    assert "00:00:01,700 --> 00:00:02," in srt and "ZISHÉL Glam. Официальная регистрация" in srt
    # 7) music bed was synthesized (no library) and 9) final mp4: H.264 1080x1920 + AAC, 3*2 - 2*0.3 = 5.4 s
    assert next((tmp_path / "work").glob("autopilot_*/music.wav")).is_file()
    out = tmp_path / "out" / state["output"]["filename"]
    info = _streams(ffmpeg, out)
    assert "h264" in info and "1080x1920" in info and "aac" in info and "Duration: 00:00:05.4" in info
    assert [d["index"] for d in state["scenes_detail"]] == [1, 2, 3] and state["scenes_detail"][1]["product"]


def test_regenerate_one_scene_reuses_everything_else(tmp_path):
    ffmpeg = _ffmpeg()
    deps = FakeDeps(ffmpeg)
    state = _run(tmp_path, deps)
    first_output = state["output"]["filename"]
    before_media, before_llm, before_tts = len(deps.media), len(deps.prompts), len(deps.tts_calls)

    state = autopilot.regenerate_scene(state["id"], 3, "static shot, female doctor, 35, white coat, waves",
                                       out_dir=tmp_path / "out", work_root=tmp_path / "work", deps=deps,
                                       background=False)
    assert state["status"] == "done", state["error"]
    new = deps.media[before_media:]
    assert [(m["kind"], m["out"]) for m in new] == [("image", "key_3_v1.png"), ("video", "scene_03_v1_try0.mp4")]
    assert len(deps.prompts) == before_llm and len(deps.tts_calls) == before_tts  # no new script, no new voice
    assert state["output"]["filename"].endswith("_v1.mp4") and state["output"]["filename"] != first_output
    assert state["scenes_detail"][2]["prompt"].endswith("waves") and state["log"][-1] == "Готово"
    assert "1080x1920" in _streams(ffmpeg, tmp_path / "out" / state["output"]["filename"])
    bad = autopilot.regenerate_scene(state["id"], 9, out_dir=tmp_path / "out", work_root=tmp_path / "work",
                                     deps=deps, background=False)
    assert bad["status"] == "failed" and bad["error"] == "Такой сцены нет."


def test_story_without_product_has_no_beautyart_rules_and_generates_every_keyframe(tmp_path):
    ffmpeg = _ffmpeg()
    deps = FakeDeps(ffmpeg)  # the board still flags scene 2 as a product: without a real photo it is generated
    state = _run(tmp_path, deps, phrase="история про кота-повара на 1 минуту")
    assert state["status"] == "done", state["error"]
    assert all("Правила карточек Beautyart" not in p for p in deps.prompts)
    assert [m["out"] for m in deps.media if m["kind"] == "image"] == ["key_1.png", "key_2.png", "key_3.png"]


def test_tts_kokoro_for_english_and_free_edge_tts_for_russian(tmp_path, monkeypatch):
    saved = []

    class Communicate:
        def __init__(self, text, voice):
            self.text, self.voice = text, voice

        async def save(self, path):
            saved.append((self.text, self.voice))
            Path(path).write_bytes(b"mp3")

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=Communicate))
    deps = autopilot.Deps()
    calls = []
    monkeypatch.setattr(deps, "fal_call", lambda model, body, cancelled: calls.append((model, body)) or
                        {"audio": {"url": "https://fal.mock/a.wav"}})
    monkeypatch.setattr(deps, "download", lambda url, out: (out.write_bytes(b"wav"), out)[1])
    assert deps.tts("Hello doctors", "en", tmp_path / "v1", lambda: False).suffix == ".wav"
    assert calls == [("fal-ai/kokoro/american-english", {"prompt": "Hello doctors", "voice": "af_heart"})]
    assert deps.tts("Привет", "ru", tmp_path / "v2", lambda: False).suffix == ".mp3"  # Kokoro has no Russian
    assert saved == [("Привет", "ru-RU-SvetlanaNeural")] and len(calls) == 1

    def fail(model, body, cancelled):
        raise cg.CloudError("fal down")
    monkeypatch.setattr(deps, "fal_call", fail)
    deps.tts("Hi", "en", tmp_path / "v3", lambda: False)
    assert saved[-1] == ("Hi", "en-US-AriaNeural")


def test_subtitle_cues_and_srt():
    cues = autopilot.subtitle_cues("раз два три четыре пять шесть семь восемь", 1.0, 4.0)
    assert cues == [(1.0, 4.0, "раз два три четыре пять шесть"), (4.0, 5.0, "семь восемь")]
    assert autopilot.to_srt(cues[:1]) == "1\n00:00:01,000 --> 00:00:04,000\nраз два три четыре пять шесть\n\n"
    assert autopilot.subtitle_cues("", 0, 3) == []


# ---------------------------------------------------------------- graph memory

def test_search_how_botox_looks():
    paths = [n["path"] for n in kb.search("как выглядит ботокс")]
    assert paths[0] == "products/categories/botulinum-toxins.md"
    assert 1 <= len(paths) <= 5
    assert "body" not in kb.search("как выглядит ботокс")[0]  # search never loads whole files


def test_search_glam_card_brings_mandatory_rules_and_product():
    paths = [n["path"] for n in kb.search("карточка Glam")]
    assert paths[0] == "products/rules/beautyart-card-rules.md" and "products/ours/zishel-glam.md" in paths
    for phrase in ("пост про MELAGENTA", "ролик с Sagitta", "Rose Lidocaine сторис"):
        found = [n["path"] for n in kb.search(phrase)]
        assert found[0] == kb.BEAUTYART_RULES and any(p.startswith("products/ours/") for p in found), phrase


def test_one_mechanism_for_the_whole_knowledge_folder():
    assert kb.search("правила промптинга")[0]["path"] == "rules.md"
    assert kb.search("/hero")[0]["path"] == "slash-commands.json#/hero"
    assert any(n["path"] == "recipes/one_prompt_film.md" for n in kb.search("одной фразой ролик сценарий"))
    assert json.loads(kb.read("slash-commands.json#/hero")["text"])["command"] == "/hero"
    assert kb.read("recipes.json#one_prompt_film")["text"].startswith("{")
    glam = kb.read("ours/zishel-glam.md")  # product-relative links resolve too
    assert glam["path"] == "products/ours/zishel-glam.md" and "НЕ для морщин" in glam["text"]


def test_read_and_ref_image_stay_inside_the_knowledge_folder():
    assert kb.ref_image("refs/ours/zishel_glam_cutout.png").name == "zishel_glam_cutout.png"
    assert kb.ref_image("products/refs/ours/zishel_glam_cutout.png").is_file()
    assert kb.product_photo("products/ours/zishel-glam.md").name == "zishel_glam_box_cropped.jpg"
    assert "/refs/ours/" in kb.product_photo("products/ours/sagitta-pdo.md").as_posix()
    for bad in ("../../app/launch.py", "products/../../../app/launch.py", "products/refs/ours/zishel_glam_cutout.png"):
        with pytest.raises(KeyError):
            kb.read(bad)
    for bad in ("../index.json", "refs/../../../app/launch.py", "INDEX.md"):
        with pytest.raises(KeyError):
            kb.ref_image(bad)


def test_system_prompt_has_graph_rule_but_not_whole_files(monkeypatch):
    monkeypatch.setattr(assistant_chat.cloud_generation, "env",
                        lambda name: {"LLM_API_KEY": "k", "LLM_BASE_URL": "https://openrouter.ai/api/v1"}.get(name, ""))
    sent = []
    monkeypatch.setattr(assistant_chat, "_post_json", lambda url, payload, key, timeout=90: sent.append(payload) or
                        {"choices": [{"message": {"role": "assistant", "content": "ok"}}]})
    assistant_chat.chat({"messages": [{"role": "user", "content": "карточка Glam"}]})
    system = sent[0]["messages"][0]["content"]
    assert "search_knowledge" in system and kb.BEAUTYART_RULES in system and "products/refs/ours/" in system
    assert "Плюсы ZISHÉL Glam" not in system and "## Золотые правила" not in system  # read on demand only
    summary = kb.summary()
    one = next(c for c in summary["categories"] if c["id"] == "one_prompt_film")
    assert one["title"] == "Одной фразой" and one["autopilot"]


def test_launch_routes_for_graph_and_regeneration():
    source = (ROOT / "app" / "launch.py").read_text(encoding="utf-8")
    for route in ('@api.get("/api/v1/assistant/knowledge/search")', '@api.get("/api/v1/assistant/knowledge/read")',
                  '@api.get("/api/v1/assistant/knowledge/ref/{path:path}")',
                  '@api.post("/api/v1/assistant/autopilot/{run_id}/scene/{index}")'):
        assert route in source
