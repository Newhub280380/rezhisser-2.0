"""Freefield apps: catalog, validation, payloads checked against fal's published OpenAPI schemas (saved
2026-11-14 in fixtures), dry-run and a run with a mocked fal client. Nothing is sent to fal here."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from services import freefield_apps as ff  # noqa: E402

SCHEMAS = Path(__file__).resolve().parent / "fixtures" / "freefield_fal_schemas"
FILES = {"image": "a.png", "video": "a.mp4", "audio": "a.wav"}
PRIORITY = {"recast", "motion", "dub", "speak", "talking", "upscale-video"}


@pytest.fixture()
def uploads(tmp_path):
    for name in FILES.values():
        (tmp_path / name).write_bytes(b"x" * 64)
    return tmp_path


def _values(app):
    values = {}
    for spec in app["inputs"]:
        if spec["type"] in FILES:
            values[spec["id"]] = FILES[spec["type"]]
        elif spec["required"] and "default" not in spec:
            values[spec["id"]] = "test text"
    return values


def _input_schema(endpoint):
    doc = json.loads((SCHEMAS / (endpoint.replace("/", "_") + ".json")).read_text(encoding="utf-8"))
    comps = doc["components"]["schemas"]
    post = next(p["post"] for p in doc["paths"].values() if "post" in p)
    ref = post["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    return comps[ref], comps


def _enum(prop, comps):
    if prop.get("enum"):
        return prop["enum"]
    if prop.get("allOf"):
        return comps.get(prop["allOf"][0].get("$ref", "").split("/")[-1], {}).get("enum")
    return None


def test_catalog_has_priority_apps_and_no_dead_entries():
    apps = {a["id"]: a for a in ff.catalog()["apps"]}
    assert PRIORITY <= set(apps)
    for app in apps.values():
        assert "build" not in app
        if app["status"] == "ready":
            assert (app["endpoint"] or app["free"]) and app["price"] and app["inputs"], app["id"]
        else:
            assert app["status"] == "soon" and app["needs"] and not app["endpoint"], app["id"]
    assert apps["dub"]["status"] == "soon" and apps["dub-cloud"]["status"] == "ready"


@pytest.mark.parametrize("app", [a for a in ff.APPS if a["status"] == "ready" and not a["free"]], ids=lambda a: a["id"])
def test_payload_matches_fal_schema_for_every_option(app, uploads):
    schema, comps = _input_schema(app["endpoint"])
    props, required = schema["properties"], schema.get("required", [])
    clean = ff.validate(app["id"], _values(app), lambda n: uploads / n)
    variants = [clean]
    for spec in app["inputs"]:
        if spec["type"] == "select":
            variants += [{**clean, spec["id"]: option} for option in spec["options"]]
    for values in variants:
        endpoint, body = ff.build_request(app["id"], values, lambda p: f"https://files/{p.name}")
        assert endpoint == app["endpoint"]
        assert not set(required) - set(body), (app["id"], required)
        for key, value in body.items():
            assert key in props, (app["id"], key)
            allowed = _enum(props[key], comps)
            if allowed:
                assert value in allowed, (app["id"], key, value)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if props[key].get("minimum") is not None:
                    assert value >= props[key]["minimum"], (app["id"], key)
                if props[key].get("maximum") is not None:
                    assert value <= props[key]["maximum"], (app["id"], key)


def test_validation_messages(uploads):
    with pytest.raises(ff.AppError, match="Заполните"):
        ff.validate("recast", {"character": "a.png"}, lambda n: uploads / n)
    with pytest.raises(ff.AppError, match="недопустимое"):
        ff.validate("recast", {"clip": "a.mp4", "character": "a.png", "resolution": "4k"}, lambda n: uploads / n)
    with pytest.raises(ff.AppError, match="скоро"):
        ff.validate("dub", {}, lambda n: uploads / n)
    big = uploads / "big.mp4"
    with open(big, "wb") as fh:
        fh.truncate((ff.MAX_VIDEO_MB + 1) * 1024 * 1024)
    with pytest.raises(ff.AppError, match="больше"):
        ff.validate("upscale-video", {"clip": "big.mp4"}, lambda n: uploads / n)


def test_dry_run_builds_without_reading_files(uploads):
    plan = ff.dry_run("speak", {"image": "a.png", "line": "Привет!"}, lambda n: uploads / n)
    assert plan["submitted"] is False
    assert plan["url"] == "https://queue.fal.run/lightricks/ltx-2.5/image-to-video/fast"
    assert plan["body"]["generate_audio"] is True and "Привет!" in plan["body"]["prompt"]
    assert plan["body"]["image_url"].startswith("<файл a.png")


def test_run_with_mocked_fal_client(uploads, tmp_path):
    calls = []

    class FakeFal:
        def call(self, model, body, cancelled=lambda: False):
            calls.append((model, body))
            return {"video": {"url": "https://v3.fal.media/files/out.mp4"}}

    saved = []
    state = ff.start_run("upscale-video", {"clip": "a.mp4", "target": "2160p"}, resolve_file=lambda n: uploads / n,
                         file_to_url=lambda p: "data:video/mp4;base64,AAA", client=FakeFal(), out_dir=tmp_path,
                         download=lambda url, out: saved.append((url, out)), url_for=lambda n: f"/api/v1/file/{n}",
                         background=False)
    assert calls == [("fal-ai/seedvr/upscale/video", {"video_url": "data:video/mp4;base64,AAA",
                                                      "output_format": "X264 (.mp4)", "output_quality": "high",
                                                      "upscale_mode": "target", "target_resolution": "2160p"})]
    assert state["status"] == "done" and state["output"]["url"].startswith("/api/v1/file/")
    assert saved and saved[0][0].endswith("out.mp4")


def test_run_failure_is_reported(uploads, tmp_path):
    class Broken:
        def call(self, model, body, cancelled=lambda: False):
            return {"nothing": 1}

    state = ff.start_run("remove-bg", {"image": "a.png"}, resolve_file=lambda n: uploads / n,
                         file_to_url=lambda p: "u", client=Broken(), out_dir=tmp_path, download=lambda *a: None,
                         url_for=str, background=False)
    assert state["status"] == "failed" and "нет ссылки" in state["error"]


@pytest.mark.parametrize("result,kind,url", [
    ({"images": [{"url": "i"}]}, "image", "i"), ({"image": {"url": "j"}}, "image", "j"),
    ({"audio": {"url": "a"}}, "audio", "a"), ({"audio": "s"}, "audio", "s"), ({"video": {"url": "v"}}, "video", "v"),
])
def test_output_url(result, kind, url):
    assert ff.output_url(result, kind) == url


def test_local_face_detect_runs_free_without_fal(tmp_path):
    from PIL import Image
    Image.new("RGB", (320, 240), (13, 15, 16)).save(tmp_path / "blank.png")
    plan = ff.dry_run("face-detect", {"image": "blank.png"}, lambda n: tmp_path / n)
    assert plan["free"] and plan["endpoint"] == "local" and plan["url"] is None
    run = ff.start_run("face-detect", {"image": "blank.png"}, resolve_file=lambda n: tmp_path / n, file_to_url=None,
                       client=None, out_dir=tmp_path, download=None, url_for=lambda n: n, background=False)
    assert run["status"] == "done" and run["output"]["kind"] == "image", run
    assert (tmp_path / run["output"]["filename"]).is_file() and run["output"]["text"].startswith("Найдено лиц: 0")


def test_prompt_prep_uses_only_the_free_model(tmp_path, monkeypatch):
    sent = []

    class Reply:
        def __init__(self, text):
            self.text = text

        def read(self):
            return json.dumps({"choices": [{"message": {"content": self.text}}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        sent.append(json.loads(req.data))
        return Reply("" if len(sent) == 1 else "A slow push-in over black silk.")

    monkeypatch.setattr(ff.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(ff, "ENV", {"LLM_API_KEY": "k"}.get)
    run = ff.start_run("prompt-prep", {"idea": "чёрный шёлк"}, resolve_file=None, file_to_url=None, client=None,
                       out_dir=tmp_path, download=None, url_for=lambda n: n, background=False)
    assert run["status"] == "done" and run["output"]["text"] == "A slow push-in over black silk."
    assert [b["model"] for b in sent] == [ff.FREE_LLM, ff.FREE_LLM]  # empty first answer -> retry, never a paid model


def test_relight_prompt_keeps_the_person():
    clean = {"image": Path("a.png"), "direction": "Сзади (контровой)", "tone": "Тёплый", "hard": True,
             "details": "", "steps": 4, "seed": -1}
    endpoint, body = ff.build_request("relight", clean, lambda p: "u")
    assert endpoint == "fal-ai/flux-2/klein/9b/edit" and body["image_urls"] == ["u"]
    assert "rim light" in body["prompt"] and "hard" in body["prompt"] and "exactly the same" in body["prompt"]
