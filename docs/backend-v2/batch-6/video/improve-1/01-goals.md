# Video Module Improve-1: Optimization Goals

## Background

Video module (batch-6) first-pass implementation completed the subtitle-based summarization path:
Studio panel SSE summarization, `/video` slash command agent integration, Bilibili authentication,
CRUD and notebook association. However, the following gaps remain:

1. BilibiliClient only implements 3 of 11 designed methods, causing 4 agent tools to crash at runtime
2. No subtitle fallback: videos without CC subtitles cannot be summarized
3. No ASR transcription pipeline (only scaffold exists)
4. B站 AI summary interface not implemented (agent supplementary info)
5. Video skill defines 12 tools, exceeding note(8)/diagram(7) norms, polluting agent context

This document defines the scope, objectives, and boundaries of improve-1.

---

## Optimization Objectives

### O1: Complete BilibiliClient Missing Methods

Implement the remaining BilibiliClient methods referencing bilibili-cli design:

- `search_video(keyword, page)` -- video keyword search
- `get_hot_videos(page)` -- hot video discovery
- `get_rank_videos(day)` -- ranking list
- `get_related_videos(bvid)` -- related video recommendation
- `get_video_ai_conclusion(bvid)` -- B站 AI summary text
- `get_audio_url(bvid)` -- audio stream URL for ASR
- `download_audio(url, dest)` -- audio file download

Detail: [02-bilibili-client-patch.md](02-bilibili-client-patch.md)

### O2: Build ASR Transcription Pipeline

For videos without subtitles, provide API-based speech-to-text transcription:

- Zhipu GLM-ASR-2512: multipart upload, <=30s per segment
- Qwen qwen3-asr-flash: base64 in messages, <=5min per segment
- Audio acquisition from Bilibili + format conversion (PyAV) + time-based segmentation
- Concurrent transcription with provider-specific adapters
- Default provider: zhipu, user-switchable

Detail: [03-asr-pipeline.md](03-asr-pipeline.md)

### O3: Add ASR Configuration to Global Settings Panel

Extend the existing `app_settings` key-value config system:

- `asr.provider` / `asr.model` database keys
- API endpoints: GET/PUT/POST reset
- Frontend settings panel: "ASR" section under "Model" tab
- API key reuse from LLM config (same provider key)

Detail: [04-asr-config.md](04-asr-config.md)

### O4: Integrate B站 AI Summary as Agent-Only Tool

- Add `get_video_ai_conclusion(bvid)` to BilibiliClient
- Expose as agent tool via VideoSkillProvider (merged into `get_video_content`)
- Agent-only: not used in studio panel summarization pipeline
- Purpose: help agent quickly understand video content without full summarization

### O5: Streamline Video Skill Tools (12 -> 9)

Align with /note and /diagram tool count norms:

| Merge | Before | After |
|-------|--------|-------|
| Discovery | search_video + get_hot_videos + get_rank_videos + get_related_videos (4) | discover_videos(source, ...) (1) |
| Content | get_video_subtitle + get_video_ai_conclusion (2) | get_video_content(type) (1) |

Result: 12 + 1(new) - 4(merged) = **9 tools**

---

## Scope Boundaries

### In Scope

- BilibiliClient method completion (referencing bilibili-cli)
- ASR pipeline: audio download, format conversion, segmentation, transcription
- ASR config: DB keys, API, frontend settings panel section
- B站 AI summary as agent tool
- VideoSkillProvider tool count reduction
- New dependency: `av` (PyAV) for audio processing
- Payload normalization for new API responses

### Out of Scope

- Local ASR models (Whisper, FunASR, etc.) -- all ASR via cloud API
- Studio panel summarization pipeline changes (subtitle priority unchanged)
- YouTube or other platform support
- Frontend video player or UI changes beyond settings panel
- ASR quality evaluation or benchmark
- Bilibili personal data APIs (collections, history, subscriptions)

---

## Dependency Changes

| Package | Version | Purpose |
|---------|---------|---------|
| `av` | >=14.0.0 | Audio format conversion (m4s/AAC -> WAV) and time-based segmentation; bundles FFmpeg as wheels, no system FFmpeg required |

Note: `tiktoken`, `bilibili-api-python`, `aiohttp` are already available in the project.

---

## Document Index

| Document | Scope |
|----------|-------|
| [01-goals.md](01-goals.md) | This file: objectives, scope, boundaries |
| [02-bilibili-client-patch.md](02-bilibili-client-patch.md) | BilibiliClient missing methods, payload normalization |
| [03-asr-pipeline.md](03-asr-pipeline.md) | ASR pipeline architecture, provider adapters, segmentation strategy |
| [04-asr-config.md](04-asr-config.md) | ASR configuration: DB schema, API endpoints, frontend panel |
