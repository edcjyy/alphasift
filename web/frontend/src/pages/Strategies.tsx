import { useEffect, useState } from 'react';
import { Layers } from 'lucide-react';
import { apiGet } from '@/api';
import type { StrategySummary } from '@/types';

export default function Strategies() {
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<StrategySummary[]>('/api/v1/strategies')
      .then(setStrategies)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">策略管理</h1>

      {loading ? (
        <div className="text-center text-gray-400 py-12">加载中...</div>
      ) : strategies.length === 0 ? (
        <div className="text-center text-gray-400 py-12">
          <Layers className="w-12 h-12 mx-auto mb-3 text-gray-600" />
          暂无可用策略
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {strategies.map((s) => (
            <div
              key={s.name}
              className="bg-surface rounded-xl border border-border p-5 hover:border-accent/50 transition-colors"
            >
              <div className="flex items-start justify-between">
                <h3 className="font-semibold text-lg">{s.display_name ?? s.name}</h3>
                <span className="text-xs text-gray-500 bg-surface-active px-2 py-0.5 rounded">
                  v{s.version ?? '?'}
                </span>
              </div>
              <p className="text-gray-400 text-sm mt-2">{s.description ?? ''}</p>
              <div className="flex items-center gap-2 mt-3">
                <span className="text-xs bg-accent/10 text-accent px-2 py-0.5 rounded">
                  {s.category ?? '未分类'}
                </span>
              </div>
              {(s.tags?.length ?? 0) > 0 && (
                <div className="flex gap-1.5 flex-wrap mt-3">
                  {s.tags!.map((tag) => (
                    <span
                      key={tag}
                      className="text-xs bg-surface-active text-gray-300 px-2 py-0.5 rounded"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
