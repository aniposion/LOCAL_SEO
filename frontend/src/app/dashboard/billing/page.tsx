'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  CheckCircle,
  CreditCard,
  Download,
  ExternalLink,
  Loader2,
  Zap,
  Building2,
  Star,
  Crown,
  AlertCircle,
  Receipt,
  FileText,
  Copy,
  Calendar,
  XCircle,
  RefreshCw,
  Mail,
  Filter,
  ArrowDownRight,
  Clock,
  Ban,
  Plus,
  Trash2,
  Check,
} from 'lucide-react';
import { billingApi, creditsApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { toast } from 'sonner';
import { AddonsSection } from '@/components/billing/AddonsSection';
import { BillingAuditTrail } from '@/components/billing/BillingAuditTrail';
import { BillingInfoSection } from '@/components/billing/BillingInfoSection';

interface Subscription {
  plan: string;
  plan_type?: string;
  status: string;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  price: number;
  interval: 'monthly' | 'yearly';
  trial_end?: string | null;
  dunning_status?: string;
}

interface Invoice {
  id: string;
  number: string | null;
  status: string;
  amount: number;
  currency: string;
  created_at: string;
  paid_at: string | null;
  pdf_url: string | null;
  hosted_url: string | null;
  line_items: Array<{ description: string; amount: number }>;
}

interface PaymentMethod {
  id: string;
  type: string;
  card: {
    brand: string;
    last4: string;
    exp_month: number;
    exp_year: number;
  };
  is_default: boolean;
}

interface Payment {
  id: string;
  amount: number;
  currency: string;
  status: string;
  description: string | null;
  invoice_url: string | null;
  receipt_url: string | null;
  created_at: string;
}

interface CreditRefundOrder {
  id: string;
  package_id: string;
  credits_amount: number;
  price_cents: number;
  status: string;
  created_at: string;
  refunded_at?: string | null;
}

interface CreditPurchaseLifecycleOrder {
  id: string;
  package_id: string;
  credits_amount: number;
  price_cents: number;
  status: string;
  stripe_session_id: string;
  stripe_payment_intent_id?: string | null;
  created_at: string;
  completed_at?: string | null;
  refunded_at?: string | null;
}

interface Plan {
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
  popular?: boolean;
  setup_fee?: number | null;
  managed_service?: boolean;
  minimum_term_months?: number | null;
}

interface SubscriptionChangePreview {
  current_plan: {
    name: string;
    price: number;
    add_ons: string[];
  };
  new_plan: {
    name: string;
    price: number;
    add_ons: string[];
  };
  proration: {
    amount_due_now: number;
    credit_applied: number;
    next_invoice_date: string | null;
    next_invoice_amount: number;
  };
  effective: string;
  preview_line_items: Array<{
    description: string;
    amount: number;
    period_start: string;
    period_end: string;
    proration: boolean;
  }>;
}

interface BillingPlanResponse {
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
  setup_fee?: number | null;
  managed_service?: boolean;
  minimum_term_months?: number | null;
}

const PLAN_ORDER = ['free', 'maps_starter', 'calls_growth', 'competitive_market', 'starter', 'pro', 'premium', 'agency'] as const;
const PLAN_ORDER_INDEX = PLAN_ORDER.reduce<Record<string, number>>((acc, planId, index) => {
  acc[planId] = index;
  return acc;
}, {});
const POPULAR_PLAN_ID = 'calls_growth';

function normalizePlan(plan: BillingPlanResponse): Plan {
  return {
    id: plan.id,
    name: plan.name,
    price_monthly: plan.price_monthly,
    price_yearly: plan.price_yearly,
    features: plan.features,
    limits: plan.limits,
    popular: plan.id === POPULAR_PLAN_ID,
    setup_fee: plan.setup_fee,
    managed_service: plan.managed_service,
    minimum_term_months: plan.minimum_term_months,
  };
}

function sortPlans(plans: BillingPlanResponse[]): Plan[] {
  return plans
    .map(normalizePlan)
    .sort((left, right) => {
      const leftIndex = PLAN_ORDER_INDEX[left.id] ?? Number.MAX_SAFE_INTEGER;
      const rightIndex = PLAN_ORDER_INDEX[right.id] ?? Number.MAX_SAFE_INTEGER;
      return leftIndex - rightIndex || left.name.localeCompare(right.name);
    });
}

function formatLocationsLabel(limit: number): string {
  if (limit < 0) return 'Unlimited locations';
  if (limit === 1) return '1 Location';
  return `${limit} Locations`;
}

function planRank(planId: string): number {
  return PLAN_ORDER_INDEX[planId] ?? Number.MAX_SAFE_INTEGER;
}

function normalizeSubscription(
  data: Partial<Subscription> & {
    plan_type?: string;
    status: string;
    billing_cycle?: 'monthly' | 'yearly';
    current_price?: number | null;
  }
): Subscription {
  const planId = data.plan || data.plan_type || 'free';
  const interval =
    data.interval === 'yearly' || data.billing_cycle === 'yearly' ? 'yearly' : 'monthly';
  const price =
    typeof data.price === 'number'
      ? data.price
      : typeof data.current_price === 'number'
        ? data.current_price
        : 0;

  return {
    plan: planId,
    plan_type: data.plan_type || planId,
    status: data.status,
    current_period_end: data.current_period_end || null,
    cancel_at_period_end: data.cancel_at_period_end ?? false,
    price,
    interval,
    trial_end: data.trial_end || null,
    dunning_status: data.dunning_status,
  };
}

export default function BillingPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [paymentsLoading, setPaymentsLoading] = useState(true);
  const [refundOrders, setRefundOrders] = useState<CreditRefundOrder[]>([]);
  const [refundOrdersLoading, setRefundOrdersLoading] = useState(true);
  const [creditOrders, setCreditOrders] = useState<CreditPurchaseLifecycleOrder[]>([]);
  const [creditOrdersLoading, setCreditOrdersLoading] = useState(true);
  const [creditOrderStatusFilter, setCreditOrderStatusFilter] = useState<string>('all');
  const [creditOrderSearch, setCreditOrderSearch] = useState('');
  const [selectedCreditOrder, setSelectedCreditOrder] = useState<CreditPurchaseLifecycleOrder | null>(null);
  const [showCreditOrderDetail, setShowCreditOrderDetail] = useState(false);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [invoicesLoading, setInvoicesLoading] = useState(true);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
  const [billingInterval, setBillingInterval] = useState<'monthly' | 'yearly'>('monthly');
  const [isUpgrading, setIsUpgrading] = useState(false);
  const [isResuming, setIsResuming] = useState(false);

  // Plan change preview state
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState<SubscriptionChangePreview | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [isChangingPlan, setIsChangingPlan] = useState(false);
  const [checkoutNotice, setCheckoutNotice] = useState<'success' | 'cancelled' | null>(null);

  // Payment methods state
  const [paymentMethodsLoading, setPaymentMethodsLoading] = useState(true);
  const [removingPaymentMethod, setRemovingPaymentMethod] = useState<string | null>(null);
  const [settingDefault, setSettingDefault] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const checkoutState = new URLSearchParams(window.location.search).get('checkout');
      if (checkoutState === 'success' || checkoutState === 'cancelled') {
        setCheckoutNotice(checkoutState);
      }
    }
    void fetchPlans();
    void fetchSubscription();
    void fetchPayments();
    void fetchRefundOrders();
    void fetchCreditOrders();
    void fetchInvoices();
    void fetchPaymentMethods();
  }, []);

  const fetchPlans = async () => {
    setPlansLoading(true);
    setPlansError(null);
    try {
      const response = await billingApi.getPlans();
      setPlans(sortPlans(response.data || []));
    } catch (error) {
      setPlans([]);
      setPlansError(getApiErrorMessage(error, 'Live billing plans are unavailable right now.'));
    } finally {
      setPlansLoading(false);
    }
  };

  const fetchSubscription = async () => {
    try {
      const [subscriptionResponse, dunningResponse] = await Promise.all([
        billingApi.getSubscription(),
        billingApi.getDunningStatus().catch(() => null),
      ]);

      const dunningState = dunningResponse?.data?.state;
      const normalized = normalizeSubscription({
        ...subscriptionResponse.data,
        dunning_status:
          dunningState === 'warning'
            ? 'grace_period'
            : dunningState === 'suspended'
              ? 'restricted'
              : undefined,
      });

      setSubscription(normalized);
    } catch {
      setSubscription(null);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchPayments = async () => {
    setPaymentsLoading(true);
    try {
      const response = await billingApi.getPayments(20);
      setPayments(response.data);
    } catch {
      // Demo payments for development
      setPayments([]);
    } finally {
      setPaymentsLoading(false);
    }
  };

  const fetchRefundOrders = async () => {
    setRefundOrdersLoading(true);
    try {
      const response = await creditsApi.getOrders('refunded', 6, 0);
      setRefundOrders(response.data?.orders || []);
    } catch {
      setRefundOrders([]);
    } finally {
      setRefundOrdersLoading(false);
    }
  };

  const fetchCreditOrders = async () => {
    setCreditOrdersLoading(true);
    try {
      const response = await creditsApi.getOrders(undefined, 10, 0);
      setCreditOrders(response.data?.orders || []);
    } catch {
      setCreditOrders([]);
    } finally {
      setCreditOrdersLoading(false);
    }
  };

  const fetchInvoices = async () => {
    setInvoicesLoading(true);
    try {
      const response = await billingApi.getInvoices({ limit: 10 });
      setInvoices(response.data.invoices || []);
    } catch {
      setInvoices([]);
    } finally {
      setInvoicesLoading(false);
    }
  };

  const fetchPaymentMethods = async () => {
    setPaymentMethodsLoading(true);
    try {
      const response = await billingApi.getPaymentMethods();
      setPaymentMethods(response.data || []);
    } catch {
      setPaymentMethods([]);
    } finally {
      setPaymentMethodsLoading(false);
    }
  };

  // Plan change preview
  const handlePreviewChange = async (planId: string) => {
    setSelectedPlan(planId);
    setPreviewLoading(true);
    setShowPreviewModal(true);
    try {
      const response = await billingApi.previewChange(planId, []);
      setPreviewData(response.data);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to load the plan preview.'));
      setShowPreviewModal(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleConfirmPlanChange = async () => {
    if (!selectedPlan) return;
    setIsChangingPlan(true);
    try {
      await billingApi.changeSubscription(selectedPlan, [], true);
      toast.success('Plan updated successfully.');
      setShowPreviewModal(false);
      void fetchSubscription();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to change the plan.'));
    } finally {
      setIsChangingPlan(false);
    }
  };

  // Payment method management
  const handleRemovePaymentMethod = async (methodId: string) => {
    setRemovingPaymentMethod(methodId);
    try {
      await billingApi.removePaymentMethod(methodId);
      toast.success('Payment method removed.');
      void fetchPaymentMethods();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to remove the payment method.'));
    } finally {
      setRemovingPaymentMethod(null);
    }
  };

  const handleSetDefaultPaymentMethod = async (methodId: string) => {
    setSettingDefault(methodId);
    try {
      await billingApi.setDefaultPaymentMethod(methodId);
      toast.success('Default payment method updated.');
      void fetchPaymentMethods();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to update the default payment method.'));
    } finally {
      setSettingDefault(null);
    }
  };

  const handleDownloadInvoicePdf = async (invoiceId: string) => {
    try {
      const response = await billingApi.getInvoicePdf(invoiceId);
      if (response.data.pdf_url) {
        window.open(response.data.pdf_url, '_blank');
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to download the invoice PDF.'));
    }
  };

  const getCardBrandLogo = (brand: string) => {
    const brandColors: Record<string, string> = {
      visa: 'from-blue-600 to-blue-800',
      mastercard: 'from-red-500 to-orange-500',
      amex: 'from-blue-400 to-blue-600',
      discover: 'from-orange-400 to-orange-600',
    };
    return brandColors[brand.toLowerCase()] || 'from-gray-600 to-gray-800';
  };

  const handleResumeSubscription = async () => {
    setIsResuming(true);
    try {
      await billingApi.resumeSubscription();
      toast.success('Subscription resumed.');
      void fetchSubscription();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to resume the subscription.'));
    } finally {
      setIsResuming(false);
    }
  };

  const handleExportCSV = async () => {
    try {
      const response = await billingApi.exportPayments({});
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'payments.csv';
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Payment export downloaded.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to export payment history.'));
    }
  };

  const handleResendInvoice = async (invoiceId: string) => {
    try {
      await billingApi.resendInvoice(invoiceId);
      toast.success('Invoice email sent.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to resend the invoice.'));
    }
  };

  const formatCurrency = (amount: number, currency: string) => {
    if (currency.toUpperCase() === 'KRW') {
      return `\${amount.toLocaleString()}`;
    }
    return `$${amount.toFixed(2)}`;
  };

  const formatUsdCents = (amountCents: number) => formatCurrency(amountCents / 100, 'USD');

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const formatCreditPackageLabel = (packageId: string) => {
    return packageId.replace('credits_', '').replace(/_/g, ' ');
  };

  const formatCreditOrderStatus = (status: string) =>
    status.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());

  const creditOrderCounts = creditOrders.reduce(
    (counts, order) => {
      counts[order.status] = (counts[order.status] || 0) + 1;
      return counts;
    },
    {} as Record<string, number>
  );

  const filteredCreditOrders = useMemo(() => {
    const search = creditOrderSearch.trim().toLowerCase();
    return creditOrders.filter((order) => {
      const matchesStatus =
        creditOrderStatusFilter === 'all' || order.status === creditOrderStatusFilter;
      const matchesSearch =
        !search ||
        order.package_id.toLowerCase().includes(search) ||
        order.status.toLowerCase().includes(search) ||
        String(order.credits_amount).includes(search);
      return matchesStatus && matchesSearch;
    });
  }, [creditOrders, creditOrderSearch, creditOrderStatusFilter]);

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'succeeded':
        return <Badge className="bg-green-100 text-green-700">Succeeded</Badge>;
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-700">Pending</Badge>;
      case 'failed':
        return <Badge className="bg-red-100 text-red-700">Failed</Badge>;
      default:
        return <Badge className="bg-gray-100 text-gray-700">{status}</Badge>;
    }
  };

  const handleUpgrade = async (planId: string) => {
    // If user has active subscription, show preview modal
    const currentPlanId = subscription?.plan || subscription?.plan_type || 'free';

    if (subscription && subscription.status === 'active' && currentPlanId !== 'free') {
      handlePreviewChange(planId);
      return;
    }

    // Otherwise redirect to checkout for new subscription
    setIsUpgrading(true);
    try {
      const response = await billingApi.createCheckout(planId, billingInterval);
      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      } else {
        toast.success('Plan updated successfully!');
        void fetchSubscription();
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to process the upgrade.'));
    } finally {
      setIsUpgrading(false);
    }
  };

  const handleManageBilling = async () => {
    try {
      const response = await billingApi.getPortal();
      if (response.data.portal_url) {
        window.location.href = response.data.portal_url;
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to open the billing portal.'));
    }
  };

  const currentPlanId = subscription?.plan || subscription?.plan_type || 'free';
  const currentPlan = plans.find((p) => p.id === currentPlanId) ?? null;
  const currentPlanName = currentPlan?.name || currentPlanId.replace(/\b\w/g, (char) => char.toUpperCase());

  const handleCopyStripeRefs = async (order: CreditPurchaseLifecycleOrder) => {
    const refs = [
      `Credit order ID: ${order.id}`,
      `Stripe checkout session: ${order.stripe_session_id || 'Not recorded'}`,
      `Stripe payment intent: ${order.stripe_payment_intent_id || 'Not available yet'}`,
    ].join('\n');

    try {
      await navigator.clipboard.writeText(refs);
      toast.success('Stripe references copied.');
    } catch {
      window.prompt('Copy the Stripe references below:', refs);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-6 w-32 mb-4" />
            <Skeleton className="h-4 w-64" />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Billing</h1>
        <p className="text-gray-500">Start with plan status. Open billing records only when you need invoice or payment detail.</p>
      </div>

      {checkoutNotice ? (
        <div
          className={`rounded-lg border p-4 ${
            checkoutNotice === 'success'
              ? 'border-green-200 bg-green-50 text-green-900'
              : 'border-amber-200 bg-amber-50 text-amber-950'
          }`}
        >
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-3">
              {checkoutNotice === 'success' ? (
                <CheckCircle className="mt-0.5 h-5 w-5 text-green-600" />
              ) : (
                <AlertCircle className="mt-0.5 h-5 w-5 text-amber-600" />
              )}
              <div>
                <p className="font-medium">
                  {checkoutNotice === 'success' ? 'Checkout is being confirmed' : 'Checkout was not completed'}
                </p>
                <p className="mt-1 text-sm">
                  {checkoutNotice === 'success'
                    ? 'Stripe confirmation can take a moment. Refresh this page if the plan has not updated yet.'
                    : 'You can retry checkout, open the billing portal, or contact support if the payment method was declined.'}
                </p>
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={handleManageBilling}>
              Manage billing
            </Button>
          </div>
        </div>
      ) : null}

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Billing Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {subscription?.status === 'past_due' || subscription?.dunning_status === 'restricted'
                ? 'Fix payment access first'
                : subscription?.status === 'trialing'
                  ? 'Compare plans before the free preview ends'
                  : 'Confirm the current plan still matches your workflow'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Plan choice controls which growth workflows unlock. Payment history, invoices, and audit logs stay below as secondary details.
            </p>
          </div>
          <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={handleManageBilling}>
            Manage billing
          </Button>
        </CardContent>
      </Card>

      {/* Dunning Banners */}
      {subscription?.status === 'past_due' && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <XCircle className="w-5 h-5 text-red-600 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium text-red-800">Payment failed</p>
            <p className="text-sm text-red-700">
              Please update your billing method. We will retry the charge automatically.
            </p>
          </div>
          <Button size="sm" onClick={handleManageBilling}>
            Update billing method
          </Button>
        </div>
      )}

      {subscription?.dunning_status === 'grace_period' && (
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-start gap-3">
          <Clock className="w-5 h-5 text-yellow-600 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium text-yellow-800">Payment grace period</p>
            <p className="text-sm text-yellow-700">
              Update your billing method within 7 days to avoid service restrictions.
            </p>
          </div>
          <Button size="sm" onClick={handleManageBilling}>
            Update billing method
          </Button>
        </div>
      )}

      {subscription?.dunning_status === 'restricted' && (
        <div className="p-4 bg-gray-900 border border-gray-700 rounded-lg flex items-start gap-3">
          <Ban className="w-5 h-5 text-red-400 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium text-white">Service is restricted</p>
            <p className="text-sm text-gray-300">
              Payment is still unresolved, so content creation and some workflows are currently limited until billing is fixed.
            </p>
          </div>
          <Button size="sm" variant="destructive" onClick={handleManageBilling}>
            Pay now
          </Button>
        </div>
      )}

      {/* Current Plan */}
      <Card>
        <CardHeader>
          <CardTitle>Current Plan</CardTitle>
          <CardDescription>Your active subscription details</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center">
                <Zap className="w-7 h-7 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-xl font-bold">{currentPlanName}</h3>
                  <Badge className={
                    subscription?.status === 'active' ? 'bg-green-100 text-green-700' :
                    subscription?.status === 'trialing' ? 'bg-blue-100 text-blue-700' :
                    subscription?.status === 'past_due' ? 'bg-red-100 text-red-700' :
                    'bg-yellow-100 text-yellow-700'
                  }>
                    {subscription?.status === 'active' ? 'Active' :
                     subscription?.status === 'trialing' ? 'Preview' :
                     subscription?.status === 'past_due' ? 'Past Due' :
                     subscription?.status}
                  </Badge>
                </div>
                <p className="text-gray-500">
                  {formatCurrency(subscription?.price || 0, 'USD')}/
                  {subscription?.interval === 'yearly' ? 'yr' : 'mo'} ·
                  {subscription?.status === 'trialing'
                    ? ` Preview ends on ${subscription?.trial_end && new Date(subscription.trial_end).toLocaleDateString()}`
                    : ` Renews on ${subscription?.current_period_end && new Date(subscription.current_period_end).toLocaleDateString()}`
                  }
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={handleManageBilling}>
                <CreditCard className="w-4 h-4 mr-2" />
                Manage Billing
              </Button>
            </div>
          </div>

          {/* Cancellation scheduled banner with Resume button */}
          {subscription?.cancel_at_period_end && (
            <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />
              <div className="flex-1">
                <p className="font-medium text-yellow-800">Cancellation scheduled</p>
                <p className="text-sm text-yellow-700">
                  {subscription?.current_period_end && new Date(subscription.current_period_end).toLocaleDateString()} - your subscription will end on that date unless you resume first.
                  You can resume at any time before the current period closes.
                </p>
              </div>
              <Button
                size="sm"
                onClick={handleResumeSubscription}
                disabled={isResuming}
              >
                {isResuming ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-1" />
                    Resume subscription
                  </>
                )}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Plans */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold">Available Plans</h2>
          <div className="flex items-center gap-2 bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => setBillingInterval('monthly')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                billingInterval === 'monthly' ? 'bg-white shadow' : 'text-gray-600'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingInterval('yearly')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                billingInterval === 'yearly' ? 'bg-white shadow' : 'text-gray-600'
              }`}
            >
              Yearly
              <Badge className="ml-2 bg-green-100 text-green-700">Save 17%</Badge>
            </button>
          </div>
        </div>

        {plansLoading ? (
          <div className="grid gap-6 md:grid-cols-3">
            {[1, 2, 3].map((index) => (
              <Card key={index}>
                <CardHeader>
                  <Skeleton className="h-6 w-24" />
                  <Skeleton className="h-4 w-32" />
                </CardHeader>
                <CardContent className="space-y-4">
                  <Skeleton className="h-10 w-28" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-10 w-full" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : plansError ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            {plansError}
          </div>
        ) : (
        <div className="grid md:grid-cols-3 gap-6">
          {plans.map((plan) => {
            const price = billingInterval === 'monthly' ? plan.price_monthly : plan.price_yearly;
            const isCurrentPlan = plan.id === currentPlanId;
            const nextActionLabel =
              planRank(plan.id) > planRank(currentPlanId) ? 'Upgrade' : 'Downgrade';

            return (
              <Card
                key={plan.id}
                className={`relative ${plan.popular ? 'border-violet-500 border-2' : ''} ${
                  isCurrentPlan ? 'bg-violet-50' : ''
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-violet-600">Most Popular</Badge>
                  </div>
                )}
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {plan.id === 'maps_starter' && <Building2 className="w-5 h-5 text-violet-600" />}
                    {plan.id === 'calls_growth' && <Zap className="w-5 h-5 text-violet-600" />}
                    {plan.id === 'competitive_market' && <Crown className="w-5 h-5 text-amber-500" />}
                    {plan.id === 'starter' && <Zap className="w-5 h-5 text-violet-600" />}
                    {plan.id === 'pro' && <Star className="w-5 h-5 text-violet-600" />}
                    {plan.id === 'premium' && <Crown className="w-5 h-5 text-amber-500" />}
                    {plan.id === 'agency' && <Building2 className="w-5 h-5 text-violet-600" />}
                    {plan.name}
                  </CardTitle>
                  <CardDescription>
                    {formatLocationsLabel(plan.limits.locations)}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="mb-6">
                    <span className="text-4xl font-bold">${price}</span>
                    <span className="text-gray-500">/{billingInterval === 'monthly' ? 'mo' : 'yr'}</span>
                    {billingInterval === 'yearly' && (
                      <div className="mt-1">
                        <span className="text-sm text-gray-400 line-through">${plan.price_monthly * 12}/yr</span>
                        <span className="text-sm text-green-600 ml-2">Save ${(plan.price_monthly * 12) - plan.price_yearly}</span>
                      </div>
                    )}
                    {typeof plan.setup_fee === 'number' ? (
                      <div className="mt-1 text-sm text-gray-500">
                        ${plan.setup_fee.toLocaleString()} setup
                        {plan.minimum_term_months ? ` | ${plan.minimum_term_months}-month pilot` : ''}
                      </div>
                    ) : null}
                  </div>

                  <ul className="space-y-3 mb-6">
                    {plan.features.map((feature, index) => (
                      <li key={index} className="flex items-center gap-2 text-sm">
                        <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                        {feature}
                      </li>
                    ))}
                  </ul>

                  {isCurrentPlan ? (
                    <div className="flex w-full items-center justify-center rounded-md border border-border bg-muted/40 px-4 py-2 text-sm font-medium text-muted-foreground">
                      Current Plan
                    </div>
                  ) : (
                    <Button
                      className={`w-full ${plan.popular ? 'bg-gradient-to-r from-violet-600 to-indigo-600' : ''}`}
                      variant={plan.popular ? 'default' : 'outline'}
                      onClick={() => handleUpgrade(plan.id)}
                      disabled={isUpgrading}
                    >
                      {isUpgrading ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        nextActionLabel
                      )}
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
        )}
      </div>

      {/* Add-ons Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Plus className="w-5 h-5" />
                Add-ons
              </CardTitle>
              <CardDescription>Expand your plan with add-ons that fit your workflow.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <AddonsSection
            currentPlan={currentPlanId}
            onAddonChange={() => void fetchSubscription()}
          />
        </CardContent>
      </Card>

      {/* Billing Info */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="w-5 h-5" />
                Billing Details
              </CardTitle>
              <CardDescription>Manage invoice details and billing contact information.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <BillingInfoSection />
        </CardContent>
      </Card>

      <details className="group rounded-xl border bg-white shadow-sm">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4">
          <div>
            <div className="text-sm font-semibold text-slate-900">Operational billing records</div>
            <div className="text-sm text-slate-500">
              Payment history, credit refunds, and credit purchase lifecycle are available when support or accounting needs them.
            </div>
          </div>
          <span className="text-xs font-medium text-slate-500 group-open:hidden">Show</span>
          <span className="hidden text-xs font-medium text-slate-500 group-open:inline">Hide</span>
        </summary>
        <div className="space-y-6 px-4 pb-4">
      {/* Payment History */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Receipt className="w-5 h-5" />
                Payment History
              </CardTitle>
              <CardDescription>Review charges, refunds, and receipts.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {paymentsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : payments.length === 0 ? (
            <div className="text-center py-12">
              <Receipt className="w-12 h-12 mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500">No payments recorded yet.</p>
              <p className="mt-1 text-sm text-gray-400">Your first successful charge will appear here.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {payments.map((payment) => (
                <div
                  key={payment.id}
                  className="flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-gradient-to-br from-violet-500 to-indigo-600 rounded-lg flex items-center justify-center">
                      <CreditCard className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <p className="font-medium">
                        {payment.description || 'Subscription charge'}
                      </p>
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <Calendar className="w-3.5 h-3.5" />
                        {formatDate(payment.created_at)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="font-bold text-lg">
                        {formatCurrency(payment.amount, payment.currency)}
                      </p>
                      {getStatusBadge(payment.status)}
                    </div>
                    <div className="flex items-center gap-1">
                      {payment.invoice_url && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => window.open(payment.invoice_url!, '_blank')}
                          title="Open invoice"
                        >
                          <FileText className="w-4 h-4" />
                        </Button>
                      )}
                      {payment.receipt_url && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => window.open(payment.receipt_url!, '_blank')}
                          title="Download receipt"
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
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
            <ArrowDownRight className="h-5 w-5 text-rose-600" />
            Credit Refund History
          </CardTitle>
          <CardDescription>
            Refunded credit purchases and the balance reversals tied to them.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {refundOrdersLoading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : refundOrders.length === 0 ? (
            <div className="rounded-lg border border-dashed p-6 text-center text-sm text-gray-500">
              No refunded credit purchases have been recorded yet.
            </div>
          ) : (
            <div className="space-y-3">
              {refundOrders.map((order) => (
                <div
                  key={order.id}
                  className="flex flex-col gap-3 rounded-lg border bg-rose-50/50 p-4 md:flex-row md:items-center md:justify-between"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-rose-100">
                      <ArrowDownRight className="h-5 w-5 text-rose-600" />
                    </div>
                    <div>
                      <p className="font-medium">
                        {order.credits_amount} credits refunded
                      </p>
                      <p className="text-sm text-gray-500">
                        Package {formatCreditPackageLabel(order.package_id)} - Ordered {formatDate(order.created_at)}
                      </p>
                      <p className="text-sm text-gray-500">
                        Refunded {order.refunded_at ? formatDate(order.refunded_at) : 'Pending refund timestamp'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className="font-semibold text-rose-700">
                        -{formatCurrency(order.price_cents / 100, 'USD')}
                      </p>
                      <p className="text-xs text-gray-500">Refunded payment amount</p>
                    </div>
                    <Badge className="bg-rose-100 text-rose-700">
                      {order.status}
                    </Badge>
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
            <Clock className="h-5 w-5 text-slate-700" />
            Credit Purchase Lifecycle
          </CardTitle>
          <CardDescription>
            Recent credit orders across completed, pending, canceled, expired, and refunded states.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {creditOrdersLoading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : creditOrders.length === 0 ? (
            <div className="rounded-lg border border-dashed p-6 text-center text-sm text-gray-500">
              No credit purchase orders have been recorded yet.
            </div>
          ) : (
            <>
              <div className="grid gap-3 md:grid-cols-5">
                <div className="rounded-lg border bg-slate-50 p-3">
                  <div className="text-xs text-gray-500">Completed</div>
                  <div className="mt-1 text-2xl font-semibold">{creditOrderCounts.completed || 0}</div>
                </div>
                <div className="rounded-lg border bg-amber-50 p-3">
                  <div className="text-xs text-amber-700">Pending</div>
                  <div className="mt-1 text-2xl font-semibold text-amber-900">{creditOrderCounts.pending || 0}</div>
                </div>
                <div className="rounded-lg border bg-gray-50 p-3">
                  <div className="text-xs text-gray-600">Canceled</div>
                  <div className="mt-1 text-2xl font-semibold text-gray-900">{creditOrderCounts.canceled || 0}</div>
                </div>
                <div className="rounded-lg border bg-gray-50 p-3">
                  <div className="text-xs text-gray-600">Expired</div>
                  <div className="mt-1 text-2xl font-semibold text-gray-900">{creditOrderCounts.expired || 0}</div>
                </div>
                <div className="rounded-lg border bg-rose-50 p-3">
                  <div className="text-xs text-rose-700">Refunded</div>
                  <div className="mt-1 text-2xl font-semibold text-rose-900">{creditOrderCounts.refunded || 0}</div>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex flex-col gap-3 rounded-lg border bg-slate-50/60 p-4 md:flex-row md:items-center md:justify-between">
                  <div className="flex items-center gap-2 text-sm text-slate-600">
                    <Filter className="h-4 w-4" />
                    Filter recent credit orders
                  </div>
                  <div className="flex flex-col gap-3 md:flex-row md:items-center">
                    <div className="flex flex-wrap gap-2">
                      {['all', 'completed', 'pending', 'canceled', 'expired', 'refunded'].map((status) => (
                        <Button
                          key={status}
                          type="button"
                          size="sm"
                          variant={creditOrderStatusFilter === status ? 'default' : 'outline'}
                          onClick={() => setCreditOrderStatusFilter(status)}
                          className="capitalize"
                        >
                          {status === 'all' ? 'All statuses' : status}
                        </Button>
                      ))}
                    </div>
                    <Input
                      value={creditOrderSearch}
                      onChange={(event) => setCreditOrderSearch(event.target.value)}
                      placeholder="Search package, status, or credits"
                      className="w-full md:w-72"
                    />
                  </div>
                </div>
                {filteredCreditOrders.length === 0 ? (
                  <div className="rounded-lg border border-dashed p-6 text-center text-sm text-gray-500">
                    No credit orders match the current filters.
                  </div>
                ) : filteredCreditOrders.map((order) => (
                  <div
                    key={order.id}
                    className="flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <p className="font-medium">
                        {order.credits_amount} credits - ${(order.price_cents / 100).toFixed(2)}
                      </p>
                      <p className="text-sm text-gray-500">
                        Package {formatCreditPackageLabel(order.package_id)} - Ordered {formatDate(order.created_at)}
                      </p>
                      <p className="text-xs text-gray-500">
                        {order.status === 'completed' && order.completed_at
                          ? `Completed ${formatDate(order.completed_at)}`
                          : order.status === 'refunded' && order.refunded_at
                            ? `Refunded ${formatDate(order.refunded_at)}`
                            : order.status === 'pending'
                              ? 'Still waiting for payment confirmation'
                              : order.status === 'expired'
                                ? 'Checkout expired before payment completed'
                                : order.status === 'canceled'
                                  ? 'Customer canceled before payment completed'
                                  : `Status: ${order.status}`}
                      </p>
                    </div>
                    <Badge
                      className={
                        order.status === 'completed'
                          ? 'bg-green-100 text-green-700'
                          : order.status === 'pending'
                            ? 'bg-amber-100 text-amber-700'
                            : order.status === 'refunded'
                              ? 'bg-rose-100 text-rose-700'
                              : 'bg-gray-100 text-gray-700'
                      }
                    >
                      {order.status}
                    </Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedCreditOrder(order);
                        setShowCreditOrderDetail(true);
                      }}
                    >
                      View details
                    </Button>
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>
        </div>
      </details>

      <Dialog open={showCreditOrderDetail} onOpenChange={setShowCreditOrderDetail}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Credit Order Details</DialogTitle>
            <DialogDescription>
              Review the full lifecycle, Stripe references, and timestamps for this credit purchase.
            </DialogDescription>
          </DialogHeader>
          {selectedCreditOrder ? (
            <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border bg-slate-50 p-4">
                  <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Package</div>
                  <div className="mt-2 font-semibold">{formatCreditPackageLabel(selectedCreditOrder.package_id)}</div>
                  <div className="mt-1 text-sm text-gray-500">
                    {selectedCreditOrder.credits_amount} credits
                  </div>
                </div>
                <div className="rounded-lg border bg-slate-50 p-4">
                  <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Status</div>
                  <div className="mt-2 flex items-center gap-2">
                    <Badge
                      className={
                        selectedCreditOrder.status === 'completed'
                          ? 'bg-green-100 text-green-700'
                          : selectedCreditOrder.status === 'pending'
                            ? 'bg-amber-100 text-amber-700'
                            : selectedCreditOrder.status === 'refunded'
                              ? 'bg-rose-100 text-rose-700'
                              : 'bg-gray-100 text-gray-700'
                      }
                    >
                      {formatCreditOrderStatus(selectedCreditOrder.status)}
                    </Badge>
                  </div>
                  <div className="mt-1 text-sm text-gray-500">
                    {formatCurrency(selectedCreditOrder.price_cents / 100, 'USD')}
                  </div>
                </div>
              </div>

              <div className="rounded-lg border p-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Created</div>
                    <div className="mt-1 text-sm">{formatDate(selectedCreditOrder.created_at)}</div>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Completed</div>
                    <div className="mt-1 text-sm">
                      {selectedCreditOrder.completed_at ? formatDate(selectedCreditOrder.completed_at) : 'Not completed'}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Refunded</div>
                    <div className="mt-1 text-sm">
                      {selectedCreditOrder.refunded_at ? formatDate(selectedCreditOrder.refunded_at) : 'No refund recorded'}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Order ID</div>
                    <div className="mt-1 break-all font-mono text-xs text-gray-600">{selectedCreditOrder.id}</div>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border p-4">
                <div className="space-y-3">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Stripe checkout session</div>
                    <div className="mt-1 break-all font-mono text-xs text-gray-600">
                      {selectedCreditOrder.stripe_session_id || 'Not recorded'}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Stripe payment intent</div>
                    <div className="mt-1 break-all font-mono text-xs text-gray-600">
                      {selectedCreditOrder.stripe_payment_intent_id || 'Not available yet'}
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border bg-slate-50 p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">
                      Refund and dispute operations
                    </div>
                    <p className="mt-1 text-sm text-gray-600">
                      Open the related workflow and use the Stripe references above to find the exact payment quickly.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => handleCopyStripeRefs(selectedCreditOrder)}
                    >
                      <Copy className="mr-2 h-4 w-4" />
                      Copy Stripe refs
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => window.open('/admin/disputes', '_blank', 'noopener,noreferrer')}
                    >
                      <ExternalLink className="mr-2 h-4 w-4" />
                      Open dispute operations
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => window.open('/dashboard/usage', '_blank', 'noopener,noreferrer')}
                    >
                      <ExternalLink className="mr-2 h-4 w-4" />
                      Open refund history
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreditOrderDetail(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Tabs for Invoices and Payment Methods */}
      <Tabs defaultValue="invoices" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="invoices" className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Invoices
          </TabsTrigger>
          <TabsTrigger value="methods" className="flex items-center gap-2">
            <CreditCard className="w-4 h-4" />
            Payment Methods
          </TabsTrigger>
          <TabsTrigger value="audit" className="flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Audit Trail
          </TabsTrigger>
        </TabsList>

        {/* Invoices Tab */}
        <TabsContent value="invoices">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="w-5 h-5" />
                    Invoice History
                  </CardTitle>
                  <CardDescription>Issued invoices and downloadable PDFs.</CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={handleExportCSV}>
                  <Download className="w-4 h-4 mr-2" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {invoicesLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : invoices.length === 0 ? (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                  <p className="text-gray-500">No invoices yet.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {invoices.map((invoice) => (
                    <div
                      key={invoice.id}
                      className="flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                          <FileText className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <p className="font-medium">
                            {invoice.number || `INV-${invoice.id.slice(0, 8)}`}
                          </p>
                          <div className="flex items-center gap-2 text-sm text-gray-500">
                            <Calendar className="w-3.5 h-3.5" />
                            {formatDate(invoice.created_at)}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <p className="font-bold text-lg">
                            {formatCurrency(invoice.amount, invoice.currency)}
                          </p>
                          <Badge className={
                            invoice.status === 'paid' ? 'bg-green-100 text-green-700' :
                            invoice.status === 'open' ? 'bg-yellow-100 text-yellow-700' :
                            invoice.status === 'void' ? 'bg-gray-100 text-gray-700' :
                            'bg-red-100 text-red-700'
                          }>
                            {invoice.status === 'paid' ? 'Paid' :
                             invoice.status === 'open' ? 'Open' :
                             invoice.status === 'void' ? 'Voided' : invoice.status}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDownloadInvoicePdf(invoice.id)}
                            title="Download PDF"
                          >
                            <Download className="w-4 h-4" />
                          </Button>
                          {invoice.hosted_url && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => window.open(invoice.hosted_url!, '_blank')}
                              title="Open hosted invoice"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleResendInvoice(invoice.id)}
                            title="Resend invoice email"
                          >
                            <Mail className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Payment Methods Tab */}
        <TabsContent value="methods">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <CreditCard className="w-5 h-5" />
                    Payment Methods
                  </CardTitle>
                  <CardDescription>Saved cards and billing methods.</CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={handleManageBilling}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add payment method
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {paymentMethodsLoading ? (
                <div className="space-y-3">
                  {[1, 2].map((i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : paymentMethods.length === 0 ? (
                <div className="text-center py-12">
                  <CreditCard className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                  <p className="text-gray-500">No payment methods saved yet.</p>
                  <Button className="mt-4" onClick={handleManageBilling}>
                    <Plus className="w-4 h-4 mr-2" />
                    Add payment method
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {paymentMethods.map((method) => (
                    <div
                      key={method.id}
                      className={`flex items-center justify-between p-4 rounded-lg transition-colors ${
                        method.is_default ? 'bg-violet-50 border border-violet-200' : 'bg-gray-50 hover:bg-gray-100'
                      }`}
                    >
                      <div className="flex items-center gap-4">
                        <div className={`w-14 h-10 bg-gradient-to-r ${getCardBrandLogo(method.card.brand)} rounded-lg flex items-center justify-center`}>
                          <span className="text-white text-xs font-bold uppercase">
                            {method.card.brand}
                          </span>
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-medium">Ending in {method.card.last4}</p>
                            {method.is_default && (
                              <Badge className="bg-violet-100 text-violet-700">Default</Badge>
                            )}
                          </div>
                          <p className="text-sm text-gray-500">
                            Expires {method.card.exp_month.toString().padStart(2, '0')}/{method.card.exp_year}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {!method.is_default && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleSetDefaultPaymentMethod(method.id)}
                            disabled={settingDefault === method.id}
                          >
                            {settingDefault === method.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <>
                                <Check className="w-4 h-4 mr-1" />
                                Set as default
                              </>
                            )}
                          </Button>
                        )}
                        {method.is_default ? (
                          <div className="rounded-md border border-dashed border-violet-200 bg-white px-3 py-2 text-xs text-violet-700">
                            Set another payment method as default before removing this one.
                          </div>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRemovePaymentMethod(method.id)}
                            disabled={removingPaymentMethod === method.id}
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                          >
                            {removingPaymentMethod === method.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audit">
          <BillingAuditTrail />
        </TabsContent>
      </Tabs>

      {/* Plan Change Preview Modal */}
      <Dialog open={showPreviewModal} onOpenChange={setShowPreviewModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Review plan change</DialogTitle>
            <DialogDescription>Check the live proration details before confirming.</DialogDescription>
          </DialogHeader>

          {previewLoading ? (
            <div className="py-8 flex items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin text-violet-600" />
            </div>
          ) : previewData && (
            <div className="space-y-4">
              <div className="p-4 bg-gray-50 rounded-lg space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">Current plan</span>
                  <span className="font-medium">{previewData.current_plan.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">New plan</span>
                  <span className="font-medium text-violet-600">{previewData.new_plan.name}</span>
                </div>
                <Separator />
                <div className="flex justify-between">
                  <span className="text-gray-600">Current plan credit</span>
                  <span className="text-green-600">
                    +{formatUsdCents(previewData.proration.credit_applied || 0)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">New plan amount</span>
                  <span>{formatUsdCents(previewData.new_plan.price || 0)}</span>
                </div>
                <Separator />
                <div className="flex justify-between text-lg font-bold">
                  <span>Amount due today</span>
                  <span className={previewData.proration.amount_due_now > 0 ? 'text-violet-600' : 'text-green-600'}>
                    {formatUsdCents(Math.max(0, previewData.proration.amount_due_now || 0))}
                  </span>
                </div>
                {previewData.proration.credit_applied > 0 && (
                  <p className="text-sm text-green-600">
                    Credit applied automatically: {formatUsdCents(previewData.proration.credit_applied)}
                  </p>
                )}
              </div>

              {previewData.proration.next_invoice_date ? (
                <div className="rounded-lg border p-4 text-sm text-gray-700">
                  <p className="font-medium">Next invoice</p>
                  <p className="mt-1">
                    {formatUsdCents(previewData.proration.next_invoice_amount || 0)} on{' '}
                    {formatDate(previewData.proration.next_invoice_date)}
                  </p>
                </div>
              ) : null}

              {previewData.preview_line_items.length > 0 ? (
                <div className="rounded-lg border p-4">
                  <p className="text-sm font-medium text-gray-900">Preview line items</p>
                  <div className="mt-3 space-y-2">
                    {previewData.preview_line_items.map((item, index) => (
                      <div key={`${item.description}-${index}`} className="flex items-start justify-between gap-4 text-sm">
                        <div>
                          <p className="text-gray-900">{item.description}</p>
                          <p className="text-xs text-gray-500">
                            {formatDate(item.period_start)} - {formatDate(item.period_end)}
                          </p>
                        </div>
                        <span className={item.amount < 0 ? 'text-green-600' : 'text-gray-700'}>
                          {item.amount < 0 ? '-' : ''}
                          {formatUsdCents(Math.abs(item.amount))}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              <p className="text-sm text-gray-500">
                * Proration applies the unused value from your current billing period to the new plan automatically.
              </p>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPreviewModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleConfirmPlanChange}
              disabled={isChangingPlan || previewLoading}
              className="bg-gradient-to-r from-violet-600 to-indigo-600"
            >
              {isChangingPlan ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : null}
              Confirm change
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
