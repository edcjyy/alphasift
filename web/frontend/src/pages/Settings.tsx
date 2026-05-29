import { useEffect, useState } from 'react';
import {
  Activity,
  Database,
  Brain,
  Server,
  Settings as SettingsIcon,
  Terminal,
  Save,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Info,
  Layers,
} from 'lucide-react';
import { apiGet, fetchEnv, updateEnv } from '@/api';
import type { HealthResponse, EnvEntry, EnvUpdateResponse } from '@/types';
import LLMChannelEditor from '@/components/settings/LLMChannelEditor';

// 环境变量分组配置
const ENV_GROUPS: {
  label: string;
  icon: React.ReactNode;
  keys: string[];
  description: string;
}[] = [
  {
    label: 'LLM 渠道配置',
    icon: <Brain className="w-4 h-4" />,
    keys: [],  // 由 LLMChannelEditor 组件独立渲染
    description: '按渠道（Channel）管理模型接入地址、API Key 和模型列表',
  },
  {
    label: '数据源',
    icon: <Database className="w-4 h-4" />,
    keys: [
      'SNAPSHOT_SOURCE_PRIORITY',
      'TUSHARE_API_URL',
      'TUSHARE_TOKEN',
      'TUSHARE_API_TOKEN',
      'TUSHARE_TRADE_DATE',
      'ALPHASIFT_DATA_DIR',
      'STRATEGIES_DIR',
    ],
    description: '行情数据源优先级、Tushare 凭证和本地目录',
  },
  {
    label: 'DSA 深度分析',
    icon: <Terminal className="w-4 h-4" />,
    keys: [
      'DSA_API_URL',
      'DSA_REPORT_TYPE',
      'DSA_MAX_PICKS',
      'DSA_TIMEOUT_SEC',
      'DSA_FORCE_REFRESH',
      'DSA_NOTIFY',
    ],
    description: '配置深度分析服务地址和参数',
  },
  {
    label: '后置分析',
    icon: <SettingsIcon className="w-4 h-4" />,
    keys: [
      'POST_ANALYZERS',
      'POST_ANALYSIS_MAX_PICKS',
      'POST_ANALYZER_URL',
      'POST_ANALYZER_TIMEOUT_SEC',
    ],
    description: '选股结果后置分析模块及外部评分工具',
  },
  {
    label: '风险评估',
    icon: <AlertTriangle className="w-4 h-4" />,
    keys: ['RISK_ENABLED', 'RISK_MAX_PENALTY', 'RISK_VETO_HIGH'],
    description: '配置风险过滤和扣分规则',
  },
  {
    label: '组合多样性',
    icon: <Activity className="w-4 h-4" />,
    keys: [
      'PORTFOLIO_DIVERSITY_ENABLED',
      'PORTFOLIO_MAX_SAME_LLM_SECTOR',
      'PORTFOLIO_CONCENTRATION_PENALTY',
    ],
    description: '避免选股结果过度集中于同一行业',
  },
  {
    label: '每日增强',
    icon: <RefreshCw className="w-4 h-4" />,
    keys: [
      'DAILY_ENRICH_ENABLED',
      'DAILY_ENRICH_MAX_CANDIDATES',
      'DAILY_LOOKBACK_DAYS',
      'DAILY_SOURCE',
      'DAILY_FETCH_RETRIES',
    ],
    description: '每日自动补充实时行情和日K特征',
  },
  {
    label: '行业映射',
    icon: <Layers className="w-4 h-4" />,
    keys: [
      'INDUSTRY_MAP_FILES',
      'INDUSTRY_PROVIDER',
      'INDUSTRY_PROVIDER_MAX_BOARDS',
    ],
    description: '代码→行业/概念/板块热度映射',
  },
  {
    label: '回测评估',
    icon: <CheckCircle className="w-4 h-4" />,
    keys: [
      'EVALUATION_COST_BPS',
      'EVALUATION_FOLLOW_THROUGH_PCT',
      'EVALUATION_FAILED_BREAKOUT_PCT',
      'EVALUATION_PRICE_PATH_ENABLED',
      'EVALUATION_PRICE_PATH_LOOKBACK_DAYS',
    ],
    description: '配置选股策略回测评估参数',
  },
];

/** 格式化环境变量值为可编辑文本 */
function formatEnvValue(entry: EnvEntry): string {
  if (entry.masked && entry.value.startsWith('***')) {
    return '';
  }
  return entry.value;
}

export default function Settings() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [envEntries, setEnvEntries] = useState<EnvEntry[]>([]);
  const [envDraft, setEnvDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<EnvUpdateResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'health' | 'env'>('health');
  const [activeGroup, setActiveGroup] = useState(0);
  const [restartFlag, setRestartFlag] = useState(false);

  // 加载数据
  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const [healthRes, envRes] = await Promise.all([
          apiGet<HealthResponse>('/api/v1/system/health').catch(() => null),
          fetchEnv().catch(() => [] as EnvEntry[]),
        ]);
        if (!mounted) return;
        if (healthRes) setHealth(healthRes);
        setEnvEntries(envRes);
        // 初始化草稿
        const draft: Record<string, string> = {};
        for (const e of envRes) {
          draft[e.key] = formatEnvValue(e);
        }
        setEnvDraft(draft);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => { mounted = false; };
  }, []);

  // 保存环境变量
  async function handleSave() {
    setSaving(true);
    setSaveResult(null);
    try {
      const changes: Record<string, string> = {};
      for (const key of Object.keys(envDraft)) {
        const entry = envEntries.find((e) => e.key === key);
        if (!entry) continue;
        const newValue = envDraft[key] ?? '';
        // 跳过脱敏字段的空值（表示不修改）
        if (entry.masked && newValue === '') continue;
        // 与当前值比较，只提交有变化的
        const current = formatEnvValue(entry);
        if (newValue !== current) {
          changes[key] = newValue;
        }
      }
      if (Object.keys(changes).length === 0) {
        setSaveResult({ status: 'ok', updated: [], requires_restart: false, message: '没有变更' });
        return;
      }
      const res = await updateEnv(changes);
      setSaveResult(res);
      setRestartFlag(restartFlag || res.requires_restart);
      // 刷新环境变量
      const refreshed = await fetchEnv();
      setEnvEntries(refreshed);
      const draft: Record<string, string> = {};
      for (const e of refreshed) {
        draft[e.key] = formatEnvValue(e);
      }
      setEnvDraft(draft);
    } catch (err: any) {
      setSaveResult({ status: 'error', updated: [], requires_restart: false, message: err.message || '保存失败' });
    } finally {
      setSaving(false);
    }
  }

  // 渲染单个字段
  function renderField(key: string) {
    const entry = envEntries.find((e) => e.key === key);
    if (!entry) return null;
    const isBoolean = entry.value === 'true' || entry.value === 'false' || key.endsWith('_ENABLED') || key.endsWith('_SILENT') || key.endsWith('_MODE');
    const masked = entry.masked;

    return (
      <div key={key} className="mb-3">
        <label className="block text-xs text-gray-400 mb-1 font-mono">
          {key}
          {masked && <span className="ml-1 text-yellow-500 text-xxs">（敏感，已脱敏）</span>}
        </label>
        {isBoolean ? (
          <select
            className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm"
            value={envDraft[key] === 'true' ? 'true' : envDraft[key] === 'false' ? 'false' : ''}
            onChange={(e) => setEnvDraft((d) => ({ ...d, [key]: e.target.value }))}
          >
            <option value="">— 未设置 —</option>
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
        ) : masked ? (
          <input
            type="password"
            className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-mono"
            value={envDraft[key]}
            placeholder="输入新值（留空则不修改）"
            onChange={(e) => setEnvDraft((d) => ({ ...d, [key]: e.target.value }))}
          />
        ) : (
          <input
            className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-mono"
            value={envDraft[key]}
            placeholder="未设置"
            onChange={(e) => setEnvDraft((d) => ({ ...d, [key]: e.target.value }))}
          />
        )}
      </div>
    );
  }

  if (loading) {
    return <div className="p-6 text-gray-500">加载中...</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>

      {/* Tab 切换 */}
      <div className="flex gap-2 border-b border-border">
        <button
          className={`pb-2 px-4 text-sm font-medium ${activeTab === 'health' ? 'text-accent border-b-2 border-accent' : 'text-gray-400'}`}
          onClick={() => setActiveTab('health')}
        >
          <span className="inline-flex items-center gap-1">
            <Activity className="w-4 h-4" /> 系统状态
          </span>
        </button>
        <button
          className={`pb-2 px-4 text-sm font-medium ${activeTab === 'env' ? 'text-accent border-b-2 border-accent' : 'text-gray-400'}`}
          onClick={() => setActiveTab('env')}
        >
          <span className="inline-flex items-center gap-1">
            <SettingsIcon className="w-4 h-4" /> 环境配置
          </span>
        </button>
      </div>

      {/* ── Tab 1：系统状态 ───────────────────────── */}
      {activeTab === 'health' && (
        <div className="space-y-6">
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
                  <span className={health.status === 'ok' ? 'text-fall' : 'text-rise'}>
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

          {/* 重启提示 */}
          {restartFlag && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-yellow-500 mt-0.5" />
              <div>
                <div className="font-medium text-yellow-500">需要重启后端</div>
                <div className="text-sm text-gray-400 mt-1">
                  部分环境变量已更改，需要重启后端服务才能生效。请在 NAS Docker 中重启容器，或终止并重新运行 <code>python web/serve.py</code>。
                </div>
              </div>
            </div>
          )}

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
                'GET /api/v1/runs/{run_id} — 获取运行详情',
                'POST /api/v1/evaluate/{run_id} — 执行评估',
                'GET  /api/v1/strategies — 获取策略列表',
                'GET  /api/v1/system/health — 系统健康检查',
                'GET  /api/v1/system/env — 读取环境变量',
                'PUT  /api/v1/system/env — 更新环境变量',
              ].map((line) => (
                <div key={line} className="text-gray-400 py-1">
                  {line}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Tab 2：环境配置 ───────────────────────── */}
      {activeTab === 'env' && (
        <div className="space-y-6">
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4 flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-500 mt-0.5" />
            <div className="text-sm text-gray-300">
              <p>此处修改的是 <code className="font-mono text-accent">.env</code> 文件中的环境变量。保存后：</p>
              <ul className="list-disc ml-5 mt-1 space-y-1 text-gray-400">
                <li>部分变量<strong className="text-yellow-500">需要重启后端</strong>才能生效（保存后会提示）</li>
                <li>部分变量下次 API 请求时自动生效</li>
                <li>敏感字段（如 API Token）显示时已脱敏，留空表示不修改</li>
              </ul>
            </div>
          </div>

          {/* 分组标签 */}
          <div className="flex flex-wrap gap-2">
            {ENV_GROUPS.map((g, i) => (
              <button
                key={g.label}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${
                  activeGroup === i
                    ? 'bg-accent/20 border-accent text-accent'
                    : 'bg-surface border-border text-gray-400 hover:text-gray-200'
                }`}
                onClick={() => setActiveGroup(i)}
              >
                {g.label}
              </button>
            ))}
          </div>

          {/* 当前分组表单 — LLM 渠道使用专用编辑器 */}
          {activeGroup === 0 ? (
            <div className="bg-surface rounded-xl border border-border p-5">
              <h3 className="font-medium mb-1 flex items-center gap-2">
                <Brain className="w-4 h-4" />
                LLM 渠道配置
              </h3>
              <p className="text-xs text-gray-500 mb-4">
                按渠道管理 LLM 提供商，每个渠道可独立配置 Base URL、API Key 和模型列表
              </p>
              <LLMChannelEditor
                envEntries={envEntries}
                onSaved={() => {
                  fetchEnv().then((refreshed) => {
                    setEnvEntries(refreshed);
                    const draft: Record<string, string> = {};
                    for (const e of refreshed) draft[e.key] = formatEnvValue(e);
                    setEnvDraft(draft);
                  });
                }}
              />
            </div>
          ) : (
            <div className="bg-surface rounded-xl border border-border p-5">
              <h3 className="font-medium mb-1 flex items-center gap-2">
                {ENV_GROUPS[activeGroup]?.icon}
                {ENV_GROUPS[activeGroup]?.label ?? '未知分组'}
              </h3>
              <p className="text-xs text-gray-500 mb-4">{ENV_GROUPS[activeGroup]?.description ?? ''}</p>
              {(ENV_GROUPS[activeGroup]?.keys ?? []).map(renderField)}
            </div>
          )}

          {/* 保存按钮 + 结果提示 */}
          <div className="flex items-center gap-4">
            <button
              className="px-6 py-2.5 bg-accent text-white rounded-xl font-medium text-sm disabled:opacity-50 flex items-center gap-2"
              onClick={handleSave}
              disabled={saving}
            >
              <Save className="w-4 h-4" />
              {saving ? '保存中...' : '保存更改'}
            </button>

            <button
              className="px-4 py-2.5 border border-border rounded-xl text-sm text-gray-400 hover:text-gray-200"
              onClick={() => {
                const draft: Record<string, string> = {};
                for (const e of envEntries) {
                  draft[e.key] = formatEnvValue(e);
                }
                setEnvDraft(draft);
                setSaveResult(null);
              }}
            >
              重置
            </button>

            {saveResult && (
              <span className={`text-sm ${saveResult.status === 'ok' ? 'text-fall' : 'text-rise'}`}>
                {saveResult.message}
                {saveResult.status === 'ok' && saveResult.updated.length > 0 && (
                  <span className="text-gray-500 ml-1">
                    （已更新: {saveResult.updated.join(', ')}）
                  </span>
                )}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
