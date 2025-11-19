/**
 * TypeScript types for the application
 */

export enum RunStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

export enum RecordStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  ERROR = 'error'
}

export enum Label {
  PURE_BODYWEAR = 'Pure Bodywear',
  BODYWEAR_LEANING = 'Bodywear Leaning',
  NEEDS_REVIEW = 'Needs Review',
  GENERALIST = 'Generalist',
  ERROR = 'Error'
}

export interface Run {
  id: number
  name: string
  status: RunStatus
  total_records: number
  processed_records: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  progress_percentage: number
}

export interface RunStatusResponse {
  id: number
  name: string
  status: RunStatus
  total_records: number
  processed_records: number
  progress_percentage: number
  eta_seconds: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface ClassificationRecord {
  id: number
  run_id: number
  domain: string
  label: Label | null
  confidence: number | null
  text_score: number | null
  vision_score: number | null
  reasons: string | null
  stage_used: string | null
  image_count: number
  http_status: number | null
  final_url: string | null
  nav_count: number
  heading_count: number
  error: string | null
  status: RecordStatus
  created_at: string
  started_at: string | null
  processed_at: string | null
  is_overridden: boolean
}

export interface RunStatistics {
  total_records: number
  completed_records: number
  error_records: number
  label_distribution: Record<string, number>
  stage_distribution: Record<string, number>
  average_confidence: number | null
  average_processing_time_seconds: number | null
}

export interface PaginatedResponse<T> {
  records?: T[]
  runs?: T[]
  total: number
  page: number
  page_size: number
}
