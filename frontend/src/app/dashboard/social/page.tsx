'use client';

import Link from 'next/link';
import { useEffect, useEffectEvent, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Download,
  Instagram,
  Loader2,
  MessageCircle,
  MessageSquare,
  Send,
  Settings,
  Sparkles,
  TrendingUp,
  User,
  Zap,
} from 'lucide-react';

import { extractCollectionPayload, locationsApi, socialApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';

interface LocationOption {
  id: string;
  name: string;
}

interface SocialMessage {
  id: string;
  platform: string;
  type: string;
  sender_id: string;
  sender_name: string;
  message: string;
  created_at: string;
  post_id?: string;
  sentiment?: string;
  triage_priority?: string;
  triage_reason?: string;
  suggested_response?: string;
}

interface SocialStats {
  total_messages: number;
  auto_responded: number;
  manual_responses: number;
  failed_responses: number;
  response_rate: number;
  avg_response_time_minutes: number;
  sentiment_positive: number;
  sentiment_neutral: number;
  sentiment_negative: number;
  last_successful_response_at?: string | null;
  last_failed_response_at?: string | null;
  automation_health?: string;
  automation_health_reason?: string | null;
}

interface SocialHistoryItem {
  id: string;
  response_mode: string;
  message_type: string;
  sender_name?: string;
  source_message?: string;
  response_text: string;
  success: boolean;
  sentiment?: string;
  responded_at?: string;
}

interface SocialHistoryResponse {
  items: SocialHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

interface SocialSettings {
  auto_respond_enabled: boolean;
  auto_respond_dms: boolean;
  auto_respond_comments: boolean;
  response_delay_seconds: number;
  excluded_keywords: string[];
  high_priority_alerts_enabled: boolean;
  high_priority_alert_channel: string;
}

export default function SocialPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [locationId, setLocationId] = useState<string>('');
  const [messages, setMessages] = useState<SocialMessage[]>([]);
  const [stats, setStats] = useState<SocialStats | null>(null);
  const [history, setHistory] = useState<SocialHistoryItem[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyLimit] = useState(10);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [settings, setSettings] = useState<SocialSettings | null>(null);
  const [excludedKeywordsInput, setExcludedKeywordsInput] = useState('');
  const [historyModeFilter, setHistoryModeFilter] = useState('all');
  const [historySuccessFilter, setHistorySuccessFilter] = useState('all');
  const [historySentimentFilter, setHistorySentimentFilter] = useState('all');
  const [historySearch, setHistorySearch] = useState('');
  const [selectedMessage, setSelectedMessage] = useState<SocialMessage | null>(null);
  const [isResponseDialogOpen, setIsResponseDialogOpen] = useState(false);
  const [responseText, setResponseText] = useState('');
  const [isGeneratingSuggestion, setIsGeneratingSuggestion] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const hasLocations = locations.length > 0;

  const formatDateTime = (value?: string | null) => {
    if (!value) return 'None';
    return new Date(value).toLocaleString();
  };

  const loadLocations = async () => {
    try {
      const response = await locationsApi.list();
      const items = extractCollectionPayload<LocationOption>(response.data, 'locations');
      setLocations(items);
      if (items.length > 0) {
        setLocationId(items[0].id);
      } else {
        setStatusMessage('Add a location first to use Advanced Response Automation.');
      }
    } catch {
      toast.error('Failed to load locations');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchHistory = async (
    targetLocationId: string,
    options?: { mode?: string; success?: string; sentiment?: string; search?: string }
  ) => {
    const response = await socialApi.getHistory(targetLocationId, {
      limit: historyLimit,
      offset: historyOffset,
      mode: options?.mode && options.mode !== 'all' ? options.mode : undefined,
      success:
        options?.success === 'all' || !options?.success
          ? undefined
          : options.success === 'success',
      sentiment: options?.sentiment && options.sentiment !== 'all' ? options.sentiment : undefined,
      search: options?.search?.trim() || undefined,
    });
    const payload = response.data as SocialHistoryResponse;
    setHistory(Array.isArray(payload.items) ? payload.items : []);
    setHistoryTotal(payload.total || 0);
  };

  const fetchLocationSocialData = async (targetLocationId: string) => {
    if (!targetLocationId) return;

    try {
      const [messagesResponse, statsResponse, settingsResponse] = await Promise.all([
        socialApi.getMessages(targetLocationId),
        socialApi.getStats(targetLocationId),
        socialApi.getSettings(targetLocationId),
      ]);

      const nextMessages = Array.isArray(messagesResponse.data.messages) ? messagesResponse.data.messages : [];
      setMessages(nextMessages);
      setStats(statsResponse.data);
      setSettings(settingsResponse.data);
      setExcludedKeywordsInput((settingsResponse.data.excluded_keywords || []).join(', '));
      await fetchHistory(targetLocationId, {
        mode: historyModeFilter,
        success: historySuccessFilter,
        sentiment: historySentimentFilter,
        search: historySearch,
      });
      setStatusMessage(
        'Advanced Response Automation is in beta. Inbox review does not auto-generate AI replies. Generate suggestions on demand before sending, especially if Instagram is not fully connected.'
      );
    } catch {
      setMessages([]);
      setStats(null);
      setHistory([]);
      setSettings(null);
      setStatusMessage('Advanced Response Automation is unavailable for this location until Instagram is connected. Open Integrations to reconnect and try again.');
      toast.error('Failed to load response automation data');
    }
  };

  const loadLocationsOnMount = useEffectEvent(async () => {
    await loadLocations();
  });

  const loadLocationSocialData = useEffectEvent(async (targetLocationId: string) => {
    await fetchLocationSocialData(targetLocationId);
  });

  const loadHistory = useEffectEvent(async (targetLocationId: string) => {
    await fetchHistory(targetLocationId, {
      mode: historyModeFilter,
      success: historySuccessFilter,
      sentiment: historySentimentFilter,
      search: historySearch,
    });
  });

  useEffect(() => {
    void loadLocationsOnMount();
  }, []);

  useEffect(() => {
    void loadLocationSocialData(locationId);
  }, [locationId]);

  useEffect(() => {
    if (!locationId) return;
    void loadHistory(locationId);
  }, [locationId, historyModeFilter, historySuccessFilter, historySentimentFilter, historySearch, historyOffset, historyLimit]);

  useEffect(() => {
    setHistoryOffset(0);
  }, [locationId, historyModeFilter, historySuccessFilter, historySentimentFilter, historySearch]);

  const handleSendResponse = async () => {
    if (!responseText.trim()) {
      toast.error('Please enter a response');
      return;
    }
    if (!locationId || !selectedMessage) return;

    setIsSubmitting(true);
    try {
      await socialApi.respond(locationId, {
        message_id: selectedMessage.id,
        response_text: responseText,
        sender_id: selectedMessage.sender_id,
        sender_name: selectedMessage.sender_name,
        message_text: selectedMessage.message,
        message_type: selectedMessage.type,
        platform: selectedMessage.platform,
        post_id: selectedMessage.post_id,
        message_created_at: selectedMessage.created_at,
      });
      setMessages((prev) => prev.filter((message) => message.id !== selectedMessage.id));
      setIsResponseDialogOpen(false);
      setSelectedMessage(null);
      setResponseText('');
      toast.success('Response sent');
      await fetchLocationSocialData(locationId);
    } catch {
      toast.error('Failed to send response');
    } finally {
      setIsSubmitting(false);
    }
  };

  const applySuggestedResponse = (messageId: string, suggestedResponse: string) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId ? { ...message, suggested_response: suggestedResponse } : message
      )
    );
    setSelectedMessage((prev) =>
      prev && prev.id === messageId ? { ...prev, suggested_response: suggestedResponse } : prev
    );
  };

  const handleGenerateSuggestion = async () => {
    if (!locationId || !selectedMessage) return;

    setIsGeneratingSuggestion(true);
    try {
      const response = await socialApi.generateResponse(locationId, selectedMessage.message, selectedMessage.type);
      const suggestedResponse = response.data?.suggested_response || '';
      setResponseText(suggestedResponse);
      applySuggestedResponse(selectedMessage.id, suggestedResponse);
      toast.success('AI suggestion generated');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to generate AI suggestion'));
    } finally {
      setIsGeneratingSuggestion(false);
    }
  };

  const handleAutoRespondAll = async () => {
    if (!locationId) return;

    setIsSubmitting(true);
    try {
      const response = await socialApi.autoRespondAll(locationId);
      toast.success(
        `Processed ${response.data.success_count} messages, skipped ${response.data.skipped_count || 0}`
      );
      await fetchLocationSocialData(locationId);
    } catch {
      toast.error('Failed to auto-respond');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveSettings = async () => {
    if (!locationId || !settings) return;

    setIsSubmitting(true);
    try {
      const payload = {
        ...settings,
        excluded_keywords: excludedKeywordsInput
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      };
      const response = await socialApi.updateSettings(locationId, payload);
      setSettings(response.data);
      setExcludedKeywordsInput((response.data.excluded_keywords || []).join(', '));
      toast.success('Automation settings saved');
    } catch {
      toast.error('Failed to save automation settings');
    } finally {
      setIsSubmitting(false);
    }
  };

  const tabCounts = useMemo(() => ({
    all: messages.length,
    dm: messages.filter((message) => message.type === 'dm').length,
    comment: messages.filter((message) => message.type === 'comment').length,
  }), [messages]);
  const highPriorityMessages = useMemo(
    () => messages.filter((message) => message.triage_priority === 'high'),
    [messages]
  );
  const automationHealthLabel = useMemo(() => {
    if (!stats?.automation_health) return 'Unknown';
    return stats.automation_health
      .split('_')
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }, [stats?.automation_health]);

  const filteredMessages = (tab: string) => messages.filter((message) => tab === 'all' || message.type === tab);

  const handleExportHistory = async () => {
    if (!locationId) return;
    try {
      const response = await socialApi.exportHistory(locationId, {
        mode: historyModeFilter !== 'all' ? historyModeFilter : undefined,
        success:
          historySuccessFilter === 'all'
            ? undefined
            : historySuccessFilter === 'success',
        sentiment: historySentimentFilter !== 'all' ? historySentimentFilter : undefined,
        search: historySearch.trim() || undefined,
      });
      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `social-history-${locationId}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('History export started');
    } catch {
      toast.error('Failed to export social history');
    }
  };

  const getTypeIcon = (type: string) => {
    if (type === 'comment') return <MessageSquare className="h-4 w-4" />;
    return <MessageCircle className="h-4 w-4" />;
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="mb-2 h-8 w-16" />
                <Skeleton className="h-4 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (!hasLocations) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Advanced Response Automation</h1>
          <p className="text-gray-500">Beta workflow for Instagram DMs and comment replies.</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>No location available</CardTitle>
            <CardDescription>
              Add a live business location before using social response automation, history exports, or per-location settings.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3">
            <Button asChild>
              <Link href="/dashboard/locations">Open Locations</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/dashboard/integrations">Check Integrations</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div>
          <h1 className="text-2xl font-bold">Advanced Response Automation</h1>
          <p className="text-gray-500">Beta workflow for Instagram DMs and comment replies.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            className="h-10 min-w-[220px] rounded-md border bg-white px-3 text-sm"
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
          >
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
          <Button variant="outline" asChild>
            <a href="/dashboard/integrations">
              <Settings className="mr-2 h-4 w-4" />
              Check Integrations
            </a>
          </Button>
          {messages.length > 0 ? (
            <Button
              onClick={handleAutoRespondAll}
              disabled={isSubmitting}
              className="bg-gradient-to-r from-pink-500 to-purple-600"
            >
              {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Zap className="mr-2 h-4 w-4" />}
              Auto-Respond All
            </Button>
          ) : (
            <div className="flex items-center rounded-md border border-dashed px-3 py-2 text-sm text-gray-500">
              No pending messages are ready for bulk auto-response right now.
            </div>
          )}
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Social Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {highPriorityMessages.length > 0
                ? 'Handle high-priority messages manually'
                : messages.length > 0
                  ? 'Review pending messages before automation'
                  : 'Keep social response settings ready'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Pending messages are the main workspace. History and automation settings are secondary maintenance areas.
            </p>
          </div>
          <Badge className="w-fit bg-white/10 text-white hover:bg-white/10">
            {messages.length} pending
          </Badge>
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

      {highPriorityMessages.length > 0 && (
        <Card className="border-rose-200 bg-rose-50">
          <CardContent className="flex items-start gap-3 pt-6">
            <AlertCircle className="mt-0.5 h-5 w-5 text-rose-600" />
            <div className="text-sm text-rose-900">
              <div className="font-medium">High-priority messages need manual review</div>
              <div className="mt-1">
                {highPriorityMessages.length} message(s) are flagged as high priority based on sentiment or public visibility.
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {stats && (
        <Card className="border-slate-200 bg-slate-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-slate-700" />
              Operational Summary
            </CardTitle>
            <CardDescription>Real response signals from the last 7 days.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-lg border bg-white p-4">
                <div className="text-sm text-gray-500">Automation health</div>
                <div className="mt-1 flex items-center gap-2 text-lg font-semibold">
                  <Badge
                    className={
                      stats.automation_health === 'ready'
                        ? 'bg-green-100 text-green-700'
                        : stats.automation_health === 'partial'
                          ? 'bg-amber-100 text-amber-700'
                          : stats.automation_health === 'disconnected'
                            ? 'bg-rose-100 text-rose-700'
                            : 'bg-slate-100 text-slate-700'
                    }
                  >
                    {automationHealthLabel}
                  </Badge>
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  {stats.automation_health_reason || 'No additional details available.'}
                </div>
              </div>
              <div className="rounded-lg border bg-white p-4">
                <div className="text-sm text-gray-500">High-priority pending</div>
                <div className="mt-1 text-3xl font-bold text-rose-700">{highPriorityMessages.length}</div>
                <div className="mt-2 text-xs text-gray-500">Needs manual review before auto-reply.</div>
              </div>
              <div className="rounded-lg border bg-white p-4">
                <div className="text-sm text-gray-500">Failed responses</div>
                <div className="mt-1 text-3xl font-bold text-rose-700">{stats.failed_responses}</div>
                <div className="mt-2 text-xs text-gray-500">Stored in the audit log.</div>
              </div>
              <div className="rounded-lg border bg-white p-4">
                <div className="text-sm text-gray-500">Last successful response</div>
                <div className="mt-1 text-sm font-medium text-gray-900">
                  {formatDateTime(stats.last_successful_response_at)}
                </div>
              </div>
              <div className="rounded-lg border bg-white p-4">
                <div className="text-sm text-gray-500">Last failed response</div>
                <div className="mt-1 text-sm font-medium text-gray-900">
                  {formatDateTime(stats.last_failed_response_at)}
                </div>
              </div>
              <div className="rounded-lg border bg-white p-4">
                <div className="text-sm text-gray-500">Settings</div>
                <div className="mt-1 text-sm font-medium text-gray-900">
                  {settings?.auto_respond_enabled ? 'Automation on' : 'Automation paused'}
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  {settings?.auto_respond_dms ? 'DMs on' : 'DMs off'} 쨌 {settings?.auto_respond_comments ? 'Comments on' : 'Comments off'}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-7">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2">
                <MessageCircle className="h-5 w-5 text-pink-500" />
                <span className="text-3xl font-bold">{stats.total_messages}</span>
              </div>
              <p className="mt-1 text-sm text-gray-500">Total Messages</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                <span className="text-3xl font-bold text-green-600">{stats.auto_responded}</span>
              </div>
              <p className="mt-1 text-sm text-gray-500">Auto-Responded</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2">
                <Send className="h-5 w-5 text-slate-500" />
                <span className="text-3xl font-bold text-slate-700">{stats.manual_responses}</span>
              </div>
              <p className="mt-1 text-sm text-gray-500">Manual Responses</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-blue-500" />
                <span className="text-3xl font-bold text-blue-600">{stats.response_rate}%</span>
              </div>
              <p className="mt-1 text-sm text-gray-500">Response Rate</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-purple-500" />
                <span className="text-3xl font-bold text-purple-600">{stats.avg_response_time_minutes}m</span>
              </div>
              <p className="mt-1 text-sm text-gray-500">Avg Response Time</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-green-600">{stats.sentiment_positive}</div>
              <p className="mt-1 text-sm text-gray-500">Positive</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-amber-600">{stats.sentiment_neutral}</div>
              <p className="mt-1 text-sm text-gray-500">Neutral</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-rose-600">{stats.sentiment_negative}</div>
              <p className="mt-1 text-sm text-gray-500">Negative</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-rose-700">{highPriorityMessages.length}</div>
              <p className="mt-1 text-sm text-gray-500">High Priority</p>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Instagram className="h-5 w-5 text-pink-500" />
            Pending Messages
          </CardTitle>
          <CardDescription>Review pending messages first, then generate AI suggestions only when you are ready to reply.</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="all">
            <TabsList>
              <TabsTrigger value="all">All ({tabCounts.all})</TabsTrigger>
              <TabsTrigger value="dm">DMs ({tabCounts.dm})</TabsTrigger>
              <TabsTrigger value="comment">Comments ({tabCounts.comment})</TabsTrigger>
            </TabsList>

            {['all', 'dm', 'comment'].map((tab) => (
              <TabsContent key={tab} value={tab} className="mt-4 space-y-4">
                {filteredMessages(tab).length > 0 ? (
                  filteredMessages(tab).map((message) => (
                    <div key={message.id} className="rounded-lg border p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                      <div className="mb-2 flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-pink-400 to-purple-500 text-white">
                              <User className="h-5 w-5" />
                            </div>
                            <div>
                              <p className="font-semibold">@{message.sender_name}</p>
                              <div className="flex items-center gap-2 text-sm text-gray-500">
                                {getTypeIcon(message.type)}
                                <span>{message.type === 'dm' ? 'Direct Message' : 'Comment'}</span>
                                <span>&bull;</span>
                                <span>{new Date(message.created_at).toLocaleTimeString()}</span>
                              </div>
                            </div>
                          </div>

                          <div className="mb-2 flex flex-wrap gap-2">
                            <Badge
                              className={
                                message.triage_priority === 'high'
                                  ? 'bg-rose-100 text-rose-700'
                                  : message.triage_priority === 'medium'
                                    ? 'bg-amber-100 text-amber-700'
                                    : message.triage_priority === 'low'
                                      ? 'bg-slate-100 text-slate-700'
                                      : 'bg-blue-100 text-blue-700'
                              }
                            >
                              {message.triage_priority || 'normal'} priority
                            </Badge>
                            {message.sentiment && (
                              <Badge variant="outline">{message.sentiment}</Badge>
                            )}
                            {message.triage_reason && (
                              <Badge variant="secondary">{message.triage_reason}</Badge>
                            )}
                          </div>

                          <p className="mb-3 text-gray-800">{message.message}</p>

                          {message.suggested_response && (
                            <div className="rounded-lg border-l-2 border-purple-500 bg-purple-50 p-3">
                              <div className="mb-1 flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-purple-600" />
                                <p className="text-sm font-medium text-purple-700">Suggested Response</p>
                              </div>
                              <p className="text-sm text-gray-700">{message.suggested_response}</p>
                            </div>
                          )}
                        </div>

                        <div className="flex flex-col gap-2">
                          <Badge className={message.type === 'dm' ? 'bg-blue-100 text-blue-700' : 'bg-pink-100 text-pink-700'}>
                            {message.type === 'dm' ? 'DM' : 'Comment'}
                          </Badge>
                          <Button
                            size="sm"
                            onClick={() => {
                              setSelectedMessage(message);
                              setResponseText(message.suggested_response || '');
                              setIsResponseDialogOpen(true);
                            }}
                          >
                            <Send className="mr-1 h-4 w-4" />
                            Reply
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="py-8 text-center text-gray-500">
                    <CheckCircle className="mx-auto mb-2 h-12 w-12 text-green-300" />
                    <p>No pending messages in this filter.</p>
                  </div>
                )}
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle>Response History</CardTitle>
                <CardDescription>Recent manual and auto responses stored as audit history.</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={handleExportHistory}>
                <Download className="mr-2 h-4 w-4" />
                Export CSV
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 md:grid-cols-4">
              <select
                className="h-10 rounded-md border bg-white px-3 text-sm"
                value={historyModeFilter}
                onChange={(e) => setHistoryModeFilter(e.target.value)}
              >
                <option value="all">All modes</option>
                <option value="manual">Manual</option>
                <option value="auto">Auto</option>
              </select>
              <select
                className="h-10 rounded-md border bg-white px-3 text-sm"
                value={historySuccessFilter}
                onChange={(e) => setHistorySuccessFilter(e.target.value)}
              >
                <option value="all">All results</option>
                <option value="success">Successful only</option>
                <option value="failed">Failed only</option>
              </select>
              <select
                className="h-10 rounded-md border bg-white px-3 text-sm"
                value={historySentimentFilter}
                onChange={(e) => setHistorySentimentFilter(e.target.value)}
              >
                <option value="all">All sentiments</option>
                <option value="positive">Positive</option>
                <option value="neutral">Neutral</option>
                <option value="negative">Negative</option>
              </select>
              <Input
                placeholder="Search sender or message"
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
              />
            </div>
            {history.length > 0 ? (
              <>
                {history.map((item) => (
                  <div key={item.id} className="rounded-lg border p-3">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <Badge variant="secondary">{item.response_mode}</Badge>
                      <Badge variant="outline">{item.message_type}</Badge>
                      <Badge
                        className={
                          item.sentiment === 'positive'
                            ? 'bg-green-100 text-green-700'
                            : item.sentiment === 'negative'
                              ? 'bg-rose-100 text-rose-700'
                              : 'bg-amber-100 text-amber-700'
                        }
                      >
                        {item.sentiment || 'neutral'}
                      </Badge>
                      <Badge className={item.success ? 'bg-green-100 text-green-700' : 'bg-rose-100 text-rose-700'}>
                        {item.success ? 'sent' : 'failed'}
                      </Badge>
                    </div>
                    <div className="text-sm font-medium text-gray-900">
                      {item.sender_name ? `@${item.sender_name}` : 'Unknown sender'}
                    </div>
                    {item.source_message && <div className="mt-1 text-sm text-gray-600">Incoming: {item.source_message}</div>}
                    <div className="mt-1 text-sm text-gray-900">Response: {item.response_text}</div>
                    {item.responded_at && (
                      <div className="mt-2 text-xs text-gray-500">{new Date(item.responded_at).toLocaleString()}</div>
                    )}
                  </div>
                ))}
                <div className="flex items-center justify-between pt-2">
                  <div className="text-sm text-gray-500">
                    Showing {historyOffset + 1}-{Math.min(historyOffset + history.length, historyTotal)} of {historyTotal}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={historyOffset === 0}
                      onClick={() => setHistoryOffset(Math.max(0, historyOffset - historyLimit))}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={historyOffset + history.length >= historyTotal}
                      onClick={() => setHistoryOffset(historyOffset + historyLimit)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-sm text-gray-500">No social response history has been saved for this location yet.</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Automation Settings</CardTitle>
            <CardDescription>These settings are now stored per location instead of returning demo defaults.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {settings ? (
              <>
                <label className="flex items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    checked={settings.auto_respond_enabled}
                    onChange={(e) => setSettings({ ...settings, auto_respond_enabled: e.target.checked })}
                  />
                  Enable automation
                </label>
                <label className="flex items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    checked={settings.auto_respond_dms}
                    onChange={(e) => setSettings({ ...settings, auto_respond_dms: e.target.checked })}
                  />
                  Auto-respond to DMs
                </label>
                <label className="flex items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    checked={settings.auto_respond_comments}
                    onChange={(e) => setSettings({ ...settings, auto_respond_comments: e.target.checked })}
                  />
                  Auto-respond to comments
                </label>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Response delay (seconds)</label>
                  <Input
                    type="number"
                    min={0}
                    value={settings.response_delay_seconds}
                    onChange={(e) =>
                      setSettings({ ...settings, response_delay_seconds: Number(e.target.value) || 0 })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Excluded keywords</label>
                  <Input
                    placeholder="spam, unsubscribe"
                    value={excludedKeywordsInput}
                    onChange={(e) => setExcludedKeywordsInput(e.target.value)}
                  />
                </div>
                <label className="flex items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    checked={settings.high_priority_alerts_enabled}
                    onChange={(e) =>
                      setSettings({ ...settings, high_priority_alerts_enabled: e.target.checked })
                    }
                  />
                  Alert me when high-priority messages are detected
                </label>
                <div className="space-y-2">
                  <label className="text-sm font-medium">High-priority alert channel</label>
                  <select
                    className="h-10 w-full rounded-md border bg-white px-3 text-sm"
                    value={settings.high_priority_alert_channel}
                    onChange={(e) =>
                      setSettings({ ...settings, high_priority_alert_channel: e.target.value })
                    }
                  >
                    <option value="preferred">Use account preference</option>
                    <option value="email">Email</option>
                    <option value="slack">Slack</option>
                    <option value="sms">SMS</option>
                  </select>
                </div>
                <Button onClick={handleSaveSettings} disabled={isSubmitting}>
                  {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Settings className="mr-2 h-4 w-4" />}
                  Save Settings
                </Button>
              </>
            ) : (
              <div className="text-sm text-gray-500">
                Automation settings are unavailable for this location right now. Refresh the page or reconnect the social channel in Integrations.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog
        open={isResponseDialogOpen}
        onOpenChange={(open) => {
          setIsResponseDialogOpen(open);
          if (!open) {
            setSelectedMessage(null);
            setResponseText('');
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Send Response</DialogTitle>
            <DialogDescription>Reply to @{selectedMessage?.sender_name} with an on-demand AI suggestion or your own text.</DialogDescription>
          </DialogHeader>

          {selectedMessage && (
            <div className="space-y-4">
              <div className="rounded-lg bg-gray-50 p-3">
                <p className="mb-1 text-sm text-gray-600">Original message</p>
                <p className="text-gray-800">{selectedMessage.message}</p>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">Response</label>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleGenerateSuggestion}
                    disabled={isGeneratingSuggestion || isSubmitting}
                  >
                    {isGeneratingSuggestion ? (
                      <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="mr-1 h-4 w-4" />
                    )}
                    {selectedMessage.suggested_response ? 'Regenerate AI Suggestion' : 'Generate AI Suggestion'}
                  </Button>
                </div>
                {selectedMessage.suggested_response && (
                  <div className="rounded-lg border-l-2 border-purple-500 bg-purple-50 p-3">
                    <div className="mb-1 flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-purple-600" />
                      <p className="text-sm font-medium text-purple-700">Latest AI Suggestion</p>
                    </div>
                    <p className="text-sm text-gray-700">{selectedMessage.suggested_response}</p>
                  </div>
                )}
                <textarea
                  className="h-32 w-full resize-none rounded-lg border p-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  placeholder="Type your response..."
                  value={responseText}
                  onChange={(e) => setResponseText(e.target.value)}
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsResponseDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSendResponse}
              disabled={isSubmitting || isGeneratingSuggestion}
              className="bg-gradient-to-r from-pink-500 to-purple-600"
            >
              {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
              Send Response
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
