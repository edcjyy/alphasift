import { create } from 'zustand';
import apiClient from '@/api';
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
      const data = await apiClient.post<{run_id: string | null; result: any}>('/api/v1/screen', params);
      // 解包后端返回的 {run_id, result} 结构
      const result = data.result as RunDetail;
      const runDetail: RunDetail = {
        ...result,
        run_id: data.run_id || result.run_id || '',
        created_at: result.created || result.created_at || '',
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
