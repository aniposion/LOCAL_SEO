'use client';

import { useState, ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { useFeatureAccess } from '@/hooks/useFeatureAccess';
import { UpgradeModal } from './UpgradeModal';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Lock, Zap, Crown, Star } from 'lucide-react';
import Link from 'next/link';

interface FeatureGateProps {
  feature: string;
  requiredPlan?: 'starter' | 'pro' | 'premium' | 'agency';
  children: ReactNode;
  fallback?: 'modal' | 'inline' | 'blur';
  className?: string;
}

const PLAN_ORDER = ['free', 'maps_starter', 'calls_growth', 'competitive_market', 'starter', 'pro', 'premium', 'agency'];

const planIcons: Record<'pro' | 'premium' | 'agency', LucideIcon> = {
  pro: Star,
  premium: Crown,
  agency: Star,
};

export function FeatureGate({
  feature,
  requiredPlan = 'pro',
  children,
  fallback = 'inline',
  className = '',
}: FeatureGateProps) {
  const { data: featureAccess, isLoading } = useFeatureAccess();
  const [showModal, setShowModal] = useState(false);

  // Loading state - show children
  if (isLoading) {
    return <>{children}</>;
  }

  const currentPlan = featureAccess?.plan || 'free';
  const currentPlanIndex = PLAN_ORDER.indexOf(currentPlan);
  const requiredPlanIndex = PLAN_ORDER.indexOf(requiredPlan);

  // Check feature access
  const featureValue = featureAccess?.features?.[feature as keyof typeof featureAccess.features];
  const hasFeatureAccess = typeof featureValue === 'boolean' ? featureValue : false;
  const hasPlanAccess = currentPlanIndex >= requiredPlanIndex;

  // If user has access, render children
  if (hasFeatureAccess || hasPlanAccess) {
    return <>{children}</>;
  }

  // User doesn't have access - show fallback
  const upgradePlan: 'pro' | 'premium' | 'agency' = requiredPlan === 'starter' ? 'pro' : requiredPlan;
  const Icon = planIcons[upgradePlan] || Star;

  // Modal fallback
  if (fallback === 'modal') {
    return (
      <>
        <div onClick={() => setShowModal(true)} className={`cursor-pointer ${className}`}>
          {children}
        </div>
        <UpgradeModal
          open={showModal}
          onOpenChange={setShowModal}
          feature={feature}
          requiredPlan={upgradePlan}
          currentPlan={currentPlan}
        />
      </>
    );
  }

  // Blur fallback
  if (fallback === 'blur') {
    return (
      <div className={`relative ${className}`}>
        <div className="blur-sm pointer-events-none select-none">
          {children}
        </div>
        <div className="absolute inset-0 bg-white/80 flex items-center justify-center">
          <div className="text-center p-6">
            <div className="w-12 h-12 mx-auto mb-3 bg-violet-100 rounded-xl flex items-center justify-center">
              <Lock className="w-6 h-6 text-violet-600" />
            </div>
            <Badge className="mb-2">{requiredPlan.toUpperCase()} plan required</Badge>
            <p className="text-sm text-gray-600 mb-4">
              Choose a paid plan to use this workflow.
            </p>
            <Link href="/dashboard/billing">
              <Button size="sm">
                <Zap className="w-4 h-4 mr-2" />
                View plans
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Inline fallback (default)
  return (
    <Card className={`border-dashed border-2 border-violet-200 bg-violet-50/50 ${className}`}>
      <CardContent className="p-6 text-center">
        <div className="w-12 h-12 mx-auto mb-4 bg-gradient-to-br from-violet-100 to-indigo-100 rounded-xl flex items-center justify-center">
          <Icon className="w-6 h-6 text-violet-600" />
        </div>
        <Badge className="mb-3 bg-violet-100 text-violet-700">
          {requiredPlan.toUpperCase()} plan
        </Badge>
        <h3 className="font-semibold mb-2">This workflow unlocks on a paid plan</h3>
        <p className="text-sm text-gray-600 mb-4">
          Upgrade to {requiredPlan.toUpperCase()} when you are ready to use this workflow.
        </p>
        <Link href="/dashboard/billing">
          <Button className="bg-gradient-to-r from-violet-600 to-indigo-600">
            <Zap className="w-4 h-4 mr-2" />
            View plan options
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}

// Export the hook for reuse
export { useUpgradeModal } from './UpgradeModal';
