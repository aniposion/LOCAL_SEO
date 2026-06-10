'use client';

import { useEffect, useMemo, useState } from 'react';
import { Loader2, Mail, Megaphone, Pause, Play, Plus, RotateCcw, Search, Send, ShieldAlert, Smartphone, BarChart3 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { extractCollectionPayload, locationsApi, reviewBoosterApi, reviewCampaignsApi } from '@/lib/api';
import { toast } from 'sonner';

type CampaignStatusFilter = 'all' | 'active' | 'paused' | 'completed';
type RequestStatusFilter = 'all' | 'pending' | 'retrying' | 'delivered' | 'failed' | 'opted_out';

interface LocationOption {
  id: string;
  name: string;
  address?: string | null;
}

interface ReviewBoosterAnalytics {
  location_id: string;
  period_days: number;
  total_campaigns: number;
  active_campaigns: number;
  paused_campaigns: number;
  completed_campaigns: number;
  total_requests: number;
  pending_requests: number;
  delivered_requests: number;
  failed_requests: number;
  pending_retries: number;
  opted_out_requests: number;
  attention_requests: number;
  total_sent: number;
}

interface ReviewTemplatesResponse {
  sms_templates: { id: string; name: string; template: string }[];
  placeholders: string[];
}

interface Campaign {
  id: string;
  name: string;
  google_review_url: string;
  sms_template?: string;
  email_template?: string;
  status: 'active' | 'paused' | 'completed';
  total_sent: number;
  total_clicked?: number;
  total_reviews_estimated?: number;
  created_at: string;
}

interface ReviewRequest {
  id: string;
  campaign_id: string;
  customer_name: string;
  customer_email?: string;
  customer_phone?: string;
  channel: string;
  status: 'pending' | 'sent' | 'delivered' | 'failed' | 'opted_out';
  consent_given: boolean;
  consent_method?: string;
  google_link_included: boolean;
  sent_at?: string;
  delivered_at?: string;
  last_attempt_at?: string;
  next_retry_at?: string;
  retry_count: number;
  last_error?: string;
  created_at: string;
}

const campaignStatusOptions: { value: CampaignStatusFilter; label: string }[] = [
  { value: 'all', label: 'All campaigns' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'completed', label: 'Completed' },
];

const requestStatusOptions: { value: RequestStatusFilter; label: string }[] = [
  { value: 'all', label: 'All requests' },
  { value: 'pending', label: 'Pending' },
  { value: 'retrying', label: 'Pending retry' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'failed', label: 'Failed' },
  { value: 'opted_out', label: 'Opted out' },
];

function campaignStatusBadge(status: Campaign['status']) {
  if (status === 'active') return 'bg-green-100 text-green-700';
  if (status === 'paused') return 'bg-amber-100 text-amber-700';
  return 'bg-slate-100 text-slate-600';
}

function requestStatusBadge(request: ReviewRequest, retrying: boolean) {
  if (retrying) return 'bg-amber-100 text-amber-700';
  if (request.status === 'delivered') return 'bg-green-100 text-green-700';
  if (request.status === 'sent') return 'bg-blue-100 text-blue-700';
  if (request.status === 'failed') return 'bg-rose-100 text-rose-700';
  if (request.status === 'opted_out') return 'bg-slate-100 text-slate-600';
  return 'bg-gray-100 text-gray-600';
}

export default function ReviewsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [selectedLocationId, setSelectedLocationId] = useState('');
  const [analytics, setAnalytics] = useState<ReviewBoosterAnalytics | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [requests, setRequests] = useState<ReviewRequest[]>([]);
  const [templates, setTemplates] = useState<ReviewTemplatesResponse | null>(null);

  const [activeTab, setActiveTab] = useState<'overview' | 'campaigns' | 'requests'>('overview');
  const [campaignStatusFilter, setCampaignStatusFilter] = useState<CampaignStatusFilter>('all');
  const [requestStatusFilter, setRequestStatusFilter] = useState<RequestStatusFilter>('all');
  const [requestSearch, setRequestSearch] = useState('');

  const [isCampaignDialogOpen, setIsCampaignDialogOpen] = useState(false);
  const [isRequestDialogOpen, setIsRequestDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [campaignName, setCampaignName] = useState('');
  const [googleReviewUrl, setGoogleReviewUrl] = useState('');
  const [smsTemplate, setSmsTemplate] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState('default');

  const [customerName, setCustomerName] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [requestChannel, setRequestChannel] = useState<'email' | 'sms'>('sms');
  const [selectedCampaign, setSelectedCampaign] = useState('');
  const activeLocationId = selectedLocationId || locations[0]?.id || '';

  useEffect(() => {
    void loadLocations();
  }, []);

  useEffect(() => {
    if (!activeLocationId) return;
    void loadData(activeLocationId);
  }, [activeLocationId]);

  const loadLocations = async () => {
    setIsLoading(true);
    try {
      const response = await locationsApi.list();
      const list = extractCollectionPayload<LocationOption>(response.data, 'locations');
      setLocations(list);
      setSelectedLocationId((current) =>
        current && list.some((location) => location.id === current)
          ? current
          : (list[0]?.id ?? '')
      );
    } catch (error) {
      console.error('Failed to load locations:', error);
      toast.error('Failed to load locations');
      setLocations([]);
      setSelectedLocationId('');
    } finally {
      setIsLoading(false);
    }
  };

  const loadData = async (locationId: string) => {
    setIsLoading(true);
    try {
      const [analyticsRes, campaignsRes, requestsRes, templatesRes] = await Promise.allSettled([
        reviewBoosterApi.getAnalytics(locationId, 30),
        reviewCampaignsApi.list(locationId),
        reviewCampaignsApi.getRequests(locationId),
        reviewBoosterApi.getTemplates(),
      ]);

      setAnalytics(analyticsRes.status === 'fulfilled' ? analyticsRes.value.data : null);
      setCampaigns(campaignsRes.status === 'fulfilled' ? campaignsRes.value.data.items || [] : []);
      setRequests(requestsRes.status === 'fulfilled' ? requestsRes.value.data.items || [] : []);
      setTemplates(templatesRes.status === 'fulfilled' ? templatesRes.value.data : null);

      if (campaignsRes.status === 'rejected') {
        console.error('Failed to load campaigns:', campaignsRes.reason);
        toast.error('Failed to load campaigns');
      }
      if (requestsRes.status === 'rejected') {
        console.error('Failed to load requests:', requestsRes.reason);
        toast.error('Failed to load requests');
      }
    } catch (error) {
      console.error('Failed to load Review Booster data:', error);
      toast.error('Failed to load Review Booster data');
    } finally {
      setIsLoading(false);
    }
  };

  const campaignLookup = useMemo(
    () => new Map(campaigns.map((campaign) => [campaign.id, campaign])),
    [campaigns]
  );

  const enrichedRequests = useMemo(() => {
    return requests.map((request) => {
      const campaign = campaignLookup.get(request.campaign_id);
      const retrying = request.status === 'failed' && (request.retry_count > 0 || Boolean(request.next_retry_at));
      return {
        ...request,
        campaign_name: campaign?.name || 'Unknown campaign',
        retrying,
      };
    });
  }, [requests, campaignLookup]);

  const summary = analytics || {
    location_id: activeLocationId,
    period_days: 30,
    total_campaigns: campaigns.length,
    active_campaigns: campaigns.filter((campaign) => campaign.status === 'active').length,
    paused_campaigns: campaigns.filter((campaign) => campaign.status === 'paused').length,
    completed_campaigns: campaigns.filter((campaign) => campaign.status === 'completed').length,
    total_requests: requests.length,
    pending_requests: enrichedRequests.filter((request) => request.status === 'pending').length,
    delivered_requests: enrichedRequests.filter((request) => request.status === 'delivered').length,
    failed_requests: enrichedRequests.filter((request) => request.status === 'failed' && !request.retrying).length,
    pending_retries: enrichedRequests.filter((request) => request.retrying).length,
    opted_out_requests: enrichedRequests.filter((request) => request.status === 'opted_out').length,
    attention_requests: enrichedRequests.filter((request) => request.status === 'failed' || request.status === 'opted_out' || request.retrying).length,
    total_sent: campaigns.reduce((sum, campaign) => sum + (campaign.total_sent || 0), 0),
  } as ReviewBoosterAnalytics;
  const filteredCampaigns = useMemo(() => {
    return campaigns.filter((campaign) => campaignStatusFilter === 'all' || campaign.status === campaignStatusFilter);
  }, [campaignStatusFilter, campaigns]);

  const filteredRequests = useMemo(() => {
    const search = requestSearch.trim().toLowerCase();
    return enrichedRequests.filter((request) => {
      const matchesFilter =
        requestStatusFilter === 'all' ||
        (requestStatusFilter === 'pending' && request.status === 'pending') ||
        (requestStatusFilter === 'retrying' && request.retrying) ||
        (requestStatusFilter === 'delivered' && request.status === 'delivered') ||
        (requestStatusFilter === 'failed' && request.status === 'failed' && !request.retrying) ||
        (requestStatusFilter === 'opted_out' && request.status === 'opted_out');

      const matchesSearch =
        !search ||
        request.customer_name.toLowerCase().includes(search) ||
        (request.customer_email || '').toLowerCase().includes(search) ||
        (request.customer_phone || '').toLowerCase().includes(search) ||
        (request.last_error || '').toLowerCase().includes(search) ||
        request.campaign_name.toLowerCase().includes(search);

      return matchesFilter && matchesSearch;
    });
  }, [enrichedRequests, requestSearch, requestStatusFilter]);

  const handleLocationChange = (locationId: string) => {
    setSelectedLocationId(locationId);
    setCampaignStatusFilter('all');
    setRequestStatusFilter('all');
    setRequestSearch('');
  };

  const handleCreateCampaign = async () => {
    if (!activeLocationId || !campaignName.trim() || !googleReviewUrl.trim()) {
      toast.error('Please fill in the required fields');
      return;
    }

    setIsSubmitting(true);
    try {
      await reviewCampaignsApi.create(activeLocationId, {
        name: campaignName,
        google_review_url: googleReviewUrl,
        sms_template: smsTemplate || undefined,
        channels: ['sms'],
      });
      toast.success('Campaign created');
      setIsCampaignDialogOpen(false);
      setCampaignName('');
      setGoogleReviewUrl('');
      setSmsTemplate('');
      setSelectedTemplateId('default');
      await loadData(activeLocationId);
    } catch (error) {
      console.error('Failed to create campaign:', error);
      toast.error('Failed to create campaign');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleCampaign = async (campaignId: string, status: Campaign['status']) => {
    try {
      await reviewCampaignsApi.update(campaignId, { status: status === 'active' ? 'paused' : 'active' });
      toast.success(status === 'active' ? 'Campaign paused' : 'Campaign activated');
      if (activeLocationId) {
        await loadData(activeLocationId);
      }
    } catch (error) {
      console.error('Failed to update campaign:', error);
      toast.error('Failed to update campaign');
    }
  };

  const handleSendReviewRequest = async () => {
    if (!activeLocationId) return;
    if (!customerName.trim()) {
      toast.error('Please enter a customer name');
      return;
    }
    if (!customerEmail && !customerPhone) {
      toast.error('Please enter an email or phone number');
      return;
    }

    setIsSubmitting(true);
    try {
      await reviewCampaignsApi.sendRequest(activeLocationId, {
        campaign_id: selectedCampaign || undefined,
        customer_name: customerName,
        customer_email: customerEmail || undefined,
        customer_phone: customerPhone || undefined,
        channel: requestChannel,
        consent_given: true,
        consent_method: 'manual_dashboard',
      });
      toast.success('Review request sent');
      setIsRequestDialogOpen(false);
      setCustomerName('');
      setCustomerEmail('');
      setCustomerPhone('');
      await loadData(activeLocationId);
    } catch (error) {
      console.error('Failed to send review request:', error);
      toast.error('Failed to send review request');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRequeueRequest = async (requestId: string) => {
    if (!activeLocationId) return;

    try {
      await reviewCampaignsApi.requeueRequest(requestId);
      toast.success('Request requeued');
      await loadData(activeLocationId);
    } catch (error) {
      console.error('Failed to requeue request:', error);
      toast.error('Failed to requeue request');
    }
  };

  const openCampaignDialog = () => {
    if (!activeLocationId) {
      toast.error('Create or connect a location before creating a review campaign.');
      return;
    }

    const defaultTemplate = templates?.sms_templates?.find((template) => template.id === selectedTemplateId) || templates?.sms_templates?.[0];
    if (defaultTemplate && !smsTemplate) {
      setSmsTemplate(defaultTemplate.template);
    }
    setIsCampaignDialogOpen(true);
  };

  const openRequestDialog = () => {
    if (!activeLocationId) {
      toast.error('Create or connect a location before sending review requests.');
      return;
    }

    setIsRequestDialogOpen(true);
  };

  if (isLoading && !activeLocationId) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((index) => (
            <Card key={index}>
              <CardContent className="pt-6">
                <Skeleton className="mb-2 h-8 w-20" />
                <Skeleton className="h-4 w-28" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const hasAttention = summary.failed_requests > 0 || summary.pending_retries > 0 || summary.opted_out_requests > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge className="bg-violet-100 text-violet-700">Review Booster</Badge>
            <Badge variant="outline">Operator view</Badge>
          </div>
          <div>
            <h1 className="text-2xl font-bold">Campaigns and Requests</h1>
            <p className="text-gray-500">Track real request activity, retries, and opt-out attention without demo data.</p>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          {locations.length > 1 ? (
            <div className="min-w-[240px]">
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-500">Location</label>
              <select
                value={activeLocationId}
                onChange={(event) => handleLocationChange(event.target.value)}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                {locations.map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <div className="flex gap-2">
            <Button variant="outline" onClick={openCampaignDialog} disabled={!activeLocationId}>
              <Plus className="mr-2 h-4 w-4" />
              New Campaign
            </Button>
            <Button onClick={openRequestDialog} disabled={!activeLocationId} className="bg-gradient-to-r from-violet-600 to-indigo-600">
              <Send className="mr-2 h-4 w-4" />
              Request Review
            </Button>
          </div>
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Reviews Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {hasAttention ? 'Fix failed or retrying review requests first' : 'Ask one happy customer for a review'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Review growth works best as a simple habit: send requests, watch failures, and follow up before volume stalls.
            </p>
          </div>
          <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={openRequestDialog} disabled={!activeLocationId}>
            Request review
          </Button>
        </CardContent>
      </Card>

      {hasAttention ? (
        <Card className="border-amber-200 bg-amber-50/70">
          <CardContent className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 h-5 w-5 text-amber-600" />
              <div>
                <p className="font-semibold text-amber-950">Review Booster needs attention</p>
                <p className="text-sm text-amber-900/80">
                  {summary.failed_requests} failed requests, {summary.pending_retries} pending retries, and {summary.opted_out_requests} opt-outs are in the queue.
                </p>
              </div>
            </div>
            <Button variant="outline" onClick={() => setActiveTab('requests')}>
              Review requests
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as typeof activeTab)}>
        <TabsList>
          <TabsTrigger value="overview">
            <BarChart3 className="mr-2 h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="campaigns">
            <Megaphone className="mr-2 h-4 w-4" />
            Campaigns ({summary.total_campaigns})
          </TabsTrigger>
          <TabsTrigger value="requests">
            <Send className="mr-2 h-4 w-4" />
            Requests ({summary.total_requests})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6 space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
            <Card><CardContent className="pt-6"><div className="text-3xl font-bold text-violet-600">{summary.total_campaigns}</div><p className="mt-1 text-sm text-gray-500">Campaigns</p></CardContent></Card>
            <Card><CardContent className="pt-6"><div className="text-3xl font-bold text-green-600">{summary.active_campaigns}</div><p className="mt-1 text-sm text-gray-500">Active</p></CardContent></Card>
            <Card><CardContent className="pt-6"><div className="text-3xl font-bold text-blue-600">{summary.delivered_requests}</div><p className="mt-1 text-sm text-gray-500">Delivered</p></CardContent></Card>
            <Card><CardContent className="pt-6"><div className="text-3xl font-bold text-rose-600">{summary.failed_requests}</div><p className="mt-1 text-sm text-gray-500">Failed</p></CardContent></Card>
            <Card><CardContent className="pt-6"><div className="text-3xl font-bold text-amber-600">{summary.pending_retries}</div><p className="mt-1 text-sm text-gray-500">Pending retries</p></CardContent></Card>
            <Card><CardContent className="pt-6"><div className="text-3xl font-bold text-slate-700">{summary.opted_out_requests}</div><p className="mt-1 text-sm text-gray-500">Opt-outs</p></CardContent></Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Campaign health</CardTitle>
                <CardDescription>Campaign status is visible in counts, request volume, and retry pressure.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {campaigns.length > 0 ? campaigns.map((campaign) => {
                  const related = enrichedRequests.filter((request) => request.campaign_id === campaign.id);
                  const delivered = related.filter((request) => request.status === 'delivered').length;
                  const failed = related.filter((request) => request.status === 'failed' && !request.retrying).length;
                  const retrying = related.filter((request) => request.retrying).length;
                  const optedOut = related.filter((request) => request.status === 'opted_out').length;
                  const attention = failed + retrying + optedOut;

                  return (
                    <div key={campaign.id} className="rounded-xl border p-4 shadow-sm transition-shadow hover:shadow-md">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-semibold text-slate-900">{campaign.name}</p>
                            <Badge className={campaignStatusBadge(campaign.status)}>{campaign.status}</Badge>
                            {attention > 0 ? <Badge className="bg-amber-100 text-amber-700">Attention needed</Badge> : null}
                          </div>
                          <p className="truncate text-sm text-gray-500">{campaign.google_review_url}</p>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
                          <div className="rounded-lg bg-gray-50 px-3 py-2"><p className="text-lg font-bold">{campaign.total_sent}</p><p className="text-xs text-gray-500">Sent</p></div>
                          <div className="rounded-lg bg-green-50 px-3 py-2"><p className="text-lg font-bold text-green-700">{delivered}</p><p className="text-xs text-gray-500">Delivered</p></div>
                          <div className="rounded-lg bg-rose-50 px-3 py-2"><p className="text-lg font-bold text-rose-700">{failed}</p><p className="text-xs text-gray-500">Failed</p></div>
                          <div className="rounded-lg bg-amber-50 px-3 py-2"><p className="text-lg font-bold text-amber-700">{retrying}</p><p className="text-xs text-gray-500">Retrying</p></div>
                        </div>
                      </div>

                      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                        <span>{optedOut} opted out</span>
                        <span>•</span>
                        <span>{campaign.total_reviews_estimated || 0} estimated reviews</span>
                        <span>•</span>
                        <span>{campaign.total_clicked || 0} clicks</span>
                      </div>
                    </div>
                  );
                }) : (
                  <div className="rounded-xl border border-dashed bg-white p-8 text-center">
                    <Megaphone className="mx-auto mb-3 h-10 w-10 text-gray-300" />
                    <p className="font-medium text-slate-900">No campaigns yet</p>
                    <p className="mt-1 text-sm text-gray-500">Create the first campaign to start collecting review requests.</p>
                    <Button className="mt-4" onClick={openCampaignDialog}>
                      <Plus className="mr-2 h-4 w-4" />
                      Create first campaign
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Operational note</CardTitle>
                <CardDescription>Review Booster works from live request data, not demo reviews.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-gray-600">
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="font-medium text-slate-900">Main queue</p>
                  <p className="mt-1">Start with failed requests and pending retries.</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="font-medium text-slate-900">Opt-out handling</p>
                  <p className="mt-1">Requests marked opted out stay visible so operators can verify compliance.</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="font-medium text-slate-900">Templates</p>
                  <p className="mt-1">English request templates are available and editable before sending.</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        <TabsContent value="campaigns" className="mt-6 space-y-6">
          <div className="flex flex-wrap gap-2">
            {campaignStatusOptions.map((option) => (
              <Button key={option.value} variant={campaignStatusFilter === option.value ? 'default' : 'outline'} size="sm" onClick={() => setCampaignStatusFilter(option.value)}>
                {option.label}
              </Button>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            {filteredCampaigns.map((campaign) => {
              const related = enrichedRequests.filter((request) => request.campaign_id === campaign.id);
              const delivered = related.filter((request) => request.status === 'delivered').length;
              const failed = related.filter((request) => request.status === 'failed' && !request.retrying).length;
              const retrying = related.filter((request) => request.retrying).length;
              const optedOut = related.filter((request) => request.status === 'opted_out').length;
              const attention = failed + retrying + optedOut;

              return (
                <Card key={campaign.id} className="border-slate-200 shadow-sm">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Megaphone className="h-5 w-5 text-violet-600" />
                        <CardTitle className="text-lg">{campaign.name}</CardTitle>
                      </div>
                      <Badge className={campaignStatusBadge(campaign.status)}>{campaign.status}</Badge>
                    </div>
                    <CardDescription className="break-all">{campaign.google_review_url}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-3 text-center md:grid-cols-4">
                      <div className="rounded-lg bg-gray-50 px-3 py-2"><p className="text-xl font-bold">{campaign.total_sent}</p><p className="text-xs text-gray-500">Sent</p></div>
                      <div className="rounded-lg bg-green-50 px-3 py-2"><p className="text-xl font-bold text-green-700">{delivered}</p><p className="text-xs text-gray-500">Delivered</p></div>
                      <div className="rounded-lg bg-rose-50 px-3 py-2"><p className="text-xl font-bold text-rose-700">{failed}</p><p className="text-xs text-gray-500">Failed</p></div>
                      <div className="rounded-lg bg-amber-50 px-3 py-2"><p className="text-xl font-bold text-amber-700">{retrying}</p><p className="text-xs text-gray-500">Retrying</p></div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                      <span>{optedOut} opted out</span>
                      <span>•</span>
                      <span>{campaign.total_reviews_estimated || 0} estimated reviews</span>
                      <span>•</span>
                      <span>{campaign.total_clicked || 0} clicks</span>
                      {attention > 0 ? <><span>•</span><span className="font-medium text-amber-700">{attention} items need attention</span></> : null}
                    </div>
                    {campaign.status === 'completed' ? (
                      <div className="rounded-lg border border-dashed bg-slate-50 px-3 py-3 text-sm text-slate-600">
                        Completed campaigns stay read-only for reporting. Create a new campaign to send more review requests.
                      </div>
                    ) : (
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" className="flex-1" onClick={() => handleToggleCampaign(campaign.id, campaign.status)}>
                          {campaign.status === 'active' ? <><Pause className="mr-2 h-4 w-4" />Pause</> : <><Play className="mr-2 h-4 w-4" />Activate</>}
                        </Button>
                        <Button size="sm" className="flex-1" onClick={() => { setSelectedCampaign(campaign.id); openRequestDialog(); }}>
                          <Send className="mr-2 h-4 w-4" />Send request
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}

            {filteredCampaigns.length === 0 ? (
              <Card className="col-span-full">
                <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                  <Megaphone className="mb-3 h-12 w-12 text-gray-300" />
                  <p className="font-medium text-slate-900">No campaigns match this filter</p>
                  <p className="mt-1 text-sm text-gray-500">Try a different campaign status or create a new campaign.</p>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </TabsContent>

        <TabsContent value="requests" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Request queue</CardTitle>
              <CardDescription>Failed requests, pending retries, delivered requests, and opt-outs are visible here.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex flex-wrap gap-2">
                  {requestStatusOptions.map((option) => (
                    <Button key={option.value} variant={requestStatusFilter === option.value ? 'default' : 'outline'} size="sm" onClick={() => setRequestStatusFilter(option.value)}>
                      {option.label}
                    </Button>
                  ))}
                </div>
                <div className="w-full lg:max-w-sm">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                    <Input value={requestSearch} onChange={(event) => setRequestSearch(event.target.value)} placeholder="Search customer, campaign, phone, or error" className="pl-9" />
                  </div>
                </div>
              </div>

              {filteredRequests.length > 0 ? (
                <div className="space-y-3">
                  {filteredRequests.map((request) => (
                    <div key={request.id} className="rounded-xl border p-4 shadow-sm">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-semibold text-slate-900">{request.customer_name}</p>
                            <Badge variant="outline">{campaignLookup.get(request.campaign_id)?.name || request.campaign_id}</Badge>
                            <Badge className={requestStatusBadge(request, request.retrying)}>
                              {request.retrying ? 'Retrying' : request.status}
                            </Badge>
                          </div>
                          <p className="text-sm text-gray-500">
                            {request.customer_email || request.customer_phone || 'No contact details'} via {request.channel.toUpperCase()}
                          </p>
                          <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                            <span>Retries: {request.retry_count}</span>
                            {request.next_retry_at ? <span>Next retry: {new Date(request.next_retry_at).toLocaleString()}</span> : null}
                            {request.sent_at ? <span>Sent: {new Date(request.sent_at).toLocaleString()}</span> : null}
                            {request.delivered_at ? <span>Delivered: {new Date(request.delivered_at).toLocaleString()}</span> : null}
                          </div>
                          {request.last_error ? <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">Last error: {request.last_error}</div> : null}
                        </div>
                        <div className="flex flex-col gap-2 lg:items-end">
                          {(request.status === 'failed' || request.retrying) ? (
                            <Button size="sm" variant="outline" onClick={() => void handleRequeueRequest(request.id)}>
                              <RotateCcw className="mr-2 h-4 w-4" />
                              Retry now
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-xl border border-dashed bg-slate-50 p-10 text-center">
                  <Send className="mx-auto mb-3 h-12 w-12 text-gray-300" />
                  <p className="font-medium text-slate-900">No requests match this filter</p>
                  <p className="mt-1 text-sm text-gray-500">Adjust the filter or send a new review request to start the queue.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={isRequestDialogOpen} onOpenChange={setIsRequestDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Request a review</DialogTitle>
            <DialogDescription>Send a review request by SMS or email from the selected location.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Customer name *</label>
              <Input placeholder="John Doe" value={customerName} onChange={(event) => setCustomerName(event.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Email</label>
              <Input type="email" placeholder="john@example.com" value={customerEmail} onChange={(event) => setCustomerEmail(event.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Phone</label>
              <Input type="tel" placeholder="+1 (555) 000-0000" value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Send via</label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: 'email' as const, icon: Mail, label: 'Email' },
                  { id: 'sms' as const, icon: Smartphone, label: 'SMS' },
                ].map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setRequestChannel(option.id)}
                    className={`flex flex-col items-center gap-1 rounded-lg border p-3 transition-colors ${requestChannel === option.id ? 'border-violet-500 bg-violet-50' : 'hover:border-gray-300'}`}
                  >
                    <option.icon className={`h-5 w-5 ${requestChannel === option.id ? 'text-violet-600' : 'text-gray-500'}`} />
                    <span className="text-sm">{option.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsRequestDialogOpen(false)}>Cancel</Button>
            <Button onClick={() => void handleSendReviewRequest()} disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
              Send request
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isCampaignDialogOpen} onOpenChange={setIsCampaignDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create review campaign</DialogTitle>
            <DialogDescription>Use an English template and edit it before sending.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Campaign name *</label>
              <Input placeholder="Holiday season follow-up" value={campaignName} onChange={(event) => setCampaignName(event.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Google review link *</label>
              <Input placeholder="https://g.page/r/your-business/review" value={googleReviewUrl} onChange={(event) => setGoogleReviewUrl(event.target.value)} />
              <p className="text-xs text-gray-500">Use the review link from Google Business Profile.</p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <label className="text-sm font-medium">SMS template</label>
                <Button variant="ghost" size="sm" onClick={() => {
                  const template = templates?.sms_templates?.find((item) => item.id === 'default') || templates?.sms_templates?.[0];
                  if (template) setSmsTemplate(template.template);
                }}>
                  Default template
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {(templates?.sms_templates || []).map((template) => (
                  <Button
                    key={template.id}
                    type="button"
                    size="sm"
                    variant={selectedTemplateId === template.id ? 'default' : 'outline'}
                    onClick={() => {
                      setSelectedTemplateId(template.id);
                      setSmsTemplate(template.template);
                    }}
                  >
                    {template.name}
                  </Button>
                ))}
              </div>
              <textarea
                className="h-28 w-full resize-none rounded-lg border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                placeholder="Hi {customer_name}, thanks for choosing {business_name}. If you have a minute, please leave a Google review here: {google_link}"
                value={smsTemplate}
                onChange={(event) => setSmsTemplate(event.target.value)}
              />
              <div className="space-y-1 text-xs text-gray-500">
                <p>Placeholders: {'{customer_name}'}, {'{business_name}'}, {'{google_link}'}</p>
                {templates?.placeholders?.length ? <p>{templates.placeholders.join(' • ')}</p> : null}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCampaignDialogOpen(false)}>Cancel</Button>
            <Button onClick={() => void handleCreateCampaign()} disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
              Create campaign
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
