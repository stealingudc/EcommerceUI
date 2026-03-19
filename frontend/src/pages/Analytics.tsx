/**
 * Analytics — Store KPI table with grand totals + 4 horizontal bar chart panels.
 */
import { useState, useEffect, useCallback } from 'react';
import { fetchAnalytics, fetchStoreAnalytics, refreshStoreAnalytics } from '../api';

interface StoreKPI {
  store: string;
  products: number;
  active_products: number;
  total_stock: number;
  avg_price: number;
  vendors: number;
  revenue_30d: number;
  units_sold_30d: number;
  sell_through_pct: number;
  stock_turnover: number;
}

interface ChartData {
  label: string;
  value: number;
}

function HorizontalBarChart({ data, color, label }: { data: ChartData[]; color: string; label: string }) {
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div className="card" style={{ padding: 'var(--spacing-5)' }}>
      <h3 style={{ marginBottom: 'var(--spacing-4)' }}>{label}</h3>
      <div className="flex flex-col gap-2">
        {data.slice(0, 10).map((d, i) => (
          <div key={i} className="flex items-center gap-3" style={{ fontSize: '0.8125rem' }}>
            <span className="text-sm truncate" style={{ width: 120, flexShrink: 0, textAlign: 'right', color: 'var(--color-text-secondary)' }}>
              {d.label}
            </span>
            <div style={{ flex: 1, height: 22, background: 'rgba(148,163,184,0.06)', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
              <div style={{
                width: `${(d.value / max) * 100}%`,
                height: '100%',
                background: `linear-gradient(90deg, ${color}, ${color}dd)`,
                borderRadius: 'var(--radius-sm)',
                transition: 'width var(--transition-slow)',
                minWidth: d.value > 0 ? 4 : 0,
              }} />
            </div>
            <span className="text-mono text-sm" style={{ width: 50, textAlign: 'right', fontWeight: 500 }}>
              {d.value.toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Analytics() {
  const [stores, setStores] = useState<StoreKPI[]>([]);
  const [charts, setCharts] = useState<{ vendors: ChartData[]; pipeline: ChartData[]; rankings: ChartData[]; per_store: ChartData[] }>({
    vendors: [], pipeline: [], rankings: [], per_store: []
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [storeRes, chartRes] = await Promise.all([fetchStoreAnalytics(), fetchAnalytics()]);
      setStores(storeRes.data.stores || []);
      setCharts({
        vendors: chartRes.data.vendors || [],
        pipeline: chartRes.data.pipeline || [],
        rankings: chartRes.data.rankings || [],
        per_store: chartRes.data.per_store || [],
      });
    } catch (err) {
      console.error('Analytics load failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await refreshStoreAnalytics(); await loadData(); } finally { setRefreshing(false); }
  };

  // Grand totals
  const totals = stores.reduce((acc, s) => ({
    products: acc.products + s.products,
    active_products: acc.active_products + s.active_products,
    total_stock: acc.total_stock + s.total_stock,
    avg_price: 0,
    vendors: acc.vendors + s.vendors,
    revenue_30d: acc.revenue_30d + s.revenue_30d,
    units_sold_30d: acc.units_sold_30d + s.units_sold_30d,
    sell_through_pct: 0,
    stock_turnover: 0,
  }), { products: 0, active_products: 0, total_stock: 0, avg_price: 0, vendors: 0, revenue_30d: 0, units_sold_30d: 0, sell_through_pct: 0, stock_turnover: 0 });
  totals.avg_price = stores.length ? stores.reduce((s, r) => s + r.avg_price, 0) / stores.length : 0;

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <h1>Analytics</h1>
        <button className={`btn btn-ghost btn-sm ${refreshing ? 'animate-pulse' : ''}`} onClick={handleRefresh} disabled={refreshing}>
          ↻ Refresh
        </button>
      </div>

      {/* Store KPI Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: 'var(--spacing-8)' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Store</th>
                <th>Products</th>
                <th>Active</th>
                <th>Total Stock</th>
                <th>Avg Price</th>
                <th>Vendors</th>
                <th>Revenue (30d)</th>
                <th>Units Sold (30d)</th>
                <th>Sell-Through %</th>
                <th>Stock Turnover</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}><td colSpan={10}><div className="skeleton skeleton-text" style={{ width: `${50 + Math.random() * 40}%` }} /></td></tr>
                ))
              ) : stores.length === 0 ? (
                <tr><td colSpan={10} className="text-muted" style={{ textAlign: 'center', padding: 'var(--spacing-12)' }}>No store data</td></tr>
              ) : (
                <>
                  {stores.map((s, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 500 }}>{s.store}</td>
                      <td className="text-mono">{s.products.toLocaleString()}</td>
                      <td className="text-mono">{s.active_products.toLocaleString()}</td>
                      <td className="text-mono">{s.total_stock.toLocaleString()}</td>
                      <td className="text-mono">{s.avg_price.toFixed(2)}</td>
                      <td className="text-mono">{s.vendors}</td>
                      <td className="text-mono text-success" style={{ fontWeight: 600 }}>{s.revenue_30d.toLocaleString()}</td>
                      <td className="text-mono">{s.units_sold_30d.toLocaleString()}</td>
                      <td className="text-mono">{s.sell_through_pct.toFixed(1)}%</td>
                      <td className="text-mono">{s.stock_turnover.toFixed(2)}</td>
                    </tr>
                  ))}
                  {/* Grand totals row */}
                  <tr style={{ background: 'var(--table-header-bg)', fontWeight: 600 }}>
                    <td>Total</td>
                    <td className="text-mono">{totals.products.toLocaleString()}</td>
                    <td className="text-mono">{totals.active_products.toLocaleString()}</td>
                    <td className="text-mono">{totals.total_stock.toLocaleString()}</td>
                    <td className="text-mono">{totals.avg_price.toFixed(2)}</td>
                    <td className="text-mono">{totals.vendors}</td>
                    <td className="text-mono text-success">{totals.revenue_30d.toLocaleString()}</td>
                    <td className="text-mono">{totals.units_sold_30d.toLocaleString()}</td>
                    <td className="text-mono">—</td>
                    <td className="text-mono">—</td>
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4 Chart Panels */}
      <div className="grid grid-cols-2 gap-6">
        <HorizontalBarChart data={charts.vendors} color="#6366f1" label="Top Vendors" />
        <HorizontalBarChart data={charts.pipeline} color="#34d399" label="Pipeline Distribution" />
        <HorizontalBarChart data={charts.rankings} color="#fbbf24" label="Sales Rankings" />
        <HorizontalBarChart data={charts.per_store} color="#22d3ee" label="Products per Store" />
      </div>
    </div>
  );
}
