export interface Pick {
  rank: number;
  code: string;
  name: string;
  final_score: number;
  screen_score: number;
  llm_score?: number;
  ranking_reason: string;
  risk_summary: string;
  price: number;
  change_pct: number;
  amount: number;
  total_mv?: number;
  turnover_rate?: number;
  volume_ratio?: number;
  pe_ratio?: number;
  pb_ratio?: number;
  industry: string;
  concepts: string;
  factor_scores: Record<string, number>;
  risk_score?: number;
  risk_level: string;
  risk_flags: string[];
  llm_sector: string;
  llm_theme: string;
  llm_tags: string[];
  llm_catalysts: string[];
  llm_risks: string[];
}

export interface RunDetail {
  run_id: string;
  strategy: string;
  created: string;           // 后端用 created
  created_at?: string;       // 兼容
  snapshot_source?: string;
  total_candidates: number;
  picks: Pick[];
  factor_weights?: Record<string, number>;
  market?: string;
  config?: ScreenConfig;
}

export interface RunSummary {
  run_id: string;
  strategy: string;
  created_at: string;
  picks_count: number;
  snapshot_source?: string;
}

export interface StrategySummary {
  name: string;
  display_name?: string;
  description?: string;
  version?: string;
  category?: string;
  tags?: string[];
}

export interface EvaluateResult {
  run_id: string;
  strategy: string;
  evaluation_date: string;
  holding_days: number;
  results: EvaluatePickResult[];
  summary: EvaluateSummary;
  with_price_path: boolean;
}

export interface EvaluatePickResult {
  code: string;
  name: string;
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  return_pct: number;
  max_drawdown_pct: number;
  win: boolean;
}

export interface EvaluateSummary {
  total: number;
  avg_return_pct: number;
  win_rate: number;
  max_drawdown_pct: number;
  best_return_pct: number;
  worst_return_pct: number;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  details: {
    data_dir: string;
    snapshot_sources: string[] | string;
    llm_model: string;
    llm_status: string;
    dsa_url: string;
    dsa_reachable: boolean;
  };
}

export interface ScreenConfig {
  strategy: string;
  max_output?: number;
  use_llm?: boolean;
  daily_enrich?: boolean;
  post_analyzers?: string[];
  save_run?: boolean;
  explain?: boolean;
  context?: string;
}

export interface ScreenParams {
  strategy: string;
  max_output?: number;
  use_llm?: boolean;
  daily_enrich?: boolean;
  post_analyzers?: string[];
  save_run?: boolean;
  explain?: boolean;
  context?: string;
}

// ---------------------------------------------------------------------------
// 环境变量配置
// ---------------------------------------------------------------------------
export interface EnvEntry {
  key: string;
  value: string;
  masked: boolean;
}

export interface EnvUpdateRequest {
  changes: Record<string, string>;
}

export interface EnvUpdateResponse {
  status: string;
  updated: string[];
  requires_restart: boolean;
  message: string;
}
