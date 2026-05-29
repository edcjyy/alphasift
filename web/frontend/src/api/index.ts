import axios from 'axios';

/**
 * 原始 axios 实例（无响应拦截器包装）
 * 所有请求返回 AxiosResponse，由调用方通过 .then(r => r.data) 提取
 */
const api = axios.create({
  baseURL: '',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
});

export default api;

// ---------------------------------------------------------------------------
// 类型安全的 API 封装（返回体 = res.data，无需关心 AxiosResponse）
// ---------------------------------------------------------------------------

/** GET */
export async function apiGet<T>(url: string, config?: any): Promise<T> {
  const res = await api.get<T>(url, config);
  return res.data;
}

/** POST */
export async function apiPost<T>(url: string, data?: unknown, config?: any): Promise<T> {
  const res = await api.post<T>(url, data, config);
  return res.data;
}

/** PUT */
export async function apiPut<T>(url: string, data?: unknown, config?: any): Promise<T> {
  const res = await api.put<T>(url, data, config);
  return res.data;
}

/** DELETE */
export async function apiDelete<T>(url: string, config?: any): Promise<T> {
  const res = await api.delete<T>(url, config);
  return res.data;
}

// ---------------------------------------------------------------------------
// 环境变量 API
// ---------------------------------------------------------------------------

import type { EnvEntry, EnvUpdateResponse } from '@/types';

/** 获取所有可配置的环境变量（敏感值已脱敏） */
export async function fetchEnv(): Promise<EnvEntry[]> {
  return apiGet<EnvEntry[]>('/api/v1/system/env');
}

/** 更新环境变量 */
export async function updateEnv(changes: Record<string, string>): Promise<EnvUpdateResponse> {
  return apiPut<EnvUpdateResponse>('/api/v1/system/env', { changes });
}
