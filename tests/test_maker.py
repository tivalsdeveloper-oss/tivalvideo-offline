from pathlib import Path
from unittest.mock import patch

import pytest

from tivalvideo import ToolManager, VideoConfig, VideoError, VideoMaker


def test_presets():
    assert (VideoConfig.shorts().width, VideoConfig.shorts().height) == (1080, 1920)
    assert (VideoConfig.landscape().width, VideoConfig.landscape().height) == (1920, 1080)


def test_requires_images():
    with pytest.raises(ValueError, match="At least one image"):
        VideoMaker().create([], "hello")


def test_rejects_missing_image(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        VideoMaker().create([tmp_path / "missing.png"], "hello")


def test_tool_paths(tmp_path: Path):
    tools = ToolManager(tmp_path)
    assert tools.model.name == "en_US-lessac-medium.onnx"
    assert tools.model_config.name.endswith(".onnx.json")


def test_ffmpeg_error_becomes_video_error(tmp_path: Path):
    maker = VideoMaker(tools=ToolManager(tmp_path))
    with (
        patch("subprocess.run", side_effect=__import__("subprocess").CalledProcessError(2, [])),
        pytest.raises(VideoError, match="FFmpeg failed"),
    ):
        maker._run("-version")
