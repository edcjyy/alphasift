import { useEffect, useState } from 'react';
import { Activity, Database, Brain, Server } from 'lucide-react';
import apiClient from '@/api';
import type { HealthResponse } from '@/types';

export default function Settings() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    apiClient
      .get<HealthResponse>('/api/v1/system/health')
      .then(setHealth)
      .catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>

      {/* 系统健康 */}
      <div className="bg-surface rounded-xl border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4 text-accent" />
          系统健康状态
        </h2>
        {health ? (
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">状态</span>
              <span
                className={
                  health.status === 'ok' ? 'text-fall' : 'text-rise'
                }
              >
                {health.status}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">时间戳</span>
              <span>{health.timestamp}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 flex items-center gap-1">
                <Database className="w-3 h-3" /> 数据源
              </span>
              <span>
                {Array.isArray(health.details.snapshot_sources)
                  ? health.details.snapshot_sources.join(', ')
                  : health.details.snapshot_sources}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 flex items-center gap-1">
                <Brain className="w-3 h-3" /> LLM
              </span>
              <span
                className={
                  health.details.llm_status === '已配置' ? 'text-fall' : 'text-gray-500'
                }
              >
                {health.details.llm_status === '已配置' ? '可用' : health.details.llm_status}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400 flex items-center gap-1">
                <Server className="w-3 h-3" /> DSA
              </span>
              <span
                className={
                  health.details.dsa_reachable ? 'text-fall' : 'text-rise'
                }
              >
                {health.details.dsa_reachable ? '可达 (可进行深度分析)' : '不可达'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">数据目录</span>
              <span className="font-mono text-xs">{health.details.data_dir}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">LLM 模型</span>
              <span>{health.details.llm_model}</span>
            </div>
          </div>
        ) : (
          <div className="text-gray-500 text-sm">无法获取系统健康信息</div>
        )}
      </div>

      {/* API 配置说明 */}
      <div className="bg-surface rounded-xl border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <Server className="w-4 h-4 text-accent" />
          API 端点
        </h2>
        <div className="space-y-2 text-sm font-mono">
          {[
            'POST /api/v1/screen — 执行选股',
            'GET  /api/v1/runs — 获取运行列表',
            'GET  /api/v1/runs/{run_id} — 获取运行详情',
            'POST /api/v1/evaluate/{run_id} — 执行评估',
            'GET  /api/v1/strategies — 获取策略列表',
            'GET  /api/v1/system/health — 系统健康检查',
          ].map((line) => (
            <div key={line} className="text-gray-400 py-1">
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
