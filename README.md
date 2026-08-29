# TivalVideo Offline

Create narrated vertical Shorts or landscape videos from images, entirely offline after the first setup. TivalVideo uses a managed FFmpeg executable for video rendering and Piper for local AI narration.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

`pip` automatically installs FFmpeg and Piper dependencies. The first video automatically downloads the approximately 61 MB Piper voice model, or you can prepare it explicitly:

```bash
tivalvideo setup
```

After setup, disconnect from the internet and create videos offline.

## Python example

```python
from tivalvideo import create_video

create_video(
    images=["lesson1.png", "lesson2.png", "lesson3.png"],
    narration="Learn TivalTube with these simple examples.",
    output="tivaltube-short.mp4",
)
```

## Terminal example

Create `narration.txt`, then run:

```bash
tivalvideo create \
  lesson1.png lesson2.png lesson3.png \
  --narration narration.txt \
  --output short.mp4
```

Use `--landscape` for a 1920×1080 video:

```bash
tivalvideo create *.png -n narration.txt -o youtube.mp4 --landscape
```

## Features

- 1080×1920 TikTok and YouTube Shorts
- 1920×1080 landscape videos
- Offline Piper AI narration
- Managed FFmpeg binary—no `apt install ffmpeg` required
- Blurred full-screen background with centred images
- Automatic fade transitions
- H.264 video and AAC audio
- Automatic voice-model caching
- Python API and terminal command

## Notes

- The first setup requires internet access for the voice download.
- Generated videos work from local image files and text only.
- Keep the voice model cached to remain fully offline.

Powered by tivalsdeveloper.

