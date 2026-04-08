# LingtiStudio

<p align="center">
  <img src="./screenshots/doggie.gif" alt="LingtiStudio doggie" width="180" />
</p>

Lingti means **greyhound** in Chinese, the fastest dog.  
**LingtiStudio** helps you turn an idea into a complete AI video workflow, fast.

From a single topic, LingtiStudio can take you through:

**script -> review -> keyframes -> voiceover -> clips -> assembly -> final video**

It is built for creators who want to go from short videos to longer, multi-scene productions without manually stitching together five different tools.

[中文说明 / Chinese Guide](./README-CN.md)

---

## Chinese Demo Video

<table>
  <tr>
    <td width="320">
      <a href="https://www.bilibili.com/video/BV1NjDrBnECg/">
        <img src="./screenshots/cn-video-header.png" alt="LingtiStudio Chinese demo video cover" width="320" />
      </a>
    </td>
    <td>
      <strong>Chinese demo video: LingtiStudio open-source walkthrough and output showcase</strong>
      <br />
      <br />
      If you want to see the product flow, interface, and generation results before trying it yourself, this Bilibili video is the best starting point.
      <br />
      <br />
      <a href="https://www.bilibili.com/video/BV1NjDrBnECg/">Watch on Bilibili</a>
    </td>
  </tr>
</table>

---

## Screenshots

<table>
  <tr>
    <td width="33.33%">
      <img src="./screenshots/index_page.png" alt="LingtiStudio home page" />
    </td>
    <td width="33.33%">
      <img src="./screenshots/video_gen_page.png" alt="LingtiStudio video generation page" />
    </td>
    <td width="33.33%">
      <img src="./screenshots/video_done_page.png" alt="LingtiStudio final output page" />
    </td>
  </tr>
  <tr>
    <td align="center"><strong>Home</strong></td>
    <td align="center"><strong>Video Generation Workspace</strong></td>
    <td align="center"><strong>Final Output Page</strong></td>
  </tr>
</table>

---

## What It Is

LingtiStudio is an open-source AI video production system for local-first creation.

It is designed to make the full generation chain feel like **one product**, not a pile of disconnected scripts and providers.

With LingtiStudio, you can go from a rough idea to a polished deliverable with:
- script generation
- human review before expensive generation starts
- keyframe image generation
- TTS voiceover
- image-to-video generation
- FFmpeg assembly
- subtitle export
- JianYing / CapCut draft generation

That means you can build:
- short promotional videos
- narrated explainers
- multi-scene story videos
- polished ad-style videos
- longer AI-assisted productions with reviewable scenes and recoverable outputs

Instead of a one-shot black box, LingtiStudio gives you a workflow you can pause, inspect, edit, resume, and deliver.

---

## Why It Feels Different

Most AI video tools are great at giving you a result.  
LingtiStudio is built to give you a **production pipeline**.

It focuses on:
- **reviewability**: inspect and edit scenes before expensive generation begins
- **recoverability**: resume from script, video, or assembly instead of starting over
- **consistency**: keep prompts, voice, aspect ratio, and style aligned across scenes
- **long-form readiness**: handle multi-scene projects more like a structured workflow than a toy prompt box
- **local control**: keep your config, outputs, drafts, and assembly on your own machine

---

## Workflow

LingtiStudio turns end-to-end AI video generation into a one-click, full-stack workflow:

1. Generate a script from a topic or imported reference analysis
2. Review and edit scenes before continuing
3. Generate keyframes for every scene
4. Generate voiceover for every scene
5. Turn keyframes into video clips with Kling or Seedance
6. Assemble the final video with audio, transitions, subtitles, and export artifacts
7. Export the final MP4, subtitle file, and JianYing / CapCut draft

This is especially useful when you want the speed of AI generation but still need the control of a real production flow.

---

## Current Stack

- Backend: FastAPI
- Frontend: Next.js + Ant Design
- LLM: DeepSeek / MiniMax / Gemini / OpenAI / Kimi / Zhipu / Ollama
- Image: MiniMax Image / Gemini image generation
- Video: Kling / Seedance
- TTS: MiniMax
- Assembly: FFmpeg

---

## Supported Models

The table below reflects the built-in provider and model options currently exposed by the web setup flow and runtime config.

| Stage | Provider | Built-in models |
| --- | --- | --- |
| Script / planning | MiniMax | `MiniMax-M2.5`, `MiniMax-M2.7` |
| Script / planning | DeepSeek | `deepseek-chat`, `deepseek-reasoner` |
| Script / planning | Moonshot Kimi | `moonshot-v1-8k`, `moonshot-v1-32k` |
| Script / planning | Zhipu | `glm-4`, `glm-4-air` |
| Script / planning | Gemini | `gemini-2.5-flash`, `gemini-1.5-pro` |
| Script / planning | OpenAI | `gpt-4o`, `gpt-4.1-mini` |
| Script / planning | Ollama | `qwen2.5:latest`, `llama3.1:8b` |
| Keyframe image generation | MiniMax Image | `image-01` |
| Keyframe image generation | Nano Banana / Gemini Image | `gemini-2.0-flash-preview-image-generation`, `gemini-3-pro-image-preview` |
| Voiceover / TTS | MiniMax TTS | `speech-2.8-hd`, `speech-02-hd` |
| Video clip generation | Kling | `kling-v3` |
| Video clip generation | Seedance | `doubao-seedance-1-5-pro-250528`, `Doubao-Seedance-1.0-pro` |
| Assembly / subtitles / export | Local FFmpeg | local environment dependent |

Notes:
- The web UI shows these as the default built-in options; advanced users can still edit `configs/config.yaml` manually.
- MiniMax currently provides the built-in voice catalog and voice preview flow in the UI.
- Final assembly is done locally with FFmpeg, so subtitle burn-in and some transition behaviors depend on your FFmpeg build.

---

## First-Run Experience

When the web UI detects missing required configuration, it automatically opens a setup dialog.

You can configure:
- default LLM provider and model
- image provider and model
- video provider and model
- TTS model
- API keys for the selected services

Settings are written to:

```bash
configs/config.yaml
```

If you prefer manual setup, copy the example file first:

```bash
cp configs/config.example.yaml configs/config.yaml
```

---

## Quick Start

### 1. Requirements

- Python 3.10+
- Node.js 18+
- FFmpeg in PATH

Check FFmpeg:

```bash
ffmpeg -version
```

### 2. Install

```bash
git clone https://github.com/ruilisi/LingtiStudio.git
cd LingtiStudio

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
yarn install
cd ..
```

### 3. Start backend

```bash
.venv/bin/python -m uvicorn api.server:app --host 0.0.0.0 --port 8000
```

### 4. Start frontend

```bash
cd frontend
yarn dev --port 3001
```

Open:

```text
http://127.0.0.1:3001
```

If the config is incomplete, the setup dialog will appear automatically.

---

## Docker

LingtiStudio also ships with a release-oriented Docker setup so users can start the product first and configure tokens in the browser later.

The release image is intentionally trimmed for the browser-first workflow:
- it is optimized for script -> review -> keyframes -> TTS -> clips -> assembly
- it avoids shipping heavy optional dependencies such as local Whisper / Torch by default
- optional integrations such as pyJianYingDraft still fall back gracefully when unavailable

### Recommended: prebuilt release image

Tagged releases can publish a prebuilt container image to GHCR through GitHub Actions:

```bash
docker run --rm \
  -p 3000:3000 \
  -p 8000:8000 \
  -v "$(pwd)/configs:/app/configs" \
  -v "$(pwd)/data:/app/data" \
  --name lingtistudio \
  ghcr.io/ruilisi/lingtistudio:v1.1.0
```

This is the fastest path for end users because it avoids local image builds entirely.

### Option 1: Docker Compose

```bash
docker compose up -d --build
```

Then open:

```text
http://localhost:3000
```

On first run:
- LingtiStudio opens the browser setup dialog automatically
- users can choose providers and models in the UI
- API tokens are written to `./configs/config.yaml`
- outputs, uploads, and local runtime data are stored in `./data`

Default ports:
- Web UI: `3000`
- API: `8000`

### Option 2: Single Docker image

Build:

```bash
docker build -t lingtistudio:latest .
```

Run:

```bash
docker run --rm \
  -p 3000:3000 \
  -p 8000:8000 \
  -v "$(pwd)/configs:/app/configs" \
  -v "$(pwd)/data:/app/data" \
  --name lingtistudio \
  lingtistudio:latest
```

Then open:

```text
http://localhost:3000
```

This path is intended for open-source releases where users want:
- one container image
- browser-first onboarding
- persistent config and output directories on the host

Notes:
- the release image is a lighter runtime image, not a full development image
- if you want local ASR / Whisper tooling inside Docker, treat that as an advanced custom build layer
- for most users, the browser UI + external API providers are enough to start generating immediately after setup

---

## CLI

Run a generation task directly:

```bash
.venv/bin/python cli/main.py run --topic "A modern retirement hotel near Shanghai, 40 seconds"
```

Test connectors:

```bash
.venv/bin/python cli/main.py test --module llm
.venv/bin/python cli/main.py test --module image
.venv/bin/python cli/main.py test --module tts
.venv/bin/python cli/main.py test --module video
```

---

## Web UI

Main routes:

- `/` Home
- `/create` Quick generation
- `/studio` Pro workspace
- `/analyze` Reference video analysis
- `/settings` Setup and connectors

Highlights:

- first-run setup modal
- provider/model friendly config editing
- script review before generation
- resumable projects
- live console logs
- downloadable final video, subtitles, and JianYing draft

---

## TTS Behavior

The built-in voice catalog and voice preview are currently available only for **MiniMax TTS**.

If the active TTS provider does not support the MiniMax voice catalog, the UI switches from:

- voice picker

to:

- manual `voice_id` input

This keeps the interface usable for custom or externally managed voice setups.

---

## Project Structure

```text
api/                FastAPI backend
cli/                CLI entrypoints
core/               Config loader and shared settings
modules/            LLM / image / TTS / video / assembly modules
frontend/           Next.js frontend
configs/            Example and local config files
data/               Outputs, uploads, cache, local runtime data
```

---

## Notes

- This project is optimized for local workflows, not multi-tenant SaaS deployment.
- Some providers are configurable at the UI layer before every backend path is fully generalized.
- FFmpeg features depend on your local build. If subtitle burn-in is unavailable, LingtiStudio can still output MP4 + SRT.

---

## License

MIT
