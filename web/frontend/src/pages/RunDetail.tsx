import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { ArrowLeft, BarChart3 } from 'lucide-react';
import apiClient from '@/api';
import type { RunDetail } from '@/types';
import PickTable from '@/components/PickTable';

const COLORS = [
  '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316',
  '#eab308', '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6',
];

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    apiClient
      .get<{run_id: string; result: any}>(`/api/v1/runs/${runId}`)
      .then((data) => {
        const r = data.result as RunDetail;
        setRun({
          ...r,
          run_id: data.run_id || runId,
          created_at: r.created || r.created_at || '',
        } as RunDetail);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center text-gray-400">
        加载中...
      </div>
    );
  }

  if (!run) {
    return (
      <div className="p-6 flex items-center justify-center text-gray-400">
        运行记录不存在
      </div>
    );
  }

  // 行业分布
  const industryMap: Record<string, number> = {};
  for (const pick of run.picks) {
    const ind = pick.industry || '未知';
    industryMap[ind] = (industryMap[ind] ?? 0) + 1;
  }
  const industryData = Object.entries(industryMap).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/runs')}
          className="text-gray-400 hover:text-white"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-2xl font-bold">运行详情</h1>
      </div>

      {/* 元信息 */}
      <div className="bg-surface rounded-xl border border-border p-4">
        <div className="grid grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-gray-500">运行 ID</div>
            <div className="font-mono text-xs mt-0.5">{run.run_id}</div>
          </div>
          <div>
            <div className="text-gray-500">策略</div>
            <div className="mt-0.5">{run.strategy}</div>
          </div>
          <div>
            <div className="text-gray-500">时间</div>
            <div className="mt-0.5">{run.created_at || run.created || ''}</div>
          </div>
          <div>
            <div className="text-gray-500">候选 / 选中</div>
            <div className="mt-0.5">
              {run.total_candidates} / {run.picks.length}
            </div>
          </div>
          {run.snapshot_source && (
            <div className="col-span-4">
              <div className="text-gray-500">数据快照</div>
              <div className="mt-0.5 font-mono text-xs">{run.snapshot_source}</div>
            </div>
          )}
        </div>
      </div>

      {/* 行业分布 + 评估按钮 */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-surface rounded-xl border border-border p-4">
          <h2 className="font-medium mb-3">行业分布</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={industryData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={2}
                dataKey="value"
                label={({ name, percent }) =>
                  `${name} ${(percent * 100).toFixed(0)}%`
                }
                labelLine={false}
              >
                {industryData.map((_entry, i) => (
                  <Cell
                    key={`cell-${i}`}
                    fill={COLORS[i % COLORS.length]!}
                  />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-surface rounded-xl border border-border p-4 flex flex-col items-center justify-center gap-4">
          <BarChart3 className="w-12 h-12 text-accent" />
          <p className="text-gray-400 text-sm">执行 T+N 评估查看收益表现</p>
          <button
            onClick={() => navigate(`/evaluate/${run.run_id}`)}
            className="px-6 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm transition-colors"
          >
            执行评估
          </button>
        </div>
      </div>

      {/* 排名表格 */}
      <div className="bg-surface rounded-xl border border-border">
        <div className="px-4 py-3 border-b border-border font-medium">
          选股排名
        </div>
        <PickTable picks={run.picks} />
      </div>
    </div>
  );
}
