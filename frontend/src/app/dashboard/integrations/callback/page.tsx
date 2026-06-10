'use client';

import { Suspense, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, CheckCircle2, Loader2, XCircle } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

function IntegrationsCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const provider = searchParams.get('provider') || 'integration';
  const statusValue = searchParams.get('status') || 'failed';
  const message = searchParams.get('message');
  const accountName = searchParams.get('account_name');

  const view = useMemo(() => {
    if (statusValue === 'connected') {
      return {
        icon: <CheckCircle2 className="h-10 w-10 text-green-600" />,
        title: `${provider} connected`,
        description: accountName
          ? `Connected account: ${accountName}`
          : 'The channel is ready for publishing and automation.',
        tone: 'text-green-700',
      };
    }
    if (statusValue === 'cancelled') {
      return {
        icon: <AlertCircle className="h-10 w-10 text-amber-600" />,
        title: `${provider} connection cancelled`,
        description: message || 'The authorization flow was cancelled before completion.',
        tone: 'text-amber-700',
      };
    }
    return {
      icon: <XCircle className="h-10 w-10 text-red-600" />,
      title: `${provider} connection failed`,
      description: message || 'The authorization flow did not complete successfully.',
      tone: 'text-red-700',
    };
  }, [accountName, message, provider, statusValue]);

  useEffect(() => {
    if (statusValue === 'connected') {
      const timer = window.setTimeout(() => {
        router.replace('/dashboard/integrations');
      }, 2500);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [router, statusValue]);

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-xl items-center justify-center p-6">
      <Card className="w-full">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4">{view.icon}</div>
          <CardTitle className="text-2xl capitalize">{view.title}</CardTitle>
          <CardDescription className={view.tone}>{view.description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-center">
          {statusValue === 'connected' && (
            <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Returning to integrations...
            </div>
          )}
          {statusValue !== 'connected' ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-left text-sm text-amber-900">
              <p className="font-medium">Next action</p>
              <p className="mt-1">
                Go back to Integrations and retry the connection. If the provider keeps failing,
                send the account name and this message to support so we can finish the setup manually.
              </p>
            </div>
          ) : null}
          <div className="flex justify-center gap-3">
            <Link href="/dashboard/integrations">
              <Button>{statusValue === 'connected' ? 'Back to Integrations' : 'Retry in Integrations'}</Button>
            </Link>
            {statusValue !== 'connected' ? (
              <Link href="/contact?subject=Integration%20connection%20help">
                <Button variant="outline">Contact support</Button>
              </Link>
            ) : null}
            <Link href="/dashboard">
              <Button variant="outline">Open Dashboard</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function IntegrationsCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto flex min-h-[70vh] max-w-xl items-center justify-center p-6">
          <Card className="w-full">
            <CardContent className="flex min-h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
            </CardContent>
          </Card>
        </div>
      }
    >
      <IntegrationsCallbackContent />
    </Suspense>
  );
}
