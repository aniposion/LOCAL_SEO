'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import {
  AlertTriangle,
  CheckCircle,
  DollarSign,
  FileText,
  Info,
  Loader2,
  Package,
  RefreshCw,
  Send,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { adminApi } from '@/lib/api';
import { getApiErrorMessage, getApiErrorStatus } from '@/lib/api-errors';
import { toast } from 'sonner';

interface CreditRefund {
  id: string;
  payment_id: string;
  user_id: string;
  user_email: string;
  amount: number;
  reason: string;
  status: string;
  package_id?: string;
  credits_amount?: number;
  created_at: string;
  processed_at?: string;
}

interface Dispute {
  id: string;
  user_id: string;
  user_email: string;
  payment_id: string;
  amount: number;
  reason: string;
  status: string;
  evidence?: string;
  created_at: string;
  evidence_due_by?: string;
  source?: string;
}

interface DisputeListPayload {
  disputes: Dispute[];
  stripe_available: boolean;
  data_source: string;
  warning?: string | null;
}

interface EvidenceTemplateOption {
  id: string;
  label: string;
  description: string;
}

interface IndustryEvidenceOption {
  id: string;
  label: string;
  guidance: string;
}

function suggestTemplateForReason(reason?: string) {
  const normalized = (reason || '').toLowerCase();
  if (normalized.includes('duplicate')) return 'duplicate-charge';
  if (
    normalized.includes('canceled') ||
    normalized.includes('cancelled') ||
    normalized.includes('subscription') ||
    normalized.includes('refund')
  ) {
    return 'cancellation-policy';
  }
  if (
    normalized.includes('fraud') ||
    normalized.includes('unrecognized') ||
    normalized.includes('not_received')
  ) {
    return 'customer-communication';
  }
  return 'service-delivered';
}

const EVIDENCE_TEMPLATES: EvidenceTemplateOption[] = [
  {
    id: 'service-delivered',
    label: 'Service delivered',
    description: 'Use when the customer completed the purchase and the service or access was delivered.',
  },
  {
    id: 'cancellation-policy',
    label: 'Cancellation policy',
    description: 'Use when the charge followed an accepted cancellation or refund policy.',
  },
  {
    id: 'duplicate-charge',
    label: 'Duplicate charge clarification',
    description: 'Use when a duplicate concern was already resolved or no duplicate exists.',
  },
  {
    id: 'customer-communication',
    label: 'Customer communication',
    description: 'Use when you have email, SMS, or support records showing the issue was addressed.',
  },
];

const INDUSTRY_EVIDENCE_OPTIONS: IndustryEvidenceOption[] = [
  {
    id: 'general-local',
    label: 'General local business',
    guidance: 'Use for standard service delivery, fulfillment, and customer communication records.',
  },
  {
    id: 'home-services',
    label: 'Home services',
    guidance: 'Best for scheduled visits, dispatch notes, and completion confirmation.',
  },
  {
    id: 'clinic-spa',
    label: 'Clinic or med spa',
    guidance: 'Best for consultations, scheduled treatments, and intake confirmation.',
  },
  {
    id: 'restaurant-hospitality',
    label: 'Restaurant or hospitality',
    guidance: 'Best for reservations, order fulfillment, and guest communication history.',
  },
];

function buildIndustryEvidenceBlock(industryId: string) {
  switch (industryId) {
    case 'home-services':
      return [
        '',
        'Industry details to include:',
        '- Scheduled service date and arrival window',
        '- Technician or crew dispatch confirmation',
        '- Completion notes, photos, or signed service confirmation if available',
      ].join('\n');
    case 'clinic-spa':
      return [
        '',
        'Industry details to include:',
        '- Consultation or treatment booking confirmation',
        '- Intake, consent, or scheduling acknowledgement if applicable',
        '- Delivery timestamp and any follow-up communication',
      ].join('\n');
    case 'restaurant-hospitality':
      return [
        '',
        'Industry details to include:',
        '- Reservation, order, or booking confirmation',
        '- Fulfillment timing or service completion details',
        '- Any recovery or guest communication before the dispute',
      ].join('\n');
    default:
      return [
        '',
        'Industry details to include:',
        '- How the customer confirmed the purchase',
        '- What was delivered and when',
        '- Any follow-up communication, usage, or service confirmation',
      ].join('\n');
  }
}

function buildEvidenceTemplate(templateId: string, dispute: Dispute | null, industryId: string) {
  const customer = dispute?.user_email || 'the customer';
  const amount = dispute ? `$${dispute.amount.toFixed(2)}` : 'the disputed amount';
  const paymentId = dispute?.payment_id || 'the payment reference';
  const industryBlock = buildIndustryEvidenceBlock(industryId);

  const footer = [
    '',
    'Supporting details to complete before sending:',
    `- Customer reference: ${customer}`,
    `- Payment reference: ${paymentId}`,
    `- Amount disputed: ${amount}`,
    '- Timeline: [purchase date, delivery date, and any follow-up dates]',
    '- Supporting proof attached or available: [invoice, usage log, policy text, or communication record]',
  ].join('\n');

  switch (templateId) {
    case 'service-delivered':
      return [
        'The customer authorized this purchase and the service was delivered as described.',
        '',
        'Summary:',
        '- The customer completed the purchase flow successfully.',
        '- Our records show the service, access, or deliverable was made available after payment.',
        '- Internal usage, fulfillment, or delivery records support this timeline.',
        industryBlock,
        footer,
      ].join('\n');
    case 'cancellation-policy':
      return [
        'The disputed charge followed the cancellation and refund terms accepted at the time of purchase.',
        '',
        'Summary:',
        '- The customer completed the purchase while the policy was visible.',
        '- The refund request falls outside the stated refund window or policy conditions.',
        '- We can provide the exact policy text and the timeline relevant to this charge.',
        industryBlock,
        footer,
      ].join('\n');
    case 'duplicate-charge':
      return [
        'This charge does not appear to be an unresolved duplicate.',
        '',
        'Summary:',
        '- Related payment records were reviewed for the customer.',
        '- Any mistaken charge was already refunded, or no second charge exists for the same purchase.',
        '- We can provide the relevant payment references showing the final resolved state.',
        industryBlock,
        footer,
      ].join('\n');
    default:
      return [
        'The customer completed the purchase and our records show communication after payment about the service.',
        '',
        'Summary:',
        '- The customer received confirmation or follow-up communication after purchase.',
        '- Our team attempted to address the issue directly before the dispute was filed.',
        '- Relevant email, SMS, or support history can be provided as supporting evidence.',
        industryBlock,
        footer,
      ].join('\n');
  }
}

function formatDate(value?: string) {
  if (!value) return 'Pending';
  return new Date(value).toLocaleDateString();
}

function getStatusBadge(status: string) {
  const styles: Record<string, string> = {
    completed: 'bg-green-100 text-green-700',
    refunded: 'bg-green-100 text-green-700',
    pending: 'bg-yellow-100 text-yellow-700',
    under_review: 'bg-orange-100 text-orange-700',
    warning_needs_response: 'bg-amber-100 text-amber-700',
    needs_response: 'bg-amber-100 text-amber-700',
    warning_closed: 'bg-gray-100 text-gray-700',
    accepted: 'bg-green-100 text-green-700',
    canceled: 'bg-gray-100 text-gray-700',
    expired: 'bg-gray-100 text-gray-700',
  };

  return <Badge className={styles[status] || 'bg-gray-100 text-gray-700'}>{status.replace(/_/g, ' ')}</Badge>;
}

export default function DisputesPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [refunds, setRefunds] = useState<CreditRefund[]>([]);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [disputesUnavailable, setDisputesUnavailable] = useState<string | null>(null);
  const [disputeWarning, setDisputeWarning] = useState<string | null>(null);
  const [stripeAvailable, setStripeAvailable] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [isRefundDialogOpen, setIsRefundDialogOpen] = useState(false);
  const [refundPaymentId, setRefundPaymentId] = useState('');
  const [refundReason, setRefundReason] = useState('');
  const [isProcessingRefund, setIsProcessingRefund] = useState(false);

  const [isRespondDialogOpen, setIsRespondDialogOpen] = useState(false);
  const [selectedDispute, setSelectedDispute] = useState<Dispute | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState('service-delivered');
  const [selectedIndustryId, setSelectedIndustryId] = useState('general-local');
  const [selectedProofChecklist, setSelectedProofChecklist] = useState<string[]>([]);
  const [attachmentFiles, setAttachmentFiles] = useState<File[]>([]);
  const [attachmentNote, setAttachmentNote] = useState('');
  const [evidence, setEvidence] = useState('');

  const [isAccepting, setIsAccepting] = useState<string | null>(null);

  useEffect(() => {
    void fetchData();
  }, []);

  const fetchData = async () => {
    setIsLoading(true);

    try {
      const refundsRes = await adminApi.getRefunds();
      setRefunds(refundsRes.data.refunds || []);
    } catch (error) {
      console.error('Failed to fetch refunds:', error);
      toast.error('Failed to load refund data');
      setRefunds([]);
    }

    try {
      const disputesRes = await adminApi.getDisputes();
      const disputePayload = disputesRes.data as DisputeListPayload;
      setDisputes(disputePayload.disputes || []);
      setStripeAvailable(disputePayload.stripe_available ?? true);
      setDisputeWarning(disputePayload.warning || null);
      setDisputesUnavailable(null);
    } catch (error) {
      const detail = getApiErrorMessage(error, 'Failed to load disputes.');
      const status = getApiErrorStatus(error);
      setStripeAvailable(false);
      setDisputeWarning(null);
      if (status === 503) {
        setDisputesUnavailable(detail || 'Dispute management requires Stripe to be configured.');
      } else {
        setDisputesUnavailable(detail || 'Failed to load disputes.');
      }
      setDisputes([]);
    }

    setIsLoading(false);
  };

  const handleProcessRefund = async () => {
    if (!refundPaymentId.trim() || !refundReason.trim()) {
      toast.error('Payment ID and reason are required');
      return;
    }

    setIsProcessingRefund(true);
    try {
      const res = await adminApi.processRefund(refundPaymentId.trim(), null, refundReason.trim());
      const data = res.data;
      if (data.stripe_error) {
        toast.warning(
          `Credits clawed back but Stripe refund failed: ${data.stripe_error}. Issue the payment refund manually.`
        );
      } else {
        toast.success(
          `Refund processed - ${data.credits_deducted ?? '?'} credits deducted` +
            (data.stripe_refund_id ? ` | Stripe refund ${data.stripe_refund_id}` : '')
        );
      }
      setIsRefundDialogOpen(false);
      setRefundPaymentId('');
      setRefundReason('');
      await fetchData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to process refund'));
    } finally {
      setIsProcessingRefund(false);
    }
  };

  const openRespondDialog = (dispute: Dispute, templateId?: string) => {
    const resolvedTemplateId = templateId || suggestTemplateForReason(dispute.reason);
    setSelectedDispute(dispute);
    setSelectedTemplateId(resolvedTemplateId);
    setSelectedIndustryId('general-local');
    setSelectedProofChecklist([]);
    setAttachmentFiles([]);
    setAttachmentNote('');
    setEvidence(buildEvidenceTemplate(resolvedTemplateId, dispute, 'general-local'));
    setIsRespondDialogOpen(true);
  };

  const toggleProofChecklist = (item: string) => {
    setSelectedProofChecklist((prev) =>
      prev.includes(item) ? prev.filter((existing) => existing !== item) : [...prev, item]
    );
  };

  const handleRespondToDispute = async () => {
    if (!selectedDispute || !evidence.trim()) {
      toast.error('Please provide evidence');
      return;
    }
    if (evidence.trim().length < 40) {
      toast.error('Please provide a fuller evidence summary before submitting');
      return;
    }

    setIsSubmitting(true);
    try {
      const uploadedAttachmentUrls: string[] = [];
      if (attachmentFiles.length > 0) {
        for (const file of attachmentFiles) {
          const uploadResponse = await adminApi.uploadDisputeAttachment(file);
          uploadedAttachmentUrls.push(uploadResponse.data.url);
        }
      }

      const res = await adminApi.respondToDispute(selectedDispute.id, {
        evidence,
        proof_checklist: selectedProofChecklist,
        attachment_names: attachmentFiles.map((file) => file.name),
        attachment_urls: uploadedAttachmentUrls,
        attachment_note: attachmentNote.trim() || undefined,
      });
      toast.success(res.data.message || 'Evidence submitted successfully');
      setIsRespondDialogOpen(false);
      setSelectedDispute(null);
      setSelectedProofChecklist([]);
      setAttachmentFiles([]);
      setAttachmentNote('');
      setEvidence('');
      await fetchData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to submit evidence'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAcceptDispute = async (dispute: Dispute) => {
    if (!window.confirm(`Accept dispute for ${dispute.user_email || dispute.payment_id}? This will refund the customer.`)) {
      return;
    }

    setIsAccepting(dispute.id);
    try {
      const res = await adminApi.acceptDispute(dispute.id);
      toast.success(res.data.message || 'Dispute accepted');
      await fetchData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to accept dispute'));
    } finally {
      setIsAccepting(null);
    }
  };

  const totalRefundedAmount = refunds.reduce((sum, refund) => sum + refund.amount, 0);
  const actionableDisputeCount = disputes.filter((dispute) =>
    ['needs_response', 'warning_needs_response', 'under_review'].includes(dispute.status)
  ).length;
  const needsOperatorActionCount = disputes.filter((dispute) =>
    ['needs_response', 'warning_needs_response'].includes(dispute.status)
  ).length;
  const completedRefundCount = refunds.filter((refund) => refund.status === 'refunded').length;

  const checklistItems = useMemo(
    () => [
      'Confirm the dispute status is still actionable before responding.',
      'Build one short timeline: purchase, delivery, and follow-up.',
      'Reference only facts you can prove with logs, policy text, or communication records.',
      'Accept only when you intend to concede the charge and refund the customer.',
    ],
    []
  );

  const proofChecklistOptions = useMemo(
    () => [
      'Purchase authorization',
      'Delivery or fulfillment log',
      'Usage or access log',
      'Policy or cancellation terms',
      'Customer communication record',
      'Refund or resolution timeline',
    ],
    []
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="mb-2 h-8 w-16" />
                <Skeleton className="h-4 w-24" />
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
          <h1 className="text-2xl font-bold">Disputes &amp; Refunds</h1>
          <p className="text-gray-500">Handle charge disputes carefully and review refunded credit purchases.</p>
        </div>
        <Button variant="outline" onClick={() => setIsRefundDialogOpen(true)}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Process Refund
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
              <span className="text-3xl font-bold text-orange-600">{disputesUnavailable ? 0 : actionableDisputeCount}</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Active Disputes</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5 text-blue-500" />
              <span className="text-3xl font-bold">{completedRefundCount}</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Completed Refunds</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-red-500" />
              <span className="text-3xl font-bold text-red-600">${totalRefundedAmount.toFixed(2)}</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Total Refunded</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="refunds">
        <TabsList>
          <TabsTrigger value="refunds">
            <RefreshCw className="mr-2 h-4 w-4" />
            Credit Refunds ({refunds.length})
          </TabsTrigger>
          <TabsTrigger value="disputes">
            <AlertTriangle className="mr-2 h-4 w-4" />
            Disputes ({disputesUnavailable ? 0 : disputes.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="refunds" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Credit Purchase Refunds</CardTitle>
              <CardDescription>
                Credit purchase orders that were refunded and clawed back from customer balances.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {refunds.length > 0 ? (
                <div className="space-y-4">
                  {refunds.map((refund) => (
                    <div key={refund.id} className="rounded-lg border p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{refund.user_email}</span>
                            {getStatusBadge(refund.status)}
                          </div>
                          <p className="text-sm text-gray-500">
                            Payment: {refund.payment_id || 'Unavailable'} ? ${refund.amount.toFixed(2)}
                          </p>
                          {refund.package_id ? (
                            <p className="flex items-center gap-1 text-sm text-gray-500">
                              <Package className="h-3 w-3" />
                              {refund.package_id} ? {refund.credits_amount} credits
                            </p>
                          ) : null}
                          <p className="text-sm">Reason: {refund.reason}</p>
                          <p className="text-xs text-gray-400">Processed: {formatDate(refund.processed_at)}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 text-center">
                  <DollarSign className="mx-auto mb-4 h-12 w-12 text-gray-300" />
                  <p className="text-gray-500">No credit purchase refunds on record</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="disputes" className="mt-6 space-y-4">
          {!disputesUnavailable ? (
            <Card className="border-slate-200 bg-slate-50">
              <CardContent className="pt-6">
                <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-900">
                  <ShieldAlert className="h-4 w-4 text-slate-700" />
                  Operator checklist before you respond
                </div>
                <ul className="space-y-1 text-sm text-slate-700">
                  {checklistItems.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>Payment Disputes</CardTitle>
              <CardDescription>Disputes filed by customers or issuing banks through Stripe.</CardDescription>
            </CardHeader>
            <CardContent>
              {disputesUnavailable ? (
                <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
                  <Info className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                  <div>
                    <p className="font-medium text-amber-800">Disputes unavailable</p>
                    <p className="mt-1 text-sm text-amber-700">{disputesUnavailable}</p>
                    <p className="mt-2 text-sm text-amber-600">
                      Configure Stripe fully before handling disputes here. Until then, use the Stripe Dashboard.
                    </p>
                  </div>
                </div>
              ) : disputeWarning ? (
                <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
                  <Info className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                  <div>
                    <p className="font-medium text-amber-800">
                      {stripeAvailable ? 'Stripe warning' : 'Local dispute ledger only'}
                    </p>
                    <p className="mt-1 text-sm text-amber-700">{disputeWarning}</p>
                    {!stripeAvailable ? (
                      <p className="mt-2 text-sm text-amber-600">
                        You can still review the persisted dispute ledger here, but respond and accept actions stay disabled until Stripe is connected.
                      </p>
                    ) : null}
                  </div>
                </div>
              ) : disputes.length > 0 ? (
                <div className="space-y-4">
                  {disputes.map((dispute) => (
                    <div key={dispute.id} className="rounded-lg border p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{dispute.user_email || dispute.payment_id}</span>
                            {getStatusBadge(dispute.status)}
                            {!stripeAvailable ? <Badge variant="outline">Local cache</Badge> : null}
                          </div>
                          <p className="text-sm text-gray-500">Payment: {dispute.payment_id} ? ${dispute.amount.toFixed(2)}</p>
                          <p className="text-sm">Reason: {dispute.reason}</p>
                          <p className="text-xs text-gray-400">Filed: {formatDate(dispute.created_at)}</p>
                          {dispute.evidence_due_by ? (
                            <p className="text-xs text-gray-400">Evidence due: {formatDate(dispute.evidence_due_by)}</p>
                          ) : null}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {(dispute.status === 'needs_response' || dispute.status === 'warning_needs_response') ? (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => openRespondDialog(dispute)}
                                disabled={!stripeAvailable}
                              >
                                <FileText className="mr-1 h-4 w-4" />
                                Respond
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                disabled={!stripeAvailable || isAccepting === dispute.id}
                                onClick={() => handleAcceptDispute(dispute)}
                              >
                                {isAccepting === dispute.id ? (
                                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                                ) : (
                                  <XCircle className="mr-1 h-4 w-4" />
                                )}
                                Accept
                              </Button>
                            </>
                          ) : (
                            <Badge variant="secondary">No operator action available</Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 text-center">
                  <CheckCircle className="mx-auto mb-4 h-12 w-12 text-green-300" />
                  <p className="text-gray-500">No active disputes</p>
                </div>
              )}
            </CardContent>
          </Card>

          {!disputesUnavailable && needsOperatorActionCount > 0 ? (
            <Card className="border-amber-200 bg-amber-50">
              <CardContent className="pt-6 text-sm text-amber-900">
                {needsOperatorActionCount} dispute{needsOperatorActionCount === 1 ? '' : 's'} still need a decision.
                {stripeAvailable
                  ? ' Respond when you have evidence. Accept only when you want to concede and refund the customer.'
                  : ' Connect Stripe before responding or accepting those disputes from this workspace.'}
              </CardContent>
            </Card>
          ) : null}
        </TabsContent>
      </Tabs>

      <Dialog open={isRefundDialogOpen} onOpenChange={setIsRefundDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Process Credit Purchase Refund</DialogTitle>
            <DialogDescription>
              Enter the Stripe payment-intent ID for the completed credit purchase. Credits will be clawed back first,
              then a Stripe refund will be attempted if Stripe is configured.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Stripe Payment-Intent ID</label>
              <Input placeholder="pi_..." value={refundPaymentId} onChange={(e) => setRefundPaymentId(e.target.value)} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Reason</label>
              <Input placeholder="Customer request, duplicate charge, or admin correction" value={refundReason} onChange={(e) => setRefundReason(e.target.value)} />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsRefundDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleProcessRefund} disabled={isProcessingRefund}>
              {isProcessingRefund ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Process Refund
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={isRespondDialogOpen}
        onOpenChange={(open) => {
          setIsRespondDialogOpen(open);
          if (!open) {
            setSelectedDispute(null);
            setSelectedIndustryId('general-local');
            setSelectedProofChecklist([]);
            setAttachmentFiles([]);
            setAttachmentNote('');
            setEvidence('');
          }
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Respond to Dispute</DialogTitle>
            <DialogDescription>
              Submit factual evidence to Stripe. Pick a template, customize it, then send one clear summary.
            </DialogDescription>
          </DialogHeader>

          {selectedDispute ? (
            <div className="space-y-4">
              <div className="rounded-lg bg-gray-50 p-3">
                <p className="font-medium">{selectedDispute.user_email || selectedDispute.payment_id}</p>
                <p className="text-sm text-gray-500">Amount: ${selectedDispute.amount.toFixed(2)}</p>
                <p className="text-sm">Reason: {selectedDispute.reason}</p>
              </div>

              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                Focus on what you can prove: purchase authorization, delivery, usage, policy acceptance, and communication history.
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <label className="text-sm font-medium">Evidence template</label>
                  <Badge variant="outline" className="text-xs">
                    Recommended:{' '}
                    {EVIDENCE_TEMPLATES.find(
                      (template) => template.id === suggestTemplateForReason(selectedDispute.reason)
                    )?.label || 'Service delivered'}
                  </Badge>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  {EVIDENCE_TEMPLATES.map((template) => (
                    <button
                      key={template.id}
                      type="button"
                      onClick={() => {
                        setSelectedTemplateId(template.id);
                        setEvidence(buildEvidenceTemplate(template.id, selectedDispute, selectedIndustryId));
                      }}
                      className={`rounded-lg border p-3 text-left text-sm transition-colors ${
                        selectedTemplateId === template.id
                          ? 'border-violet-300 bg-violet-50'
                          : 'border-slate-200 bg-white hover:bg-slate-50'
                      }`}
                    >
                      <div className="font-medium text-slate-900">{template.label}</div>
                      <div className="mt-1 text-slate-500">{template.description}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <label className="text-sm font-medium">Business context</label>
                  <Badge variant="outline" className="text-xs">
                    Tailor the evidence for the business type
                  </Badge>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  {INDUSTRY_EVIDENCE_OPTIONS.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => {
                        setSelectedIndustryId(option.id);
                        setEvidence(buildEvidenceTemplate(selectedTemplateId, selectedDispute, option.id));
                      }}
                      className={`rounded-lg border p-3 text-left text-sm transition-colors ${
                        selectedIndustryId === option.id
                          ? 'border-violet-300 bg-violet-50'
                          : 'border-slate-200 bg-white hover:bg-slate-50'
                      }`}
                    >
                      <div className="font-medium text-slate-900">{option.label}</div>
                      <div className="mt-1 text-slate-500">{option.guidance}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <label className="text-sm font-medium">Proof checklist</label>
                  <Badge variant="outline" className="text-xs">
                    Added to the evidence summary
                  </Badge>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  {proofChecklistOptions.map((item) => {
                    const selected = selectedProofChecklist.includes(item);
                    return (
                      <button
                        key={item}
                        type="button"
                        onClick={() => toggleProofChecklist(item)}
                        className={`rounded-lg border p-3 text-left text-sm transition-colors ${
                          selected
                            ? 'border-violet-300 bg-violet-50'
                            : 'border-slate-200 bg-white hover:bg-slate-50'
                        }`}
                      >
                        <div className="font-medium text-slate-900">{item}</div>
                        <div className="mt-1 text-slate-500">
                          {selected ? 'Included in the dispute response.' : 'Click to include this proof item.'}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-3 rounded-lg border bg-slate-50/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <label className="text-sm font-medium">Attachment references</label>
                    <p className="mt-1 text-xs text-slate-500">
                      Files are uploaded to cloud storage when you submit. The dispute summary includes their stored links. Direct Stripe file upload is not wired yet.
                    </p>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    Honest reference only
                  </Badge>
                </div>
                <Input
                  type="file"
                  multiple
                  onChange={(event) => setAttachmentFiles(Array.from(event.target.files || []))}
                />
                {attachmentFiles.length > 0 ? (
                  <div className="space-y-2 rounded-lg border bg-white p-3 text-sm text-slate-600">
                    {attachmentFiles.map((file) => (
                      <div key={`${file.name}-${file.size}`} className="flex items-center justify-between gap-3">
                        <span className="truncate">{file.name}</span>
                        <span className="shrink-0 text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed bg-white p-3 text-sm text-slate-500">
                    No files selected yet. Add file names if you want them referenced in the dispute note.
                  </div>
                )}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Attachment note</label>
                  <textarea
                    className="h-24 w-full resize-none rounded-lg border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                    placeholder="Optional note about what the attachments show."
                    value={attachmentNote}
                    onChange={(e) => setAttachmentNote(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Evidence</label>
                <textarea
                  className="h-56 w-full resize-none rounded-lg border p-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="Describe the evidence supporting your case..."
                  value={evidence}
                  onChange={(e) => setEvidence(e.target.value)}
                />
                <div className="text-xs text-gray-500">
                  {evidence.trim().length} characters. Aim for a complete summary with dates, customer reference, and the proof you can provide.
                </div>
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsRespondDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleRespondToDispute} disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
              Submit Evidence
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
