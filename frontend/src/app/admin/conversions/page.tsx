'use client';

import { useEffect, useState } from 'react';
import { adminApi } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertTriangle,
  BarChart3,
  Calendar,
  CreditCard,
  DollarSign,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  UserPlus,
  Users,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { toast } from 'sonner';

type PeriodKey = '7d' | '30d' | '90d';

interface ConversionMetricDelta {
  visitors: number | null;
  signups: number | null;
  trials: number | null;
  paid: number | null;
  revenue_collected: number | null;
}

interface ConversionMetricsSnapshot {
  visitors: number;
  signups: number;
  trials: number;
  paid: number;
  revenue_collected: number;
  current_mrr: number;
  visitor_to_signup: number;
  signup_to_trial: number;
  trial_to_paid: number;
  overall_conversion: number;
  churn_rate: number;
  avg_trial_length_days: number;
  top_drop_off_point: string;
  payment_recovery_accounts: number;
  canceled_subscriptions: number;
  changes: ConversionMetricDelta;
}

interface ConversionFunnelStep {
  name: string;
  count: number;
  rate: number;
  drop_off: number;
}

interface ConversionDropOffReason {
  reason: string;
  count: number;
  percentage: number;
}

interface ConversionInsight {
  id: string;
  severity: 'critical' | 'warning' | 'info';
  title: string;
  description: string;
}

interface ConversionAnalyticsResponse {
  start_date: string;
  end_date: string;
  period_days: number;
  metrics: ConversionMetricsSnapshot;
  funnel: ConversionFunnelStep[];
  drop_off_reasons: ConversionDropOffReason[];
  insights: ConversionInsight[];
  notes: string[];
  generated_at: string;
  source: string;
}

function formatDate(value: Date): string {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, '0');
  const day = `${value.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function getRangeForPeriod(period: PeriodKey): { startDate: string; endDate: string } {
  const end = new Date();
  const start = new Date(end);
  const days = period === '7d' ? 7 : period === '90d' ? 90 : 30;
  start.setDate(start.getDate() - (days - 1));

  return {
    startDate: formatDate(start),
    endDate: formatDate(end),
  };
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: value % 1 === 0 ? 0 : 2,
  }).format(value);
}

function formatChange(change: number | null | undefined): string | null {
  if (change === null || change === undefined) {
    return null;
  }
  const rounded = Math.abs(change).toFixed(1).replace(/\.0$/, '');
  return `${rounded}%`;
}

function changeTone(change: number | null | undefined): string {
  if (change === null || change === undefined || change === 0) {
    return 'text-slate-500';
  }
  return change > 0 ? 'text-emerald-600' : 'text-rose-600';
}

function insightTone(severity: ConversionInsight['severity']): string {
  if (severity === 'critical') {
    return 'border-rose-200 bg-rose-50 text-rose-900';
  }
  if (severity === 'warning') {
    return 'border-amber-200 bg-amber-50 text-amber-900';
  }
  return 'border-blue-200 bg-blue-50 text-blue-900';
}

function insightBadgeTone(severity: ConversionInsight['severity']): string {
  if (severity === 'critical') {
    return 'bg-rose-100 text-rose-700';
  }
  if (severity === 'warning') {
    return 'bg-amber-100 text-amber-700';
  }
  return 'bg-blue-100 text-blue-700';
}

async function fetchConversions(selectedPeriod: PeriodKey): Promise<ConversionAnalyticsResponse> {
  const range = getRangeForPeriod(selectedPeriod);
  const response = await adminApi.getConversions(range.startDate, range.endDate);
  return response.data as ConversionAnalyticsResponse;
}

function StatCard({
  title,
  value,
  change,
  icon: Icon,
  iconClassName,
}: {
  title: string;
  value: string;
  change: number | null | undefined;
  icon: LucideIcon;
  iconClassName: string;
}) {
  const changeLabel = formatChange(change);

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-sm text-slate-500">{title}</p>
            <p className="text-2xl font-semibold text-slate-900">{value}</p>
            <div className={`flex items-center gap-1 text-sm ${changeTone(change)}`}>
              {change !== null && change !== undefined ? (
                <>
                  {change >= 0 ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                  <span>{changeLabel} vs previous period</span>
                </>
              ) : (
                <span>Not enough previous-period data</span>
              )}
            </div>
          </div>
          <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconClassName}`}>
            <Icon className="h-5 w-5 text-white" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function ConversionsPage() {
  const [period, setPeriod] = useState<PeriodKey>('30d');
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<ConversionAnalyticsResponse | null>(null);

  const loadData = async (selectedPeriod: PeriodKey) => {
    setLoading(true);

    try {
      setData(await fetchConversions(selectedPeriod));
    } catch {
      toast.error('Failed to load live conversion analytics.');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      setLoading(true);

      try {
        const next = await fetchConversions(period);
        if (!cancelled) {
          setData(next);
        }
      } catch {
        if (!cancelled) {
          toast.error('Failed to load live conversion analytics.');
          setData(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [period]);

  if (loading && !data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-72" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-36" />
          ))}
        </div>
        <Skeleton className="h-80" />
        <div className="grid gap-6 xl:grid-cols-2">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Conversion Analytics</h1>
          <p className="text-sm text-slate-600">
            This screen now depends on live admin analytics data only.
          </p>
        </div>
        <Card>
          <CardContent className="flex min-h-56 flex-col items-center justify-center gap-3 text-center">
            <AlertTriangle className="h-10 w-10 text-amber-500" />
            <div className="space-y-1">
              <p className="font-medium text-slate-900">Live conversion analytics are unavailable.</p>
              <p className="text-sm text-slate-600">
                The page will not fall back to demo numbers. Try refreshing after the backend is healthy.
              </p>
            </div>
            <Button variant="outline" onClick={() => void loadData(period)}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { metrics, funnel, drop_off_reasons: dropOffReasons, insights, notes } = data;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold text-slate-900">Conversion Analytics</h1>
          <p className="text-sm text-slate-600">
            Live funnel reporting for signups, trials, paid accounts, and billing health.
          </p>
          <p className="text-xs text-slate-500">
            Range: {data.start_date} to {data.end_date} - Source: {data.source}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Select value={period} onValueChange={(value) => setPeriod(value as PeriodKey)}>
            <SelectTrigger className="w-[150px]">
              <Calendar className="mr-2 h-4 w-4" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>

          <Button variant="outline" onClick={() => void loadData(period)}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {notes.length > 0 && (
        <Card className="border-slate-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Data notes</CardTitle>
            <CardDescription>
              This page uses persisted production signals only and avoids fabricated admin demo numbers.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {notes.map((note) => (
              <div key={note} className="flex items-start gap-2 text-sm text-slate-600">
                <span className="mt-1 h-1.5 w-1.5 rounded-full bg-slate-400" />
                <span>{note}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Website visitors"
          value={metrics.visitors.toLocaleString()}
          change={metrics.changes.visitors}
          icon={Users}
          iconClassName="bg-blue-500"
        />
        <StatCard
          title="New signups"
          value={metrics.signups.toLocaleString()}
          change={metrics.changes.signups}
          icon={UserPlus}
          iconClassName="bg-emerald-500"
        />
        <StatCard
          title="Paid accounts"
          value={metrics.paid.toLocaleString()}
          change={metrics.changes.paid}
          icon={CreditCard}
          iconClassName="bg-violet-500"
        />
        <StatCard
          title="Revenue collected"
          value={formatCurrency(metrics.revenue_collected)}
          change={metrics.changes.revenue_collected}
          icon={DollarSign}
          iconClassName="bg-amber-500"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="border-l-4 border-l-blue-500">
          <CardContent className="pt-6">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm text-slate-500">Visitor to signup</span>
              <Badge className="bg-blue-100 text-blue-700">{metrics.visitor_to_signup}%</Badge>
            </div>
            <Progress value={metrics.visitor_to_signup} className="h-2" />
            <p className="mt-3 text-xs text-slate-500">
              Overall conversion from website visitors into account creation.
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-emerald-500">
          <CardContent className="pt-6">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm text-slate-500">Signup to trial</span>
              <Badge className="bg-emerald-100 text-emerald-700">{metrics.signup_to_trial}%</Badge>
            </div>
            <Progress value={metrics.signup_to_trial} className="h-2" />
            <p className="mt-3 text-xs text-slate-500">
              Measures whether new accounts are activating the product quickly enough.
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-violet-500">
          <CardContent className="pt-6">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm text-slate-500">Trial to paid</span>
              <Badge className="bg-violet-100 text-violet-700">{metrics.trial_to_paid}%</Badge>
            </div>
            <Progress value={metrics.trial_to_paid} className="h-2" />
            <p className="mt-3 text-xs text-slate-500">
              Based on invoice-backed successful payments in the selected range.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Funnel overview
          </CardTitle>
          <CardDescription>
            Each step uses live counts only. Missing instrumentation stays visible as missing data.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {funnel.map((step) => (
            <div key={step.name} className="space-y-2">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-medium text-slate-900">{step.name}</p>
                  <p className="text-sm text-slate-500">{step.count.toLocaleString()} accounts or visits</p>
                </div>
                <div className="text-right">
                  <p className="font-medium text-slate-900">{step.rate}%</p>
                  <p className="text-sm text-rose-500">{step.drop_off}% drop-off</p>
                </div>
              </div>
              <Progress value={step.rate} className="h-3" />
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Drop-off signals
            </CardTitle>
            <CardDescription>
              These reasons are derived from live funnel gaps, churn, and payment recovery state.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {dropOffReasons.map((reason, index) => (
              <div key={`${reason.reason}-${index}`} className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-sm font-medium text-slate-700">
                      {index + 1}
                    </div>
                    <div>
                      <p className="font-medium text-slate-900">{reason.reason}</p>
                      <p className="text-sm text-slate-500">{reason.count.toLocaleString()} affected records</p>
                    </div>
                  </div>
                  <p className="text-sm font-medium text-slate-700">{reason.percentage}%</p>
                </div>
                <Progress value={reason.percentage} className="h-2" />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-amber-500" />
              Operator insights
            </CardTitle>
            <CardDescription>
              Action-focused interpretation of the current conversion and billing signals.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {insights.map((insight) => (
              <div key={insight.id} className={`rounded-xl border p-4 ${insightTone(insight.severity)}`}>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <p className="font-medium">{insight.title}</p>
                  <Badge className={insightBadgeTone(insight.severity)}>{insight.severity}</Badge>
                </div>
                <p className="text-sm leading-6">{insight.description}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Health snapshot</CardTitle>
          <CardDescription>
            Current monetization and retention context for the selected reporting window.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-2xl bg-slate-50 p-5">
            <p className="text-sm text-slate-500">Current MRR snapshot</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{formatCurrency(metrics.current_mrr)}</p>
            <p className="mt-2 text-xs text-slate-500">Current billable subscription footprint</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-5">
            <p className="text-sm text-slate-500">Overall conversion</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{metrics.overall_conversion}%</p>
            <p className="mt-2 text-xs text-slate-500">Visitor to paid account</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-5">
            <p className="text-sm text-slate-500">Churn rate</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{metrics.churn_rate}%</p>
            <p className="mt-2 text-xs text-slate-500">{metrics.canceled_subscriptions} subscription cancellations in range</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-5">
            <p className="text-sm text-slate-500">Average trial length</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{metrics.avg_trial_length_days}d</p>
            <p className="mt-2 text-xs text-slate-500">Observed from persisted trial starts</p>
          </div>
          <div className="rounded-2xl bg-slate-50 p-5">
            <p className="text-sm text-slate-500">Top drop-off point</p>
            <p className="mt-2 text-lg font-semibold text-slate-900">{metrics.top_drop_off_point}</p>
            <p className="mt-2 text-xs text-slate-500">
              {metrics.payment_recovery_accounts} account(s) currently in payment recovery
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
