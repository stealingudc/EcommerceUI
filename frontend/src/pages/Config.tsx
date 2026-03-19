/**
 * Config — 3-tab configuration with CRUD for categories/groups,
 * parser category assignment, and application settings with inline editing.
 */
import { useState, useEffect, useCallback } from 'react';
import {
  fetchConfig, createProductCategory, updateProductCategory, deleteProductCategory,
  createParserCategory, createProductGroup, updateProductGroup, deleteProductGroup,
  assignParserCategories, updateSetting, triggerSalesRankings
} from '../api';

interface Category { id: number; name: string; code?: string; }
interface ParserAssign { id: number; name: string; category: string | null; }
interface AppSetting { key: string; value: string; type: string; description: string; }

type Tab = 'categories' | 'parsers' | 'settings';

export default function Config() {
  const [tab, setTab] = useState<Tab>('categories');
  const [loading, setLoading] = useState(true);

  // Data
  const [productCategories, setProductCategories] = useState<Category[]>([]);
  const [parserCategories, setParserCategories] = useState<Category[]>([]);
  const [productGroups, setProductGroups] = useState<Category[]>([]);
  const [parsers, setParsers] = useState<ParserAssign[]>([]);
  const [settings, setSettings] = useState<AppSetting[]>([]);

  // Forms
  const [newCatName, setNewCatName] = useState('');
  const [newCatCode, setNewCatCode] = useState('');
  const [newParserCat, setNewParserCat] = useState('');
  const [newGroupName, setNewGroupName] = useState('');

  // Inline edit tracking
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [recalculating, setRecalculating] = useState(false);

  // Category / Group inline editing
  const [editingCatId, setEditingCatId] = useState<number | null>(null);
  const [editCatName, setEditCatName] = useState('');
  const [editCatCode, setEditCatCode] = useState('');
  const [editingGroupId, setEditingGroupId] = useState<number | null>(null);
  const [editGroupName, setEditGroupName] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchConfig();
      const d = res.data;
      setProductCategories(d.categories || []);
      // Derive parser categories from unique parser category values
      const uniqueCats = [...new Set<string>((d.parsers || []).map((p: any) => p.category).filter(Boolean))];
      setParserCategories(uniqueCats.map((c: string, i: number) => ({ id: i + 1, name: c })));
      setProductGroups(d.groups || []);
      setParsers(d.parsers || []);
      setSettings((d.settings || []).map((s: any) => ({ ...s, type: s.type || s.value_type })));
    } catch (err) {
      console.error('Config load failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleAddProductCategory = async () => {
    if (!newCatName.trim() || !newCatCode.trim()) return;
    try {
      await createProductCategory({ name: newCatName.trim(), code: newCatCode.trim().toUpperCase() });
      setNewCatName(''); setNewCatCode('');
      loadData();
    } catch (err) { console.error(err); }
  };

  const handleAddParserCategory = async () => {
    if (!newParserCat.trim()) return;
    try {
      await createParserCategory({ name: newParserCat.trim() });
      setNewParserCat('');
      loadData();
    } catch (err) { console.error(err); }
  };

  const handleAddGroup = async () => {
    if (!newGroupName.trim()) return;
    try {
      await createProductGroup({ name: newGroupName.trim() });
      setNewGroupName('');
      loadData();
    } catch (err) { console.error(err); }
  };

  const handleParserCategoryChange = async (parserId: number, newCategory: string) => {
    setParsers(ps => ps.map(p => p.id === parserId ? { ...p, category: newCategory || null } : p));
    try {
      await assignParserCategories([{ parser_id: parserId, category: newCategory || null }]);
    } catch { loadData(); }
  };

  const handleSaveSetting = async (key: string) => {
    setSaving(true);
    try {
      await updateSetting(key, editValue);
      setSettings(ss => ss.map(s => s.key === key ? { ...s, value: editValue } : s));
      setEditingKey(null);
    } catch (err) { console.error(err); } finally { setSaving(false); }
  };

  const handleRecalculate = async () => {
    setRecalculating(true);
    try { await triggerSalesRankings(); } finally { setRecalculating(false); }
  };

  // ─── Category edit/delete ──────────────────────────────────
  const startEditCategory = (cat: Category) => {
    setEditingCatId(cat.id);
    setEditCatName(cat.name);
    setEditCatCode(cat.code || '');
  };

  const handleSaveCategory = async (id: number) => {
    if (!editCatName.trim()) return;
    try {
      await updateProductCategory(id, { name: editCatName.trim(), code: editCatCode.trim().toUpperCase() });
      setEditingCatId(null);
      loadData();
    } catch (err) { console.error(err); }
  };

  const handleDeleteCategory = async (id: number) => {
    if (!confirm('Delete this category?')) return;
    try {
      await deleteProductCategory(id);
      loadData();
    } catch (err) { console.error(err); }
  };

  // ─── Group edit/delete ─────────────────────────────────────
  const startEditGroup = (g: Category) => {
    setEditingGroupId(g.id);
    setEditGroupName(g.name);
  };

  const handleSaveGroup = async (id: number) => {
    if (!editGroupName.trim()) return;
    try {
      await updateProductGroup(id, { name: editGroupName.trim() });
      setEditingGroupId(null);
      loadData();
    } catch (err) { console.error(err); }
  };

  const handleDeleteGroup = async (id: number) => {
    if (!confirm('Delete this group?')) return;
    try {
      await deleteProductGroup(id);
      loadData();
    } catch (err) { console.error(err); }
  };

  if (loading) {
    return (
      <div className="animate-fade-in">
        <div className="skeleton skeleton-heading" />
        <div className="grid grid-cols-3 gap-4">
          {[1,2,3].map(i => <div key={i} className="card skeleton" style={{ height: 200 }} />)}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <h1>Configuration</h1>
        <div className="flex items-center gap-3">
          <button className={`btn btn-ghost btn-sm ${recalculating ? 'animate-pulse' : ''}`} onClick={handleRecalculate} disabled={recalculating}>
            🏷️ Recalculate Rankings
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1" style={{ marginBottom: 'var(--spacing-6)' }}>
        {[
          { key: 'categories' as Tab, label: 'Categories & Groups' },
          { key: 'parsers' as Tab, label: 'Store Parsers' },
          { key: 'settings' as Tab, label: 'Application Settings' },
        ].map(t => (
          <button key={t.key} className={`btn btn-sm ${tab === t.key ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Categories & Groups */}
      {tab === 'categories' && (
        <div className="grid grid-cols-3 gap-6 animate-fade-in">
          {/* Product Categories */}
          <div className="card" style={{ padding: 'var(--spacing-5)' }}>
            <h3 style={{ marginBottom: 'var(--spacing-4)' }}>Product Categories</h3>
            <div className="flex gap-2" style={{ marginBottom: 'var(--spacing-4)' }}>
              <input className="input" placeholder="Name" value={newCatName} onChange={e => setNewCatName(e.target.value)} style={{ flex: 1 }} />
              <input className="input" placeholder="Code" value={newCatCode} onChange={e => setNewCatCode(e.target.value)} style={{ width: 80 }} />
              <button className="btn btn-primary btn-sm" onClick={handleAddProductCategory}>+</button>
            </div>
            <table className="data-table">
              <thead><tr><th>Name</th><th>Code</th><th style={{ width: 80 }}>Actions</th></tr></thead>
              <tbody>
                {productCategories.map(c => (
                  <tr key={c.id}>
                    {editingCatId === c.id ? (
                      <>
                        <td>
                          <input className="input" value={editCatName} onChange={e => setEditCatName(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') handleSaveCategory(c.id); if (e.key === 'Escape') setEditingCatId(null); }}
                            style={{ width: '100%' }} autoFocus />
                        </td>
                        <td>
                          <input className="input" value={editCatCode} onChange={e => setEditCatCode(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') handleSaveCategory(c.id); if (e.key === 'Escape') setEditingCatId(null); }}
                            style={{ width: 80 }} />
                        </td>
                        <td>
                          <div className="flex gap-1">
                            <button className="btn btn-primary btn-sm" onClick={() => handleSaveCategory(c.id)}>✓</button>
                            <button className="btn btn-ghost btn-sm" onClick={() => setEditingCatId(null)}>✕</button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="text-sm">{c.name}</td>
                        <td className="text-mono text-xs">{c.code}</td>
                        <td>
                          <div className="flex gap-1">
                            <button className="btn btn-ghost btn-sm" onClick={() => startEditCategory(c)} title="Edit">✏️</button>
                            <button className="btn btn-ghost btn-sm" onClick={() => handleDeleteCategory(c.id)} title="Delete">🗑</button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Parser Categories */}
          <div className="card" style={{ padding: 'var(--spacing-5)' }}>
            <h3 style={{ marginBottom: 'var(--spacing-4)' }}>Parser Categories</h3>
            <div className="flex gap-2" style={{ marginBottom: 'var(--spacing-4)' }}>
              <input className="input" placeholder="Name" value={newParserCat} onChange={e => setNewParserCat(e.target.value)} style={{ flex: 1 }} />
              <button className="btn btn-primary btn-sm" onClick={handleAddParserCategory}>+</button>
            </div>
            <table className="data-table">
              <thead><tr><th>Name</th></tr></thead>
              <tbody>
                {parserCategories.map(c => (
                  <tr key={c.id}><td className="text-sm">{c.name}</td></tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Product Groups */}
          <div className="card" style={{ padding: 'var(--spacing-5)' }}>
            <h3 style={{ marginBottom: 'var(--spacing-4)' }}>Product Groups</h3>
            <div className="flex gap-2" style={{ marginBottom: 'var(--spacing-4)' }}>
              <input className="input" placeholder="Name" value={newGroupName} onChange={e => setNewGroupName(e.target.value)} style={{ flex: 1 }} />
              <button className="btn btn-primary btn-sm" onClick={handleAddGroup}>+</button>
            </div>
            <table className="data-table">
              <thead><tr><th>Name</th><th style={{ width: 80 }}>Actions</th></tr></thead>
              <tbody>
                {productGroups.map(g => (
                  <tr key={g.id}>
                    {editingGroupId === g.id ? (
                      <>
                        <td>
                          <input className="input" value={editGroupName} onChange={e => setEditGroupName(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') handleSaveGroup(g.id); if (e.key === 'Escape') setEditingGroupId(null); }}
                            style={{ width: '100%' }} autoFocus />
                        </td>
                        <td>
                          <div className="flex gap-1">
                            <button className="btn btn-primary btn-sm" onClick={() => handleSaveGroup(g.id)}>✓</button>
                            <button className="btn btn-ghost btn-sm" onClick={() => setEditingGroupId(null)}>✕</button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="text-sm">{g.name}</td>
                        <td>
                          <div className="flex gap-1">
                            <button className="btn btn-ghost btn-sm" onClick={() => startEditGroup(g)} title="Edit">✏️</button>
                            <button className="btn btn-ghost btn-sm" onClick={() => handleDeleteGroup(g.id)} title="Delete">🗑</button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Parser Assignments */}
      {tab === 'parsers' && (
        <div className="card animate-fade-in" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Parser Name</th>
                  <th>Current Category</th>
                  <th>Assign Category</th>
                </tr>
              </thead>
              <tbody>
                {parsers.map(p => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 500 }}>{p.name}</td>
                    <td className="text-sm text-muted">{p.category || '—'}</td>
                    <td>
                      <select
                        className="select"
                        value={p.category || ''}
                        onChange={e => handleParserCategoryChange(p.id, e.target.value)}
                        style={{ maxWidth: 200 }}
                      >
                        <option value="">None</option>
                        {parserCategories.map(c => (
                          <option key={c.id} value={c.name}>{c.name}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Application Settings */}
      {tab === 'settings' && (
        <div className="card animate-fade-in" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Setting</th>
                  <th>Value</th>
                  <th>Type</th>
                  <th>Description</th>
                  <th style={{ width: 60 }}>Edit</th>
                </tr>
              </thead>
              <tbody>
                {settings.map(s => (
                  <tr key={s.key}>
                    <td className="text-mono text-sm" style={{ fontWeight: 500 }}>{s.key}</td>
                    <td>
                      {editingKey === s.key ? (
                        <div className="flex gap-2 items-center">
                          <input
                            className="input"
                            value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') handleSaveSetting(s.key); if (e.key === 'Escape') setEditingKey(null); }}
                            style={{ width: 150 }}
                            autoFocus
                          />
                          <button className="btn btn-primary btn-sm" onClick={() => handleSaveSetting(s.key)} disabled={saving}>✓</button>
                          <button className="btn btn-ghost btn-sm" onClick={() => setEditingKey(null)}>✕</button>
                        </div>
                      ) : (
                        <span className="text-mono">{s.value}</span>
                      )}
                    </td>
                    <td><span className="badge badge-neutral">{s.type}</span></td>
                    <td className="text-xs text-muted">{s.description}</td>
                    <td>
                      {editingKey !== s.key && (
                        <button className="btn btn-ghost btn-sm" onClick={() => { setEditingKey(s.key); setEditValue(s.value); }}>✏️</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
