'use client';

import Link from 'next/link';
import { useEffect, useEffectEvent, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Copy,
  CreditCard,
  Download,
  Image as ImageIcon,
  Loader2,
  Mail,
  MessageSquare,
  RefreshCw,
  ShieldAlert,
  Users,
  Wallet,
} from 'lucide-react';
import { toast } from 'sonner';

import { adminApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';

const USAGE_LIMIT_FIELDS = [
  { key: 'sms_daily', label: 'SMS daily' },
  { key: 'sms_monthly', label: 'SMS monthly' },
  { key: 'ai_content_daily', label: 'AI content daily' },
  { key: 'ai_content_monthly', label: 'AI content monthly' },
  { key: 'ai_image_daily', label: 'AI image daily' },
  { key: 'ai_image_monthly', label: 'AI image monthly' },
  { key: 'ai_response_daily', label: 'AI response daily' },
  { key: 'ai_response_monthly', label: 'AI response monthly' },
  { key: 'api_calls_daily', label: 'API calls daily' },
  { key: 'api_calls_monthly', label: 'API calls monthly' },
] as const;

type UsageLimitFieldKey = (typeof USAGE_LIMIT_FIELDS)[number]['key'];

type UsageLimitFormValues = Record<UsageLimitFieldKey, string>;

interface UserCustomLimits {
  plan_type?: string;
  status?: string;
  locations_limit?: number;
  posts_per_month?: number;
  api_calls_per_day?: number;
  agency_location_count?: number;
  active_addons?: string[];
  usage_overrides?: Partial<Record<UsageLimitFieldKey, number>>;
  effective_usage_limits?: Partial<Record<UsageLimitFieldKey, number>>;
}

interface User {
  id: string;
  email: string;
  full_name: string | null;
  plan: string;
  credits: number;
  status: string;
  created_at: string;
  last_login: string | null;
  custom_limits?: UserCustomLimits | null;
}

interface UsersResponse {
  users: User[];
  total: number;
}

interface SystemStats {
  total_users: number;
  active_users: number;
  total_credits_issued: number;
  revenue_this_month: number;
}

interface ContactRequest {
  id: string;
  name: string;
  email: string;
  subject: string;
  message: string;
  phone?: string | null;
  business_name?: string | null;
  source: string;
  recommended_package?: string | null;
  audit_id?: string | null;
  lead_score: number;
  sales_notes?: string | null;
  close_reason?: string | null;
  contacted_at?: string | null;
  booked_at?: string | null;
  won_at?: string | null;
  lost_at?: string | null;
  closed_at?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

interface ContactRequestsResponse {
  requests: ContactRequest[];
  total: number;
}

interface ContactRequestSummary {
  total: number;
  by_status: Record<string, number>;
  booked_conversion_rate: number;
  won_conversion_rate: number;
  avg_first_response_hours: number | null;
  new_over_24h_total: number;
  sla_target_hours: number;
}

interface RecoveryAccount {
  account_id: string;
  email: string;
  company_name?: string | null;
  plan: string;
  subscription_status: string;
  access_state: string;
  dunning_status: string;
  payment_retry_count: number;
  last_payment_error?: string | null;
  next_payment_retry_at?: string | null;
  current_period_end?: string | null;
  action_plan: RecoveryActionPlan;
}

interface RecoveryDispute {
  dispute_id: string;
  account_id: string;
  user_email: string;
  amount: number;
  reason?: string | null;
  status: string;
  evidence_due_by?: string | null;
  created_at: string;
  action_plan: RecoveryActionPlan;
}

interface RecoveryRefund {
  order_id: string;
  account_id: string;
  user_email: string;
  payment_id: string;
  amount: number;
  status: string;
  created_at: string;
  processed_at?: string | null;
  action_plan: RecoveryActionPlan;
}

interface RecoveryRunbookItem {
  id: string;
  title: string;
  priority: string;
  summary: string;
  steps: string[];
  cta_label?: string | null;
  cta_href?: string | null;
}

interface RecoveryActionPlan {
  headline: string;
  operator_note: string;
  customer_message: string;
}

interface RecoveryActivityEntry {
  id: string;
  account_id?: string | null;
  account_email?: string | null;
  action: string;
  operator_action?: string | null;
  entity_type?: string | null;
  entity_id?: string | null;
  description?: string | null;
  created_at: string;
}

interface RecoveryQueueResponse {
  dunning_accounts: RecoveryAccount[];
  disputes: RecoveryDispute[];
  recent_refunds: RecoveryRefund[];
  runbook_items: RecoveryRunbookItem[];
  recent_operator_actions: RecoveryActivityEntry[];
  dunning_total: number;
  dispute_total: number;
  urgent_dispute_total: number;
  refunded_total: number;
  action_required_total: number;
}

interface DunningRecoveryLinkResponse {
  account_id: string;
  email: string;
  portal_url: string;
  portal_available: boolean;
  portal_source: string;
  portal_error?: string | null;
  action_plan: RecoveryActionPlan;
  generated_at: string;
}

interface OperationsFeedItem {
  id: string;
  domain: string;
  severity: string;
  title: string;
  summary: string;
  status: string;
  account_id?: string | null;
  account_email?: string | null;
  location_id?: string | null;
  location_name?: string | null;
  entity_type?: string | null;
  entity_id?: string | null;
  occurred_at: string;
  actionable: boolean;
  action_href?: string | null;
}

interface OperationsFeedResponse {
  items: OperationsFeedItem[];
  total: number;
  actionable_total: number;
  domain_totals: Record<string, number>;
}

interface UploadMigrationAuditItem {
  source_type: string;
  entity_id: string;
  field_name: string;
  url: string;
  recommended_action: string;
  storage_key?: string | null;
  account_id?: string | null;
  account_email?: string | null;
  location_id?: string | null;
  location_name?: string | null;
  created_at: string;
}

interface UploadMigrationAuditResponse {
  upload_asset_total: number;
  upload_asset_local_total: number;
  legacy_post_image_total: number;
  legacy_post_ai_image_total: number;
  legacy_billing_attachment_total: number;
  affected_account_total: number;
  actionable_total: number;
  cloud_storage_configured: boolean;
  sample_limit: number;
  batch_summaries: Array<{
    recommended_action: string;
    priority: string;
    reference_total: number;
    affected_account_total: number;
    affected_location_total: number;
    summary: string;
  }>;
  runbook_steps: string[];
  items: UploadMigrationAuditItem[];
}

interface UploadMigrationBatchPreviewItem {
  source_type: string;
  entity_id: string;
  field_name: string;
  original_url: string;
  destination_key?: string | null;
  status: string;
  local_path?: string | null;
  message?: string | null;
}

interface UploadMigrationCleanupPreviewItem {
  local_path: string;
  relative_path: string;
  destination_keys: string[];
  migrated_urls: string[];
  reference_count: number;
  reference_fields: string[];
  reason: string;
}

interface UploadMigrationBatchPreviewResponse {
  source_type_filter?: string | null;
  batch_offset: number;
  batch_limit: number;
  matching_total: number;
  candidate_total: number;
  planned_total: number;
  missing_local_file_total: number;
  skipped_total: number;
  error_total: number;
  has_more: boolean;
  next_offset?: number | null;
  source_totals: Record<string, number>;
  cloud_storage_configured: boolean;
  cleanup_candidate_total: number;
  apply_command: string;
  next_apply_command?: string | null;
  cleanup_candidates: UploadMigrationCleanupPreviewItem[];
  items: UploadMigrationBatchPreviewItem[];
  generated_at: string;
}

interface MonthlyCreditDistributionResponse {
  considered: number;
  processed: number;
  skipped: number;
}

const PLAN_BADGES: Record<string, string> = {
  free: 'bg-gray-100 text-gray-700',
  maps_starter: 'bg-sky-100 text-sky-700',
  calls_growth: 'bg-violet-100 text-violet-700',
  competitive_market: 'bg-amber-100 text-amber-700',
  starter: 'bg-blue-100 text-blue-700',
  pro: 'bg-violet-100 text-violet-700',
  premium: 'bg-amber-100 text-amber-700',
  agency: 'bg-emerald-100 text-emerald-700',
};

const STATUS_BADGES: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  trialing: 'bg-blue-100 text-blue-700',
  past_due: 'bg-amber-100 text-amber-700',
  canceled: 'bg-gray-100 text-gray-700',
  suspended: 'bg-red-100 text-red-700',
  warning: 'bg-amber-100 text-amber-700',
  needs_response: 'bg-red-100 text-red-700',
  warning_needs_response: 'bg-red-100 text-red-700',
  under_review: 'bg-blue-100 text-blue-700',
  warning_under_review: 'bg-blue-100 text-blue-700',
  refunded: 'bg-green-100 text-green-700',
  refund_created: 'bg-green-100 text-green-700',
  dispute_updated: 'bg-blue-100 text-blue-700',
  subscription_updated: 'bg-amber-100 text-amber-700',
  new: 'bg-sky-100 text-sky-700',
  contacted: 'bg-violet-100 text-violet-700',
  booked: 'bg-blue-100 text-blue-700',
  won: 'bg-green-100 text-green-700',
  lost: 'bg-amber-100 text-amber-700',
  closed: 'bg-green-100 text-green-700',
  spam: 'bg-red-100 text-red-700',
};

const PRIORITY_BADGES: Record<string, string> = {
  high: 'bg-red-100 text-red-700',
  normal: 'bg-blue-100 text-blue-700',
  monitor: 'bg-gray-100 text-gray-700',
};

const SEVERITY_BADGES: Record<string, string> = {
  critical: 'bg-red-100 text-red-700',
  warning: 'bg-amber-100 text-amber-700',
  info: 'bg-blue-100 text-blue-700',
};

const DOMAIN_BADGES: Record<string, string> = {
  publish: 'bg-rose-100 text-rose-700',
  oauth: 'bg-cyan-100 text-cyan-700',
  notifications: 'bg-emerald-100 text-emerald-700',
  review_booster: 'bg-violet-100 text-violet-700',
};

function formatDate(value?: string | null) {
  if (!value) {
    return 'Not recorded';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
}

function formatShortDate(value?: string | null) {
  if (!value) {
    return 'Not recorded';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString();
}

function statusBadgeClass(status: string) {
  return STATUS_BADGES[status] || 'bg-gray-100 text-gray-700';
}

function planBadgeClass(plan: string) {
  return PLAN_BADGES[plan] || 'bg-gray-100 text-gray-700';
}

function priorityBadgeClass(priority: string) {
  return PRIORITY_BADGES[priority] || 'bg-gray-100 text-gray-700';
}

function leadScoreBadgeClass(score: number) {
  if (score >= 80) {
    return 'bg-red-100 text-red-700';
  }
  if (score >= 60) {
    return 'bg-amber-100 text-amber-700';
  }
  return 'bg-blue-100 text-blue-700';
}

function formatLabel(value?: string | null) {
  if (!value) {
    return 'Not recorded';
  }

  return value.replaceAll('_', ' ');
}

function createEmptyUsageLimitValues(): UsageLimitFormValues {
  return Object.fromEntries(
    USAGE_LIMIT_FIELDS.map((field) => [field.key, ''])
  ) as UsageLimitFormValues;
}

function buildUsageLimitValues(user: User): UsageLimitFormValues {
  const values = createEmptyUsageLimitValues();
  const overrides = user.custom_limits?.usage_overrides || {};

  for (const field of USAGE_LIMIT_FIELDS) {
    const currentValue = overrides[field.key];
    if (typeof currentValue === 'number') {
      values[field.key] = String(currentValue);
    }
  }

  return values;
}

function effectiveUsageLimit(user: User, key: UsageLimitFieldKey): string {
  const value = user.custom_limits?.effective_usage_limits?.[key];
  return typeof value === 'number' ? value.toLocaleString() : 'Plan default';
}

function usageOverrideCount(user: User): number {
  return Object.keys(user.custom_limits?.usage_overrides || {}).length;
}

function severityBadgeClass(severity: string) {
  return SEVERITY_BADGES[severity] || 'bg-gray-100 text-gray-700';
}

function domainBadgeClass(domain: string) {
  return DOMAIN_BADGES[domain] || 'bg-gray-100 text-gray-700';
}

async function copyTextToClipboard(text: string, successMessage: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(successMessage);
  } catch {
    window.prompt('Copy the text below:', text);
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function ActionPlanPanel({
  actionPlan,
  workflowHref,
  workflowLabel = 'Open workflow',
}: {
  actionPlan: RecoveryActionPlan;
  workflowHref?: string;
  workflowLabel?: string;
}) {
  return (
    <div className="mt-3 rounded-lg border border-dashed bg-white p-3">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Suggested next action</div>
      <div className="mt-1 text-sm font-medium text-gray-900">{actionPlan.headline}</div>
      <div className="mt-2 whitespace-pre-line text-xs text-gray-600">{actionPlan.operator_note}</div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => void copyTextToClipboard(actionPlan.operator_note, 'Internal note copied.')}
        >
          <Copy className="mr-2 h-4 w-4" />
          Copy internal note
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void copyTextToClipboard(actionPlan.customer_message, 'Customer update copied.')}
        >
          <Copy className="mr-2 h-4 w-4" />
          Copy customer update
        </Button>
        {workflowHref ? (
          <Link href={workflowHref}>
            <Button variant="ghost" size="sm">
              {workflowLabel}
            </Button>
          </Link>
        ) : null}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isDistributingMonthlyCredits, setIsDistributingMonthlyCredits] = useState(false);
  const [pendingDunningAction, setPendingDunningAction] = useState<string | null>(null);
  const [pendingCreditUpdateUserId, setPendingCreditUpdateUserId] = useState<string | null>(null);
  const [pendingPlanUpdateUserId, setPendingPlanUpdateUserId] = useState<string | null>(null);
  const [pendingLimitUpdateUserId, setPendingLimitUpdateUserId] = useState<string | null>(null);
  const [pendingLifecycleUserId, setPendingLifecycleUserId] = useState<string | null>(null);
  const [pendingContactRequestId, setPendingContactRequestId] = useState<string | null>(null);
  const [isExportingUploadAudit, setIsExportingUploadAudit] = useState(false);
  const [isExportingUploadCleanupManifest, setIsExportingUploadCleanupManifest] = useState(false);
  const [isCopyingUploadApplyCommand, setIsCopyingUploadApplyCommand] = useState(false);
  const [isCopyingUploadNextCommand, setIsCopyingUploadNextCommand] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [users, setUsers] = useState<User[]>([]);
  const [userTotal, setUserTotal] = useState(0);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [contactRequests, setContactRequests] = useState<ContactRequest[]>([]);
  const [contactRequestTotal, setContactRequestTotal] = useState(0);
  const [contactSummary, setContactSummary] = useState<ContactRequestSummary | null>(null);
  const [recoveryQueue, setRecoveryQueue] = useState<RecoveryQueueResponse | null>(null);
  const [operationsFeed, setOperationsFeed] = useState<OperationsFeedResponse | null>(null);
  const [uploadMigrationAudit, setUploadMigrationAudit] = useState<UploadMigrationAuditResponse | null>(null);
  const [uploadMigrationBatchPreview, setUploadMigrationBatchPreview] =
    useState<UploadMigrationBatchPreviewResponse | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [filterPlan, setFilterPlan] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [contactStatusFilter, setContactStatusFilter] = useState('new');
  const [creditEditorUserId, setCreditEditorUserId] = useState<string | null>(null);
  const [creditAmount, setCreditAmount] = useState('');
  const [creditReason, setCreditReason] = useState('');
  const [planEditorUserId, setPlanEditorUserId] = useState<string | null>(null);
  const [planValue, setPlanValue] = useState('starter');
  const [limitEditorUserId, setLimitEditorUserId] = useState<string | null>(null);
  const [limitValues, setLimitValues] = useState<UsageLimitFormValues>(createEmptyUsageLimitValues);

  const runLoadData = async (manual: boolean = false) => {
    if (manual) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }

    const [
      statsResult,
      usersResult,
      contactRequestsResult,
      contactSummaryResult,
      recoveryResult,
      operationsResult,
      uploadAuditResult,
      uploadPreviewResult,
    ] = await Promise.allSettled([
      adminApi.getStats(),
      adminApi.getUsers({
        page: 1,
        page_size: 20,
        search: searchQuery || undefined,
        plan: filterPlan === 'all' ? undefined : filterPlan,
        status: filterStatus === 'all' ? undefined : filterStatus,
      }),
      adminApi.getContactRequests({
        status: contactStatusFilter,
        limit: 8,
        offset: 0,
      }),
      adminApi.getContactRequestSummary(),
      adminApi.getRecoveryQueue(5),
      adminApi.getOperationsFeed(12),
      adminApi.getUploadMigrationAudit(8),
      adminApi.getUploadMigrationBatchPreview({ limit: 5, offset: 0 }),
    ]);

    const errors: string[] = [];

    if (statsResult.status === 'fulfilled') {
      setStats(statsResult.value.data as SystemStats);
    } else {
      setStats(null);
      errors.push(getApiErrorMessage(statsResult.reason, 'System stats could not be loaded.'));
    }

    if (usersResult.status === 'fulfilled') {
      const data = usersResult.value.data as UsersResponse;
      setUsers(data.users || []);
      setUserTotal(data.total || 0);
    } else {
      setUsers([]);
      setUserTotal(0);
      errors.push(getApiErrorMessage(usersResult.reason, 'Admin users could not be loaded.'));
    }

    if (contactRequestsResult.status === 'fulfilled') {
      const data = contactRequestsResult.value.data as ContactRequestsResponse;
      setContactRequests(data.requests || []);
      setContactRequestTotal(data.total || 0);
    } else {
      setContactRequests([]);
      setContactRequestTotal(0);
      errors.push(getApiErrorMessage(contactRequestsResult.reason, 'Contact requests could not be loaded.'));
    }

    if (contactSummaryResult.status === 'fulfilled') {
      setContactSummary(contactSummaryResult.value.data as ContactRequestSummary);
    } else {
      setContactSummary(null);
      errors.push(getApiErrorMessage(contactSummaryResult.reason, 'Contact summary could not be loaded.'));
    }

    if (recoveryResult.status === 'fulfilled') {
      setRecoveryQueue(recoveryResult.value.data as RecoveryQueueResponse);
    } else {
      setRecoveryQueue(null);
      errors.push(getApiErrorMessage(recoveryResult.reason, 'Recovery queue could not be loaded.'));
    }

    if (operationsResult.status === 'fulfilled') {
      setOperationsFeed(operationsResult.value.data as OperationsFeedResponse);
    } else {
      setOperationsFeed(null);
      errors.push(getApiErrorMessage(operationsResult.reason, 'Operations feed could not be loaded.'));
    }

    if (uploadAuditResult.status === 'fulfilled') {
      setUploadMigrationAudit(uploadAuditResult.value.data as UploadMigrationAuditResponse);
    } else {
      setUploadMigrationAudit(null);
      errors.push(getApiErrorMessage(uploadAuditResult.reason, 'Upload migration audit could not be loaded.'));
    }

    if (uploadPreviewResult.status === 'fulfilled') {
      setUploadMigrationBatchPreview(uploadPreviewResult.value.data as UploadMigrationBatchPreviewResponse);
    } else {
      setUploadMigrationBatchPreview(null);
      errors.push(getApiErrorMessage(uploadPreviewResult.reason, 'Upload migration batch preview could not be loaded.'));
    }

    setLoadError(errors.length > 0 ? errors.join(' ') : null);

    if (manual) {
      setIsRefreshing(false);
    } else {
      setIsLoading(false);
    }
  };

  const loadOnMount = useEffectEvent(async () => {
    await runLoadData(false);
  });

  const handleDunningRecoveryAction = async (item: RecoveryAccount, mode: 'open' | 'copy') => {
    setPendingDunningAction(`${item.account_id}:${mode}`);
    try {
      const response = await adminApi.createDunningRecoveryLink(item.account_id);
      const payload = response.data as DunningRecoveryLinkResponse;

      if (mode === 'copy') {
        await copyTextToClipboard(
          payload.action_plan.customer_message,
          'Live customer recovery update copied.'
        );
      } else if (payload.portal_url) {
        window.open(payload.portal_url, '_blank', 'noopener,noreferrer');
        toast.success(
          payload.portal_available
            ? 'Billing recovery link opened.'
            : 'Fallback billing recovery page opened.'
        );
      }

      await runLoadData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Billing recovery link could not be prepared.'));
    } finally {
      setPendingDunningAction(null);
    }
  };

  const handleExportUploadAudit = async () => {
    setIsExportingUploadAudit(true);
    try {
      const response = await adminApi.exportUploadMigrationAudit();
      downloadBlob(response.data as Blob, 'upload-migration-audit.csv');
      toast.success('Upload migration audit exported.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Upload migration export could not be generated.'));
    } finally {
      setIsExportingUploadAudit(false);
    }
  };

  const handleCopyUploadApplyCommand = async (mode: 'current' | 'next') => {
    const command =
      mode === 'next'
        ? uploadMigrationBatchPreview?.next_apply_command
        : uploadMigrationBatchPreview?.apply_command;
    if (!command) {
      return;
    }

    if (mode === 'current') {
      setIsCopyingUploadApplyCommand(true);
    } else {
      setIsCopyingUploadNextCommand(true);
    }

    try {
      await copyTextToClipboard(
        command,
        mode === 'current'
          ? 'Current apply command copied.'
          : 'Next batch apply command copied.'
      );
    } finally {
      if (mode === 'current') {
        setIsCopyingUploadApplyCommand(false);
      } else {
        setIsCopyingUploadNextCommand(false);
      }
    }
  };

  const handleExportUploadCleanupManifest = async () => {
    if (!uploadMigrationBatchPreview) {
      return;
    }

    setIsExportingUploadCleanupManifest(true);
    try {
      const payload = {
        generated_at: uploadMigrationBatchPreview.generated_at,
        source_type_filter: uploadMigrationBatchPreview.source_type_filter ?? null,
        batch_offset: uploadMigrationBatchPreview.batch_offset,
        batch_limit: uploadMigrationBatchPreview.batch_limit,
        matching_total: uploadMigrationBatchPreview.matching_total,
        candidate_total: uploadMigrationBatchPreview.candidate_total,
        planned_total: uploadMigrationBatchPreview.planned_total,
        cleanup_candidate_total: uploadMigrationBatchPreview.cleanup_candidate_total,
        has_more: uploadMigrationBatchPreview.has_more,
        next_offset: uploadMigrationBatchPreview.next_offset ?? null,
        source_totals: uploadMigrationBatchPreview.source_totals,
        apply_command: uploadMigrationBatchPreview.apply_command,
        next_apply_command: uploadMigrationBatchPreview.next_apply_command ?? null,
        cleanup_candidates: uploadMigrationBatchPreview.cleanup_candidates,
      };
      downloadBlob(
        new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }),
        `upload-migration-cleanup-preview-offset-${uploadMigrationBatchPreview.batch_offset}.json`
      );
      toast.success('Cleanup preview manifest exported.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Cleanup preview manifest could not be exported.'));
    } finally {
      setIsExportingUploadCleanupManifest(false);
    }
  };

  const handleOpenCreditEditor = (user: User) => {
    setCreditEditorUserId(user.id);
    setCreditAmount('');
    setCreditReason('');
  };

  const handleOpenPlanEditor = (user: User) => {
    setPlanEditorUserId(user.id);
    setPlanValue(user.plan || 'starter');
  };

  const handleOpenLimitEditor = (user: User) => {
    setLimitEditorUserId(user.id);
    setLimitValues(buildUsageLimitValues(user));
  };

  const handleCloseCreditEditor = () => {
    if (pendingCreditUpdateUserId) {
      return;
    }

    setCreditEditorUserId(null);
    setCreditAmount('');
    setCreditReason('');
  };

  const handleClosePlanEditor = () => {
    if (pendingPlanUpdateUserId) {
      return;
    }

    setPlanEditorUserId(null);
    setPlanValue('starter');
  };

  const handleCloseLimitEditor = () => {
    if (pendingLimitUpdateUserId) {
      return;
    }

    setLimitEditorUserId(null);
    setLimitValues(createEmptyUsageLimitValues());
  };

  const handleLimitValueChange = (key: UsageLimitFieldKey, value: string) => {
    setLimitValues((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const handleSubmitCreditUpdate = async (user: User) => {
    const parsedCredits = Number.parseInt(creditAmount, 10);
    const trimmedReason = creditReason.trim();

    if (!Number.isFinite(parsedCredits) || parsedCredits <= 0) {
      toast.error('Enter a positive credit amount.');
      return;
    }

    if (!trimmedReason) {
      toast.error('Enter an operator reason before granting credits.');
      return;
    }

    setPendingCreditUpdateUserId(user.id);
    try {
      await adminApi.updateUserCredits(user.id, parsedCredits, trimmedReason);
      toast.success('Bonus credits added.');
      setCreditEditorUserId(null);
      setCreditAmount('');
      setCreditReason('');
      await runLoadData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Credits could not be updated.'));
    } finally {
      setPendingCreditUpdateUserId(null);
    }
  };

  const handleSubmitPlanUpdate = async (user: User) => {
    setPendingPlanUpdateUserId(user.id);
    try {
      await adminApi.updateUserPlan(user.id, planValue);
      toast.success('Plan updated.');
      setPlanEditorUserId(null);
      await runLoadData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Plan could not be updated.'));
    } finally {
      setPendingPlanUpdateUserId(null);
    }
  };

  const handleSubmitLimitUpdate = async (user: User) => {
    const payload: Partial<Record<UsageLimitFieldKey, number | null>> = {};

    for (const field of USAGE_LIMIT_FIELDS) {
      const rawValue = limitValues[field.key].trim();
      if (!rawValue) {
        payload[field.key] = null;
        continue;
      }

      const parsed = Number.parseInt(rawValue, 10);
      if (!Number.isFinite(parsed) || parsed < 0) {
        toast.error(`${field.label} must be a non-negative integer.`);
        return;
      }
      payload[field.key] = parsed;
    }

    setPendingLimitUpdateUserId(user.id);
    try {
      await adminApi.updateUserLimits(user.id, payload);
      toast.success('Usage limit overrides updated.');
      setLimitEditorUserId(null);
      setLimitValues(createEmptyUsageLimitValues());
      await runLoadData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Usage limit overrides could not be updated.'));
    } finally {
      setPendingLimitUpdateUserId(null);
    }
  };

  const handleDistributeMonthlyCredits = async () => {
    setIsDistributingMonthlyCredits(true);
    try {
      const response = await adminApi.distributeMonthlyCredits();
      const payload = response.data as MonthlyCreditDistributionResponse;
      toast.success(
        `Monthly credits distributed for ${payload.processed} account(s). ${payload.skipped} skipped.`
      );
      await runLoadData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Monthly credit distribution could not be completed.'));
    } finally {
      setIsDistributingMonthlyCredits(false);
    }
  };

  const handleSuspendUser = async (user: User) => {
    setPendingLifecycleUserId(user.id);
    try {
      await adminApi.suspendUser(user.id);
      toast.success('Account suspended.');
      await runLoadData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Account could not be suspended.'));
    } finally {
      setPendingLifecycleUserId(null);
    }
  };

  const handleActivateUser = async (user: User) => {
    setPendingLifecycleUserId(user.id);
    try {
      await adminApi.activateUser(user.id);
      toast.success('Account reactivated.');
      await runLoadData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Account could not be reactivated.'));
    } finally {
      setPendingLifecycleUserId(null);
    }
  };

  const handleUpdateContactRequestStatus = async (requestId: string, nextStatus: string) => {
    setPendingContactRequestId(requestId);
    try {
      await adminApi.updateContactRequestStatus(requestId, nextStatus);
      toast.success('Contact request updated.');
      await runLoadData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Contact request could not be updated.'));
    } finally {
      setPendingContactRequestId(null);
    }
  };

  useEffect(() => {
    void loadOnMount();
  }, []);

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-24 w-full" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <Skeleton key={item} className="h-32 w-full" />
          ))}
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">Admin Recovery Console</h1>
          <p className="text-sm text-gray-600">
            Review the live recovery queue first, then move into refund and dispute actions.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => void handleDistributeMonthlyCredits()}
            disabled={isDistributingMonthlyCredits || isRefreshing}
          >
            {isDistributingMonthlyCredits ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Run monthly credits
          </Button>
          <Button variant="outline" onClick={() => void runLoadData(true)} disabled={isRefreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Link href="/admin/disputes">
            <Button>
              <ShieldAlert className="mr-2 h-4 w-4" />
              Open Disputes And Refunds
            </Button>
          </Link>
        </div>
      </div>

      {loadError ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {loadError}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total accounts</CardDescription>
            <CardTitle className="flex items-center gap-2 text-3xl">
              <Users className="h-6 w-6 text-blue-600" />
              {stats?.total_users ?? 0}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-gray-600">
            {stats?.active_users ?? 0} active accounts are currently using the product.
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Action required now</CardDescription>
            <CardTitle className="flex items-center gap-2 text-3xl">
              <AlertTriangle className="h-6 w-6 text-amber-600" />
              {recoveryQueue?.action_required_total ?? 0}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-gray-600">
            {(recoveryQueue?.dunning_total ?? 0) > 0 || (recoveryQueue?.urgent_dispute_total ?? 0) > 0
              ? `${recoveryQueue?.dunning_total ?? 0} dunning account(s), ${recoveryQueue?.urgent_dispute_total ?? 0} urgent dispute(s).`
              : 'No urgent billing recovery items are queued right now.'}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Monthly revenue snapshot</CardDescription>
            <CardTitle className="flex items-center gap-2 text-3xl">
              <Wallet className="h-6 w-6 text-emerald-600" />$
              {(stats?.revenue_this_month ?? 0).toLocaleString()}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-gray-600">
            Real subscription revenue only. Demo math has been removed from this screen.
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Refunded orders tracked</CardDescription>
            <CardTitle className="flex items-center gap-2 text-3xl">
              <CreditCard className="h-6 w-6 text-violet-600" />
              {recoveryQueue?.refunded_total ?? 0}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-gray-600">
            Recent refund completions stay visible here for support verification.
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5 text-sky-600" />
                Contact Requests
              </CardTitle>
              <CardDescription>
                Public audit-review and managed-pilot inquiries captured from the contact page.
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Select value={contactStatusFilter} onValueChange={setContactStatusFilter}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="new">New</SelectItem>
                  <SelectItem value="contacted">Contacted</SelectItem>
                  <SelectItem value="booked">Booked</SelectItem>
                  <SelectItem value="won">Won</SelectItem>
                  <SelectItem value="lost">Lost</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                  <SelectItem value="spam">Spam</SelectItem>
                  <SelectItem value="all">All</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" onClick={() => void runLoadData(true)} disabled={isRefreshing}>
                <RefreshCw className={`mr-2 h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                Load
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-sm text-gray-600">
            <Badge variant="outline">{contactRequestTotal} matching request(s)</Badge>
            <Badge className={statusBadgeClass(contactStatusFilter)}>{formatLabel(contactStatusFilter)}</Badge>
          </div>

          {contactSummary ? (
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-lg border bg-white p-3">
                <div className="text-xs uppercase tracking-wide text-gray-500">Booked rate</div>
                <div className="mt-1 text-2xl font-semibold">{contactSummary.booked_conversion_rate}%</div>
                <div className="text-xs text-gray-500">
                  {(contactSummary.by_status.booked || 0) + (contactSummary.by_status.won || 0)} booked or won
                </div>
              </div>
              <div className="rounded-lg border bg-white p-3">
                <div className="text-xs uppercase tracking-wide text-gray-500">Won rate</div>
                <div className="mt-1 text-2xl font-semibold">{contactSummary.won_conversion_rate}%</div>
                <div className="text-xs text-gray-500">{contactSummary.by_status.won || 0} won lead(s)</div>
              </div>
              <div className="rounded-lg border bg-white p-3">
                <div className="text-xs uppercase tracking-wide text-gray-500">Avg first response</div>
                <div className="mt-1 text-2xl font-semibold">
                  {contactSummary.avg_first_response_hours === null ? '-' : `${contactSummary.avg_first_response_hours}h`}
                </div>
                <div className="text-xs text-gray-500">SLA target {contactSummary.sla_target_hours}h</div>
              </div>
              <div className="rounded-lg border bg-white p-3">
                <div className="text-xs uppercase tracking-wide text-gray-500">SLA risk</div>
                <div className="mt-1 text-2xl font-semibold">{contactSummary.new_over_24h_total}</div>
                <div className="text-xs text-gray-500">new lead(s) older than 24h</div>
              </div>
            </div>
          ) : null}

          {contactRequests.length ? (
            <div className="space-y-3">
              {contactRequests.map((request) => (
                <div key={request.id} className="rounded-lg border bg-gray-50 p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <MessageSquare className="h-4 w-4 text-gray-500" />
                        <span className="font-medium">{request.subject}</span>
                        <Badge className={statusBadgeClass(request.status)}>{request.status}</Badge>
                        <Badge variant="outline">{request.source}</Badge>
                        <Badge className={leadScoreBadgeClass(request.lead_score)}>Score {request.lead_score}</Badge>
                        {request.recommended_package ? (
                          <Badge variant="outline">{formatLabel(request.recommended_package)}</Badge>
                        ) : null}
                      </div>
                      <div className="text-sm text-gray-600">
                        {request.name} | {request.email}
                        {request.phone ? ` | ${request.phone}` : ''}
                      </div>
                      <div className="text-sm text-gray-600">
                        Business: {request.business_name || 'Not provided'}
                      </div>
                      <div className="text-sm text-gray-600">
                        Audit: {request.audit_id || 'Not linked'}
                      </div>
                      <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                        <span>Contacted {formatDate(request.contacted_at)}</span>
                        <span>Booked {formatDate(request.booked_at)}</span>
                        <span>Won {formatDate(request.won_at)}</span>
                        <span>Lost {formatDate(request.lost_at)}</span>
                        <span>Closed {formatDate(request.closed_at)}</span>
                      </div>
                    </div>
                    <div className="text-xs text-gray-500">Received {formatDate(request.created_at)}</div>
                  </div>

                  <p className="mt-3 whitespace-pre-wrap rounded-md border bg-white p-3 text-sm leading-6 text-gray-700">
                    {request.message}
                  </p>
                  {request.sales_notes ? (
                    <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                      {request.sales_notes}
                    </div>
                  ) : null}
                  {request.close_reason ? (
                    <div className="mt-2 rounded-md border border-gray-200 bg-white p-3 text-sm text-gray-700">
                      Close reason: {request.close_reason}
                    </div>
                  ) : null}

                  <div className="mt-3 flex flex-wrap gap-2">
                    <a href={`mailto:${request.email}?subject=${encodeURIComponent(`Re: ${request.subject}`)}`}>
                      <Button size="sm" variant="outline">
                        <Mail className="mr-2 h-4 w-4" />
                        Email
                      </Button>
                    </a>
                    {request.status !== 'contacted' ? (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={pendingContactRequestId === request.id}
                        onClick={() => void handleUpdateContactRequestStatus(request.id, 'contacted')}
                      >
                        {pendingContactRequestId === request.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                        Mark contacted
                      </Button>
                    ) : null}
                    {request.status !== 'booked' ? (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={pendingContactRequestId === request.id}
                        onClick={() => void handleUpdateContactRequestStatus(request.id, 'booked')}
                      >
                        Booked
                      </Button>
                    ) : null}
                    {request.status !== 'won' ? (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={pendingContactRequestId === request.id}
                        onClick={() => void handleUpdateContactRequestStatus(request.id, 'won')}
                      >
                        Won
                      </Button>
                    ) : null}
                    {request.status !== 'lost' ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={pendingContactRequestId === request.id}
                        onClick={() => void handleUpdateContactRequestStatus(request.id, 'lost')}
                      >
                        Lost
                      </Button>
                    ) : null}
                    {request.status !== 'closed' ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={pendingContactRequestId === request.id}
                        onClick={() => void handleUpdateContactRequestStatus(request.id, 'closed')}
                      >
                        Close
                      </Button>
                    ) : null}
                    {request.status !== 'spam' ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={pendingContactRequestId === request.id}
                        onClick={() => void handleUpdateContactRequestStatus(request.id, 'spam')}
                      >
                        Mark spam
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
              No contact requests match this filter.
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Recovery Queue</CardTitle>
            <CardDescription>
              The highest-signal accounts and disputes that currently need operator attention.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Accounts in dunning</h3>
                <Badge variant="outline">{recoveryQueue?.dunning_total ?? 0}</Badge>
              </div>
              {recoveryQueue?.dunning_accounts?.length ? (
                recoveryQueue.dunning_accounts.map((item) => (
                  <div key={item.account_id} className="rounded-lg border bg-gray-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <div className="font-medium">{item.company_name || item.email}</div>
                        <div className="text-sm text-gray-500">{item.email}</div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge className={planBadgeClass(item.plan)}>{item.plan}</Badge>
                        <Badge className={statusBadgeClass(item.access_state)}>{item.access_state}</Badge>
                      </div>
                    </div>
                    <div className="mt-3 space-y-1 text-sm text-gray-600">
                      <div>Dunning state: {item.dunning_status}</div>
                      <div>Retry count: {item.payment_retry_count}</div>
                      <div>Current period end: {formatShortDate(item.current_period_end)}</div>
                      <div>Next retry: {formatDate(item.next_payment_retry_at)}</div>
                      <div>
                        Last error: {item.last_payment_error || 'No payment error message recorded yet.'}
                      </div>
                    </div>
                    <ActionPlanPanel actionPlan={item.action_plan} />
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={pendingDunningAction === `${item.account_id}:open`}
                        onClick={() => void handleDunningRecoveryAction(item, 'open')}
                      >
                        {pendingDunningAction === `${item.account_id}:open` ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <CreditCard className="mr-2 h-4 w-4" />
                        )}
                        Open billing recovery link
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={pendingDunningAction === `${item.account_id}:copy`}
                        onClick={() => void handleDunningRecoveryAction(item, 'copy')}
                      >
                        {pendingDunningAction === `${item.account_id}:copy` ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Copy className="mr-2 h-4 w-4" />
                        )}
                        Copy live customer update
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
                  No accounts are currently in warning or suspended billing states.
                </div>
              )}
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Actionable disputes</h3>
                <Badge variant="outline">{recoveryQueue?.dispute_total ?? 0}</Badge>
              </div>
              {recoveryQueue?.disputes?.length ? (
                recoveryQueue.disputes.map((item) => (
                  <div key={item.dispute_id} className="rounded-lg border bg-gray-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="font-medium">{item.user_email}</div>
                      <Badge className={statusBadgeClass(item.status)}>{formatLabel(item.status)}</Badge>
                    </div>
                    <div className="mt-3 space-y-1 text-sm text-gray-600">
                      <div>Amount: ${item.amount.toFixed(2)}</div>
                      <div>Reason: {item.reason || 'No dispute reason recorded.'}</div>
                      <div>Evidence due: {formatDate(item.evidence_due_by)}</div>
                      <div>Opened: {formatDate(item.created_at)}</div>
                    </div>
                    <ActionPlanPanel
                      actionPlan={item.action_plan}
                      workflowHref="/admin/disputes"
                      workflowLabel="Open dispute workflow"
                    />
                  </div>
                ))
              ) : (
                <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
                  No persisted disputes are waiting for operator action right now.
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent refunds</CardTitle>
            <CardDescription>
              Keep recent refund completions visible while support closes the customer loop.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {recoveryQueue?.recent_refunds?.length ? (
              recoveryQueue.recent_refunds.map((item) => (
                <div key={item.order_id} className="rounded-lg border bg-gray-50 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-medium">{item.user_email}</div>
                    <Badge className={statusBadgeClass(item.status)}>{item.status}</Badge>
                  </div>
                  <div className="mt-3 space-y-1 text-sm text-gray-600">
                    <div>Amount: ${item.amount.toFixed(2)}</div>
                    <div>Payment ref: {item.payment_id || 'Not recorded'}</div>
                    <div>Refunded at: {formatDate(item.processed_at)}</div>
                  </div>
                  <ActionPlanPanel
                    actionPlan={item.action_plan}
                    workflowHref="/admin/disputes"
                    workflowLabel="Open refund workflow"
                  />
                </div>
              ))
            ) : (
              <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
                Refunded orders will appear here after support or Stripe completes the refund flow.
              </div>
            )}
            <Link href="/admin/disputes">
              <Button variant="outline" className="w-full">
                Open Detailed Refund Workflow
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Operator Runbook</CardTitle>
            <CardDescription>
              Keep the recovery loop consistent so billing, support, and product state stay aligned.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {recoveryQueue?.runbook_items?.length ? (
              recoveryQueue.runbook_items.map((item) => (
                <div key={item.id} className="rounded-lg border bg-gray-50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="font-medium">{item.title}</div>
                      <div className="text-sm text-gray-600">{item.summary}</div>
                    </div>
                    <Badge className={priorityBadgeClass(item.priority)}>{item.priority}</Badge>
                  </div>
                  <div className="mt-3 space-y-2 text-sm text-gray-600">
                    {item.steps.map((step, index) => (
                      <div key={`${item.id}-${index}`}>
                        {index + 1}. {step}
                      </div>
                    ))}
                  </div>
                  {item.cta_href && item.cta_label ? (
                    <Link href={item.cta_href} className="mt-4 inline-block">
                      <Button variant="outline" size="sm">
                        {item.cta_label}
                      </Button>
                    </Link>
                  ) : null}
                </div>
              ))
            ) : (
              <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
                No operator runbook items are available yet.
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Operator Actions</CardTitle>
            <CardDescription>
              The latest manual recovery steps are persisted so the next operator can pick up safely.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {recoveryQueue?.recent_operator_actions?.length ? (
              recoveryQueue.recent_operator_actions.map((item) => (
                <div key={item.id} className="rounded-lg border bg-gray-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-medium">{formatLabel(item.operator_action)}</div>
                    <Badge className={statusBadgeClass(item.action)}>{formatLabel(item.action)}</Badge>
                  </div>
                  <div className="mt-3 space-y-1 text-sm text-gray-600">
                    <div>Account: {item.account_email || 'Not linked to an account'}</div>
                    <div>
                      Entity: {item.entity_type || 'Not recorded'} / {item.entity_id || 'Not recorded'}
                    </div>
                    <div>Description: {item.description || 'No description recorded.'}</div>
                    <div>Logged at: {formatDate(item.created_at)}</div>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
                Manual dunning, refund, and dispute actions will appear here after operators take recovery steps.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Cross-domain Operations Feed</CardTitle>
          <CardDescription>
            Recent publish, OAuth, notification, and review booster events that matter for day-to-day operations.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-sm text-gray-600">
            <Badge variant="outline">
              {operationsFeed?.actionable_total ?? 0} actionable event(s)
            </Badge>
            {operationsFeed?.domain_totals
              ? Object.entries(operationsFeed.domain_totals).map(([domain, count]) => (
                  <Badge key={domain} className={domainBadgeClass(domain)}>
                    {formatLabel(domain)} {count}
                  </Badge>
                ))
              : null}
          </div>

          {operationsFeed?.items?.length ? (
            <div className="space-y-3">
              {operationsFeed.items.map((item) => (
                <div key={item.id} className="rounded-lg border bg-gray-50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Activity className="h-4 w-4 text-gray-500" />
                        <span className="font-medium">{item.title}</span>
                        <Badge className={severityBadgeClass(item.severity)}>{item.severity}</Badge>
                        <Badge className={domainBadgeClass(item.domain)}>{formatLabel(item.domain)}</Badge>
                      </div>
                      <div className="text-sm text-gray-600">{item.summary}</div>
                    </div>
                    {item.action_href ? (
                      <Link href={item.action_href}>
                        <Button variant="outline" size="sm">
                          Open workflow
                        </Button>
                      </Link>
                    ) : null}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-500">
                    <div>Status: {formatLabel(item.status)}</div>
                    <div>Account: {item.account_email || 'Not recorded'}</div>
                    <div>Location: {item.location_name || 'Not recorded'}</div>
                    <div>Occurred: {formatDate(item.occurred_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
              No cross-domain operational events are recorded yet.
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-1">
              <CardTitle>Upload Migration Audit</CardTitle>
              <CardDescription>
                Remaining legacy local upload references that still need migration into persisted cloud-backed storage.
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => void handleExportUploadAudit()} disabled={isExportingUploadAudit}>
              {isExportingUploadAudit ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-sm text-gray-600">
            <Badge variant="outline">
              {uploadMigrationAudit?.actionable_total ?? 0} actionable reference(s)
            </Badge>
            <Badge variant="outline">
              {uploadMigrationAudit?.affected_account_total ?? 0} affected account(s)
            </Badge>
            <Badge className={uploadMigrationAudit?.cloud_storage_configured ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>
              {uploadMigrationAudit?.cloud_storage_configured ? 'Cloud storage configured' : 'Cloud storage not configured'}
            </Badge>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-lg border bg-gray-50 p-4">
              <div className="text-xs uppercase tracking-wide text-gray-500">Upload assets</div>
              <div className="mt-2 text-2xl font-semibold">{uploadMigrationAudit?.upload_asset_local_total ?? 0}</div>
              <div className="mt-1 text-xs text-gray-500">
                {uploadMigrationAudit?.upload_asset_total ?? 0} persisted asset(s) scanned
              </div>
            </div>
            <div className="rounded-lg border bg-gray-50 p-4">
              <div className="text-xs uppercase tracking-wide text-gray-500">Post image_url</div>
              <div className="mt-2 text-2xl font-semibold">{uploadMigrationAudit?.legacy_post_image_total ?? 0}</div>
              <div className="mt-1 text-xs text-gray-500">Legacy manual image references still local.</div>
            </div>
            <div className="rounded-lg border bg-gray-50 p-4">
              <div className="text-xs uppercase tracking-wide text-gray-500">Post ai_image_url</div>
              <div className="mt-2 text-2xl font-semibold">{uploadMigrationAudit?.legacy_post_ai_image_total ?? 0}</div>
              <div className="mt-1 text-xs text-gray-500">Generated image URLs still pointing at local uploads.</div>
            </div>
            <div className="rounded-lg border bg-gray-50 p-4">
              <div className="text-xs uppercase tracking-wide text-gray-500">Billing attachments</div>
              <div className="mt-2 text-2xl font-semibold">{uploadMigrationAudit?.legacy_billing_attachment_total ?? 0}</div>
              <div className="mt-1 text-xs text-gray-500">Dispute or refund attachment references still local.</div>
            </div>
          </div>

          {uploadMigrationBatchPreview ? (
            <div className="rounded-lg border bg-white p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-1">
                  <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Batch preview</div>
                  <div className="text-sm text-gray-600">
                    Dry-run preview for the next safe apply batch. Copy the command instead of guessing the next offset by hand.
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleCopyUploadApplyCommand('current')}
                    disabled={isCopyingUploadApplyCommand}
                  >
                    {isCopyingUploadApplyCommand ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Copy className="mr-2 h-4 w-4" />}
                    Copy apply command
                  </Button>
                  {uploadMigrationBatchPreview.next_apply_command ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleCopyUploadApplyCommand('next')}
                      disabled={isCopyingUploadNextCommand}
                    >
                      {isCopyingUploadNextCommand ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Copy className="mr-2 h-4 w-4" />}
                      Copy next batch
                    </Button>
                  ) : null}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleExportUploadCleanupManifest()}
                    disabled={isExportingUploadCleanupManifest || uploadMigrationBatchPreview.cleanup_candidate_total === 0}
                  >
                    {isExportingUploadCleanupManifest ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                    Export cleanup preview
                  </Button>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-gray-600">
                <Badge variant="outline">{uploadMigrationBatchPreview.planned_total} planned item(s)</Badge>
                <Badge variant="outline">{uploadMigrationBatchPreview.matching_total} total match(es)</Badge>
                <Badge variant="outline">{uploadMigrationBatchPreview.cleanup_candidate_total} cleanup candidate(s)</Badge>
                <Badge variant="outline">Offset {uploadMigrationBatchPreview.batch_offset}</Badge>
                <Badge variant="outline">Limit {uploadMigrationBatchPreview.batch_limit}</Badge>
                <Badge className={uploadMigrationBatchPreview.cloud_storage_configured ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>
                  {uploadMigrationBatchPreview.cloud_storage_configured ? 'Ready to apply' : 'Cloud storage not configured'}
                </Badge>
                {uploadMigrationBatchPreview.next_offset !== undefined && uploadMigrationBatchPreview.next_offset !== null ? (
                  <Badge variant="outline">Next offset {uploadMigrationBatchPreview.next_offset}</Badge>
                ) : null}
              </div>

              {Object.keys(uploadMigrationBatchPreview.source_totals || {}).length ? (
                <div className="mt-3 flex flex-wrap gap-2 text-sm text-gray-600">
                  {Object.entries(uploadMigrationBatchPreview.source_totals).map(([sourceType, count]) => (
                    <Badge key={sourceType} variant="outline">
                      {formatLabel(sourceType)} {count}
                    </Badge>
                  ))}
                </div>
              ) : null}

              <div className="mt-4 rounded-lg border bg-gray-50 p-3 text-xs text-gray-600">
                <div className="font-medium text-gray-700">Current batch command</div>
                <div className="mt-2 break-all font-mono">{uploadMigrationBatchPreview.apply_command}</div>
              </div>

              <div className="mt-4 rounded-lg border bg-amber-50 p-4">
                <div className="text-xs font-medium uppercase tracking-wide text-amber-700">Cleanup preview</div>
                <div className="mt-1 text-sm text-amber-900">
                  These local files would become cleanup candidates after this batch applies. Review them first, then rerun the audit before deleting anything.
                </div>
                {uploadMigrationBatchPreview.cleanup_candidates.length ? (
                  <div className="mt-4 space-y-3">
                    {uploadMigrationBatchPreview.cleanup_candidates.map((item) => (
                      <div key={`${item.local_path}:${item.relative_path}`} className="rounded-lg border border-amber-200 bg-white p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-gray-900">{item.relative_path}</span>
                          <Badge variant="outline">{item.reference_count} ref(s)</Badge>
                        </div>
                        <div className="mt-2 break-all text-xs text-gray-600">Local path: {item.local_path}</div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-600">
                          {item.destination_keys.map((destinationKey) => (
                            <Badge key={destinationKey} variant="outline">
                              {destinationKey}
                            </Badge>
                          ))}
                        </div>
                        <div className="mt-2 text-xs text-gray-500">{item.reason}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 rounded-lg border border-dashed border-amber-200 bg-white p-4 text-sm text-gray-600">
                    This batch would not leave any local file ready for cleanup yet. That usually means another persisted reference still points at the same upload path.
                  </div>
                )}
              </div>

              {uploadMigrationBatchPreview.items.length ? (
                <div className="mt-4 space-y-3">
                  {uploadMigrationBatchPreview.items.map((item) => (
                    <div key={`${item.source_type}:${item.entity_id}:${item.field_name}:${item.original_url}`} className="rounded-lg border bg-gray-50 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <ImageIcon className="h-4 w-4 text-gray-500" />
                            <span className="font-medium">{item.original_url}</span>
                            <Badge variant="outline">{item.source_type}</Badge>
                            <Badge variant="outline">{item.field_name}</Badge>
                            <Badge className="bg-blue-100 text-blue-700">{item.status}</Badge>
                          </div>
                          <div className="text-xs text-gray-500">
                            Destination key: {item.destination_key || 'Not recorded'}
                          </div>
                          <div className="text-xs text-gray-500">
                            Local path: {item.local_path || item.message || 'Not recorded'}
                          </div>
                        </div>
                        <div className="text-xs text-gray-500">Entity {item.entity_id}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-4 rounded-lg border border-dashed p-4 text-sm text-gray-500">
                  The current batch preview is empty. Try exporting the audit manifest and reviewing the next offset.
                </div>
              )}
            </div>
          ) : null}

          {uploadMigrationAudit?.batch_summaries?.length ? (
            <div className="grid gap-3 xl:grid-cols-2">
              {uploadMigrationAudit.batch_summaries.map((batch) => (
                <div key={batch.recommended_action} className="rounded-lg border bg-gray-50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="font-medium">{formatLabel(batch.recommended_action)}</div>
                      <div className="text-sm text-gray-600">{batch.summary}</div>
                    </div>
                    <Badge className={priorityBadgeClass(batch.priority)}>{batch.priority}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-500">
                    <div>{batch.reference_total} reference(s)</div>
                    <div>{batch.affected_account_total} account(s)</div>
                    <div>{batch.affected_location_total} location(s)</div>
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {uploadMigrationAudit?.runbook_steps?.length ? (
            <div className="rounded-lg border bg-white p-4">
              <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Suggested batch runbook</div>
              <div className="mt-3 space-y-2 text-sm text-gray-600">
                {uploadMigrationAudit.runbook_steps.map((step, index) => (
                  <div key={`upload-runbook-${index}`}>
                    {index + 1}. {step}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {uploadMigrationAudit?.items?.length ? (
            <div className="space-y-3">
              {uploadMigrationAudit.items.map((item) => (
                <div key={`${item.source_type}:${item.entity_id}:${item.field_name}:${item.url}`} className="rounded-lg border bg-gray-50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <ImageIcon className="h-4 w-4 text-gray-500" />
                        <span className="font-medium">{item.url}</span>
                        <Badge variant="outline">{item.source_type}</Badge>
                        <Badge variant="outline">{item.field_name}</Badge>
                        <Badge className="bg-blue-100 text-blue-700">{formatLabel(item.recommended_action)}</Badge>
                      </div>
                      <div className="text-sm text-gray-600">
                        Account: {item.account_email || 'Not recorded'} | Location: {item.location_name || 'Not recorded'}
                      </div>
                    </div>
                    <div className="text-xs text-gray-500">Seen {formatDate(item.created_at)}</div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-500">
                    <div>Entity: {item.entity_id}</div>
                    <div>Storage key: {item.storage_key || 'Not recorded'}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
              No legacy local upload references are currently visible in persisted upload assets, posts, or billing attachment logs.
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Live Account List</CardTitle>
          <CardDescription>
            This view now uses the real account database. Filters are server-backed.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <Input
              placeholder="Search email or company"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
            <Select value={filterPlan} onValueChange={setFilterPlan}>
              <SelectTrigger>
                <SelectValue placeholder="Filter plan" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All plans</SelectItem>
                <SelectItem value="free">Free</SelectItem>
                <SelectItem value="starter">Starter</SelectItem>
                <SelectItem value="pro">Pro</SelectItem>
                <SelectItem value="premium">Premium</SelectItem>
                <SelectItem value="agency">Agency</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger>
                <SelectValue placeholder="Filter status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="trialing">Trialing</SelectItem>
                <SelectItem value="past_due">Past due</SelectItem>
                <SelectItem value="canceled">Canceled</SelectItem>
                <SelectItem value="suspended">Suspended</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => void runLoadData(true)} disabled={isRefreshing}>
              {isRefreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Apply filters
            </Button>
          </div>

          <div className="rounded-lg border">
            <div className="border-b bg-gray-50 px-4 py-3 text-sm text-gray-600">
              Showing {users.length} of {userTotal} account(s)
            </div>
            {users.length === 0 ? (
              <div className="p-6 text-sm text-gray-500">No accounts matched the current filters.</div>
            ) : (
              <div className="divide-y">
                {users.map((user) => (
                  <div key={user.id} className="flex flex-col gap-3 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="space-y-1">
                      <div className="font-medium">{user.full_name || user.email}</div>
                      <div className="text-sm text-gray-500">{user.email}</div>
                      <div className="text-xs text-gray-500">
                        Created {formatShortDate(user.created_at)} | Last login {formatDate(user.last_login)}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge className={planBadgeClass(user.plan)}>{user.plan}</Badge>
                      <Badge className={statusBadgeClass(user.status)}>{user.status}</Badge>
                      <Badge variant="outline">{user.credits} credits</Badge>
                      {usageOverrideCount(user) > 0 ? (
                        <Badge variant="outline">{usageOverrideCount(user)} custom limit override(s)</Badge>
                      ) : null}
                      {user.status === 'suspended' ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => void handleActivateUser(user)}
                          disabled={
                            pendingLifecycleUserId === user.id ||
                            (pendingLifecycleUserId !== null && pendingLifecycleUserId !== user.id) ||
                            pendingCreditUpdateUserId === user.id ||
                            pendingLimitUpdateUserId === user.id
                          }
                        >
                          {pendingLifecycleUserId === user.id ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : null}
                          Reactivate account
                        </Button>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => void handleSuspendUser(user)}
                          disabled={
                            pendingLifecycleUserId === user.id ||
                            (pendingLifecycleUserId !== null && pendingLifecycleUserId !== user.id) ||
                            pendingCreditUpdateUserId === user.id ||
                            pendingLimitUpdateUserId === user.id
                          }
                        >
                          {pendingLifecycleUserId === user.id ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : null}
                          Suspend account
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleOpenPlanEditor(user)}
                        disabled={
                          pendingPlanUpdateUserId === user.id ||
                          (pendingPlanUpdateUserId !== null && pendingPlanUpdateUserId !== user.id) ||
                          pendingLifecycleUserId === user.id ||
                          pendingCreditUpdateUserId === user.id ||
                          pendingLimitUpdateUserId === user.id
                        }
                      >
                        {pendingPlanUpdateUserId === user.id ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : null}
                        Change plan
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleOpenCreditEditor(user)}
                        disabled={
                          pendingCreditUpdateUserId === user.id ||
                          (pendingCreditUpdateUserId !== null && pendingCreditUpdateUserId !== user.id) ||
                          pendingLifecycleUserId === user.id ||
                          pendingPlanUpdateUserId === user.id ||
                          pendingLimitUpdateUserId === user.id
                        }
                      >
                        {pendingCreditUpdateUserId === user.id ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : null}
                        Add bonus credits
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleOpenLimitEditor(user)}
                        disabled={
                          pendingLimitUpdateUserId === user.id ||
                          (pendingLimitUpdateUserId !== null && pendingLimitUpdateUserId !== user.id) ||
                          pendingCreditUpdateUserId === user.id ||
                          pendingLifecycleUserId === user.id ||
                          pendingPlanUpdateUserId === user.id
                        }
                      >
                        {pendingLimitUpdateUserId === user.id ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : null}
                        Edit usage limits
                      </Button>
                      <Link href="/admin/disputes">
                        <Button variant="ghost" size="sm">
                          Review billing actions
                        </Button>
                      </Link>
                    </div>
                    {creditEditorUserId === user.id ? (
                      <div className="rounded-lg border bg-gray-50 p-3 lg:ml-auto lg:w-[32rem]">
                        <div className="text-sm font-medium text-gray-900">Grant admin bonus credits</div>
                        <div className="mt-1 text-xs text-gray-500">
                          This posts directly to the live admin credits endpoint. Failures are shown as-is.
                        </div>
                        <div className="mt-3 grid gap-3 md:grid-cols-[10rem_minmax(0,1fr)]">
                          <Input
                            type="number"
                            min="1"
                            step="1"
                            placeholder="Credits"
                            value={creditAmount}
                            onChange={(event) => setCreditAmount(event.target.value)}
                            disabled={pendingCreditUpdateUserId === user.id}
                          />
                          <Input
                            placeholder="Reason for audit trail"
                            value={creditReason}
                            onChange={(event) => setCreditReason(event.target.value)}
                            disabled={pendingCreditUpdateUserId === user.id}
                          />
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            onClick={() => void handleSubmitCreditUpdate(user)}
                            disabled={pendingCreditUpdateUserId === user.id}
                          >
                            {pendingCreditUpdateUserId === user.id ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : null}
                            Grant credits
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleCloseCreditEditor}
                            disabled={pendingCreditUpdateUserId === user.id}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : null}
                    {planEditorUserId === user.id ? (
                      <div className="rounded-lg border bg-gray-50 p-3 lg:ml-auto lg:w-[28rem]">
                        <div className="text-sm font-medium text-gray-900">Change subscription plan</div>
                        <div className="mt-1 text-xs text-gray-500">
                          Stripe-backed subscriptions sync through the billing service. Local-only accounts update the
                          stored subscription snapshot directly.
                        </div>
                        <div className="mt-3">
                          <Select
                            value={planValue}
                            onValueChange={setPlanValue}
                            disabled={pendingPlanUpdateUserId === user.id}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select plan" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="free">Free</SelectItem>
                              <SelectItem value="maps_starter">Maps Starter</SelectItem>
                              <SelectItem value="calls_growth">Calls Growth</SelectItem>
                              <SelectItem value="competitive_market">Competitive Market</SelectItem>
                              <SelectItem value="starter">Starter</SelectItem>
                              <SelectItem value="pro">Pro</SelectItem>
                              <SelectItem value="premium">Premium</SelectItem>
                              <SelectItem value="agency">Agency</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            onClick={() => void handleSubmitPlanUpdate(user)}
                            disabled={pendingPlanUpdateUserId === user.id}
                          >
                            {pendingPlanUpdateUserId === user.id ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : null}
                            Apply plan
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleClosePlanEditor}
                            disabled={pendingPlanUpdateUserId === user.id}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : null}
                    {limitEditorUserId === user.id ? (
                      <div className="rounded-lg border bg-gray-50 p-3 lg:ml-auto lg:w-[40rem]">
                        <div className="text-sm font-medium text-gray-900">Account-specific usage limit overrides</div>
                        <div className="mt-1 text-xs text-gray-500">
                          Leave a field blank to fall back to the plan default. Changes apply immediately to live usage
                          checks and admin detail views.
                        </div>
                        <div className="mt-3 grid gap-3 md:grid-cols-2">
                          {USAGE_LIMIT_FIELDS.map((field) => (
                            <div key={field.key} className="space-y-1">
                              <label className="text-xs font-medium uppercase tracking-wide text-gray-500">
                                {field.label}
                              </label>
                              <Input
                                type="number"
                                min="0"
                                step="1"
                                placeholder={`Default ${effectiveUsageLimit(user, field.key)}`}
                                value={limitValues[field.key]}
                                onChange={(event) => handleLimitValueChange(field.key, event.target.value)}
                                disabled={pendingLimitUpdateUserId === user.id}
                              />
                              <div className="text-[11px] text-gray-500">
                                Effective now: {effectiveUsageLimit(user, field.key)}
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            onClick={() => void handleSubmitLimitUpdate(user)}
                            disabled={pendingLimitUpdateUserId === user.id}
                          >
                            {pendingLimitUpdateUserId === user.id ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : null}
                            Apply overrides
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setLimitValues(createEmptyUsageLimitValues())}
                            disabled={pendingLimitUpdateUserId === user.id}
                          >
                            Reset form to defaults
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleCloseLimitEditor}
                            disabled={pendingLimitUpdateUserId === user.id}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
