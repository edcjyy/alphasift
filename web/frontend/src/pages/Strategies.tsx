import { useEffect, useRef, useState } from 'react';
import { Layers, Upload, Trash2, RefreshCw, AlertCircle, FileUp, X } from 'lucide-react';
import { apiGet, apiPost, apiDelete } from '@/api';
import type { StrategySummary } from '@/types';

export default function Strategies() {
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [restarting, setRestarting] = useState(false);
  const [pendingChange, setPendingChange] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
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
  const handleDelete = async (name: string) => {
    if (!confirm(`确认删除策略「${name}」？\n删除后需要重启容器或点击「重启生效」才能清除缓存。`)) return;

    setDeleting(name);
    try {
      await apiDelete<{ ok: boolean; message: string }>(`/api/v1/strategies/${name}`);
      showMsg('success', `策略 "${name}" 已删除`);
      setPendingChange(true);
      // 先从前端列表中移除
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
      // 等待并尝试重新连接
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
              className="bg-surface rounded-xl border border-border p-5 hover:border-accent/50 transition-colors group relative"
            >
              {/* 删除按钮 */}
              <button
                onClick={() => handleDelete(s.name)}
                disabled={deleting === s.name}
                className="absolute top-3 right-3 p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-400/10 opacity-0 group-hover:opacity-100 transition-all disabled:opacity-50"
                title="删除策略"
              >
                {deleting === s.name ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </button>

              <div className="flex items-start justify-between pr-8">
                <h3 className="font-semibold text-lg">{s.display_name ?? s.name}</h3>
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
    </div>
  );
}
