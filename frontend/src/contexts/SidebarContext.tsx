/**
 * SidebarContext — Sidebar data with stale-while-revalidate pattern.
 * Loads from localStorage immediately, then refreshes from API in background.
 * Supports optimistic count updates on pipeline status changes.
 */
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { fetchSidebar } from '../api';

interface ParserItem {
  id: number;
  name: string;
  category: string | null;
  product_count: number;
}

interface PipelineStatusCount {
  status: string;
  slug: string;
  count: number;
}

interface SidebarData {
  parsers: ParserItem[];
  pipeline_statuses: PipelineStatusCount[];
}

interface SidebarContextType {
  data: SidebarData | null;
  loading: boolean;
  refresh: () => Promise<void>;
  updateFlowCount: (fromSlug: string | null, toSlug: string) => void;
}

const STORAGE_KEY = 'ecommerce_sidebar_data';

const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<SidebarData | null>(() => {
    // Load from localStorage for instant render
    try {
      const cached = localStorage.getItem(STORAGE_KEY);
      return cached ? JSON.parse(cached) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchSidebar();
      const newData = res.data;
      setData(newData);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newData));
    } catch {
      // Keep cached data on error
    } finally {
      setLoading(false);
    }
  }, []);

  // Background refresh on mount
  useEffect(() => {
    refresh();
  }, [refresh]);

  /**
   * Optimistic count update when a product moves between pipeline statuses.
   */
  const updateFlowCount = useCallback((fromSlug: string | null, toSlug: string) => {
    setData((prev) => {
      if (!prev) return prev;
      const statuses = prev.pipeline_statuses.map((s) => {
        if (fromSlug && s.slug === fromSlug) {
          return { ...s, count: Math.max(0, s.count - 1) };
        }
        if (s.slug === toSlug) {
          return { ...s, count: s.count + 1 };
        }
        return s;
      });
      const updated = { ...prev, pipeline_statuses: statuses };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });
  }, []);

  return (
    <SidebarContext.Provider value={{ data, loading, refresh, updateFlowCount }}>
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar() {
  const context = useContext(SidebarContext);
  if (!context) throw new Error('useSidebar must be used inside SidebarProvider');
  return context;
}

export default SidebarContext;
