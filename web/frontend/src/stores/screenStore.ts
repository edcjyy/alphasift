import { create } from 'zustand';
import { apiPost, apiGet } from '@/api';
import type { RunDetail, ScreenParams } from '@/types';

interface ScreenProgress {
  task_id: string;
  stage: string;
  message: string;
  pct: number;
  stages: string[];
}

interface ScreenStore {
  isScreening: boolean;
  currentResult: RunDetail | null;
  error: string | null;
  progress: ScreenProgress | null;
  startScreen: (params: ScreenParams) => Promise<void>;
  clearResult: () => void;
}

const STAGE_LABELS: Record<string, string> = {
  init: '初始化',
  loading_strategy: '加载策略',
  fetching_snapshot: '获取行情',
  applying_filters: '筛选股票',
  enriching_daily: '补充日线',
  scoring: '因子评分',
  llm_ranking: 'LLM排序',
  post_analysis: '后置分析',
  saving: '保存结果',
  done: '完成',
  error: '错误',
};

export function getStageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage;
}

export const useScreenStore = create<ScreenStore>((set) => ({
  isScreening: false,
  currentResult: null,
  error: null,
  progress: null,

  startScreen: async (params: ScreenParams) => {
    set({ isScreening: true, error: null, progress: null });
    try {
      const data = await apiPost<{ run_id: string | null; result: any; task_id?: string }>(
        '/api/v1/screen',
        params,
        { timeout: 600000 },
      );
      const result = data.result as RunDetail;
      const runDetail: RunDetail = {
        ...result,
        run_id: data.run_id || result.run_id || '',
        created_at: result.created || result.created_at || '',
        picks: result.picks || [],
      };
      set({ currentResult: runDetail, isScreening: false, progress: null });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '选股失败',
        isScreening: false,
        progress: null,
      });
    }
  },

  clearResult: () => set({ currentResult: null, error: null, progress: null }),
}));
