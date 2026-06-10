'use client';

import { useEffect, useState } from 'react';
import {
  AlertCircle,
  Code,
  Copy,
  Archive,
  ExternalLink,
  FileText,
  Globe,
  Loader2,
  Search,
  Sparkles,
  Tag,
} from 'lucide-react';

import { extractCollectionPayload, websiteSeoApi, locationsApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';

interface LocationOption {
  id: string;
  name: string;
}

interface ChannelStatus {
  id: string;
  type: string;
  status: string;
  error_message?: string | null;
  last_publish_succeeded_at?: string | null;
}

interface SeoHistoryItem {
  id: string;
  content_type: string;
  status: string;
  title?: string | null;
  slug?: string | null;
  page_type?: string | null;
  source_topic?: string | null;
  published_url?: string | null;
  provider_reference?: string | null;
  last_error?: string | null;
  approval_status?: string;
  approval_requested_at?: string | null;
  approved_at?: string | null;
  rejected_at?: string | null;
  rejection_reason?: string | null;
  published_at?: string | null;
  archived_at?: string | null;
  archived_reason?: string | null;
  created_at?: string | null;
}

interface SeoHistoryPayload {
  items: SeoHistoryItem[];
  count: number;
  total: number;
  limit: number;
  offset: number;
}

interface SeoMetaTagsDraft {
  title: string;
  description: string;
  schema_json: string;
  draft_id?: string;
}

interface SeoApprovalDraft {
  draft_id?: string;
  approval_status?: string;
  rejection_reason?: string | null;
}

interface SeoBlogDraft extends SeoApprovalDraft {
  title: string;
  slug?: string | null;
  word_count: number;
  meta_description?: string | null;
  keywords?: string[];
  content_markdown: string;
}

interface SeoServicePageDraft extends SeoApprovalDraft {
  service_name: string;
  keywords?: string[];
  content_html: string;
}

interface SeoOptimizationRecommendation {
  type: string;
  priority: string;
  message: string;
}

interface SeoPageOptimizationDraft {
  draft_id?: string;
  page_url: string;
  analysis?: {
    word_count?: number;
    has_h1?: boolean;
    has_h2?: boolean;
  };
  recommendations?: SeoOptimizationRecommendation[];
  target_keywords?: string[];
  suggested_meta_tags?: {
    title?: string;
    description?: string;
  };
}

interface SeoDraftRecord {
  id: string;
  content_type: 'meta_tags' | 'blog_post' | 'service_page' | 'optimization' | string;
  approval_status?: string;
  rejection_reason?: string | null;
  payload?: Record<string, unknown>;
}

export default function SEOPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState('keywords');
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [locationId, setLocationId] = useState<string>('');
  const [keywords, setKeywords] = useState<string[]>([]);
  const [metaTags, setMetaTags] = useState<SeoMetaTagsDraft | null>(null);
  const [generatedBlog, setGeneratedBlog] = useState<SeoBlogDraft | null>(null);
  const [generatedServicePage, setGeneratedServicePage] = useState<SeoServicePageDraft | null>(null);
  const [pageOptimization, setPageOptimization] = useState<SeoPageOptimizationDraft | null>(null);
  const [seoHistory, setSeoHistory] = useState<SeoHistoryItem[]>([]);
  const [seoHistoryMeta, setSeoHistoryMeta] = useState<SeoHistoryPayload>({
    items: [],
    count: 0,
    total: 0,
    limit: 8,
    offset: 0,
  });
  const [historyStatusFilter, setHistoryStatusFilter] = useState<string>('all');
  const [historyApprovalFilter, setHistoryApprovalFilter] = useState<string>('all');
  const [historyContentTypeFilter, setHistoryContentTypeFilter] = useState<string>('all');
  const [historySearch, setHistorySearch] = useState('');
  const [historyView, setHistoryView] = useState<'all' | 'failed' | 'archived'>('all');
  const [selectedArchiveIds, setSelectedArchiveIds] = useState<string[]>([]);
  const [seoStatusMessage, setSeoStatusMessage] = useState<string | null>(null);
  const [websiteChannel, setWebsiteChannel] = useState<ChannelStatus | null>(null);
  const [isBlogDialogOpen, setIsBlogDialogOpen] = useState(false);
  const [isServiceDialogOpen, setIsServiceDialogOpen] = useState(false);
  const [isOptimizeDialogOpen, setIsOptimizeDialogOpen] = useState(false);
  const [blogTopic, setBlogTopic] = useState('');
  const [serviceName, setServiceName] = useState('');
  const [serviceDescription, setServiceDescription] = useState('');
  const [pageUrl, setPageUrl] = useState('');
  const [pageContent, setPageContent] = useState('');
  const hasLocations = locations.length > 0;

  useEffect(() => {
    const loadLocations = async () => {
      try {
        const response = await locationsApi.list();
        const items = extractCollectionPayload<LocationOption>(response.data, 'locations');
        setLocations(items);

        if (items.length > 0) {
          setLocationId(items[0].id);
        } else {
          setSeoStatusMessage('Add a location first to use Website SEO tools.');
        }
      } catch {
        setSeoStatusMessage('Website SEO tools could not be loaded right now. Open Integrations to connect the Website channel and try again.');
      } finally {
        setIsLoading(false);
      }
    };

    void loadLocations();
  }, []);

  useEffect(() => {
    const loadKeywords = async () => {
      if (!locationId) {
        setKeywords([]);
        return;
      }

      try {
        const response = await websiteSeoApi.getKeywords(locationId);
        setKeywords(Array.isArray(response.data.keywords) ? response.data.keywords : []);
        setSeoStatusMessage(null);
      } catch {
        setKeywords([]);
        setSeoStatusMessage('Website SEO keyword suggestions are unavailable for this location until the Website channel is connected. Open Integrations to reconnect and try again.');
      }
    };

    void loadKeywords();
  }, [locationId]);

  useEffect(() => {
    const loadChannels = async () => {
      if (!locationId) {
        setWebsiteChannel(null);
        return;
      }

      try {
        const response = await locationsApi.listChannels(locationId);
        const channels = extractCollectionPayload<ChannelStatus>(response.data, 'channels');
        setWebsiteChannel(channels.find((channel: ChannelStatus) => channel.type === 'WEBSITE') || null);
      } catch {
        setWebsiteChannel(null);
      }
    };

    void loadChannels();
  }, [locationId]);

  useEffect(() => {
    const loadHistory = async () => {
      if (!locationId) {
        setSeoHistory([]);
        setSelectedArchiveIds([]);
        setSeoHistoryMeta((current) => ({ ...current, items: [], count: 0, total: 0, offset: 0 }));
        return;
      }

      try {
        const response = await websiteSeoApi.getHistory(locationId, {
          limit: seoHistoryMeta.limit,
          offset: seoHistoryMeta.offset,
          content_type: historyContentTypeFilter !== 'all' ? historyContentTypeFilter : undefined,
          status: historyView === 'failed' ? 'failed' : historyView === 'archived' ? 'archived' : historyStatusFilter !== 'all' ? historyStatusFilter : undefined,
          approval_status: historyApprovalFilter !== 'all' ? historyApprovalFilter : undefined,
          search: historySearch || undefined,
        });
        setSeoHistory(Array.isArray(response.data.items) ? response.data.items : []);
        setSelectedArchiveIds((current) =>
          current.filter((draftId) => response.data.items?.some((item: SeoHistoryItem) => item.id === draftId))
        );
        setSeoHistoryMeta({
          items: Array.isArray(response.data.items) ? response.data.items : [],
          count: response.data.count || 0,
          total: response.data.total || 0,
          limit: response.data.limit || 8,
          offset: response.data.offset || 0,
        });
      } catch {
        setSeoHistory([]);
        setSeoHistoryMeta((current) => ({ ...current, items: [], count: 0, total: 0 }));
      }
    };

    void loadHistory();
  }, [locationId, seoHistoryMeta.offset, seoHistoryMeta.limit, historyStatusFilter, historyApprovalFilter, historyContentTypeFilter, historySearch, historyView]);

  const websitePublishReady =
    !!websiteChannel && !['disconnected', 'error', 'expired'].includes(websiteChannel.status);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const refreshHistory = async () => {
    if (!locationId) return;
    const history = await websiteSeoApi.getHistory(locationId, {
      limit: seoHistoryMeta.limit,
      offset: seoHistoryMeta.offset,
      content_type: historyContentTypeFilter !== 'all' ? historyContentTypeFilter : undefined,
      status: historyView === 'failed' ? 'failed' : historyView === 'archived' ? 'archived' : historyStatusFilter !== 'all' ? historyStatusFilter : undefined,
      approval_status: historyApprovalFilter !== 'all' ? historyApprovalFilter : undefined,
      search: historySearch || undefined,
    });
    setSeoHistory(Array.isArray(history.data.items) ? history.data.items : []);
    setSeoHistoryMeta({
      items: Array.isArray(history.data.items) ? history.data.items : [],
      count: history.data.count || 0,
      total: history.data.total || 0,
      limit: history.data.limit || seoHistoryMeta.limit,
      offset: history.data.offset || 0,
    });
  };

  const canGoPrevious = seoHistoryMeta.offset > 0;
  const canGoNext = seoHistoryMeta.offset + seoHistoryMeta.limit < seoHistoryMeta.total;
  const canArchiveSelected = selectedArchiveIds.length > 0;
  const visibleDraftIds = seoHistory.map((item) => item.id);

  const updateApprovalDraft = <T extends SeoApprovalDraft>(
    current: T | null,
    draftId: string,
    patch: Partial<T>
  ): T | null => (current?.draft_id === draftId ? { ...current, ...patch } : current);

  const handleGenerateMetaTags = async () => {
    if (!locationId) return;

    setIsGenerating(true);
    try {
      const response = await websiteSeoApi.generateMetaTags({
        location_id: locationId,
        page_type: 'home',
      });
      setMetaTags(response.data);
      setActiveTab('meta');
      await refreshHistory();
      setSeoStatusMessage(null);
      toast.success('Meta tags generated');
    } catch {
      setMetaTags(null);
      setSeoStatusMessage('Website SEO is unavailable for this location until the Website channel is connected. Open Integrations to reconnect and try again.');
      toast.error('Meta tags could not be generated');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateBlogPost = async () => {
    if (!locationId || !blogTopic.trim()) {
      toast.error('Please enter a topic');
      return;
    }

    setIsGenerating(true);
    try {
      const response = await websiteSeoApi.generateBlogPost({
        location_id: locationId,
        topic: blogTopic,
      });
      setGeneratedBlog(response.data);
      setActiveTab('content');
      await refreshHistory();
      setSeoStatusMessage(null);
      setIsBlogDialogOpen(false);
      toast.success('Blog draft generated');
    } catch {
      setGeneratedBlog(null);
      setSeoStatusMessage('Website SEO blog generation is unavailable for this location until the Website channel is connected. Open Integrations to reconnect and try again.');
      toast.error('Blog post could not be generated');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateServicePage = async () => {
    if (!locationId || !serviceName.trim()) {
      toast.error('Please enter a service name');
      return;
    }

    setIsGenerating(true);
    try {
      const response = await websiteSeoApi.generateServicePage({
        location_id: locationId,
        service_name: serviceName,
        service_description: serviceDescription.trim() || undefined,
      });
      setGeneratedServicePage(response.data);
      setActiveTab('content');
      await refreshHistory();
      setSeoStatusMessage(null);
      setIsServiceDialogOpen(false);
      toast.success('Service page draft generated');
    } catch {
      setGeneratedServicePage(null);
      setSeoStatusMessage('Website SEO service page generation is unavailable for this location until the Website channel is connected. Open Integrations to reconnect and try again.');
      toast.error('Service page could not be generated');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleOptimizePage = async () => {
    if (!locationId || !pageUrl.trim() || pageContent.trim().length < 50) {
      toast.error('Enter a page URL and at least 50 characters of current content');
      return;
    }

    setIsGenerating(true);
    try {
      const response = await websiteSeoApi.optimizePage({
        location_id: locationId,
        page_url: pageUrl,
        current_content: pageContent,
      });
      setPageOptimization(response.data);
      setActiveTab('optimize');
      await refreshHistory();
      setSeoStatusMessage(null);
      setIsOptimizeDialogOpen(false);
      toast.success('SEO page analysis generated');
    } catch {
      setPageOptimization(null);
      setSeoStatusMessage('Existing page analysis is unavailable for this location right now. Open Integrations to verify the Website channel and try again.');
      toast.error('Page analysis could not be generated');
    } finally {
      setIsGenerating(false);
    }
  };

  const handlePublishToWebsite = async (
    draft: SeoBlogDraft | SeoServicePageDraft,
    contentType: 'blog' | 'service_page'
  ) => {
    if (!locationId || !draft) return;

    setIsGenerating(true);
    try {
      await websiteSeoApi.publish({
        location_id: locationId,
        content_type: contentType,
        content: draft,
        draft_id: draft.draft_id,
      });
      await refreshHistory();
      toast.success('Website publish requested');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Website publish is not configured for this location'));
    } finally {
      setIsGenerating(false);
    }
  };

  const handleOpenDraft = async (draftId: string) => {
    try {
      const response = await websiteSeoApi.getDraft(draftId);
      const draft = response.data as SeoDraftRecord;
      const payload = draft.payload || {};

      if (draft.content_type === 'meta_tags') {
        setMetaTags({ ...(payload as unknown as SeoMetaTagsDraft), draft_id: draft.id });
        setActiveTab('meta');
        return;
      }

      if (draft.content_type === 'blog_post') {
        setGeneratedBlog({
          ...(payload as unknown as SeoBlogDraft),
          draft_id: draft.id,
          approval_status: draft.approval_status,
          rejection_reason: draft.rejection_reason,
        });
        setActiveTab('content');
        return;
      }

      if (draft.content_type === 'service_page') {
        setGeneratedServicePage({
          ...(payload as unknown as SeoServicePageDraft),
          draft_id: draft.id,
          approval_status: draft.approval_status,
          rejection_reason: draft.rejection_reason,
        });
        setActiveTab('content');
        return;
      }

      if (draft.content_type === 'optimization') {
        setPageOptimization({ ...(payload as unknown as SeoPageOptimizationDraft), draft_id: draft.id });
        setActiveTab('optimize');
      }
    } catch {
      toast.error('Draft details could not be loaded');
    }
  };

  const handleRetryPublish = async (draftId: string) => {
    try {
      const response = await websiteSeoApi.getDraft(draftId);
      const draft = response.data as SeoDraftRecord;
      const payload = draft.payload || {};
      const contentType = draft.content_type === 'service_page' ? 'service_page' : 'blog';
      if (contentType === 'service_page') {
        await handlePublishToWebsite(
          { ...(payload as unknown as SeoServicePageDraft), draft_id: draft.id },
          contentType
        );
      } else {
        await handlePublishToWebsite(
          { ...(payload as unknown as SeoBlogDraft), draft_id: draft.id },
          contentType
        );
      }
    } catch {
      toast.error('Retry publish could not be started');
    }
  };

  const handleArchiveSelected = async (draftIds: string[] = selectedArchiveIds) => {
    if (!locationId || draftIds.length === 0) return;

    const reason = window.prompt('Optional archive note') || undefined;
    try {
      await websiteSeoApi.archiveHistory(locationId, draftIds, reason);
      setSelectedArchiveIds([]);
      await refreshHistory();
      toast.success('Selected drafts archived');
    } catch {
      toast.error('Drafts could not be archived');
    }
  };

  const handleRequestApproval = async (draftId: string) => {
    try {
      await websiteSeoApi.requestDraftApproval(draftId);
      setGeneratedBlog((current) =>
        updateApprovalDraft(current, draftId, { approval_status: 'pending' })
      );
      setGeneratedServicePage((current) =>
        updateApprovalDraft(current, draftId, { approval_status: 'pending' })
      );
      await refreshHistory();
      toast.success('SEO draft sent for approval');
    } catch {
      toast.error('Approval request could not be created');
    }
  };

  const handleApproveDraft = async (draftId: string) => {
    try {
      await websiteSeoApi.approveDraft(draftId);
      setGeneratedBlog((current) =>
        updateApprovalDraft(current, draftId, { approval_status: 'approved' })
      );
      setGeneratedServicePage((current) =>
        updateApprovalDraft(current, draftId, { approval_status: 'approved' })
      );
      await refreshHistory();
      toast.success('SEO draft approved');
    } catch {
      toast.error('Draft approval failed');
    }
  };

  const handleRejectDraft = async (draftId: string) => {
    const reason = window.prompt('Optional rejection reason') || undefined;
    try {
      await websiteSeoApi.rejectDraft(draftId, reason);
      setGeneratedBlog((current) =>
        updateApprovalDraft(current, draftId, {
          approval_status: 'rejected',
          rejection_reason: reason,
        })
      );
      setGeneratedServicePage((current) =>
        updateApprovalDraft(current, draftId, {
          approval_status: 'rejected',
          rejection_reason: reason,
        })
      );
      await refreshHistory();
      toast.success('SEO draft rejected');
    } catch {
      toast.error('Draft rejection failed');
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-10 w-64" />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Website SEO</h1>
        <p className="text-gray-500">Choose one SEO job first. Draft history and diagnostics stay collapsed until needed.</p>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">SEO Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {websitePublishReady ? 'Create or improve one website page' : 'Connect the website channel before publishing'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Use the tabs below for one workflow at a time: keywords, meta tags, content drafts, or an existing page audit.
            </p>
          </div>
          <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={() => setActiveTab(websitePublishReady ? 'content' : 'meta')}>
            Start SEO workflow
          </Button>
        </CardContent>
      </Card>

      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="flex items-start gap-3 pt-6">
          <AlertCircle className="mt-0.5 h-5 w-5 text-amber-600" />
          <div className="text-sm text-amber-900">
            This is a beta workflow. Generated output should be reviewed before publishing, and website publishing may not be configured for every location.
          </div>
        </CardContent>
      </Card>

      <details className="group rounded-xl border bg-white shadow-sm">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4">
          <div>
            <div className="text-sm font-semibold text-slate-900">Draft history and archive controls</div>
            <div className="text-sm text-slate-500">Use this only when you need to review, search, or archive previous SEO output.</div>
          </div>
          <span className="text-xs font-medium text-slate-500 group-open:hidden">Show</span>
          <span className="hidden text-xs font-medium text-slate-500 group-open:inline">Hide</span>
        </summary>
        <div className="px-4 pb-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Location</CardTitle>
          <CardDescription>Select which location to use for Website SEO tools.</CardDescription>
        </CardHeader>
        <CardContent>
          {hasLocations ? (
            <select
              className="h-10 w-full rounded-md border bg-white px-3 text-sm"
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
            >
              {locations.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.name}
                </option>
              ))}
            </select>
          ) : (
            <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
              Connect a live location first. Website SEO tools only load real metadata, drafts, and publishing status after a location is available.
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent SEO Drafts</CardTitle>
          <CardDescription>Generated SEO output is now saved so it can be reviewed, published, or revisited later.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3">
            <div className="flex gap-2">
              <Button
                variant={historyView === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setHistoryView('all');
                  setSeoHistoryMeta((current) => ({ ...current, offset: 0 }));
                  setSelectedArchiveIds([]);
                }}
              >
                All drafts
              </Button>
              <Button
                variant={historyView === 'failed' ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setHistoryView('failed');
                  setSeoHistoryMeta((current) => ({ ...current, offset: 0 }));
                  setSelectedArchiveIds([]);
                }}
              >
                Failed only
              </Button>
              <Button
                variant={historyView === 'archived' ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setHistoryView('archived');
                  setSeoHistoryMeta((current) => ({ ...current, offset: 0 }));
                  setSelectedArchiveIds([]);
                }}
              >
                Archived only
              </Button>
            </div>
            <div className="grid gap-3 md:grid-cols-4">
              <select
                className="h-10 rounded-md border bg-white px-3 text-sm"
                value={historyContentTypeFilter}
                onChange={(e) => {
                  setHistoryContentTypeFilter(e.target.value);
                  setSeoHistoryMeta((current) => ({ ...current, offset: 0 }));
                  setSelectedArchiveIds([]);
                }}
              >
                <option value="all">All content types</option>
                <option value="meta_tags">Meta tags</option>
                <option value="blog_post">Blog posts</option>
                <option value="service_page">Service pages</option>
                <option value="optimization">Page audits</option>
              </select>
              <select
                className="h-10 rounded-md border bg-white px-3 text-sm"
                value={historyStatusFilter}
                onChange={(e) => {
                  setHistoryStatusFilter(e.target.value);
                  setSeoHistoryMeta((current) => ({ ...current, offset: 0 }));
                  setSelectedArchiveIds([]);
                }}
                disabled={historyView === 'failed' || historyView === 'archived'}
              >
                <option value="all">All statuses</option>
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="failed">Failed</option>
              </select>
              <select
                className="h-10 rounded-md border bg-white px-3 text-sm"
                value={historyApprovalFilter}
                onChange={(e) => {
                  setHistoryApprovalFilter(e.target.value);
                  setSeoHistoryMeta((current) => ({ ...current, offset: 0 }));
                  setSelectedArchiveIds([]);
                }}
              >
                <option value="all">All approval states</option>
                <option value="not_requested">Not requested</option>
                <option value="pending">Pending approval</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
              <Input
                placeholder="Search title, slug, topic, or error"
                value={historySearch}
                onChange={(e) => {
                  setHistorySearch(e.target.value);
                  setSeoHistoryMeta((current) => ({ ...current, offset: 0 }));
                  setSelectedArchiveIds([]);
                }}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-slate-50 px-3 py-2 text-sm">
            <div className="text-gray-600">
              {selectedArchiveIds.length > 0
                ? `${selectedArchiveIds.length} draft${selectedArchiveIds.length === 1 ? '' : 's'} selected for archive`
                : 'Select drafts to archive them from active history.'}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedArchiveIds(visibleDraftIds)}
                disabled={visibleDraftIds.length === 0}
              >
                Select all visible
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedArchiveIds([])}
                disabled={!canArchiveSelected}
              >
                Clear selection
              </Button>
              <Button variant="outline" size="sm" onClick={() => void handleArchiveSelected()} disabled={!canArchiveSelected}>
                <Archive className="mr-2 h-4 w-4" />
                Archive selected
              </Button>
            </div>
          </div>
          {seoHistory.length > 0 ? (
            seoHistory.map((item) => (
              <div key={item.id} className="rounded-lg border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 rounded border-gray-300"
                      checked={selectedArchiveIds.includes(item.id)}
                      onChange={(event) => {
                        setSelectedArchiveIds((current) =>
                          event.target.checked
                            ? [...current, item.id]
                            : current.filter((draftId) => draftId !== item.id)
                        );
                      }}
                    />
                    <div className="space-y-1">
                      <div className="font-medium">{item.title || item.source_topic || item.content_type.replace('_', ' ')}</div>
                      <div className="text-xs uppercase tracking-wide text-gray-500">{item.content_type.replace('_', ' ')}</div>
                    </div>
                  </div>
                  <Badge
                    variant={
                      item.status === 'published'
                        ? 'default'
                        : item.status === 'failed'
                          ? 'destructive'
                          : item.status === 'archived'
                            ? 'outline'
                            : 'secondary'
                    }
                  >
                    {item.status}
                  </Badge>
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge variant="outline">
                    Approval: {item.approval_status?.replace('_', ' ') || 'not requested'}
                  </Badge>
                </div>
                {item.slug && <div className="mt-2 text-sm text-gray-500">/{item.slug}</div>}
                {item.last_error && (
                  <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    {item.last_error}
                  </div>
                )}
                {item.rejection_reason && (
                  <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                    Rejection reason: {item.rejection_reason}
                  </div>
                )}
                {item.archived_at && (
                  <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                    Archived: {new Date(item.archived_at).toLocaleString()}
                    {item.archived_reason ? ` | ${item.archived_reason}` : ''}
                  </div>
                )}
                <div className="mt-2 text-xs text-gray-500">Created: {item.created_at ? new Date(item.created_at).toLocaleString() : 'Unknown'}</div>
                {item.approval_requested_at && (
                  <div className="text-xs text-gray-500">Approval requested: {new Date(item.approval_requested_at).toLocaleString()}</div>
                )}
                {item.approved_at && (
                  <div className="text-xs text-gray-500">Approved: {new Date(item.approved_at).toLocaleString()}</div>
                )}
                {item.rejected_at && (
                  <div className="text-xs text-gray-500">Rejected: {new Date(item.rejected_at).toLocaleString()}</div>
                )}
                {item.published_at && (
                  <div className="text-xs text-gray-500">Published: {new Date(item.published_at).toLocaleString()}</div>
                )}
                {item.published_url && (
                  <div className="mt-2">
                    <a href={item.published_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-violet-600 hover:underline">
                      Open published page
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </div>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => handleOpenDraft(item.id)}>
                    Reopen
                  </Button>
                  {(item.content_type === 'blog_post' || item.content_type === 'service_page') && item.status !== 'archived' &&
                    (!item.approval_status || item.approval_status === 'not_requested' || item.approval_status === 'rejected') && (
                      <Button variant="outline" size="sm" onClick={() => handleRequestApproval(item.id)}>
                        Request Approval
                      </Button>
                    )}
                  {(item.content_type === 'blog_post' || item.content_type === 'service_page') && item.status !== 'archived' &&
                    item.approval_status === 'pending' && (
                      <>
                        <Button size="sm" onClick={() => handleApproveDraft(item.id)}>
                          Approve
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handleRejectDraft(item.id)}>
                          Reject
                        </Button>
                      </>
                    )}
                  {item.status === 'failed' && ['blog_post', 'service_page'].includes(item.content_type) && (
                    <Button
                      size="sm"
                      onClick={() => handleRetryPublish(item.id)}
                      disabled={!websitePublishReady || isGenerating || item.approval_status !== 'approved'}
                    >
                      Retry Publish
                    </Button>
                  )}
                  {item.status !== 'archived' && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleArchiveSelected([item.id])}
                    >
                      Archive
                    </Button>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="text-sm text-gray-500">No generated SEO drafts have been saved for this location yet.</div>
          )}
          <div className="flex items-center justify-between border-t pt-3">
            <p className="text-xs text-gray-500">
              Showing {seoHistoryMeta.total === 0 ? 0 : seoHistoryMeta.offset + 1}-
              {Math.min(seoHistoryMeta.offset + seoHistoryMeta.limit, seoHistoryMeta.total)} of {seoHistoryMeta.total}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={!canGoPrevious}
                onClick={() => setSeoHistoryMeta((current) => ({ ...current, offset: Math.max(current.offset - current.limit, 0) }))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!canGoNext}
                onClick={() => setSeoHistoryMeta((current) => ({ ...current, offset: current.offset + current.limit }))}
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
        </div>
      </details>

      {seoStatusMessage && <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{seoStatusMessage}</div>}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Website Publishing Connection</CardTitle>
          <CardDescription>SEO publishing is only available when a website channel is configured in Integrations.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {websiteChannel ? (
            <>
              <div className="flex items-center justify-between rounded-md border px-3 py-2">
                <span>Website channel status</span>
                <Badge variant={websitePublishReady ? 'default' : 'secondary'}>
                  {websitePublishReady ? 'Ready to publish' : websiteChannel.status}
                </Badge>
              </div>
              {websiteChannel.error_message && (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">{websiteChannel.error_message}</div>
              )}
              {websiteChannel.last_publish_succeeded_at && (
                <div className="text-gray-500">Last successful publish: {new Date(websiteChannel.last_publish_succeeded_at).toLocaleString()}</div>
              )}
            </>
          ) : (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
              No website channel is configured for this location. Connect it in Integrations before publishing SEO content.
            </div>
          )}
          <div>
            <Button variant="outline" asChild>
              <a href="/dashboard/integrations">Open Integrations</a>
            </Button>
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="keywords">
            <Search className="mr-2 h-4 w-4" />
            Keywords
          </TabsTrigger>
          <TabsTrigger value="meta">
            <Code className="mr-2 h-4 w-4" />
            Meta Tags
          </TabsTrigger>
          <TabsTrigger value="content">
            <FileText className="mr-2 h-4 w-4" />
            Content
          </TabsTrigger>
          <TabsTrigger value="optimize">
            <Globe className="mr-2 h-4 w-4" />
            Optimize
          </TabsTrigger>
        </TabsList>

        <TabsContent value="keywords" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Local SEO Keywords</CardTitle>
              <CardDescription>Keyword ideas generated from location and service data.</CardDescription>
            </CardHeader>
            <CardContent>
              {keywords.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {keywords.map((keyword, index) => (
                    <Badge
                      key={`${keyword}-${index}`}
                      variant="secondary"
                      className="cursor-pointer px-3 py-1.5 text-sm hover:bg-violet-100"
                      onClick={() => copyToClipboard(keyword)}
                    >
                      <Tag className="mr-1 h-3 w-3" />
                      {keyword}
                    </Badge>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-gray-500">No keyword suggestions are available for this location yet.</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="meta" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <CardTitle>Meta Tag Generator</CardTitle>
                  <CardDescription>Generate title, description, and schema markup for the selected location.</CardDescription>
                </div>
                {hasLocations ? (
                  <Button onClick={handleGenerateMetaTags} disabled={isGenerating}>
                    {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                    Generate Tags
                  </Button>
                ) : (
                  <p className="max-w-xs text-sm text-gray-500">
                    Connect a location first to generate live meta tags and schema.
                  </p>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {metaTags ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Title Tag</Label>
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(metaTags.title)}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="rounded-lg bg-gray-50 p-3 font-mono text-sm">{metaTags.title}</div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Meta Description</Label>
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(metaTags.description)}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="rounded-lg bg-gray-50 p-3 font-mono text-sm">{metaTags.description}</div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Schema.org JSON-LD</Label>
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(metaTags.schema_json)}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    <pre className="overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-green-400">{metaTags.schema_json}</pre>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-gray-500">
                  {hasLocations
                    ? 'Generate tags to inspect the current beta output.'
                    : 'Connect a location first to inspect generated tags for a real business.'}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="content" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <CardTitle>Website SEO Drafts</CardTitle>
                  <CardDescription>Generate blog and service page drafts, review them, and optionally send them to your website channel.</CardDescription>
                </div>
                {hasLocations ? (
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={() => setIsOptimizeDialogOpen(true)}>
                      <Search className="mr-2 h-4 w-4" />
                      Audit Existing Page
                    </Button>
                    <Button variant="outline" onClick={() => setIsServiceDialogOpen(true)}>
                      <Globe className="mr-2 h-4 w-4" />
                      New Service Page
                    </Button>
                    <Button onClick={() => setIsBlogDialogOpen(true)}>
                      <Sparkles className="mr-2 h-4 w-4" />
                      New Blog Draft
                    </Button>
                  </div>
                ) : (
                  <p className="max-w-xs text-sm text-gray-500">
                    Connect a location first to generate live SEO drafts or audit an existing page.
                  </p>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {generatedBlog ? (
                <div className="space-y-4 rounded-lg border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold">{generatedBlog.title}</h3>
                      <p className="text-sm text-gray-500">/{generatedBlog.slug}</p>
                    </div>
                    <Badge>{generatedBlog.word_count} words</Badge>
                  </div>
                  <p className="text-sm text-gray-600">{generatedBlog.meta_description}</p>
                  <div className="flex flex-wrap gap-2">
                    {(generatedBlog.keywords || []).map((keyword: string, index: number) => (
                      <Badge key={`${keyword}-${index}`} variant="secondary">{keyword}</Badge>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {generatedBlog.draft_id && (!generatedBlog.approval_status || generatedBlog.approval_status === 'not_requested' || generatedBlog.approval_status === 'rejected') && (
                      <Button variant="outline" size="sm" onClick={() => handleRequestApproval(generatedBlog.draft_id!)}>
                        Request Approval
                      </Button>
                    )}
                    {generatedBlog.draft_id && generatedBlog.approval_status === 'pending' && (
                      <>
                        <Button size="sm" onClick={() => handleApproveDraft(generatedBlog.draft_id!)}>
                          Approve
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handleRejectDraft(generatedBlog.draft_id!)}>
                          Reject
                        </Button>
                      </>
                    )}
                    <Button variant="outline" size="sm" onClick={() => copyToClipboard(generatedBlog.content_markdown)}>
                      <Copy className="mr-2 h-4 w-4" />
                      Copy Draft
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handlePublishToWebsite(generatedBlog, 'blog')}
                      disabled={isGenerating || !websitePublishReady || generatedBlog.approval_status !== 'approved'}
                    >
                      {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ExternalLink className="mr-2 h-4 w-4" />}
                      Publish to Website
                    </Button>
                  </div>
                  {generatedBlog.approval_status && generatedBlog.approval_status !== 'approved' && (
                    <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                      This draft must be approved before it can be published.
                    </div>
                  )}
                  {!websitePublishReady && (
                    <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                      Website publishing is disabled until this location has a healthy website channel in Integrations.
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-sm text-gray-500">
                  {hasLocations
                    ? 'No SEO blog draft has been generated for this session yet.'
                    : 'Connect a location first to generate a live SEO blog draft.'}
                </div>
              )}

              {generatedServicePage ? (
                <div className="space-y-4 rounded-lg border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold">{generatedServicePage.service_name}</h3>
                      <p className="text-sm text-gray-500">Service page draft</p>
                    </div>
                    <Badge variant="secondary">Service Page</Badge>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(generatedServicePage.keywords || []).map((keyword: string, index: number) => (
                      <Badge key={`${keyword}-${index}`} variant="secondary">{keyword}</Badge>
                    ))}
                  </div>
                  <div className="max-h-64 overflow-y-auto rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
                    <pre className="whitespace-pre-wrap font-sans">{generatedServicePage.content_html}</pre>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {generatedServicePage.draft_id && (!generatedServicePage.approval_status || generatedServicePage.approval_status === 'not_requested' || generatedServicePage.approval_status === 'rejected') && (
                      <Button variant="outline" size="sm" onClick={() => handleRequestApproval(generatedServicePage.draft_id!)}>
                        Request Approval
                      </Button>
                    )}
                    {generatedServicePage.draft_id && generatedServicePage.approval_status === 'pending' && (
                      <>
                        <Button size="sm" onClick={() => handleApproveDraft(generatedServicePage.draft_id!)}>
                          Approve
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handleRejectDraft(generatedServicePage.draft_id!)}>
                          Reject
                        </Button>
                      </>
                    )}
                    <Button variant="outline" size="sm" onClick={() => copyToClipboard(generatedServicePage.content_html)}>
                      <Copy className="mr-2 h-4 w-4" />
                      Copy Draft
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handlePublishToWebsite(generatedServicePage, 'service_page')}
                      disabled={isGenerating || !websitePublishReady || generatedServicePage.approval_status !== 'approved'}
                    >
                      {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ExternalLink className="mr-2 h-4 w-4" />}
                      Publish to Website
                    </Button>
                  </div>
                  {generatedServicePage.approval_status && generatedServicePage.approval_status !== 'approved' && (
                    <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                      This draft must be approved before it can be published.
                    </div>
                  )}
                  {!websitePublishReady && (
                    <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                      Website publishing is disabled until this location has a healthy website channel in Integrations.
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-sm text-gray-500">
                  {hasLocations
                    ? 'No service page draft has been generated for this session yet.'
                    : 'Connect a location first to generate a live service page draft.'}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="optimize" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <CardTitle>Existing Page SEO Audit</CardTitle>
                  <CardDescription>Review an existing page and get a saved optimization draft with recommendations.</CardDescription>
                </div>
                {hasLocations ? (
                  <Button onClick={() => setIsOptimizeDialogOpen(true)}>
                    <Search className="mr-2 h-4 w-4" />
                    Audit Existing Page
                  </Button>
                ) : (
                  <p className="max-w-xs text-sm text-gray-500">
                    Connect a location first to audit an existing page with live business context.
                  </p>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {pageOptimization ? (
                <div className="space-y-4 rounded-lg border p-4">
                  <div>
                    <div className="text-sm text-gray-500">Page URL</div>
                    <div className="font-medium">{pageOptimization.page_url}</div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-lg bg-gray-50 p-3">
                      <div className="text-xs uppercase text-gray-500">Word Count</div>
                      <div className="mt-1 text-xl font-semibold">{pageOptimization.analysis?.word_count ?? 0}</div>
                    </div>
                    <div className="rounded-lg bg-gray-50 p-3">
                      <div className="text-xs uppercase text-gray-500">H1 Present</div>
                      <div className="mt-1 text-xl font-semibold">{pageOptimization.analysis?.has_h1 ? 'Yes' : 'No'}</div>
                    </div>
                    <div className="rounded-lg bg-gray-50 p-3">
                      <div className="text-xs uppercase text-gray-500">H2 Present</div>
                      <div className="mt-1 text-xl font-semibold">{pageOptimization.analysis?.has_h2 ? 'Yes' : 'No'}</div>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="font-medium">Recommendations</div>
                    {(pageOptimization.recommendations || []).length > 0 ? (
                      (pageOptimization.recommendations || []).map((recommendation: SeoOptimizationRecommendation, index: number) => (
                        <div key={`${recommendation.type}-${index}`} className="rounded-lg border p-3">
                          <div className="flex items-center justify-between gap-2">
                            <div className="font-medium">{recommendation.type.replace('_', ' ')}</div>
                            <Badge variant={recommendation.priority === 'high' ? 'destructive' : 'secondary'}>
                              {recommendation.priority}
                            </Badge>
                          </div>
                          <div className="mt-2 text-sm text-gray-600">{recommendation.message}</div>
                        </div>
                      ))
                    ) : (
                      <div className="text-sm text-gray-500">No recommendations were generated for this page yet.</div>
                    )}
                  </div>
                  <div className="space-y-2">
                    <div className="font-medium">Target Keywords</div>
                    <div className="flex flex-wrap gap-2">
                      {(pageOptimization.target_keywords || []).map((keyword: string, index: number) => (
                        <Badge key={`${keyword}-${index}`} variant="secondary">{keyword}</Badge>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="font-medium">Suggested Meta Tags</div>
                    <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
                      <div><strong>Title:</strong> {pageOptimization.suggested_meta_tags?.title}</div>
                      <div className="mt-2"><strong>Description:</strong> {pageOptimization.suggested_meta_tags?.description}</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-gray-500">
                  {hasLocations
                    ? 'No page audit has been generated in this session yet.'
                    : 'Connect a location first to generate a saved page audit.'}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={isBlogDialogOpen} onOpenChange={setIsBlogDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate Blog Draft</DialogTitle>
            <DialogDescription>Enter a topic for the selected location.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Topic</Label>
              <Input placeholder="e.g. Summer skin care tips in Dallas" value={blogTopic} onChange={(e) => setBlogTopic(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsBlogDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleGenerateBlogPost} disabled={isGenerating}>
              {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              Generate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isServiceDialogOpen} onOpenChange={setIsServiceDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate Service Page</DialogTitle>
            <DialogDescription>Create an SEO-focused service page draft for the selected location.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Service name</Label>
              <Input placeholder="e.g. Emergency plumbing" value={serviceName} onChange={(e) => setServiceName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Short description</Label>
              <Input placeholder="Optional notes about the service" value={serviceDescription} onChange={(e) => setServiceDescription(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsServiceDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleGenerateServicePage} disabled={isGenerating}>
              {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              Generate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isOptimizeDialogOpen} onOpenChange={setIsOptimizeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Audit Existing Page</DialogTitle>
            <DialogDescription>Paste the current page URL and content so the SEO workflow can analyze it.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Page URL</Label>
              <Input placeholder="https://example.com/service-page" value={pageUrl} onChange={(e) => setPageUrl(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Current page content</Label>
              <textarea
                className="min-h-40 w-full rounded-md border bg-white px-3 py-2 text-sm"
                placeholder="Paste the current page text or HTML here"
                value={pageContent}
                onChange={(e) => setPageContent(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOptimizeDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleOptimizePage} disabled={isGenerating}>
              {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
              Analyze
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
