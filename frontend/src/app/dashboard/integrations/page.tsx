'use client';

import { useEffect, useEffectEvent, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  ArrowRight,
  Bell,
  Loader2,
  PlugZap,
  RefreshCw,
  Unplug,
} from 'lucide-react';

import { extractCollectionPayload, locationsApi, notificationsApi, oauthApi, qaApi, socialApi, reviewResponderApi, socialProofHistoryApi } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { getApiErrorMessage } from '@/lib/api-errors';
import { toast } from 'sonner';

interface IntegrationLocation {
  id: string;
  name: string;
  gbp_connected?: boolean;
  gbp_status?: string | null;
  instagram_connected?: boolean;
  instagram_status?: string | null;
  website_connected?: boolean;
  website_status?: string | null;
}

interface ChannelDetail {
  id: string;
  type: 'GBP' | 'INSTAGRAM' | 'WEBSITE' | string;
  status: string;
  platform_account_id?: string | null;
  platform_account_name?: string | null;
  access_token_expires_at?: string | null;
  is_token_expired?: boolean;
  needs_refresh?: boolean;
  reconnect_required?: boolean;
  error_message?: string | null;
  error_count?: number;
  last_publish_failed_at?: string | null;
  last_publish_failed_error?: string | null;
  last_publish_succeeded_at?: string | null;
  recent_publish_failures?: number;
  recent_publish_successes?: number;
  qa_pending_count?: number;
  qa_failed_count?: number;
  qa_posted_count?: number;
  qa_last_failed_at?: string | null;
  qa_last_posted_at?: string | null;
  qa_last_sync_at?: string | null;
  qa_last_sync_error?: string | null;
  qa_last_sync_question_count?: number;
  qa_feedback_good_count?: number;
  qa_feedback_needs_edit_count?: number;
  qa_feedback_wrong_count?: number;
}

interface SocialAutomationSettings {
  auto_respond_enabled: boolean;
  auto_respond_dms: boolean;
  auto_respond_comments: boolean;
  response_delay_seconds: number;
  excluded_keywords: string[];
  high_priority_alerts_enabled?: boolean;
  high_priority_alert_channel?: string;
}

interface SocialAutomationStats {
  total_messages: number;
  auto_responded: number;
  manual_responses: number;
  failed_responses: number;
  avg_response_time_minutes: number;
  response_rate: number;
  sentiment_positive: number;
  sentiment_neutral: number;
  sentiment_negative: number;
  last_successful_response_at?: string | null;
  last_failed_response_at?: string | null;
  automation_health?: string;
  automation_health_reason?: string | null;
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

interface SocialProofSummary {
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
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const channelBadgeClass = (status?: string | null, connected?: boolean) => {
  if (status === 'reconnect required') return 'border-red-200 bg-red-50 text-red-700';
  if (status === 'token refresh needed') return 'border-amber-200 bg-amber-50 text-amber-700';
  if (connected) return 'border-green-200 bg-green-50 text-green-700';
  return 'border-gray-200 bg-gray-50 text-gray-700';
};

const formatDateTime = (value?: string | null) => {
  if (!value) return 'None';
  return new Date(value).toLocaleString();
};

export default function IntegrationsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [locations, setLocations] = useState<IntegrationLocation[]>([]);
  const [channelsByLocation, setChannelsByLocation] = useState<Record<string, ChannelDetail[]>>({});
  const [socialSettingsByLocation, setSocialSettingsByLocation] = useState<Record<string, SocialAutomationSettings>>({});
  const [socialStatsByLocation, setSocialStatsByLocation] = useState<Record<string, SocialAutomationStats>>({});
  const [reviewResponderSummaryByLocation, setReviewResponderSummaryByLocation] = useState<Record<string, ReviewResponderSummary>>({});
  const [socialProofSummaryByLocation, setSocialProofSummaryByLocation] = useState<Record<string, SocialProofSummary>>({});
  const [notificationHealth, setNotificationHealth] = useState<NotificationHealthSummary | null>(null);
  const [selectedLocationId, setSelectedLocationId] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'attention' | 'stable'>('all');

  const loadData = async () => {
    try {
      const response = await locationsApi.list();
      const locationItems = extractCollectionPayload<IntegrationLocation>(response.data, 'locations');
      setLocations(locationItems);
      if (locationItems.length > 0 && selectedLocationId === 'all') {
        setSelectedLocationId('all');
      }

      const channelResponses = await Promise.allSettled(
        locationItems.map(async (location: IntegrationLocation) => {
          const channelsResponse = await locationsApi.listChannels(location.id);
          return {
            locationId: location.id,
            channels: extractCollectionPayload<ChannelDetail>(channelsResponse.data, 'channels'),
          };
        })
      );

      const nextChannelsByLocation: Record<string, ChannelDetail[]> = {};
      for (const result of channelResponses) {
        if (result.status === 'fulfilled') {
          nextChannelsByLocation[result.value.locationId] = result.value.channels;
        }
      }
      setChannelsByLocation(nextChannelsByLocation);

      const socialSettingResponses = await Promise.allSettled(
        locationItems.map(async (location: IntegrationLocation) => {
          const socialSettingsResponse = await socialApi.getSettings(location.id);
          return {
            locationId: location.id,
            settings: socialSettingsResponse.data,
          };
        })
      );

      const nextSocialSettingsByLocation: Record<string, SocialAutomationSettings> = {};
      for (const result of socialSettingResponses) {
        if (result.status === 'fulfilled') {
          nextSocialSettingsByLocation[result.value.locationId] = result.value.settings;
        }
      }
      setSocialSettingsByLocation(nextSocialSettingsByLocation);

      const socialStatsResponses = await Promise.allSettled(
        locationItems.map(async (location: IntegrationLocation) => {
          const socialStatsResponse = await socialApi.getStats(location.id);
          return {
            locationId: location.id,
            stats: socialStatsResponse.data,
          };
        })
      );

      const nextSocialStatsByLocation: Record<string, SocialAutomationStats> = {};
      for (const result of socialStatsResponses) {
        if (result.status === 'fulfilled') {
          nextSocialStatsByLocation[result.value.locationId] = result.value.stats;
        }
      }
      setSocialStatsByLocation(nextSocialStatsByLocation);

      const responderSummaryResponses = await Promise.allSettled(
        locationItems.map(async (location: IntegrationLocation) => {
          const summaryResponse = await reviewResponderApi.getSummary(location.id);
          return {
            locationId: location.id,
            summary: summaryResponse.data,
          };
        })
      );

      const nextReviewResponderSummaryByLocation: Record<string, ReviewResponderSummary> = {};
      for (const result of responderSummaryResponses) {
        if (result.status === 'fulfilled') {
          nextReviewResponderSummaryByLocation[result.value.locationId] = result.value.summary;
        }
      }
      setReviewResponderSummaryByLocation(nextReviewResponderSummaryByLocation);

      const socialProofResponses = await Promise.allSettled(
        locationItems.map(async (location: IntegrationLocation) => {
          const historyResponse = await socialProofHistoryApi.getHistory(location.id, { limit: 1, offset: 0 });
          return {
            locationId: location.id,
            metrics: historyResponse.data?.metrics,
          };
        })
      );

      const nextSocialProofSummaryByLocation: Record<string, SocialProofSummary> = {};
      for (const result of socialProofResponses) {
        if (result.status === 'fulfilled' && result.value.metrics) {
          nextSocialProofSummaryByLocation[result.value.locationId] = result.value.metrics;
        }
      }
      setSocialProofSummaryByLocation(nextSocialProofSummaryByLocation);

      try {
        const notificationHealthResponse = await notificationsApi.getHealthSummary();
        setNotificationHealth(notificationHealthResponse.data);
      } catch {
        setNotificationHealth(null);
      }
    } catch {
      toast.error('Failed to load integration status');
      setLocations([]);
      setChannelsByLocation({});
      setSocialSettingsByLocation({});
      setSocialStatsByLocation({});
      setReviewResponderSummaryByLocation({});
      setSocialProofSummaryByLocation({});
      setNotificationHealth(null);
    } finally {
      setIsLoading(false);
    }
  };

  const loadOnMount = useEffectEvent(async () => {
    await loadData();
  });

  useEffect(() => {
    void loadOnMount();
  }, []);

  const handleInstagramReconnect = async (locationId: string) => {
    setActionKey(`reconnect:${locationId}`);
    try {
      const frontendRedirect = `${window.location.origin}/dashboard/integrations/callback`;
      const callbackUri = `${API_BASE_URL}/oauth/instagram/callback?frontend_redirect=${encodeURIComponent(frontendRedirect)}`;
      const response = await oauthApi.getInstagramAuthorizeUrl(locationId, callbackUri);
      const authorizationUrl = response.data.authorization_url;
      if (!authorizationUrl) {
        throw new Error('Missing authorization URL');
      }
      window.location.href = authorizationUrl;
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to start Instagram reconnect'));
      setActionKey(null);
    }
  };

  const handleRefreshChannel = async (channelId: string) => {
    setActionKey(`refresh:${channelId}`);
    try {
      await oauthApi.refreshChannel(channelId);
      toast.success('Channel token refreshed');
      await loadData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to refresh token'));
    } finally {
      setActionKey(null);
    }
  };

  const handleDisconnectChannel = async (channelId: string) => {
    setActionKey(`disconnect:${channelId}`);
    try {
      await oauthApi.disconnectChannel(channelId);
      toast.success('Channel disconnected');
      await loadData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to disconnect channel'));
    } finally {
      setActionKey(null);
    }
  };

  const handleQASync = async (locationId: string) => {
    setActionKey(`qa-sync:${locationId}`);
    try {
      const response = await qaApi.sync(locationId);
      const synced = response.data?.synced_questions ?? 0;
      const pending = response.data?.pending_count ?? 0;
      toast.success(`Q&A synced: ${synced} questions checked, ${pending} pending.`);
      await loadData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to sync GBP Q&A'));
    } finally {
      setActionKey(null);
    }
  };

  const summary = useMemo(() => {
    let reconnectRequired = 0;
    let refreshNeeded = 0;
    let failedChannels = 0;
    let recentPublishFailures = 0;
    let qaFailures = 0;
    let socialAttention = 0;
    let reviewResponderAttention = 0;
    let socialProofAttention = 0;
    let notificationAttention = 0;

    for (const channels of Object.values(channelsByLocation)) {
      for (const channel of channels) {
        if (channel.reconnect_required) reconnectRequired += 1;
        else if (channel.needs_refresh) refreshNeeded += 1;
        if (channel.last_publish_failed_at) failedChannels += 1;
        recentPublishFailures += channel.recent_publish_failures || 0;
        if ((channel.qa_failed_count || 0) > 0) qaFailures += 1;
      }
    }

    for (const stats of Object.values(socialStatsByLocation)) {
      if (stats.automation_health && stats.automation_health !== 'ready') {
        socialAttention += 1;
      } else if ((stats.failed_responses || 0) > 0) {
        socialAttention += 1;
      }
    }

    for (const summary of Object.values(reviewResponderSummaryByLocation)) {
      if ((summary.pending_count || 0) > 0 || (summary.failed_count || 0) > 0 || (summary.high_priority_pending_count || 0) > 0) {
        reviewResponderAttention += 1;
      }
    }

    for (const summary of Object.values(socialProofSummaryByLocation)) {
      if ((summary.attention_required_count || 0) > 0 || (summary.pending_count || 0) > 0) {
        socialProofAttention += 1;
      }
    }

    if (notificationHealth?.attention_needed) {
      notificationAttention = 1;
    }

    return {
      reconnectRequired,
      refreshNeeded,
      failedChannels,
      recentPublishFailures,
      qaFailures,
      socialAttention,
      reviewResponderAttention,
      socialProofAttention,
      notificationAttention,
    };
  }, [channelsByLocation, notificationHealth, socialStatsByLocation, reviewResponderSummaryByLocation, socialProofSummaryByLocation]);

  const blockingIssueCount =
    summary.reconnectRequired +
    summary.refreshNeeded +
    summary.failedChannels +
    summary.qaFailures +
    summary.socialAttention +
    summary.reviewResponderAttention +
    summary.socialProofAttention +
    summary.notificationAttention;

  const fixFirstMessage: { title: string; detail: string; action: string; tone: 'critical' | 'warning' | 'healthy' } = (() => {
    if (summary.reconnectRequired > 0) {
      return {
        title: `${summary.reconnectRequired} issue${summary.reconnectRequired === 1 ? '' : 's'} blocking publishing`,
        detail: 'Reconnect these channels first. Publishing, sync, and automation retries can keep failing until the connection is restored.',
        action: 'Show blocked locations',
        tone: 'critical',
      };
    }

    if (summary.refreshNeeded > 0 || summary.failedChannels > 0) {
      const count = summary.refreshNeeded + summary.failedChannels;
      return {
        title: `${count} channel issue${count === 1 ? '' : 's'} need a quick fix`,
        detail: 'Refresh tokens or inspect recent failures before launching new posts, Q&A syncs, or automation runs.',
        action: 'Show channels to fix',
        tone: 'warning',
      };
    }

    if (blockingIssueCount > 0) {
      return {
        title: `${blockingIssueCount} workflow item${blockingIssueCount === 1 ? '' : 's'} need attention`,
        detail: 'Operational workflows are mostly connected, but one or more review, social, Q&A, or notification items need follow-up.',
        action: 'Show attention items',
        tone: 'warning',
      };
    }

    return {
      title: 'No integration blockers found',
      detail: 'Connections look healthy. Keep this page as a quick pre-flight check before publishing or running automations.',
      action: 'Review all locations',
      tone: 'healthy',
    };
  })();

  const filteredLocations = useMemo(() => {
    return locations.filter((location) => {
      if (selectedLocationId !== 'all' && location.id !== selectedLocationId) {
        return false;
      }

      if (statusFilter === 'all') {
        return true;
      }

      const channels = channelsByLocation[location.id] || [];
      const reviewSummary = reviewResponderSummaryByLocation[location.id];
      const socialProofSummary = socialProofSummaryByLocation[location.id];
      const socialStats = socialStatsByLocation[location.id];
      const hasChannelAttention = channels.some(
        (channel) =>
          channel.reconnect_required ||
          channel.needs_refresh ||
          !!channel.last_publish_failed_at ||
          (channel.qa_failed_count || 0) > 0
      );
      const hasSocialAttention =
        !!socialStats &&
        ((socialStats.failed_responses || 0) > 0 ||
          (!!socialStats.automation_health && socialStats.automation_health !== 'ready'));
      const hasReviewAttention =
        !!reviewSummary &&
        ((reviewSummary.pending_count || 0) > 0 ||
          (reviewSummary.failed_count || 0) > 0 ||
          (reviewSummary.high_priority_pending_count || 0) > 0);
      const hasSocialProofAttention =
        !!socialProofSummary &&
        ((socialProofSummary.attention_required_count || 0) > 0 || (socialProofSummary.pending_count || 0) > 0);
      const needsAttention = hasChannelAttention || hasSocialAttention || hasReviewAttention || hasSocialProofAttention;
      return statusFilter === 'attention' ? needsAttention : !needsAttention;
    });
  }, [
    channelsByLocation,
    locations,
    reviewResponderSummaryByLocation,
    selectedLocationId,
    socialProofSummaryByLocation,
    socialStatsByLocation,
    statusFilter,
  ]);

  const handleFixFirst = () => {
    setStatusFilter(blockingIssueCount > 0 ? 'attention' : 'all');
    window.setTimeout(() => {
      document.getElementById('integration-details')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 0);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Integrations</h1>
        <p className="text-gray-500">Fix blockers first, then use diagnostics only when you need more detail.</p>
      </div>

      <Card
        className={
          fixFirstMessage.tone === 'critical'
            ? 'border-red-200 bg-red-50'
            : fixFirstMessage.tone === 'warning'
              ? 'border-amber-200 bg-amber-50'
              : 'border-emerald-200 bg-emerald-50'
        }
      >
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            {fixFirstMessage.tone === 'healthy' ? (
              <PlugZap className="mt-1 h-5 w-5 text-emerald-700" />
            ) : (
              <AlertCircle
                className={
                  fixFirstMessage.tone === 'critical'
                    ? 'mt-1 h-5 w-5 text-red-700'
                    : 'mt-1 h-5 w-5 text-amber-700'
                }
              />
            )}
            <div>
              <Badge
                className={
                  fixFirstMessage.tone === 'critical'
                    ? 'mb-2 bg-red-100 text-red-700 hover:bg-red-100'
                    : fixFirstMessage.tone === 'warning'
                      ? 'mb-2 bg-amber-100 text-amber-700 hover:bg-amber-100'
                      : 'mb-2 bg-emerald-100 text-emerald-700 hover:bg-emerald-100'
                }
              >
                Fix First
              </Badge>
              <h2 className="text-xl font-semibold text-slate-950">{fixFirstMessage.title}</h2>
              <p className="mt-1 max-w-2xl text-sm text-slate-700">{fixFirstMessage.detail}</p>
            </div>
          </div>
          <Button onClick={handleFixFirst} className="shrink-0">
            {fixFirstMessage.action}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </CardContent>
      </Card>

      <details className="group rounded-xl border bg-white shadow-sm">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4">
          <div>
            <div className="text-sm font-semibold text-slate-900">Diagnostic counts</div>
            <div className="text-sm text-slate-500">
              Optional detail for operators who need to inspect connection, publishing, review, social, or notification health.
            </div>
          </div>
          <span className="text-xs font-medium text-slate-500 group-open:hidden">Show</span>
          <span className="hidden text-xs font-medium text-slate-500 group-open:inline">Hide</span>
        </summary>
        <div className="space-y-4 px-5 pb-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Card className="border-red-200 bg-red-50">
              <CardContent className="pt-6">
                <div className="text-sm text-red-700">Reconnect Required</div>
                <div className="mt-2 text-3xl font-bold text-red-900">{summary.reconnectRequired}</div>
              </CardContent>
            </Card>
            <Card className="border-amber-200 bg-amber-50">
              <CardContent className="pt-6">
                <div className="text-sm text-amber-700">Refresh Needed</div>
                <div className="mt-2 text-3xl font-bold text-amber-900">{summary.refreshNeeded}</div>
              </CardContent>
            </Card>
            <Card className="border-slate-200 bg-slate-50">
              <CardContent className="pt-6">
                <div className="text-sm text-slate-700">Channels With Recent Failures</div>
                <div className="mt-2 text-3xl font-bold text-slate-900">{summary.failedChannels}</div>
                <div className="mt-1 text-xs text-slate-600">
                  {summary.recentPublishFailures} failed publish attempts recorded
                </div>
              </CardContent>
            </Card>
            <Card className="border-violet-200 bg-violet-50">
              <CardContent className="pt-6">
                <div className="text-sm text-violet-700">GBP Q&A Failures</div>
                <div className="mt-2 text-3xl font-bold text-violet-900">{summary.qaFailures}</div>
              </CardContent>
            </Card>
            <Card className="border-rose-200 bg-rose-50">
              <CardContent className="pt-6">
                <div className="text-sm text-rose-700">Social Attention Needed</div>
                <div className="mt-2 text-3xl font-bold text-rose-900">{summary.socialAttention}</div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Card className="border-sky-200 bg-sky-50">
              <CardContent className="pt-6">
                <div className="text-sm text-sky-700">Review Responder Attention</div>
                <div className="mt-2 text-3xl font-bold text-sky-900">{summary.reviewResponderAttention}</div>
                <div className="mt-1 text-xs text-sky-700">
                  Locations with pending, failed, or high-priority review responses
                </div>
              </CardContent>
            </Card>
            <Card className="border-fuchsia-200 bg-fuchsia-50">
              <CardContent className="pt-6">
                <div className="text-sm text-fuchsia-700">Social Proof Attention</div>
                <div className="mt-2 text-3xl font-bold text-fuchsia-900">{summary.socialProofAttention}</div>
                <div className="mt-1 text-xs text-fuchsia-700">
                  Locations with pending or attention-required social proof cards
                </div>
              </CardContent>
            </Card>
            <Card className="border-cyan-200 bg-cyan-50">
              <CardContent className="pt-6">
                <div className="text-sm text-cyan-700">Notification Attention</div>
                <div className="mt-2 text-3xl font-bold text-cyan-900">{summary.notificationAttention}</div>
                <div className="mt-1 text-xs text-cyan-700">
                  Account-level push setup, saved devices, and recent delivery failures
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </details>

      {notificationHealth ? (
        <details className="group rounded-xl border bg-white shadow-sm">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-cyan-600" />
              <div>
                <div className="text-sm font-semibold text-slate-900">Notification delivery details</div>
                <div className="text-sm text-slate-500">Push readiness and recent delivery behavior.</div>
              </div>
            </div>
            <span className="text-xs font-medium text-slate-500 group-open:hidden">Show</span>
            <span className="hidden text-xs font-medium text-slate-500 group-open:inline">Hide</span>
          </summary>
        <Card className="mx-4 mb-4 shadow-none">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Bell className="h-5 w-5 text-cyan-600" />
              Notification Subscription Health
            </CardTitle>
            <CardDescription>Account-level push readiness and recent delivery behavior.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 text-sm md:grid-cols-3">
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
                <div className="text-gray-500">Delivered in last {notificationHealth.window_days} days</div>
                <div className="font-medium">{notificationHealth.recent_delivered_count}</div>
              </div>
              <div>
                <div className="text-gray-500">Failed in last {notificationHealth.window_days} days</div>
                <div className={notificationHealth.recent_failed_count > 0 ? 'font-medium text-rose-700' : 'font-medium'}>
                  {notificationHealth.recent_failed_count}
                </div>
              </div>
              <div>
                <div className="text-gray-500">Unavailable attempts</div>
                <div className={notificationHealth.recent_unavailable_count > 0 ? 'font-medium text-amber-700' : 'font-medium'}>
                  {notificationHealth.recent_unavailable_count}
                </div>
              </div>
            </div>
            <div className="rounded-lg border bg-slate-50 p-4 text-sm text-slate-700">
              <div className="font-medium">Last delivery attempt</div>
              <div className="mt-1">
                {notificationHealth.last_delivery_attempt_at
                  ? `${formatDateTime(notificationHealth.last_delivery_attempt_at)} via ${notificationHealth.last_delivery_channel || 'unknown'} (${notificationHealth.last_delivery_status || 'unknown'})`
                  : 'No notification delivery attempts recorded yet.'}
              </div>
              {notificationHealth.last_delivery_failure_reason ? (
                <div className="mt-2 text-rose-700">{notificationHealth.last_delivery_failure_reason}</div>
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
                  'Notifications need attention before push delivery can be considered reliable.'
                : 'Notification subscriptions and recent deliveries look healthy.'}
            </div>
            <Link href="/dashboard/notifications">
              <Button variant="outline" size="sm">
                {notificationHealth.attention_needed ? 'Fix Notifications' : 'Open Notifications'}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
        </details>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Filters</CardTitle>
          <CardDescription>Narrow the integrations view by location or health state.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          <select
            className="h-10 rounded-md border bg-white px-3 text-sm"
            value={selectedLocationId}
            onChange={(e) => setSelectedLocationId(e.target.value)}
          >
            <option value="all">All locations</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
          <select
            className="h-10 rounded-md border bg-white px-3 text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | 'attention' | 'stable')}
          >
            <option value="all">All statuses</option>
            <option value="attention">Needs attention</option>
            <option value="stable">Stable only</option>
          </select>
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2].map((i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="mb-3 h-6 w-48" />
                <Skeleton className="mb-2 h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : locations.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No locations found</CardTitle>
            <CardDescription>Add a location before connecting channels.</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/onboarding">
              <Button>Add your first location</Button>
            </Link>
          </CardContent>
        </Card>
      ) : filteredLocations.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-gray-500">
            No locations match the current integration filters.
          </CardContent>
        </Card>
      ) : (
        <div id="integration-details" className="grid gap-4">
          {filteredLocations.map((location) => {
            const channels = channelsByLocation[location.id] || [];
            const socialSettings = socialSettingsByLocation[location.id];

            return (
              <Card key={location.id}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle className="text-lg">{location.name}</CardTitle>
                      <CardDescription>Operational channel status for this location.</CardDescription>
                    </div>
                    <Link href={`/dashboard?location=${location.id}`}>
                      <Button variant="outline">
                        Open dashboard
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Button>
                    </Link>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {socialSettings && (
                    <div className="rounded-lg border bg-slate-50 p-4">
                      <div className="mb-2 text-sm font-medium text-slate-900">Social automation health</div>
                      <div className="grid gap-3 text-sm md:grid-cols-2">
                        <div>
                          <div className="text-gray-500">Automation</div>
                          <div>{socialSettings.auto_respond_enabled ? 'Enabled' : 'Disabled'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Response delay</div>
                          <div>{socialSettings.response_delay_seconds}s</div>
                        </div>
                        <div>
                          <div className="text-gray-500">DMs</div>
                          <div>{socialSettings.auto_respond_dms ? 'On' : 'Off'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Comments</div>
                          <div>{socialSettings.auto_respond_comments ? 'On' : 'Off'}</div>
                        </div>
                        <div className="md:col-span-2">
                          <div className="text-gray-500">Excluded keywords</div>
                          <div>{socialSettings.excluded_keywords?.length ? socialSettings.excluded_keywords.join(', ') : 'None'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">High-priority alerts</div>
                          <div>{socialSettings.high_priority_alerts_enabled ? 'Enabled' : 'Disabled'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Alert channel</div>
                          <div>{socialSettings.high_priority_alert_channel || 'preferred'}</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {socialStatsByLocation[location.id] && (
                    <div className="rounded-lg border bg-white p-4">
                      <div className="mb-2 text-sm font-medium text-slate-900">Social response summary</div>
                      <div className="grid gap-3 text-sm md:grid-cols-2">
                        <div>
                          <div className="text-gray-500">Automation health</div>
                          <div className="font-medium capitalize">
                            {socialStatsByLocation[location.id].automation_health || 'unknown'}
                          </div>
                        </div>
                        <div>
                          <div className="text-gray-500">Failed responses</div>
                          <div className="font-medium text-rose-700">
                            {socialStatsByLocation[location.id].failed_responses || 0}
                          </div>
                        </div>
                        <div>
                          <div className="text-gray-500">Last successful response</div>
                          <div className="font-medium">
                            {formatDateTime(socialStatsByLocation[location.id].last_successful_response_at)}
                          </div>
                        </div>
                        <div>
                          <div className="text-gray-500">Last failed response</div>
                          <div className="font-medium">
                            {formatDateTime(socialStatsByLocation[location.id].last_failed_response_at)}
                          </div>
                        </div>
                      </div>
                      {socialStatsByLocation[location.id].automation_health_reason && (
                        <div className="mt-3 text-xs text-gray-500">
                          {socialStatsByLocation[location.id].automation_health_reason}
                        </div>
                      )}
                    </div>
                  )}

                  {reviewResponderSummaryByLocation[location.id] && (
                    <div className="rounded-lg border bg-sky-50 p-4">
                      <div className="mb-2 text-sm font-medium text-sky-900">Review responder health</div>
                      <div className="grid gap-3 text-sm md:grid-cols-2">
                        <div>
                          <div className="text-sky-700/80">Pending drafts</div>
                          <div>{reviewResponderSummaryByLocation[location.id].pending_count || 0}</div>
                        </div>
                        <div>
                          <div className="text-sky-700/80">High priority pending</div>
                          <div className={(reviewResponderSummaryByLocation[location.id].high_priority_pending_count || 0) > 0 ? 'text-amber-700' : ''}>
                            {reviewResponderSummaryByLocation[location.id].high_priority_pending_count || 0}
                          </div>
                        </div>
                        <div>
                          <div className="text-sky-700/80">Failed responses</div>
                          <div className={(reviewResponderSummaryByLocation[location.id].failed_count || 0) > 0 ? 'text-red-600' : ''}>
                            {reviewResponderSummaryByLocation[location.id].failed_count || 0}
                          </div>
                        </div>
                        <div>
                          <div className="text-sky-700/80">Last activity</div>
                          <div>{formatDateTime(reviewResponderSummaryByLocation[location.id].last_activity_at)}</div>
                        </div>
                        {reviewResponderSummaryByLocation[location.id].last_bulk_retry_at && (
                          <div className="md:col-span-2">
                            <div className="text-sky-700/80">Last bulk retry</div>
                            <div>
                              {formatDateTime(reviewResponderSummaryByLocation[location.id].last_bulk_retry_at)}{' '}
                              &mdash;{' '}
                              <span className="text-green-700">
                                {reviewResponderSummaryByLocation[location.id].last_bulk_retry_succeeded ?? 0} succeeded
                              </span>
                              {', '}
                              <span className={(reviewResponderSummaryByLocation[location.id].last_bulk_retry_still_failed ?? 0) > 0 ? 'text-red-600' : ''}>
                                {reviewResponderSummaryByLocation[location.id].last_bulk_retry_still_failed ?? 0} still failed
                              </span>
                              {' of '}
                              {reviewResponderSummaryByLocation[location.id].last_bulk_retry_total ?? 0}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {socialProofSummaryByLocation[location.id] && (
                    <div className="rounded-lg border bg-fuchsia-50 p-4">
                      <div className="mb-2 text-sm font-medium text-fuchsia-900">Social proof health</div>
                      <div className="grid gap-3 text-sm md:grid-cols-2">
                        <div>
                          <div className="text-fuchsia-700/80">Pending cards</div>
                          <div>{socialProofSummaryByLocation[location.id].pending_count || 0}</div>
                        </div>
                        <div>
                          <div className="text-fuchsia-700/80">Attention required</div>
                          <div className={(socialProofSummaryByLocation[location.id].attention_required_count || 0) > 0 ? 'text-rose-600' : ''}>
                            {socialProofSummaryByLocation[location.id].attention_required_count || 0}
                          </div>
                        </div>
                        <div>
                          <div className="text-fuchsia-700/80">Approval rate</div>
                          <div>{Math.round(socialProofSummaryByLocation[location.id].approval_rate)}%</div>
                        </div>
                        <div>
                          <div className="text-fuchsia-700/80">Publish rate</div>
                          <div>{Math.round(socialProofSummaryByLocation[location.id].publish_rate)}%</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {channels.length === 0 ? (
                    <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
                      No channels connected yet.
                    </div>
                  ) : (
                    channels.map((channel) => (
                      <div key={channel.id} className="rounded-lg border p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="font-medium">{channel.type}</div>
                            <div className="text-sm text-gray-500">
                              {channel.platform_account_name || channel.platform_account_id || 'No account linked'}
                            </div>
                          </div>
                          <Badge className={channelBadgeClass(
                            channel.reconnect_required
                              ? 'reconnect required'
                              : channel.needs_refresh
                                ? 'token refresh needed'
                                : channel.status,
                            !channel.reconnect_required && !channel.needs_refresh && channel.status === 'connected'
                          )}>
                            {channel.reconnect_required
                              ? 'reconnect required'
                              : channel.needs_refresh
                                ? 'token refresh needed'
                                : channel.status}
                          </Badge>
                        </div>

                        <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
                          <div>
                            <div className="text-gray-500">Token expires</div>
                            <div>{formatDateTime(channel.access_token_expires_at)}</div>
                          </div>
                          <div>
                            <div className="text-gray-500">Last successful publish</div>
                            <div>{formatDateTime(channel.last_publish_succeeded_at)}</div>
                          </div>
                          <div>
                            <div className="text-gray-500">Recent publish failure</div>
                            <div>{formatDateTime(channel.last_publish_failed_at)}</div>
                          </div>
                          <div>
                            <div className="text-gray-500">Failure detail</div>
                            <div className={channel.last_publish_failed_error ? 'text-red-600' : ''}>
                              {channel.last_publish_failed_error || channel.error_message || 'None'}
                            </div>
                          </div>
                          <div>
                            <div className="text-gray-500">Recent publish failures</div>
                            <div>{channel.recent_publish_failures || 0}</div>
                          </div>
                          <div>
                            <div className="text-gray-500">Recent publish successes</div>
                            <div>{channel.recent_publish_successes || 0}</div>
                          </div>
                        </div>

                        {channel.type === 'GBP' && (
                          <div className="mt-4 rounded-lg border bg-violet-50 p-4">
                            <div className="mb-2 text-sm font-medium text-violet-900">Q&A draft health</div>
                            <div className="grid gap-3 text-sm md:grid-cols-2">
                              <div>
                                <div className="text-violet-700/80">Pending drafts</div>
                                <div>{channel.qa_pending_count || 0}</div>
                              </div>
                              <div>
                                <div className="text-violet-700/80">Failed drafts</div>
                                <div className={(channel.qa_failed_count || 0) > 0 ? 'text-red-600' : ''}>
                                  {channel.qa_failed_count || 0}
                                </div>
                              </div>
                              <div>
                                <div className="text-violet-700/80">Posted answers</div>
                                <div>{channel.qa_posted_count || 0}</div>
                              </div>
                              <div>
                                <div className="text-violet-700/80">Last posted answer</div>
                                <div>{formatDateTime(channel.qa_last_posted_at)}</div>
                              </div>
                              <div className="md:col-span-2">
                                <div className="text-violet-700/80">Last failed draft update</div>
                                <div>{formatDateTime(channel.qa_last_failed_at)}</div>
                              </div>
                              <div>
                                <div className="text-violet-700/80">Last Q&A sync</div>
                                <div>{formatDateTime(channel.qa_last_sync_at)}</div>
                              </div>
                              <div>
                                <div className="text-violet-700/80">Questions seen in last sync</div>
                                <div>{channel.qa_last_sync_question_count || 0}</div>
                              </div>
                              <div>
                                <div className="text-violet-700/80">Drafts rated good</div>
                                <div>{channel.qa_feedback_good_count || 0}</div>
                              </div>
                              <div>
                                <div className="text-violet-700/80">Need edits</div>
                                <div className={(channel.qa_feedback_needs_edit_count || 0) > 0 ? 'text-amber-700' : ''}>
                                  {channel.qa_feedback_needs_edit_count || 0}
                                </div>
                              </div>
                              <div>
                                <div className="text-violet-700/80">Marked wrong</div>
                                <div className={(channel.qa_feedback_wrong_count || 0) > 0 ? 'text-red-600' : ''}>
                                  {channel.qa_feedback_wrong_count || 0}
                                </div>
                              </div>
                              <div className="md:col-span-2">
                                <div className="text-violet-700/80">Last Q&A sync error</div>
                                <div className={channel.qa_last_sync_error ? 'text-red-600' : ''}>
                                  {channel.qa_last_sync_error || 'None'}
                                </div>
                              </div>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {channel.status === 'connected' ? (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleQASync(location.id)}
                                  disabled={actionKey === `qa-sync:${location.id}`}
                                >
                                  {actionKey === `qa-sync:${location.id}` ? (
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                  ) : (
                                    <RefreshCw className="mr-2 h-4 w-4" />
                                  )}
                                  Sync Q&A now
                                </Button>
                              ) : (
                                <div className="inline-flex items-center rounded-md border border-dashed border-violet-200 bg-white px-3 py-2 text-xs text-violet-700">
                                  Reconnect GBP before running a manual Q&amp;A sync.
                                </div>
                              )}
                              <Link href={`/dashboard/qa`}>
                                <Button variant="ghost" size="sm">
                                  Open Q&amp;A
                                  <ArrowRight className="ml-2 h-4 w-4" />
                                </Button>
                              </Link>
                            </div>
                          </div>
                        )}

                        {channel.type === 'INSTAGRAM' && (
                          <div className="mt-4 flex flex-wrap gap-2">
                            <Button
                              onClick={() => handleInstagramReconnect(location.id)}
                              disabled={actionKey === `reconnect:${location.id}`}
                            >
                              {actionKey === `reconnect:${location.id}` ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              ) : (
                                <PlugZap className="mr-2 h-4 w-4" />
                              )}
                              {channel.reconnect_required
                                ? 'Reconnect Instagram'
                                : channel.status === 'connected'
                                  ? 'Re-authorize Instagram'
                                  : 'Connect Instagram'}
                            </Button>
                            {channel.reconnect_required ? (
                              <div className="inline-flex items-center rounded-md border border-dashed border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                                Refresh token becomes available after Instagram reconnects.
                              </div>
                            ) : (
                              <Button
                                variant="outline"
                                onClick={() => handleRefreshChannel(channel.id)}
                                disabled={actionKey === `refresh:${channel.id}`}
                              >
                                {actionKey === `refresh:${channel.id}` ? (
                                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                ) : (
                                  <RefreshCw className="mr-2 h-4 w-4" />
                                )}
                                Refresh token
                              </Button>
                            )}
                            <Button
                              variant="outline"
                              onClick={() => handleDisconnectChannel(channel.id)}
                              disabled={actionKey === `disconnect:${channel.id}`}
                            >
                              {actionKey === `disconnect:${channel.id}` ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              ) : (
                                <Unplug className="mr-2 h-4 w-4" />
                              )}
                              Disconnect
                            </Button>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
