import { useState } from 'react';
import type { Pick } from '@/types';
import { cn } from '@/utils/cn';
import StockChartModal from './StockChartModal';

function FactorRadar({ scores }: { scores: Record<string, number> }) {
  const keys = Object.keys(scores);
  if (keys.length === 0) return <span className="text-gray-500">-</span>;
  return (
    <div className="flex gap-1 flex-wrap max-w-[180px]">
      {keys.slice(0, 4).map((k) => (
        <span
          key={k}
          className="inline-block text-xs bg-surface-active rounded px-1.5 py-0.5"
          title={`${k}: ${scores[k]!.toFixed(2)}`}
        >
          {k} {scores[k]!.toFixed(1)}
        </span>
      ))}
      {keys.length > 4 && (
        <span className="text-xs text-gray-500">+{keys.length - 4}</span>
      )}
    </div>
  );
}

function RiskTags({ flags }: { flags: string[] }) {
  if (flags.length === 0) return <span className="text-gray-500">-</span>;
  return (
    <div className="flex gap-1 flex-wrap max-w-[120px]">
      {flags.map((f) => (
        <span key={f} className="inline-block text-xs text-rise bg-rise/10 rounded px-1.5 py-0.5">
          {f}
        </span>
      ))}
    </div>
  );
}

export default function PickTable({ picks }: { picks: Pick[] }) {
  const [chartStock, setChartStock] = useState<{ code: string; name: string } | null>(null);

  return (
    <>
    <div className="overflow-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-gray-500 border-b border-border sticky top-0 bg-surface">
          <tr>
            <th className="px-3 py-2 w-10">#</th>
            <th className="px-3 py-2">代码</th>
            <th className="px-3 py-2">名称</th>
            <th className="px-3 py-2">综合分</th>
            <th className="px-3 py-2">筛选分</th>
            <th className="px-3 py-2">LLM分</th>
            <th className="px-3 py-2">涨幅</th>
            <th className="px-3 py-2">行业</th>
            <th className="px-3 py-2">因子雷达</th>
            <th className="px-3 py-2">风险标签</th>
            <th className="px-3 py-2 w-28">操作</th>
          </tr>
        </thead>
        <tbody>
          {picks.map((p) => (
            <tr
              key={p.code}
              className="border-b border-border hover:bg-surface-hover"
            >
              <td className="px-3 py-2 text-gray-400">{p.rank}</td>
              <td className="px-3 py-2 font-mono">{p.code}</td>
              <td className="px-3 py-2 font-medium">{p.name}</td>
              <td className="px-3 py-2">{p.final_score.toFixed(2)}</td>
              <td className="px-3 py-2">{p.screen_score.toFixed(2)}</td>
              <td className="px-3 py-2">{p.llm_score?.toFixed(2) ?? '-'}</td>
              <td
                className={cn(
                  'px-3 py-2 font-medium',
                  p.change_pct >= 0 ? 'text-rise' : 'text-fall',
                )}
              >
                {p.change_pct >= 0 ? '+' : ''}
                {p.change_pct.toFixed(2)}%
              </td>
              <td className="px-3 py-2 text-gray-400">{p.industry}</td>
              <td className="px-3 py-2">
                <FactorRadar scores={p.factor_scores} />
              </td>
              <td className="px-3 py-2">
                <RiskTags flags={p.risk_flags} />
              </td>
              <td className="px-3 py-2">
                <div className="flex gap-1.5">
                  <button
                    onClick={() => setChartStock({ code: p.code, name: p.name })}
                    className="text-xs text-blue-400 hover:text-blue-300 px-1.5 py-0.5 rounded hover:bg-surface-active"
                  >
                    K线
                  </button>
                  <button
                    onClick={() => window.open(`http://192.168.31.100:19500/chat?stock=${p.code}`, '_blank')}
                    className="text-xs text-accent hover:text-accent-hover px-1.5 py-0.5 rounded hover:bg-surface-active"
                  >
                    深度分析
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    {chartStock && (
      <StockChartModal
        code={chartStock.code}
        name={chartStock.name}
        onClose={() => setChartStock(null)}
      />
    )}
    </>
  );
}
