# Bramble & Grace Clay Studio

Bramble & Grace Clay Studio is a local-first Windows application for turning illustrated story scenes into simple animated clay-style videos. The app uses a React + TypeScript + Vite interface and a local FastAPI backend. No account, telemetry, cloud API key, or paid online service is required for the implemented baseline workflow.

## Current tested MVP

The tested baseline supports creating one story project at a time, importing DOCX/TXT/Markdown or pasted text, separating English and Brazilian Portuguese story sections, importing many scene images, reordering scenes, reusable Grace/Bramble/Pip/Oliver/Barnaby/Narrator profiles, conservative speaker suggestions, manual speaker confirmation, separate EN/PT-BR script assignments, separate EN/PT-BR character voice speeds, global voice speed, subtitle size and text color controls, local TTS, SRT/VTT generation, FFmpeg Clay Motion scene rendering, active-speaker procedural mouth movement, scene previews, final story joining, generation queue, project autosave, system status, and separate EN/PT-BR render caches.

Final rendering is blocked when a dialogue line still has an unconfirmed speaker. The app does not silently guess an uncertain speaker.

Two project modes are included: **Bramble & Grace** and **General Video**.

## Local engines

The baseline renderer is **Clay Motion**. It works without a large diffusion-video model.

**Chatterbox Multilingual** is supported as the preferred optional local TTS engine through an isolated local service. Windows SAPI is the local fallback when Chatterbox is not installed.

**Rhubarb Lip Sync** has an optional local installer and adapter. The current tested baseline render path uses procedural active-speaker mouth movement; Rhubarb is available for continued mouth-cue integration.

**ComfyUI** has an optional installer and configurable local API workflow adapter. You do not need to manually build nodes in normal use. The current tested baseline does not bundle or claim a specific Wan/HuMo/MuseTalk video workflow as tested. Large AI video models are optional enhancements, not required for Clay Motion.

For the target AMD Radeon RX 9060 XT, the optional ComfyUI installer uses the current Windows ROCm/gfx1200 package path when that GPU is detected. ComfyUI is kept in its own environment so it cannot break the Python 3.11 application backend.

## Install

Install Git, Node/npm, FFmpeg, and Python 3.11, then double-click:

`INSTALL.bat`

The installer creates the Python environment, installs backend dependencies, installs/builds the frontend, prepares data folders, creates the small demo project, and offers optional Rhubarb, Chatterbox, and ComfyUI installation. It does not silently download giant video models.

## Start

Double-click:

`START.bat`

The launcher starts only the local services that are installed, starts the FastAPI backend, waits for health, and opens the browser.

Use `CHECK.bat` to inspect the installation. Use `STOP.bat` to stop only processes that this app recorded as its own.

## Storage

Projects are stored under:

`data/projects/`

Each story project contains its own story, images, voices/audio, scenes, subtitles, renders, cache, temp files, and logs.

Final English videos are stored under the project's:

`renders/en/`

Brazilian Portuguese videos are stored under:

`renders/pt-br/`

Original image files outside the project folder are not automatically deleted.

## Optional ComfyUI workflows

Place an API-format ComfyUI workflow and matching `*.adapter.json` file in `workflows/`. The adapter maps Clay Studio fields such as input image, audio, prompt, negative prompt, seed, width/height, and output node to the local workflow.

No untested giant workflow is shipped as if it were verified.

## Tests

The backend test suite currently passes **14/14 tests** in the build environment. It covers project creation/autosave, bilingual separation, EN/PT-BR scene switching, separate language render caches, speaker mapping, uncertain-speaker review, voice configuration, UTF-8 Portuguese subtitles, scene ordering/reordering, aspect-ratio calculations, queue failure handling, API health, and actual FFmpeg MP4 smoke rendering.

The frontend source was syntax-checked after the final rewrite. A complete Vite production build could not be executed in the build container because Node packages were not available there; `INSTALL.bat` performs `npm install` and `npm run build` on the Windows machine.

## Current MVP limits

This commit is the tested local MVP/core workflow, not a claim that every optional feature from the long-term design is finished. In particular, Wan Speech-to-Video, MuseTalk, HuMo, automatic Rhubarb-driven mouth-shape compositing, project ZIP import/export, full model download/remove management, music ducking/SFX mixing, and advanced visual character recognition are not yet claimed as tested end-to-end in this commit.

The baseline Clay Motion video path is intentionally independent of those optional engines so the application can still produce local story videos.
