'use client';
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle,
  Clock3,
  Download,
  Filter,
  Image as ImageIcon,
  Instagram,
  RefreshCw,
  Search,
  Share2,
  Sparkles,
  Star,
  XCircle,
} from 'lucide-react';
import { socialProofApi, type SocialProofCard } from '@/lib/api/ai-features';
import { extractCollectionPayload, locationsApi } from '@/lib/api';
import { getAccessToken } from '@/lib/auth-token';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

interface LocationOption {
  id: string;
  name: string;
}

type SocialProofHistoryCard = Omit<SocialProofCard, 'approved_at' | 'published_at'> & {
  approved_at?: string | null;
  published_at?: string | null;
  rejection_reason?: string | null;
  published_to?: string | null;
  platform_post_id?: string | null;
  updated_at?: string;
  generated_by_ai?: string;
};

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
  last_published_at: string | null;
  last_rejected_at: string | null;
  last_pending_at: string | null;
}

interface SocialProofHistoryResponse {
  items: SocialProofHistoryCard[];
  total: number;
  limit: number;
  offset: number;
  status_filter: string;
  search: string | null;
  metrics: SocialProofMetrics;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const HISTORY_PAGE_SIZE = 12;

function getStatusBadgeVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'published':
      return 'default';
    case 'approved':
      return 'secondary';
    case 'rejected':
      return 'destructive';
    case 'attention':
      return 'destructive';
    default:
      return 'outline';
  }
}

function formatDateTime(value?: string | null) {
  if (!value) return 'Unknown';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Unknown' : parsed.toLocaleString();
}

function formatRelativeLabel(value?: string | null) {
  if (!value) return 'Unknown';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Unknown';
  const diffMinutes = Math.max(1, Math.floor((Date.now() - parsed.getTime()) / 60000));
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}

function getStatusForCard(card: Pick<SocialProofHistoryCard, 'status' | 'updated_at'>) {
  return card.status === 'pending' &&
    card.updated_at &&
    new Date(card.updated_at).getTime() < Date.now() - 24 * 60 * 60 * 1000
    ? 'attention'
    : card.status;
}

export default function SocialProofPage() {
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [locationsLoading, setLocationsLoading] = useState(true);
  const [selectedLocationId, setSelectedLocationId] = useState<string>('');
  const [selectedCard, setSelectedCard] = useState<SocialProofHistoryCard | null>(null);
  const [rejectingCard, setRejectingCard] = useState<SocialProofHistoryCard | null>(null);
  const [rejectionReason, setRejectionReason] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'attention' | 'draft' | 'pending' | 'approved' | 'rejected' | 'published'>('all');
  const [search, setSearch] = useState('');
  const [pageOffset, setPageOffset] = useState(0);

  const queryClient = useQueryClient();
  const activeLocationId = selectedLocationId || locations[0]?.id || '';

  useEffect(() => {
    const loadLocations = async () => {
      try {
        const response = await locationsApi.list();
        const nextLocations = extractCollectionPayload<LocationOption>(response.data, 'locations');
        setLocations(nextLocations);
        setSelectedLocationId((current) => current || nextLocations[0]?.id || '');
      } catch (error) {
        console.error('Failed to load locations for social proof:', error);
      } finally {
        setLocationsLoading(false);
      }
    };

    void loadLocations();
  }, []);

  useEffect(() => {
    setPageOffset(0);
  }, [activeLocationId, statusFilter, search]);

  const authFetchJson = async <T,>(path: string): Promise<T> => {
    const token = getAccessToken();
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Request failed with status ${response.status}`);
    }
    return response.json() as Promise<T>;
  };

  const { data: history, isLoading, error } = useQuery({
    queryKey: ['social-proof-history', activeLocationId, statusFilter, search, pageOffset],
    queryFn: () => {
      const params = new URLSearchParams({
        limit: String(HISTORY_PAGE_SIZE),
        offset: String(pageOffset),
        status_filter: statusFilter,
      });
      if (search.trim()) {
        params.set('search', search.trim());
      }
      return authFetchJson<SocialProofHistoryResponse>(`/social-proof/history/${activeLocationId}?${params.toString()}`);
    },
    enabled: !locationsLoading && !!activeLocationId,
    refetchInterval: 30000,
  });

  const autoGenerateMutation = useMutation({
    mutationFn: async () =>
      socialProofApi.autoGenerate({
        location_id: activeLocationId,
        days_back: 30,
        min_rating: 5,
        max_cards: 3,
        min_text_length: 50,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['social-proof-history', activeLocationId] });
    },
  });

  const approveMutation = useMutation({
    mutationFn: ({ id, publish }: { id: number; publish: boolean }) =>
      socialProofApi.approve(id, publish),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['social-proof-history', activeLocationId] });
      setSelectedCard(null);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      socialProofApi.reject(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['social-proof-history', activeLocationId] });
      setRejectingCard(null);
      setRejectionReason('');
    },
  });

  const handleDownload = async (url?: string | null, cardId?: number) => {
    if (!url) return;
    try {
      const response = await fetch(url);
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `social-proof-card-${cardId || 'card'}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  const handleReject = () => {
    if (rejectingCard && rejectionReason.trim()) {
      rejectMutation.mutate({
        id: rejectingCard.id,
        reason: rejectionReason,
      });
    }
  };

  const metrics = history?.metrics;
  const pendingCount = metrics?.pending_count || 0;
  const selectedLocation = locations.find((location) => location.id === activeLocationId) || null;
  const selectedCardStatus = selectedCard ? getStatusForCard(selectedCard) : 'draft';

  if (locationsLoading || isLoading) {
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
              Create or connect a business location before managing social proof cards.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Failed to load social proof history</h1>
          <p className="mt-2 text-muted-foreground">
            The workspace could not load the saved card history for this location.
          </p>
        </div>
        <Button onClick={() => queryClient.invalidateQueries({ queryKey: ['social-proof-history', activeLocationId] })}>
          Retry
        </Button>
      </div>
    );
  }

  const totalPages = history ? Math.max(1, Math.ceil(history.total / history.limit)) : 1;
  const currentPage = history ? Math.floor(history.offset / history.limit) + 1 : 1;
  const canGoPrev = (history?.offset || 0) > 0;
  const canGoNext = history ? history.offset + history.limit < history.total : false;

  const filterButtons: Array<{
    label: string;
    value: typeof statusFilter;
    count?: number;
  }> = [
    { label: 'All', value: 'all', count: metrics?.total_cards },
    { label: 'Attention', value: 'attention', count: metrics?.attention_required_count },
    { label: 'Draft', value: 'draft', count: metrics?.draft_count },
    { label: 'Pending', value: 'pending', count: metrics?.pending_count },
    { label: 'Approved', value: 'approved', count: metrics?.approved_count },
    { label: 'Published', value: 'published', count: metrics?.published_count },
    { label: 'Rejected', value: 'rejected', count: metrics?.rejected_count },
  ];

  return (
    <div className="container mx-auto space-y-8 py-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Social Proof Cards</h1>
          <p className="mt-2 text-muted-foreground">
            Manage generated cards, see published results, and review anything that still needs attention.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={pendingCount > 0 ? 'default' : 'secondary'} className="px-4 py-2 text-lg">
            {pendingCount} Pending
          </Badge>
          <Button onClick={() => autoGenerateMutation.mutate()} disabled={autoGenerateMutation.isPending}>
            {autoGenerateMutation.isPending ? (
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-2 h-4 w-4" />
            )}
            Auto-Generate
          </Button>
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Social Proof Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {pendingCount > 0 ? 'Approve the strongest proof card first' : 'Generate one proof card from real customer signals'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Use this page to turn reviews and outcomes into public trust assets. Keep weak or unclear cards out of the website and social channels.
            </p>
          </div>
          <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={() => autoGenerateMutation.mutate()} disabled={autoGenerateMutation.isPending}>
            {autoGenerateMutation.isPending ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
            Generate card
          </Button>
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

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Cards</CardTitle>
            <ImageIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.total_cards ?? 0}</div>
            <p className="mt-2 text-xs text-muted-foreground">Saved cards for this location</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.pending_count ?? 0}</div>
            <p className="mt-2 text-xs text-muted-foreground">Awaiting review</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Published</CardTitle>
            <Share2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.published_count ?? 0}</div>
            <p className="mt-2 text-xs text-muted-foreground">Already published cards</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Rejected</CardTitle>
            <XCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.rejected_count ?? 0}</div>
            <p className="mt-2 text-xs text-muted-foreground">Cards not approved for publishing</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Needs Attention</CardTitle>
            <Filter className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.attention_required_count ?? 0}</div>
            <p className="mt-2 text-xs text-muted-foreground">Pending or draft for more than a day</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Selected Location</CardTitle>
            <Instagram className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="truncate text-2xl font-bold">{selectedLocation?.name || '-'}</div>
            <p className="mt-2 text-xs text-muted-foreground">Current review queue scope</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle>History</CardTitle>
              <CardDescription>
                Saved cards by status, search, and operational priority. Published and rejected cards stay visible here.
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Approval rate {metrics ? `${metrics.approval_rate}%` : '0%'}</Badge>
              <Badge variant="outline">Publish rate {metrics ? `${metrics.publish_rate}%` : '0%'}</Badge>
              <Badge variant="outline">Last published {formatRelativeLabel(metrics?.last_published_at)}</Badge>
            </div>
          </div>

          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search title, review, author, reason, or platform post id"
                className="pl-9"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {filterButtons.map((button) => (
                <Button
                  key={button.value}
                  variant={statusFilter === button.value ? 'default' : 'outline'}
                  onClick={() => setStatusFilter(button.value)}
                  className="gap-2"
                >
                  {button.label}
                  {typeof button.count === 'number' ? <Badge variant="secondary">{button.count}</Badge> : null}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {history && history.items.length > 0 ? (
            <>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {history.items.map((card) => {
                  const effectiveStatus = getStatusForCard(card);
                  return (
                    <Card key={card.id} className="overflow-hidden">
                      <div className="relative aspect-square bg-muted">
                        {card.final_card_url ? (
                          <img src={card.final_card_url} alt={card.card_title} className="h-full w-full object-cover" />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center">
                            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                          </div>
                        )}
                        <div className="absolute left-3 top-3 flex flex-wrap gap-2">
                          <Badge variant={getStatusBadgeVariant(effectiveStatus)}>
                            {effectiveStatus}
                          </Badge>
                          <Badge variant="outline">{card.layout_style}</Badge>
                        </div>
                      </div>
                      <CardHeader>
                        <div className="space-y-2">
                          <CardTitle className="text-base">{card.card_title}</CardTitle>
                          <CardDescription className="flex flex-wrap items-center gap-2">
                            <span className="flex items-center gap-1">
                              <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                              {card.review_rating}/5
                            </span>
                            <span>by {card.review_author || 'Customer'}</span>
                          </CardDescription>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <p className="line-clamp-3 text-sm text-muted-foreground">{card.card_text}</p>
                        <div className="space-y-1 text-xs text-muted-foreground">
                          <p>Created: {formatDateTime(card.created_at)}</p>
                          <p>Updated: {formatDateTime(card.updated_at)}</p>
                          {card.published_at ? <p>Published: {formatDateTime(card.published_at)}</p> : null}
                          {card.rejection_reason ? <p>Rejected: {card.rejection_reason}</p> : null}
                          {card.published_to ? <p>Published to: {card.published_to}</p> : null}
                          {card.platform_post_id ? <p>Platform post id: {card.platform_post_id}</p> : null}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" className="flex-1" onClick={() => setSelectedCard(card)}>
                            View
                          </Button>
                          {card.final_card_url ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleDownload(card.final_card_url, card.id)}
                            >
                              <Download className="mr-2 h-4 w-4" />
                              Download
                            </Button>
                          ) : (
                            <div className="flex items-center rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
                              Card image is still generating.
                            </div>
                          )}
                        </div>
                        {(card.status === 'pending' || card.status === 'draft') && (
                          <div className="flex gap-2 pt-1">
                            <Button
                              size="sm"
                              className="flex-1"
                              onClick={() => approveMutation.mutate({ id: card.id, publish: false })}
                              disabled={approveMutation.isPending}
                            >
                              <CheckCircle className="mr-2 h-4 w-4" />
                              Approve
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setRejectingCard(card)}>
                              <XCircle className="mr-2 h-4 w-4" />
                              Reject
                            </Button>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

              <div className="flex flex-col gap-3 border-t pt-4 md:flex-row md:items-center md:justify-between">
                <p className="text-sm text-muted-foreground">
                  Showing {history.items.length} of {history.total} cards
                  {' '}
                  {search ? `for "${search}"` : ''}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setPageOffset((prev) => Math.max(prev - history.limit, 0))}
                    disabled={!canGoPrev}
                  >
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Page {currentPage} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    onClick={() => setPageOffset((prev) => prev + history.limit)}
                    disabled={!canGoNext}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <CheckCircle className="mb-4 h-12 w-12 text-green-500" />
                <h3 className="mb-2 text-lg font-semibold">
                  {search || statusFilter !== 'all' ? 'No cards match these filters' : 'All Caught Up'}
                </h3>
                <p className="mb-4 text-center text-muted-foreground">
                  {search || statusFilter !== 'all'
                    ? 'Try widening the search or switching to a different status filter.'
                    : 'No social proof cards are waiting for review right now.'}
                </p>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!selectedCard} onOpenChange={() => setSelectedCard(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedCard?.card_title}</DialogTitle>
            <DialogDescription>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <div className="flex">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Star
                      key={i}
                      className={`h-4 w-4 ${
                        i < (selectedCard?.review_rating || 0) ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'
                      }`}
                    />
                  ))}
                </div>
                <span>by {selectedCard?.review_author || 'Customer'}</span>
                <Badge variant={getStatusBadgeVariant(selectedCardStatus)}>
                  {selectedCardStatus}
                </Badge>
              </div>
            </DialogDescription>
          </DialogHeader>

          {selectedCard && (
            <div className="space-y-4">
              {selectedCard.final_card_url ? (
                <img src={selectedCard.final_card_url} alt={selectedCard.card_title} className="w-full rounded-lg" />
              ) : (
                <div className="flex h-72 items-center justify-center rounded-lg bg-muted">
                  <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              )}
              <div className="space-y-2">
                <h4 className="text-sm font-semibold">Original Review</h4>
                <p className="text-sm text-muted-foreground">{selectedCard.review_text}</p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Card>
                  <CardContent className="pt-6 text-sm">
                    <p className="text-muted-foreground">Created</p>
                    <p className="font-medium">{formatDateTime(selectedCard.created_at)}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6 text-sm">
                    <p className="text-muted-foreground">Last updated</p>
                    <p className="font-medium">{formatDateTime(selectedCard.updated_at)}</p>
                  </CardContent>
                </Card>
                {selectedCard.published_at ? (
                  <Card>
                    <CardContent className="pt-6 text-sm">
                      <p className="text-muted-foreground">Published at</p>
                      <p className="font-medium">{formatDateTime(selectedCard.published_at)}</p>
                    </CardContent>
                  </Card>
                ) : null}
                {selectedCard.rejection_reason ? (
                  <Card>
                    <CardContent className="pt-6 text-sm">
                      <p className="text-muted-foreground">Rejection reason</p>
                      <p className="font-medium">{selectedCard.rejection_reason}</p>
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            {selectedCard?.final_card_url ? (
              <Button variant="outline" onClick={() => handleDownload(selectedCard.final_card_url, selectedCard.id)}>
                <Download className="mr-2 h-4 w-4" />
                Download
              </Button>
            ) : (
              <div className="flex items-center rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
                Download becomes available after the card image finishes generating.
              </div>
            )}
            {(selectedCard?.status === 'pending' || selectedCard?.status === 'draft') && (
              <>
                <Button variant="outline" onClick={() => setRejectingCard(selectedCard)}>
                  <XCircle className="mr-2 h-4 w-4" />
                  Reject
                </Button>
                <Button onClick={() => selectedCard && approveMutation.mutate({ id: selectedCard.id, publish: false })} disabled={approveMutation.isPending}>
                  {approveMutation.isPending ? (
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle className="mr-2 h-4 w-4" />
                  )}
                  Approve
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!rejectingCard} onOpenChange={() => setRejectingCard(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Card</DialogTitle>
            <DialogDescription>
              Please provide a reason for rejecting this social proof card.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <Textarea
              value={rejectionReason}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setRejectionReason(e.target.value)}
              placeholder="Explain what should change before this card is approved..."
              className="min-h-[100px]"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectingCard(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleReject} disabled={!rejectionReason.trim() || rejectMutation.isPending}>
              {rejectMutation.isPending ? (
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <XCircle className="mr-2 h-4 w-4" />
              )}
              Reject Card
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
