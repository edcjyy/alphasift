import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Loader2, AlertCircle } from 'lucide-react';
import { useScreenStore } from '@/stores/screenStore';
import { apiGet } from '@/api';
import type { StrategySummary } from '@/types';
import PickTable from '@/components/PickTable';

export default function Screen() {
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [strategy, setStrategy] = useState('');
  const [maxOutput, setMaxOutput] = useState(20);
  const [useLlm, setUseLlm] = useState(false);
  const [dailyEnrich, setDailyEnrich] = useState(false);
  const [saveRun, setSaveRun] = useState(true);

  const { isScreening, currentResult, error, startScreen, clearResult } =
    useScreenStore();
  const navigate = useNavigate();

  // name → display_name 映射
  const strategyNames = useMemo(() => {
    const map: Record<string, string> = {};
    strategies.forEach((s) => { map[s.name] = s.display_name ?? s.name; });
    return map;
  }, [strategies]);

  useEffect(() => {
    apiGet<StrategySummary[]>('/api/v1/strategies')
      .then((data) => {
        setStrategies(data);
        if (data.length > 0) setStrategy(data[0]!.name);
      })
      .catch(() => {});
  }, []);

  const handleScreen = () => {
    if (!strategy) return;
    startScreen({
      strategy,
      max_output: maxOutput,
      use_llm: useLlm,
      daily_enrich: dailyEnrich,
      save_run: saveRun,
    });
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">选股面板</h1>

      {/* 参数面板 */}
      <div className="bg-surface rounded-xl border border-border p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          {/* 策略选择 */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">策略</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full bg-gray-900 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
            >
              {strategies.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.display_name}
                </option>
              ))}
            </select>
          </div>

          {/* 最大输出 */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">最大输出数</label>
            <input
              type="number"
              min={1}
              max={100}
              value={maxOutput}
              onChange={(e) => setMaxOutput(Number(e.target.value))}
              className="w-full bg-gray-900 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
            />
          </div>
        </div>

        {/* 开关选项 */}
        <div className="flex gap-6">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={useLlm}
              onChange={(e) => setUseLlm(e.target.checked)}
              className="accent-accent w-4 h-4"
            />
            使用 LLM 增强
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={dailyEnrich}
              onChange={(e) => setDailyEnrich(e.target.checked)}
              className="accent-accent w-4 h-4"
            />
            日线数据补充
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={saveRun}
              onChange={(e) => setSaveRun(e.target.checked)}
              className="accent-accent w-4 h-4"
            />
            保存运行
          </label>
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-3">
          <button
            onClick={handleScreen}
            disabled={isScreening || !strategy}
            className="flex items-center gap-2 px-5 py-2 bg-accent hover:bg-accent-hover disabled:bg-gray-700 text-white rounded-lg text-sm transition-colors"
          >
            {isScreening ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {isScreening ? '选股中...' : '开始选股'}
          </button>
          {currentResult && (
            <button
              onClick={clearResult}
              className="px-4 py-2 border border-border hover:bg-surface-hover rounded-lg text-sm transition-colors"
            >
              清除结果
            </button>
          )}
        </div>

        {error && (
          <div className="flex items-center gap-2 text-rise text-sm">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}
      </div>

      {/* 结果 */}
      {currentResult && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">选股结果</h2>
            <div className="flex gap-3 text-sm text-gray-400">
              <span>策略: {strategyNames[currentResult.strategy] ?? currentResult.strategy}</span>
              <span>时间: {currentResult.created_at}</span>
              <span>候选: {currentResult.total_candidates}</span>
              <button
                onClick={() => navigate(`/evaluate/${currentResult.run_id}`)}
                className="text-accent hover:text-accent-hover"
              >
                执行评估
              </button>
            </div>
          </div>
          <div className="bg-surface rounded-xl border border-border">
            <PickTable picks={currentResult.picks} />
          </div>
        </div>
      )}
    </div>
  );
}
