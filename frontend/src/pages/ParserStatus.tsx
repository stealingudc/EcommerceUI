/**
 * ParserStatus — Monitor parser health with dual status system,
 * coverage progress bars, run log table, and activity legend.
 */
import { useState, useEffect, useCallback } from 'react';
import { fetchParserStatus, fetchParserRuns } from '../api';

interface Parser {
  id: number;
  name: string;
  category: string | null;
  total_products: number;
  products_24h: number;
  products_48h: number;
  coverage_pct: number;
  last_stock_update: string | null;
  run_status: string;
  activity_status: string;
  last_run_status: string | null;
  avg_duration: number | null;
  hours_since_run: number | null;
}

interface RunLog {
  id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  products_found: number;
  products_parsed_success: number;
  products_parsed_failed: number;
  duration_seconds: number | null;
  error_message: string | null;
}

const STATUS_BADGES: Record<string, { cls: string; label: string }> = {
  Healthy: { cls: 'badge-healthy', label: 'Healthy' },
  Warning: { cls: 'badge-warning', label: 'Warning' },
  Stale: { cls: 'badge-error', label: 'Stale' },
  Running: { cls: 'badge-info', label: 'Running' },
  Error: { cls: 'badge-error', label: 'Error' },
  Unknown: { cls: 'badge-neutral', label: 'Unknown' },
};

const ACTIVITY_BADGES: Record<string, { cls: string; label: string }> = {
  Active: { cls: 'badge-healthy', label: 'Active' },
  Partial: { cls: 'badge-warning', label: 'Partial' },
  Stale: { cls: 'badge-error', label: 'Stale' },
  Inactive: { cls: 'badge-error', label: 'Inactive' },
};

function ProgressBar({ pct }: { pct: number }) {
  const color = pct >= 80 ? 'var(--color-emerald-400)' : pct >= 50 ? 'var(--color-amber-400)' : pct >= 20 ? '#f97316' : 'var(--color-red-400)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
      <div style={{ flex: 1, height: 6, background: 'rgba(148,163,184,0.1)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', background: color, borderRadius: 3, transition: 'width var(--transition-slow)' }} />
      </div>
      <span className="text-mono text-xs" style={{ width: 36, textAlign: 'right' }}>{pct.toFixed(0)}%</span>
    </div>
  );
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const hrs = diff / 3600000;
  if (hrs < 1) return `${Math.round(diff / 60000)}m ago`;
  if (hrs < 24) return `${Math.round(hrs)}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export default function ParserStatus() {
  const [parsers, setParsers] = useState<Parser[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedParserId, setSelectedParserId] = useState<number | null>(null);
  const [runLogs, setRunLogs] = useState<RunLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchParserStatus();
      setParsers(res.data.parsers || []);
    } catch (err) {
      console.error('ParserStatus load failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const loadRunLogs = async (parserId: number) => {
    if (selectedParserId === parserId) { setSelectedParserId(null); return; }
    setSelectedParserId(parserId);
    setLogsLoading(true);
    try {
      const res = await fetchParserRuns(parserId);
      setRunLogs(res.data.runs || []);
    } catch {
      setRunLogs([]);
    } finally {
      setLogsLoading(false);
    }
  };

  const selectedParser = parsers.find(p => p.id === selectedParserId);

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div className="flex items-center gap-4">
          <h1>Parser Status</h1>
          <span className="text-sm text-muted">{parsers.length} parsers</span>
        </div>
      </div>

      {/* Parser Cards Grid */}
      {loading ? (
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="card skeleton" style={{ height: 180 }} />)}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4" style={{ marginBottom: 'var(--spacing-8)' }}>
          {parsers.map(p => {
            const runBadge = STATUS_BADGES[p.run_status] || STATUS_BADGES.Unknown;
            const actBadge = ACTIVITY_BADGES[p.activity_status] || ACTIVITY_BADGES.Inactive;
            return (
              <div
                key={p.id}
                className={`card ${selectedParserId === p.id ? 'parser-card-active' : ''}`}
                style={{ padding: 'var(--spacing-5)', cursor: 'pointer' }}
                onClick={() => loadRunLogs(p.id)}
              >
                <div className="flex justify-between items-center" style={{ marginBottom: 'var(--spacing-3)' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{p.name}</div>
                    {p.category && <div className="text-xs text-muted">{p.category}</div>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`badge ${runBadge.cls}`}>{runBadge.label}</span>
                    <span className={`badge ${actBadge.cls}`}>{actBadge.label}</span>
                  </div>
                </div>

                <div className="flex flex-col gap-2" style={{ fontSize: '0.8125rem' }}>
                  <div className="flex justify-between">
                    <span className="text-muted">Products</span>
                    <span className="text-mono">{p.total_products.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">24h Updates</span>
                    <span className={`text-mono ${p.products_24h > 0 ? 'text-success' : ''}`}>{p.products_24h.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">48h Updates</span>
                    <span className="text-mono">{p.products_48h.toLocaleString()}</span>
                  </div>
                  <div>
                    <div className="flex justify-between" style={{ marginBottom: 2 }}>
                      <span className="text-muted">Coverage</span>
                    </div>
                    <ProgressBar pct={p.coverage_pct} />
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Last Run</span>
                    <span className="text-xs">{timeAgo(p.last_stock_update)}</span>
                  </div>
                  {p.avg_duration != null && (
                    <div className="flex justify-between">
                      <span className="text-muted">Avg Duration</span>
                      <span className="text-mono text-xs">{p.avg_duration.toFixed(0)}s</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Run Log Table */}
      {selectedParserId && (
        <div className="card animate-fade-in" style={{ padding: 0, overflow: 'hidden', marginBottom: 'var(--spacing-8)' }}>
          <div style={{ padding: 'var(--spacing-4) var(--spacing-5)', borderBottom: '1px solid var(--table-border)' }}>
            <h3>Run Logs — {selectedParser?.name}</h3>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>Duration</th>
                  <th>Products Found</th>
                  <th>Success</th>
                  <th>Failed</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {logsLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}><td colSpan={8}><div className="skeleton skeleton-text" /></td></tr>
                  ))
                ) : runLogs.length === 0 ? (
                  <tr><td colSpan={8} className="text-muted" style={{ textAlign: 'center', padding: 'var(--spacing-8)' }}>No run logs found</td></tr>
                ) : runLogs.map(r => (
                  <tr key={r.id}>
                    <td>
                      <span className={`badge ${r.status === 'success' ? 'badge-healthy' : r.status === 'running' ? 'badge-info' : 'badge-error'}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="text-xs">{new Date(r.started_at).toLocaleString()}</td>
                    <td className="text-xs">{r.finished_at ? new Date(r.finished_at).toLocaleString() : '—'}</td>
                    <td className="text-mono text-xs">{r.duration_seconds ? `${r.duration_seconds.toFixed(1)}s` : '—'}</td>
                    <td className="text-mono">{r.products_found}</td>
                    <td className="text-mono text-success">{r.products_parsed_success}</td>
                    <td className={`text-mono ${r.products_parsed_failed > 0 ? 'text-error' : ''}`}>{r.products_parsed_failed}</td>
                    <td className="text-xs text-error">{r.error_message || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Activity Legend */}
      <div className="card" style={{ padding: 'var(--spacing-5)' }}>
        <h3 style={{ marginBottom: 'var(--spacing-3)' }}>Activity Status Legend</h3>
        <div className="flex gap-6 flex-wrap" style={{ fontSize: '0.8125rem' }}>
          <div className="flex items-center gap-2">
            <span className="badge badge-healthy">Active</span>
            <span className="text-muted">&gt;50% updated in 24h</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge badge-warning">Partial</span>
            <span className="text-muted">10-50% updated in 24h</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge badge-error">Stale</span>
            <span className="text-muted">&lt;10% in 24h, some in 48h</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge badge-error">Inactive</span>
            <span className="text-muted">&lt;10% updated in 48h</span>
          </div>
        </div>
      </div>

      <style>{`
        .parser-card-active {
          border-color: var(--color-accent-primary) !important;
          box-shadow: 0 0 0 1px var(--color-accent-primary);
        }
      `}</style>
    </div>
  );
}
