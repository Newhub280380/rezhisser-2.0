"""Cloud engine: request mapping, provider bodies, .env settings (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from services import cloud_generation as cg  # noqa: E402


def test_request_from_params_video_and_image(tmp_path, monkeypatch):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"\x89PNG")
    video = cg.request_from_params(
        {"prompt": " neon ", "resolution": "720x1280", "video_length": 121, "image_start": [str(ref)]},
        {"fps": 24}, tmp_path)
    assert video == {"kind": "video", "prompt": "neon", "image": ref, "image_end": None, "width": 720, "height": 1280,
                     "ratio": "9:16", "resolution": "768P", "duration": 5}
    image = cg.request_from_params({"prompt": "p", "resolution": "1920x1080", "image_mode": 1}, {}, tmp_path)
    assert (image["kind"], image["ratio"], image["resolution"], image["image"]) == ("image", "16:9", "2K", None)


def test_provider_routes(tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"x")
    t2v = {"kind": "video", "prompt": "p", "image": None, "width": 1280, "height": 720,
           "ratio": "16:9", "resolution": "768P", "duration": 6}
    i2v = dict(t2v, image=ref)
    img = dict(t2v, kind="image")
    body = cg.MiniMax().video_body(t2v)
    assert body["model"] == "MiniMax-H3" and body["ratio"] == "16:9" and body["duration"] == 6
    assert cg.MiniMax().video_body(i2v)["content"][1]["role"] == "first_frame"
    path, body = cg.MiniMax().image_body(img)
    assert (path, body["model"], body["aspect_ratio"]) == ("/v1/images/generations", "MiniMax-H3-Image", "16:9")
    path, body = cg.MiniMax().image_body(dict(img, image=ref))
    assert path == "/v1/images/edits" and body["images"][0]["image_url"].startswith("data:image/png;base64,")
    assert cg.Fal().endpoint_and_body(t2v)[0] == "minimax/h3/text-to-video"
    assert cg.Fal().endpoint_and_body(i2v)[0] == "minimax/h3/image-to-video"
    assert cg.Fal().endpoint_and_body(img)[0] == "fal-ai/moss-image"
    assert cg.MuApi().slug_and_body(i2v)[0] == "minimax-h3-image-to-video"
    assert cg.MuApi().slug_and_body(img)[0] == "minimax-h3-image"
    slug, body = cg.MuApi().slug_and_body(dict(img, image=ref))
    assert slug == "qwen2-1-image-to-image" and len(body["images_list"]) == 1


def test_env_settings_and_llm_override(tmp_path, monkeypatch):
    for key in (*cg.SECRET_KEYS, *cg.PLAIN_KEYS):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text("# keep\nOTHER=1\nFAL_KEY=\n", encoding="utf-8")
    assert cg.active_provider() is None and cg.llm_override() is None
    cg.save_env({"FAL_KEY": "k", "CLOUD_PROVIDER": "fal", "LLM_BASE_URL": "https://x/v1",
                 "LLM_API_KEY": "s", "EVIL": "no"}, path)
    text = path.read_text(encoding="utf-8")
    assert "# keep" in text and "OTHER=1" in text and "FAL_KEY=k" in text and "EVIL" not in text
    assert cg.active_provider() == "fal" and cg.ready("fal") and not cg.ready("minimax")
    assert cg.llm_override()["remote_url"] == "https://x"
    assert cg.public_config()["keys"] == {"MINIMAX_API_KEY": False, "FAL_KEY": True,
                                          "MUAPI_API_KEY": False, "LLM_API_KEY": True}


def test_last_frame_and_unsupported_modes(tmp_path):
    first, last = tmp_path / "a.png", tmp_path / "b.png"
    first.write_bytes(b"a")
    last.write_bytes(b"b")
    req = cg.request_from_params({"prompt": "p", "image_start": str(first), "image_end": str(last),
                                  "video_length": 120}, {}, tmp_path)
    assert req["image_end"] == last
    roles = [c.get("role") for c in cg.MiniMax().video_body(req)["content"]]
    assert roles == [None, "first_frame", "last_frame"] and "ratio" not in cg.MiniMax().video_body(req)
    assert "end_image_url" in cg.Fal().endpoint_and_body(req)[1]
    assert "last_image_url" in cg.MuApi().slug_and_body(req)[1]
    assert cg.unsupported_reason({"prompt": "p", "image_start": "x"}, {}) is None
    assert cg.unsupported_reason({"video_guide": "v.mp4"}, {}) == "source video"
    assert cg.unsupported_reason({"edit_outpaint_shot_aware": True}, {}) == "outpaint"
    assert cg.unsupported_reason({}, {"audio_only": True}) == "audio generation"


def test_execute_rejects_unsupported_job(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "k")
    job = {"id": "j1", "out_dir": str(tmp_path), "params": {"prompt": "p", "image_mask": "m.png"}}
    try:
        cg.execute(job, "fal", {})
    except cg.CloudError as error:
        assert "mask" in str(error)
    else:
        raise AssertionError("mask job must not reach the cloud")
