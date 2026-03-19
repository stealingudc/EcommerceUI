/**
 * PipelineStatusView — Products at a specific pipeline stage with
 * status tabs, comprehensive filters, financial KPIs, and Excel export.
 */
import { useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { fetchPipelineStatus, exportPipelineExcel } from '../api';

const STATUSES = [
  { slug: 'new', label: 'New' },
  { slug: 'supplier-info', label: 'Waiting for Supplier Info' },
  { slug: 'financial-review', label: 'Financial Review' },
  { slug: 'market-research', label: 'Market Research' },
  { slug: 'approved', label: 'Approved' },
  { slug: 'hold', label: 'Hold' },
  { slug: 'discarded', label: 'Discarded' },
];

const RANKING_OPTIONS = [
  { value: '', label: 'All Rankings' },
  { value: 'High', label: 'High' },
  { value: 'Good', label: 'Good' },
  { value: 'Slow', label: 'Slow' },
  { value: 'Poor', label: 'Poor' },
];

const MARGIN_OPTIONS = [
  { value: '', label: 'All Margins' },
  { value: 'Healthy', label: 'Healthy (≥50%)' },
  { value: 'Average', label: 'Average (30-50%)' },
  { value: 'Low', label: 'Low (<30%)' },
];

interface PipelineProduct {
  id: number;
  image: string;
  title: string;
  parser_name: string;
  group_name: string | null;
  sales_ranking: string | null;
  categories: string;
  retail_price: number | null;
  cogs_usd: number | null;
  gross_margin: number | null;
  margin_health: string | null;
  suggested_qty_min: number | null;
  suggested_qty_max: number | null;
}

const emptyForm = {
  title: '',
  sales_ranking: '',
  margin_health: '',
  min_price: '',
  max_price: '',
  min_cogs: '',
  max_cogs: '',
};

export default function PipelineStatusView() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();

  const [products, setProducts] = useState<PipelineProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  // Filter form state (local, applied on button click)
  const [form, setForm] = useState(emptyForm);
  const [appliedFilters, setAppliedFilters] = useState(emptyForm);
  const [showFilters, setShowFilters] = useState(false);

  const [sortBy, setSortBy] = useState('id');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);

  const updateField = (key: string, value: string) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const applyFilters = () => {
    setAppliedFilters({ ...form });
    setPage(1);
  };

  const clearFilters = () => {
    setForm(emptyForm);
    setAppliedFilters(emptyForm);
    setPage(1);
  };

  // Reset on slug change
  useEffect(() => { setPage(1); setForm(emptyForm); setAppliedFilters(emptyForm); }, [slug]);

  const loadData = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    try {
      const params: Record<string, any> = { page, sort_by: sortBy, sort_dir: sortDir };
      if (appliedFilters.title) params.title = appliedFilters.title;
      if (appliedFilters.sales_ranking) params.sales_ranking = appliedFilters.sales_ranking;
      if (appliedFilters.margin_health) params.margin_health = appliedFilters.margin_health;
      if (appliedFilters.min_price) params.min_price = parseFloat(appliedFilters.min_price);
      if (appliedFilters.max_price) params.max_price = parseFloat(appliedFilters.max_price);
      if (appliedFilters.min_cogs) params.min_cogs = parseFloat(appliedFilters.min_cogs);
      if (appliedFilters.max_cogs) params.max_cogs = parseFloat(appliedFilters.max_cogs);
      const res = await fetchPipelineStatus(slug, params);
      setProducts(res.data.products || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error('Pipeline status load failed:', err);
    } finally {
      setLoading(false);
    }
  }, [slug, page, sortBy, sortDir, appliedFilters]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSort = (key: string) => {
    if (sortBy === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(key); setSortDir('desc'); }
    setPage(1);
  };

  const handleExport = async () => {
    if (!slug) return;
    setExporting(true);
    try {
      const res = await exportPipelineExcel(slug);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `pipeline-${slug}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  const currentLabel = STATUSES.find(s => s.slug === slug)?.label || slug;
  const activeCount = Object.values(appliedFilters).filter(v => v !== '').length;

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div className="flex items-center gap-4">
          <h1>{currentLabel}</h1>
          <span className="text-sm text-muted">{total} products</span>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn btn-ghost btn-sm" onClick={() => setShowFilters(!showFilters)}>
            {showFilters ? '▲ Filters' : '▼ Filters'}{activeCount > 0 ? ` (${activeCount})` : ''}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={handleExport} disabled={exporting}>📊 Export Excel</button>
        </div>
      </div>

      {/* Status Tabs */}
      <div className="flex gap-1" style={{ marginBottom: 'var(--spacing-6)', overflowX: 'auto' }}>
        {STATUSES.map(s => (
          <button
            key={s.slug}
            className={`btn btn-sm ${s.slug === slug ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => navigate(`/pipeline/${s.slug}`)}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="card animate-fade-in" style={{ marginBottom: 'var(--spacing-6)', padding: 'var(--spacing-4) var(--spacing-5)' }}>
          <div className="flex items-center gap-3 flex-wrap">
            <input className="input" placeholder="Search name, title, or #ID..." value={form.title}
              onChange={e => updateField('title', e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') applyFilters(); }}
              style={{ maxWidth: 220 }} />
            <select className="select" value={form.sales_ranking} onChange={e => updateField('sales_ranking', e.target.value)} style={{ maxWidth: 140 }}>
              {RANKING_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <select className="select" value={form.margin_health} onChange={e => updateField('margin_health', e.target.value)} style={{ maxWidth: 150 }}>
              {MARGIN_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-3 flex-wrap" style={{ marginTop: 'var(--spacing-3)' }}>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted">Price (RON)</span>
              <input className="input" type="number" placeholder="Min" value={form.min_price}
                onChange={e => updateField('min_price', e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') applyFilters(); }}
                style={{ width: 80 }} />
              <span className="text-xs text-muted">–</span>
              <input className="input" type="number" placeholder="Max" value={form.max_price}
                onChange={e => updateField('max_price', e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') applyFilters(); }}
                style={{ width: 80 }} />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted">COGS (USD)</span>
              <input className="input" type="number" placeholder="Min" value={form.min_cogs}
                onChange={e => updateField('min_cogs', e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') applyFilters(); }}
                style={{ width: 80 }} />
              <span className="text-xs text-muted">–</span>
              <input className="input" type="number" placeholder="Max" value={form.max_cogs}
                onChange={e => updateField('max_cogs', e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') applyFilters(); }}
                style={{ width: 80 }} />
            </div>
          </div>
          <div className="flex items-center gap-2" style={{ marginTop: 'var(--spacing-3)', justifyContent: 'flex-end' }}>
            <button className="btn btn-ghost btn-sm" onClick={clearFilters}>✕ Clear</button>
            <button className="btn btn-primary btn-sm" onClick={applyFilters}>🔍 Apply Filters</button>
          </div>
        </div>
      )}

      {/* Data Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 50 }}></th>
                <th className={sortBy === 'id' ? 'sorted' : ''} onClick={() => handleSort('id')}>ID</th>
                <th className={sortBy === 'title' ? 'sorted' : ''} onClick={() => handleSort('title')}>Title</th>
                <th className={sortBy === 'parser_name' ? 'sorted' : ''} onClick={() => handleSort('parser_name')}>Store</th>
                <th>Group</th>
                <th>Rank</th>
                <th>Categories</th>
                <th className={sortBy === 'retail_price' ? 'sorted' : ''} onClick={() => handleSort('retail_price')}>Retail (RON)</th>
                <th className={sortBy === 'cogs_usd' ? 'sorted' : ''} onClick={() => handleSort('cogs_usd')}>COGS (USD)</th>
                <th className={sortBy === 'gross_margin' ? 'sorted' : ''} onClick={() => handleSort('gross_margin')}>Margin %</th>
                <th>Health</th>
                <th>Qty Range</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}><td colSpan={13}><div className="skeleton skeleton-text" style={{ width: `${50 + Math.random() * 40}%` }} /></td></tr>
                ))
              ) : products.length === 0 ? (
                <tr><td colSpan={13} className="text-muted" style={{ textAlign: 'center', padding: 'var(--spacing-12)' }}>No products at this status</td></tr>
              ) : products.map(p => (
                <tr key={p.id}>
                  <td>
                    <div className="dash-thumb">
                      {p.image ? <img src={p.image} alt="" loading="lazy" /> : <div className="dash-thumb-empty">?</div>}
                    </div>
                  </td>
                  <td className="text-mono text-sm">{p.id}</td>
                  <td>
                    <Link className="dash-product-link" to={`/product/${p.id}/pipeline-details`}>{p.title || `Product #${p.id}`}</Link>
                  </td>
                  <td className="text-sm text-muted">{p.parser_name}</td>
                  <td className="text-sm">{p.group_name || '—'}</td>
                  <td>
                    {p.sales_ranking ? (
                      <span className={`badge ${p.sales_ranking === 'High' ? 'badge-healthy' : p.sales_ranking === 'Good' ? 'badge-info' : p.sales_ranking === 'Slow' ? 'badge-warning' : 'badge-error'}`}>
                        {p.sales_ranking}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="text-xs text-muted">{p.categories || '—'}</td>
                  <td className="text-mono">{p.retail_price?.toFixed(2) ?? '—'}</td>
                  <td className="text-mono">{p.cogs_usd?.toFixed(2) ?? '—'}</td>
                  <td className={`text-mono ${p.gross_margin != null ? (p.gross_margin >= 50 ? 'text-success' : p.gross_margin >= 30 ? 'text-warning' : 'text-error') : ''}`} style={{ fontWeight: 600 }}>
                    {p.gross_margin != null ? `${p.gross_margin.toFixed(1)}%` : '—'}
                  </td>
                  <td>
                    {p.margin_health ? (
                      <span className={`badge ${p.margin_health === 'Healthy' ? 'badge-healthy' : p.margin_health === 'Average' ? 'badge-warning' : 'badge-error'}`}>
                        {p.margin_health}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="text-mono text-sm">
                    {p.suggested_qty_min || p.suggested_qty_max ? `${p.suggested_qty_min ?? '—'} – ${p.suggested_qty_max ?? '—'}` : '—'}
                  </td>
                  <td>
                    <Link className="btn btn-ghost btn-sm" to={`/product/${p.id}/pipeline-details`}>Open →</Link>
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
