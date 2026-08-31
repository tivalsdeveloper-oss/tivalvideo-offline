from pathlib import Path
from unittest.mock import patch

import pytest

from tivalvideo import (
    DEFAULT_VOICE,
    VOICE_CATALOG,
    ToolManager,
    VideoConfig,
    VideoError,
    VideoMaker,
    add_narration,
)


def test_presets():
    assert (VideoConfig.shorts().width, VideoConfig.shorts().height) == (1080, 1920)
    assert (VideoConfig.landscape().width, VideoConfig.landscape().height) == (1920, 1080)


def test_requires_visual_content():
    with pytest.raises(ValueError, match="at least one image or typing_text"):
        VideoMaker().create([], "hello")


def test_rejects_missing_image(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        VideoMaker().create([tmp_path / "missing.png"], "hello")


def test_tool_paths(tmp_path: Path):
    tools = ToolManager(tmp_path)
    assert tools.model.name == "en_US-lessac-medium.onnx"
    assert tools.model_config.name.endswith(".onnx.json")


def test_voice_catalog_and_selection(tmp_path: Path):
    tools = ToolManager(tmp_path)
    assert tools.selected_voice == DEFAULT_VOICE
    assert "en_US-amy-medium" in VOICE_CATALOG
    tools.select_voice("en_GB-alan-medium")
    assert tools.model.name == "en_GB-alan-medium.onnx"
    assert "/en/en_GB/alan/medium/" in VOICE_CATALOG["en_GB-alan-medium"].model_url


def test_unknown_voice_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="Unknown voice"):
        ToolManager(tmp_path, voice="robot")


def test_remove_voice(tmp_path: Path):
    tools = ToolManager(tmp_path)
    tools.voice_dir.mkdir(parents=True)
    tools.model.write_bytes(b"voice")
    assert tools.remove_voice(DEFAULT_VOICE)
    assert not tools.voice_dir.exists()
    assert not tools.remove_voice(DEFAULT_VOICE)


def test_ffmpeg_error_becomes_video_error(tmp_path: Path):
    maker = VideoMaker(tools=ToolManager(tmp_path))
    with (
        patch("subprocess.run", side_effect=__import__("subprocess").CalledProcessError(2, [])),
        pytest.raises(VideoError, match="FFmpeg failed"),
    ):
        maker._run("-version")


def test_rejects_narration_and_audio(tmp_path: Path):
    image = tmp_path / "image.png"
    audio = tmp_path / "voice.wav"
    image.touch()
    audio.touch()
    with pytest.raises(ValueError, match="narration or audio"):
        VideoMaker().create([image], "hello", audio=audio)


def test_rejects_unknown_background():
    with pytest.raises(ValueError, match="Unknown background"):
        VideoMaker().create(typing_text="hello", background="space")


def test_built_in_background(tmp_path: Path):
    config = VideoConfig(width=64, height=96)
    canvas = VideoMaker(config)._background_canvas("ocean", None)
    assert canvas.size == (64, 96)


def test_custom_background_is_cropped(tmp_path: Path):
    from PIL import Image

    source = tmp_path / "background.png"
    Image.new("RGB", (20, 20), "red").save(source)
    config = VideoConfig(width=64, height=96)
    canvas = VideoMaker(config)._background_canvas("midnight", source)
    assert canvas.size == (64, 96)


def test_add_narration_requires_audio_source(tmp_path: Path):
    video = tmp_path / "screen.mp4"
    video.touch()
    with pytest.raises(ValueError, match="narration text or an audio file"):
        VideoMaker().add_narration(video)


def test_add_narration_rejects_two_audio_sources(tmp_path: Path):
    video = tmp_path / "screen.mp4"
    audio = tmp_path / "voice.wav"
    video.touch()
    audio.touch()
    with pytest.raises(ValueError, match="narration or audio"):
        VideoMaker().add_narration(video, "hello", audio=audio)


@pytest.mark.parametrize("mode", ["loud", "", "remove"])
def test_add_narration_rejects_unknown_mode(tmp_path: Path, mode: str):
    video = tmp_path / "screen.mp4"
    audio = tmp_path / "voice.wav"
    video.touch()
    audio.touch()
    with pytest.raises(ValueError, match="replace, mix, or duck"):
        VideoMaker().add_narration(video, audio=audio, original_audio=mode)


def test_add_narration_rejects_invalid_volume(tmp_path: Path):
    video = tmp_path / "screen.mp4"
    audio = tmp_path / "voice.wav"
    video.touch()
    audio.touch()
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        VideoMaker().add_narration(video, audio=audio, original_volume=1.1)


def test_public_add_narration_delegates():
    with patch("tivalvideo.maker.VideoMaker.add_narration", return_value=Path("done.mp4")) as call:
        result = add_narration("screen.mp4", audio="voice.mp3", original_audio="mix")
    assert result == Path("done.mp4")
    assert call.call_args.kwargs["original_audio"] == "mix"
