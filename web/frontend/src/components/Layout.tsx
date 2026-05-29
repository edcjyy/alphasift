import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Search,
  History,
  Layers,
  Clock,
  Settings as SettingsIcon,
  Activity,
  Brain,
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { apiGet } from '@/api';
import type { HealthResponse } from '@/types';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/screen', label: '选股', icon: Search },
  { to: '/runs', label: '运行记录', icon: History },
  { to: '/strategies', label: '策略管理', icon: Layers },
  { to: '/evolution', label: '策略进化', icon: Brain },
  { to: '/schedule', label: '定时任务', icon: Clock },
  { to: '/settings', label: '设置', icon: SettingsIcon },
];

export default function Layout() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    apiGet<HealthResponse>('/api/v1/system/health')
      .then(setHealth)
      .catch(() => {});
  }, []);

  return (
    <div className="flex h-screen">
      {/* 侧边栏 */}
      <aside className="w-56 bg-surface border-r border-border flex flex-col">
        <div className="h-14 flex items-center px-4 border-b border-border">
          <Activity className="w-5 h-5 text-accent mr-2" />
          <span className="font-semibold text-lg">AlphaSift</span>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-surface-active text-white'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-surface-hover'
                }`
              }
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {health && (
          <div className="p-3 border-t border-border text-xs text-gray-500 space-y-1">
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  health.status === 'ok' ? 'bg-fall' : 'bg-rise'
                }`}
              />
              数据源:{' '}
              {Array.isArray(health.details.snapshot_sources)
                ? health.details.snapshot_sources.join(',')
                : health.details.snapshot_sources}
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  health.details.llm_status === '已配置' ? 'bg-fall' : 'bg-gray-600'
                }`}
              />
              LLM:{' '}
              {health.details.llm_status === '已配置' ? '可用' : '不可用'}
            </div>
          </div>
        )}
      </aside>

      {/* 主内容区 */}
      <main className="flex-1 overflow-auto bg-gray-950">
        <Outlet />
      </main>
    </div>
  );
}
