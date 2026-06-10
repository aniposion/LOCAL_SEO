'use client';
/* eslint-disable @next/next/no-img-element */

import { Suspense, useEffect, useEffectEvent, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  CheckCircle,
  XCircle,
  Loader2,
  Calendar,
  MapPin,
  AlertCircle,
  Clock,
} from 'lucide-react';
import { api, postsApi } from '@/lib/api';
import { getApiErrorStatus } from '@/lib/api-errors';

interface PostData {
  id: string;
  title: string;
  body: string;
  image_url?: string;
  platform: string;
  location_name: string;
  location_address: string;
  scheduled_at?: string;
  created_at: string;
}

type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired' | 'loading' | 'error';

function ApproveInner() {
  const params = useParams();
  const searchParams = useSearchParams();
  const postId = params.token as string;
  const approvalToken = searchParams.get('token');
  const action = searchParams.get('action');

  const [status, setStatus] = useState<ApprovalStatus>('loading');
  const [post, setPost] = useState<PostData | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const fetchPostData = async () => {
    try {
      const response = await api.get(`/approval/posts/${postId}/preview`, {
        params: { token: approvalToken },
      });
      const data = response.data;
      setPost({
        id: data.id,
        title: data.title,
        body: data.body,
        image_url: data.image_url,
        platform: data.platform,
        location_name: data.location?.name || 'Unknown location',
        location_address: [data.location?.address, data.location?.city].filter(Boolean).join(', '),
        scheduled_at: data.scheduled_at,
        created_at: data.created_at || data.approval_requested_at || '',
      });
      setStatus('pending');
      setErrorMessage('');
      return true;
    } catch (error) {
      const status = getApiErrorStatus(error);
      if (status === 410) {
        setStatus('expired');
        setErrorMessage('This approval link has expired. Ask your team to send a new approval link from the dashboard.');
      } else if (status === 404) {
        setStatus('error');
        setErrorMessage('This approval link was not found. It may have been revoked.');
      } else {
        setStatus('error');
        setErrorMessage('We could not load this approval link right now. Please try again later or ask your team to reopen it from the dashboard.');
      }
      return false;
    }
  };

  const handleApprovalDecision = async (decision: 'approve' | 'reject') => {
    if (!approvalToken) return;
    setIsSubmitting(true);
    try {
      if (decision === 'approve') {
        await postsApi.approve(postId, approvalToken);
        setStatus('approved');
      } else {
        await postsApi.reject(postId, approvalToken);
        setStatus('rejected');
      }
    } catch {
      setStatus('error');
      setErrorMessage(
        decision === 'approve'
          ? 'We could not approve this content right now. Please return to the dashboard and try again.'
          : 'We could not reject this content right now. Please return to the dashboard and try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const runInitialApprovalAction = useEffectEvent(async () => {
    const loaded = await fetchPostData();
    if (!loaded) return;

    if (action === 'approve' || action === 'reject') {
      await handleApprovalDecision(action);
    }
  });

  useEffect(() => {
    if (!postId || !approvalToken) {
      setStatus('error');
      setErrorMessage('This approval link is incomplete. Ask your team to send a new approval link from the dashboard.');
      return;
    }

    void runInitialApprovalAction();
  }, [postId, approvalToken, action]);

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-violet-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading content...</p>
        </div>
      </div>
    );
  }

  if (status === 'expired') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="pt-8 text-center">
            <Clock className="w-16 h-16 text-orange-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold mb-2">Link Expired</h2>
            <p className="text-gray-600 mb-6">{errorMessage}</p>
            <p className="text-sm text-gray-500">
              Please log in to your dashboard to manage this content.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="pt-8 text-center space-y-4">
            <AlertCircle className="w-16 h-16 text-red-500 mx-auto" />
            <h2 className="text-xl font-bold">We could not load this approval link</h2>
            <p className="text-gray-600">{errorMessage}</p>
            <a href="https://app.localseooptimizer.com/dashboard" className="inline-flex items-center justify-center rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white">Go to dashboard</a>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === 'approved') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="pt-8 text-center">
            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-12 h-12 text-green-600" />
            </div>
            <h2 className="text-2xl font-bold text-green-700 mb-2">Approved!</h2>
            <p className="text-gray-600 mb-6">
              {post?.scheduled_at
                ? 'The content has been approved and will keep its scheduled publish time.'
                : 'The content has been approved and moved into the publish queue.'}
            </p>
            <div className="p-4 bg-gray-50 rounded-lg text-left">
              <p className="font-medium">{post?.title}</p>
              <p className="text-sm text-gray-500 mt-1">
                {post?.scheduled_at
                  ? `Scheduled for ${new Date(post.scheduled_at).toLocaleString()}`
                  : 'Queued for publishing'
                }
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === 'rejected') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="pt-8 text-center">
            <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <XCircle className="w-12 h-12 text-red-600" />
            </div>
            <h2 className="text-2xl font-bold text-red-700 mb-2">Rejected</h2>
            <p className="text-gray-600">
              The content has been rejected and will not be published.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Content Approval</h1>
          <p className="text-gray-600 mt-1">Review this content, then approve or reject it.</p>
        </div>

        {/* Post Preview */}
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{post?.title}</CardTitle>
                <CardDescription className="flex items-center gap-2 mt-1">
                  <MapPin className="w-4 h-4" />
                  {post?.location_name}
                </CardDescription>
              </div>
              <Badge>{post?.platform}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Image */}
            {post?.image_url && (
              <div className="relative aspect-video rounded-lg overflow-hidden bg-gray-100">
                <img
                  src={post.image_url}
                  alt="Post preview"
                  className="w-full h-full object-cover"
                />
              </div>
            )}

            {/* Body */}
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="whitespace-pre-wrap text-gray-700">{post?.body}</p>
            </div>

            {/* Meta Info */}
            <div className="flex items-center gap-4 text-sm text-gray-500">
              <div className="flex items-center gap-1">
                <MapPin className="w-4 h-4" />
                {post?.location_address}
              </div>
              {post?.scheduled_at && (
                <div className="flex items-center gap-1">
                  <Calendar className="w-4 h-4" />
                  {new Date(post.scheduled_at).toLocaleString()}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Action Buttons */}
        <div className="grid grid-cols-2 gap-4">
          <Button
            variant="outline"
            size="lg"
            className="h-16 text-red-600 border-red-200 hover:bg-red-50"
            onClick={() => void handleApprovalDecision('reject')}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                <XCircle className="w-5 h-5 mr-2" />
                Reject
              </>
            )}
          </Button>

          <Button
            size="lg"
            className="h-16 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
            onClick={() => void handleApprovalDecision('approve')}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                <CheckCircle className="w-5 h-5 mr-2" />
                Approve
              </>
            )}
          </Button>
        </div>

        <p className="mt-4 text-center text-sm text-gray-500">
          Need copy changes first? Reject this draft and request revisions from the dashboard.
        </p>

        {/* Footer Note */}
        <p className="text-center text-sm text-gray-500 mt-6">
          This link expires in 72 hours. No login required.
        </p>
      </div>
    </div>
  );
}

export default function ApprovePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-12 h-12 animate-spin text-violet-600" />
      </div>
    }>
      <ApproveInner />
    </Suspense>
  );
}
