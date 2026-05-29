import { useEffect, useState } from 'react';
import { Plus, Trash2, Play, Pause, RotateCw, Clock } from 'lucide-react';
import { apiGet, apiPost, apiPut, apiDelete } from '@/api';
import type { StrategySummary } from '@/types';

interface ScheduleTask {
  id: string;
  name: string;
  strategy: string;
  cron_expr: string;
  enabled: boolean;
  max_output: number;
  use_llm: boolean;
  daily_enrich: boolean;
  save_run: boolean;
  created_at: string;
  last_run_at: string;
  next_run_at: string;
}

const CRON_PRESETS: { label: string; cron: string }[] = [
  { label: '每天 9:30（交易日）', cron: '30 9 * * 1-5' },
  { label: '每周一 9:30', cron: '30 9 * * 1' },
  { label: '每天 15:00 收盘后', cron: '0 15 * * 1-5' },
  { label: '每小时', cron: '0 * * * *' },
  { label: '每天 8:00', cron: '0 8 * * *' },
  { label: '自定义', cron: '' },
];

export default function Schedule() {
  const [tasks, setTasks] = useState<ScheduleTask[]>([]);
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [running, setRunning] = useState<Set<string>>(new Set());

  // 表单状态
  const [form, setForm] = useState({
    name: '',
    strategy: '',
    cron_expr: '30 9 * * 1-5',
    max_output: 20,
    use_llm: false,
    daily_enrich: false,
    save_run: true,
  });

  // 加载数据
  const loadTasks = async () => {
    try {
      const [taskList, stratList] = await Promise.all([
        apiGet<ScheduleTask[]>('/api/v1/schedule'),
        apiGet<StrategySummary[]>('/api/v1/strategies'),
      ]);
      setTasks(taskList);
      setStrategies(stratList);
      if (stratList.length > 0 && !form.strategy) {
        setForm((f) => ({ ...f, strategy: stratList[0]!.name }));
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTasks(); }, []);

  // 创建 / 更新任务
  const handleSave = async () => {
    if (!form.strategy || !form.cron_expr) return;
    try {
      if (editingId) {
        await apiPut(`/api/v1/schedule/${editingId}`, form);
      } else {
        await apiPost('/api/v1/schedule', form);
      }
      setShowForm(false);
      setEditingId(null);
      resetForm();
      await loadTasks();
    } catch {
      // ignore
    }
  };

  // 删除
  const handleDelete = async (id: string) => {
    if (!confirm('确定删除该定时任务？')) return;
    await apiDelete(`/api/v1/schedule/${id}`).catch(() => {});
    await loadTasks();
  };

  // 切换启用
  const handleToggle = async (task: ScheduleTask) => {
    await apiPut(`/api/v1/schedule/${task.id}`, { enabled: !task.enabled });
    await loadTasks();
  };

  // 手动执行
  const handleRun = async (id: string) => {
    setRunning((s) => new Set(s).add(id));
    try {
      await apiPost(`/api/v1/schedule/${id}/run`, {}, { timeout: 600000 });
    } catch {
      // ignore
    }
    setRunning((s) => {
      const next = new Set(s);
      next.delete(id);
      return next;
    });
    await loadTasks();
  };

  // 编辑
  const handleEdit = (task: ScheduleTask) => {
    setForm({
      name: task.name,
      strategy: task.strategy,
      cron_expr: task.cron_expr,
      max_output: task.max_output,
      use_llm: task.use_llm,
      daily_enrich: task.daily_enrich,
      save_run: task.save_run,
    });
    setEditingId(task.id);
    setShowForm(true);
  };

  const resetForm = () => {
    setForm({
      name: '',
      strategy: strategies[0]?.name ?? '',
      cron_expr: '30 9 * * 1-5',
      max_output: 20,
      use_llm: false,
      daily_enrich: false,
      save_run: true,
    });
    setEditingId(null);
  };

  const formatTime = (iso: string) => {
    if (!iso || iso === 'N/A') return '—';
    return new Date(iso).toLocaleString('zh-CN', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  };

  if (loading) {
    return <div className="p-6 text-gray-500">加载中...</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Clock className="w-6 h-6 text-accent" />
          定时任务
        </h1>
        <button
          onClick={() => { resetForm(); setShowForm(true); }}
          className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          新建任务
        </button>
      </div>

      {/* 创建/编辑表单 */}
      {showForm && (
        <div className="bg-surface rounded-xl border border-border p-5 space-y-4">
          <h2 className="font-medium">{editingId ? '编辑任务' : '新建定时任务'}</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">任务名称</label>
              <input
                className="w-full bg-gray-900 border border-border rounded-lg px-3 py-2 text-sm"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="例如：每日开盘选股"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">策略</label>
              <select
                className="w-full bg-gray-900 border border-border rounded-lg px-3 py-2 text-sm"
                value={form.strategy}
                onChange={(e) => setForm((f) => ({ ...f, strategy: e.target.value }))}
              >
                {strategies.map((s) => (
                  <option key={s.name} value={s.name}>{s.display_name ?? s.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Cron 表达式</label>
            <div className="flex gap-2">
              <select
                className="bg-gray-900 border border-border rounded-lg px-3 py-2 text-sm flex-shrink-0"
                value={form.cron_expr}
                onChange={(e) => {
                  if (e.target.value) setForm((f) => ({ ...f, cron_expr: e.target.value }));
                }}
              >
                {CRON_PRESETS.map((p) => (
                  <option key={p.label} value={p.cron || ''}>
                    {p.label}
                  </option>
                ))}
              </select>
              <input
                className="flex-1 bg-gray-900 border border-border rounded-lg px-3 py-2 text-sm font-mono"
                value={form.cron_expr}
                onChange={(e) => setForm((f) => ({ ...f, cron_expr: e.target.value }))}
                placeholder="分 时 日 月 周 (如 30 9 * * 1-5)"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">最大输出</label>
              <input
                type="number" min={1} max={100}
                className="w-full bg-gray-900 border border-border rounded-lg px-3 py-2 text-sm"
                value={form.max_output}
                onChange={(e) => setForm((f) => ({ ...f, max_output: Number(e.target.value) }))}
              />
            </div>
          </div>

          <div className="flex gap-6">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={form.use_llm}
                onChange={(e) => setForm((f) => ({ ...f, use_llm: e.target.checked }))}
                className="accent-accent w-4 h-4" />
              LLM 增强
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={form.daily_enrich}
                onChange={(e) => setForm((f) => ({ ...f, daily_enrich: e.target.checked }))}
                className="accent-accent w-4 h-4" />
              日线补充
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={form.save_run}
                onChange={(e) => setForm((f) => ({ ...f, save_run: e.target.checked }))}
                className="accent-accent w-4 h-4" />
              保存结果
            </label>
          </div>

          <div className="flex gap-3">
            <button onClick={handleSave}
              className="px-5 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm">
              {editingId ? '更新' : '创建'}
            </button>
            <button onClick={() => { setShowForm(false); setEditingId(null); }}
              className="px-4 py-2 border border-border hover:bg-surface-hover rounded-lg text-sm">
              取消
            </button>
          </div>
        </div>
      )}

      {/* 任务列表 */}
      <div className="space-y-3">
        {tasks.length === 0 ? (
          <div className="bg-surface rounded-xl border border-border p-12 text-center text-gray-500">
            <Clock className="w-12 h-12 mx-auto mb-3 text-gray-600" />
            暂无定时任务，点击上方按钮创建
          </div>
        ) : (
          tasks.map((task) => (
            <div key={task.id}
              className="bg-surface rounded-xl border border-border p-4 hover:border-accent/30 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${task.enabled ? 'bg-fall' : 'bg-gray-600'}`} />
                    <span className="font-medium">{task.name}</span>
                    <span className="text-xs bg-accent/10 text-accent px-2 py-0.5 rounded">{task.strategy}</span>
                  </div>
                  <div className="text-sm text-gray-400 flex items-center gap-4">
                    <span className="font-mono text-xs">{task.cron_expr}</span>
                    <span>下次: {formatTime(task.next_run_at)}</span>
                    {task.last_run_at && <span>上次: {formatTime(task.last_run_at)}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => handleToggle(task)}
                    className="p-1.5 rounded-lg hover:bg-surface-hover text-gray-400 hover:text-white"
                    title={task.enabled ? '暂停' : '启用'}
                  >
                    {task.enabled ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  </button>
                  <button onClick={() => handleRun(task.id)}
                    disabled={running.has(task.id)}
                    className="p-1.5 rounded-lg hover:bg-surface-hover text-gray-400 hover:text-accent"
                    title="立即执行"
                  >
                    <RotateCw className={`w-4 h-4 ${running.has(task.id) ? 'animate-spin' : ''}`} />
                  </button>
                  <button onClick={() => handleEdit(task)}
                    className="text-xs px-2 py-1 rounded-lg hover:bg-surface-hover text-gray-400 hover:text-white"
                  >
                    编辑
                  </button>
                  <button onClick={() => handleDelete(task.id)}
                    className="p-1.5 rounded-lg hover:bg-rise/10 text-gray-400 hover:text-rise"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
