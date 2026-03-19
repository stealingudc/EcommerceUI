/**
 * SystemMonitoring — Dashboard showing MV status, refresh schedule,
 * database stats, score distribution, and manual refresh controls.
 */
import { useState, useEffect, useCallback } from 'react';
import { fetchSystemMonitoring, refreshSingleMV } from '../api';
import './SystemMonitoring.css';

interface MVInfo {
  name: string;
  exists: boolean;
  row_count: number | null;
  size_bytes: number | null;
  size_pretty: string | null;
}

interface MonitoringData {
  materialized_views: MVInfo[];
  schedule: {
    type: string;
    target_hour: string;
    next_refresh_at: string;
    seconds_until_refresh: number;
  };
  database: {
    size: string | null;
    table_counts: Record<string, number | null>;
  };
  score_distribution: Record<string, number>;
}

function formatCountdown(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function formatNumber(n: number | null): string {
  if (n === null || n === undefined) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

const GRADE_COLORS: Record<string, string> = {
  A: '#22c55e',
  B: '#6366f1',
  C: '#eab308',
  D: '#f97316',
  F: '#71717a',
};

export default function SystemMonitoring() {
  const [data, setData] = useState<MonitoringData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshingMV, setRefreshingMV] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);

  const loadData = useCallback(async () => {
    try {
      const res = await fetchSystemMonitoring();
      setData(res.data);
      setCountdown(res.data.schedule.seconds_until_refresh);
    } catch (err) {
      console.error('Failed to load monitoring data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Countdown timer
  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setInterval(() => {
      setCountdown(prev => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [countdown]);

  const handleRefreshMV = async (mvName: string) => {
    setRefreshingMV(mvName);
    try {
      await refreshSingleMV(mvName);
      await loadData();
    } catch (err) {
      console.error(`Failed to refresh ${mvName}:`, err);
    } finally {
      setRefreshingMV(null);
    }
  };

  if (loading) {
    return (
      <div className="mon-page">
        <div className="mon-header">
          <h1>System Monitoring</h1>
        </div>
        <div className="mon-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card mon-skeleton">
              <div className="skeleton skeleton-text" style={{ width: '60%' }} />
              <div className="skeleton skeleton-text" style={{ width: '80%' }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mon-page">
        <div className="mon-header"><h1>System Monitoring</h1></div>
        <p className="text-muted">Failed to load monitoring data.</p>
      </div>
    );
  }

  const totalGraded = Object.values(data.score_distribution).reduce((a, b) => a + b, 0);

  return (
    <div className="mon-page">
      {/* Header */}
      <div className="mon-header">
        <h1>System Monitoring</h1>
        <button className="btn btn-primary" onClick={loadData}>↻ Refresh</button>
      </div>

      {/* Stats Cards */}
      <div className="mon-stats-row">
        <div className="card mon-stat-card">
          <div className="mon-stat-label">Database Size</div>
          <div className="mon-stat-value">{data.database.size || '—'}</div>
        </div>
        <div className="card mon-stat-card">
          <div className="mon-stat-label">Products</div>
          <div className="mon-stat-value">{formatNumber(data.database.table_counts.products)}</div>
        </div>
        <div className="card mon-stat-card">
          <div className="mon-stat-label">Stock History</div>
          <div className="mon-stat-value">{formatNumber(data.database.table_counts.stock_history)}</div>
        </div>
        <div className="card mon-stat-card">
          <div className="mon-stat-label">Price History</div>
          <div className="mon-stat-value">{formatNumber(data.database.table_counts.price_history)}</div>
        </div>
        <div className="card mon-stat-card mon-stat-countdown">
          <div className="mon-stat-label">Next MV Refresh</div>
          <div className="mon-stat-value">{formatCountdown(countdown)}</div>
          <div className="mon-stat-sublabel">Daily at {data.schedule.target_hour}</div>
        </div>
      </div>

      {/* Score Distribution */}
      {totalGraded > 0 && (
        <div className="card mon-score-card">
          <h2>Score Distribution</h2>
          <div className="mon-score-grid">
            {['A', 'B', 'C', 'D', 'F'].map(grade => {
              const count = data.score_distribution[grade] || 0;
              const pct = totalGraded > 0 ? ((count / totalGraded) * 100).toFixed(1) : '0';
              return (
                <div key={grade} className="mon-score-item">
                  <div className="mon-score-bar-container">
                    <div
                      className="mon-score-bar"
                      style={{
                        height: `${Math.max(4, (count / totalGraded) * 100)}%`,
                        backgroundColor: GRADE_COLORS[grade],
                      }}
                    />
                  </div>
                  <div className="mon-score-label" style={{ color: GRADE_COLORS[grade] }}>
                    {grade}
                  </div>
                  <div className="mon-score-count">{formatNumber(count)}</div>
                  <div className="mon-score-pct">{pct}%</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* MV Table */}
      <div className="card mon-mv-card">
        <h2>Materialized Views</h2>
        <div className="mon-mv-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Size</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.materialized_views.map(mv => (
                <tr key={mv.name}>
                  <td className="mon-mv-name">{mv.name}</td>
                  <td>
                    <span className={`badge ${mv.exists ? 'badge-healthy' : 'badge-error'}`}>
                      {mv.exists ? 'Active' : 'Missing'}
                    </span>
                  </td>
                  <td className="text-mono">{formatNumber(mv.row_count)}</td>
                  <td className="text-mono text-sm">{mv.size_pretty || '—'}</td>
                  <td>
                    <button
                      className="btn btn-ghost btn-sm"
                      disabled={!mv.exists || refreshingMV === mv.name}
                      onClick={() => handleRefreshMV(mv.name)}
                    >
                      {refreshingMV === mv.name ? '⏳' : '↻'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
