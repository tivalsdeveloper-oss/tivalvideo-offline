"""Automatic tool and voice-model management."""

from __future__ import annotations

import hashlib
import shutil
import urllib.request
from pathlib import Path
from typing import Callable

import imageio_ffmpeg
from platformdirs import user_data_dir

VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
MODEL_URL = f"{VOICE_BASE}/en_US-lessac-medium.onnx"
CONFIG_URL = f"{VOICE_BASE}/en_US-lessac-medium.onnx.json"

Progress = Callable[[str], None]


class ToolManager:
    """Locate FFmpeg and cache the Piper voice required for offline use."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir or user_data_dir("tivalvideo", "tivalsdeveloper"))
        self.voice_dir = self.data_dir / "voices" / "en_US-lessac-medium"

    @property
    def ffmpeg(self) -> Path:
        """Return imageio-ffmpeg's managed executable."""
        return Path(imageio_ffmpeg.get_ffmpeg_exe())

    @property
    def model(self) -> Path:
        return self.voice_dir / "en_US-lessac-medium.onnx"

    @property
    def model_config(self) -> Path:
        return self.voice_dir / "en_US-lessac-medium.onnx.json"

    def ready(self) -> bool:
        return self.ffmpeg.is_file() and self.model.stat().st_size > 1_000_000 if self.model.exists() else False

    def setup(self, progress: Progress = print, force: bool = False) -> dict[str, Path]:
        """Download missing voice files. Pip installs FFmpeg and Piper automatically."""
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        progress(f"FFmpeg ready: {self.ffmpeg}")
        self._download(MODEL_URL, self.model, progress, force)
        self._download(CONFIG_URL, self.model_config, progress, force)
        progress("TivalVideo is ready for offline use.")
        return {"ffmpeg": self.ffmpeg, "voice": self.model, "voice_config": self.model_config}

    @staticmethod
    def _download(url: str, destination: Path, progress: Progress, force: bool) -> None:
        if destination.exists() and destination.stat().st_size > 1000 and not force:
            progress(f"Using cached file: {destination.name}")
            return
        temp = destination.with_suffix(destination.suffix + ".part")
        progress(f"Downloading {destination.name}...")
        try:
            with urllib.request.urlopen(url, timeout=60) as response, temp.open("wb") as output:
                shutil.copyfileobj(response, output)
            temp.replace(destination)
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    def fingerprint(self) -> str:
        """Return a short fingerprint for the cached model."""
        if not self.model.exists():
            return "not-installed"
        digest = hashlib.sha256()
        with self.model.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()[:16]

