'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { useHasFeature, FEATURE_NAMES, UPGRADE_SUGGESTIONS, FeatureAccess } from '@/hooks/useFeatureAccess';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Lock, Sparkles, ArrowRight } from 'lucide-react';

interface FeatureGateProps {
  feature: keyof FeatureAccess['features'];
  children: ReactNode;
  fallback?: ReactNode;
  showUpgrade?: boolean;
}

/**
 * FeatureGate component - Shows content only if user has access to the feature
 *
 * Usage:
 * <FeatureGate feature="instagram_upload">
 *   <InstagramUploadComponent />
 * </FeatureGate>
 */
export function FeatureGate({
  feature,
  children,
  fallback,
  showUpgrade = true
}: FeatureGateProps) {
  const { hasAccess, isLoading } = useHasFeature(feature);

  if (isLoading) {
    return (
      <div className="animate-pulse bg-gray-100 rounded-lg h-32" />
    );
  }

  if (hasAccess) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  if (!showUpgrade) {
    return null;
  }

  const featureInfo = FEATURE_NAMES[feature] || { name: feature, description: '' };
  const suggestedPlan = UPGRADE_SUGGESTIONS[feature] || 'Pro';

  return (
    <Card className="border-2 border-dashed border-violet-200 bg-violet-50/50">
      <CardContent className="py-8 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-violet-100 flex items-center justify-center">
          <Lock className="w-8 h-8 text-violet-600" />
        </div>
        <h3 className="text-lg font-semibold mb-2">{featureInfo.name}</h3>
        <p className="text-gray-600 text-sm mb-4 max-w-md mx-auto">
          {featureInfo.description}
        </p>
        <Badge className="mb-4 bg-violet-100 text-violet-700">
          {suggestedPlan} plan required
        </Badge>
        <div className="flex justify-center gap-3">
          <Link href="/dashboard/billing">
            <Button className="bg-gradient-to-r from-violet-600 to-indigo-600">
              <Sparkles className="w-4 h-4 mr-2" />
              View plans
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * FeatureButton - Button that shows upgrade prompt if feature is not available
 */
interface FeatureButtonProps {
  feature: keyof FeatureAccess['features'];
  children: ReactNode;
  onClick?: () => void;
  className?: string;
  variant?: 'default' | 'outline' | 'ghost' | 'destructive';
}

export function FeatureButton({
  feature,
  children,
  onClick,
  className,
  variant = 'default',
}: FeatureButtonProps) {
  const { hasAccess, isLoading } = useHasFeature(feature);
  const suggestedPlan = UPGRADE_SUGGESTIONS[feature] || 'Pro';

  if (isLoading) {
    return (
      <Button disabled className={className} variant={variant}>
        Loading...
      </Button>
    );
  }

  if (hasAccess) {
    return (
      <Button onClick={onClick} className={className} variant={variant}>
        {children}
      </Button>
    );
  }

  return (
    <Link href="/dashboard/billing">
      <Button className={className} variant="outline">
        <Lock className="w-4 h-4 mr-2" />
        {suggestedPlan} plan required
      </Button>
    </Link>
  );
}

/**
 * FeatureBadge - Shows a badge indicating if feature is available
 */
interface FeatureBadgeProps {
  feature: keyof FeatureAccess['features'];
  showWhenAvailable?: boolean;
}

export function FeatureBadge({ feature, showWhenAvailable = false }: FeatureBadgeProps) {
  const { hasAccess, isLoading, isTrial } = useHasFeature(feature);
  const suggestedPlan = UPGRADE_SUGGESTIONS[feature] || 'Pro';

  if (isLoading) return null;

  if (hasAccess) {
    if (isTrial) {
      return (
        <Badge className="bg-amber-100 text-amber-700">
          Preview
        </Badge>
      );
    }
    if (showWhenAvailable) {
      return (
        <Badge className="bg-green-100 text-green-700">
          Available
        </Badge>
      );
    }
    return null;
  }

  return (
    <Badge className="bg-gray-100 text-gray-600">
      <Lock className="w-3 h-3 mr-1" />
      {suggestedPlan}
    </Badge>
  );
}

/**
 * UpgradePrompt - Full upgrade prompt card
 */
interface UpgradePromptProps {
  title?: string;
  description?: string;
  features?: string[];
  suggestedPlan?: string;
}

export function UpgradePrompt({
  title = 'Unlock more growth workflows',
  description = 'Choose a paid plan to use this feature and the workflows around it.',
  features = [],
  suggestedPlan = 'Pro',
}: UpgradePromptProps) {
  return (
    <Card className="bg-gradient-to-br from-violet-50 to-indigo-50 border-violet-200">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-violet-600" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {features.length > 0 && (
          <ul className="space-y-2 mb-6">
            {features.map((feature, index) => (
              <li key={index} className="flex items-center gap-2 text-sm text-gray-700">
                <ArrowRight className="w-4 h-4 text-violet-500" />
                {feature}
              </li>
            ))}
          </ul>
        )}
        <Link href="/dashboard/billing">
          <Button className="w-full bg-gradient-to-r from-violet-600 to-indigo-600">
            View {suggestedPlan} plan options
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}

/**
 * PlanBadge - Shows current plan badge
 */
export function PlanBadge() {
  const { isLoading, plan, isTrial } = useHasFeature('basic_dashboard');

  if (isLoading) return null;

  const planColors: Record<string, string> = {
    free: 'bg-gray-100 text-gray-700',
    starter: 'bg-blue-100 text-blue-700',
    pro: 'bg-violet-100 text-violet-700',
    premium: 'bg-amber-100 text-amber-700',
    agency: 'bg-emerald-100 text-emerald-700',
  };

  return (
    <Badge className={planColors[plan] || planColors.free}>
      {plan.charAt(0).toUpperCase() + plan.slice(1)}
      {isTrial && ' (Preview)'}
    </Badge>
  );
}
