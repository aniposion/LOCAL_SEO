'use client';
/* eslint-disable @next/next/no-img-element */

import { Suspense, useEffect, useEffectEvent, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  Send,
  Plus,
  Image as ImageIcon,
  Loader2,
  Search,
  AlertTriangle,
  SendHorizontal,
  BellRing,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { extractCollectionPayload, locationsApi, postsApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { toast } from 'sonner';
import Link from 'next/link';

interface Post {
  latest_publish_job?: {
    id: string;
    platform: string;
    status: string;
    tries: number;
    max_tries: number;
    last_error?: string | null;
    error_code?: string | null;
    next_run_at?: string | null;
    started_at?: string | null;
    completed_at?: string | null;
    platform_post_id?: string | null;
  } | null;
  id: string;
  title?: string | null;
  body?: string | null;
  platform: string;
  status: string;
  image_url?: string | null;
  created_at: string;
  updated_at: string;
  posted_at?: string | null;
  approval_requested_at?: string | null;
  approval_token?: string | null;
  error_message?: string | null;
  notification_sent: boolean;
  notification_channel?: string | null;
  notification_sent_at?: string | null;
  ai_image_url?: string | null;
}

interface LocationOption {
  id: string;
  name: string;
}

interface PublishIssue {
  job_id: string;
  post_id: string;
  location_id: string;
  location_name: string;
  title?: string | null;
  platform: string;
  job_status: string;
  post_status: string;
  tries: number;
  max_tries: number;
  can_retry: boolean;
  last_error?: string | null;
  error_code?: string | null;
  created_at: string;
  next_run_at?: string | null;
  completed_at?: string | null;
}

interface PublishIssueSummary {
  items: PublishIssue[];
  total: number;
  failed: number;
  retrying: number;
  limit: number;
}

const emptyPublishIssueSummary: PublishIssueSummary = {
  items: [],
  total: 0,
  failed: 0,
  retrying: 0,
  limit: 3,
};

const statusConfig: Record<string, { label: string; color: string; icon: LucideIcon }> = {
  pending_approval: { label: 'Pending', color: 'bg-yellow-100 text-yellow-700', icon: Clock },
  approved: { label: 'Approved', color: 'bg-green-100 text-green-700', icon: CheckCircle },
  rejected: { label: 'Rejected', color: 'bg-red-100 text-red-700', icon: XCircle },
  queued: { label: 'Queued', color: 'bg-sky-100 text-sky-700', icon: Clock },
  posted: { label: 'Published', color: 'bg-blue-100 text-blue-700', icon: Send },
  draft: { label: 'Draft', color: 'bg-gray-100 text-gray-700', icon: FileText },
  failed: { label: 'Failed', color: 'bg-red-100 text-red-700', icon: XCircle },
};

function ContentPageInner() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('status') || 'all';

  const [isLoading, setIsLoading] = useState(true);
  const [posts, setPosts] = useState<Post[]>([]);
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [publishIssueSummary, setPublishIssueSummary] = useState<PublishIssueSummary>(emptyPublishIssueSummary);
  const [selectedLocationId, setSelectedLocationId] = useState<string>('all');
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [failedPublishOnly, setFailedPublishOnly] = useState(false);
  const [selectedPost, setSelectedPost] = useState<Post | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [isActioning, setIsActioning] = useState(false);

  const fetchLocations = async () => {
    try {
      const response = await locationsApi.list();
      const nextLocations = extractCollectionPayload<LocationOption>(response.data, 'locations');
      setLocations(nextLocations);
    } catch {
      toast.error('Failed to load locations');
      setLocations([]);
    }
  };

  const fetchPosts = async () => {
    setIsLoading(true);
    try {
      const [postsResponse, issuesResponse] = await Promise.all([
        postsApi.list({
          locationId: selectedLocationId === 'all' ? undefined : selectedLocationId,
          search: searchQuery.trim() || undefined,
          platform: selectedPlatform === 'all' ? undefined : selectedPlatform,
        }),
        postsApi.getPublishIssues({
          locationId: selectedLocationId === 'all' ? undefined : selectedLocationId,
          search: searchQuery.trim() || undefined,
          platform: selectedPlatform === 'all' ? undefined : selectedPlatform,
          limit: 3,
        }),
      ]);
      setPosts(Array.isArray(postsResponse.data) ? postsResponse.data : []);
      setPublishIssueSummary(
        issuesResponse.data && Array.isArray(issuesResponse.data.items)
          ? {
              items: issuesResponse.data.items,
              total: Number(issuesResponse.data.total || 0),
              failed: Number(issuesResponse.data.failed || 0),
              retrying: Number(issuesResponse.data.retrying || 0),
              limit: Number(issuesResponse.data.limit || 3),
            }
          : emptyPublishIssueSummary
      );
    } catch {
      toast.error('Failed to load content');
      setPosts([]);
      setPublishIssueSummary(emptyPublishIssueSummary);
    } finally {
      setIsLoading(false);
    }
  };

  const loadLocationsOnMount = useEffectEvent(async () => {
    await fetchLocations();
  });

  const loadPostsWithFilters = useEffectEvent(async () => {
    await fetchPosts();
  });

  useEffect(() => {
    void loadLocationsOnMount();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadPostsWithFilters();
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery, selectedLocationId, selectedPlatform]);

  const handleApprove = async (post: Post) => {
    if (!post.approval_token) {
      toast.error('No approval token available');
      return;
    }

    setIsActioning(true);
    try {
      await postsApi.approve(post.id, post.approval_token);
      toast.success('Content approved');
      await fetchPosts();
      setIsPreviewOpen(false);
    } catch {
      toast.error('Failed to approve content');
    } finally {
      setIsActioning(false);
    }
  };

  const handleReject = async (post: Post) => {
    if (!post.approval_token) {
      toast.error('No approval token available');
      return;
    }

    setIsActioning(true);
    try {
      await postsApi.reject(post.id, post.approval_token);
      toast.success('Content rejected');
      await fetchPosts();
      setIsPreviewOpen(false);
    } catch {
      toast.error('Failed to reject content');
    } finally {
      setIsActioning(false);
    }
  };

  const handlePublish = async (post: Post) => {
    setIsActioning(true);
    try {
      await postsApi.publish(post.id);
      toast.success('Content published');
      await fetchPosts();
      setIsPreviewOpen(false);
    } catch {
      toast.error('Failed to publish content');
    } finally {
      setIsActioning(false);
    }
  };

  const handleRetryPublish = async (post: Post) => {
    setIsActioning(true);
    try {
      await postsApi.retryPublish(post.id);
      toast.success('Publish retry started');
      await fetchPosts();
      setIsPreviewOpen(false);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to retry publishing'));
    } finally {
      setIsActioning(false);
    }
  };

  const handleResendNotification = async (post: Post) => {
    setIsActioning(true);
    try {
      await postsApi.resendApprovalNotification(post.id);
      toast.success('Approval notification resent');
      await fetchPosts();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to resend approval notification'));
    } finally {
      setIsActioning(false);
    }
  };

  const filterPosts = (status: string) => {
    let nextPosts = posts;

    if (status === 'pending') {
      nextPosts = nextPosts.filter((p) => p.status === 'pending_approval');
    } else if (status !== 'all') {
      nextPosts = nextPosts.filter((p) => p.status === status);
    }

    if (failedPublishOnly) {
      nextPosts = nextPosts.filter((p) => p.latest_publish_job?.status === 'failed');
    }

    return nextPosts;
  };

  const counts = useMemo(
    () => ({
      all: posts.length,
      pending: posts.filter((p) => p.status === 'pending_approval').length,
      approved: posts.filter((p) => p.status === 'approved').length,
      posted: posts.filter((p) => p.status === 'posted').length,
      failed: posts.filter((p) => p.status === 'failed').length,
      failedPublishJobs: publishIssueSummary.total,
      notificationRetries: posts.filter((p) => p.status === 'pending_approval' && !p.notification_sent).length,
    }),
    [posts, publishIssueSummary.total]
  );

  const PostCard = ({ post }: { post: Post }) => {
    const config = statusConfig[post.status] || statusConfig.draft;
    const StatusIcon = config.icon;

    return (
      <Card
        className="cursor-pointer transition-shadow hover:shadow-md"
        onClick={() => {
          setSelectedPost(post);
          setIsPreviewOpen(true);
        }}
      >
        <CardContent className="p-4">
          <div className="flex gap-4">
            <div className="flex h-20 w-20 flex-shrink-0 items-center justify-center rounded-lg bg-gray-100">
              {(post.ai_image_url || post.image_url) ? (
                <img src={post.ai_image_url || post.image_url || ''} alt="" className="h-full w-full rounded-lg object-cover" />
              ) : (
                <ImageIcon className="h-8 w-8 text-gray-400" />
              )}
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="truncate font-semibold">{post.title || 'Untitled Post'}</h3>
                  <p className="mt-1 line-clamp-2 text-sm text-gray-500">
                    {post.body ? `${post.body.substring(0, 120)}${post.body.length > 120 ? '...' : ''}` : 'No content body'}
                  </p>
                </div>
                <Badge className={config.color}>
                  <StatusIcon className="mr-1 h-3 w-3" />
                  {config.label}
                </Badge>
              </div>

              <div className="mt-3 flex items-center gap-4 text-sm text-gray-500">
                <span className="capitalize">{post.platform.toLowerCase()}</span>
                <span>&bull;</span>
                <span>{new Date(post.created_at).toLocaleDateString()}</span>
                {post.status === 'pending_approval' && !post.notification_sent && (
                  <>
                    <span>&bull;</span>
                    <span className="text-amber-600">Notification failed</span>
                  </>
                )}
                {post.posted_at && (
                  <>
                    <span>&bull;</span>
                    <span>Published {new Date(post.posted_at).toLocaleDateString()}</span>
                  </>
                )}
                {post.latest_publish_job?.status === 'failed' && (
                  <>
                    <span>&bull;</span>
                    <span className="text-red-600">Latest publish failed</span>
                  </>
                )}
              </div>

              {post.latest_publish_job?.last_error && (
                <div className="mt-3 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {post.latest_publish_job.last_error}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <div className="flex gap-4">
                  <Skeleton className="h-20 w-20 rounded-lg" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-5 w-48" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-32" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Content</h1>
          <p className="text-gray-500">Manage approvals, publish retries, and channel-ready content from one place.</p>
        </div>
        <Link href="/dashboard/content/new">
          <Button className="bg-gradient-to-r from-violet-600 to-indigo-600">
            <Plus className="mr-2 h-4 w-4" />
            Create Content
          </Button>
        </Link>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Content Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {counts.failedPublishJobs > 0
                ? 'Fix failed publishing before creating more content'
                : counts.pending > 0
                  ? 'Approve pending content first'
                  : 'Create one useful customer-facing update'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Keep the queue moving in this order: fix failures, approve waiting posts, then create the next update.
            </p>
          </div>
          <Link href={counts.failedPublishJobs > 0 ? '/dashboard/integrations' : '/dashboard/content/new'}>
            <Button className="bg-white text-slate-950 hover:bg-slate-100">
              {counts.failedPublishJobs > 0 ? 'Check integrations' : 'Create content'}
            </Button>
          </Link>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardContent className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm text-gray-500">Needs approval</span>
              <Clock className="h-4 w-4 text-amber-500" />
            </div>
            <div className="text-3xl font-semibold">{counts.pending}</div>
            <p className="mt-1 text-sm text-gray-500">Posts waiting for owner approval.</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm text-gray-500">Ready to publish</span>
              <SendHorizontal className="h-4 w-4 text-blue-500" />
            </div>
            <div className="text-3xl font-semibold">{counts.approved}</div>
            <p className="mt-1 text-sm text-gray-500">Approved content that can go live now.</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm text-gray-500">Publish issues</span>
              <AlertTriangle className="h-4 w-4 text-red-500" />
            </div>
            <div className="text-3xl font-semibold">{counts.failedPublishJobs}</div>
            <p className="mt-1 text-sm text-gray-500">Latest failed or retrying publish jobs that still need attention.</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm text-gray-500">Resend needed</span>
              <BellRing className="h-4 w-4 text-violet-500" />
            </div>
            <div className="text-3xl font-semibold">{counts.notificationRetries}</div>
            <p className="mt-1 text-sm text-gray-500">Approval notices that need another send attempt.</p>
          </CardContent>
        </Card>
      </div>

      {publishIssueSummary.total > 0 && (
        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="space-y-4 p-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-red-700">
                  <AlertTriangle className="h-4 w-4" />
                  Publish health needs attention
                </div>
                <p className="mt-2 text-sm text-red-800">
                  {publishIssueSummary.total} actionable publish issue{publishIssueSummary.total === 1 ? '' : 's'} across the current content queue.
                  {' '}Failed: {publishIssueSummary.failed}. Retrying: {publishIssueSummary.retrying}.
                </p>
              </div>
              <Button
                variant="outline"
                className="border-red-200 bg-white text-red-700 hover:bg-red-100"
                onClick={() => setFailedPublishOnly(true)}
              >
                <AlertTriangle className="mr-2 h-4 w-4" />
                Focus failed posts
              </Button>
            </div>

            <div className="space-y-3">
              {publishIssueSummary.items.map((issue) => (
                <div
                  key={issue.job_id}
                  className="flex flex-col gap-3 rounded-lg border border-red-100 bg-white/80 p-3 md:flex-row md:items-start md:justify-between"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-gray-900">
                      {issue.title || 'Untitled post'}
                    </div>
                    <div className="mt-1 text-sm text-gray-600">
                      {issue.location_name} 쨌 {issue.platform} 쨌 attempts {issue.tries}/{issue.max_tries}
                    </div>
                    <div className="mt-1 text-sm text-red-700">
                      {issue.last_error || 'Latest publish attempt needs attention.'}
                    </div>
                    <div className="mt-1 text-xs text-gray-500">
                      Logged {new Date(issue.created_at).toLocaleString()}
                      {issue.next_run_at ? ` 쨌 retry scheduled ${new Date(issue.next_run_at).toLocaleString()}` : ''}
                    </div>
                  </div>
                  <Link href={`/dashboard/content/${issue.post_id}`}>
                    <Button variant="outline">Open Post</Button>
                  </Link>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search title, body, or publish error"
              className="pl-9"
            />
          </div>
          <Select value={selectedLocationId} onValueChange={setSelectedLocationId}>
            <SelectTrigger className="w-full md:w-[240px]">
              <SelectValue placeholder="All locations" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All locations</SelectItem>
              {locations.map((location) => (
                <SelectItem key={location.id} value={location.id}>
                  {location.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={selectedPlatform} onValueChange={setSelectedPlatform}>
            <SelectTrigger className="w-full md:w-[200px]">
              <SelectValue placeholder="All platforms" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All platforms</SelectItem>
              <SelectItem value="GBP">Google Business Profile</SelectItem>
              <SelectItem value="INSTAGRAM">Instagram</SelectItem>
              <SelectItem value="WEBSITE">Website</SelectItem>
            </SelectContent>
          </Select>
          {(selectedLocationId !== 'all' || selectedPlatform !== 'all' || searchQuery.trim()) && (
            <Button
              variant="outline"
              onClick={() => {
                setSelectedLocationId('all');
                setSelectedPlatform('all');
                setSearchQuery('');
                setFailedPublishOnly(false);
              }}
            >
              Clear filters
            </Button>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant={failedPublishOnly ? 'default' : 'outline'}
          onClick={() => setFailedPublishOnly((current) => !current)}
          className={failedPublishOnly ? 'bg-red-600 hover:bg-red-700' : ''}
        >
          <AlertTriangle className="mr-2 h-4 w-4" />
          Failed publish only
        </Button>
        {failedPublishOnly && (
          <span className="text-sm text-gray-500">
            Showing only posts whose latest publish attempt failed.
          </span>
        )}
      </div>

      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="all">All ({counts.all})</TabsTrigger>
          <TabsTrigger value="pending">Pending ({counts.pending})</TabsTrigger>
          <TabsTrigger value="approved">Approved ({counts.approved})</TabsTrigger>
          <TabsTrigger value="posted">Published ({counts.posted})</TabsTrigger>
          <TabsTrigger value="failed">Failed ({counts.failed})</TabsTrigger>
        </TabsList>

        {['all', 'pending', 'approved', 'posted', 'failed'].map((tab) => (
          <TabsContent key={tab} value={tab} className="mt-4 space-y-4">
            {filterPosts(tab).length > 0 ? (
              filterPosts(tab).map((post) => <PostCard key={post.id} post={post} />)
            ) : (
              <Card>
                <CardContent className="py-12 text-center text-gray-500">
                  <FileText className="mx-auto mb-4 h-12 w-12 text-gray-300" />
                  <p>No content found</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        ))}
      </Tabs>

      <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedPost?.title || 'Post Preview'}</DialogTitle>
            <DialogDescription>
              {selectedPost?.platform} ??{selectedPost && new Date(selectedPost.created_at).toLocaleDateString()}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {(selectedPost?.ai_image_url || selectedPost?.image_url) && (
              <img src={selectedPost?.ai_image_url || selectedPost?.image_url || ''} alt="" className="h-64 w-full rounded-lg object-cover" />
            )}
            <div className="prose prose-sm max-w-none">
              <p className="whitespace-pre-wrap">{selectedPost?.body || 'No content body'}</p>
            </div>
            {selectedPost?.status === 'pending_approval' && !selectedPost.notification_sent && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                Approval notification has not been delivered yet. Use resend to try again.
              </div>
            )}
            {selectedPost?.error_message && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {selectedPost.error_message}
              </div>
            )}
            {selectedPost?.latest_publish_job && (
              <div className="rounded-lg border p-3 text-sm">
                <div className="mb-2 font-medium">Latest publish job</div>
                <div className="space-y-1 text-gray-600">
                  <div>Status: {selectedPost.latest_publish_job.status}</div>
                  <div>Attempts: {selectedPost.latest_publish_job.tries} / {selectedPost.latest_publish_job.max_tries}</div>
                  {selectedPost.latest_publish_job.last_error && (
                    <div className="text-red-600">Last error: {selectedPost.latest_publish_job.last_error}</div>
                  )}
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            {selectedPost?.status === 'pending_approval' && (
              <>
                <Button variant="outline" onClick={() => handleResendNotification(selectedPost)} disabled={isActioning}>
                  {isActioning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                  Resend Notification
                </Button>
                <Button variant="outline" onClick={() => handleReject(selectedPost)} disabled={isActioning}>
                  <XCircle className="mr-2 h-4 w-4" />
                  Reject
                </Button>
                <Button onClick={() => handleApprove(selectedPost)} disabled={isActioning} className="bg-green-600 hover:bg-green-700">
                  {isActioning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle className="mr-2 h-4 w-4" />}
                  Approve
                </Button>
              </>
            )}
            {selectedPost?.status === 'approved' && (
              <Button onClick={() => handlePublish(selectedPost)} disabled={isActioning}>
                {isActioning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                Publish Now
              </Button>
            )}
            {selectedPost?.status === 'failed' && (
              <Button onClick={() => handleRetryPublish(selectedPost)} disabled={isActioning}>
                {isActioning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                Retry Publish
              </Button>
            )}
            {selectedPost && (
              <Link href={`/dashboard/content/${selectedPost.id}`}>
                <Button variant="outline">Open Details</Button>
              </Link>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function ContentPage() {
  return (
    <Suspense fallback={<div className="p-8"><Skeleton className="h-96 w-full" /></div>}>
      <ContentPageInner />
    </Suspense>
  );
}
