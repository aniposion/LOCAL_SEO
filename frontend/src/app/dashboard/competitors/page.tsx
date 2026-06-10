'use client';

import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Clock3,
  Database,
  Eye,
  MapPin,
  RefreshCw,
  ShieldAlert,
  Star,
  Target,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { competitorApi } from '@/lib/api/ai-features';
import { locationsApi } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

type DashboardLocation = {
  id: string;
  name: string;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  services?: string[] | null;
  category?: string | null;
};

export default function CompetitorsPage() {
  const [locations, setLocations] = useState<DashboardLocation[]>([]);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [businessType, setBusinessType] = useState('');
  const [locationsLoading, setLocationsLoading] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    const loadLocations = async () => {
      try {
        const response = await locationsApi.list();
        const payload = response.data;
        const items = Array.isArray(payload)
          ? (payload as DashboardLocation[])
          : Array.isArray((payload as { locations?: DashboardLocation[] } | undefined)?.locations)
            ? ((payload as { locations?: DashboardLocation[] }).locations ?? [])
            : [];

        setLocations(items);
        setLocationId((current) =>
          current && items.some((location) => location.id === current)
            ? current
            : (items[0]?.id ?? null)
        );
      } catch (error) {
        console.error('Failed to load locations for competitor dashboard:', error);
        setLocations([]);
        setLocationId(null);
      } finally {
        setLocationsLoading(false);
      }
    };

    void loadLocations();
  }, []);

  const activeLocationId = locationId || locations[0]?.id || null;
  const selectedLocation = locations.find((location) => location.id === activeLocationId) ?? null;

  useEffect(() => {
    const nextBusinessType =
      selectedLocation?.category?.trim() ||
      selectedLocation?.services?.find((service) => service.trim().length > 0)?.trim() ||
      '';

    setBusinessType(nextBusinessType);
  }, [selectedLocation]);

  const {
    data: report,
    isLoading: reportLoading,
    error: reportError,
  } = useQuery({
    queryKey: ['competitor-report', activeLocationId],
    queryFn: () => competitorApi.getReport(activeLocationId || ''),
    enabled: !!activeLocationId,
    refetchInterval: 300000,
  });

  const {
    data: trackedCompetitors = [],
    isLoading: competitorsLoading,
    error: competitorsError,
  } = useQuery({
    queryKey: ['competitor-list', activeLocationId],
    queryFn: () => competitorApi.list(activeLocationId || ''),
    enabled: !!activeLocationId,
    refetchInterval: 300000,
  });

  const discoverMutation = useMutation({
    mutationFn: () => {
      if (!activeLocationId) {
        throw new Error('Select a location before discovering competitors.');
      }

      return competitorApi.discover({
        location_id: activeLocationId,
        radius_miles: 3.0,
        business_type: businessType.trim(),
        max_results: 3,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['competitor-report', activeLocationId] });
      queryClient.invalidateQueries({ queryKey: ['competitor-list', activeLocationId] });
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: () => {
      if (!activeLocationId) {
        throw new Error('Select a location before running competitor analysis.');
      }

      return competitorApi.analyze({
        location_id: activeLocationId,
        force_refresh: true,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['competitor-report', activeLocationId] });
      queryClient.invalidateQueries({ queryKey: ['competitor-list', activeLocationId] });
    },
  });

  const competitors = report?.competitors?.length ? report.competitors : trackedCompetitors;
  const discoverBlockedMessage = !activeLocationId
    ? 'Select a location before discovering nearby competitors.'
    : businessType.trim().length === 0
      ? 'Enter a business type before running nearby discovery for this location.'
      : null;

  const getThreatColor = (level: string) => {
    switch (level) {
      case 'high':
        return 'text-red-500';
      case 'medium':
        return 'text-yellow-500';
      case 'low':
        return 'text-green-500';
      default:
        return 'text-gray-500';
    }
  };

  const getThreatBadgeVariant = (level: string): 'destructive' | 'default' | 'secondary' => {
    switch (level) {
      case 'high':
        return 'destructive';
      case 'medium':
        return 'default';
      default:
        return 'secondary';
    }
  };

  const getRatingTrendIcon = (trend: string) => {
    switch (trend) {
      case 'improving':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'declining':
        return <TrendingDown className="h-4 w-4 text-red-500" />;
      default:
        return <div className="h-4 w-4" />;
    }
  };

  const formatAge = (minutes?: number | null) => {
    if (minutes === null || minutes === undefined) {
      return 'Unknown';
    }
    if (minutes < 60) {
      return `${Math.max(1, minutes)} min ago`;
    }
    const hours = Math.round(minutes / 60);
    if (hours < 24) {
      return `${hours}h ago`;
    }
    const days = Math.round(hours / 24);
    return `${days}d ago`;
  };

  const formatDateTime = (value?: string | null) => {
    if (!value) {
      return 'Unknown';
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 'Unknown' : parsed.toLocaleString();
  };

  const formatLocationLabel = (location: DashboardLocation) => {
    const parts = [location.city, location.state].filter(Boolean);
    return parts.length > 0 ? `${location.name} (${parts.join(', ')})` : location.name;
  };

  const getFreshnessBadgeVariant = (status?: string): 'default' | 'secondary' | 'destructive' => {
    switch (status) {
      case 'stale':
        return 'destructive';
      case 'attention':
        return 'secondary';
      default:
        return 'default';
    }
  };

  if (locationsLoading || (activeLocationId && reportLoading && competitorsLoading)) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!activeLocationId) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle>No location available</CardTitle>
            <CardDescription>
              Create or connect a business location before viewing competitor analysis.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto space-y-8 py-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Competitor Analysis</h1>
          <p className="mt-2 text-muted-foreground">
            Saved competitor snapshots based on synced reviews and the latest analysis run.
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            This page is not live monitoring. Refresh it after you discover competitors or sync reviews.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {discoverBlockedMessage ? (
            <div className="flex items-center rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
              {discoverBlockedMessage}
            </div>
          ) : (
            <Button variant="outline" onClick={() => discoverMutation.mutate()} disabled={discoverMutation.isPending}>
              {discoverMutation.isPending ? (
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Eye className="mr-2 h-4 w-4" />
              )}
              Discover Nearby
            </Button>
          )}
          <Button onClick={() => analyzeMutation.mutate()} disabled={analyzeMutation.isPending || !activeLocationId}>
            {analyzeMutation.isPending ? (
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Target className="mr-2 h-4 w-4" />
            )}
            Run Analysis
          </Button>
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Competitor Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {competitors.length === 0 ? 'Discover nearby competitors first' : 'Turn one competitor gap into an action item'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              This page is useful only when it creates a practical next move: content, reviews, SEO, or positioning.
            </p>
          </div>
          <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={() => analyzeMutation.mutate()} disabled={analyzeMutation.isPending || !activeLocationId}>
            {analyzeMutation.isPending ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Target className="mr-2 h-4 w-4" />}
            Run analysis
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Scope</CardTitle>
          <CardDescription>
            Choose the location and business type you want to use before discovering nearby competitors.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-[minmax(0,280px)_minmax(0,1fr)]">
          <div className="space-y-2">
            <Label htmlFor="competitor-location">Location</Label>
            <Select value={activeLocationId ?? undefined} onValueChange={setLocationId}>
              <SelectTrigger id="competitor-location">
                <SelectValue placeholder="Select location" />
              </SelectTrigger>
              <SelectContent>
                {locations.map((location) => (
                  <SelectItem key={location.id} value={location.id}>
                    {formatLocationLabel(location)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="competitor-business-type">Business type for discovery</Label>
            <Input
              id="competitor-business-type"
              value={businessType}
              onChange={(event) => setBusinessType(event.target.value)}
              placeholder="Cafe, salon, dental clinic"
            />
            <p className="text-xs text-muted-foreground">
              We auto-fill this from the selected location when a category or service is available. Adjust it before discovery if needed.
            </p>
          </div>
        </CardContent>
      </Card>

      {discoverBlockedMessage ? (
        <Card className="border-border/60 bg-muted/30">
          <CardContent className="p-4 text-sm text-muted-foreground">{discoverBlockedMessage}</CardContent>
        </Card>
      ) : null}

      {reportError ? (
        <Card className="border-amber-200 bg-amber-50/80">
          <CardContent className="flex items-start gap-3 p-4">
            <ShieldAlert className="mt-1 h-5 w-5 text-amber-700" />
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold text-amber-900">Saved analysis is not ready yet</p>
                <Badge variant="secondary">Needs analysis</Badge>
              </div>
              <p className="text-sm text-amber-900">
                Discover nearby competitors and run analysis for <span className="font-medium">{selectedLocation?.name}</span> to create a fresh report.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {competitorsError ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="flex items-start justify-between gap-4 p-4">
            <div className="space-y-1">
              <p className="font-semibold text-destructive">Tracked competitors could not be loaded</p>
              <p className="text-sm text-muted-foreground">
                Try refreshing the competitor list for <span className="font-medium">{selectedLocation?.name}</span>.
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => queryClient.invalidateQueries({ queryKey: ['competitor-list', activeLocationId] })}
            >
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {report?.freshness && report.freshness.freshness_status !== 'fresh' ? (
        <Card className="border-amber-200 bg-amber-50/80">
          <CardContent className="flex items-start gap-3 p-4">
            <ShieldAlert className="mt-1 h-5 w-5 text-amber-700" />
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold text-amber-900">Attention needed</p>
                <Badge variant={getFreshnessBadgeVariant(report.freshness.freshness_status)}>
                  {report.freshness.freshness_status}
                </Badge>
              </div>
              <p className="text-sm text-amber-900">
                {report.freshness.freshness_notes?.[0] || 'The latest competitor snapshot may be outdated or based on a small sample.'}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Analysis Freshness</CardTitle>
            <Clock3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Badge variant={getFreshnessBadgeVariant(report?.freshness?.freshness_status)}>
                {report?.freshness?.freshness_status || 'unknown'}
              </Badge>
            </div>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Analysis age</span>
                <span className="font-medium">{formatAge(report?.freshness?.analysis_age_minutes)}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Last review sync</span>
                <span className="font-medium">{formatDateTime(report?.freshness?.last_review_sync_at)}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Recent review sample</span>
                <span className="font-medium">{report?.freshness?.review_sample_size ?? 0}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Threat Level</CardTitle>
            <AlertTriangle className={getThreatColor(report?.overall_threat_level || 'low')} />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">{report?.overall_threat_level || 'Not available'}</div>
            <Badge variant={getThreatBadgeVariant(report?.overall_threat_level || 'low')} className="mt-2">
              {competitors.length} Competitors Tracked
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Rating Trend</CardTitle>
            {getRatingTrendIcon(report?.analysis?.rating_trend || 'stable')}
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">{report?.analysis?.rating_trend || 'Not available'}</div>
            <p className="mt-2 text-xs text-muted-foreground">
              {report ? 'Based on the latest saved analysis' : 'Run analysis after discovery to generate a trend snapshot.'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cache Age</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatAge(report?.freshness?.cache_age_minutes)}</div>
            <p className="mt-2 text-xs text-muted-foreground">Age of the saved analysis snapshot</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="competitors">Competitors</TabsTrigger>
          <TabsTrigger value="insights">AI Insights</TabsTrigger>
          <TabsTrigger value="actions">Action Items</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Analysis Summary</CardTitle>
              <CardDescription>
                Based on the latest saved analysis and synced reviews for this location
              </CardDescription>
            </CardHeader>
            <CardContent>
              {report?.analysis?.summary_text ? (
                <p className="text-lg leading-relaxed">{report.analysis.summary_text}</p>
              ) : (
                <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                  No saved summary is available yet for this location. Discover nearby competitors and run analysis to generate one.
                </div>
              )}
              {report?.freshness?.freshness_notes?.length ? (
                <div className="mt-4 rounded-lg border bg-muted/30 p-3 text-sm text-muted-foreground">
                  <p className="font-medium text-foreground">Freshness notes</p>
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {report.freshness.freshness_notes.map((note, index) => (
                      <li key={index}>{note}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Trending Keywords</CardTitle>
              <CardDescription>What customers are talking about in your area</CardDescription>
            </CardHeader>
            <CardContent>
              {report?.key_insights?.length ? (
                <div className="flex flex-wrap gap-2">
                  {report.key_insights.map((keyword, index) => (
                    <Badge key={index} variant="outline" className="px-3 py-1 text-sm">
                      {keyword}
                    </Badge>
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                  No keyword insights yet. Competitor keywords will appear here after analysis is generated for this location.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="competitors" className="space-y-4">
          {competitors.length ? (
            competitors.map((competitor) => (
              <Card key={competitor.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="space-y-1">
                      <CardTitle>{competitor.name}</CardTitle>
                      <CardDescription className="flex items-center gap-2">
                        <MapPin className="h-3 w-3" />
                        {competitor.distance_miles.toFixed(1)} miles away | {competitor.address}
                      </CardDescription>
                      <p className="text-xs text-muted-foreground">
                        Last review sync: {formatDateTime(competitor.last_review_synced_at)}
                      </p>
                    </div>
                    <Badge variant={competitor.status === 'active' ? 'default' : 'secondary'}>
                      {competitor.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Rating</span>
                        <div className="flex items-center gap-1">
                          <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                          <span className="font-semibold">{competitor.rating.toFixed(1)}</span>
                        </div>
                      </div>
                      <Progress value={(competitor.rating / 5) * 100} className="h-2" />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Reviews</span>
                        <span className="font-semibold">{competitor.review_count}</span>
                      </div>
                      <Progress value={Math.min((competitor.review_count / 1000) * 100, 100)} className="h-2" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>No tracked competitors yet</CardTitle>
                <CardDescription>
                  Discover nearby businesses for {selectedLocation?.name} once you have a business type ready.
                </CardDescription>
              </CardHeader>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="insights" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Competitive Intelligence</CardTitle>
              <CardDescription>AI-generated insights from competitor reviews</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h3 className="mb-3 font-semibold">Trending Topics</h3>
                {report?.analysis?.trending_keywords?.length ? (
                  <div className="grid gap-2">
                    {report.analysis.trending_keywords.map((keyword, index) => (
                      <div key={index} className="flex items-center justify-between rounded-lg bg-muted p-3">
                        <span>{keyword}</span>
                        <Badge variant="outline">Trending</Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                    AI insight topics will appear here after a saved competitor analysis is generated.
                  </div>
                )}
              </div>

              <Separator />

              <div>
                <h3 className="mb-3 font-semibold">Market Position</h3>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Threat Level</span>
                    <Badge variant={getThreatBadgeVariant(report?.overall_threat_level || 'low')}>
                      {report?.overall_threat_level || 'unknown'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Rating Trend</span>
                    <div className="flex items-center gap-2">
                      {getRatingTrendIcon(report?.analysis?.rating_trend || 'stable')}
                      <span className="text-sm capitalize">{report?.analysis?.rating_trend || 'stable'}</span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="actions" className="space-y-4">
          {report?.analysis?.recommended_actions?.length ? (
            report.analysis.recommended_actions.map((action, index) => (
              <Card key={index}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="space-y-1">
                      <CardTitle className="text-lg">{action.title}</CardTitle>
                      <CardDescription>{action.description}</CardDescription>
                    </div>
                    <div className="flex gap-2">
                      <Badge variant={action.priority === 'high' ? 'destructive' : 'default'}>
                        {action.priority} priority
                      </Badge>
                      <Badge variant="outline">{action.effort} effort</Badge>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            ))
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>No action items yet</CardTitle>
                <CardDescription>
                  Recommended actions will show up here after a saved competitor analysis is available for this location.
                </CardDescription>
              </CardHeader>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
