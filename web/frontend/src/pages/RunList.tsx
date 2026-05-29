import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import { apiGet } from '@/api';
import type { RunSummary, StrategySummary } from '@/types';

export default function RunList() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [strategy, setStrategy] = useState('');
  const [strategyNames, setStrategyNames] = useState<Record<string, string>>({});
  const navigate = useNavigate();

  useEffect(() => {
    apiGet<StrategySummary[]>('/api/v1/strategies')
      .then((data) => {
        const map: Record<string, string> = {};
        data.forEach((s) => { map[s.name] = s.display_name ?? s.name; });
        setStrategyNames(map);
      })
      .catch(() => {});
  }, []);

  const fetchRuns = (s?: string) => {
    setLoading(true);
    apiGet<RunSummary[]>('/api/v1/runs', {
      params: { limit: 50, strategy: s || undefined },
    })
      .then(setRuns)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const handleStrategyFilter = (s: string) => {
    setStrategy(s);
    fetchRuns(s);
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">运行记录</h1>

      {/* 筛选 */}
      <div className="flex gap-3">
        <button
          onClick={() => handleStrategyFilter('')}
          className={`px-3 py-1 rounded-lg text-sm ${
            !strategy
              ? 'bg-accent text-white'
              : 'bg-surface border border-border text-gray-400 hover:text-white'
          }`}
        >
          全部
        </button>
        <input
          type="text"
          placeholder="按策略名称筛选..."
          value={strategy}
          onChange={(e) => handleStrategyFilter(e.target.value)}
          className="bg-gray-900 border border-border rounded-lg px-3 py-1 text-sm focus:outline-none focus:border-accent w-64"
        />
      </div>

      {/* 列表 */}
      <div className="bg-surface rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-border">
              <th className="px-4 py-2">运行 ID</th>
              <th className="px-4 py-2">策略</th>
              <th className="px-4 py-2">创建时间</th>
              <th className="px-4 py-2">选股数</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  加载中...
                </td>
              </tr>
            ) : runs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
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
                    {run.run_id.slice(0, 12)}
                  </td>
                  <td className="px-4 py-2">
                    {strategyNames[run.strategy] ? (
                      <div>
                        <span>{strategyNames[run.strategy]}</span>
                        {strategyNames[run.strategy] !== run.strategy && (
                          <span className="text-xs text-gray-500 ml-1.5 font-mono">{run.strategy}</span>
                        )}
                      </div>
                    ) : (
                      run.strategy
                    )}
                  </td>
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
