export type WorkflowStage =
  | "idle"
  | "generating_script"
  | "awaiting_review"
  | "generating_images"
  | "generating_audio"
  | "generating_video"
  | "assembling"
  | "completed"
  | "failed";

export interface SceneDraft {
  scene_id: number;
  duration: number;
  image_prompt: string;
  video_prompt: string;
  voiceover: string;
  transition?: string;
  camera_motion?: string;
  style_tags?: string[];
  shot_mode?: string;
}

export interface ScriptDraft {
  title: string;
  topic?: string;
  style?: string;
  total_duration?: number;
  scenes: SceneDraft[];
  metadata?: Record<string, unknown>;
}

export interface ProjectResult {
  final_video?: string;
  plain_video?: string;
  subtitled_video?: string | null;
  subtitle_file?: string | null;
  subtitles_burned?: boolean;
  subtitle_warning?: string | null;
  draft_dir?: string;
  total_duration?: number;
  script?: ScriptDraft;
}

export interface ProjectStatus {
  type?: string;
  project_id?: string;
  stage: WorkflowStage;
  progress: number;
  message?: string;
  timestamp?: string;
  error?: string;
  current_scene?: number;
  total_scenes?: number;
  keyframes?: string[];
  requires_action?: boolean;
  action_type?: string;
  script?: ScriptDraft;
  result?: ProjectResult;
}

export interface ProjectLog {
  type: "log";
  project_id: string;
  message: string;
  timestamp: string;
}

export interface ProjectAction {
  key: "approve_review" | "reject_review" | "resume_from_script" | "resume_from_video" | "reassemble";
  label: string;
  kind: "primary" | "danger" | "default";
}

export interface ArtifactManifest {
  project_dir: string;
  script?: string | null;
  keyframes: string[];
  audio: string[];
  clips: string[];
  final_video?: string | null;
  plain_video?: string | null;
  subtitled_video?: string | null;
  subtitles: string[];
  draft_dir?: string | null;
  has_script: boolean;
  has_keyframes: boolean;
  has_audio: boolean;
  has_clips: boolean;
  has_result: boolean;
}

export interface ProjectRecord {
  id: string;
  title?: string;
  topic: string;
  created_at: string;
  status: ProjectStatus;
  voice_id?: string | null;
  script?: ScriptDraft | null;
  result?: ProjectResult | null;
  from_analysis?: string | null;
  has_script?: boolean;
  has_keyframes?: boolean;
  resumable_from_script?: boolean;
  artifacts?: ArtifactManifest;
  actions?: ProjectAction[];
}

export interface CreateProjectPayload {
  topic: string;
  style?: string;
  target_duration?: number;
  voice_id?: string;
  video_engine?: "kling" | "seedance" | "minimax" | "auto";
  reference_images?: string[];
  add_subtitles?: boolean;
  resolution?: "720p" | "1080p" | "4K";
  aspect_ratio?: "9:16" | "16:9";
  global_style_prompt?: string;
}

export interface ProviderOption {
  value: string;
  label: string;
  models: string[];
  voice_catalog_supported?: boolean;
}

export interface KeysStatus {
  llm: {
    provider: string;
    configured: boolean;
  };
  image_gen: {
    provider: string;
    configured: boolean;
  };
  tts: {
    provider: string;
    configured: boolean;
  };
  kling: {
    configured: boolean;
  };
  minimax_video: {
    configured: boolean;
  };
  seedance: {
    configured: boolean;
  };
}

export interface SystemHealth {
  status: string;
  name: string;
  version: string;
  api_base: string;
  defaults: {
    llm_provider: string;
    llm_model: string;
    image_provider: string;
    video_provider: string;
  };
}

export interface ConnectorStatus {
  llm: {
    default_provider: string;
    model: string;
    configured: boolean;
  };
  image: {
    provider: string;
    model: string;
    configured: boolean;
  };
  tts: {
    provider: string;
    model: string;
    configured: boolean;
    default_voice?: string;
    voice_catalog_supported: boolean;
  };
  video: {
    default_provider: string;
    model?: string;
    configured: boolean;
    minimax_configured?: boolean;
    kling_configured: boolean;
    seedance_configured: boolean;
  };
}

export interface SystemSetup {
  onboarding_required: boolean;
  config_path: string;
  config_exists: boolean;
  missing_requirements: Array<{
    key: string;
    label: string;
    message: string;
  }>;
  current: {
    llm_provider: string;
    llm_model: string;
    image_provider: string;
    image_model: string;
    video_provider: string;
    video_model: string;
    tts_provider: string;
    tts_model: string;
    tts_default_voice?: string;
  };
  capabilities: {
    tts_voice_catalog_supported: boolean;
  };
  options: {
    llm_providers: ProviderOption[];
    image_providers: ProviderOption[];
    video_providers: ProviderOption[];
    tts_providers: ProviderOption[];
  };
}

export interface VoiceOption {
  id: string;
  name: string;
  description: string;
  language: string;
  tags: string[];
  source_type: "system" | "voice_cloning" | "voice_generation";
  created_time?: string | null;
  preview_available: boolean;
}

export interface VoiceCatalogResponse {
  provider: string;
  default_voice?: string;
  source: string;
  fallback: boolean;
  voices: VoiceOption[];
}

export interface VoicePreviewResponse {
  voice_id: string;
  preview_text: string;
  cache_key: string;
  audio_url: string;
  cached: boolean;
}

export interface AnalysisCharacter {
  character_id: number;
  name: string;
  description: string;
  appearance_prompt: string;
  replacement_image?: string | null;
}

export interface AnalysisResult {
  title: string;
  style: string;
  aspect_ratio: string;
  total_duration: number;
  bgm_style: string;
  color_grade: string;
  overall_prompt: string;
  characters: AnalysisCharacter[];
  scenes: SceneDraft[];
  reverse_prompts: string[];
  raw_analysis: string;
}

export interface AnalysisTask {
  analysis_id: string;
  status: "processing" | "completed" | "failed";
  filename?: string;
  file_path?: string;
  created_at?: string;
  result?: AnalysisResult | null;
  error?: string | null;
}
