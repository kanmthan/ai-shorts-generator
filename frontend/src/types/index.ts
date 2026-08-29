/**
 * Shared TypeScript interfaces for the AI Shorts Generator frontend.
 *
 * These mirror the backend SQLAlchemy models described in
 * `PRPs/ai-shorts-generator-prp.md`. Phase 2 agents should keep these in sync
 * with the API response schemas.
 */

/* -------------------------------------------------------------------------- */
/* User                                                                       */
/* -------------------------------------------------------------------------- */

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  oauth_provider: string | null;
  created_at: string;
}

/* -------------------------------------------------------------------------- */
/* Project                                                                    */
/* -------------------------------------------------------------------------- */

export type ProjectStatus =
  | 'pending'
  | 'fetching'
  | 'transcribing'
  | 'analyzing'
  | 'ready'
  | 'failed';

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface Project {
  id: number;
  user_id: number;
  url: string;
  platform: string | null;
  external_id: string | null;
  title: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  status: ProjectStatus;
  language: string | null;
  /** Backend returns a count, not the full transcript array, on ProjectOut. */
  transcript_segment_count?: number;
  error_message: string | null;
  /** 0-100 pipeline progress hint. */
  progress?: number;
  created_at: string | null;
  updated_at: string | null;
}

/* -------------------------------------------------------------------------- */
/* Short                                                                      */
/* -------------------------------------------------------------------------- */

export type ShortStatus = 'draft' | 'queued' | 'rendering' | 'rendered' | 'failed';

/**
 * Nine 1-10 metrics plus a computed `overall` float. Keys match the backend
 * `ScoresOut` schema. On `ShortOut.scores` the backend serialises a free-form
 * dict, so treat individual keys as possibly-absent when reading detail rows.
 */
export interface Scores {
  hook_strength: number;
  standalone_value: number;
  engagement: number;
  retention: number;
  payoff: number;
  clarity: number;
  shareability: number;
  viral_potential: number;
  b_roll_quality: number;
  overall: number;
}

/** Per-short editing/render preferences (stored as JSON on the model). */
export interface Editing {
  remove_silences: boolean;
  silence_threshold_db: number;
  keep_original_audio: boolean;
  caption_style: string;
  caption_emphasis: boolean;
  broll_opacity: number;
  keep_speaker_on_high_impact: boolean;
  target_aspect_ratio: string;
}

export interface Short {
  id: number;
  project_id: number;
  index: number;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  title: string;
  hook: string;
  summary: string;
  reason: string;
  scores: Scores;
  caption: string;
  hashtags: string[];
  editing: Editing;
  category: string;
  status: ShortStatus;
  created_at: string;
  broll_segments?: BrollSegment[];
  subtitle_segments?: SubtitleSegment[];
}

/* -------------------------------------------------------------------------- */
/* BrollSegment                                                               */
/* -------------------------------------------------------------------------- */

export type BrollType =
  | 'stock_video'
  | 'image'
  | 'screenshot'
  | 'screen_recording'
  | 'chart'
  | 'animation'
  | 'news_image'
  | 'original_cutaway';

export type BrollTransition = 'smooth_cut' | 'quick_cut' | 'fade' | 'dissolve';

export type BrollPlacement = 'start' | 'middle' | 'end';

export type BrollAssetSource = 'pexels' | 'pixabay' | 'original';

export type BrollAssetStatus = 'pending' | 'fetched' | 'not_found' | 'skipped';

export interface BrollSegment {
  id: number;
  short_id: number;
  start: string;
  end: string;
  original_start: string;
  original_end: string;
  duration_seconds: number;
  description: string;
  reason: string;
  search_keywords: string[];
  type: BrollType;
  transition: BrollTransition;
  placement: BrollPlacement;
  use_broll: boolean;
  asset_url: string | null;
  asset_source: BrollAssetSource | null;
  asset_status: BrollAssetStatus;
}

/* -------------------------------------------------------------------------- */
/* SubtitleSegment                                                            */
/* -------------------------------------------------------------------------- */

export interface SubtitleSegment {
  id: number;
  short_id: number;
  start: string;
  end: string;
  text: string;
  highlight_words: string[] | null;
}

/* -------------------------------------------------------------------------- */
/* RenderJob                                                                  */
/* -------------------------------------------------------------------------- */

export type RenderStatus =
  | 'queued'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type RenderStage =
  | 'downloading'
  | 'trimming'
  | 'broll'
  | 'captions'
  | 'encoding'
  | 'uploading';

export interface RenderJob {
  id: number;
  short_id: number;
  user_id: number;
  status: RenderStatus;
  progress: number;
  stage: RenderStage | null;
  output_url: string | null;
  output_format: string;
  video_codec: string;
  audio_codec: string;
  resolution: string;
  aspect_ratio: string;
  file_size_bytes: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

/* -------------------------------------------------------------------------- */
/* Auth + API helper shapes                                                   */
/* -------------------------------------------------------------------------- */

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name?: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/* -------------------------------------------------------------------------- */
/* Dashboard & Settings (Module 5)                                            */
/* -------------------------------------------------------------------------- */

export interface DashboardStats {
  projects_total: number;
  projects_ready: number;
  shorts_total: number;
  renders_total: number;
  renders_completed: number;
  storage_bytes: number;
}

export interface UsageStats {
  claude_input_tokens: number;
  claude_output_tokens: number;
  stock_api_calls: number;
  period_start: string;
  period_end: string;
}
