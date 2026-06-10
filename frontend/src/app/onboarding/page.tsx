'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  Building2,
  CheckCircle,
  Clock3,
  Loader2,
  Mail,
  MapPin,
  Navigation,
  Phone,
  RefreshCw,
  Search,
  Sparkles,
  Star,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { onboardingApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { useAuthStore } from '@/store/auth';
import {
  useOnboardingStore,
  type OnboardingAuditRecommendation,
  type OnboardingAuditResult,
  type OnboardingSolutionPresentation,
  type OnboardingSolutionStep,
} from '@/store/onboarding';

type AuditStatusResponse = {
  audit_id: string;
  status: string;
  message: string;
  progress: number;
  needs_selection?: boolean;
  candidates?: Array<{
    place_id: string;
    name: string;
    address: string;
    rating?: number | null;
    review_count?: number | null;
  }>;
  result?: OnboardingAuditResult;
};

function normalizeAuditResult(result: unknown): OnboardingAuditResult | null {
  if (!result || typeof result !== 'object') {
    return null;
  }

  const data = result as Record<string, unknown>;
  const business = data.business as Record<string, unknown> | undefined;
  const scores = data.scores as Record<string, unknown> | undefined;
  const diagnosis = data.diagnosis as Record<string, unknown> | undefined;
  const estimatedLoss = data.estimated_loss as Record<string, unknown> | undefined;
  const recommendations = Array.isArray(data.recommendations)
    ? (data.recommendations as OnboardingAuditRecommendation[])
    : [];

  if (!business || !scores || !diagnosis || !estimatedLoss) {
    return null;
  }

  return {
    business: {
      name: typeof business.name === 'string' ? business.name : 'Your business',
      address: typeof business.address === 'string' ? business.address : '',
      category: typeof business.category === 'string' ? business.category : null,
      rating: typeof business.rating === 'number' ? business.rating : null,
      review_count: typeof business.review_count === 'number' ? business.review_count : null,
      photo_count: typeof business.photo_count === 'number' ? business.photo_count : null,
    },
    scores: {
      total: typeof scores.total === 'number' ? scores.total : 0,
      grade: typeof scores.grade === 'string' ? scores.grade : null,
      review: typeof scores.review === 'number' ? scores.review : 0,
      activity: typeof scores.activity === 'number' ? scores.activity : 0,
      completeness: typeof scores.completeness === 'number' ? scores.completeness : 0,
      competition: typeof scores.competition === 'number' ? scores.competition : 0,
    },
    diagnosis: {
      review_gap: typeof diagnosis.review_gap === 'number' ? diagnosis.review_gap : 0,
      days_since_post:
        typeof diagnosis.days_since_post === 'number' ? diagnosis.days_since_post : null,
      missing_info: Array.isArray(diagnosis.missing_info)
        ? diagnosis.missing_info.filter((item): item is string => typeof item === 'string')
        : [],
    },
    estimated_loss: {
      monthly_dollars:
        typeof estimatedLoss.monthly_dollars === 'number' ? estimatedLoss.monthly_dollars : null,
      missed_calls:
        typeof estimatedLoss.missed_calls === 'number' ? estimatedLoss.missed_calls : null,
    },
    summary: typeof data.summary === 'string' ? data.summary : '',
    recommendations,
    recommended_plan:
      typeof data.recommended_plan === 'string' ? data.recommended_plan : null,
  };
}

export default function OnboardingPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const {
    step,
    setStep,
    auditId,
    setAuditId,
    businessName,
    address,
    setBusinessInfo,
    candidates,
    setCandidates,
    auditResult,
    setAuditResult,
    solutionPresentation,
    setSolutionPresentation,
    setAnalyzing,
    analysisProgress,
    setAnalysisProgress,
  } = useOnboardingStore();

  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [flowError, setFlowError] = useState<string | null>(null);

  const isPublicFlow = !isAuthenticated;
  const stepTotal = 5;

  const buildAuditReviewUrl = () => {
    const params = new URLSearchParams();
    if (businessName) {
      params.set('subject', `Free audit review for ${businessName}`);
      params.set(
        'message',
        `Hi, I'd like to review the Google Maps audit for ${businessName} and talk through the recommended fix plan.`
      );
    }
    return `/contact?${params.toString()}`;
  };

  const buildDashboardHandoffUrl = (source: 'onboarding' | 'trial') => {
    const params = new URLSearchParams({
      source,
      setup: 'complete',
    });

    return `/dashboard?${params.toString()}`;
  };

  const submitAuditRequest = async (event: React.FormEvent) => {
    event.preventDefault();
    setFlowError(null);

    if (!businessName.trim() || !address.trim()) {
      toast.error('Please complete the required fields.');
      return;
    }

    if (isPublicFlow && !email.trim()) {
      toast.error('Please enter your email address.');
      return;
    }

    setIsLoading(true);

    try {
      const response = isPublicFlow
        ? await onboardingApi.requestFreeAudit(
            {
              business_name: businessName.trim(),
              address: address.trim(),
              phone: phone.trim() || undefined,
              website_url: websiteUrl.trim() || undefined,
            },
            email.trim()
          )
        : await onboardingApi.start({
            business_name: businessName.trim(),
            address: address.trim(),
            phone: phone.trim() || undefined,
            website_url: websiteUrl.trim() || undefined,
          });

      const nextAuditId = response.data.audit_id as string;
      setAuditId(nextAuditId);
      setStep(3);
      await startAnalysisPolling(nextAuditId);
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to start the audit');
      setFlowError(`${message} You can retry the audit or ask us to review the business manually.`);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectBusiness = async (placeId: string) => {
    if (!auditId) {
      return;
    }

    setIsLoading(true);
    setFlowError(null);

    try {
      if (isPublicFlow) {
        await onboardingApi.selectFreeAuditBusiness(auditId, placeId);
      } else {
        await onboardingApi.selectBusiness(auditId, placeId);
      }

      setStep(3);
      await startAnalysisPolling(auditId);
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to select this business');
      setFlowError(`${message} Choose another listing, retry the search, or contact us for a manual review.`);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const startAnalysisPolling = async (id: string) => {
    setAnalyzing(true);
    setFlowError(null);
    setAnalysisProgress(10);

    const progressSteps = [15, 28, 42, 58, 74, 88, 96];
    let progressIndex = 0;

    const progressInterval = setInterval(() => {
      if (progressIndex < progressSteps.length) {
        setAnalysisProgress(progressSteps[progressIndex]);
        progressIndex += 1;
      }
    }, 1400);

    const pollStatus = async (): Promise<void> => {
      try {
        const response = isPublicFlow
          ? await onboardingApi.getFreeAuditStatus(id)
          : await onboardingApi.getStatus(id);
        const data = response.data as AuditStatusResponse;

        if (data.needs_selection && data.candidates?.length) {
          clearInterval(progressInterval);
          setAnalyzing(false);
          setCandidates(data.candidates);
          setStep(2);
          return;
        }

        if (data.status === 'completed') {
          clearInterval(progressInterval);
          setAnalysisProgress(100);
          setAnalyzing(false);

          const fallbackResult = isPublicFlow ? null : (await onboardingApi.getResult()).data;
          const resolvedResult = normalizeAuditResult(data.result ?? fallbackResult);

          if (!resolvedResult) {
            throw new Error('Audit result payload is incomplete.');
          }

          setAuditResult(resolvedResult);
          setStep(4);
          return;
        }

        if (data.status === 'failed') {
          clearInterval(progressInterval);
          setAnalyzing(false);
          const message = data.message || 'The audit could not be completed.';
          setFlowError(`${message} We can still review the business manually from your contact request.`);
          toast.error(message);
          setStep(1);
          return;
        }

        window.setTimeout(() => {
          void pollStatus();
        }, 2000);
      } catch (error) {
        clearInterval(progressInterval);
        setAnalyzing(false);
        const message = getApiErrorMessage(error, 'Failed to get audit status');
        setFlowError(`${message} Retry the audit or send the details to sales so we can finish the review manually.`);
        toast.error(message);
      }
    };

    await pollStatus();
  };

  const handleViewSolution = async () => {
    if (!auditId) {
      return;
    }

    setIsLoading(true);
    setFlowError(null);

    try {
      const response = isPublicFlow
        ? await onboardingApi.getSolutionByAuditId(auditId, 'en')
        : await onboardingApi.getSolution('en');
      setSolutionPresentation(response.data as OnboardingSolutionPresentation);
      setStep(5);
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to load the fix plan');
      setFlowError(`${message} Your audit is still saved; contact us and include the audit id if this keeps happening.`);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartTrial = async () => {
    setIsLoading(true);
    setFlowError(null);

    try {
      await onboardingApi.startTrial();
      toast.success('Your free preview is active.');
      const dashboardUrl = buildDashboardHandoffUrl('trial');

      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(
          'onboarding_handoff',
          JSON.stringify({
            source: 'trial',
            setup: 'complete',
            audit_id: auditId,
            business_name: businessName,
            address,
            completed_at: new Date().toISOString(),
          })
        );
      }

      router.push(dashboardUrl);
    } catch {
      const dashboardUrl = buildDashboardHandoffUrl('onboarding');
      router.push(`/signup?redirect=${encodeURIComponent(dashboardUrl)}`);
    } finally {
      setIsLoading(false);
    }
  };

  const issueCount = auditResult
    ? [
        auditResult.diagnosis.review_gap > 0 ? 1 : 0,
        auditResult.diagnosis.missing_info.length > 0 ? 1 : 0,
        auditResult.recommendations.length,
      ].reduce((sum, value) => sum + value, 0)
    : 0;

  const topRecommendations = (auditResult?.recommendations ?? []).slice(0, 3);
  const missingInfoLabels = auditResult?.diagnosis.missing_info
    .map((item) => item.replace(/_/g, ' '))
    .join(', ');

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      <header className="border-b bg-white/80 backdrop-blur-md">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-cyan-500">
              <MapPin className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-xl">Local SEO Optimizer</span>
          </Link>
          <div className="flex items-center gap-3 text-sm text-gray-500">
            <span>
              Step {step} of {stepTotal}
            </span>
            <Progress value={(step / stepTotal) * 100} className="h-2 w-24" />
          </div>
        </div>
      </header>

      <main className="container mx-auto max-w-3xl px-4 py-12">
        {flowError ? (
          <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-950">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600" />
              <div className="min-w-0 flex-1">
                <p className="font-semibold">We could not finish that step.</p>
                <p className="mt-1 text-sm leading-6 text-amber-900">{flowError}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setFlowError(null);
                      setStep(1);
                    }}
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Try again
                  </Button>
                  <Link href={buildAuditReviewUrl()}>
                    <Button type="button" size="sm" variant="ghost">
                      <Mail className="mr-2 h-4 w-4" />
                      Contact sales
                    </Button>
                  </Link>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {step === 1 && (
          <Card className="border-0 shadow-lg">
            <CardHeader className="pb-2 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-100">
                <Search className="h-8 w-8 text-sky-700" />
              </div>
              <CardTitle className="text-2xl">Get My Free Maps Audit</CardTitle>
              <CardDescription className="text-base">
                We&apos;ll check your Google Maps visibility, review strength, and local competitor gaps in plain English.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <form onSubmit={submitAuditRequest} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="businessName">Business name</Label>
                  <Input
                    id="businessName"
                    placeholder="e.g., Naperville Plumbing Co."
                    value={businessName}
                    onChange={(event) => setBusinessInfo(event.target.value, address)}
                    className="h-12"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="address">City / service area</Label>
                  <Input
                    id="address"
                    placeholder="e.g., Naperville, IL"
                    value={address}
                    onChange={(event) => setBusinessInfo(businessName, event.target.value)}
                    className="h-12"
                  />
                </div>

                {isPublicFlow && (
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                      <Input
                        id="email"
                        type="email"
                        placeholder="owner@business.com"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        className="h-12 pl-10"
                      />
                    </div>
                  </div>
                )}

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone (optional)</Label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                      <Input
                        id="phone"
                        placeholder="(555) 123-4567"
                        value={phone}
                        onChange={(event) => setPhone(event.target.value)}
                        className="h-12 pl-10"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="websiteUrl">Website (optional)</Label>
                    <Input
                      id="websiteUrl"
                      placeholder="https://yourbusiness.com"
                      value={websiteUrl}
                      onChange={(event) => setWebsiteUrl(event.target.value)}
                      className="h-12"
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  className="h-12 w-full bg-gradient-to-r from-sky-500 to-cyan-500 hover:from-sky-600 hover:to-cyan-600"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Searching Google Maps...
                    </>
                  ) : (
                    <>
                      Check My Google Maps Visibility
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </form>

              <div className="rounded-2xl border border-sky-100 bg-sky-50 p-4 text-sm text-sky-900">
                <p className="font-medium">No fake reviews. No ranking guarantees.</p>
                <p className="mt-1 text-sky-800">
                  We use this audit to show what may be costing calls from nearby customers and what would be fixed first.
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 2 && (
          <Card className="border-0 shadow-lg">
            <CardHeader className="pb-2 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-100">
                <Building2 className="h-8 w-8 text-sky-700" />
              </div>
              <CardTitle className="text-2xl">Confirm the Right Listing</CardTitle>
              <CardDescription className="text-base">
                We found multiple matches. Pick the one you want us to audit.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {candidates.map((candidate) => (
                <button
                  key={candidate.place_id}
                  onClick={() => void handleSelectBusiness(candidate.place_id)}
                  disabled={isLoading}
                  className="w-full rounded-xl border p-4 text-left transition-colors hover:border-sky-400 hover:bg-sky-50 disabled:opacity-50"
                >
                  <div className="font-semibold text-slate-900">{candidate.name}</div>
                  <div className="mt-1 text-sm text-gray-500">{candidate.address}</div>
                  {candidate.rating != null && (
                    <div className="mt-2 flex items-center gap-1 text-sm text-slate-700">
                      <Star className="h-4 w-4 fill-yellow-500 text-yellow-500" />
                      <span>{candidate.rating}</span>
                      <span className="text-gray-400">
                        ({candidate.review_count ?? 0} reviews)
                      </span>
                    </div>
                  )}
                </button>
              ))}
              <Button variant="ghost" className="w-full" onClick={() => setStep(1)}>
                Back to search
              </Button>
            </CardContent>
          </Card>
        )}

        {step === 3 && (
          <Card className="border-0 shadow-lg">
            <CardHeader className="pb-2 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-100">
                <Sparkles className="h-8 w-8 animate-pulse text-sky-700" />
              </div>
              <CardTitle className="text-2xl">Building Your Audit</CardTitle>
              <CardDescription className="text-base">
                We&apos;re comparing your profile against nearby competitors and checking what may be limiting calls.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <Progress value={analysisProgress} className="h-3" />
              <div className="space-y-3">
                {[
                  'Finding your business on Google Maps',
                  'Checking reviews, ratings, and recency',
                  'Comparing nearby competitors',
                  'Looking for profile and page gaps',
                  'Preparing the first fix plan',
                ].map((label, index) => {
                  const done = analysisProgress >= (index + 1) * 20;
                  return (
                    <div key={label} className="flex items-center gap-3">
                      {done ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : (
                        <div className="h-5 w-5 rounded-full border-2 border-gray-300" />
                      )}
                      <span className={done ? 'text-slate-900' : 'text-gray-400'}>{label}</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {step === 4 && auditResult && (
          <div className="space-y-6">
            <Card className="border-0 shadow-lg">
              <CardHeader className="pb-2">
                <div className="mb-3 flex items-center justify-between gap-4">
                  <div>
                    <CardTitle className="text-2xl">Your Google Maps Visibility Audit</CardTitle>
                    <CardDescription className="mt-1 text-base">
                      We found {Math.max(issueCount, 3)} issues that may be costing calls from nearby customers.
                    </CardDescription>
                  </div>
                  <Badge className="bg-sky-100 text-sky-800 hover:bg-sky-100">
                    {auditResult.business.category || 'Local business'}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="rounded-3xl bg-slate-50 px-6 py-8 text-center">
                  <div className="text-sm font-medium uppercase tracking-[0.18em] text-slate-500">
                    Local Visibility Readiness Score
                  </div>
                  <div className="mt-3 text-6xl font-bold text-sky-700">
                    {auditResult.scores.total}
                  </div>
                  <div className="mt-2 text-sm text-gray-500">
                    Internal score based on profile completeness, review strength, competitor gaps, and tracking readiness. This is not a Google ranking score.
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border bg-white p-4">
                    <div className="text-sm font-medium text-slate-500">Review gap</div>
                    <div className="mt-2 text-2xl font-bold text-slate-900">
                      {auditResult.diagnosis.review_gap > 0
                        ? `${auditResult.diagnosis.review_gap} behind nearby competitors`
                        : 'No major review gap found'}
                    </div>
                    <div className="mt-2 text-sm text-gray-500">
                      Current rating {auditResult.business.rating ?? 'N/A'} from{' '}
                      {auditResult.business.review_count ?? 0} reviews.
                    </div>
                  </div>

                  <div className="rounded-2xl border bg-white p-4">
                    <div className="text-sm font-medium text-slate-500">Profile completeness</div>
                    <div className="mt-2 text-2xl font-bold text-slate-900">
                      {auditResult.diagnosis.missing_info.length
                        ? `${auditResult.diagnosis.missing_info.length} missing signals`
                        : 'No major missing profile fields'}
                    </div>
                    <div className="mt-2 text-sm text-gray-500">
                      {missingInfoLabels || 'Hours, phone, website, description, and photos look present.'}
                    </div>
                  </div>

                  <div className="rounded-2xl border bg-white p-4">
                    <div className="text-sm font-medium text-slate-500">Recent activity</div>
                    <div className="mt-2 flex items-center gap-2 text-2xl font-bold text-slate-900">
                      <Clock3 className="h-5 w-5 text-sky-700" />
                      {auditResult.diagnosis.days_since_post != null
                        ? `${auditResult.diagnosis.days_since_post} days since last post`
                        : 'No recent posting data found'}
                    </div>
                    <div className="mt-2 text-sm text-gray-500">
                      Fresh photos, posts, and recent activity help a profile look active to nearby customers.
                    </div>
                  </div>

                  <div className="rounded-2xl border bg-white p-4">
                    <div className="text-sm font-medium text-slate-500">Potential revenue leak</div>
                    <div className="mt-2 flex items-center gap-2 text-2xl font-bold text-slate-900">
                      <Phone className="h-5 w-5 text-sky-700" />
                      {auditResult.estimated_loss.monthly_dollars != null
                        ? `$${auditResult.estimated_loss.monthly_dollars.toLocaleString()} / month`
                        : 'Estimate unavailable'}
                    </div>
                    <div className="mt-2 text-sm text-gray-500">
                      Estimated missed calls: {auditResult.estimated_loss.missed_calls ?? 'N/A'} per month.
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl border border-sky-100 bg-sky-50 p-5">
                  <div className="text-sm font-medium uppercase tracking-[0.18em] text-sky-700">
                    Summary
                  </div>
                  <p className="mt-2 text-sm leading-7 text-slate-700">{auditResult.summary}</p>
                </div>

                <div className="space-y-3">
                  <h3 className="text-lg font-semibold">Top issues we would fix first</h3>
                  {topRecommendations.map((recommendation) => (
                    <div
                      key={`${recommendation.category}-${recommendation.title}`}
                      className="rounded-2xl border border-gray-200 bg-white p-4"
                    >
                      <div className="text-sm font-semibold text-slate-900">
                        {recommendation.title}
                      </div>
                      <div className="mt-1 text-sm text-gray-600">
                        {recommendation.description}
                      </div>
                      <div className="mt-2 text-xs font-medium uppercase tracking-[0.16em] text-sky-700">
                        Next action: {recommendation.action}
                      </div>
                    </div>
                  ))}
                </div>

                <Button
                  onClick={() => void handleViewSolution()}
                  className="h-12 w-full bg-gradient-to-r from-sky-500 to-cyan-500 hover:from-sky-600 hover:to-cyan-600"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      Show Me the Full Fix Plan
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>
        )}

        {step === 5 && solutionPresentation && (
          <div className="space-y-6">
            <Card className="border-0 bg-slate-50 shadow-lg">
              <CardContent className="pt-6">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="rounded-xl border bg-white p-4">
                    <p className="text-sm font-medium text-slate-900">What we fix first</p>
                    <p className="mt-1 text-sm text-slate-600">
                      Google Business Profile cleanup, review request setup, and the highest-impact local visibility gaps.
                    </p>
                  </div>
                  <div className="rounded-xl border bg-white p-4">
                    <p className="text-sm font-medium text-slate-900">What you keep</p>
                    <p className="mt-1 text-sm text-slate-600">
                      You keep ownership of your Google Business Profile. We only need manager access.
                    </p>
                  </div>
                  <div className="rounded-xl border bg-white p-4">
                    <p className="text-sm font-medium text-slate-900">What this is not</p>
                    <p className="mt-1 text-sm text-slate-600">
                      No fake reviews, no ranking guarantees, and no busywork dashboard you have to learn alone.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-0 bg-gradient-to-br from-sky-600 to-cyan-600 text-white shadow-lg">
              <CardContent className="pt-6 text-center">
                <h2 className="text-2xl font-bold">{solutionPresentation.opening?.headline}</h2>
                <p className="mt-2 text-sky-100">{solutionPresentation.opening?.message}</p>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-lg">
              <CardHeader>
                <CardTitle>What We Would Fix For You</CardTitle>
                <CardDescription>
                  The first 30 days should be about fixing the practical issues that affect trust, follow-up, and visibility.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {(solutionPresentation.solutions ?? []).map(
                  (solution: OnboardingSolutionStep, index: number) => (
                    <div
                      key={`${solution.title}-${index}`}
                      className="flex gap-4 rounded-2xl bg-gray-50 p-4"
                    >
                      <div className="text-2xl">{solution.emoji}</div>
                      <div>
                        <div className="font-semibold text-slate-900">{solution.title}</div>
                        <div className="text-sm text-gray-600">
                          {solution.description || solution.benefit || solution.subtitle}
                        </div>
                      </div>
                    </div>
                  )
                )}
              </CardContent>
            </Card>

            {solutionPresentation.projection && (
              <Card className="border border-emerald-200 bg-emerald-50 shadow-lg">
                <CardContent className="pt-6">
                  <h3 className="font-semibold text-emerald-900">
                    {solutionPresentation.projection.headline}
                  </h3>
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <div className="rounded-2xl bg-white p-4 text-center">
                      <Phone className="mx-auto mb-2 h-6 w-6 text-emerald-600" />
                      <div className="text-2xl font-bold text-emerald-700">
                        {solutionPresentation.projection.expected_results?.calls ?? 'More'}
                      </div>
                      <div className="text-sm text-gray-500">Call opportunity</div>
                    </div>
                    <div className="rounded-2xl bg-white p-4 text-center">
                      <Navigation className="mx-auto mb-2 h-6 w-6 text-emerald-600" />
                      <div className="text-2xl font-bold text-emerald-700">
                        {solutionPresentation.projection.expected_results?.directions ?? 'More'}
                      </div>
                      <div className="text-sm text-gray-500">Visit / direction opportunity</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {solutionPresentation.pricing && (
              <Card className="border-0 shadow-lg">
                <CardHeader>
                  <CardTitle>Recommended Managed Pilot</CardTitle>
                  <CardDescription>
                    Based on the audit, this is the smallest package we would review with you first.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col gap-4 rounded-2xl border border-sky-100 bg-sky-50 p-5 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="text-xl font-bold text-slate-950">
                        {solutionPresentation.pricing.plan_name || 'Managed Pilot'}
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-700">
                        {solutionPresentation.pricing.positioning ||
                          'A managed 3-month pilot focused on Google Maps visibility, reviews, and calls.'}
                      </p>
                      <p className="mt-2 text-xs font-medium uppercase tracking-[0.16em] text-sky-700">
                        3-month pilot, then month-to-month
                      </p>
                    </div>
                    <div className="text-left sm:text-right">
                      <div className="text-3xl font-bold text-slate-950">
                        ${solutionPresentation.pricing.price_monthly?.toLocaleString() || '699'}
                        <span className="text-sm font-medium text-slate-600">/mo</span>
                      </div>
                      {solutionPresentation.pricing.setup_fee != null && (
                        <div className="mt-1 text-sm text-slate-600">
                          ${solutionPresentation.pricing.setup_fee.toLocaleString()} setup
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            <Card className="border-0 shadow-lg">
              <CardContent className="pt-6 text-center">
                <h3 className="text-xl font-bold">
                  {isPublicFlow ? 'Want the full fix plan?' : solutionPresentation.cta?.headline}
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  {isPublicFlow
                    ? "Book a short audit review and we'll walk through what we would update first, what it would take, and whether a managed pilot makes sense."
                    : 'Open the workspace and decide which channels and workflows you want to activate first.'}
                </p>

                <div className="mt-6 space-y-3">
                  {isPublicFlow ? (
                    <>
                      <Button
                        size="lg"
                        className="h-14 w-full bg-gradient-to-r from-sky-500 to-cyan-500 text-lg hover:from-sky-600 hover:to-cyan-600"
                        onClick={() => router.push(buildAuditReviewUrl())}
                      >
                        Book My Free Audit Review
                      </Button>
                      <Button
                        size="lg"
                        variant="outline"
                        className="h-14 w-full text-lg"
                        onClick={() => router.push('/pricing')}
                      >
                        See Managed Pricing
                      </Button>
                    </>
                  ) : (
                    <Button
                      onClick={() => void handleStartTrial()}
                      size="lg"
                      className="h-14 w-full bg-gradient-to-r from-sky-500 to-cyan-500 text-lg hover:from-sky-600 hover:to-cyan-600"
                      disabled={isLoading}
                    >
                      {isLoading ? (
                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      ) : (
                        solutionPresentation.cta?.button_text || 'Start Free Preview'
                      )}
                    </Button>
                  )}
                </div>

                <p className="mt-4 text-sm text-gray-500">
                  {isPublicFlow
                    ? "No spam. No obligation. We'll review the audit in plain English."
                    : 'No credit card required. Paid growth workflows stay locked until you choose a plan.'}
                </p>
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
