'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  Bell,
  CheckCircle,
  Clock,
  DollarSign,
  Eye,
  FileText,
  Globe,
  Navigation,
  Phone,
  Star,
  TrendingUp,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Highlights, MetricsChart, ProofCard, WeeklyReportCard } from '@/components/dashboard';
import {
  extractCollectionPayload,
  locationsApi,
  metricsApi,
  notificationsApi,
  postsApi,
  reportsApi,
  revenueApi,
  reviewResponderApi,
  socialProofHistoryApi,
} from '@/lib/api';

interface DashboardLocation {
  id: string;
  name: string;
  gbp_connected?: boolean;
  gbp_status?: string | null;
  instagram_connected?: boolean;
  instagram_status?: string | null;
  website_connected?: boolean;
  website_status?: string | null;
}

interface DashboardChannelSummary {
  id: string;
  type: string;
  status: string;
  reconnect_required?: boolean;
  needs_refresh?: boolean;
  last_publish_succeeded_at?: string | null;
  last_publish_failed_at?: string | null;
  last_publish_failed_error?: string | null;
  qa_pending_count?: number;
  qa_failed_count?: number;
  qa_last_sync_at?: string | null;
}

interface ReviewResponderSummary {
  total_count: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  published_count: number;
  failed_count: number;
  high_priority_pending_count: number;
  high_priority_total_count: number;
  average_rating?: number | null;
  last_activity_at?: string | null;
  last_failed_at?: string | null;
  last_published_at?: string | null;
  last_bulk_retry_at?: string | null;
  last_bulk_retry_succeeded?: number | null;
  last_bulk_retry_still_failed?: number | null;
  last_bulk_retry_total?: number | null;
}

interface SocialProofMetrics {
  total_cards: number;
  draft_count: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  published_count: number;
  attention_required_count: number;
  approval_rate: number;
  publish_rate: number;
  last_published_at?: string | null;
  last_rejected_at?: string | null;
  last_pending_at?: string | null;
}

interface NotificationHealthSummary {
  subscription_count: number;
  unread_count: number;
  push_configured: boolean;
  push_availability_reason?: string | null;
  last_delivery_attempt_at?: string | null;
  last_delivery_status?: string | null;
  last_delivery_channel?: string | null;
  last_delivery_failure_reason?: string | null;
  recent_delivered_count: number;
  recent_failed_count: number;
  recent_unavailable_count: number;
  recent_skipped_count: number;
  attention_needed: boolean;
  window_days: number;
  source: string;
}

interface MetricDelta {
  current: number;
  previous: number;
  delta: number;
  percent_change: number;
}

interface DashboardPayload {
  location_id: string;
  metrics: {
    calls: MetricDelta;
    directions: MetricDelta;
    website_clicks: MetricDelta;
    profile_views: MetricDelta;
    new_reviews: MetricDelta;
    avg_rating: number | null;
    estimated_revenue: number;
  };
  highlights: Array<{
    type: 'increase' | 'decrease' | 'milestone';
    metric: string;
    message: string;
    value: number;
    percent: number;
  }>;
  chart_data: Array<{
    date: string;
    calls: number;
    directions: number;
    website_clicks: number;
  }>;
}

interface WeeklyReportItem {
  id: string;
  report_week: string;
  summary: {
    calls_total: number;
    calls_delta: number;
    calls_percent: number;
    directions_total: number;
    directions_delta: number;
    directions_percent: number;
    estimated_revenue: number;
    highlights: string[];
  };
  pdf_url?: string | null;
  sent_at?: string | null;
}

interface RevenueProfileSummary {
  business_type?: string | null;
  average_order_value?: number | string | null;
  owner_hourly_value?: number | string | null;
}

interface PostSummary {
  id: string;
  title?: string | null;
  platform?: string | null;
  status?: string | null;
}

function hasRevenueProfileConfigured(profile: RevenueProfileSummary | null) {
  if (!profile) return false;
  if (profile.business_type && profile.business_type.trim().length > 0) return true;
  const aov = Number(profile.average_order_value ?? 150);
  const hourly = Number(profile.owner_hourly_value ?? 50);
  return aov !== 150 || hourly !== 50;
}

function DashboardPageFallback() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="mb-2 h-8 w-56" />
        <Skeleton className="h-4 w-72" />
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((item) => (
          <Card key={item}>
            <CardContent className="pt-6">
              <Skeleton className="mb-2 h-4 w-24" />
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function DashboardPageInner() {
  const searchParams = useSearchParams();
  const [isBootLoading, setIsBootLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [locations, setLocations] = useState<DashboardLocation[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [allPosts, setAllPosts] = useState<PostSummary[]>([]);
  const [pendingPosts, setPendingPosts] = useState<PostSummary[]>([]);
  const [selectedChannels, setSelectedChannels] = useState<DashboardChannelSummary[]>([]);
  const [latestReport, setLatestReport] = useState<WeeklyReportItem | undefined>(undefined);
  const [revenueProfile, setRevenueProfile] = useState<RevenueProfileSummary | null>(null);
  const [reviewResponderSummary, setReviewResponderSummary] = useState<ReviewResponderSummary | null>(null);
  const [socialProofMetrics, setSocialProofMetrics] = useState<SocialProofMetrics | null>(null);
  const [notificationHealth, setNotificationHealth] = useState<NotificationHealthSummary | null>(null);

  const activeLocationId = selectedLocation || locations[0]?.id || null;
  const selectedLocationRecord = locations.find((location) => location.id === activeLocationId) ?? null;
  const gbpChannel = selectedChannels.find((channel) => channel.type === 'GBP');
  const publishingChannels = selectedChannels.filter((channel) =>
    channel.type === 'GBP' || channel.type === 'INSTAGRAM' || channel.type === 'WEBSITE'
  );
  const setupComplete = searchParams.get('setup') === 'complete';
  const setupSource = searchParams.get('source');

  const loadLocations = async () => {
    const locResponse = await locationsApi.list();
    const locationItems = extractCollectionPayload<DashboardLocation>(locResponse.data, 'locations');
    setLocations(locationItems);
    setSelectedLocation((current) =>
      current && locationItems.some((location) => location.id === current)
        ? current
        : (locationItems[0]?.id ?? null)
    );
    return locationItems;
  };

  const loadDashboardData = async (locationId: string, silent = false) => {
    if (!silent) setIsRefreshing(true);
    try {
      const [dashboardRes, postsRes, pendingPostsRes, channelsRes, revenueRes, reportsRes] = await Promise.all([
        metricsApi.getDashboard(locationId, 7),
        postsApi.list({ locationId }),
        postsApi.list({ locationId, status: 'pending_approval' }),
        locationsApi.listChannels(locationId),
        revenueApi.getProfile(locationId),
        reportsApi.list(locationId, 1),
      ]);

      const [reviewResponderResult, socialProofResult, notificationHealthResult] = await Promise.allSettled([
        reviewResponderApi.getSummary(locationId),
        socialProofHistoryApi.getHistory(locationId, { limit: 1, offset: 0 }),
        notificationsApi.getHealthSummary(),
      ]);

      setDashboard(dashboardRes.data);
      setAllPosts(Array.isArray(postsRes.data) ? postsRes.data : []);
      setPendingPosts(Array.isArray(pendingPostsRes.data) ? pendingPostsRes.data : []);
      setSelectedChannels(Array.isArray(channelsRes.data) ? channelsRes.data : []);
      setRevenueProfile(revenueRes.data || null);
      setLatestReport(reportsRes.data?.items?.[0]);
      setReviewResponderSummary(
        reviewResponderResult.status === 'fulfilled' ? reviewResponderResult.value.data : null
      );
      setSocialProofMetrics(
        socialProofResult.status === 'fulfilled' ? socialProofResult.value.data?.metrics ?? null : null
      );
      setNotificationHealth(
        notificationHealthResult.status === 'fulfilled' ? notificationHealthResult.value.data ?? null : null
      );
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      setDashboard(null);
      setAllPosts([]);
      setPendingPosts([]);
      setSelectedChannels([]);
      setRevenueProfile(null);
      setLatestReport(undefined);
      setReviewResponderSummary(null);
      setSocialProofMetrics(null);
      setNotificationHealth(null);
    } finally {
      setIsRefreshing(false);
      setIsBootLoading(false);
    }
  };

  useEffect(() => {
    void loadLocations()
      .catch((error) => {
        console.error('Failed to load locations:', error);
      })
      .finally(() => {
        setIsBootLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!activeLocationId) return;
    void loadDashboardData(activeLocationId);
  }, [activeLocationId]);

  const activationChecklist = useMemo(() => {
    const hasPublishingChannel = selectedChannels.some(
      (channel) =>
        (channel.type === 'INSTAGRAM' || channel.type === 'WEBSITE') &&
        channel.status === 'connected' &&
        !channel.reconnect_required
    );

    return [
      {
        id: 'gbp',
        label: 'Connect Google Business Profile',
        done: !!selectedLocationRecord?.gbp_connected,
        href: '/dashboard/integrations',
        helper: selectedLocationRecord?.gbp_connected
          ? 'GBP is connected for this location.'
          : 'Connect GBP first so reviews, Q&A, and profile visibility data can sync.',
      },
      {
        id: 'revenue',
        label: 'Set revenue assumptions',
        done: hasRevenueProfileConfigured(revenueProfile),
        href: '/dashboard/roi',
        helper: hasRevenueProfileConfigured(revenueProfile)
          ? 'Revenue inputs are saved for ROI and weekly reporting.'
          : 'Set order value and owner time assumptions so ROI is usable.',
      },
      {
        id: 'content',
        label: 'Create your first draft',
        done: allPosts.length > 0,
        href: '/dashboard/content/new',
        helper: allPosts.length > 0
          ? `${allPosts.length} post${allPosts.length === 1 ? '' : 's'} already created.`
          : 'Generate your first post so approval and publishing workflows can start.',
      },
      {
        id: 'publishing',
        label: 'Prepare a publishing channel',
        done: hasPublishingChannel,
        href: '/dashboard/integrations',
        helper: hasPublishingChannel
          ? 'At least one publishing channel is ready.'
          : 'Connect Instagram or Website so content can move beyond draft stage.',
      },
      {
        id: 'qa',
        label: 'Sync Google Q&A at least once',
        done: !!gbpChannel?.qa_last_sync_at,
        href: '/dashboard/qa',
        helper: gbpChannel?.qa_last_sync_at
          ? `Last synced ${new Date(gbpChannel.qa_last_sync_at).toLocaleString()}.`
          : 'Run a first Q&A sync to pull live questions into the workspace.',
      },
      {
        id: 'notifications',
        label: 'Enable notifications on at least one device',
        done: Boolean(notificationHealth?.push_configured && notificationHealth?.subscription_count > 0),
        href: '/dashboard/notifications',
        helper: notificationHealth?.push_configured
          ? notificationHealth?.subscription_count
            ? `${notificationHealth.subscription_count} saved device${notificationHealth.subscription_count === 1 ? '' : 's'} ready for alerts.`
            : 'Push is configured, but no browser has been subscribed yet.'
          : notificationHealth?.push_availability_reason || 'Finish push setup so alerts can reach the operator in time.',
      },
    ];
  }, [
    allPosts.length,
    gbpChannel?.qa_last_sync_at,
    notificationHealth?.push_availability_reason,
    notificationHealth?.push_configured,
    notificationHealth?.subscription_count,
    revenueProfile,
    selectedChannels,
    selectedLocationRecord?.gbp_connected,
  ]);

  const completedChecklistCount = activationChecklist.filter((item) => item.done).length;
  const nextChecklistItem = activationChecklist.find((item) => !item.done) ?? null;
  const launchChecklist = activationChecklist.slice(0, 3);
  const advancedChecklist = activationChecklist.slice(3);
  const completedLaunchCount = launchChecklist.filter((item) => item.done).length;

  const activityItems = useMemo(() => {
    const items: Array<{ label: string; detail: string; tone: 'neutral' | 'good' | 'warn' }> = [];

    if (pendingPosts.length > 0) {
      items.push({
        label: 'Approval work waiting',
        detail: `${pendingPosts.length} post${pendingPosts.length === 1 ? '' : 's'} still need approval.`,
        tone: 'warn',
      });
    }
    if (gbpChannel?.qa_failed_count) {
      items.push({
        label: 'Q&A needs review',
        detail: `${gbpChannel.qa_failed_count} Q&A draft${gbpChannel.qa_failed_count === 1 ? '' : 's'} failed and should be retried.`,
        tone: 'warn',
      });
    }
    const recentPublish = publishingChannels.find((channel) => channel.last_publish_succeeded_at);
    if (recentPublish?.last_publish_succeeded_at) {
      items.push({
        label: `${recentPublish.type} published recently`,
        detail: new Date(recentPublish.last_publish_succeeded_at).toLocaleString(),
        tone: 'good',
      });
    }
    if (latestReport?.report_week) {
      items.push({
        label: 'Latest weekly report ready',
        detail: `Week of ${new Date(latestReport.report_week).toLocaleDateString()}`,
        tone: 'neutral',
      });
    }
    if (notificationHealth?.attention_needed) {
      items.push({
        label: 'Notification setup needs attention',
        detail:
          notificationHealth.push_availability_reason ||
          'Push delivery has no saved device or recent delivery problems need review.',
        tone: 'warn',
      });
    }
    if (dashboard?.highlights?.length) {
      for (const highlight of dashboard.highlights.slice(0, 2)) {
        items.push({
          label: 'Performance highlight',
          detail: highlight.message,
          tone: highlight.type === 'decrease' ? 'warn' : 'good',
        });
      }
    }
    return items.slice(0, 5);
  }, [
    dashboard?.highlights,
    gbpChannel?.qa_failed_count,
    latestReport?.report_week,
    notificationHealth?.attention_needed,
    notificationHealth?.push_availability_reason,
    pendingPosts.length,
    publishingChannels,
  ]);

  if (isBootLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="mb-2 h-8 w-56" />
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <Card key={item}>
              <CardContent className="pt-6">
                <Skeleton className="mb-2 h-4 w-24" />
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (locations.length === 0) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-100">
          <AlertCircle className="h-8 w-8 text-violet-600" />
        </div>
        <h2 className="mb-2 text-2xl font-bold">Add your first location</h2>
        <p className="mb-6 max-w-md text-gray-500">
          The workspace needs at least one business location before posts, reviews, and reporting can start.
        </p>
        <Link href="/onboarding">
          <Button className="bg-gradient-to-r from-violet-600 to-indigo-600">
            Start onboarding
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Local Growth Control Center</h1>
          <p className="text-gray-500">
            Start here to improve visibility, earn trust, capture demand, and prove revenue impact for each location.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={activeLocationId || ''}
            onChange={(event) => setSelectedLocation(event.target.value)}
          >
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
          <Button variant="outline" onClick={() => activeLocationId && void loadDashboardData(activeLocationId)} disabled={isRefreshing}>
            {isRefreshing ? <Clock className="mr-2 h-4 w-4 animate-spin" /> : null}
            Refresh
          </Button>
        </div>
      </div>

      {setupComplete ? (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-3">
              <CheckCircle className="mt-0.5 h-5 w-5 text-green-700" />
              <div>
                <p className="font-medium text-green-900">
                  {setupSource === 'trial' ? 'Free preview setup completed' : 'Onboarding completed'}
                </p>
                <p className="text-sm text-green-800">
                  The workspace is ready. Focus on the next action that gets this location to first value.
                </p>
              </div>
            </div>
            {nextChecklistItem ? (
              <Link href={nextChecklistItem.href}>
                <Button className="bg-green-700 hover:bg-green-800">
                  Open next step
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {selectedLocationRecord?.instagram_status &&
      selectedLocationRecord.instagram_status !== 'connected' &&
      selectedLocationRecord.instagram_status !== 'not configured' ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-center justify-between gap-4 pt-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 text-amber-600" />
              <div>
                <p className="font-medium text-amber-900">Instagram connection needs attention</p>
                <p className="text-sm text-amber-800">
                  {selectedLocationRecord.name}: {selectedLocationRecord.instagram_status}
                </p>
              </div>
            </div>
            <Link href="/dashboard/integrations">
              <Button variant="outline" className="border-amber-300 bg-white text-amber-900 hover:bg-amber-100">
                Review connection
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : null}

      <Card className="overflow-hidden border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-sky-950 text-white shadow-sm">
        <CardContent className="grid gap-6 p-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.9fr)]">
          <div className="space-y-4">
            <Badge className="border-white/20 bg-white/10 text-white hover:bg-white/10">
              Today&apos;s Next Best Action
            </Badge>
            <div>
              <h2 className="text-3xl font-semibold tracking-tight">
                {nextChecklistItem ? nextChecklistItem.label : 'Keep the operating rhythm moving'}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-200">
                {nextChecklistItem
                  ? nextChecklistItem.helper
                  : 'Core setup is complete. Review the supporting cards only to catch new blockers or prove what improved.'}
              </p>
            </div>
            {nextChecklistItem ? (
              <Link href={nextChecklistItem.href}>
                <Button size="lg" className="bg-white text-slate-950 hover:bg-slate-100">
                  Do this now
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            ) : (
              <div className="rounded-lg border border-emerald-300/30 bg-emerald-400/10 p-3 text-sm text-emerald-50">
                No setup blocker is waiting. Use the weekly cards below to protect momentum and prove ROI.
              </div>
            )}
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/10 p-4">
            <div className="text-sm font-semibold text-white">Why this matters</div>
            <p className="mt-2 text-sm leading-6 text-slate-200">
              The dashboard now picks one action first, then keeps metrics and advanced workflows secondary so operators
              do not have to decode the whole product before making progress.
            </p>
            <div className="mt-4 grid gap-2 text-sm">
              <div className="flex items-center gap-3 rounded-xl bg-white/10 p-3">
                <Globe className="h-4 w-4 text-sky-200" />
                <span>Get found through healthier profiles and local content.</span>
              </div>
              <div className="flex items-center gap-3 rounded-xl bg-white/10 p-3">
                <Star className="h-4 w-4 text-amber-200" />
                <span>Earn trust with reviews, Q&A, and visible proof.</span>
              </div>
              <div className="flex items-center gap-3 rounded-xl bg-white/10 p-3">
                <Phone className="h-4 w-4 text-emerald-200" />
                <span>Capture demand before missed calls or replies go cold.</span>
              </div>
              <div className="flex items-center gap-3 rounded-xl bg-white/10 p-3">
                <TrendingUp className="h-4 w-4 text-violet-200" />
                <span>Prove ROI with actions tied back to business value.</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
        <ProofCard
          title="Calls"
          value={dashboard?.metrics.calls.current || 0}
          previousValue={dashboard?.metrics.calls.previous || 0}
          icon={<Phone className="w-6 h-6 text-green-600" />}
          iconBgColor="bg-green-100"
        />
        <ProofCard
          title="Directions"
          value={dashboard?.metrics.directions.current || 0}
          previousValue={dashboard?.metrics.directions.previous || 0}
          icon={<Navigation className="w-6 h-6 text-blue-600" />}
          iconBgColor="bg-blue-100"
        />
        <ProofCard
          title="Profile Views"
          value={dashboard?.metrics.profile_views.current || 0}
          previousValue={dashboard?.metrics.profile_views.previous || 0}
          icon={<Eye className="w-6 h-6 text-purple-600" />}
          iconBgColor="bg-purple-100"
        />
        <ProofCard
          title="Average Rating"
          value={dashboard?.metrics.avg_rating || 0}
          format="rating"
          icon={<Star className="w-6 h-6 text-yellow-600" />}
          iconBgColor="bg-yellow-100"
          showDelta={false}
        />
        <ProofCard
          title="Estimated Revenue"
          value={dashboard?.metrics.estimated_revenue || 0}
          previousValue={0}
          format="currency"
          icon={<DollarSign className="w-6 h-6 text-violet-600" />}
          iconBgColor="bg-violet-100"
          showDelta={false}
          subtitle="Based on your current revenue assumptions"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(340px,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">3-Step Launch Checklist</CardTitle>
            <CardDescription>
              Finish these first. Everything else is secondary until the business can be found, measured, and updated.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border bg-slate-50 p-4">
              <div>
                <div className="font-medium">Launch progress</div>
                <div className="text-sm text-gray-500">
                  {completedLaunchCount} of {launchChecklist.length} launch steps completed for this location
                </div>
              </div>
              <Badge variant="secondary">{Math.round((completedLaunchCount / launchChecklist.length) * 100)}%</Badge>
            </div>
            {nextChecklistItem ? (
              <div className="rounded-lg border border-dashed bg-white p-4">
                <div className="mb-1 text-sm font-medium text-slate-900">Do this next</div>
                <div className="text-sm text-gray-600">{nextChecklistItem.label}</div>
                <div className="mt-1 text-sm text-gray-500">{nextChecklistItem.helper}</div>
              </div>
            ) : (
              <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
                Core setup is complete. You can keep building weekly habits from content, reviews, and reporting.
              </div>
            )}
            <div className="space-y-3">
              {launchChecklist.map((item) => (
                <div key={item.id} className="flex items-start justify-between gap-4 rounded-lg border p-4">
                  <div className="flex items-start gap-3">
                    <div className={`mt-0.5 flex h-8 w-8 items-center justify-center rounded-full ${item.done ? 'bg-green-100' : 'bg-amber-100'}`}>
                      {item.done ? (
                        <CheckCircle className="h-4 w-4 text-green-700" />
                      ) : (
                        <Clock className="h-4 w-4 text-amber-700" />
                      )}
                    </div>
                    <div>
                      <p className="font-medium">{item.label}</p>
                      <p className="text-sm text-gray-500">{item.helper}</p>
                    </div>
                  </div>
                  <Link href={item.href}>
                    <Button variant={item.done ? 'outline' : 'default'} size="sm">
                      {item.done ? 'Review' : 'Open'}
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
            <details className="group rounded-lg border border-dashed bg-slate-50">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium text-slate-700">
                <span>
                  Advanced setup checks ({completedChecklistCount - completedLaunchCount} of {advancedChecklist.length} complete)
                </span>
                <span className="text-xs text-slate-500 group-open:hidden">Show</span>
                <span className="hidden text-xs text-slate-500 group-open:inline">Hide</span>
              </summary>
              <div className="space-y-3 px-4 pb-4">
                {advancedChecklist.map((item) => (
                  <div key={item.id} className="flex items-start justify-between gap-4 rounded-lg border bg-white p-4">
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 flex h-8 w-8 items-center justify-center rounded-full ${item.done ? 'bg-green-100' : 'bg-amber-100'}`}>
                        {item.done ? (
                          <CheckCircle className="h-4 w-4 text-green-700" />
                        ) : (
                          <Clock className="h-4 w-4 text-amber-700" />
                        )}
                      </div>
                      <div>
                        <p className="font-medium">{item.label}</p>
                        <p className="text-sm text-gray-500">{item.helper}</p>
                      </div>
                    </div>
                    <Link href={item.href}>
                      <Button variant={item.done ? 'outline' : 'default'} size="sm">
                        {item.done ? 'Review' : 'Open'}
                      </Button>
                    </Link>
                  </div>
                ))}
              </div>
            </details>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Publishing Reliability</CardTitle>
            <CardDescription>Keep channels healthy so approved content can actually reach customers.</CardDescription>
          </CardHeader>
          <CardContent>
            {publishingChannels.length > 0 ? (
              <div className="space-y-3">
                {publishingChannels.map((channel) => (
                  <div key={channel.id} className="rounded-lg border p-4">
                    <div className="flex items-center justify-between">
                      <div className="font-medium">{channel.type}</div>
                      <Badge
                        className={
                          channel.reconnect_required
                            ? 'border-red-200 bg-red-50 text-red-700'
                            : channel.needs_refresh
                              ? 'border-amber-200 bg-amber-50 text-amber-700'
                              : channel.status === 'connected'
                                ? 'border-green-200 bg-green-50 text-green-700'
                                : 'border-gray-200 bg-gray-50 text-gray-700'
                        }
                      >
                        {channel.reconnect_required
                          ? 'reconnect required'
                          : channel.needs_refresh
                            ? 'token refresh needed'
                            : channel.status}
                      </Badge>
                    </div>
                    <div className="mt-3 text-sm text-gray-500">Last successful publish</div>
                    <div className="text-sm font-medium">
                      {channel.last_publish_succeeded_at
                        ? new Date(channel.last_publish_succeeded_at).toLocaleString()
                        : 'No successful publish yet'}
                    </div>
                    {channel.last_publish_failed_at ? (
                      <div className="mt-2 text-xs text-red-600">
                        Last failure: {channel.last_publish_failed_error || 'Publish failed'}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500">No publishing channels configured yet.</div>
            )}
          </CardContent>
        </Card>
      </div>

      <details className="group rounded-2xl border bg-white shadow-sm">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4">
          <div>
            <div className="font-semibold text-slate-950">Supporting diagnostics</div>
            <div className="mt-1 text-sm text-slate-500">
              Open this only when you want deeper signals about reviews, proof assets, alerts, reports, and trends.
            </div>
          </div>
          <span className="text-sm font-medium text-slate-600 group-open:hidden">Show details</span>
          <span className="hidden text-sm font-medium text-slate-600 group-open:inline">Hide details</span>
        </summary>
        <div className="space-y-6 border-t bg-slate-50/60 p-5">
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            <Card>
          <CardHeader>
            <CardTitle className="text-lg">Trust Protection</CardTitle>
            <CardDescription>Respond to reviews quickly so public reputation keeps working for the business.</CardDescription>
          </CardHeader>
          <CardContent>
            {reviewResponderSummary ? (
              <div className="space-y-3">
                <div className="grid gap-3 text-sm md:grid-cols-2">
                  <div>
                    <div className="text-gray-500">Pending drafts</div>
                    <div className="font-medium">{reviewResponderSummary.pending_count}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">High-priority pending</div>
                    <div className="font-medium text-amber-700">{reviewResponderSummary.high_priority_pending_count}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Failed responses</div>
                    <div className="font-medium text-rose-700">{reviewResponderSummary.failed_count}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Published responses</div>
                    <div className="font-medium">{reviewResponderSummary.published_count}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Last activity</div>
                    <div className="font-medium">
                      {reviewResponderSummary.last_activity_at
                        ? new Date(reviewResponderSummary.last_activity_at).toLocaleString()
                        : 'No activity yet'}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-500">Last failed</div>
                    <div className="font-medium">
                      {reviewResponderSummary.last_failed_at
                        ? new Date(reviewResponderSummary.last_failed_at).toLocaleString()
                        : 'None'}
                    </div>
                  </div>
                </div>
                {reviewResponderSummary.last_bulk_retry_at ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                    <span className="font-medium">Last bulk retry</span>{' '}
                    {new Date(reviewResponderSummary.last_bulk_retry_at).toLocaleString()}
                    {': '}
                    <span className="font-medium text-green-700">{reviewResponderSummary.last_bulk_retry_succeeded ?? 0} succeeded</span>
                    {', '}
                    <span className={reviewResponderSummary.last_bulk_retry_still_failed ? 'font-medium text-rose-600' : ''}>
                      {reviewResponderSummary.last_bulk_retry_still_failed ?? 0} still failed
                    </span>
                    {' of '}
                    {reviewResponderSummary.last_bulk_retry_total ?? 0} attempted
                  </div>
                ) : null}
                <div className="rounded-lg border border-dashed bg-slate-50 p-3 text-sm text-slate-700">
                  {reviewResponderSummary.high_priority_total_count > 0
                    ? 'There are review responses that need manual attention before they are published.'
                    : 'Review response workflow is quiet right now.'}
                </div>
                <Link href="/dashboard/review-responder">
                  <Button variant="outline" size="sm">
                    Open Review Responder
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="text-sm text-gray-500">No review responder activity yet for this location.</div>
            )}
          </CardContent>
            </Card>

            <Card>
          <CardHeader>
            <CardTitle className="text-lg">Proof Assets</CardTitle>
            <CardDescription>Turn customer signals into reusable proof that helps more prospects convert.</CardDescription>
          </CardHeader>
          <CardContent>
            {socialProofMetrics ? (
              <div className="space-y-3">
                <div className="grid gap-3 text-sm md:grid-cols-2">
                  <div>
                    <div className="text-gray-500">Pending cards</div>
                    <div className="font-medium">{socialProofMetrics.pending_count}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Attention required</div>
                    <div className="font-medium text-rose-700">{socialProofMetrics.attention_required_count}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Approval rate</div>
                    <div className="font-medium">{Math.round(socialProofMetrics.approval_rate)}%</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Publish rate</div>
                    <div className="font-medium">{Math.round(socialProofMetrics.publish_rate)}%</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Last published</div>
                    <div className="font-medium">
                      {socialProofMetrics.last_published_at
                        ? new Date(socialProofMetrics.last_published_at).toLocaleString()
                        : 'No published cards yet'}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-500">Last rejected</div>
                    <div className="font-medium">
                      {socialProofMetrics.last_rejected_at
                        ? new Date(socialProofMetrics.last_rejected_at).toLocaleString()
                        : 'None'}
                    </div>
                  </div>
                </div>
                <div className="rounded-lg border border-dashed bg-rose-50 p-3 text-sm text-rose-700">
                  {socialProofMetrics.attention_required_count > 0
                    ? 'Some social proof cards need review before they can be published.'
                    : 'Social proof workflow is currently up to date.'}
                </div>
                <Link href="/dashboard/social-proof">
                  <Button variant="outline" size="sm">
                    Open Social Proof
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="text-sm text-gray-500">No social proof activity yet for this location.</div>
            )}
          </CardContent>
            </Card>

            <Card>
          <CardHeader>
            <CardTitle className="text-lg">Alert Readiness</CardTitle>
            <CardDescription>Make sure urgent failures and customer follow-up items reach the operator in time.</CardDescription>
          </CardHeader>
          <CardContent>
            {notificationHealth ? (
              <div className="space-y-3">
                <div className="grid gap-3 text-sm md:grid-cols-2">
                  <div>
                    <div className="text-gray-500">Saved devices</div>
                    <div className="font-medium">{notificationHealth.subscription_count}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Unread inbox</div>
                    <div className="font-medium">{notificationHealth.unread_count}</div>
                  </div>
                  <div>
                    <div className="text-gray-500">Push status</div>
                    <div className={notificationHealth.push_configured ? 'font-medium text-green-700' : 'font-medium text-amber-700'}>
                      {notificationHealth.push_configured ? 'Configured' : 'Needs setup'}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-500">Recent failed deliveries</div>
                    <div className={notificationHealth.recent_failed_count > 0 ? 'font-medium text-rose-700' : 'font-medium'}>
                      {notificationHealth.recent_failed_count}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-500">Recent unavailable attempts</div>
                    <div className={notificationHealth.recent_unavailable_count > 0 ? 'font-medium text-amber-700' : 'font-medium'}>
                      {notificationHealth.recent_unavailable_count}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-500">Delivered in last {notificationHealth.window_days} days</div>
                    <div className="font-medium">{notificationHealth.recent_delivered_count}</div>
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  <div className="mb-1 flex items-center gap-2 font-medium">
                    <Bell className="h-4 w-4" />
                    Last delivery attempt
                  </div>
                  <div>
                    {notificationHealth.last_delivery_attempt_at
                      ? `${new Date(notificationHealth.last_delivery_attempt_at).toLocaleString()} via ${notificationHealth.last_delivery_channel || 'unknown'} (${notificationHealth.last_delivery_status || 'unknown'})`
                      : 'No delivery attempts recorded yet.'}
                  </div>
                  {notificationHealth.last_delivery_failure_reason ? (
                    <div className="mt-1 text-rose-700">{notificationHealth.last_delivery_failure_reason}</div>
                  ) : null}
                </div>
                <div
                  className={`rounded-lg border border-dashed p-3 text-sm ${
                    notificationHealth.attention_needed
                      ? 'border-amber-200 bg-amber-50 text-amber-900'
                      : 'border-green-200 bg-green-50 text-green-800'
                  }`}
                >
                  {notificationHealth.attention_needed
                    ? notificationHealth.push_availability_reason ||
                      'Notifications need attention. Review push setup, saved devices, or recent failed deliveries.'
                    : 'Notification delivery looks healthy right now.'}
                </div>
                <Link href="/dashboard/notifications">
                  <Button variant="outline" size="sm">
                    {notificationHealth.attention_needed ? 'Fix Notifications' : 'Open Notifications'}
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="text-sm text-gray-500">Notification health has not been loaded yet.</div>
            )}
          </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <MetricsChart data={dashboard?.chart_data || []} title="Last 7 Days of Calls, Directions, and Clicks" />
            </div>
            <Highlights highlights={dashboard?.highlights || []} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <WeeklyReportCard
              report={latestReport}
              onGenerate={() => {
                window.location.href = '/dashboard/reports';
              }}
              onDownload={() => {
                window.location.href = '/dashboard/reports';
              }}
              onSendEmail={() => {
                window.location.href = '/dashboard/reports';
              }}
            />

            <Card>
          <CardHeader>
            <CardTitle className="text-lg">Next Action Signals</CardTitle>
            <CardDescription>Use these signals to decide what will improve outcomes fastest.</CardDescription>
          </CardHeader>
          <CardContent>
            {activityItems.length > 0 ? (
              <div className="space-y-4">
                {activityItems.map((item, index) => (
                  <div key={`${item.label}-${index}`} className="flex items-start gap-3">
                    <div
                      className={`mt-0.5 h-2.5 w-2.5 rounded-full ${
                        item.tone === 'warn'
                          ? 'bg-amber-500'
                          : item.tone === 'good'
                            ? 'bg-green-500'
                            : 'bg-slate-400'
                      }`}
                    />
                    <div className="min-w-0">
                      <p className="font-medium">{item.label}</p>
                      <p className="text-sm text-gray-500">{item.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed p-6 text-center text-sm text-gray-500">
                No recent operational signals yet. Connect channels and start publishing to build activity history.
              </div>
            )}
          </CardContent>
            </Card>
          </div>
        </div>
      </details>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">Pending Approvals</CardTitle>
              <CardDescription>Approve or revise content so visibility work does not stall.</CardDescription>
            </div>
            <Badge variant="secondary">{pendingPosts.length}</Badge>
          </CardHeader>
          <CardContent>
            {pendingPosts.length > 0 ? (
              <div className="space-y-3">
                {pendingPosts.slice(0, 3).map((post) => (
                  <div key={post.id} className="flex items-start gap-3 rounded-lg bg-gray-50 p-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-100">
                      <FileText className="h-5 w-5 text-violet-600" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{post.title || 'Untitled post'}</p>
                      <p className="text-sm text-gray-500">{post.platform || 'Unknown platform'}</p>
                    </div>
                    <Link href="/dashboard/content?status=pending_approval">
                      <Button size="sm" variant="outline">
                        Review
                      </Button>
                    </Link>
                  </div>
                ))}
                <Link href="/dashboard/content?status=pending_approval">
                  <Button variant="ghost" className="w-full">
                    Open content queue
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="py-8 text-center text-gray-500">
                <CheckCircle className="mx-auto mb-2 h-12 w-12 text-green-500" />
                <p>No content is waiting for approval right now.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Outcome Shortcuts</CardTitle>
            <CardDescription>Jump directly to the workflows that create visibility, trust, demand, or ROI proof.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link href="/dashboard/content/new" className="block">
              <Button variant="outline" className="h-auto w-full justify-start py-3">
                <div className="mr-3 flex h-10 w-10 items-center justify-center rounded-lg bg-violet-100">
                  <FileText className="h-5 w-5 text-violet-600" />
                </div>
                <div className="text-left">
                  <p className="font-medium">Create visibility content</p>
                  <p className="text-sm text-gray-500">Publish fresh updates that help the location get found</p>
                </div>
              </Button>
            </Link>
            <Link href="/dashboard/reviews" className="block">
              <Button variant="outline" className="h-auto w-full justify-start py-3">
                <div className="mr-3 flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-100">
                  <Star className="h-5 w-5 text-yellow-600" />
                </div>
                <div className="text-left">
                  <p className="font-medium">Build review trust</p>
                  <p className="text-sm text-gray-500">Ask happy customers for proof and route issues privately</p>
                </div>
              </Button>
            </Link>
            <Link href="/dashboard/integrations" className="block">
              <Button variant="outline" className="h-auto w-full justify-start py-3">
                <div className="mr-3 flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
                  <Globe className="h-5 w-5 text-blue-600" />
                </div>
                <div className="text-left">
                  <p className="font-medium">Remove channel blockers</p>
                  <p className="text-sm text-gray-500">Reconnect services before publishing or automation fails</p>
                </div>
              </Button>
            </Link>
            <Link href="/dashboard/roi" className="block">
              <Button variant="outline" className="h-auto w-full justify-start py-3">
                <div className="mr-3 flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
                  <TrendingUp className="h-5 w-5 text-green-600" />
                </div>
                <div className="text-left">
                  <p className="font-medium">Prove revenue impact</p>
                  <p className="text-sm text-gray-500">Keep ROI assumptions aligned with the real business model</p>
                </div>
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<DashboardPageFallback />}>
      <DashboardPageInner />
    </Suspense>
  );
}
