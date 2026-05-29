import { useState, useMemo } from 'react';
import {
  ChevronDown, Plus, Trash2, Eye, EyeOff,
  CheckCircle, XCircle, RotateCw,
} from 'lucide-react';
import { updateEnv } from '@/api';
import type { EnvEntry, EnvUpdateResponse } from '@/types';
import { PROVIDER_TEMPLATES, PROTOCOL_OPTIONS } from './llmProviderTemplates';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChannelConfig {
  id: string;
  name: string;
  protocol: string;
  baseUrl: string;
  apiKey: string;
  models: string;
  enabled: boolean;
}

interface Props {
  envEntries: EnvEntry[];
  onSaved: () => void;
}

// ---------------------------------------------------------------------------
// Parse / serialise
// ---------------------------------------------------------------------------

const KEY_MAP: Record<keyof Omit<ChannelConfig, 'id'>, string> = {
  name: '',
  protocol: 'PROTOCOL',
  baseUrl: 'BASE_URL',
  apiKey: 'API_KEYS',
  models: 'MODELS',
  enabled: 'ENABLED',
};

function fmtKey(channelName: string, field: string): string {
  return `LLM_${channelName.toUpperCase()}_${field}`;
}

function parseChannels(entries: EnvEntry[]): ChannelConfig[] {
  const map = new Map(entries.map((e) => [e.key, e.value]));
  const names = (map.get('LLM_CHANNELS') ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  return names.map((name, i) => ({
    id: String(i),
    name: name.toLowerCase(),
    protocol: map.get(fmtKey(name, 'PROTOCOL')) || 'openai',
    baseUrl: map.get(fmtKey(name, 'BASE_URL')) || '',
    apiKey: map.get(fmtKey(name, 'API_KEYS')) || '',
    models: map.get(fmtKey(name, 'MODELS')) || '',
    enabled: (map.get(fmtKey(name, 'ENABLED')) ?? 'true') === 'true',
  }));
}

function channelsToChanges(
  channels: ChannelConfig[],
  existingEntries: EnvEntry[],
): Record<string, string> {
  const changes: Record<string, string> = {};
  const currentMap = new Map(existingEntries.map((e) => [e.key, e.value]));

  // 1) LLM_CHANNELS
  const newNames = channels.map((c) => c.name).join(',');
  if (newNames !== (currentMap.get('LLM_CHANNELS') ?? '').replace(/\s/g, '')) {
    changes['LLM_CHANNELS'] = newNames;
  }

  // 2) Per-channel fields
  for (const c of channels) {
    for (const [field, suffix] of Object.entries(KEY_MAP)) {
      if (!suffix) continue;
      const key = fmtKey(c.name, suffix);
      const newVal = String(c[field as keyof ChannelConfig]);
      if (newVal !== (currentMap.get(key) ?? '')) {
        changes[key] = newVal;
      }
    }
  }

  // 3) Clean up removed channels
  const activeNames = new Set(channels.map((c) => c.name.toUpperCase()));
  for (const key of currentMap.keys()) {
    if (key.startsWith('LLM_') && key !== 'LLM_CHANNELS') {
      const parts = key.split('_');
      if (parts.length >= 2 && !activeNames.has(parts[1]!)) {
        changes[key] = '';  // Signal deletion by setting empty
      }
    }
  }

  return changes;
}

// Recursively merge so deleted-channel cleanup is preserved
function ensureCleanupKeys(changes: Record<string, string>, allKeys: string[], activeNames: string[]): Record<string, string> {
  const upperNames = new Set(activeNames.map((n) => n.toUpperCase()));
  const merged = { ...changes };
  for (const key of allKeys) {
    if (key.startsWith('LLM_') && key !== 'LLM_CHANNELS') {
      const parts = key.split('_');
      if (parts.length >= 2 && !upperNames.has(parts[1]!) && !(key in merged)) {
        merged[key] = '';
      }
    }
  }
  return merged;
}


// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LLMChannelEditor({ envEntries, onSaved }: Props) {
  const [channels, setChannels] = useState<ChannelConfig[]>(() => parseChannels(envEntries));
  const [expanded, setExpanded] = useState<Set<number>>(new Set([0]));
  const [keyVisible, setKeyVisible] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<EnvUpdateResponse | null>(null);
  const [addPreset, setAddPreset] = useState('');
  const [testing, setTesting] = useState<Set<number>>(new Set());
  const [testResults, setTestResults] = useState<Map<number, { ok: boolean; msg: string }>>(new Map());

  const allEntryKeys = useMemo(() => envEntries.map((e) => e.key), [envEntries]);

  // ── mutations ────────────────────────────────────────────────

  function toggleExpand(idx: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(idx) ? next.delete(idx) : next.add(idx);
      return next;
    });
  }

  function updateChannel(idx: number, field: keyof ChannelConfig, value: string | boolean) {
    setChannels((prev) => prev.map((c, i) => (i === idx ? { ...c, [field]: value } : c)));
  }

  function toggleKeyVisible(idx: number) {
    setKeyVisible((prev) => {
      const next = new Set(prev);
      next.has(idx) ? next.delete(idx) : next.add(idx);
      return next;
    });
  }

  function addChannel() {
    const preset = PROVIDER_TEMPLATES.find((t) => t.channelId === addPreset) ?? PROVIDER_TEMPLATES[0]!;
    const newCh: ChannelConfig = {
      id: String(channels.length),
      name: preset.channelId,
      protocol: preset.protocol,
      baseUrl: preset.baseUrl,
      apiKey: '',
      models: preset.placeholderModels,
      enabled: true,
    };
    setChannels((prev) => [...prev, newCh]);
    setExpanded(new Set([channels.length]));
    setAddPreset('');
  }

  function removeChannel(idx: number) {
    setChannels((prev) => prev.filter((_, i) => i !== idx));
  }

  async function testChannel(idx: number) {
    const ch = channels[idx];
    if (!ch) return;
    setTesting((s) => new Set(s).add(idx));
    setTestResults((m) => {
      const next = new Map(m);
      next.delete(idx);
      return next;
    });
    try {
      // 简单的 /models 探测
      const url = ch.baseUrl.replace(/\/+$/, '') + '/models';
      const res = await fetch(url, {
        headers: ch.apiKey ? { Authorization: `Bearer ${ch.apiKey}` } : {},
      });
      const text = await res.text();
      setTestResults((m) => {
        const next = new Map(m);
        next.set(idx, { ok: res.ok, msg: res.ok ? `成功 (${res.status}) 已发现模型列表` : `失败 (${res.status}): ${text.slice(0, 80)}` });
        return next;
      });
    } catch (e: any) {
      setTestResults((m) => {
        const next = new Map(m);
        next.set(idx, { ok: false, msg: `连接失败: ${e.message}` });
        return next;
      });
    }
    setTesting((s) => {
      const next = new Set(s);
      next.delete(idx);
      return next;
    });
  }

  async function handleSave() {
    setSaving(true);
    setSaveResult(null);
    try {
      let changes = channelsToChanges(channels, envEntries);
      changes = ensureCleanupKeys(changes, allEntryKeys, channels.map((c) => c.name));
      if (Object.keys(changes).length === 0) {
        setSaveResult({ status: 'ok', updated: [], requires_restart: false, message: '没有变更' });
        return;
      }
      // Also update os.environ via the backend
      const res = await updateEnv(changes);
      setSaveResult(res);
      if (res.status === 'ok') onSaved();
    } catch (err: any) {
      setSaveResult({ status: 'error', updated: [], requires_restart: false, message: err.message ?? '保存失败' });
    } finally {
      setSaving(false);
    }
  }

  // ── render ───────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* 渠道列表 */}
      {channels.map((ch, idx) => (
        <div key={ch.id} className="bg-surface rounded-xl border border-border overflow-hidden">
          {/* Header */}
          <button
            onClick={() => toggleExpand(idx)}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface-hover transition-colors text-left"
          >
            <div className="flex items-center gap-3">
              <ChevronDown
                className={`w-4 h-4 text-gray-400 transition-transform ${expanded.has(idx) ? '' : '-rotate-90'}`}
              />
              <span className="font-medium text-sm">{ch.name}</span>
              <span className="text-xs bg-surface-active text-gray-400 px-2 py-0.5 rounded">
                {PROTOCOL_OPTIONS.find((p) => p.value === ch.protocol)?.label ?? ch.protocol}
              </span>
              <span className={`w-2 h-2 rounded-full ${ch.enabled ? 'bg-fall' : 'bg-gray-600'}`} />
              {testResults.get(idx) && (
                testResults.get(idx)!.ok
                  ? <CheckCircle className="w-4 h-4 text-fall" />
                  : <XCircle className="w-4 h-4 text-rise" />
              )}
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); removeChannel(idx); }}
              className="p-1 rounded hover:bg-rise/10 text-gray-400 hover:text-rise"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </button>

          {/* Body */}
          {expanded.has(idx) && (
            <div className="px-4 pb-4 space-y-3 border-t border-border">
              <div className="grid grid-cols-2 gap-3 pt-3">
                {/* 渠道名称 */}
                <div>
                  <label className="block text-xs text-gray-400 mb-1">渠道名称</label>
                  <input
                    className="w-full bg-gray-900 border border-border rounded-lg px-3 py-1.5 text-sm font-mono"
                    value={ch.name}
                    onChange={(e) => updateChannel(idx, 'name', e.target.value)}
                  />
                </div>

                {/* 协议 */}
                <div>
                  <label className="block text-xs text-gray-400 mb-1">协议</label>
                  <select
                    className="w-full bg-gray-900 border border-border rounded-lg px-3 py-1.5 text-sm"
                    value={ch.protocol}
                    onChange={(e) => updateChannel(idx, 'protocol', e.target.value)}
                  >
                    {PROTOCOL_OPTIONS.map((p) => (
                      <option key={p.value} value={p.value}>{p.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Base URL */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Base URL</label>
                <input
                  className="w-full bg-gray-900 border border-border rounded-lg px-3 py-1.5 text-sm font-mono"
                  value={ch.baseUrl}
                  onChange={(e) => updateChannel(idx, 'baseUrl', e.target.value)}
                  placeholder="https://api.minimax.chat/v1"
                />
              </div>

              {/* API Key */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">API Key / Token</label>
                <div className="relative">
                  <input
                    type={keyVisible.has(idx) ? 'text' : 'password'}
                    className="w-full bg-gray-900 border border-border rounded-lg px-3 py-1.5 pr-10 text-sm font-mono"
                    value={ch.apiKey}
                    onChange={(e) => updateChannel(idx, 'apiKey', e.target.value)}
                    placeholder="支持多个 Key 逗号分隔"
                  />
                  <button
                    onClick={() => toggleKeyVisible(idx)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                  >
                    {keyVisible.has(idx) ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Models + Enabled */}
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className="block text-xs text-gray-400 mb-1">模型列表</label>
                  <input
                    className="w-full bg-gray-900 border border-border rounded-lg px-3 py-1.5 text-sm"
                    value={ch.models}
                    onChange={(e) => updateChannel(idx, 'models', e.target.value)}
                    placeholder="逗号分隔，如 abab6.5s-chat,abab6.5s-chat-240k"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">启用</label>
                  <select
                    className="w-full bg-gray-900 border border-border rounded-lg px-3 py-1.5 text-sm"
                    value={ch.enabled ? 'true' : 'false'}
                    onChange={(e) => updateChannel(idx, 'enabled', e.target.value === 'true')}
                  >
                    <option value="true">启用</option>
                    <option value="false">禁用</option>
                  </select>
                </div>
              </div>

              {/* 测试连接 + 反馈 */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => testChannel(idx)}
                  disabled={testing.has(idx)}
                  className="flex items-center gap-1 px-3 py-1 text-xs border border-border rounded-lg text-gray-400 hover:text-white hover:border-accent/50 disabled:opacity-50"
                >
                  <RotateCw className={`w-3 h-3 ${testing.has(idx) ? 'animate-spin' : ''}`} />
                  测试连接
                </button>
                {testResults.get(idx) && (
                  <span className={`text-xs ${testResults.get(idx)!.ok ? 'text-fall' : 'text-rise'}`}>
                    {testResults.get(idx)!.msg}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      ))}

      {/* 添加渠道 */}
      <div className="flex items-center gap-2">
        <select
          className="bg-gray-900 border border-border rounded-lg px-3 py-1.5 text-sm text-gray-400"
          value={addPreset}
          onChange={(e) => setAddPreset(e.target.value)}
        >
          <option value="">选择服务商模板...</option>
          {PROVIDER_TEMPLATES.map((t) => (
            <option key={t.channelId} value={t.channelId}>{t.label}</option>
          ))}
        </select>
        <button
          onClick={addChannel}
          disabled={!addPreset}
          className="flex items-center gap-1 px-3 py-1.5 text-sm border border-border rounded-lg text-gray-400 hover:text-white hover:border-accent/50 disabled:opacity-50"
        >
          <Plus className="w-3.5 h-3.5" />
          添加渠道
        </button>
      </div>

      {/* 保存按钮 */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2 bg-accent hover:bg-accent-hover disabled:bg-gray-700 text-white rounded-lg text-sm"
        >
          {saving ? '保存中...' : '保存渠道配置'}
        </button>
        {saveResult && (
          <span className={`text-sm ${saveResult.status === 'ok' ? 'text-fall' : 'text-rise'}`}>
            {saveResult.message}
          </span>
        )}
      </div>
    </div>
  );
}
