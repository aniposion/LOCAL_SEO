'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  CheckCircle,
  Loader2,
  MessageSquare,
  Phone,
  PhoneCall,
  PhoneMissed,
  RefreshCw,
  Send,
  Settings,
} from 'lucide-react';
import { toast } from 'sonner';

import { callsApi, extractCollectionPayload, locationsApi } from '@/lib/api';
import { getApiErrorMessage, getApiErrorStatus } from '@/lib/api-errors';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';

interface LocationOption {
  id: string;
  name: string;
}

interface CallStats {
  total_calls: number;
  missed_calls: number;
  answered_calls: number;
  text_backs_sent: number;
  text_back_rate: number;
}

interface CallLog {
  id: string;
  caller_phone: string;
  masked_phone: string;
  call_status: string;
  call_duration: number;
  sms_sent: boolean;
  sms_sent_at?: string | null;
  created_at: string;
}

interface CallThread {
  id: string;
  customer_phone: string;
  masked_phone: string;
  status: string;
  last_message_at?: string | null;
  unread_count: number;
  created_at: string;
}

interface CallMessage {
  id: string;
  direction: string;
  body: string;
  status?: string | null;
  created_at: string;
}

interface CallSettings {
  twilio_number: string;
  forward_to: string;
  enabled: boolean;
  sms_template: string;
}

const EMPTY_STATS: CallStats = {
  total_calls: 0,
  missed_calls: 0,
  answered_calls: 0,
  text_backs_sent: 0,
  text_back_rate: 0,
};

function formatDateTime(value?: string | null): string {
  if (!value) {
    return 'Not available';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) {
    return '0:00';
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

function getCallStatusBadge(status: string) {
  switch (status) {
    case 'completed':
      return <Badge className="bg-green-100 text-green-700">Answered</Badge>;
    case 'no-answer':
      return <Badge className="bg-red-100 text-red-700">No Answer</Badge>;
    case 'busy':
      return <Badge className="bg-orange-100 text-orange-700">Busy</Badge>;
    case 'failed':
      return <Badge className="bg-gray-100 text-gray-700">Failed</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function getCallIcon(status: string) {
  switch (status) {
    case 'completed':
      return <PhoneCall className="h-4 w-4 text-green-500" />;
    case 'no-answer':
      return <PhoneMissed className="h-4 w-4 text-red-500" />;
    default:
      return <Phone className="h-4 w-4 text-orange-500" />;
  }
}

export default function CallsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);

  const [loadError, setLoadError] = useState<string | null>(null);
  const [messageError, setMessageError] = useState<string | null>(null);

  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [selectedLocationId, setSelectedLocationId] = useState('');
  const [days, setDays] = useState('30');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const [messageReloadToken, setMessageReloadToken] = useState(0);

  const [stats, setStats] = useState<CallStats>(EMPTY_STATS);
  const [callLogs, setCallLogs] = useState<CallLog[]>([]);
  const [threads, setThreads] = useState<CallThread[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState('');
  const [messages, setMessages] = useState<CallMessage[]>([]);

  const [settings, setSettings] = useState<CallSettings | null>(null);
  const [settingsMissing, setSettingsMissing] = useState(false);
  const [enabledDraft, setEnabledDraft] = useState(false);
  const [smsTemplateDraft, setSmsTemplateDraft] = useState('');
  const [replyBody, setReplyBody] = useState('');
  const activeLocationId = selectedLocationId || locations[0]?.id || '';

  const selectedLocationName = useMemo(
    () => locations.find((location) => location.id === activeLocationId)?.name || 'Selected location',
    [locations, activeLocationId]
  );

  const selectedThread = useMemo(
    () => threads.find((thread) => thread.id === selectedThreadId) || null,
    [threads, selectedThreadId]
  );

  const hasSettingsChanges = useMemo(() => {
    if (!settings) {
      return false;
    }

    return settings.enabled !== enabledDraft || settings.sms_template !== smsTemplateDraft;
  }, [enabledDraft, settings, smsTemplateDraft]);

  useEffect(() => {
    let isCancelled = false;

    const loadLocations = async () => {
      setIsLoading(true);
      try {
        const response = await locationsApi.list();
        const items = extractCollectionPayload<LocationOption>(response.data, 'locations');
        const normalized = items.map((item: { id: string; name: string }) => ({
          id: item.id,
          name: item.name,
        }));

        if (isCancelled) {
          return;
        }

        setLocations(normalized);
        setSelectedLocationId((current) => current || normalized[0]?.id || '');
        setLoadError(null);
      } catch (error) {
        if (isCancelled) {
          return;
        }

        setLocations([]);
        setSelectedLocationId('');
        setLoadError(getApiErrorMessage(error, 'Calls & SMS setup could not be loaded.'));
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadLocations();

    return () => {
      isCancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!activeLocationId) {
      setStats(EMPTY_STATS);
      setCallLogs([]);
      setThreads([]);
      setSelectedThreadId('');
      setMessages([]);
      setSettings(null);
      setSettingsMissing(false);
      setEnabledDraft(false);
      setSmsTemplateDraft('');
      return;
    }

    let isCancelled = false;

    const loadLocationData = async () => {
      setIsRefreshing(true);

      const nextErrors: string[] = [];

      try {
        const [statsResult, logsResult, threadsResult, settingsResult] = await Promise.allSettled([
          callsApi.getStats(activeLocationId, Number(days)),
          callsApi.getLogs(activeLocationId, Number(days)),
          callsApi.getThreads(activeLocationId, unreadOnly),
          callsApi.getSettings(activeLocationId),
        ]);

        if (isCancelled) {
          return;
        }

        if (statsResult.status === 'fulfilled') {
          setStats((statsResult.value.data as CallStats) || EMPTY_STATS);
        } else {
          setStats(EMPTY_STATS);
          nextErrors.push(getApiErrorMessage(statsResult.reason, 'Call stats could not be loaded.'));
        }

        if (logsResult.status === 'fulfilled') {
          const data = logsResult.value.data as { items?: CallLog[] };
          setCallLogs(data.items || []);
        } else {
          setCallLogs([]);
          nextErrors.push(getApiErrorMessage(logsResult.reason, 'Call logs could not be loaded.'));
        }

        let nextThreads: CallThread[] = [];
        if (threadsResult.status === 'fulfilled') {
          const data = threadsResult.value.data as { items?: CallThread[] };
          nextThreads = data.items || [];
          setThreads(nextThreads);
        } else {
          setThreads([]);
          nextErrors.push(getApiErrorMessage(threadsResult.reason, 'SMS inbox could not be loaded.'));
        }

        if (nextThreads.length === 0) {
          setSelectedThreadId('');
          setMessages([]);
        } else {
          setSelectedThreadId((current) => (nextThreads.some((thread) => thread.id === current) ? current : nextThreads[0].id));
        }

        if (settingsResult.status === 'fulfilled') {
          const nextSettings = settingsResult.value.data as CallSettings;
          setSettings(nextSettings);
          setSettingsMissing(false);
          setEnabledDraft(nextSettings.enabled);
          setSmsTemplateDraft(nextSettings.sms_template);
        } else if (getApiErrorStatus(settingsResult.reason) === 404) {
          setSettings(null);
          setSettingsMissing(true);
          setEnabledDraft(false);
          setSmsTemplateDraft('');
        } else {
          setSettings(null);
          setSettingsMissing(false);
          setEnabledDraft(false);
          setSmsTemplateDraft('');
          nextErrors.push(getApiErrorMessage(settingsResult.reason, 'Call settings could not be loaded.'));
        }

        setLoadError(nextErrors.length > 0 ? nextErrors.join(' ') : null);
      } finally {
        if (!isCancelled) {
          setIsRefreshing(false);
        }
      }
    };

    void loadLocationData();

    return () => {
      isCancelled = true;
    };
  }, [activeLocationId, days, reloadToken, unreadOnly]);

  useEffect(() => {
    if (!activeLocationId || !selectedThreadId) {
      setMessages([]);
      setMessageError(null);
      return;
    }

    let isCancelled = false;

    const loadMessages = async () => {
      setIsLoadingMessages(true);
      try {
        const response = await callsApi.getMessages(activeLocationId, selectedThreadId);
        if (isCancelled) {
          return;
        }

        const data = response.data as { messages?: CallMessage[] };
        setMessages(data.messages || []);
        setMessageError(null);
      } catch (error) {
        if (isCancelled) {
          return;
        }

        setMessages([]);
        setMessageError(getApiErrorMessage(error, 'Conversation could not be loaded.'));
      } finally {
        if (!isCancelled) {
          setIsLoadingMessages(false);
        }
      }
    };

    void loadMessages();

    return () => {
      isCancelled = true;
    };
  }, [activeLocationId, messageReloadToken, selectedThreadId]);

  const handleRefresh = () => {
    setReloadToken((current) => current + 1);
  };

  const handleMarkThreadRead = async () => {
    if (!activeLocationId || !selectedThreadId) {
      return;
    }

    try {
      await callsApi.markRead(activeLocationId, selectedThreadId);
      setThreads((current) =>
        current.map((thread) =>
          thread.id === selectedThreadId
            ? {
                ...thread,
                unread_count: 0,
              }
            : thread
        )
      );
      toast.success('Thread marked as read.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Thread could not be marked as read.'));
    }
  };

  const handleSendMessage = async () => {
    if (!activeLocationId || !selectedThreadId) {
      return;
    }

    const trimmedBody = replyBody.trim();
    if (!trimmedBody) {
      toast.error('Write a reply before sending.');
      return;
    }

    setIsSendingMessage(true);
    try {
      await callsApi.sendMessage(activeLocationId, selectedThreadId, trimmedBody);
      setReplyBody('');
      setMessageReloadToken((current) => current + 1);
      setReloadToken((current) => current + 1);
      toast.success('Reply sent to the live SMS thread.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Reply could not be sent.'));
    } finally {
      setIsSendingMessage(false);
    }
  };

  const handleSaveSettings = async () => {
    if (!activeLocationId || !settings || !hasSettingsChanges) {
      return;
    }

    setIsSavingSettings(true);
    try {
      const response = await callsApi.updateSettings(activeLocationId, {
        enabled: enabledDraft,
        sms_template: smsTemplateDraft,
      });
      const data = response.data as { enabled: boolean; sms_template: string };

      setSettings((current) =>
        current
          ? {
              ...current,
              enabled: data.enabled,
              sms_template: data.sms_template,
            }
          : current
      );
      setEnabledDraft(data.enabled);
      setSmsTemplateDraft(data.sms_template);
      toast.success('Call settings saved.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Call settings could not be saved.'));
    } finally {
      setIsSavingSettings(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <Card key={item}>
              <CardContent className="pt-6">
                <Skeleton className="mb-3 h-8 w-16" />
                <Skeleton className="h-4 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Card>
          <CardContent className="space-y-3 pt-6">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-64 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (locations.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Calls & SMS</h1>
          <p className="text-gray-500">Monitor live missed-call recovery and SMS threads.</p>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>No locations connected</CardTitle>
            <CardDescription>Add at least one location before using missed-call recovery.</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Calls & SMS</h1>
          <p className="text-gray-500">Review live missed calls, SMS replies, and Twilio recovery settings.</p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="calls-location">Location</Label>
            <Select value={activeLocationId} onValueChange={setSelectedLocationId}>
              <SelectTrigger id="calls-location" className="w-full min-w-[220px]">
                <SelectValue placeholder="Select a location" />
              </SelectTrigger>
              <SelectContent>
                {locations.map((location) => (
                  <SelectItem key={location.id} value={location.id}>
                    {location.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="calls-range">Window</Label>
            <Select value={days} onValueChange={setDays}>
              <SelectTrigger id="calls-range" className="w-full min-w-[140px]">
                <SelectValue placeholder="Select range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7">Last 7 days</SelectItem>
                <SelectItem value="30">Last 30 days</SelectItem>
                <SelectItem value="90">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" onClick={handleRefresh} disabled={isRefreshing} className="self-end">
            {isRefreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Refresh
          </Button>
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Calls Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {stats.missed_calls > 0 ? 'Recover missed-call demand first' : 'Keep call recovery ready'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Start with missed calls and unread SMS threads. Settings are secondary unless recovery is not working.
            </p>
          </div>
          <Badge className="w-fit bg-white/10 text-white hover:bg-white/10">
            {stats.missed_calls} missed
          </Badge>
        </CardContent>
      </Card>

      {loadError ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="pt-6 text-sm text-amber-900">{loadError}</CardContent>
        </Card>
      ) : null}

      {settingsMissing ? (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="pt-6 text-sm text-blue-900">
            Twilio number is not configured for <span className="font-medium">{selectedLocationName}</span> yet. Live call logs
            and inbox threads can still appear, but auto-text settings cannot be edited until provisioning is complete.
          </CardContent>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Phone className="h-5 w-5 text-blue-500" />
              <span className="text-3xl font-bold">{stats.total_calls}</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Total Calls</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <PhoneMissed className="h-5 w-5 text-red-500" />
              <span className="text-3xl font-bold text-red-600">{stats.missed_calls}</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Missed Calls</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-green-500" />
              <span className="text-3xl font-bold text-green-600">{stats.text_backs_sent}</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Text-backs Sent</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-violet-500" />
              <span className="text-3xl font-bold text-violet-600">{stats.text_back_rate.toFixed(1)}%</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Recovery Rate</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">
            <Phone className="mr-2 h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="inbox">
            <MessageSquare className="mr-2 h-4 w-4" />
            SMS Inbox
          </TabsTrigger>
          <TabsTrigger value="settings">
            <Settings className="mr-2 h-4 w-4" />
            Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Recent Call Logs</CardTitle>
              <CardDescription>Live call activity for {selectedLocationName} over the last {days} days.</CardDescription>
            </CardHeader>
            <CardContent>
              {callLogs.length === 0 ? (
                <div className="rounded-lg border border-dashed p-6 text-sm text-gray-500">
                  No call logs were recorded for this location in the selected time window.
                </div>
              ) : (
                <div className="space-y-3">
                  {callLogs.map((call) => (
                    <div key={call.id} className="flex flex-col gap-3 rounded-lg border p-4 lg:flex-row lg:items-center lg:justify-between">
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 rounded-full bg-gray-100 p-2">{getCallIcon(call.call_status)}</div>
                        <div>
                          <p className="font-medium">{call.masked_phone}</p>
                          <p className="text-sm text-gray-500">
                            {formatDateTime(call.created_at)}
                            {call.call_duration > 0 ? ` 쨌 ${formatDuration(call.call_duration)}` : ''}
                          </p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {getCallStatusBadge(call.call_status)}
                        {call.sms_sent ? <Badge className="bg-blue-100 text-blue-700">SMS Sent</Badge> : null}
                        {!call.sms_sent && (call.call_status === 'no-answer' || call.call_status === 'busy') ? (
                          <Badge variant="secondary">No text-back recorded</Badge>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="inbox" className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">SMS Inbox</h2>
              <p className="text-sm text-gray-500">Live Twilio reply threads created from missed-call follow-up.</p>
            </div>
            <Button variant={unreadOnly ? 'default' : 'outline'} onClick={() => setUnreadOnly((current) => !current)}>
              {unreadOnly ? 'Showing unread only' : 'Show unread only'}
            </Button>
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
            <Card>
              <CardHeader>
                <CardTitle>Threads</CardTitle>
                <CardDescription>{threads.length} thread(s) loaded for {selectedLocationName}.</CardDescription>
              </CardHeader>
              <CardContent>
                {threads.length === 0 ? (
                  <div className="rounded-lg border border-dashed p-6 text-sm text-gray-500">
                    No SMS threads matched the current filter for this location.
                  </div>
                ) : (
                  <ScrollArea className="h-[420px] pr-3">
                    <div className="space-y-3">
                      {threads.map((thread) => {
                        const isActive = thread.id === selectedThreadId;
                        return (
                          <button
                            key={thread.id}
                            type="button"
                            onClick={() => setSelectedThreadId(thread.id)}
                            className={`w-full rounded-lg border p-4 text-left transition ${
                              isActive ? 'border-violet-500 bg-violet-50' : 'hover:bg-gray-50'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="font-medium">{thread.masked_phone}</p>
                                <p className="text-sm text-gray-500">{formatDateTime(thread.last_message_at || thread.created_at)}</p>
                              </div>
                              {thread.unread_count > 0 ? (
                                <Badge className="bg-red-100 text-red-700">{thread.unread_count} unread</Badge>
                              ) : (
                                <Badge variant="secondary">{thread.status}</Badge>
                              )}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </ScrollArea>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <CardTitle>{selectedThread ? selectedThread.masked_phone : 'Choose a thread'}</CardTitle>
                    <CardDescription>
                      {selectedThread
                        ? `Status: ${selectedThread.status} 쨌 Last activity ${formatDateTime(
                            selectedThread.last_message_at || selectedThread.created_at
                          )}`
                        : 'Select a live thread to review its message history.'}
                    </CardDescription>
                  </div>
                  {selectedThread && selectedThread.unread_count > 0 ? (
                    <Button variant="outline" onClick={handleMarkThreadRead}>
                      Mark Read
                    </Button>
                  ) : null}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {messageError ? (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{messageError}</div>
                ) : null}

                <ScrollArea className="h-[320px] rounded-lg border p-4">
                  {isLoadingMessages ? (
                    <div className="space-y-3">
                      <Skeleton className="h-16 w-3/4" />
                      <Skeleton className="ml-auto h-16 w-2/3" />
                      <Skeleton className="h-16 w-1/2" />
                    </div>
                  ) : !selectedThread ? (
                    <div className="flex h-full items-center justify-center text-sm text-gray-500">
                      Select a thread from the left to review or reply.
                    </div>
                  ) : messages.length === 0 ? (
                    <div className="flex h-full items-center justify-center text-sm text-gray-500">
                      No messages were recorded for this thread yet.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {messages.map((message) => {
                        const outbound = message.direction === 'outbound';
                        return (
                          <div key={message.id} className={`flex ${outbound ? 'justify-end' : 'justify-start'}`}>
                            <div
                              className={`max-w-[85%] rounded-lg px-4 py-3 text-sm ${
                                outbound ? 'bg-violet-600 text-white' : 'bg-gray-100 text-gray-900'
                              }`}
                            >
                              <p>{message.body}</p>
                              <p className={`mt-2 text-xs ${outbound ? 'text-violet-100' : 'text-gray-500'}`}>
                                {outbound ? 'Outbound' : 'Inbound'} 쨌 {formatDateTime(message.created_at)}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </ScrollArea>

                {selectedThread ? (
                  <div className="space-y-2">
                    <Label htmlFor="thread-reply">Send reply</Label>
                    <Textarea
                      id="thread-reply"
                      placeholder="Write a live SMS reply for this customer thread."
                      value={replyBody}
                      onChange={(event) => setReplyBody(event.target.value)}
                      disabled={isSendingMessage}
                      rows={4}
                    />
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-gray-500">
                        Replies are sent to the real thread for {selectedLocationName}. No demo messages are injected here.
                      </p>
                      <Button onClick={handleSendMessage} disabled={isSendingMessage}>
                        {isSendingMessage ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                        Send Reply
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed p-4 text-sm text-gray-600">
                    Select a live SMS thread first. The reply composer only opens when a real customer thread is selected.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="settings" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Missed-call recovery settings</CardTitle>
              <CardDescription>These controls are tied to the live Twilio number provisioned for {selectedLocationName}.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {!settings ? (
                <div className="rounded-lg border border-dashed p-6 text-sm text-gray-500">
                  {settingsMissing
                    ? 'Twilio provisioning has not been completed for this location yet.'
                    : 'Settings are temporarily unavailable for this location.'}
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Twilio tracking number</Label>
                      <Input value={settings.twilio_number} readOnly />
                      <p className="text-xs text-gray-500">Provisioned number used for call tracking and reply routing.</p>
                    </div>
                    <div className="space-y-2">
                      <Label>Forwarding destination</Label>
                      <Input value={settings.forward_to} readOnly />
                      <p className="text-xs text-gray-500">Read-only here because routing is provisioned with the live number.</p>
                    </div>
                  </div>

                  <div className="rounded-lg border p-4">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <p className="font-medium">Missed-call SMS recovery</p>
                        <p className="text-sm text-gray-500">Send an automatic text when a call ends with no answer or busy status.</p>
                      </div>
                      <Button variant={enabledDraft ? 'default' : 'outline'} onClick={() => setEnabledDraft((current) => !current)}>
                        {enabledDraft ? 'Enabled' : 'Disabled'}
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="sms-template">Auto-reply template</Label>
                    <Textarea
                      id="sms-template"
                      value={smsTemplateDraft}
                      onChange={(event) => setSmsTemplateDraft(event.target.value)}
                      rows={5}
                    />
                    <p className="text-xs text-gray-500">
                      Supported placeholders stay server-side. Keep the template honest about business name and callback routing.
                    </p>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={handleSaveSettings} disabled={!hasSettingsChanges || isSavingSettings}>
                      {isSavingSettings ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                      Save Settings
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
