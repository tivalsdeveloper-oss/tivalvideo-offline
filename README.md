# TivalVideo Offline 0.4.0

Create narrated vertical Shorts or landscape videos from images, entirely offline after the first setup. TivalVideo uses a managed FFmpeg executable for video rendering and Piper for local AI narration.

Version 0.4.0 can add AI narration or a recorded voice to existing MP4 screen recordings. Choose whether to replace, mix, or automatically duck the video's original sound.

## Narrate a screen recording

\`\`\`python
from tivalvideo import add_narration

add_narration(
    video="screen-recording.mp4",
    narration="Welcome. First, open the project folder.",
    voice="en_US-lessac-medium",
    original_audio="duck",
    original_volume=0.25,
    output="screen-recording-narrated.mp4",
)
\`\`\`

Use your own MP3 or WAV recording instead:

\`\`\`python
add_narration(
    video="screen-recording.mp4",
    audio="my-voice.mp3",
    original_audio="mix",
    output="tutorial.mp4",
)
\`\`\`

Audio modes:

- \`replace\` removes the screen recording's original sound.
- \`mix\` plays the original sound and narration together.
- \`duck\` lowers the original sound while narration plays.

\`\`\`bash
tivalvideo narrate screen-recording.mp4 \\
  --narration narration.txt \\
  --original-audio duck \\
  --output tutorial.mp4
\`\`\`

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

## Narrator voices

See all included voices and which ones are installed:

```bash
tivalvideo voices list
```

Install additional voices only when you need them:

```bash
tivalvideo voices install en_US-amy-medium
tivalvideo voices install en_US-joe-medium
tivalvideo voices install en_GB-alan-medium
```

Each medium voice is approximately 63 MB and stays cached for offline use.

Choose a voice in Python:

```python
from tivalvideo import create_video

create_video(
    typing_text="The history of Python",
    narration="Python was created by Guido van Rossum.",
    voice="en_GB-alan-medium",
    background="midnight",
    output="python-history.mp4",
)
```

Available narrator keys:

- `en_US-lessac-medium` (default, American English)
- `en_US-amy-medium` (American English)
- `en_US-joe-medium` (American English)
- `en_GB-alan-medium` (British English)

The selected voice downloads automatically on first use. Remove an unused voice with:

```bash
tivalvideo voices remove en_US-amy-medium
```

## Python example

```python
from tivalvideo import create_video

create_video(
    images=["lesson1.png", "lesson2.png", "lesson3.png"],
    narration="Learn TivalTube with these simple examples.",
    output="tivaltube-short.mp4",
)
```

## Auto-typing video

Create a complete Short without supplying lesson images:

```python
from tivalvideo import create_video

create_video(
    typing_text="Welcome to my Python lesson!",
    narration="Welcome to my Python lesson.",
    background="ocean",
    output="typing-short.mp4",
)
```

Built-in background choices are `midnight`, `ocean`, `sunset`, and `paper`.

Use your own background image:

```python
create_video(
    typing_text="Learn Python step by step",
    audio="my-recorded-voice.mp3",
    background_image="my-background.jpg",
    output="custom-short.mp4",
)
```

## Recorded voice and music

Use recorded voice instead of AI narration and optionally mix in music:

```python
create_video(
    images=["lesson1.png", "lesson2.png"],
    audio="voice.wav",
    music="background.mp3",
    output="lesson.mp4",
)
```

Do not pass both `narration` and `audio`; they are two alternative voice sources.

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
- Selectable American and British narrator voices
- Voice list, install, and remove commands
- Auto-typing text animation
- MP3/WAV recorded voice and background music
- Built-in and user-provided auto-typing backgrounds
- Python API and terminal command
- Narration for existing MP4 screen recordings
- Replace, mix, or automatically duck original video audio

## Notes

- The first setup requires internet access for the voice download.
- Generated videos work from local image files and text only.
- Keep the voice model cached to remain fully offline.

Powered by tivalsdeveloper.
