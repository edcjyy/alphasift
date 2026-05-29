import { useEffect, useState } from 'react';
import {
  Brain, History, BarChart3, Play, AlertCircle, RefreshCw,
  Eye, Check, X, ArrowRight, Lightbulb, TrendingUp, Zap,
} from 'lucide-react';
import { apiGet, apiPost } from '@/api';
import type { StrategySummary } from '@/types';

// --- Types ---

interface StrategyChange {
  change_type: string;
  target: string;
  old_value: string;
  new_value: string;
  reason: string;
  confidence: number;
}

interface ReflectionResult {
  run_id: string;
  strategy: string;
  diagnosis: string;
  summary: string;
  changes: StrategyChange[];
  passed_count: number;
  rejected_count: number;
  critic_score: number;
  applied: boolean;
  win_rate: number | null;
  avg_return_pct: number | null;
  pick_count: number;
}

interface HistoryRecord {
  id: number;
  strategy: string;
  run_id: string;
  timestamp: string;
  win_rate_before: number | null;
  diagnosis: string;
  changes: { change_type: string; target: string; old_value: string; new_value: string }[];
  improved: boolean | null;
}

interface MetaLearnData {
  total_records: number;
  total_strategies: number;
  overall_success_rate: number;
  change_stats: { change_type: string; count: number; improved_count: number; success_rate: number }[];
  recommendations: string[];
}

interface RunSummary { run_id: string; strategy: string; created_at: string; picks_count: number; }

// --- Constants ---

const TABS = [
  { key: 'reflect', label: '策略反思', icon: Brain, desc: 'LLM 分析评估结果并提出参数修改建议' },
  { key: 'history', label: '进化历史', icon: History, desc: '查看策略的进化记录和修改轨迹' },
  { key: 'metalearn', label: '元学习', icon: BarChart3, desc: '从历史中学习最优进化策略' },
] as const;
type TabKey = (typeof TABS)[number]['key'];

const CHANGE_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  ADJUST_WEIGHT: { label: '调整权重', color: 'text-blue-400 bg-blue-400/10' },
  MODIFY_FILTER: { label: '修改筛选', color: 'text-purple-400 bg-purple-400/10' },
  UPDATE_REGIME: { label: '更新Regime', color: 'text-amber-400 bg-amber-400/10' },
  MODIFY_SCORECARD: { label: '修改评分', color: 'text-green-400 bg-green-400/10' },
  MODIFY_RISK: { label: '修改风险', color: 'text-red-400 bg-red-400/10' },
};

// --- Helpers ---

const fmtPct = (v: number | null) => (v != null ? `${(v * 100).toFixed(1)}%` : '-');

// --- Main Component ---

export default function Evolution() {
  const [tab, setTab] = useState<TabKey>('reflect');
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);

  useEffect(() => {
    apiGet<RunSummary[]>('/api/v1/runs', { params: { limit: 30 } }).then(setRuns).catch(() => {});
    apiGet<StrategySummary[]>('/api/v1/strategies').then(setStrategies).catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Brain className="w-7 h-7 text-accent" />
        <h1 className="text-2xl font-bold">策略进化</h1>
      </div>

      {/* Tab Bar */}
      <div className="flex gap-1 bg-surface rounded-xl border border-border p-1">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-medium transition-colors ${
                active ? 'bg-accent text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>
      <p className="text-sm text-gray-500 -mt-4">
        {TABS.find((t) => t.key === tab)?.desc}
      </p>

      {/* Tab Content */}
      {tab === 'reflect' && <ReflectTab runs={runs} />}
      {tab === 'history' && <HistoryTab strategies={strategies} />}
      {tab === 'metalearn' && <MetaLearnTab />}
    </div>
  );
}

// =============================================================================
// Reflect Tab
// =============================================================================

function ReflectTab({ runs }: { runs: RunSummary[] }) {
  const [selectedRun, setSelectedRun] = useState('');
  const [minConfidence, setMinConfidence] = useState(0.6);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<ReflectionResult | null>(null);
  const [error, setError] = useState('');

  const handleAnalyze = async () => {
    if (!selectedRun) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await apiPost<ReflectionResult>('/api/v1/reflection/analyze', {
        run_id: selectedRun,
        apply: false,
        dry_run: false,
        min_confidence: minConfidence,
      });
      setResult(res);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? '分析失败');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (!selectedRun) return;
    if (!confirm('确认应用 LLM 建议的修改？策略文件将自动备份为 .yaml.bak。')) return;
    setApplying(true);
    try {
      const res = await apiPost<ReflectionResult>('/api/v1/reflection/analyze', {
        run_id: selectedRun,
        apply: true,
        dry_run: false,
        min_confidence: minConfidence,
      });
      setResult(res);
      setError('');
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? '应用失败');
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Controls */}
      <div className="bg-surface rounded-xl border border-border p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">选择评估记录</label>
            <select
              value={selectedRun}
              onChange={(e) => setSelectedRun(e.target.value)}
              className="w-full bg-gray-900 border border-border rounded-lg px-3 py-2 text-sm"
            >
              <option value="">-- 选择 run_id --</option>
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id.slice(0, 12)} — {r.strategy} ({r.created_at?.slice(0, 10)})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              最低置信度: {minConfidence.toFixed(2)}
            </label>
            <input
              type="range"
              min={0.1}
              max={1.0}
              step={0.05}
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
              className="w-full accent-accent"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-0.5">
              <span>冒险 (0.1)</span>
              <span>保守 (1.0)</span>
            </div>
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={handleAnalyze}
            disabled={loading || !selectedRun}
            className="flex items-center gap-2 bg-accent hover:bg-accent/80 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm transition-colors"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {loading ? '分析中...' : '开始分析'}
          </button>
          {result && result.changes.length > 0 && !result.applied && (
            <button
              onClick={handleApply}
              disabled={applying}
              className="flex items-center gap-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm transition-colors"
            >
              {applying ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              应用修改
            </button>
          )}
        </div>
        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4" /> {error}
          </div>
        )}
      </div>

      {/* Guidance */}
      {!result && !loading && (
        <div className="bg-surface rounded-xl border border-border p-5 space-y-3">
          <h3 className="font-semibold flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-amber-400" />
            使用说明
          </h3>
          <div className="text-sm text-gray-400 space-y-2">
            <p>1. 先运行一次选股并保存评估结果：<code className="text-accent bg-surface-active px-1.5 py-0.5 rounded text-xs">alphasift screen strategy --save-run</code></p>
            <p>2. 评估该次选股结果：<code className="text-accent bg-surface-active px-1.5 py-0.5 rounded text-xs">alphasift evaluate &lt;run_id&gt; --save</code></p>
            <p>3. 在上方选择 run_id 后点击「开始分析」—— LLM 将自动诊断问题并提出修改建议</p>
            <p>4. 查看建议后点击「应用修改」自动更新策略 YAML（自动备份）</p>
            <p>5. 重新选股验证改进效果，形成「选股 → 评估 → 反思 → 改进」闭环</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Score Card */}
          <div className="bg-surface rounded-xl border border-border p-5">
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-accent">{fmtPct(result.win_rate)}</div>
                <div className="text-xs text-gray-500 mt-0.5">胜率</div>
              </div>
              <div>
                <div className={`text-2xl font-bold ${(result.avg_return_pct ?? 0) >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {(result.avg_return_pct ?? 0).toFixed(2)}%
                </div>
                <div className="text-xs text-gray-500 mt-0.5">平均收益</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{result.pick_count}</div>
                <div className="text-xs text-gray-500 mt-0.5">选股数</div>
              </div>
              <div>
                <div className={`text-2xl font-bold ${result.critic_score >= 0.7 ? 'text-green-400' : 'text-amber-400'}`}>
                  {(result.critic_score * 100).toFixed(0)}%
                </div>
                <div className="text-xs text-gray-500 mt-0.5">审核评分</div>
              </div>
            </div>
          </div>

          {/* Diagnosis */}
          <div className="bg-surface rounded-xl border border-border p-5">
            <h3 className="font-semibold flex items-center gap-2 mb-2">
              <Zap className="w-4 h-4 text-yellow-400" />
              诊断结论
            </h3>
            <p className="text-sm text-gray-300 leading-relaxed">{result.diagnosis || '无诊断结论'}</p>
          </div>

          {/* Changes */}
          {result.changes.length > 0 && (
            <div className="bg-surface rounded-xl border border-border p-5">
              <h3 className="font-semibold flex items-center gap-2 mb-3">
                <ArrowRight className="w-4 h-4 text-accent" />
                建议修改 ({result.changes.length} 个)
              </h3>
              <div className="space-y-3">
                {result.changes.map((c, i) => {
                  const typeInfo = CHANGE_TYPE_LABELS[c.change_type] ?? { label: c.change_type, color: 'text-gray-400 bg-gray-400/10' };
                  return (
                    <div key={i} className="flex items-start gap-3 p-3 bg-gray-900/50 rounded-lg border border-border">
                      <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${typeInfo.color}`}>{typeInfo.label}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-mono">{c.target}</div>
                        <div className="flex items-center gap-2 mt-1 text-xs">
                          <span className="text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded">{c.old_value}</span>
                          <ArrowRight className="w-3 h-3 text-gray-600" />
                          <span className="text-accent bg-accent/10 px-1.5 py-0.5 rounded">{c.new_value}</span>
                        </div>
                        <div className="text-xs text-gray-500 mt-1">理由: {c.reason}</div>
                      </div>
                      <span className="text-xs text-gray-500 shrink-0">
                        置信 {c.confidence.toFixed(0)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {result.applied && (
            <div className="flex items-center gap-2 px-4 py-3 bg-green-500/10 border border-green-500/20 rounded-lg text-green-400 text-sm">
              <Check className="w-4 h-4" /> 修改已应用，策略文件已自动备份
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// History Tab
// =============================================================================

function HistoryTab({ strategies }: { strategies: StrategySummary[] }) {
  const [selected, setSelected] = useState('');
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const loadHistory = async (s: string) => {
    setSelected(s);
    setLoading(true);
    try {
      const data = await apiGet<HistoryRecord[]>(`/api/v1/reflection/history/${s}?limit=20`);
      setRecords(data);
    } catch {
      setRecords([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        {strategies.map((s) => (
          <button
            key={s.name}
            onClick={() => loadHistory(s.name)}
            className={`px-3 py-1.5 rounded-lg text-sm ${
              selected === s.name ? 'bg-accent text-white' : 'bg-surface border border-border text-gray-400 hover:text-white'
            }`}
          >
            {s.display_name ?? s.name}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-12">加载中...</div>
      ) : records.length === 0 ? (
        <div className="text-center text-gray-400 py-12">
          <History className="w-10 h-10 mx-auto mb-2 text-gray-600" />
          {selected ? '暂无进化记录' : '选择一个策略查看进化历史'}
          <p className="mt-2 text-xs text-gray-600">
            使用 <code className="text-accent">alphasift reflect --apply</code> 后会自动记录
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {records.map((r) => (
            <div key={r.id} className="bg-surface rounded-xl border border-border p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-accent/10 text-accent px-2 py-0.5 rounded">
                    #{r.id}
                  </span>
                  <span className="text-sm font-mono text-gray-400">{r.run_id?.slice(0, 12)}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span>胜率前: {fmtPct(r.win_rate_before)}</span>
                  {r.improved !== null && (
                    <span className={r.improved ? 'text-green-400' : 'text-red-400'}>
                      {r.improved ? '↑ 改进' : '↓ 未改进'}
                    </span>
                  )}
                  <span>{r.timestamp?.slice(0, 16)}</span>
                </div>
              </div>
              <p className="text-sm text-gray-400 line-clamp-2">{r.diagnosis}</p>
              {r.changes.length > 0 && (
                <div className="flex gap-1.5 flex-wrap mt-2">
                  {r.changes.map((c, i) => {
                    const ti = CHANGE_TYPE_LABELS[c.change_type] ?? { label: c.change_type, color: 'text-gray-400' };
                    return (
                      <span key={i} className={`text-xs px-2 py-0.5 rounded ${ti.color}`}>
                        {c.target}: {c.old_value}→{c.new_value}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Meta-Learn Tab
// =============================================================================

function MetaLearnTab() {
  const [data, setData] = useState<MetaLearnData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<MetaLearnData>('/api/v1/reflection/meta-learn')
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center text-gray-400 py-12">加载中...</div>;

  if (!data || data.total_records === 0) {
    return (
      <div className="text-center text-gray-400 py-12">
        <BarChart3 className="w-10 h-10 mx-auto mb-2 text-gray-600" />
        暂无元学习数据
        <p className="mt-2 text-xs text-gray-600">
          积累至少 5 条进化记录后，元学习器将自动分析最优修改模式
        </p>
      </div>
    );
  }

  const maxCount = Math.max(...data.change_stats.map((s) => s.count), 1);

  return (
    <div className="space-y-4">
      {/* Overview */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-surface rounded-xl border border-border p-4 text-center">
          <div className="text-2xl font-bold text-accent">{data.total_records}</div>
          <div className="text-xs text-gray-500 mt-0.5">总记录数</div>
        </div>
        <div className="bg-surface rounded-xl border border-border p-4 text-center">
          <div className="text-2xl font-bold">{data.total_strategies}</div>
          <div className="text-xs text-gray-500 mt-0.5">策略数</div>
        </div>
        <div className="bg-surface rounded-xl border border-border p-4 text-center">
          <div className={`text-2xl font-bold ${data.overall_success_rate >= 0.5 ? 'text-green-400' : 'text-amber-400'}`}>
            {(data.overall_success_rate * 100).toFixed(0)}%
          </div>
          <div className="text-xs text-gray-500 mt-0.5">成功率</div>
        </div>
      </div>

      {/* Change Type Stats */}
      {data.change_stats.length > 0 && (
        <div className="bg-surface rounded-xl border border-border p-5">
          <h3 className="font-semibold flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-green-400" />
            修改类型效果
          </h3>
          <div className="space-y-2">
            {data.change_stats.map((s) => {
              const ti = CHANGE_TYPE_LABELS[s.change_type] ?? { label: s.change_type, color: 'text-gray-400' };
              return (
                <div key={s.change_type} className="flex items-center gap-3">
                  <span className={`text-xs px-2 py-0.5 rounded w-20 text-center shrink-0 ${ti.color}`}>
                    {ti.label}
                  </span>
                  <div className="flex-1 bg-gray-900 rounded-full h-3 overflow-hidden">
                    <div
                      className="h-full bg-accent rounded-full transition-all"
                      style={{ width: `${(s.count / maxCount) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-400 w-12 text-right">{s.count}次</span>
                  <span className={`text-xs font-mono w-12 text-right ${s.success_rate >= 0.5 ? 'text-green-400' : 'text-amber-400'}`}>
                    {(s.success_rate * 100).toFixed(0)}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {data.recommendations.length > 0 && (
        <div className="bg-surface rounded-xl border border-border p-5">
          <h3 className="font-semibold flex items-center gap-2 mb-3">
            <Lightbulb className="w-4 h-4 text-amber-400" />
            元学习建议
          </h3>
          <ul className="space-y-2">
            {data.recommendations.map((r, i) => (
              <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                <span className="text-accent mt-0.5 shrink-0">•</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
