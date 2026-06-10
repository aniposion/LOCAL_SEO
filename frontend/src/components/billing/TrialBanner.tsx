'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, Clock, CreditCard, X } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { billingApi } from '@/lib/api';

const FREE_PREVIEW_DAYS = 3;

interface TrialStatus {
  is_trial: boolean;
  trial_end: string | null;
  days_remaining: number;
  plan: string;
}

export function TrialBanner() {
  const [trialStatus, setTrialStatus] = useState<TrialStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void fetchTrialStatus();
  }, []);

  const fetchTrialStatus = async () => {
    try {
      const response = await billingApi.getSubscription();
      const sub = response.data;

      if (sub?.status === 'trialing' && sub?.trial_end) {
        const trialEnd = new Date(sub.trial_end);
        const now = new Date();
        const daysRemaining = Math.ceil((trialEnd.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

        setTrialStatus({
          is_trial: true,
          trial_end: sub.trial_end,
          days_remaining: Math.max(0, daysRemaining),
          plan: sub.plan || sub.plan_type || 'free',
        });
      } else {
        setTrialStatus(null);
      }
    } catch {
      setTrialStatus(null);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !trialStatus?.is_trial || dismissed) {
    return null;
  }

  const { days_remaining, plan } = trialStatus;
  const isLastDay = days_remaining <= 1;
  const trialProgress = ((FREE_PREVIEW_DAYS - days_remaining) / FREE_PREVIEW_DAYS) * 100;

  return (
    <div
      className={`relative px-4 py-3 ${
        isLastDay
          ? 'bg-gradient-to-r from-amber-500 to-orange-500'
          : 'bg-gradient-to-r from-slate-800 to-sky-800'
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <div className="flex flex-1 items-center gap-4">
          {isLastDay ? (
            <AlertTriangle className="h-5 w-5 animate-pulse text-white" />
          ) : (
            <Clock className="h-5 w-5 text-white" />
          )}

          <div className="flex-1">
            <div className="flex items-center gap-3">
              <span className="font-medium text-white">
                {isLastDay
                  ? 'Your free preview ends soon'
                  : `${plan.toUpperCase()} preview active`}
              </span>
              <Badge className="bg-white/20 text-white hover:bg-white/30">
                {days_remaining} day{days_remaining === 1 ? '' : 's'} left
              </Badge>
            </div>
            <p className="mt-1 text-xs text-white/80">
              You can preview dashboard readiness, setup health, audit context, and billing options. Paid AI, SMS,
              publishing, and automation workflows stay locked until you choose a paid plan.
            </p>
            <div className="mt-2 max-w-xs">
              <Progress value={trialProgress} className="h-1.5 bg-white/30" />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link href="/dashboard/billing">
            <Button size="sm" className="bg-white text-slate-900 hover:bg-gray-100">
              <CreditCard className="mr-2 h-4 w-4" />
              View paid plans
            </Button>
          </Link>

          <button
            onClick={() => setDismissed(true)}
            className="p-1 text-white/60 transition-colors hover:text-white"
            aria-label="Dismiss free preview banner"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
