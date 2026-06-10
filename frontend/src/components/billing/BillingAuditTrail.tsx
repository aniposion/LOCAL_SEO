'use client';

import { useEffect, useEffectEvent, useState } from 'react';
import { Activity, RefreshCw, Webhook } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { billingApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { toast } from 'sonner';

interface BillingAuditItem {
  id: string;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
  old_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
  description?: string | null;
  created_at: string;
}

interface BillingAuditResponse {
  items: BillingAuditItem[];
  total: number;
}

interface BillingWebhookEventItem {
  id: number;
  event_id: string;
  event_type: string;
  account_match_source: string;
  related_customer?: string | null;
  related_subscription?: string | null;
  created_at?: string | null;
}

interface BillingWebhookEventResponse {
  items: BillingWebhookEventItem[];
  total: number;
}

const ACTION_LABELS: Record<string, string> = {
  subscription_created: 'Subscription created',
  subscription_updated: 'Subscription updated',
  subscription_canceled: 'Subscription canceled',
  subscription_resumed: 'Subscription resumed',
  plan_changed: 'Plan changed',
  payment_succeeded: 'Payment succeeded',
  payment_failed: 'Payment failed',
  refund_created: 'Refund created',
  dispute_created: 'Dispute created',
  dispute_updated: 'Dispute updated',
  payment_method_added: 'Payment method added',
  payment_method_removed: 'Payment method removed',
  payment_method_default_changed: 'Default payment method changed',
  billing_info_updated: 'Billing info updated',
  invoice_sent: 'Invoice sent',
};

function formatDate(value?: string | null) {
  if (!value) {
    return 'Unknown time';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
}

function formatAuditAction(action: string) {
  return ACTION_LABELS[action] || action.replaceAll('_', ' ');
}

function summarizeChange(value?: Record<string, unknown> | null) {
  if (!value || Object.keys(value).length === 0) {
    return null;
  }

  const preview = Object.entries(value)
    .slice(0, 3)
    .map(([key, entryValue]) => `${key}: ${String(entryValue)}`)
    .join(' 쨌 ');

  return preview || null;
}

function summarizeEntity(item: BillingAuditItem) {
  if (!item.entity_type && !item.entity_id) {
    return 'No entity reference recorded.';
  }

  if (!item.entity_id) {
    return item.entity_type || 'Unknown entity';
  }

  const shortId = item.entity_id.length > 18 ? `${item.entity_id.slice(0, 18)}...` : item.entity_id;
  return `${item.entity_type || 'entity'} 쨌 ${shortId}`;
}

export function BillingAuditTrail() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [auditItems, setAuditItems] = useState<BillingAuditItem[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [webhookItems, setWebhookItems] = useState<BillingWebhookEventItem[]>([]);
  const [webhookTotal, setWebhookTotal] = useState(0);

  const runLoadAuditTrail = async (manual: boolean = false) => {
    if (manual) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    const [auditResult, webhookResult] = await Promise.allSettled([
      billingApi.getAudit({ limit: 8 }),
      billingApi.getWebhookEvents({ limit: 8 }),
    ]);

    const errors: string[] = [];

    if (auditResult.status === 'fulfilled') {
      const data = auditResult.value.data as BillingAuditResponse;
      setAuditItems(data.items || []);
      setAuditTotal(data.total || 0);
    } else {
      setAuditItems([]);
      setAuditTotal(0);
      errors.push(getApiErrorMessage(auditResult.reason, 'Billing audit could not be loaded.'));
    }

    if (webhookResult.status === 'fulfilled') {
      const data = webhookResult.value.data as BillingWebhookEventResponse;
      setWebhookItems(data.items || []);
      setWebhookTotal(data.total || 0);
    } else {
      setWebhookItems([]);
      setWebhookTotal(0);
      errors.push(getApiErrorMessage(webhookResult.reason, 'Stripe webhook history could not be loaded.'));
    }

    const combinedError = errors.join(' ');
    setErrorMessage(combinedError || null);

    if (manual && combinedError) {
      toast.error(combinedError);
    }

    if (manual) {
      setRefreshing(false);
    } else {
      setLoading(false);
    }
  };

  const loadAuditTrailOnMount = useEffectEvent(async () => {
    await runLoadAuditTrail(false);
  });

  useEffect(() => {
    void loadAuditTrailOnMount();
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Operations audit trail</h3>
          <p className="text-sm text-gray-500">
            Review recent billing actions and Stripe webhook receipts for this account.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void runLoadAuditTrail(true)}
          disabled={refreshing}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {errorMessage ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {errorMessage}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Billing actions
            </CardTitle>
            <CardDescription>
              {auditTotal > 0
                ? `${auditTotal} recent account-scoped billing events are available.`
                : 'No billing audit events have been recorded for this account yet.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {auditItems.length === 0 ? (
              <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
                Billing changes will appear here after subscriptions, invoices, disputes, or payment methods change.
              </div>
            ) : (
              <div className="space-y-3">
                {auditItems.map((item) => (
                  <div key={item.id} className="rounded-lg border bg-gray-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Badge variant="secondary">{formatAuditAction(item.action)}</Badge>
                      <span className="text-xs text-gray-500">{formatDate(item.created_at)}</span>
                    </div>
                    <div className="mt-2 text-sm font-medium text-gray-900">{summarizeEntity(item)}</div>
                    <div className="mt-1 text-sm text-gray-600">
                      {item.description ||
                        summarizeChange(item.new_value) ||
                        summarizeChange(item.old_value) ||
                        'No additional details were recorded for this event.'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Webhook className="h-5 w-5" />
              Stripe webhook receipts
            </CardTitle>
            <CardDescription>
              {webhookTotal > 0
                ? `${webhookTotal} recent Stripe events matched this account.`
                : 'No Stripe webhook receipts are currently linked to this account.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {webhookItems.length === 0 ? (
              <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
                Stripe checkout, invoice, and subscription events will appear here after Stripe hits the webhook.
              </div>
            ) : (
              <div className="space-y-3">
                {webhookItems.map((item) => (
                  <div key={item.id} className="rounded-lg border bg-gray-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Badge variant="outline">{item.event_type}</Badge>
                      <span className="text-xs text-gray-500">{formatDate(item.created_at)}</span>
                    </div>
                    <div className="mt-2 break-all font-mono text-xs text-gray-700">{item.event_id}</div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-600">
                      <span>Matched by {item.account_match_source}</span>
                      {item.related_customer ? <span>Customer {item.related_customer}</span> : null}
                      {item.related_subscription ? (
                        <span>Subscription {item.related_subscription}</span>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
