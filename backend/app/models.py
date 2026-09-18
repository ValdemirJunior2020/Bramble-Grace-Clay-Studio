from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Any
from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

Language = Literal["en", "pt-br", "both"]
BlockType = Literal["narrator", "dialogue", "sound_effect", "pause", "music_cue", "scene_instruction"]
AnimationMode = Literal["clay-motion", "comfyui", "musetalk", "no-motion"]
LipSyncMode = Literal["auto", "ai-speech-video", "ai-face", "clay-mouth", "none"]

class SubtitleStyle(BaseModel):
    enabled: bool = True
    burn_in: bool = True
    export_srt: bool = True
    export_vtt: bool = True
    font: str = "Arial"
    font_size: int = 48
    text_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    background_color: str = "#000000"
    background_opacity: float = 0.0
    bold: bool = True
    outline: int = 3
    shadow: int = 1
    position: Literal["top", "center", "bottom"] = "bottom"
    max_chars: int = 42
    max_lines: int = 2
    bottom_margin: int = 72
    safe_area: int = 36

class VoiceSettings(BaseModel):
    engine: Literal["auto", "chatterbox", "sapi"] = "auto"
    speed: float = Field(1.0, ge=0.5, le=2.0)
    expression: float = Field(0.5, ge=0.0, le=1.0)
    exaggeration: float = Field(0.5, ge=0.0, le=1.0)
    cfg: float = Field(0.5, ge=0.0, le=2.0)
    seed: int = 0
    volume_db: float = 0.0
    reference_audio: str | None = None
    model: str | None = None

class MouthSettings(BaseModel):
    x: float = 0.5
    y: float = 0.6
    scale: float = 1.0
    rotation: float = 0.0
    feather: int = 2
    procedural_fallback: bool = False
    shapes: dict[str, str] = Field(default_factory=dict)

class Character(BaseModel):
    id: str
    name: str
    description: str = ""
    species: str = ""
    tag: str = "#7c3aed"
    reference_images: list[str] = Field(default_factory=list)
    main_portrait: str | None = None
    full_body_image: str | None = None
    voice_en: VoiceSettings = Field(default_factory=VoiceSettings)
    voice_pt_br: VoiceSettings = Field(default_factory=VoiceSettings)
    lip_sync_mode: LipSyncMode = "auto"
    mouth: MouthSettings = Field(default_factory=MouthSettings)
    face_position: tuple[float, float] = (0.5, 0.4)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

class ScriptBlock(BaseModel):
    id: str
    type: BlockType
    text: str = ""
    speaker: str | None = None
    speaker_confidence: float = 0.0
    needs_review: bool = False
    duration: float | None = None
    pause_after: float = 0.25
    metadata: dict[str, Any] = Field(default_factory=dict)

class CharacterPlacement(BaseModel):
    character_id: str
    visible: bool = True
    mouth_x: float | None = None
    mouth_y: float | None = None
    mouth_scale: float | None = None
    confidence: float = 0.0
    confirmed: bool = False

class Scene(BaseModel):
    id: str
    number: int
    name: str
    source_image: str
    duration: float = 5.0
    blocks: list[ScriptBlock] = Field(default_factory=list)
    blocks_by_language: dict[str, list[ScriptBlock]] = Field(default_factory=dict)
    characters_visible: list[str] = Field(default_factory=list)
    character_placements: list[CharacterPlacement] = Field(default_factory=list)
    animation_mode: AnimationMode = "clay-motion"
    workflow_name: str | None = None
    lip_sync_mode: LipSyncMode = "auto"
    motion_description: str = "Gentle handmade clay stop-motion movement. Slow camera push. Subtle breathing and blinking."
    camera_movement: str = "slow_push"
    transition: str = "fade"
    subtitle_override: SubtitleStyle | None = None
    focus_points: list[tuple[float, float]] = Field(default_factory=lambda: [(0.5, 0.5)])
    render_status: Literal["pending", "rendering", "complete", "failed"] = "pending"
    preview_path: str | None = None
    preview_signature: str | None = None
    preview_paths: dict[str, str] = Field(default_factory=dict)
    preview_signatures: dict[str, str] = Field(default_factory=dict)
    render_path: str | None = None
    render_signature: str | None = None
    render_paths: dict[str, str] = Field(default_factory=dict)
    render_signatures: dict[str, str] = Field(default_factory=dict)
    error: str | None = None

class StoryVersions(BaseModel):
    english: str = ""
    portuguese: str = ""
    heart_lesson_en: str = ""
    heart_lesson_pt: str = ""
    parents_en: str = ""
    parents_pt: str = ""

class ProjectSettings(BaseModel):
    mode: Literal["bramble", "general"] = "bramble"
    language: Language = "en"
    output_format: str = "16:9"
    width: int = 1920
    height: int = 1080
    preview_width: int = 640
    preview_height: int = 360
    fps: int = 24
    preview_fps: int = 15
    subtitle: SubtitleStyle = Field(default_factory=SubtitleStyle)
    voice_speed_global: float = Field(1.0, ge=0.5, le=2.0)
    background_fill: Literal["crop", "fit", "blur", "solid"] = "crop"
    background_color: str = "#000000"
    music_path: str | None = None
    music_volume: float = 0.16
    duck_music: bool = True
    music_fade_in: float = 1.0
    music_fade_out: float = 2.0
    clay_style_prompt: str = "Handcrafted modeling-clay children's animation, visible handmade clay texture, subtle fingerprints and sculpted details, miniature practical set, soft warm lighting, gentle stop-motion movement, child-friendly, cozy cinematic composition."

class Project(BaseModel):
    id: str
    title: str
    story_number: str = ""
    english_title: str = ""
    portuguese_title: str = ""
    folder: str
    story: StoryVersions = Field(default_factory=StoryVersions)
    script_blocks_en: list[ScriptBlock] = Field(default_factory=list)
    script_blocks_pt: list[ScriptBlock] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    render_status: str = "pending"
    thumbnail: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

class ProjectCreate(BaseModel):
    title: str
    story_number: str = ""
    english_title: str = ""
    portuguese_title: str = ""
    language: Language = "en"
    output_format: str = "16:9"
    width: int = 1920
    height: int = 1080
    mode: Literal["bramble", "general"] = "bramble"

class ReorderRequest(BaseModel):
    scene_ids: list[str]

class ScenePatch(BaseModel):
    name: str | None = None
    duration: float | None = None
    blocks: list[ScriptBlock] | None = None
    characters_visible: list[str] | None = None
    character_placements: list[CharacterPlacement] | None = None
    animation_mode: AnimationMode | None = None
    workflow_name: str | None = None
    lip_sync_mode: LipSyncMode | None = None
    motion_description: str | None = None
    camera_movement: str | None = None
    transition: str | None = None
    subtitle_override: SubtitleStyle | None = None
    focus_points: list[tuple[float, float]] | None = None

class QueueJob(BaseModel):
    id: str
    project_id: str
    scene_id: str | None = None
    kind: Literal["preview_scene", "render_scene", "render_story", "voice_preview"]
    state: Literal["queued", "running", "paused", "complete", "failed", "cancelled"] = "queued"
    stage: str = "Preparing"
    progress: float = 0.0
    message: str = ""
    result_path: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
