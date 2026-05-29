import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  ScatterChart, Scatter, ZAxis,
} from 'recharts';
import { ArrowLeft, BarChart3, TrendingUp, Activity, Brain } from 'lucide-react';
import { apiGet } from '@/api';
import type { RunDetail } from '@/types';
import PickTable from '@/components/PickTable';

const COLORS = [
  '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316',
  '#eab308', '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6',
];

/** 将数值按区间分组 */
function bucketData(values: number[], bins: number[], labels: string[]) {
  const counts = new Array(bins.length - 1).fill(0);
  for (const v of values) {
    for (let i = 0; i < bins.length - 1; i++) {
      const lo = bins[i]!;
      const hi = bins[i + 1]!;
      if (v >= lo && (i === bins.length - 2 ? v <= hi : v < hi)) {
        counts[i]++;
        break;
      }
    }
  }
  return counts.map((c, i) => ({ name: labels[i] ?? `${bins[i]}-${bins[i + 1]}`, count: c }));
}

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    apiGet<{ run_id: string; result: any }>(`/api/v1/runs/${runId}`)
      .then((data) => {
        const r = data.result as RunDetail;
        setRun({
          ...r,
          run_id: data.run_id || runId,
          created_at: r.created || r.created_at || '',
          picks: r.picks || [],
        } as RunDetail);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center text-gray-400">加载中...</div>
    );
  }
  if (!run) {
    return (
      <div className="p-6 flex items-center justify-center text-gray-400">运行记录不存在</div>
    );
  }

  // ---- 数据处理 ----
  const picks = run.picks;

  // 行业分布
  const industryMap: Record<string, number> = {};
  for (const pick of picks) {
    const ind = pick.industry || '未知';
    industryMap[ind] = (industryMap[ind] ?? 0) + 1;
  }
  const industryData = Object.entries(industryMap).map(([name, value]) => ({ name, value }));

  // 涨跌幅分布
  const changePcts = picks.map((p) => p.change_pct).filter((v) => v !== undefined && !isNaN(v));
  const changeBins = [-10, -5, -3, -1, 0, 1, 3, 5, 10];
  const changeLabels = ['<-5', '-5~-3', '-3~-1', '-1~0', '0~1', '1~3', '3~5', '>5'];
  const changeData = bucketData(changePcts, changeBins, changeLabels);

  // 得分分布
  const scores = picks.map((p) => p.final_score).filter((v) => !isNaN(v));
  const scoreBins = [0, 20, 40, 60, 70, 80, 90, 100];
  const scoreLabels = ['0-20', '20-40', '40-60', '60-70', '70-80', '80-90', '90-100'];
  const scoreData = bucketData(scores, scoreBins, scoreLabels);

  // LLM 评分 vs 筛选评分（仅当有 LLM 评分时）
  const hasLLM = picks.some((p) => p.llm_score !== undefined && p.llm_score !== null);
  const scatterData = picks
    .filter((p) => p.llm_score !== undefined && p.llm_score !== null)
    .map((p) => ({
      x: p.screen_score ?? 0,
      y: p.llm_score! * 100,   // LLM 分数归一化到 0-100
      name: p.name,
      code: p.code,
    }));

  // ---- UI ----
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/runs')} className="text-gray-400 hover:text-white">
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
            <div className="mt-0.5">{run.total_candidates} / {picks.length}</div>
          </div>
          {run.snapshot_source && (
            <div className="col-span-4">
              <div className="text-gray-500">数据快照</div>
              <div className="mt-0.5 font-mono text-xs">{run.snapshot_source}</div>
            </div>
          )}
        </div>
      </div>

      {/* ================================================================ */}
      {/* Phase 2 图表增强区域                                                 */}
      {/* ================================================================ */}

      {/* Row 1: 涨跌幅分布 + 行业分布 */}
      <div className="grid grid-cols-2 gap-4">
        {/* 涨跌幅分布 */}
        <div className="bg-surface rounded-xl border border-border p-4">
          <h2 className="font-medium mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-amber-400" />
            涨跌幅分布
          </h2>
          {changePcts.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={changeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  formatter={(v) => [`${v} 只`, '数量']}
                  contentStyle={{ background: '#1e1e2e', border: '1px solid #2e2e42', borderRadius: '8px' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {changeData.map((entry, i) => {
                    const label = entry.name;
                    const isGreen = label.includes('-') && !label.startsWith('>');
                    return (
                      <Cell
                        key={`cell-${i}`}
                        fill={isGreen ? '#22c55e' : '#ef4444'}
                      />
                    );
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-gray-500 text-sm py-10 text-center">无涨跌幅数据</div>
          )}
        </div>

        {/* 行业分布 */}
        <div className="bg-surface rounded-xl border border-border p-4">
          <h2 className="font-medium mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-accent" />
            行业分布
          </h2>
          {industryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={industryData}
                  cx="50%" cy="50%"
                  innerRadius={60} outerRadius={100}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, percent }: { name?: string; percent?: number }) =>
                    `${name ?? '?'} ${((percent ?? 0) * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {industryData.map((_entry, i) => (
                    <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]!} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-gray-500 text-sm py-10 text-center">无行业数据</div>
          )}
        </div>
      </div>

      {/* Row 2: 得分分布 + 评估入口（始终可见） */}
      <div className="grid grid-cols-2 gap-4">
        {/* 得分分布 */}
        <div className="bg-surface rounded-xl border border-border p-4">
          <h2 className="font-medium mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-blue-400" />
            综合得分分布
          </h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={scoreData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
              <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} allowDecimals={false} />
              <Tooltip
                formatter={(v) => [`${v} 只`, '数量']}
                contentStyle={{ background: '#1e1e2e', border: '1px solid #2e2e42', borderRadius: '8px' }}
              />
              <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* 评估入口 — 始终显示 */}
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

      {/* Row 3: LLM 散点图（仅当有 LLM 评分时显示） */}
      {hasLLM && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-surface rounded-xl border border-border p-4">
            <h2 className="font-medium mb-3 flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-400" />
              LLM 评分 vs 筛选评分
            </h2>
            <ResponsiveContainer width="100%" height={280}>
              <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2e2e42" />
                <XAxis
                  dataKey="x" name="筛选评分"
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  label={{ value: '筛选评分', position: 'bottom', fill: '#9ca3af', fontSize: 11 }}
                />
                <YAxis
                  dataKey="y" name="LLM评分"
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  label={{ value: 'LLM 评分', angle: -90, position: 'left', fill: '#9ca3af', fontSize: 11 }}
                />
                <ZAxis range={[60, 60]} />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ active, payload }: any) => {
                    if (active && payload?.[0]) {
                      const p = payload[0].payload;
                      return (
                        <div className="bg-gray-800 border border-gray-700 rounded-lg p-2 text-xs">
                          <div className="font-medium">{p.name} ({p.code})</div>
                          <div>筛选: {p.x.toFixed(1)} / LLM: {p.y.toFixed(1)}</div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Scatter data={scatterData} fill="#a78bfa" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 排名表格 */}
      <div className="bg-surface rounded-xl border border-border">
        <div className="px-4 py-3 border-b border-border font-medium">选股排名</div>
        <PickTable picks={picks} />
      </div>
    </div>
  );
}
