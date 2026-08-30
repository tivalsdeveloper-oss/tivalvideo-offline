"""Offline narrated-video creation."""

from __future__ import annotations

import subprocess
import tempfile
import wave
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont, ImageOps
from piper import PiperVoice, SynthesisConfig

from .tools import DEFAULT_VOICE, ToolManager

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
    typing_speed: float = 12.0
    typing_fps: int = 8
    typing_hold: float = 2.0
    music_volume: float = 0.18

    @classmethod
    def shorts(cls) -> VideoConfig:
        return cls(width=1080, height=1920)

    @classmethod
    def landscape(cls) -> VideoConfig:
        return cls(width=1920, height=1080)


class VideoMaker:
    """Create MP4 videos from images, typing text, narration, and music."""

    BACKGROUNDS = ("midnight", "ocean", "sunset", "paper")

    def __init__(self, config: VideoConfig | None = None, *,
                 tools: ToolManager | None = None, progress: Progress = print) -> None:
        self.config = config or VideoConfig.shorts()
        self.tools = tools or ToolManager()
        self.progress = progress

    def create(
        self,
        images: Sequence[str | Path] | None = None,
        narration: str | None = None,
        output: str | Path = "video.mp4",
        *,
        audio: str | Path | None = None,
        music: str | Path | None = None,
        typing_text: str | None = None,
        background: str = "midnight",
        background_image: str | Path | None = None,
        voice: str = DEFAULT_VOICE,
    ) -> Path:
        paths = self._existing_files(images or (), "image")
        audio_path = self._optional_file(audio, "audio")
        music_path = self._optional_file(music, "music")
        background_path = self._optional_file(background_image, "background image")
        if not paths and not typing_text:
            raise ValueError("Add at least one image or typing_text.")
        if narration and audio_path:
            raise ValueError("Use narration or audio, not both.")
        if background not in self.BACKGROUNDS:
            choices = ", ".join(self.BACKGROUNDS)
            raise ValueError(f"Unknown background '{background}'. Choose: {choices}.")
        self.tools.select_voice(voice)
        if narration and narration.strip() and not self.tools.ready(voice):
            self.progress("Required offline voice is missing; running one-time setup.")
            self.tools.setup(self.progress, voice=voice)

        output_path = Path(output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="tivalvideo-") as temp_name:
            temp = Path(temp_name)
            voice_audio = self._prepare_voice(narration, audio_path, temp, voice)
            main_duration = self._wav_duration(voice_audio) if voice_audio else None
            music_duration = self._media_duration(music_path, temp) if music_path else None
            target_duration = main_duration or music_duration
            item_count = len(paths) + bool(typing_text)
            seconds = max(1.0, (target_duration or item_count * 3.0) / item_count)
            segments: list[Path] = []
            if typing_text:
                typing_duration = max(
                    seconds,
                    len(typing_text) / self.config.typing_speed + self.config.typing_hold,
                )
                segments.append(self._render_typing(
                    typing_text, temp, typing_duration, background, background_path
                ))
            segments.extend(
                self._render_segment(path, temp, index, seconds)
                for index, path in enumerate(paths)
            )
            silent_video = self._concat_segments(segments, temp)
            self._add_audio(silent_video, voice_audio, music_path, output_path)
        self.progress(f"Created: {output_path}")
        return output_path

    def _prepare_voice(self, narration: str | None, audio: Path | None,
                       temp: Path, voice: str) -> Path | None:
        if narration and narration.strip():
            output = temp / "narration.wav"
            self._narrate(narration, output, voice)
            return output
        if audio:
            output = temp / "custom-audio.wav"
            self.progress("Preparing custom audio...")
            self._run("-i", str(audio), "-vn", "-ac", "2", "-ar", "44100", str(output))
            return output
        return None

    def _narrate(self, text: str, output: Path, voice: str = DEFAULT_VOICE) -> None:
        self.progress(f"Generating offline AI narration with {voice}...")
        narrator = PiperVoice.load(self.tools.model_path(voice), self.tools.config_path(voice))
        synthesis = SynthesisConfig(length_scale=self.config.voice_speed)
        with wave.open(str(output), "wb") as wav_file:
            narrator.synthesize_wav(text, wav_file, syn_config=synthesis)

    def _render_typing(self, text: str, temp: Path, duration: float,
                       background: str, background_image: Path | None) -> Path:
        self.progress("Rendering auto-typing text...")
        frames = temp / "typing-frames"
        frames.mkdir()
        base = self._background_canvas(background, background_image)
        font = self._font(max(30, self.config.width // 18))
        total = max(1, round(duration * self.config.typing_fps))
        typing = max(1, total - round(self.config.typing_hold * self.config.typing_fps))
        for number in range(total):
            count = min(len(text), round(len(text) * (number + 1) / typing))
            frame = base.copy()
            draw = ImageDraw.Draw(frame)
            shown = self._wrap_text(text[:count], font, self.config.width - 140)
            bbox = draw.multiline_textbbox((0, 0), shown, font=font, spacing=18, align="center")
            x = (self.config.width - (bbox[2] - bbox[0])) / 2
            y = (self.config.height - (bbox[3] - bbox[1])) / 2
            draw.multiline_text(
                (x + 4, y + 4), shown, font=font, fill=(0, 0, 0), spacing=18, align="center"
            )
            draw.multiline_text(
                (x, y), shown, font=font,
                fill=self._text_color(background, background_image), spacing=18, align="center"
            )
            frame.save(frames / f"frame-{number:06d}.png", optimize=True)
        output = temp / "typing.mp4"
        self._run(
            "-framerate", str(self.config.typing_fps), "-i", str(frames / "frame-%06d.png"),
            "-r", str(self.config.fps), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", str(self.config.crf), "-pix_fmt", "yuv420p", str(output),
        )
        return output

    def _background_canvas(self, style: str, image: Path | None) -> Image.Image:
        size = (self.config.width, self.config.height)
        if image:
            with Image.open(image) as source:
                return ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)
        colors = {
            "midnight": ((8, 18, 45), (52, 27, 92)),
            "ocean": ((4, 82, 130), (20, 170, 180)),
            "sunset": ((73, 22, 91), (247, 126, 70)),
            "paper": ((255, 253, 242), (235, 229, 208)),
        }
        start, end = colors[style]
        canvas = Image.new("RGB", size)
        draw = ImageDraw.Draw(canvas)
        for y in range(self.config.height):
            ratio = y / max(1, self.config.height - 1)
            color = tuple(round(a + (b - a) * ratio) for a, b in zip(start, end))
            draw.line((0, y, self.config.width, y), fill=color)
        return canvas

    def _render_segment(self, image: Path, temp: Path, index: int, duration: float) -> Path:
        output = temp / f"segment-{index:04d}.mp4"
        fade_out = max(0.0, duration - self.config.fade_seconds)
        foreground_width = max(2, self.config.width - 80)
        foreground_height = max(2, self.config.height - 100)
        filters = (
            f"[0:v]scale={self.config.width}:{self.config.height}:force_original_aspect_ratio=increase,"
            f"crop={self.config.width}:{self.config.height},gblur=sigma={self.config.blur}[bg];"
            f"[0:v]scale={foreground_width}:{foreground_height}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fade=t=in:st=0:d={self.config.fade_seconds},"
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

    def _concat_segments(self, segments: Sequence[Path], temp: Path) -> Path:
        concat = temp / "segments.txt"
        concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
        output = temp / "silent.mp4"
        self.progress("Combining video scenes...")
        self._run("-f", "concat", "-safe", "0", "-i", str(concat), "-c:v", "copy", str(output))
        return output

    def _add_audio(self, video: Path, voice: Path | None,
                   music: Path | None, output: Path) -> None:
        self.progress("Adding audio...")
        if voice and music:
            self._run(
                "-i", str(video), "-i", str(voice), "-stream_loop", "-1", "-i", str(music),
                "-filter_complex",
                f"[2:a]volume={self.config.music_volume}[music];"
                "[1:a][music]amix=inputs=2:duration=first[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                "-b:a", self.config.audio_bitrate, "-shortest", "-movflags", "+faststart", str(output),
            )
        elif voice or music:
            source = voice or music
            self._run(
                "-i", str(video), "-i", str(source), "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", self.config.audio_bitrate,
                "-shortest", "-movflags", "+faststart", str(output),
            )
        else:
            self._run("-i", str(video), "-c", "copy", "-movflags", "+faststart", str(output))

    def _media_duration(self, source: Path, temp: Path) -> float:
        converted = temp / f"duration-{source.stem}.wav"
        self._run("-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(converted))
        return self._wav_duration(converted)

    def _run(self, *arguments: str) -> None:
        command = [str(self.tools.ffmpeg), "-y", "-loglevel", "error", *arguments]
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as exc:
            raise VideoError(f"FFmpeg failed with exit code {exc.returncode}.") from exc

    @staticmethod
    def _existing_files(items: Sequence[str | Path], label: str) -> list[Path]:
        paths = [Path(item).expanduser().resolve() for item in items]
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Missing {label}(s): {', '.join(missing)}")
        return paths

    @staticmethod
    def _optional_file(item: str | Path | None, label: str) -> Path | None:
        if item is None:
            return None
        path = Path(item).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Missing {label}: {path}")
        return path

    @staticmethod
    def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()

    @staticmethod
    def _wrap_text(text: str, font: ImageFont.ImageFont, width: int) -> str:
        lines: list[str] = []
        for paragraph in text.splitlines() or [""]:
            current = ""
            for word in paragraph.split(" "):
                candidate = f"{current} {word}".strip()
                if current and font.getlength(candidate) > width:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            lines.append(current)
        return "\n".join(lines)

    @staticmethod
    def _text_color(style: str, custom: Path | None) -> tuple[int, int, int]:
        return (32, 37, 50) if style == "paper" and not custom else (255, 255, 255)

    @staticmethod
    def _wav_duration(path: Path) -> float:
        with wave.open(str(path), "rb") as wav_file:
            return wav_file.getnframes() / float(wav_file.getframerate())


def create_video(
    images: Sequence[str | Path] | None = None,
    narration: str | None = None,
    output: str | Path = "video.mp4",
    *,
    landscape: bool = False,
    audio: str | Path | None = None,
    music: str | Path | None = None,
    typing_text: str | None = None,
    background: str = "midnight",
    background_image: str | Path | None = None,
    voice: str = DEFAULT_VOICE,
) -> Path:
    """Create a vertical Short or landscape video with sensible defaults."""
    config = VideoConfig.landscape() if landscape else VideoConfig.shorts()
    return VideoMaker(config).create(
        images, narration, output, audio=audio, music=music, typing_text=typing_text,
        background=background, background_image=background_image, voice=voice,
    )
