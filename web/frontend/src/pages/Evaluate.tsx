import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { apiPost } from '@/api';
import type { EvaluateResult } from '@/types';
import { cn } from '@/utils/cn';
import StockChartModal from '@/components/StockChartModal';

export default function Evaluate() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [result, setResult] = useState<EvaluateResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [chartStock, setChartStock] = useState<{ code: string; name: string } | null>(null);

  const handleEvaluate = () => {
    if (!runId) return;
    setLoading(true);
    setError('');
    // 后端返回 { run_id: string; result: EvaluateResult }
    apiPost<{ run_id: string; result: any }>(`/api/v1/evaluate/${runId}`, {
      with_price_path: true,
    }, { timeout: 300000 })
      .then((data) => {
        setResult(data.result as EvaluateResult);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="text-gray-400 hover:text-white"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-2xl font-bold">T+N 评估</h1>
      </div>

      {/* 操作 */}
      {!result && (
        <div className="bg-surface rounded-xl border border-border p-5 space-y-3">
          <p className="text-gray-400 text-sm">
            对运行 <span className="font-mono">{runId}</span> 执行回测评估，计算持有期收益率。
          </p>
          <button
            onClick={handleEvaluate}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 bg-accent hover:bg-accent-hover disabled:bg-gray-700 text-white rounded-lg text-sm transition-colors"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? '评估中...' : '执行评估'}
          </button>
          {error && <div className="text-rise text-sm">{error}</div>}
        </div>
      )}

      {/* 评估结果 */}
      {result && (
        <>
          {/* 汇总卡片 */}
          <div className="grid grid-cols-5 gap-4">
            <div className="bg-surface rounded-xl border border-border p-4">
              <div className="text-sm text-gray-400">标的数</div>
              <div className="text-xl font-bold mt-1">
                {result.summary.total}
              </div>
            </div>
            <div className="bg-surface rounded-xl border border-border p-4">
              <div className="text-sm text-gray-400">平均收益</div>
              <div
                className={cn(
                  'text-xl font-bold mt-1',
                  result.summary.avg_return_pct >= 0
                    ? 'text-rise'
                    : 'text-fall',
                )}
              >
                {result.summary.avg_return_pct >= 0 ? '+' : ''}
                {result.summary.avg_return_pct.toFixed(2)}%
              </div>
            </div>
            <div className="bg-surface rounded-xl border border-border p-4">
              <div className="text-sm text-gray-400">胜率</div>
              <div className="text-xl font-bold mt-1">
                {(result.summary.win_rate * 100).toFixed(1)}%
              </div>
            </div>
            <div className="bg-surface rounded-xl border border-border p-4">
              <div className="text-sm text-gray-400">最大回撤</div>
              <div className="text-xl font-bold mt-1 text-rise">
                {result.summary.max_drawdown_pct.toFixed(2)}%
              </div>
            </div>
            <div className="bg-surface rounded-xl border border-border p-4">
              <div className="text-sm text-gray-400">持有天数</div>
              <div className="text-xl font-bold mt-1">
                {result.holding_days}D
              </div>
            </div>
          </div>

          {/* 收益率柱状图 */}
          <div className="bg-surface rounded-xl border border-border p-4">
            <h2 className="font-medium mb-3">个股收益率</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={result.results}>
                <XAxis
                  dataKey="name"
                  tick={{ fill: '#9ca3af', fontSize: 12 }}
                />
                <YAxis
                  tick={{ fill: '#9ca3af', fontSize: 12 }}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  formatter={(v) => [`${(v as number).toFixed(2)}%`, '收益率']}
                  contentStyle={{
                    background: '#1e1e2e',
                    border: '1px solid #2e2e42',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="return_pct" radius={[4, 4, 0, 0]}>
                  {result.results.map((entry, i) => (
                    <Cell
                      key={`cell-${i}`}
                      fill={entry.return_pct >= 0 ? '#ef4444' : '#22c55e'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 评估表格 */}
          <div className="bg-surface rounded-xl border border-border overflow-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-gray-500 border-b border-border sticky top-0 bg-surface">
                <tr>
                  <th className="px-4 py-2">代码</th>
                  <th className="px-4 py-2">名称</th>
                  <th className="px-4 py-2">入场日期</th>
                  <th className="px-4 py-2">入场价</th>
                  <th className="px-4 py-2">出场日期</th>
                  <th className="px-4 py-2">出场价</th>
                  <th className="px-4 py-2">收益率</th>
                  <th className="px-4 py-2">最大回撤</th>
                  <th className="px-4 py-2">胜负</th>
                  <th className="px-4 py-2 w-12"></th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((r) => (
                  <tr
                    key={r.code}
                    className="border-b border-border hover:bg-surface-hover"
                  >
                    <td className="px-4 py-2 font-mono">{r.code}</td>
                    <td className="px-4 py-2">{r.name}</td>
                    <td className="px-4 py-2 text-gray-400">{r.entry_date}</td>
                    <td className="px-4 py-2">{r.entry_price.toFixed(2)}</td>
                    <td className="px-4 py-2 text-gray-400">{r.exit_date}</td>
                    <td className="px-4 py-2">{r.exit_price.toFixed(2)}</td>
                    <td
                      className={cn(
                        'px-4 py-2 font-medium',
                        r.return_pct >= 0 ? 'text-rise' : 'text-fall',
                      )}
                    >
                      {r.return_pct >= 0 ? '+' : ''}
                      {r.return_pct.toFixed(2)}%
                    </td>
                    <td className="px-4 py-2 text-rise">
                      {r.max_drawdown_pct.toFixed(2)}%
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded text-xs',
                          r.win
                            ? 'bg-rise/10 text-rise'
                            : 'bg-fall/10 text-fall',
                        )}
                      >
                        {r.win ? '盈利' : '亏损'}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => setChartStock({ code: r.code, name: r.name })}
                        className="text-xs text-blue-400 hover:text-blue-300 px-1.5 py-0.5 rounded hover:bg-surface-active"
                      >
                        K线
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {chartStock && (
        <StockChartModal
          code={chartStock.code}
          name={chartStock.name}
          onClose={() => setChartStock(null)}
        />
      )}
    </div>
  );
}
