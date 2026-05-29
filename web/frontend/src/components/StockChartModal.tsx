import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CandlestickSeries, type IChartApi, type ISeriesApi, type CandlestickData, type Time } from 'lightweight-charts';
import { X, TrendingUp, Loader2 } from 'lucide-react';
import { apiGet } from '@/api';

interface KlineItem {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface KlineResponse {
  code: string;
  name: string;
  period: string;
  data: KlineItem[];
}

interface Props {
  code: string;
  name: string;
  onClose: () => void;
}

type TabKey = 'daily' | 'weekly' | 'monthly';

const TABS: { key: TabKey; label: string; count: number }[] = [
  { key: 'daily', label: '日K', count: 120 },
  { key: 'weekly', label: '周K', count: 100 },
  { key: 'monthly', label: '月K', count: 60 },
];

export default function StockChartModal({ code, name, onClose }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);
  const candleSeries = useRef<ISeriesApi<'Candlestick'> | null>(null);

  const [tab, setTab] = useState<TabKey>('daily');
  const [data, setData] = useState<KlineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // 加载数据
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    const t = TABS.find((t) => t.key === tab)!;
    apiGet<KlineResponse>(`/api/v1/stock/${code}/kline`, { params: { period: t.key, count: t.count } })
      .then((res) => {
        if (!cancelled) setData(res.data ?? []);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [code, tab]);

  // 渲染图表
  useEffect(() => {
    if (!chartRef.current || data.length === 0) return;

    // 清理旧实例
    if (chartInstance.current) {
      chartInstance.current.remove();
      chartInstance.current = null;
    }

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 500,
      layout: {
        background: { type: ColorType.Solid, color: '#0f0f1a' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#1e1e2e' },
        horzLines: { color: '#1e1e2e' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: '#6366f1', width: 1, style: 2 },
        horzLine: { color: '#6366f1', width: 1, style: 2 },
      },
      rightPriceScale: { borderColor: '#2e2e42' },
      timeScale: {
        borderColor: '#2e2e42',
        timeVisible: true,
      },
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#22c55e',
      borderUpColor: '#ef4444',
      borderDownColor: '#22c55e',
      wickUpColor: '#ef4444',
      wickDownColor: '#22c55e',
    });

    const candleData: CandlestickData[] = data.map((d) => ({
      time: (d.time + (tab === 'daily' ? '' : '')) as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    candles.setData(candleData);
    chart.timeScale().fitContent();

    chartInstance.current = chart;
    candleSeries.current = candles;

    // resize
    const onResize = () => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      chart.remove();
      chartInstance.current = null;
    };
  }, [data, tab]);

  // ESC 关闭
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-surface rounded-2xl border border-border w-[90vw] max-w-5xl max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-5 h-5 text-accent" />
            <span className="font-semibold text-lg">{name}</span>
            <span className="text-gray-500 font-mono text-sm">{code}</span>
          </div>
          <div className="flex items-center gap-2">
            {/* Tabs */}
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  tab === t.key
                    ? 'bg-accent text-white'
                    : 'bg-surface-active text-gray-400 hover:text-white'
                }`}
              >
                {t.label}
              </button>
            ))}
            <button onClick={onClose} className="ml-3 p-1 rounded-lg hover:bg-surface-hover text-gray-400 hover:text-white">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Chart */}
        <div className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-surface/80 z-10">
              <Loader2 className="w-8 h-8 text-accent animate-spin" />
            </div>
          )}
          {error && (
            <div className="absolute inset-0 flex items-center justify-center text-rise text-sm">
              {error}
            </div>
          )}
          <div ref={chartRef} className="w-full h-full min-h-[500px]" />
        </div>

        {/* Footer */}
        {data.length > 0 && (
          <div className="px-5 py-2 border-t border-border text-xs text-gray-500">
            共 {data.length} 条 · 最新: ¥{data[data.length - 1]?.close.toFixed(2)} · 前复权
          </div>
        )}
      </div>
    </div>
  );
}
