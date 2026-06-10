'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Calendar,
  Clock,
  CreditCard,
  ExternalLink,
  FileText,
  Image as ImageIcon,
  Loader2,
  MessageSquare,
  Package,
  Phone,
  Plus,
  Zap,
} from 'lucide-react';
import { api, billingApi, creditsApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { toast } from 'sonner';

interface UsageData {
  daily_used: number;
  daily_limit: number;
  daily_remaining: number;
  monthly_used: number;
  monthly_limit: number;
  monthly_remaining: number;
  cooldown_seconds: number;
  overage_cost_cents: number;
}

interface BillingPlan {
  id: string;
  name: string;
  price_monthly: number;
  price_yearly: number;
  features: string[];
  limits: {
    locations: number;
    posts_per_month: number;
    api_calls_per_day: number;
  };
}

interface UsagePlan {
  name: string;
  price_monthly: number;
  sms_daily: number;
  sms_monthly: number;
  ai_content_daily: number;
  ai_content_monthly: number;
  ai_image_daily: number;
  ai_image_monthly: number;
  ai_response_daily: number;
  ai_response_monthly: number;
  api_calls_daily: number;
  api_calls_monthly: number;
}

interface CreditPackage {
  package_id: string;
  credits: number;
  price_cents: number;
  label: string;
}

interface BillingCreditStatus {
  plan?: string;
  credits: {
    balance: number;
    bonus_balance: number;
    total_available: number;
    monthly_allocation: number;
  };
  stats: {
    total_received: number;
    total_used: number;
    total_purchased: number;
  };
  billing?: {
    last_allocation?: string | null;
    next_allocation?: string | null;
    billing_cycle_start?: string | null;
  };
  storage_mode?: string;
  purchase_available?: boolean;
  credit_packages: CreditPackage[];
}

interface CreditOrder {
  id: string;
  package_id: string;
  credits_amount: number;
  price_cents: number;
  status: string;
  stripe_session_id: string;
  created_at: string;
  completed_at?: string | null;
  refunded_at?: string | null;
}

const PLAN_ORDER = ['free', 'maps_starter', 'calls_growth', 'competitive_market', 'starter', 'pro', 'premium', 'agency'] as const;
const USAGE_TYPE_ORDER = ['sms', 'ai_content', 'ai_image', 'ai_response', 'api_calls'] as const;

function planRank(planId: string): number {
  const index = PLAN_ORDER.indexOf(planId as (typeof PLAN_ORDER)[number]);
  return index === -1 ? Number.MAX_SAFE_INTEGER : index;
}

function sortPlans(plans: BillingPlan[]): BillingPlan[] {
  return [...plans].sort((left, right) => {
    return planRank(left.id) - planRank(right.id) || left.name.localeCompare(right.name);
  });
}

function formatPlanName(planId: string): string {
  return planId.replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatCount(value?: number | null): string {
  if (value == null) return 'Unavailable';
  if (value < 0) return 'Unlimited';
  return value.toLocaleString();
}

function formatUsd(amount: number): string {
  return `$${amount.toLocaleString('en-US')}`;
}

function formatUsdCents(amountCents: number): string {
  return `$${(amountCents / 100).toFixed(2)}`;
}

function formatDate(value?: string | null): string | null {
  if (!value) return null;
  return new Date(value).toLocaleDateString();
}

function formatCooldown(seconds: number): string {
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  if (seconds >= 60) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }
  return `${seconds}s`;
}

function getUsageProgress(used: number, limit: number): number {
  if (limit <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((used / limit) * 100));
}

function getUsageIcon(type: string) {
  switch (type) {
    case 'sms':
      return Phone;
    case 'ai_content':
      return FileText;
    case 'ai_image':
      return ImageIcon;
    case 'ai_response':
      return MessageSquare;
    case 'api_calls':
      return Zap;
    default:
      return Zap;
  }
}

function getUsageLabel(type: string) {
  switch (type) {
    case 'sms':
      return 'SMS Messages';
    case 'ai_content':
      return 'AI Content';
    case 'ai_image':
      return 'AI Images';
    case 'ai_response':
      return 'AI Responses';
    case 'api_calls':
      return 'API Calls';
    default:
      return formatPlanName(type.replace(/_/g, ' '));
  }
}

function formatAllowance(daily?: number, monthly?: number) {
  if (daily == null || monthly == null) {
    return (
      <span className="text-xs text-gray-400">
        Unavailable
      </span>
    );
  }

  return (
    <div className="space-y-1">
      <div className="font-medium">{formatCount(daily)}/day</div>
      <div className="text-xs text-gray-500">{formatCount(monthly)}/month</div>
    </div>
  );
}

export default function UsagePage() {
  const [isLoading, setIsLoading] = useState(true);
  const [plan, setPlan] = useState('free');
  const [usage, setUsage] = useState<Record<string, UsageData>>({});
  const [billingPlans, setBillingPlans] = useState<BillingPlan[]>([]);
  const [usagePlans, setUsagePlans] = useState<Record<string, UsagePlan>>({});
  const [creditStatus, setCreditStatus] = useState<BillingCreditStatus | null>(null);
  const [creditOrders, setCreditOrders] = useState<CreditOrder[]>([]);
  const [usageError, setUsageError] = useState<string | null>(null);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [creditsError, setCreditsError] = useState<string | null>(null);
  const [isPurchaseDialogOpen, setIsPurchaseDialogOpen] = useState(false);
  const [selectedPackageId, setSelectedPackageId] = useState('');
  const [isPurchasing, setIsPurchasing] = useState(false);

  useEffect(() => {
    void fetchUsageData();
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const creditsState = params.get('credits');

    if (creditsState === 'success') {
      toast.success('Credit checkout completed. Purchased credits appear after Stripe confirms payment.');
    } else if (creditsState === 'cancelled') {
      toast.message('Credit checkout was cancelled.');
    } else {
      return;
    }

    params.delete('credits');
    const nextSearch = params.toString();
    const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ''}`;
    window.history.replaceState({}, '', nextUrl);
  }, []);

  useEffect(() => {
    const packages = creditStatus?.credit_packages ?? [];
    if (packages.length === 0) {
      setSelectedPackageId('');
      return;
    }

    setSelectedPackageId((currentPackageId) => {
      const hasCurrentPackage = packages.some((item) => item.package_id === currentPackageId);
      return hasCurrentPackage ? currentPackageId : packages[0].package_id;
    });
  }, [creditStatus]);

  const fetchUsageData = async () => {
    setIsLoading(true);
    setUsageError(null);
    setPlansError(null);
    setCreditsError(null);

    const results = await Promise.allSettled([
      api.get('/usage/summary'),
      billingApi.getPlans(),
      api.get('/usage/plans'),
      billingApi.getCredits(),
      creditsApi.getOrders(undefined, 10, 0),
    ]);

    const [summaryResult, billingPlansResult, usagePlansResult, creditStatusResult, ordersResult] = results;

    if (summaryResult.status === 'fulfilled') {
      setPlan(summaryResult.value.data?.plan || 'free');
      setUsage(summaryResult.value.data?.usage || {});
    } else {
      setPlan('free');
      setUsage({});
      setUsageError(getApiErrorMessage(summaryResult.reason, 'Live usage data is unavailable right now.'));
    }

    const nextPlanErrors: string[] = [];

    if (billingPlansResult.status === 'fulfilled') {
      setBillingPlans(sortPlans(billingPlansResult.value.data || []));
    } else {
      setBillingPlans([]);
      nextPlanErrors.push(getApiErrorMessage(billingPlansResult.reason, 'Live billing plans are unavailable right now.'));
    }

    if (usagePlansResult.status === 'fulfilled') {
      setUsagePlans(usagePlansResult.value.data?.plans || {});
    } else {
      setUsagePlans({});
      nextPlanErrors.push(getApiErrorMessage(usagePlansResult.reason, 'Live usage limits are unavailable right now.'));
    }

    setPlansError(nextPlanErrors.length > 0 ? nextPlanErrors[0] : null);

    if (creditStatusResult.status === 'fulfilled') {
      setCreditStatus(creditStatusResult.value.data);
    } else {
      setCreditStatus(null);
      setCreditsError(getApiErrorMessage(creditStatusResult.reason, 'Live credit balances are unavailable right now.'));
    }

    if (ordersResult.status === 'fulfilled') {
      setCreditOrders(ordersResult.value.data?.orders || []);
    } else {
      setCreditOrders([]);
    }

    setIsLoading(false);
  };

  const handlePurchaseCredits = async () => {
    const selectedPackage = (creditStatus?.credit_packages || []).find(
      (item) => item.package_id === selectedPackageId
    );

    if (!selectedPackage) {
      toast.error('No live credit package is selected.');
      return;
    }

    setIsPurchasing(true);
    try {
      const currentUrl = `${window.location.origin}/dashboard/usage`;
      const response = await creditsApi.purchase(
        selectedPackage.package_id,
        `${currentUrl}?credits=success`,
        `${currentUrl}?credits=cancelled`
      );

      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
        return;
      }

      toast.error('Credit checkout URL was not returned.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to start credit purchase.'));
    } finally {
      setIsPurchasing(false);
    }
  };

  const sortedUsageEntries = Object.entries(usage).sort(([left], [right]) => {
    return (
      USAGE_TYPE_ORDER.indexOf(left as (typeof USAGE_TYPE_ORDER)[number]) -
        USAGE_TYPE_ORDER.indexOf(right as (typeof USAGE_TYPE_ORDER)[number]) ||
      left.localeCompare(right)
    );
  });

  const currentBillingPlan = billingPlans.find((item) => item.id === plan) ?? null;
  const currentUsagePlan = usagePlans[plan] ?? null;
  const currentPrice = currentBillingPlan?.price_monthly ?? currentUsagePlan?.price_monthly ?? null;
  const nextPlan = billingPlans.find((item) => planRank(item.id) > planRank(plan)) ?? null;
  const creditPackages = [...(creditStatus?.credit_packages || [])].sort((left, right) => left.credits - right.credits);
  const selectedPackage = creditPackages.find((item) => item.package_id === selectedPackageId) ?? null;
  const canPurchaseCredits = Boolean(creditStatus?.purchase_available) && creditPackages.length > 0;
  const creditPurchaseBlockedReason = !creditStatus
    ? creditsError || 'Live credit balances are unavailable right now.'
    : !creditStatus.purchase_available
      ? 'Credit checkout is not available for this billing setup yet.'
      : creditPackages.length === 0
        ? 'No live credit packages are available right now.'
        : null;

  const getCreditPackageLabel = (packageId: string) => {
    return creditPackages.find((item) => item.package_id === packageId)?.label
      || packageId.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2].map((index) => (
            <Card key={index}>
              <CardContent className="pt-6">
                <Skeleton className="h-32 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2, 3, 4].map((index) => (
            <Card key={index}>
              <CardContent className="pt-6">
                <Skeleton className="h-28 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Usage & Credits</h1>
          <p className="text-gray-500">Only live billing, plan, and credit data is shown on this screen.</p>
        </div>
        <Badge className="bg-violet-100 px-3 py-1 text-sm text-violet-700">
          {formatPlanName(plan)} Plan
        </Badge>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Usage Next Best Action</Badge>
            <h2 className="text-xl font-semibold">Check whether any workflow is close to its limit</h2>
            <p className="mt-1 text-sm text-slate-300">
              Start with remaining capacity. Credit purchases, lifecycle detail, and plan math are secondary support sections.
            </p>
          </div>
          <Link href="/dashboard/billing">
            <Button className="bg-white text-slate-950 hover:bg-slate-100">
              Review plan capacity
            </Button>
          </Link>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Current Plan</CardTitle>
            <CardDescription>Live pricing and limits from the billing and usage contracts.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-2xl font-bold">{currentBillingPlan?.name || currentUsagePlan?.name || formatPlanName(plan)}</p>
                <p className="mt-1 text-sm text-gray-500">
                  {currentPrice != null ? `${formatUsd(currentPrice)}/month` : 'Live pricing is unavailable right now.'}
                </p>
              </div>
              <Button variant="outline" asChild>
                <Link href="/dashboard/billing">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Open Billing
                </Link>
              </Button>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border p-3">
                <p className="text-xs uppercase tracking-wide text-gray-500">Locations</p>
                <p className="mt-1 text-lg font-semibold">{formatCount(currentBillingPlan?.limits.locations)}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs uppercase tracking-wide text-gray-500">Posts / Month</p>
                <p className="mt-1 text-lg font-semibold">{formatCount(currentBillingPlan?.limits.posts_per_month)}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs uppercase tracking-wide text-gray-500">Included Credits</p>
                <p className="mt-1 text-lg font-semibold">{formatCount(creditStatus?.credits.monthly_allocation)}</p>
              </div>
            </div>

            <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-600">
              {nextPlan ? (
                <>
                  Next live upgrade: <span className="font-medium text-gray-900">{nextPlan.name}</span>{' '}
                  at {formatUsd(nextPlan.price_monthly)}/month.
                </>
              ) : (
                'You are already on the highest live plan exposed by billing.'
              )}
            </div>
          </CardContent>
        </Card>

        {creditStatus ? (
          <Card className="bg-gradient-to-br from-violet-600 to-indigo-600 text-white">
            <CardHeader className="pb-2">
              <CardTitle className="text-white">Credits</CardTitle>
              <CardDescription className="text-violet-100">
                Credits are used for overages after plan limits are exhausted.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm text-violet-200">Available Credits</p>
                  <p className="mt-1 text-4xl font-bold">{creditStatus.credits.total_available.toLocaleString()}</p>
                  {creditStatus.billing?.next_allocation ? (
                    <p className="mt-2 text-xs text-violet-100">
                      Next monthly allocation: {formatDate(creditStatus.billing.next_allocation)}
                    </p>
                  ) : null}
                </div>
                {canPurchaseCredits ? (
                  <Button
                    onClick={() => setIsPurchaseDialogOpen(true)}
                    className="bg-white text-violet-700 hover:bg-violet-50"
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Buy Credits
                  </Button>
                ) : (
                  <div className="rounded-lg border border-white/20 bg-white/10 px-4 py-3 text-sm text-violet-50">
                    {creditPurchaseBlockedReason}
                  </div>
                )}
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg bg-white/10 p-3">
                  <p className="text-xs uppercase tracking-wide text-violet-100">Bonus Balance</p>
                  <p className="mt-1 text-lg font-semibold">{creditStatus.credits.bonus_balance.toLocaleString()}</p>
                </div>
                <div className="rounded-lg bg-white/10 p-3">
                  <p className="text-xs uppercase tracking-wide text-violet-100">Monthly Allocation</p>
                  <p className="mt-1 text-lg font-semibold">{creditStatus.credits.monthly_allocation.toLocaleString()}</p>
                </div>
                <div className="rounded-lg bg-white/10 p-3">
                  <p className="text-xs uppercase tracking-wide text-violet-100">Purchased Credits</p>
                  <p className="mt-1 text-lg font-semibold">{creditStatus.stats.total_purchased.toLocaleString()}</p>
                </div>
              </div>

              {creditPurchaseBlockedReason ? (
                <p className="text-xs text-violet-100">{creditPurchaseBlockedReason}</p>
              ) : (
                <p className="text-xs text-violet-100">
                  Purchases use live package pricing and are applied only after Stripe confirms payment.
                </p>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Credits</CardTitle>
              <CardDescription>{creditsError || 'Live credit balances are unavailable right now.'}</CardDescription>
            </CardHeader>
          </Card>
        )}
      </div>

      {sortedUsageEntries.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {sortedUsageEntries.map(([type, data]) => {
            const Icon = getUsageIcon(type);
            const dailyProgress = getUsageProgress(data.daily_used, data.daily_limit);
            const monthlyProgress = getUsageProgress(data.monthly_used, data.monthly_limit);

            return (
              <Card key={type}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Icon className="h-5 w-5 text-violet-600" />
                    {getUsageLabel(type)}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="flex items-center gap-1 text-gray-500">
                        <Clock className="h-4 w-4" />
                        Daily
                      </span>
                      <span className="font-medium">
                        {data.daily_used.toLocaleString()} / {formatCount(data.daily_limit)}
                      </span>
                    </div>
                    <Progress value={dailyProgress} className="h-2" />
                    <p className="mt-1 text-xs text-gray-400">
                      {data.daily_remaining.toLocaleString()} remaining today
                    </p>
                  </div>

                  <div>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="flex items-center gap-1 text-gray-500">
                        <Calendar className="h-4 w-4" />
                        Monthly
                      </span>
                      <span className="font-medium">
                        {data.monthly_used.toLocaleString()} / {formatCount(data.monthly_limit)}
                      </span>
                    </div>
                    <Progress value={monthlyProgress} className="h-2" />
                    <p className="mt-1 text-xs text-gray-400">
                      {data.monthly_remaining.toLocaleString()} remaining this month
                    </p>
                  </div>

                  {(data.cooldown_seconds > 0 || data.overage_cost_cents > 0) ? (
                    <div className="flex flex-wrap gap-3 border-t pt-2 text-xs text-gray-500">
                      {data.cooldown_seconds > 0 ? (
                        <span>Cooldown: {formatCooldown(data.cooldown_seconds)}</span>
                      ) : null}
                      {data.overage_cost_cents > 0 ? (
                        <span>Overage: {data.overage_cost_cents} credits per extra use</span>
                      ) : null}
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Usage</CardTitle>
            <CardDescription>{usageError || 'No live usage data is available right now.'}</CardDescription>
          </CardHeader>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Live Plan Pricing & Limits</CardTitle>
          <CardDescription>
            Pricing comes from billing. SMS and AI allowances come from the usage contract. Upgrades are managed in Billing.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {plansError ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              {plansError}
            </div>
          ) : null}

          {billingPlans.length === 0 ? (
            <p className="text-sm text-gray-500">No live plan pricing is available right now.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="py-3 px-2 text-left">Metric</th>
                    {billingPlans.map((billingPlan) => (
                      <th key={billingPlan.id} className="px-2 py-3 text-center">
                        <div className="flex flex-col items-center gap-1">
                          <span>{billingPlan.name}</span>
                          {billingPlan.id === plan ? (
                            <Badge className="bg-violet-100 text-violet-700">Current</Badge>
                          ) : null}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b">
                    <td className="px-2 py-3 font-medium">Price / month</td>
                    {billingPlans.map((billingPlan) => (
                      <td
                        key={`${billingPlan.id}-price`}
                        className={`px-2 py-3 text-center ${billingPlan.id === plan ? 'bg-violet-50' : ''}`}
                      >
                        <span className="font-medium">{formatUsd(billingPlan.price_monthly)}</span>
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="px-2 py-3 font-medium">SMS</td>
                    {billingPlans.map((billingPlan) => (
                      <td
                        key={`${billingPlan.id}-sms`}
                        className={`px-2 py-3 text-center ${billingPlan.id === plan ? 'bg-violet-50' : ''}`}
                      >
                        {formatAllowance(usagePlans[billingPlan.id]?.sms_daily, usagePlans[billingPlan.id]?.sms_monthly)}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="px-2 py-3 font-medium">AI Content</td>
                    {billingPlans.map((billingPlan) => (
                      <td
                        key={`${billingPlan.id}-ai-content`}
                        className={`px-2 py-3 text-center ${billingPlan.id === plan ? 'bg-violet-50' : ''}`}
                      >
                        {formatAllowance(
                          usagePlans[billingPlan.id]?.ai_content_daily,
                          usagePlans[billingPlan.id]?.ai_content_monthly
                        )}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="px-2 py-3 font-medium">AI Images</td>
                    {billingPlans.map((billingPlan) => (
                      <td
                        key={`${billingPlan.id}-ai-image`}
                        className={`px-2 py-3 text-center ${billingPlan.id === plan ? 'bg-violet-50' : ''}`}
                      >
                        {formatAllowance(
                          usagePlans[billingPlan.id]?.ai_image_daily,
                          usagePlans[billingPlan.id]?.ai_image_monthly
                        )}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="px-2 py-3 font-medium">AI Responses</td>
                    {billingPlans.map((billingPlan) => (
                      <td
                        key={`${billingPlan.id}-ai-response`}
                        className={`px-2 py-3 text-center ${billingPlan.id === plan ? 'bg-violet-50' : ''}`}
                      >
                        {formatAllowance(
                          usagePlans[billingPlan.id]?.ai_response_daily,
                          usagePlans[billingPlan.id]?.ai_response_monthly
                        )}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="px-2 py-3 font-medium">API Calls</td>
                    {billingPlans.map((billingPlan) => (
                      <td
                        key={`${billingPlan.id}-api-calls`}
                        className={`px-2 py-3 text-center ${billingPlan.id === plan ? 'bg-violet-50' : ''}`}
                      >
                        {formatAllowance(
                          usagePlans[billingPlan.id]?.api_calls_daily,
                          usagePlans[billingPlan.id]?.api_calls_monthly
                        )}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="px-2 py-3 font-medium">Locations</td>
                    {billingPlans.map((billingPlan) => (
                      <td
                        key={`${billingPlan.id}-locations`}
                        className={`px-2 py-3 text-center ${billingPlan.id === plan ? 'bg-violet-50' : ''}`}
                      >
                        <span className="font-medium">{formatCount(billingPlan.limits.locations)}</span>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="px-2 py-3 font-medium">Posts / month</td>
                    {billingPlans.map((billingPlan) => (
                      <td
                        key={`${billingPlan.id}-posts`}
                        className={`px-2 py-3 text-center ${billingPlan.id === plan ? 'bg-violet-50' : ''}`}
                      >
                        <span className="font-medium">{formatCount(billingPlan.limits.posts_per_month)}</span>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )}

          <div className="flex flex-col gap-3 rounded-lg border bg-gray-50 p-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-gray-600">
              {nextPlan
                ? `${nextPlan.name} is the next live upgrade path from your current plan.`
                : 'Billing already shows the highest live plan currently available to this account.'}
            </p>
            <Button variant="outline" asChild>
              <Link href="/dashboard/billing">
                <ExternalLink className="mr-2 h-4 w-4" />
                Manage in Billing
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      {creditOrders.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5 text-violet-600" />
              Credit Purchase History
            </CardTitle>
            <CardDescription>Your recent live credit package purchases.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {creditOrders.map((order) => (
                <div
                  key={order.id}
                  className="flex flex-col gap-3 border-b py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="font-medium text-sm">{getCreditPackageLabel(order.package_id)}</p>
                    <p className="text-xs text-gray-400">{formatDate(order.created_at)}</p>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className="text-sm font-medium">+{order.credits_amount.toLocaleString()} credits</p>
                      <p className="text-xs text-gray-500">{formatUsdCents(order.price_cents)}</p>
                    </div>
                    <Badge
                      className={
                        order.status === 'completed'
                          ? 'bg-green-100 text-green-700'
                          : order.status === 'refunded'
                            ? 'bg-red-100 text-red-700'
                            : order.status === 'pending'
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-gray-100 text-gray-700'
                      }
                    >
                      {order.status.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Dialog open={isPurchaseDialogOpen} onOpenChange={setIsPurchaseDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Purchase Credits</DialogTitle>
            <DialogDescription>
              Choose a live package. Credits are added only after Stripe confirms payment.
            </DialogDescription>
          </DialogHeader>

          {creditPurchaseBlockedReason ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              {creditPurchaseBlockedReason}
            </div>
          ) : (
            <div className="space-y-4 py-4">
              <div className="grid gap-3 sm:grid-cols-2">
                {creditPackages.map((creditPackage) => {
                  const isSelected = selectedPackageId === creditPackage.package_id;
                  return (
                    <button
                      key={creditPackage.package_id}
                      type="button"
                      onClick={() => setSelectedPackageId(creditPackage.package_id)}
                      className={`rounded-lg border-2 p-4 text-left transition-colors ${
                        isSelected
                          ? 'border-violet-500 bg-violet-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <p className="font-medium">{creditPackage.label}</p>
                      <p className="mt-1 text-2xl font-bold">{creditPackage.credits.toLocaleString()}</p>
                      <p className="text-sm text-gray-500">credits</p>
                      <p className="mt-2 text-sm font-medium text-violet-600">
                        {formatUsdCents(creditPackage.price_cents)}
                      </p>
                    </button>
                  );
                })}
              </div>

              {selectedPackage ? (
                <div className="rounded-lg bg-gray-50 p-4">
                  <div className="flex justify-between text-sm">
                    <span>Package</span>
                    <span>{selectedPackage.label}</span>
                  </div>
                  <div className="mt-1 flex justify-between text-sm">
                    <span>Credits</span>
                    <span>{selectedPackage.credits.toLocaleString()}</span>
                  </div>
                  <div className="mt-1 flex justify-between text-sm">
                    <span>Effective price / credit</span>
                    <span>{formatUsdCents(Math.round(selectedPackage.price_cents / selectedPackage.credits))}</span>
                  </div>
                  <div className="mt-2 flex justify-between border-t pt-2 font-bold">
                    <span>Total</span>
                    <span>{formatUsdCents(selectedPackage.price_cents)}</span>
                  </div>
                </div>
              ) : null}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsPurchaseDialogOpen(false)}>
              Cancel
            </Button>
            {canPurchaseCredits ? (
              <Button
                onClick={handlePurchaseCredits}
                disabled={isPurchasing || !selectedPackage}
              >
                {isPurchasing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CreditCard className="mr-2 h-4 w-4" />}
                {selectedPackage ? `Purchase ${formatUsdCents(selectedPackage.price_cents)}` : 'Purchase Credits'}
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
