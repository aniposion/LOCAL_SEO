'use client';

import { useEffect, useEffectEvent, useMemo, useState } from 'react';
import { AlertCircle, Calendar, Eye, Navigation, Phone, Star, TrendingDown, TrendingUp } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { toast } from 'sonner';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { analyticsApi, locationsApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

interface AnalyticsLocation {
  id: string;
  name?: string;
}

interface MetricDelta {
  current: number;
  previous: number;
  delta: number;
  percent_change: number;
}

interface DashboardMetrics {
  calls: MetricDelta;
  directions: MetricDelta;
  website_clicks: MetricDelta;
  profile_views: MetricDelta;
  new_reviews: MetricDelta;
  avg_rating?: number | null;
  estimated_revenue: number;
}

interface DashboardHighlight {
  type: 'increase' | 'decrease' | 'milestone' | string;
  metric: string;
  message: string;
  value: number;
  percent: number;
}

interface ChartDataPoint {
  date: string;
  calls: number;
  directions: number;
  website_clicks: number;
}

interface TopPost {
  id: string;
  title: string;
  platform: string;
  estimated_impact: string;
  published_at?: string | null;
}

interface DashboardData {
  location_id: string;
  period_start: string;
  period_end: string;
  metrics: DashboardMetrics;
  highlights: DashboardHighlight[];
  top_posts: TopPost[];
  chart_data: ChartDataPoint[];
}

function formatPercent(change: number) {
  return `${change >= 0 ? '+' : ''}${change.toFixed(1)}%`;
}

function formatMetricName(metric: string) {
  return metric
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function getHighlightIcon(type: DashboardHighlight['type']): LucideIcon {
  if (type === 'decrease') return TrendingDown;
  if (type === 'milestone') return Star;
  return TrendingUp;
}

function getHighlightTone(type: DashboardHighlight['type']) {
  if (type === 'decrease') {
    return {
      icon: 'text-rose-600',
      card: 'bg-rose-50',
      badge: 'text-rose-700',
    };
  }
  if (type === 'milestone') {
    return {
      icon: 'text-amber-600',
      card: 'bg-amber-50',
      badge: 'text-amber-700',
    };
  }
  return {
    icon: 'text-green-600',
    card: 'bg-green-50',
    badge: 'text-green-700',
  };
}

function MetricCard({
  title,
  value,
  change,
  icon: Icon,
  iconColor,
  bgColor,
}: {
  title: string;
  value: number | string;
  change?: number;
  icon: LucideIcon;
  iconColor: string;
  bgColor: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-gray-500">{title}</p>
            <p className="mt-1 text-3xl font-bold">{value}</p>
            {change !== undefined && (
              <div className={`mt-1 flex items-center gap-1 text-sm ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {change >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                <span>{formatPercent(change)}</span>
              </div>
            )}
          </div>
          <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${bgColor}`}>
            <Icon className={`h-6 w-6 ${iconColor}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SimpleBarChart({
  points,
  metric,
  label,
}: {
  points: ChartDataPoint[];
  metric: 'calls' | 'directions';
  label: string;
}) {
  if (points.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-sm text-gray-500">
        No persisted daily snapshot data is available for this period yet.
      </div>
    );
  }

  const max = Math.max(...points.map((point) => point[metric]), 1);

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <div className="flex h-32 items-end gap-2">
        {points.map((point) => {
          const value = point[metric];
          const shortDay = new Date(point.date).toLocaleDateString(undefined, { weekday: 'short' });
          return (
            <div key={`${metric}-${point.date}`} className="flex flex-1 flex-col items-center gap-1">
              <div
                className="w-full rounded-t bg-violet-500 transition-all"
                style={{ height: `${(value / max) * 100}%`, minHeight: value > 0 ? '4px' : '0' }}
              />
              <span className="text-xs text-gray-400">{shortDay}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [period, setPeriod] = useState('7');
  const [data, setData] = useState<DashboardData | null>(null);
  const [locations, setLocations] = useState<AnalyticsLocation[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const activeLocationId = selectedLocation || locations[0]?.id || null;

  useEffect(() => {
    const fetchLocations = async () => {
      try {
        const response = await locationsApi.list();
        const payload = response.data;
        const locs = Array.isArray(payload)
          ? (payload as AnalyticsLocation[])
          : ((payload.locations || []) as AnalyticsLocation[]);
        setLocations(locs);

        if (locs.length > 0) {
          setSelectedLocation((current) =>
            current && locs.some((location) => location.id === current)
              ? current
              : locs[0].id
          );
          setStatusMessage(null);
        } else {
          setSelectedLocation(null);
          setStatusMessage('Add a location first to view analytics.');
        }
      } catch (error) {
        setLocations([]);
        setSelectedLocation(null);
        setStatusMessage('Analytics is unavailable until locations can be loaded.');
        toast.error(getApiErrorMessage(error, 'Failed to fetch locations'));
      } finally {
        setIsLoading(false);
      }
    };

    void fetchLocations();
  }, []);

  const fetchAnalytics = useEffectEvent(async () => {
    if (!activeLocationId) return;

    setIsLoading(true);
    try {
      const response = await analyticsApi.getMetrics(activeLocationId, Number.parseInt(period, 10));
      const payload = response.data as DashboardData;
      setData(payload);
      setStatusMessage(
        payload.chart_data?.length
          ? 'This page uses persisted metric snapshots and live dashboard highlights only.'
          : 'Analytics is connected, but there are no persisted daily snapshots in this period yet.'
      );
    } catch (error) {
      setData(null);
      setStatusMessage('Analytics could not be loaded for this location.');
      toast.error(getApiErrorMessage(error, 'Failed to fetch analytics'));
    } finally {
      setIsLoading(false);
    }
  });

  useEffect(() => {
    if (activeLocationId) {
      void fetchAnalytics();
    }
  }, [activeLocationId, period]);

  const topPosts = useMemo(() => data?.top_posts || [], [data?.top_posts]);
  const highlights = useMemo(() => data?.highlights || [], [data?.highlights]);

  if (isLoading && !data) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-10 w-48" />
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="mb-2 h-4 w-20" />
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-gray-500">Track your Google Maps performance from persisted metrics snapshots.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {locations.length > 1 ? (
            <select
              className="h-10 rounded-md border border-input bg-background px-3 text-sm"
              value={activeLocationId || ''}
              onChange={(event) => setSelectedLocation(event.target.value)}
            >
              {locations.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.name || location.id}
                </option>
              ))}
            </select>
          ) : null}
          <Tabs value={period} onValueChange={setPeriod}>
            <TabsList>
              <TabsTrigger value="7">7 Days</TabsTrigger>
              <TabsTrigger value="30">30 Days</TabsTrigger>
              <TabsTrigger value="90">90 Days</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="pt-6">
          <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Analytics Next Best Action</Badge>
          <h2 className="text-xl font-semibold">Look for one metric that changed, then decide why</h2>
          <p className="mt-1 text-sm text-slate-300">
            Analytics should guide the next operating decision. Start with calls, directions, profile views, or rating changes before reading every chart.
          </p>
        </CardContent>
      </Card>

      {statusMessage && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-start gap-3 pt-6">
            <AlertCircle className="mt-0.5 h-5 w-5 text-amber-600" />
            <div className="text-sm text-amber-900">{statusMessage}</div>
          </CardContent>
        </Card>
      )}

      {data && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              title="Total Calls"
              value={data.metrics.calls.current}
              change={data.metrics.calls.percent_change}
              icon={Phone}
              iconColor="text-green-600"
              bgColor="bg-green-100"
            />
            <MetricCard
              title="Direction Requests"
              value={data.metrics.directions.current}
              change={data.metrics.directions.percent_change}
              icon={Navigation}
              iconColor="text-blue-600"
              bgColor="bg-blue-100"
            />
            <MetricCard
              title="Profile Views"
              value={data.metrics.profile_views.current}
              change={data.metrics.profile_views.percent_change}
              icon={Eye}
              iconColor="text-purple-600"
              bgColor="bg-purple-100"
            />
            <MetricCard
              title="Average Rating"
              value={data.metrics.avg_rating?.toFixed(1) || 'N/A'}
              icon={Star}
              iconColor="text-yellow-600"
              bgColor="bg-yellow-100"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Calls Over Time</CardTitle>
                <CardDescription>Daily call volume from persisted dashboard snapshots.</CardDescription>
              </CardHeader>
              <CardContent>
                <SimpleBarChart points={data.chart_data || []} metric="calls" label="Calls per day" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Direction Requests</CardTitle>
                <CardDescription>Daily direction requests from persisted dashboard snapshots.</CardDescription>
              </CardHeader>
              <CardContent>
                <SimpleBarChart points={data.chart_data || []} metric="directions" label="Directions per day" />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Live Highlights</CardTitle>
                <CardDescription>Dashboard highlights generated from current vs previous period metrics.</CardDescription>
              </CardHeader>
              <CardContent>
                {highlights.length > 0 ? (
                  <div className="space-y-4">
                    {highlights.map((highlight, index) => {
                      const Icon = getHighlightIcon(highlight.type);
                      const tone = getHighlightTone(highlight.type);
                      return (
                        <div key={`${highlight.metric}-${index}`} className={`flex gap-4 rounded-lg p-4 ${tone.card}`}>
                          <Icon className={`h-6 w-6 flex-shrink-0 ${tone.icon}`} />
                          <div>
                            <p className="font-medium">{highlight.message}</p>
                            <p className={`text-sm ${tone.badge}`}>
                              {formatMetricName(highlight.metric)} - {highlight.value} - {formatPercent(highlight.percent)}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed p-6 text-sm text-gray-500">
                    No dashboard highlights are available for this period yet. More daily snapshots are needed before
                    trend summaries can be generated honestly.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Top Contributing Posts</CardTitle>
                <CardDescription>Posts linked to the highest estimated impact in the current dashboard window.</CardDescription>
              </CardHeader>
              <CardContent>
                {topPosts.length > 0 ? (
                  <div className="space-y-3">
                    {topPosts.map((post) => (
                      <div key={post.id} className="rounded-lg border p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium">{post.title}</p>
                            <p className="mt-1 text-sm text-gray-500">
                              {post.platform} - {post.published_at ? new Date(post.published_at).toLocaleDateString() : 'Publish date unavailable'}
                            </p>
                          </div>
                          <div className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">
                            <Calendar className="h-3.5 w-3.5" />
                            {post.estimated_impact}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed p-6 text-sm text-gray-500">
                    No top post attribution is available for this period yet.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
