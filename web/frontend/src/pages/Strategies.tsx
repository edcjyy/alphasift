import { useEffect, useRef, useState } from 'react';
import { Layers, Upload, Trash2, RefreshCw, AlertCircle, FileUp, X, Eye, Code } from 'lucide-react';
import { apiGet, apiPost, apiDelete } from '@/api';
import type { StrategySummary } from '@/types';

interface StrategyDetail {
  name: string;
  display_name?: string;
  description?: string;
  version?: string;
  category?: string;
  tags?: string[];
  market_scope?: string;
  source_file?: string;
  yaml?: string;
}

export default function Strategies() {
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [restarting, setRestarting] = useState(false);
  const [pendingChange, setPendingChange] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [detail, setDetail] = useState<StrategyDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadStrategies = () => {
    setLoading(true);
    apiGet<StrategySummary[]>('/api/v1/strategies')
      .then(setStrategies)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadStrategies(); }, []);

  const showMsg = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  // 查看策略详情
  const handleView = async (name: string) => {
    setDetailLoading(true);
    try {
      const data = await apiGet<StrategyDetail>(`/api/v1/strategies/${name}`);
      setDetail(data);
    } catch (err: any) {
      showMsg('error', err?.response?.data?.detail ?? '加载策略详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  // 上传策略
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await apiPost<{ ok: boolean; name: string; message: string }>(
        '/api/v1/strategies/upload',
        formData,
      );
      showMsg('success', `策略 "${res.name}" 已上传`);
      setPendingChange(true);
      loadStrategies();
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? '上传失败';
      showMsg('error', detail);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // 删除策略
  const handleDelete = async (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`确认删除策略「${name}」？\n删除后需要重启容器或点击「重启生效」才能清除缓存。`)) return;

    setDeleting(name);
    try {
      await apiDelete<{ ok: boolean; message: string }>(`/api/v1/strategies/${name}`);
      showMsg('success', `策略 "${name}" 已删除`);
      setPendingChange(true);
      setStrategies((prev) => prev.filter((s) => s.name !== name));
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? '删除失败';
      showMsg('error', detail);
    } finally {
      setDeleting(null);
    }
  };

  // 重启服务
  const handleRestart = async () => {
    if (!confirm('确认重启服务？\n页面将在几秒后恢复。')) return;

    setRestarting(true);
    try {
      await apiPost<{ ok: boolean; message: string }>('/api/v1/strategies/reload');
      showMsg('success', '服务正在重启，页面将在几秒后刷新...');
      setPendingChange(false);
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          await apiGet('/api/v1/system/health');
          clearInterval(poll);
          window.location.reload();
        } catch {
          if (attempts > 30) {
            clearInterval(poll);
            showMsg('error', '重启超时，请手动刷新页面');
            setRestarting(false);
          }
        }
      }, 2000);
    } catch (err: any) {
      showMsg('error', '重启请求失败');
      setRestarting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* 标题栏 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">策略管理</h1>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".yaml,.yml"
            onChange={handleUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 bg-accent hover:bg-accent/80 text-white px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {uploading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                上传中...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                上传策略
              </>
            )}
          </button>
        </div>
      </div>

      {/* 消息提示 */}
      {message && (
        <div
          className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
            message.type === 'success'
              ? 'bg-green-500/10 text-green-400 border border-green-500/20'
              : 'bg-red-500/10 text-red-400 border border-red-500/20'
          }`}
        >
          {message.type === 'success' ? (
            <FileUp className="w-4 h-4 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          {message.text}
          <button onClick={() => setMessage(null)} className="ml-auto hover:opacity-70">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 重启提示横幅 */}
      {pendingChange && (
        <div className="flex items-center gap-3 px-4 py-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
          <AlertCircle className="w-5 h-5 text-amber-400 shrink-0" />
          <span className="text-amber-300 text-sm flex-1">
            策略文件已变更。需要重启服务才能完全生效。
          </span>
          <button
            onClick={handleRestart}
            disabled={restarting}
            className="flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 rounded text-sm font-medium transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${restarting ? 'animate-spin' : ''}`} />
            {restarting ? '重启中...' : '重启生效'}
          </button>
        </div>
      )}

      {/* 策略列表 */}
      {loading ? (
        <div className="text-center text-gray-400 py-12">加载中...</div>
      ) : strategies.length === 0 ? (
        <div className="text-center text-gray-400 py-12">
          <Layers className="w-12 h-12 mx-auto mb-3 text-gray-600" />
          暂无可用策略
          <p className="mt-2 text-xs text-gray-600">
            点击右上角「上传策略」添加 .yaml 文件，或确认 NAS 挂载目录包含策略文件
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {strategies.map((s) => (
            <div
              key={s.name}
              onClick={() => handleView(s.name)}
              className="bg-surface rounded-xl border border-border p-5 hover:border-accent/50 transition-colors group relative cursor-pointer"
            >
              {/* 操作按钮组 */}
              <div className="absolute top-3 right-3 flex gap-1">
                <button
                  onClick={(e) => { e.stopPropagation(); handleView(s.name); }}
                  className="p-1.5 rounded-lg text-gray-500 hover:text-accent hover:bg-accent/10 opacity-0 group-hover:opacity-100 transition-all"
                  title="查看详情"
                >
                  <Eye className="w-4 h-4" />
                </button>
                <button
                  onClick={(e) => handleDelete(s.name, e)}
                  disabled={deleting === s.name}
                  className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-400/10 opacity-0 group-hover:opacity-100 transition-all disabled:opacity-50"
                  title="删除策略"
                >
                  {deleting === s.name ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </button>
              </div>

              <div className="flex items-start justify-between pr-16">
                <div>
                  <h3 className="font-semibold text-lg">{s.display_name ?? s.name}</h3>
                  {s.display_name && s.display_name !== s.name && (
                    <p className="text-xs text-gray-500 mt-0.5 font-mono">{s.name}</p>
                  )}
                </div>
                <span className="text-xs text-gray-500 bg-surface-active px-2 py-0.5 rounded shrink-0">
                  v{s.version ?? '?'}
                </span>
              </div>
              <p className="text-gray-400 text-sm mt-2 line-clamp-2">{s.description ?? ''}</p>
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

      {/* 策略详情弹窗 */}
      {detail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setDetail(null)}
        >
          <div
            className="bg-surface border border-border rounded-xl w-full max-w-3xl max-h-[85vh] mx-4 flex flex-col shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 弹窗标题 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
              <div>
                <h2 className="text-lg font-semibold">{detail.display_name ?? detail.name}</h2>
                {detail.display_name && detail.display_name !== detail.name && (
                  <p className="text-xs text-gray-500 font-mono mt-0.5">{detail.name}</p>
                )}
              </div>
              <button
                onClick={() => setDetail(null)}
                className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-surface-hover transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 弹窗内容 */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {/* 元信息 */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">版本</span>
                  <p className="mt-0.5">v{detail.version ?? '?'}</p>
                </div>
                <div>
                  <span className="text-gray-500">分类</span>
                  <p className="mt-0.5">{detail.category ?? '未分类'}</p>
                </div>
                <div>
                  <span className="text-gray-500">市场范围</span>
                  <p className="mt-0.5">{detail.market_scope ?? '-'}</p>
                </div>
                <div>
                  <span className="text-gray-500">文件名</span>
                  <p className="mt-0.5 font-mono text-xs">{detail.source_file ?? '-'}</p>
                </div>
              </div>
              {detail.description && (
                <div>
                  <span className="text-sm text-gray-500">描述</span>
                  <p className="mt-1 text-sm">{detail.description}</p>
                </div>
              )}
              {detail.tags && detail.tags.length > 0 && (
                <div>
                  <span className="text-sm text-gray-500">标签</span>
                  <div className="flex gap-1.5 flex-wrap mt-1">
                    {detail.tags.map((tag) => (
                      <span key={tag} className="text-xs bg-surface-active text-gray-300 px-2 py-0.5 rounded">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* YAML 内容 */}
              {detail.yaml ? (
                <div>
                  <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                    <Code className="w-4 h-4" />
                    YAML 配置
                  </div>
                  <pre className="bg-gray-950 border border-border rounded-lg p-4 text-xs text-gray-300 overflow-auto max-h-[400px] whitespace-pre font-mono leading-relaxed">
                    {detail.yaml}
                  </pre>
                </div>
              ) : (
                <div className="text-sm text-gray-500">
                  {detailLoading ? '加载中...' : '无法加载 YAML 内容'}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
