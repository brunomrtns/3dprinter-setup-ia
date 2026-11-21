export type AssetMode = 'single' | 'multi' | 'mesh';

export type JobStatus =
  | 'draft'
  | 'queued'
  | 'claimed'
  | 'running'
  | 'review'
  | 'published'
  | 'rejected'
  | 'failed';

export type JobStage =
  | 'preprocess'
  | 'shape'
  | 'paint'
  | 'pbr'
  | 'pack'
  | 'qa'
  | 'edit';

export interface AssetSummary {
  id: string;
  name: string;
  mode: AssetMode;
  status: string;
  currentVersion: number;
  thumbnailUrl?: string | null;
  createdAt: string;
}

export interface QaGate {
  value: unknown;
  threshold: string;
  pass: boolean;
}

export interface QaReport {
  overall_pass: boolean;
  gates: Record<string, QaGate>;
  tempo_total_s?: number;
  vram_pico_mib?: number;
}
