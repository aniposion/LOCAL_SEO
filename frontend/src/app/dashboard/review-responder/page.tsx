'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  MessageSquare,
  Star,
  CheckCircle,
  XCircle,
  Edit3,
  RefreshCw,
  Sparkles,
  Download,
  Search,
  Filter,
  AlertTriangle,
  Clock3,
} from 'lucide-react';
import {
  reviewResponseApi,
  type BulkRetryResponse,
  type FailedResponseItem,
  type ReviewResponse,
} from '@/lib/api/ai-features';
import { api, extractCollectionPayload, locationsApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';

interface LocationOption {
  id: string;
  name: string;
}

interface ReviewResponderItem extends ReviewResponse {
  high_priority?: boolean;
  priority_level?: 'high' | 'medium' | 'normal';
  priority_reason?: string;
  age_minutes?: number | null;
  platform_response_id?: string | null;
}

interface ReviewResponderHistoryResponse {
  items: ReviewResponderItem[];
  total: number;
  limit: number;
  offset: number;
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

export default function ReviewResponderPage() {
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [locationsLoading, setLocationsLoading] = useState(true);
  const [selectedLocationId, setSelectedLocationId] = useState<string>('');
  const [editingResponse, setEditingResponse] = useState<ReviewResponse | null>(null);
  const [editedDraft, setEditedDraft] = useState<string>('');
  const [rejectingResponse, setRejectingResponse] = useState<ReviewResponse | null>(null);
  const [rejectionReason, setRejectionReason] = useState<string>('');
  const [pendingSearch, setPendingSearch] = useState<string>('');
  const [pendingHighPriorityOnly, setPendingHighPriorityOnly] = useState(false);
  const [pendingPlatform, setPendingPlatform] = useState<string>('all');
  const [historySearch, setHistorySearch] = useState<string>('');
  const [historyHighPriorityOnly, setHistoryHighPriorityOnly] = useState(false);
  const [historyPlatform, setHistoryPlatform] = useState<string>('all');
  const [historyStatus, setHistoryStatus] = useState<string>('all');
  const [historyOffset, setHistoryOffset] = useState(0);
  const [selectedHistoryResponse, setSelectedHistoryResponse] = useState<ReviewResponderItem | null>(null);
  const [retryingId, setRetryingId] = useState<number | null>(null);
  const [failedSearch, setFailedSearch] = useState<string>('');
  const [failedPlatform, setFailedPlatform] = useState<string>('all');
  const [failedOffset, setFailedOffset] = useState(0);
  const [selectedFailedIds, setSelectedFailedIds] = useState<Set<number>>(new Set());

  const queryClient = useQueryClient();
  const activeLocationId = selectedLocationId || locations[0]?.id || '';

  useEffect(() => {
    const loadLocations = async () => {
      try {
        const response = await locationsApi.list();
        const nextLocations = extractCollectionPayload<LocationOption>(response.data, 'locations');
        setLocations(nextLocations);
        if (nextLocations.length > 0) {
          setSelectedLocationId((current) => current || nextLocations[0].id);
        }
      } catch {
        console.error('Failed to load locations for review responder');
      } finally {
        setLocationsLoading(false);
      }
    };

    void loadLocations();
  }, []);

  const { data: summary } = useQuery({
    queryKey: ['review-responder-summary', activeLocationId],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (activeLocationId) {
        params.set('location_id', activeLocationId);
      }
      const response = await api.get<ReviewResponderSummary>(
        `/reviews/summary${params.size ? `?${params.toString()}` : ''}`
      );
      return response.data;
    },
    enabled: !locationsLoading && !!activeLocationId,
  });

  const { data: pendingResponses, isLoading: pendingLoading } = useQuery({
    queryKey: [
      'pending-responses',
      activeLocationId,
      pendingSearch,
      pendingHighPriorityOnly,
      pendingPlatform,
    ],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (activeLocationId) params.set('location_id', activeLocationId);
      if (pendingSearch.trim()) params.set('search', pendingSearch.trim());
      if (pendingHighPriorityOnly) params.set('high_priority_only', 'true');
      if (pendingPlatform !== 'all') params.set('platform', pendingPlatform);
      const response = await api.get<ReviewResponderItem[]>(
        `/reviews/pending${params.size ? `?${params.toString()}` : ''}`
      );
      return response.data;
    },
    enabled: !locationsLoading && !!activeLocationId,
    refetchInterval: 30000,
  });

  const { data: historyResponse, isLoading: historyLoading } = useQuery({
    queryKey: [
      'review-responder-history',
      activeLocationId,
      historySearch,
      historyHighPriorityOnly,
      historyPlatform,
      historyStatus,
      historyOffset,
    ],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (activeLocationId) params.set('location_id', activeLocationId);
      if (historySearch.trim()) params.set('search', historySearch.trim());
      if (historyHighPriorityOnly) params.set('high_priority_only', 'true');
      if (historyPlatform !== 'all') params.set('platform', historyPlatform);
      if (historyStatus !== 'all') params.set('status_filter', historyStatus);
      params.set('limit', '8');
      params.set('offset', String(historyOffset));
      const response = await api.get<ReviewResponderHistoryResponse>(
        `/reviews/history${params.size ? `?${params.toString()}` : ''}`
      );
      return response.data;
    },
    enabled: !locationsLoading && !!activeLocationId,
  });

  const approveMutation = useMutation({
    mutationFn: ({ id, draft }: { id: number; draft?: string }) =>
      reviewResponseApi.approve(id, draft),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-responses', activeLocationId] });
      queryClient.invalidateQueries({ queryKey: ['review-responder-summary', activeLocationId] });
      queryClient.invalidateQueries({ queryKey: ['review-responder-history', activeLocationId] });
      setEditingResponse(null);
      setEditedDraft('');
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      reviewResponseApi.reject(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-responses', activeLocationId] });
      queryClient.invalidateQueries({ queryKey: ['review-responder-summary', activeLocationId] });
      queryClient.invalidateQueries({ queryKey: ['review-responder-history', activeLocationId] });
      setRejectingResponse(null);
      setRejectionReason('');
    },
  });

  const retryMutation = useMutation({
    mutationFn: (id: number) => {
      setRetryingId(id);
      return reviewResponseApi.retry(id);
    },
    onSettled: () => setRetryingId(null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review-responder-history', activeLocationId] });
      queryClient.invalidateQueries({ queryKey: ['review-responder-summary', activeLocationId] });
      queryClient.invalidateQueries({ queryKey: ['review-responder-failed', activeLocationId] });
    },
  });

  const { data: failedData } = useQuery({
    queryKey: [
      'review-responder-failed',
      activeLocationId,
      failedSearch,
      failedPlatform,
      failedOffset,
    ],
    queryFn: () =>
      reviewResponseApi.getFailed({
        location_id: activeLocationId || undefined,
        search: failedSearch.trim() || undefined,
        platform: failedPlatform !== 'all' ? failedPlatform : undefined,
        limit: 10,
        offset: failedOffset,
      }),
    enabled: !locationsLoading && !!activeLocationId,
    refetchInterval: 60000,
  });

  const bulkRetryMutation = useMutation<BulkRetryResponse, Error, number[]>({
    mutationFn: (ids: number[]) => reviewResponseApi.bulkRetry(ids),
    onSuccess: () => {
      setSelectedFailedIds(new Set());
      queryClient.invalidateQueries({ queryKey: ['review-responder-failed', activeLocationId] });
      queryClient.invalidateQueries({ queryKey: ['review-responder-history', activeLocationId] });
      queryClient.invalidateQueries({ queryKey: ['review-responder-summary', activeLocationId] });
    },
  });

  const exportHistory = async () => {
    const params = new URLSearchParams();
    if (activeLocationId) params.set('location_id', activeLocationId);
    if (historySearch.trim()) params.set('search', historySearch.trim());
    if (historyHighPriorityOnly) params.set('high_priority_only', 'true');
    if (historyPlatform !== 'all') params.set('platform', historyPlatform);
    if (historyStatus !== 'all') params.set('status_filter', historyStatus);
    const response = await api.get<Blob>(
      `/reviews/history/export${params.size ? `?${params.toString()}` : ''}`,
      { responseType: 'blob' }
    );
    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `review-responder-history-${activeLocationId}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const getSentimentBadge = (score: number) => {
    if (score > 0.5) return { label: 'Positive', variant: 'default' as const };
    if (score < -0.5) return { label: 'Negative', variant: 'destructive' as const };
    return { label: 'Neutral', variant: 'secondary' as const };
  };

  const getIntentBadge = (intent: string) => {
    const colors: Record<string, string> = {
      praise: 'bg-green-100 text-green-800',
      complaint: 'bg-red-100 text-red-800',
      suggestion: 'bg-blue-100 text-blue-800',
      question: 'bg-purple-100 text-purple-800',
      misunderstanding: 'bg-orange-100 text-orange-800',
    };
    return colors[intent] || 'bg-gray-100 text-gray-800';
  };

  const handleEdit = (response: ReviewResponse) => {
    setEditingResponse(response);
    setEditedDraft(response.ai_draft);
  };

  const handleApprove = (response: ReviewResponse) => {
    if (editingResponse?.id === response.id) {
      approveMutation.mutate({ id: response.id, draft: editedDraft });
    } else {
      approveMutation.mutate({ id: response.id });
    }
  };

  const handleReject = () => {
    if (rejectingResponse && rejectionReason.trim()) {
      rejectMutation.mutate({
        id: rejectingResponse.id,
        reason: rejectionReason,
      });
    }
  };

  const pendingItems = (pendingResponses || []).slice().sort((left, right) => {
    if (!!left.high_priority !== !!right.high_priority) {
      return left.high_priority ? -1 : 1;
    }
    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
  });

  const historyItems = historyResponse?.items || [];

  const ERROR_CATEGORY_LABELS: Record<string, { label: string; hint: string }> = {
    no_oauth_token: { label: 'No Google OAuth', hint: 'Go to Integrations → reconnect Google' },
    token_missing: { label: 'Token missing', hint: 'Go to Integrations → reconnect Google' },
    api_error: { label: 'GBP API error', hint: 'GBP rejected the call — see error detail' },
    unknown: { label: 'Unknown error', hint: 'Review error detail below' },
  };

  const getPublishErrorMessage = (error: string): string => {
    const lower = error.toLowerCase();
    if (lower.includes('no google oauth token') || lower.includes('reconnect google') || lower.includes('not connected')) {
      return 'Google account not connected. Go to Integrations to reconnect Google, then retry.';
    }
    if (lower.includes('access token is missing')) {
      return 'Google access token is missing. Go to Integrations to reconnect Google, then retry.';
    }
    return error;
  };

  const getPriorityBadge = (response: ReviewResponderItem) => {
    if (response.high_priority) {
      return { label: 'High priority', variant: 'destructive' as const };
    }
    if (response.priority_level === 'medium') {
      return { label: 'Medium priority', variant: 'default' as const };
    }
    return { label: 'Normal', variant: 'secondary' as const };
  };

  const summarizeStats = useMemo(() => {
    return {
      pending: summary?.pending_count ?? pendingItems.length,
      highPriorityPending: summary?.high_priority_pending_count ?? pendingItems.filter((item) => item.high_priority).length,
      published: summary?.published_count ?? 0,
      failed: summary?.failed_count ?? 0,
    };
  }, [pendingItems, summary]);

  if (locationsLoading || pendingLoading || historyLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (locations.length === 0) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle>No location available</CardTitle>
            <CardDescription>
              Create or connect a business location before managing AI review responses.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const pendingCount = summarizeStats.pending;

  return (
    <div className="container mx-auto space-y-8 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">AI Smart Review Responder</h1>
          <p className="mt-2 text-muted-foreground">
            Review and approve AI-generated responses for the selected location.
          </p>
        </div>
        <Badge variant={pendingCount > 0 ? 'default' : 'secondary'} className="px-4 py-2 text-lg">
          {pendingCount} Pending
        </Badge>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Review Reply Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {(summary?.high_priority_pending_count ?? 0) > 0
                ? 'Approve or edit high-priority replies first'
                : pendingCount > 0
                  ? 'Clear the pending reply queue'
                  : 'No replies need approval right now'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Start with pending approvals. Metrics, filters, failed publishes, and history are support tools after that.
            </p>
          </div>
          <Badge className="w-fit bg-white/10 text-white hover:bg-white/10">{pendingCount} pending</Badge>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        {locations.map((location) => (
          <Button
            key={location.id}
            variant={location.id === activeLocationId ? 'default' : 'outline'}
            onClick={() => setSelectedLocationId(location.id)}
          >
            {location.name}
          </Button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Approval</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pendingCount}</div>
            <p className="mt-2 text-xs text-muted-foreground">Awaiting your review</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">High Priority Pending</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.high_priority_pending_count ?? 0}</div>
            <p className="mt-2 text-xs text-muted-foreground">Low ratings or complaint responses</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Published</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.published_count ?? 0}</div>
            <p className="mt-2 text-xs text-muted-foreground">Published to GBP so far</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failed</CardTitle>
            <XCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.failed_count ?? 0}</div>
            <p className="mt-2 text-xs text-muted-foreground">Publish or workflow failures</p>
          </CardContent>
        </Card>
      </div>

      {(summary?.high_priority_pending_count ?? 0) > 0 ? (
        <Card className="border-amber-200 bg-amber-50/70">
          <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-amber-900">
                <AlertTriangle className="h-4 w-4" />
                <p className="font-semibold">High priority responses need attention</p>
              </div>
              <p className="text-sm text-amber-900/80">
                {summary?.high_priority_pending_count ?? 0} pending now, {summary?.high_priority_total_count ?? 0}{' '}
                total high priority items in the queue.
              </p>
            </div>
            <Button
              variant="outline"
              className="border-amber-300 bg-white text-amber-900 hover:bg-amber-100"
              onClick={() => setPendingHighPriorityOnly(true)}
            >
              Show high priority
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <Card className="border-dashed">
        <CardHeader className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Operator Filters</CardTitle>
              <CardDescription>Focus the queue on what needs attention first.</CardDescription>
            </div>
            <Badge variant={pendingCount > 0 ? 'default' : 'secondary'} className="px-3 py-1">
              {pendingCount} Pending
            </Badge>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="relative md:col-span-2">
              <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder="Search review text, author, draft, error, or review id"
                value={pendingSearch}
                onChange={(event) => setPendingSearch(event.target.value)}
              />
            </div>
            <div className="flex flex-wrap gap-2 md:justify-end">
              {['all', 'google', 'facebook', 'yelp'].map((platform) => (
                <Button
                  key={platform}
                  size="sm"
                  variant={pendingPlatform === platform ? 'default' : 'outline'}
                  onClick={() => setPendingPlatform(platform)}
                >
                  {platform === 'all' ? 'All platforms' : platform}
                </Button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant={pendingHighPriorityOnly ? 'default' : 'outline'}
              onClick={() => setPendingHighPriorityOnly((current) => !current)}
            >
              <Filter className="mr-2 h-4 w-4" />
              High priority only
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setPendingSearch('');
                setPendingPlatform('all');
                setPendingHighPriorityOnly(false);
              }}
            >
              Reset filters
            </Button>
          </div>
        </CardHeader>
      </Card>

      {pendingCount === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <CheckCircle className="mb-4 h-12 w-12 text-green-500" />
            <h3 className="mb-2 text-lg font-semibold">All Caught Up</h3>
            <p className="text-center text-muted-foreground">
              No pending review responses at the moment.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {pendingItems.map((response) => (
            <Card key={response.id} className="overflow-hidden">
              <CardHeader className="bg-muted/50">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="flex">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <Star
                            key={i}
                            className={`h-4 w-4 ${
                              i < response.review_rating
                                ? 'fill-yellow-400 text-yellow-400'
                                : 'text-gray-300'
                            }`}
                          />
                        ))}
                      </div>
                      <span className="font-semibold">{response.review_author}</span>
                      <Badge variant="outline">{response.platform}</Badge>
                      <Badge variant={getPriorityBadge(response).variant}>{getPriorityBadge(response).label}</Badge>
                    </div>
                    <CardDescription className="flex flex-wrap items-center gap-2">
                      <span>{response.review_date ? new Date(response.review_date).toLocaleDateString() : 'No date'}</span>
                      <span>•</span>
                      <span>{response.age_minutes ?? 0} min in queue</span>
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={getSentimentBadge(response.sentiment_score).variant}>
                      {getSentimentBadge(response.sentiment_score).label}
                    </Badge>
                    <Badge className={getIntentBadge(response.intent)}>{response.intent}</Badge>
                  </div>
                </div>
                {response.priority_reason ? (
                  <p className="text-xs text-muted-foreground">{response.priority_reason}</p>
                ) : null}
              </CardHeader>

              <CardContent className="space-y-6 pt-6">
                <div>
                  <Label className="mb-2 block text-sm font-semibold">Customer Review</Label>
                  <div className="rounded-lg bg-muted p-4">
                    <p className="text-sm leading-relaxed">{response.review_text}</p>
                  </div>
                </div>

                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <Label className="flex items-center gap-2 text-sm font-semibold">
                      <Sparkles className="h-4 w-4 text-primary" />
                      AI-Generated Response
                      <Badge variant="outline" className="text-xs">
                        {response.tone}
                      </Badge>
                    </Label>
                    {editingResponse?.id !== response.id && (
                      <Button variant="ghost" size="sm" onClick={() => handleEdit(response)}>
                        <Edit3 className="mr-2 h-4 w-4" />
                        Edit
                      </Button>
                    )}
                  </div>

                  {editingResponse?.id === response.id ? (
                    <Textarea
                      value={editedDraft}
                      onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditedDraft(e.target.value)}
                      className="min-h-[150px]"
                      placeholder="Edit the AI-generated response..."
                    />
                  ) : (
                    <div className="rounded-lg border-2 border-primary/20 bg-primary/5 p-4">
                      <p className="whitespace-pre-wrap text-sm leading-relaxed">{response.ai_draft}</p>
                    </div>
                  )}
                </div>

                <div className="flex gap-2 pt-4">
                  <Button className="flex-1" onClick={() => handleApprove(response)} disabled={approveMutation.isPending}>
                    {approveMutation.isPending ? (
                      <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle className="mr-2 h-4 w-4" />
                    )}
                    Approve & Publish
                  </Button>
                  <Button variant="outline" onClick={() => setRejectingResponse(response)} disabled={rejectMutation.isPending}>
                    <XCircle className="mr-2 h-4 w-4" />
                    Reject
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* ── Failed Publishes Panel ─────────────────────────────────────────── */}
      {(failedData?.total ?? 0) > 0 ? (
        <>
          <Separator />
          <Card className="border-destructive/40">
            <CardHeader className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base text-destructive">
                    <XCircle className="h-4 w-4" />
                    Failed Publishes ({failedData!.total})
                  </CardTitle>
                  <CardDescription>
                    Review responses that failed to publish. Retry individually or in bulk.
                  </CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedFailedIds.size > 0 ? (
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={bulkRetryMutation.isPending}
                      onClick={() => bulkRetryMutation.mutate(Array.from(selectedFailedIds))}
                    >
                      {bulkRetryMutation.isPending ? (
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-4 w-4" />
                      )}
                      Retry {selectedFailedIds.size} selected
                    </Button>
                  ) : null}
                  {(failedData?.items.length ?? 0) > 0 ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-destructive/30 text-destructive hover:bg-destructive/5"
                      disabled={bulkRetryMutation.isPending}
                      onClick={() =>
                        bulkRetryMutation.mutate((failedData?.items ?? []).map((item) => item.id))
                      }
                    >
                      {bulkRetryMutation.isPending ? (
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-4 w-4" />
                      )}
                      Retry this page
                    </Button>
                  ) : (
                    <div className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
                      No failed responses on this page.
                    </div>
                  )}
                </div>
              </div>

              {/* Error category summary */}
              {Object.keys(failedData?.error_category_counts ?? {}).length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(failedData!.error_category_counts).map(([cat, count]) => (
                    <Badge key={cat} variant="outline" className="border-destructive/30 text-destructive/80 text-xs">
                      {ERROR_CATEGORY_LABELS[cat]?.label ?? cat}: {count}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {/* Search + platform filter */}
              <div className="grid gap-3 md:grid-cols-3">
                <div className="relative md:col-span-2">
                  <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    placeholder="Search by author, error message, or review text"
                    value={failedSearch}
                    onChange={(e) => {
                      setFailedSearch(e.target.value);
                      setFailedOffset(0);
                    }}
                  />
                </div>
                <div className="flex flex-wrap gap-2 md:justify-end">
                  {(['all', 'google', 'facebook', 'yelp'] as const).map((p) => (
                    <Button
                      key={p}
                      size="sm"
                      variant={failedPlatform === p ? 'default' : 'outline'}
                      onClick={() => {
                        setFailedPlatform(p);
                        setFailedOffset(0);
                      }}
                    >
                      {p === 'all' ? 'All platforms' : p}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Select all / deselect all */}
              {(failedData?.items.length ?? 0) > 0 ? (
                <div className="flex items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    id="select-all-failed"
                    className="h-4 w-4 cursor-pointer accent-destructive"
                    checked={
                      failedData!.items.length > 0 &&
                      failedData!.items.every((item) => selectedFailedIds.has(item.id))
                    }
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedFailedIds(new Set(failedData!.items.map((item) => item.id)));
                      } else {
                        setSelectedFailedIds(new Set());
                      }
                    }}
                  />
                  <label htmlFor="select-all-failed" className="cursor-pointer text-muted-foreground">
                    Select all on this page ({failedData!.items.length})
                  </label>
                </div>
              ) : null}
            </CardHeader>

            <CardContent className="space-y-3 pt-0">
              {bulkRetryMutation.data ? (
                <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm">
                  <span className="font-semibold text-green-800">
                    Bulk retry complete: {bulkRetryMutation.data.succeeded} succeeded,{' '}
                    {bulkRetryMutation.data.still_failed} still failed,{' '}
                    {bulkRetryMutation.data.skipped} skipped
                  </span>
                </div>
              ) : summary?.last_bulk_retry_at ? (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  Last bulk retry{' '}
                  <span className="font-medium">{new Date(summary.last_bulk_retry_at).toLocaleString()}</span>
                  {': '}
                  <span className="font-medium text-green-700">{summary.last_bulk_retry_succeeded ?? 0} succeeded</span>
                  {', '}
                  <span className={summary.last_bulk_retry_still_failed ? 'font-medium text-red-600' : ''}>
                    {summary.last_bulk_retry_still_failed ?? 0} still failed
                  </span>
                  {' of '}
                  {summary.last_bulk_retry_total ?? 0} attempted
                </div>
              ) : null}

              {(failedData?.items ?? []).map((item: FailedResponseItem) => {
                const catMeta = ERROR_CATEGORY_LABELS[item.error_category] ?? ERROR_CATEGORY_LABELS.unknown;
                const isSelected = selectedFailedIds.has(item.id);
                return (
                  <div
                    key={item.id}
                    className={`flex flex-col gap-3 rounded-lg border p-4 transition-colors ${
                      isSelected ? 'border-destructive/60 bg-destructive/5' : 'border-destructive/20 bg-background'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4 cursor-pointer accent-destructive"
                        checked={isSelected}
                        onChange={(e) => {
                          const next = new Set(selectedFailedIds);
                          if (e.target.checked) next.add(item.id);
                          else next.delete(item.id);
                          setSelectedFailedIds(next);
                        }}
                      />
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold">{item.review_author || 'Customer'}</span>
                          <Badge variant="outline">{item.platform}</Badge>
                          <Badge variant="destructive" className="text-xs">
                            {catMeta.label}
                          </Badge>
                          {item.high_priority ? (
                            <Badge variant="destructive" className="text-xs">High priority</Badge>
                          ) : null}
                        </div>
                        {item.publish_error ? (
                          <p className="text-xs text-destructive/80 line-clamp-2">
                            {getPublishErrorMessage(item.publish_error)}
                          </p>
                        ) : (
                          <p className="text-xs text-muted-foreground">
                            {catMeta.hint}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground line-clamp-1">
                          Review: &ldquo;{item.review_text}&rdquo;
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        className="shrink-0 border-destructive/30 text-destructive hover:bg-destructive/10"
                        disabled={retryMutation.isPending && retryingId === item.id}
                        onClick={() => retryMutation.mutate(item.id)}
                      >
                        {retryMutation.isPending && retryingId === item.id ? (
                          <RefreshCw className="h-3 w-3 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3 w-3" />
                        )}
                        <span className="ml-1">Retry</span>
                      </Button>
                    </div>
                  </div>
                );
              })}

              {/* Pagination */}
              {failedData && failedData.total > failedData.limit ? (
                <div className="flex items-center justify-between pt-2 text-sm text-muted-foreground">
                  <span>
                    Showing {failedData.items.length} of {failedData.total}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setFailedOffset(Math.max(failedOffset - failedData.limit, 0))}
                      disabled={failedOffset === 0}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setFailedOffset(failedOffset + failedData.limit)}
                      disabled={failedOffset + failedData.limit >= failedData.total}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </>
      ) : null}

      <Separator />

      <Card className="border-dashed">
        <CardHeader className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Response History</CardTitle>
              <CardDescription>Search, export, and inspect published or failed review responses.</CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={exportHistory}>
              <Download className="mr-2 h-4 w-4" />
              Export CSV
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="relative md:col-span-2">
              <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder="Search by review, draft, error, or author"
                value={historySearch}
                onChange={(event) => {
                  setHistorySearch(event.target.value);
                  setHistoryOffset(0);
                }}
              />
            </div>
            <div className="flex flex-wrap gap-2 md:justify-end">
              {['all', 'pending', 'approved', 'rejected', 'published', 'failed'].map((statusValue) => (
                <Button
                  key={statusValue}
                  size="sm"
                  variant={historyStatus === statusValue ? 'default' : 'outline'}
                  onClick={() => {
                    setHistoryStatus(statusValue);
                    setHistoryOffset(0);
                  }}
                >
                  {statusValue}
                </Button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant={historyHighPriorityOnly ? 'default' : 'outline'}
              onClick={() => {
                setHistoryHighPriorityOnly((current) => !current);
                setHistoryOffset(0);
              }}
            >
              <Filter className="mr-2 h-4 w-4" />
              High priority only
            </Button>
            {['all', 'google', 'facebook', 'yelp'].map((platform) => (
              <Button
                key={platform}
                size="sm"
                variant={historyPlatform === platform ? 'default' : 'outline'}
                onClick={() => {
                  setHistoryPlatform(platform);
                  setHistoryOffset(0);
                }}
              >
                {platform === 'all' ? 'All platforms' : platform}
              </Button>
            ))}
          </div>
        </CardHeader>
      </Card>

      {historyItems.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Clock3 className="mb-4 h-12 w-12 text-muted-foreground" />
            <h3 className="mb-2 text-lg font-semibold">No history yet</h3>
            <p className="text-center text-muted-foreground">
              Published, rejected, and failed responses will appear here once the queue is used.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {historyItems.map((response) => (
            <Card key={response.id} className="overflow-hidden">
              <CardHeader className="bg-muted/50">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold">{response.review_author || 'Customer'}</span>
                      <Badge variant="outline">{response.platform}</Badge>
                      <Badge variant={response.priority_level === 'high' ? 'destructive' : 'secondary'}>
                        {response.priority_level || 'normal'}
                      </Badge>
                      <Badge variant="outline">{response.status}</Badge>
                    </div>
                    <CardDescription className="flex flex-wrap items-center gap-2">
                      <span>{response.review_date ? new Date(response.review_date).toLocaleDateString() : 'No date'}</span>
                      <span>•</span>
                      <span>{response.created_at ? new Date(response.created_at).toLocaleString() : 'Unknown time'}</span>
                    </CardDescription>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => setSelectedHistoryResponse(response)}>
                    View details
                  </Button>
                </div>
                {response.priority_reason ? (
                  <p className="text-xs text-muted-foreground">{response.priority_reason}</p>
                ) : null}
              </CardHeader>
              <CardContent className="space-y-4 pt-6">
                {response.status === 'failed' && response.publish_error ? (
                  <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3">
                    <p className="text-xs font-semibold text-destructive">Publish failed</p>
                    <p className="mt-1 text-xs text-destructive/80">{getPublishErrorMessage(response.publish_error)}</p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2 border-destructive/30 text-destructive hover:bg-destructive/10"
                      onClick={() => retryMutation.mutate(response.id)}
                      disabled={retryMutation.isPending && retryingId === response.id}
                    >
                      {retryMutation.isPending && retryingId === response.id ? (
                        <RefreshCw className="mr-2 h-3 w-3 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-3 w-3" />
                      )}
                      Retry publish
                    </Button>
                  </div>
                ) : null}
                {response.status === 'failed' && !response.publish_error ? (
                  <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3">
                    <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />
                    <p className="text-xs text-destructive/80">Publish failed — no error detail recorded.</p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="ml-auto border-destructive/30 text-destructive hover:bg-destructive/10"
                      onClick={() => retryMutation.mutate(response.id)}
                      disabled={retryMutation.isPending && retryingId === response.id}
                    >
                      {retryMutation.isPending && retryingId === response.id ? (
                        <RefreshCw className="mr-2 h-3 w-3 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-3 w-3" />
                      )}
                      Retry publish
                    </Button>
                  </div>
                ) : null}
                <div className="grid gap-3 md:grid-cols-2">
                  <div>
                    <Label className="mb-2 block text-sm font-semibold">AI Draft</Label>
                    <div className="rounded-lg border bg-background p-4">
                      <p className="line-clamp-3 whitespace-pre-wrap text-sm leading-relaxed">{response.ai_draft}</p>
                    </div>
                  </div>
                  <div>
                    <Label className="mb-2 block text-sm font-semibold">Review Text</Label>
                    <div className="rounded-lg border bg-background p-4">
                      <p className="line-clamp-3 whitespace-pre-wrap text-sm leading-relaxed">{response.review_text}</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {historyResponse ? (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Showing {historyResponse.items.length} of {historyResponse.total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setHistoryOffset(Math.max(historyOffset - historyResponse.limit, 0))}
              disabled={historyOffset === 0}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setHistoryOffset(historyOffset + historyResponse.limit)}
              disabled={historyOffset + historyResponse.limit >= historyResponse.total}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}

      <Dialog open={!!selectedHistoryResponse} onOpenChange={() => setSelectedHistoryResponse(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Review Response Detail</DialogTitle>
            <DialogDescription>
              Operator view of the saved response, priority, and publish state.
            </DialogDescription>
          </DialogHeader>
          {selectedHistoryResponse ? (
            <div className="space-y-4 py-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{selectedHistoryResponse.platform}</Badge>
                <Badge variant={selectedHistoryResponse.priority_level === 'high' ? 'destructive' : 'secondary'}>
                  {selectedHistoryResponse.priority_level || 'normal'}
                </Badge>
                <Badge variant="outline">{selectedHistoryResponse.status}</Badge>
                <Badge variant={getSentimentBadge(selectedHistoryResponse.sentiment_score).variant}>
                  {getSentimentBadge(selectedHistoryResponse.sentiment_score).label}
                </Badge>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label className="mb-2 block text-sm font-semibold">Customer Review</Label>
                  <div className="rounded-lg border bg-muted p-4">
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">{selectedHistoryResponse.review_text}</p>
                  </div>
                </div>
                <div>
                  <Label className="mb-2 block text-sm font-semibold">AI Draft</Label>
                  <div className="rounded-lg border bg-muted p-4">
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">{selectedHistoryResponse.ai_draft}</p>
                  </div>
                </div>
              </div>
              {selectedHistoryResponse.status === 'failed' ? (
                <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3">
                  <p className="text-sm font-semibold text-destructive">Publish failed</p>
                  <p className="mt-1 text-sm text-destructive/80">
                    {selectedHistoryResponse.publish_error
                      ? getPublishErrorMessage(selectedHistoryResponse.publish_error)
                      : 'No error detail recorded.'}
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-3 border-destructive/30 text-destructive hover:bg-destructive/10"
                    onClick={() => {
                      retryMutation.mutate(selectedHistoryResponse.id);
                      setSelectedHistoryResponse(null);
                    }}
                    disabled={retryMutation.isPending}
                  >
                    <RefreshCw className="mr-2 h-3 w-3" />
                    Retry publish
                  </Button>
                </div>
              ) : null}
              <div className="grid gap-3 md:grid-cols-2 text-sm">
                <div>
                  <p className="font-semibold">Priority reason</p>
                  <p className="text-muted-foreground">{selectedHistoryResponse.priority_reason || 'Normal queue item'}</p>
                </div>
                <div>
                  <p className="font-semibold">Published at</p>
                  <p className="text-muted-foreground">
                    {selectedHistoryResponse.published_at
                      ? new Date(selectedHistoryResponse.published_at).toLocaleString()
                      : 'Not published yet'}
                  </p>
                </div>
                <div>
                  <p className="font-semibold">Approved at</p>
                  <p className="text-muted-foreground">
                    {selectedHistoryResponse.approved_at
                      ? new Date(selectedHistoryResponse.approved_at).toLocaleString()
                      : 'Not approved yet'}
                  </p>
                </div>
                <div>
                  <p className="font-semibold">Platform response ID</p>
                  <p className="text-muted-foreground">{selectedHistoryResponse.platform_response_id || 'N/A'}</p>
                </div>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedHistoryResponse(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!rejectingResponse} onOpenChange={() => setRejectingResponse(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Response</DialogTitle>
            <DialogDescription>
              Please provide a reason for rejecting this AI-generated response.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <Textarea
              value={rejectionReason}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setRejectionReason(e.target.value)}
              placeholder="e.g., Tone is too formal, missing key details..."
              className="min-h-[100px]"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectingResponse(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={!rejectionReason.trim() || rejectMutation.isPending}
            >
              {rejectMutation.isPending ? (
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <XCircle className="mr-2 h-4 w-4" />
              )}
              Reject Response
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
