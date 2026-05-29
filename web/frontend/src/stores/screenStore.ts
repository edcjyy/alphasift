import { create } from 'zustand';
import { apiPost } from '@/api';
import type { RunDetail, ScreenParams } from '@/types';

interface ScreenStore {
  isScreening: boolean;
  currentResult: RunDetail | null;
  error: string | null;
  startScreen: (params: ScreenParams) => Promise<void>;
  clearResult: () => void;
}

export const useScreenStore = create<ScreenStore>((set) => ({
  isScreening: false,
  currentResult: null,
  error: null,

  startScreen: async (params: ScreenParams) => {
    set({ isScreening: true, error: null });
    try {
      // 后端返回 { run_id: string; result: RunDetail }
      const data = await apiPost<{ run_id: string | null; result: any }>('/api/v1/screen', params);
      const result = data.result as RunDetail;
      const runDetail: RunDetail = {
        ...result,
        run_id: data.run_id || result.run_id || '',
        created_at: result.created || result.created_at || '',
        picks: result.picks || [],
      };
      set({ currentResult: runDetail, isScreening: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : '选股失败',
        isScreening: false,
      });
    }
  },

  clearResult: () => set({ currentResult: null, error: null }),
}));
