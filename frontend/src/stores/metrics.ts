/**
 * P1: Metrics & Dashboard Store
 */
import { create } from 'zustand';

import { metricsApi, utmApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

export interface MetricSnapshot {
  id: string;
  location_id: string;
  snapshot_date: string;
  snapshot_type: string;
  calls: number;
  directions: number;
  website_clicks: number;
  profile_views: number;
  photo_views: number;
  total_reviews: number;
  new_reviews: number;
  avg_rating: number | null;
  calls_delta?: number | null;
  directions_delta?: number | null;
  website_clicks_delta?: number | null;
  attributed_post_ids: string[];
  call_value: number;
  estimated_revenue: number;
  created_at: string;
}

export interface MetricDelta {
  current: number;
  previous: number;
  delta: number;
  percent_change: number;
}

export interface DashboardMetrics {
  calls: MetricDelta;
  directions: MetricDelta;
  website_clicks: MetricDelta;
  profile_views: MetricDelta;
  new_reviews: MetricDelta;
  avg_rating: number | null;
  estimated_revenue: number;
}

export interface Highlight {
  type: 'increase' | 'decrease' | 'milestone';
  metric: string;
  message: string;
  value: number;
  percent: number;
}

export interface TopPost {
  id: string;
  title: string;
  published_at: string | null;
  platform: string;
  estimated_impact: string;
}

export interface ChartDataPoint {
  date: string;
  calls: number;
  directions: number;
  website_clicks: number;
}

export interface DashboardData {
  location_id: string;
  period_start: string;
  period_end: string;
  metrics: DashboardMetrics;
  highlights: Highlight[];
  top_posts: TopPost[];
  chart_data: ChartDataPoint[];
}

export interface UTMLink {
  id: string;
  original_url: string;
  utm_url: string;
  utm_source: string;
  utm_medium: string;
  utm_campaign?: string | null;
  utm_content?: string | null;
  clicks: number;
  created_at: string;
}

export interface CreateUTMLinkInput {
  original_url: string;
  campaign: string;
  post_id?: string;
  utm_source?: string;
  utm_medium?: string;
}

interface MetricsState {
  dashboard: DashboardData | null;
  snapshots: MetricSnapshot[];
  utmLinks: UTMLink[];
  isLoading: boolean;
  isLoadingSnapshots: boolean;
  isLoadingUTM: boolean;
  error: string | null;
  fetchDashboard: (locationId: string, days?: number) => Promise<void>;
  fetchSnapshots: (locationId: string, days?: number) => Promise<void>;
  fetchUTMLinks: (locationId: string) => Promise<void>;
  createUTMLink: (locationId: string, data: CreateUTMLinkInput) => Promise<UTMLink>;
  deleteUTMLink: (linkId: string) => Promise<void>;
  collectMetrics: (locationId: string) => Promise<void>;
  clearError: () => void;
}

export const useMetricsStore = create<MetricsState>((set, get) => ({
  dashboard: null,
  snapshots: [],
  utmLinks: [],
  isLoading: false,
  isLoadingSnapshots: false,
  isLoadingUTM: false,
  error: null,

  fetchDashboard: async (locationId: string, days = 30) => {
    set({ isLoading: true, error: null });
    try {
      const response = await metricsApi.getDashboard(locationId, days);
      set({ dashboard: response.data, isLoading: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch the dashboard'),
        isLoading: false,
      });
    }
  },

  fetchSnapshots: async (locationId: string, days = 30) => {
    set({ isLoadingSnapshots: true, error: null });
    try {
      const response = await metricsApi.getSnapshots(locationId, {
        limit: days,
        snapshot_type: 'daily',
      });
      set({ snapshots: response.data.items, isLoadingSnapshots: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch snapshots'),
        isLoadingSnapshots: false,
      });
    }
  },

  fetchUTMLinks: async (locationId: string) => {
    set({ isLoadingUTM: true, error: null });
    try {
      const response = await utmApi.list(locationId);
      set({ utmLinks: response.data.links ?? [], isLoadingUTM: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch UTM links'),
        isLoadingUTM: false,
      });
    }
  },

  createUTMLink: async (locationId: string, data: CreateUTMLinkInput) => {
    const response = await utmApi.create(locationId, {
      original_url: data.original_url,
      campaign: data.campaign,
      post_id: data.post_id,
      utm_source: data.utm_source,
      utm_medium: data.utm_medium,
    });
    const newLink = response.data as UTMLink;
    set((state) => ({ utmLinks: [newLink, ...state.utmLinks] }));
    return newLink;
  },

  deleteUTMLink: async (linkId: string) => {
    await utmApi.delete(linkId);
    set((state) => ({
      utmLinks: state.utmLinks.filter((link) => link.id !== linkId),
    }));
  },

  collectMetrics: async (locationId: string) => {
    await metricsApi.collect({
      location_id: locationId,
      snapshot_date: new Date().toISOString().slice(0, 10),
      snapshot_type: 'daily',
    });
    await Promise.all([
      get().fetchDashboard(locationId),
      get().fetchSnapshots(locationId),
    ]);
  },

  clearError: () => set({ error: null }),
}));
