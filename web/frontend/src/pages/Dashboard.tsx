import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, ExternalLink } from 'lucide-react';
import { apiGet } from '@/api';
import type { RunSummary, HealthResponse } from '@/types';

export default function Dashboard() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    apiGet<RunSummary[]>('/api/v1/runs', { params: { limit: 5 } })
      .then(setRuns)
      .catch(() => {});
    apiGet<HealthResponse>('/api/v1/system/health')
      .then(setHealth)
      .catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <button
          onClick={() => navigate('/screen')}
          className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          快捷选股
        </button>
      </div>

      {/* 系统状态卡片 */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-surface rounded-xl p-4 border border-border">
          <div className="text-sm text-gray-400">系统状态</div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                health?.status === 'ok' ? 'bg-fall' : 'bg-rise'
              }`}
            />
            <span className="text-lg font-medium">
              {health?.status === 'ok' ? '正常运行' : '异常'}
            </span>
          </div>
        </div>
        <div className="bg-surface rounded-xl p-4 border border-border">
          <div className="text-sm text-gray-400">数据源</div>
          <div className="text-lg font-medium mt-1">
            {health?.details
              ? Array.isArray(health.details.snapshot_sources)
                ? health.details.snapshot_sources.join(',')
                : health.details.snapshot_sources
              : '-'}
          </div>
        </div>
        <div className="bg-surface rounded-xl p-4 border border-border">
          <div className="text-sm text-gray-400">LLM 状态</div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                health?.details?.llm_status === '已配置' ? 'bg-fall' : 'bg-gray-600'
              }`}
            />
            <span className="text-lg font-medium">
              {health?.details?.llm_status === '已配置' ? '可用' : '不可用'}
            </span>
          </div>
        </div>
      </div>

      {/* 最近运行 */}
      <div className="bg-surface rounded-xl border border-border">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="font-medium">最近运行</h2>
          <button
            onClick={() => navigate('/runs')}
            className="text-sm text-accent hover:text-accent-hover flex items-center gap-1"
          >
            查看全部 <ExternalLink className="w-3 h-3" />
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-border">
              <th className="px-4 py-2">运行 ID</th>
              <th className="px-4 py-2">策略</th>
              <th className="px-4 py-2">时间</th>
              <th className="px-4 py-2">选股数</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  暂无运行记录
                </td>
              </tr>
            ) : (
              runs.map((run) => (
                <tr
                  key={run.run_id}
                  className="border-b border-border hover:bg-surface-hover cursor-pointer"
                  onClick={() => navigate(`/runs/${run.run_id}`)}
                >
                  <td className="px-4 py-2 font-mono text-xs">
                    {run.run_id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-2">{run.strategy}</td>
                  <td className="px-4 py-2 text-gray-400">{run.created_at}</td>
                  <td className="px-4 py-2">{run.picks_count}</td>
                  <td className="px-4 py-2">
                    <ExternalLink className="w-4 h-4 text-gray-500" />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
