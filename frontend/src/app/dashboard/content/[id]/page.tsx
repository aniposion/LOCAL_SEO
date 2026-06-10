'use client';
/* eslint-disable @next/next/no-img-element */

import { useEffect, useEffectEvent, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ArrowLeft,
  Save,
  Trash2,
  Loader2,
  Calendar,
  CheckCircle,
  Clock,
  XCircle,
  Send,
  Download,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { postsApi } from '@/lib/api';
import { getApiErrorMessage, getApiErrorStatus } from '@/lib/api-errors';
import { toast } from 'sonner';

interface ContentPost {
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
  image_url?: string | null;
  ai_image_url?: string | null;
  platform: string;
  status: 'draft' | 'pending_approval' | 'approved' | 'posted' | 'rejected' | 'queued' | 'failed';
  location_id: string;
  scheduled_at?: string | null;
  posted_at?: string | null;
  approval_requested_at?: string | null;
  created_at: string;
  updated_at: string;
  approval_token?: string | null;
  error_message?: string | null;
  notification_sent: boolean;
  notification_channel?: string | null;
  notification_sent_at?: string | null;
}

interface PublishJobHistoryItem {
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
  created_at: string;
  updated_at: string;
  platform_post_id?: string | null;
}

const PUBLISH_JOB_PAGE_SIZE = 10;

export default function ContentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const contentId = params.id as string;

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [post, setPost] = useState<ContentPost | null>(null);
  const [publishJobs, setPublishJobs] = useState<PublishJobHistoryItem[]>([]);
  const [jobStatusFilter, setJobStatusFilter] = useState('all');
  const [jobSearch, setJobSearch] = useState('');
  const [jobTotal, setJobTotal] = useState(0);
  const [jobOffset, setJobOffset] = useState(0);

  const [editTitle, setEditTitle] = useState('');
  const [editBody, setEditBody] = useState('');
  const [editScheduledAt, setEditScheduledAt] = useState('');

  const fetchContent = async () => {
    try {
      const postResponse = await postsApi.get(contentId);
      const data = postResponse.data;
      setPost(data);
      setEditTitle(data.title || '');
      setEditBody(data.body || '');
      setEditScheduledAt(data.scheduled_at || '');
    } catch {
      toast.error('Failed to load content');
      setPost(null);
      setPublishJobs([]);
    } finally {
      setIsLoading(false);
    }
  };

  const loadContentOnMount = useEffectEvent(async () => {
    await fetchContent();
  });

  useEffect(() => {
    void loadContentOnMount();
  }, [contentId]);

  const fetchPublishJobs = async () => {
    try {
      const jobsResponse = await postsApi.getPublishJobs(contentId, {
        status: jobStatusFilter === 'all' ? undefined : jobStatusFilter,
        search: jobSearch.trim() || undefined,
        limit: PUBLISH_JOB_PAGE_SIZE,
        offset: jobOffset,
      });
      setPublishJobs(Array.isArray(jobsResponse.data?.items) ? jobsResponse.data.items : []);
      setJobTotal(jobsResponse.data?.total || 0);
    } catch {
      setPublishJobs([]);
      setJobTotal(0);
    }
  };

  const loadPublishJobs = useEffectEvent(async () => {
    await fetchPublishJobs();
  });

  useEffect(() => {
    if (!contentId) return;

    const timer = setTimeout(() => {
      void loadPublishJobs();
    }, 250);

    return () => clearTimeout(timer);
  }, [contentId, jobOffset, jobSearch, jobStatusFilter]);

  const handleSave = async () => {
    if (!editTitle.trim() || !editBody.trim()) {
      toast.error('Title and content are required');
      return;
    }

    setIsSaving(true);
    try {
      const response = await postsApi.update(contentId, {
        title: editTitle,
        body: editBody,
        scheduled_at: editScheduledAt || null,
      });
      setPost(response.data);
      setEditTitle(response.data.title || '');
      setEditBody(response.data.body || '');
      setEditScheduledAt(response.data.scheduled_at || '');
      setIsEditing(false);
      toast.success('Content saved successfully');
    } catch {
      toast.error('Failed to save content');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await postsApi.delete(contentId);
      toast.success('Content deleted');
      router.push('/dashboard/content');
    } catch {
      toast.error('Failed to delete content');
    }
  };

  const handlePublish = async () => {
    setIsSaving(true);
    try {
      await postsApi.publish(contentId);
      await fetchContent();
      await fetchPublishJobs();
      toast.success('Content published');
    } catch {
      toast.error('Failed to publish content');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRetryPublish = async () => {
    setIsSaving(true);
    try {
      await postsApi.retryPublish(contentId);
      await fetchContent();
      await fetchPublishJobs();
      toast.success('Publish retry started');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to retry publishing'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleSendForApproval = async () => {
    setIsSaving(true);
    try {
      const response = await postsApi.requestApproval(contentId);
      setPost(response.data);
      toast.success('Sent for approval');
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to send content for approval');
      if (getApiErrorStatus(error) === 502) {
        await fetchContent();
      }
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleResendNotification = async () => {
    setIsSaving(true);
    try {
      await postsApi.resendApprovalNotification(contentId);
      await fetchContent();
      await fetchPublishJobs();
      toast.success('Approval notification resent');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to resend approval notification'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleExportPublishJobs = async () => {
    try {
      const response = await postsApi.exportPublishJobs(contentId, {
        status: jobStatusFilter === 'all' ? undefined : jobStatusFilter,
        search: jobSearch.trim() || undefined,
      });
      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `publish-jobs-${contentId}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Publish job history exported');
    } catch {
      toast.error('Failed to export publish job history');
    }
  };

  const getStatusBadge = (status: ContentPost['status']) => {
    switch (status) {
      case 'draft':
        return <Badge variant="secondary">Draft</Badge>;
      case 'pending_approval':
        return <Badge className="bg-yellow-100 text-yellow-700"><Clock className="mr-1 h-3 w-3" />Pending Approval</Badge>;
      case 'approved':
        return <Badge className="bg-blue-100 text-blue-700"><CheckCircle className="mr-1 h-3 w-3" />Approved</Badge>;
      case 'queued':
        return <Badge className="bg-sky-100 text-sky-700"><Clock className="mr-1 h-3 w-3" />Queued</Badge>;
      case 'posted':
        return <Badge className="bg-green-100 text-green-700"><Send className="mr-1 h-3 w-3" />Published</Badge>;
      case 'rejected':
        return <Badge className="bg-red-100 text-red-700"><XCircle className="mr-1 h-3 w-3" />Rejected</Badge>;
      case 'failed':
        return <Badge className="bg-red-100 text-red-700"><XCircle className="mr-1 h-3 w-3" />Failed</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="mb-4 h-64 w-full" />
            <Skeleton className="mb-2 h-6 w-3/4" />
            <Skeleton className="h-4 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!post) {
    return (
      <div className="py-12 text-center">
        <p className="text-gray-500">Content not found</p>
        <Link href="/dashboard/content">
          <Button variant="link">Back to Content</Button>
        </Link>
      </div>
    );
  }

  const contentNextAction = (() => {
    if (isEditing) {
      return {
        title: 'Save the final version',
        description: 'Lock in the title, copy, and schedule before this post moves into approval or publishing.',
      };
    }

    switch (post.status) {
      case 'approved':
        return {
          title: 'Publish this approved post',
          description: 'The content is approved. Send it live now so customers see fresh activity on your profile.',
        };
      case 'failed':
        return {
          title: 'Retry the failed publish',
          description: 'Publishing did not complete. Retry after checking the latest error and connection status.',
        };
      case 'pending_approval':
        return {
          title: post.notification_sent ? 'Wait for approval or resend the reminder' : 'Resend the approval request',
          description: post.notification_sent
            ? 'This post is waiting on a human yes. Resend only if the approver may have missed it.'
            : 'The approval notification did not go out, so resend it before waiting on a response.',
        };
      case 'queued':
        return {
          title: 'Let the queue finish publishing',
          description: 'This post is already queued. Use the job history below only if it gets stuck or fails.',
        };
      case 'posted':
        return {
          title: 'Review published content performance',
          description: 'This post is live. Use the content list and reports to decide what to publish next.',
        };
      default:
        return {
          title: 'Send this post for approval',
          description: 'Approvals protect your brand voice before content reaches Google, social, or your website.',
        };
    }
  })();

  const imageUrl = post.ai_image_url || post.image_url;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/dashboard/content">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-1 h-4 w-4" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">{isEditing ? 'Edit Content' : 'Content Details'}</h1>
            <p className="text-gray-500">{post.platform}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">{getStatusBadge(post.status)}</div>
      </div>

      <Card className="border-emerald-200 bg-gradient-to-br from-emerald-50 to-white">
        <CardContent className="space-y-4 p-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">Next Best Action</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">{contentNextAction.title}</h2>
            <p className="mt-2 text-sm text-slate-600">{contentNextAction.description}</p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            {isEditing ? (
              <Button onClick={handleSave} disabled={isSaving}>
                {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                Save Content
              </Button>
            ) : post.status === 'approved' ? (
              <Button onClick={handlePublish} disabled={isSaving}>
                {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                Publish Now
              </Button>
            ) : post.status === 'failed' ? (
              <Button onClick={handleRetryPublish} disabled={isSaving}>
                {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                Retry Publish
              </Button>
            ) : post.status === 'pending_approval' ? (
              <Button variant="outline" onClick={handleResendNotification} disabled={isSaving}>
                {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                Resend Notification
              </Button>
            ) : post.status === 'queued' ? (
              <Button disabled>Publishing Queued</Button>
            ) : post.status === 'posted' ? (
              <Button asChild>
                <Link href="/dashboard/content">View Content Calendar</Link>
              </Button>
            ) : (
              <Button onClick={handleSendForApproval} disabled={isSaving}>
                {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Clock className="mr-2 h-4 w-4" />}
                Send for Approval
              </Button>
            )}
            {!isEditing && post.status !== 'posted' && (
              <Button variant="outline" onClick={() => setIsEditing(true)}>
                Edit Copy First
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{isEditing ? 'Edit Post' : post.title || 'Untitled Post'}</CardTitle>
              <CardDescription className="mt-1 flex items-center gap-4">
                {post.scheduled_at && (
                  <span className="flex items-center gap-1">
                    <Calendar className="h-4 w-4" />
                    Scheduled: {new Date(post.scheduled_at).toLocaleString()}
                  </span>
                )}
                {post.posted_at && (
                  <span className="flex items-center gap-1">
                    <Send className="h-4 w-4" />
                    Published: {new Date(post.posted_at).toLocaleString()}
                  </span>
                )}
              </CardDescription>
            </div>
            {!isEditing && (
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
                  Edit
                </Button>
                <Button variant="outline" size="sm" className="text-red-600" onClick={() => setIsDeleteDialogOpen(true)}>
                  <Trash2 className="mr-1 h-4 w-4" />
                  Delete
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {isEditing ? (
            <>
              <div className="space-y-2">
                <Label>Title</Label>
                <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} placeholder="Post title" />
              </div>

              <div className="space-y-2">
                <Label>Content</Label>
                <textarea
                  className="h-48 w-full resize-none rounded-lg border p-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
                  value={editBody}
                  onChange={(e) => setEditBody(e.target.value)}
                  placeholder="Post content..."
                />
              </div>

              <div className="space-y-2">
                <Label>Schedule (optional)</Label>
                <Input
                  type="datetime-local"
                  value={editScheduledAt ? editScheduledAt.slice(0, 16) : ''}
                  onChange={(e) => setEditScheduledAt(e.target.value ? new Date(e.target.value).toISOString() : '')}
                />
              </div>

              <div className="flex gap-3">
                <Button variant="outline" onClick={() => setIsEditing(false)}>
                  Cancel
                </Button>
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                  Save Changes
                </Button>
              </div>
            </>
          ) : (
            <>
              {imageUrl && (
                <div className="relative aspect-video overflow-hidden rounded-lg bg-gray-100">
                  <img src={imageUrl} alt="Post image" className="h-full w-full object-cover" />
                </div>
              )}

              <div className="rounded-lg bg-gray-50 p-4">
                <p className="whitespace-pre-wrap text-gray-700">{post.body || 'No content body'}</p>
              </div>

              {post.error_message && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  {post.error_message}
                </div>
              )}
              {post.latest_publish_job && (
                <div className="rounded-lg border p-4 text-sm">
                  <div className="mb-2 font-medium">Latest publish job</div>
                  <div className="space-y-1 text-gray-600">
                    <div>Status: {post.latest_publish_job.status}</div>
                    <div>Attempts: {post.latest_publish_job.tries} / {post.latest_publish_job.max_tries}</div>
                    {post.latest_publish_job.last_error && (
                      <div className="text-red-600">Last error: {post.latest_publish_job.last_error}</div>
                    )}
                    {post.latest_publish_job.platform_post_id && (
                      <div>Provider post id: {post.latest_publish_job.platform_post_id}</div>
                    )}
                  </div>
                </div>
              )}

              <div className="rounded-lg border p-4 text-sm">
                <div className="mb-3 font-medium">Publish job history</div>
                <div className="mb-3 grid gap-3 md:grid-cols-[180px_1fr]">
                  <select
                    className="h-10 rounded-md border bg-white px-3 text-sm"
                    value={jobStatusFilter}
                    onChange={(e) => {
                      setJobStatusFilter(e.target.value);
                      setJobOffset(0);
                    }}
                  >
                    <option value="all">All statuses</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                    <option value="processing">Processing</option>
                    <option value="pending">Pending</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                  <Input
                    value={jobSearch}
                    onChange={(e) => {
                      setJobSearch(e.target.value);
                      setJobOffset(0);
                    }}
                    placeholder="Search by error, status, or provider post id"
                  />
                </div>
                <div className="mb-3 flex justify-end">
                  <Button variant="outline" size="sm" onClick={handleExportPublishJobs}>
                    <Download className="mr-2 h-4 w-4" />
                    Export CSV
                  </Button>
                </div>
                {publishJobs.length > 0 ? (
                  <div className="space-y-3">
                    {publishJobs.map((job) => (
                      <div key={job.id} className="rounded-lg border bg-gray-50 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="font-medium capitalize">
                            {job.platform.toLowerCase()} - {job.status}
                          </div>
                          <div className="text-xs text-gray-500">
                            {new Date(job.created_at).toLocaleString()}
                          </div>
                        </div>
                        <div className="mt-2 space-y-1 text-gray-600">
                          <div>Attempts: {job.tries} / {job.max_tries}</div>
                          {job.platform_post_id && <div>Provider post id: {job.platform_post_id}</div>}
                          {job.completed_at && <div>Completed: {new Date(job.completed_at).toLocaleString()}</div>}
                          {job.last_error && <div className="text-red-600">Last error: {job.last_error}</div>}
                        </div>
                      </div>
                    ))}
                    <div className="flex items-center justify-between border-t pt-3 text-sm text-gray-500">
                      <span>
                        Showing {jobTotal === 0 ? 0 : jobOffset + 1}-
                        {Math.min(jobOffset + publishJobs.length, jobTotal)} of {jobTotal}
                      </span>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={jobOffset === 0}
                          onClick={() => setJobOffset((current) => Math.max(0, current - PUBLISH_JOB_PAGE_SIZE))}
                        >
                          Previous
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={jobOffset + publishJobs.length >= jobTotal}
                          onClick={() => setJobOffset((current) => current + PUBLISH_JOB_PAGE_SIZE)}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-gray-500">
                    {jobTotal === 0 ? 'No publish jobs recorded yet.' : 'No publish jobs match the current filters.'}
                  </div>
                )}
              </div>

              {post.status === 'pending_approval' && !post.notification_sent && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                  Approval notification has not been delivered. Resend it before waiting on approval.
                </div>
              )}

              <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
                <div>
                  <p className="text-gray-500">Created</p>
                  <p className="font-medium">{new Date(post.created_at).toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-gray-500">Last Updated</p>
                  <p className="font-medium">{new Date(post.updated_at).toLocaleString()}</p>
                </div>
                {post.scheduled_at && (
                  <div>
                    <p className="text-gray-500">Scheduled For</p>
                    <p className="font-medium">{new Date(post.scheduled_at).toLocaleString()}</p>
                  </div>
                )}
                {post.posted_at && (
                  <div>
                    <p className="text-gray-500">Published</p>
                    <p className="font-medium">{new Date(post.posted_at).toLocaleString()}</p>
                  </div>
                )}
                {post.status === 'pending_approval' && (
                  <div>
                    <p className="text-gray-500">Notification</p>
                    <p className="font-medium">{post.notification_sent ? 'Sent' : 'Failed'}</p>
                  </div>
                )}
              </div>

              {post.status === 'approved' && (
                <Button onClick={handlePublish} disabled={isSaving}>
                  {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                  Publish Now
                </Button>
              )}
              {post.status === 'failed' && (
                <Button onClick={handleRetryPublish} disabled={isSaving}>
                  {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                  Retry Publish
                </Button>
              )}

              {(post.status === 'draft' || post.status === 'rejected') && (
                <Button onClick={handleSendForApproval} disabled={isSaving}>
                  {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Clock className="mr-2 h-4 w-4" />}
                  Send for Approval
                </Button>
              )}

              {post.status === 'pending_approval' && (
                <Button variant="outline" onClick={handleResendNotification} disabled={isSaving}>
                  {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                  Resend Notification
                </Button>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Content</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this content? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
