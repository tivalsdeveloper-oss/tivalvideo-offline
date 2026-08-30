"""Automatic FFmpeg and Piper narrator-voice management."""

from __future__ import annotations

import hashlib
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import imageio_ffmpeg
from platformdirs import user_data_dir

Progress = Callable[[str], None]
VOICE_ROOT = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
DEFAULT_VOICE = "en_US-lessac-medium"


@dataclass(frozen=True)
class VoiceSpec:
    """A downloadable Piper narrator voice."""

    key: str
    name: str
    language: str
    accent: str
    quality: str = "medium"

    @property
    def filename(self) -> str:
        return f"{self.key}.onnx"

    @property
    def base_url(self) -> str:
        family = self.language.split("_")[0]
        return f"{VOICE_ROOT}/{family}/{self.language}/{self.name}/{self.quality}"

    @property
    def model_url(self) -> str:
        return f"{self.base_url}/{self.filename}"

    @property
    def config_url(self) -> str:
        return f"{self.model_url}.json"


VOICE_CATALOG: dict[str, VoiceSpec] = {
    "en_US-lessac-medium": VoiceSpec(
        "en_US-lessac-medium", "lessac", "en_US", "American English"
    ),
    "en_US-amy-medium": VoiceSpec(
        "en_US-amy-medium", "amy", "en_US", "American English"
    ),
    "en_US-joe-medium": VoiceSpec(
        "en_US-joe-medium", "joe", "en_US", "American English"
    ),
    "en_GB-alan-medium": VoiceSpec(
        "en_GB-alan-medium", "alan", "en_GB", "British English"
    ),
}


class ToolManager:
    """Locate FFmpeg and manage locally cached Piper narrator voices."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        voice: str = DEFAULT_VOICE,
    ) -> None:
        self.data_dir = Path(data_dir or user_data_dir("tivalvideo", "tivalsdeveloper"))
        self.selected_voice = self.validate_voice(voice)

    @property
    def ffmpeg(self) -> Path:
        """Return imageio-ffmpeg's managed executable."""
        return Path(imageio_ffmpeg.get_ffmpeg_exe())

    @property
    def voice_dir(self) -> Path:
        return self.data_dir / "voices" / self.selected_voice

    @property
    def model(self) -> Path:
        return self.model_path(self.selected_voice)

    @property
    def model_config(self) -> Path:
        return self.config_path(self.selected_voice)

    @staticmethod
    def validate_voice(voice: str) -> str:
        if voice not in VOICE_CATALOG:
            choices = ", ".join(VOICE_CATALOG)
            raise ValueError(f"Unknown voice '{voice}'. Choose: {choices}.")
        return voice

    def select_voice(self, voice: str) -> VoiceSpec:
        """Select the narrator used by model and model_config properties."""
        self.selected_voice = self.validate_voice(voice)
        return VOICE_CATALOG[self.selected_voice]

    def model_path(self, voice: str = DEFAULT_VOICE) -> Path:
        key = self.validate_voice(voice)
        return self.data_dir / "voices" / key / f"{key}.onnx"

    def config_path(self, voice: str = DEFAULT_VOICE) -> Path:
        return self.model_path(voice).with_suffix(".onnx.json")

    def ready(self, voice: str | None = None) -> bool:
        key = self.validate_voice(voice or self.selected_voice)
        model = self.model_path(key)
        config = self.config_path(key)
        return (
            self.ffmpeg.is_file()
            and model.exists()
            and model.stat().st_size > 1_000_000
            and config.exists()
            and config.stat().st_size > 1000
        )

    def voices(self) -> tuple[VoiceSpec, ...]:
        """Return all narrator voices included in the catalogue."""
        return tuple(VOICE_CATALOG.values())

    def installed_voices(self) -> tuple[str, ...]:
        """Return narrator keys that are ready for offline use."""
        return tuple(key for key in VOICE_CATALOG if self.ready(key))

    def install_voice(
        self,
        voice: str = DEFAULT_VOICE,
        progress: Progress = print,
        force: bool = False,
    ) -> dict[str, Path]:
        """Download one narrator voice for offline use."""
        key = self.validate_voice(voice)
        spec = VOICE_CATALOG[key]
        directory = self.model_path(key).parent
        directory.mkdir(parents=True, exist_ok=True)
        progress(f"Installing narrator: {key} ({spec.accent})")
        self._download(spec.model_url, self.model_path(key), progress, force)
        self._download(spec.config_url, self.config_path(key), progress, force)
        progress(f"Narrator ready for offline use: {key}")
        return {"voice": self.model_path(key), "voice_config": self.config_path(key)}

    def remove_voice(self, voice: str) -> bool:
        """Remove a downloaded narrator voice. Returns False if it was absent."""
        key = self.validate_voice(voice)
        directory = self.model_path(key).parent
        if not directory.exists():
            return False
        shutil.rmtree(directory)
        return True

    def setup(
        self,
        progress: Progress = print,
        force: bool = False,
        voice: str | None = None,
    ) -> dict[str, Path]:
        """Prepare FFmpeg and the selected narrator voice."""
        key = self.validate_voice(voice or self.selected_voice)
        progress(f"FFmpeg ready: {self.ffmpeg}")
        files = self.install_voice(key, progress, force)
        progress("TivalVideo is ready for offline use.")
        return {"ffmpeg": self.ffmpeg, **files}

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

    def fingerprint(self, voice: str | None = None) -> str:
        """Return a short fingerprint for an installed voice model."""
        model = self.model_path(voice or self.selected_voice)
        if not model.exists():
            return "not-installed"
        digest = hashlib.sha256()
        with model.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()[:16]
