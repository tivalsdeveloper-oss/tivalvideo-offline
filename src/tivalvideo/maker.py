"""Offline narrated-video creation."""

from __future__ import annotations

import subprocess
import tempfile
import wave
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from piper import PiperVoice, SynthesisConfig

from .tools import ToolManager

Progress = Callable[[str], None]


class VideoError(RuntimeError):
    """Raised when video creation cannot finish."""


@dataclass(frozen=True)
class VideoConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    crf: int = 22
    fade_seconds: float = 0.35
    blur: int = 40
    audio_bitrate: str = "192k"
    voice_speed: float = 0.92

    @classmethod
    def shorts(cls) -> VideoConfig:
        return cls(width=1080, height=1920)

    @classmethod
    def landscape(cls) -> VideoConfig:
        return cls(width=1920, height=1080)


class VideoMaker:
    """Turn ordered images and narration text into a polished MP4."""

    def __init__(
        self,
        config: VideoConfig | None = None,
        *,
        tools: ToolManager | None = None,
        progress: Progress = print,
    ) -> None:
        self.config = config or VideoConfig.shorts()
        self.tools = tools or ToolManager()
        self.progress = progress

    def create(
        self,
        images: Sequence[str | Path],
        narration: str,
        output: str | Path = "video.mp4",
    ) -> Path:
        paths = [Path(item).expanduser().resolve() for item in images]
        if not paths:
            raise ValueError("At least one image is required.")
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Missing image(s): {', '.join(missing)}")
        if not narration.strip():
            raise ValueError("Narration text cannot be empty.")

        if not self.tools.ready():
            self.progress("Required offline files are missing; running one-time setup.")
            self.tools.setup(self.progress)

        output_path = Path(output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="tivalvideo-") as temp_name:
            temp = Path(temp_name)
            audio = temp / "narration.wav"
            self._narrate(narration, audio)
            duration = self._wav_duration(audio)
            seconds = max(1.0, duration / len(paths))
            segments = [self._render_segment(path, temp, index, seconds) for index, path in enumerate(paths)]
            concat = temp / "segments.txt"
            concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in segments), encoding="utf-8")
            self.progress("Combining video and narration...")
            self._run(
                "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(audio),
                "-c:v", "copy", "-c:a", "aac", "-b:a", self.config.audio_bitrate,
                "-shortest", "-movflags", "+faststart", str(output_path),
            )
        self.progress(f"Created: {output_path}")
        return output_path

    def _narrate(self, text: str, output: Path) -> None:
        self.progress("Generating offline AI narration...")
        voice = PiperVoice.load(self.tools.model, self.tools.model_config)
        synthesis = SynthesisConfig(
            length_scale=self.config.voice_speed,
        )
        with wave.open(str(output), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=synthesis)

    def _render_segment(self, image: Path, temp: Path, index: int, duration: float) -> Path:
        output = temp / f"segment-{index:04d}.mp4"
        fade_out = max(0.0, duration - self.config.fade_seconds)
        foreground_width = max(2, self.config.width - 80)
        foreground_height = max(2, self.config.height - 100)
        filters = (
            f"[0:v]scale={self.config.width}:{self.config.height}:force_original_aspect_ratio=increase,"
            f"crop={self.config.width}:{self.config.height},gblur=sigma={self.config.blur}[bg];"
            f"[0:v]scale={foreground_width}:{foreground_height}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
            f"fade=t=in:st=0:d={self.config.fade_seconds},"
            f"fade=t=out:st={fade_out}:d={self.config.fade_seconds},format=yuv420p"
        )
        self.progress(f"Rendering image {index + 1}...")
        self._run(
            "-loop", "1", "-i", str(image), "-t", f"{duration:.3f}",
            "-filter_complex", filters, "-r", str(self.config.fps),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(self.config.crf),
            str(output),
        )
        return output

    def _run(self, *arguments: str) -> None:
        command = [str(self.tools.ffmpeg), "-y", "-loglevel", "error", *arguments]
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as exc:
            raise VideoError(f"FFmpeg failed with exit code {exc.returncode}.") from exc

    @staticmethod
    def _wav_duration(path: Path) -> float:
        with wave.open(str(path), "rb") as wav_file:
            return wav_file.getnframes() / float(wav_file.getframerate())


def create_video(
    images: Sequence[str | Path],
    narration: str,
    output: str | Path = "video.mp4",
    *,
    landscape: bool = False,
) -> Path:
    """Create a vertical Short or landscape video with sensible defaults."""
    config = VideoConfig.landscape() if landscape else VideoConfig.shorts()
    return VideoMaker(config).create(images, narration, output)
