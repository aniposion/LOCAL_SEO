'use client';

import { AlertTriangle, TrendingUp, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';

interface UsageLimitModalProps {
  isOpen: boolean;
  onClose: () => void;
  feature: string;
  currentUsage: number;
  usageLimit: number;
  usagePercentage: number;
  upgradeMessage?: string;
  upgradeUrl?: string;
}

export function UsageLimitModal({
  isOpen,
  onClose,
  feature,
  currentUsage,
  usageLimit,
  usagePercentage,
  upgradeMessage,
  upgradeUrl = '/dashboard/billing',
}: UsageLimitModalProps) {
  const isLimitReached = usagePercentage >= 100;
  const isWarning = usagePercentage >= 80 && usagePercentage < 100;

  const handleUpgrade = () => {
    window.location.href = upgradeUrl;
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3">
            {isLimitReached ? (
              <div className="p-2 bg-red-100 rounded-full">
                <AlertTriangle className="h-6 w-6 text-red-600" />
              </div>
            ) : (
              <div className="p-2 bg-yellow-100 rounded-full">
                <AlertTriangle className="h-6 w-6 text-yellow-600" />
              </div>
            )}
            <div>
              <DialogTitle>
                {isLimitReached ? 'Usage Limit Reached' : 'Usage Warning'}
              </DialogTitle>
              <DialogDescription>
                {feature.replace(/_/g, ' ')}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Usage Progress */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Current Usage</span>
              <span className="font-semibold">
                {currentUsage} / {usageLimit}
              </span>
            </div>
            <Progress
              value={usagePercentage}
              className={`h-2 ${
                isLimitReached
                  ? '[&>div]:bg-red-500'
                  : isWarning
                  ? '[&>div]:bg-yellow-500'
                  : ''
              }`}
            />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{usagePercentage.toFixed(0)}% used</span>
              <Badge variant={isLimitReached ? 'destructive' : isWarning ? 'default' : 'secondary'}>
                {usageLimit - currentUsage} remaining
              </Badge>
            </div>
          </div>

          {/* Message */}
          <div className={`p-4 rounded-lg ${
            isLimitReached
              ? 'bg-red-50 border border-red-200'
              : 'bg-yellow-50 border border-yellow-200'
          }`}>
            <p className="text-sm">
              {isLimitReached ? (
                <>
                  You&apos;ve reached your monthly limit for this feature.
                  Upgrade your plan to continue using AI automation.
                </>
              ) : (
                <>
                  You&apos;ve used {usagePercentage.toFixed(0)}% of your monthly limit.
                  Consider upgrading to avoid interruptions.
                </>
              )}
            </p>
          </div>

          {/* Upgrade Benefits */}
          {upgradeMessage && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-primary" />
                <span className="font-semibold text-sm">Upgrade Benefits</span>
              </div>
              <p className="text-sm text-muted-foreground">{upgradeMessage}</p>

              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <Zap className="h-4 w-4 text-yellow-500" />
                  <span>Higher usage limits</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Zap className="h-4 w-4 text-yellow-500" />
                  <span>Priority AI processing</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Zap className="h-4 w-4 text-yellow-500" />
                  <span>Advanced analytics</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button variant="outline" onClick={onClose} className="w-full sm:w-auto">
            {isLimitReached ? 'Close' : 'Continue'}
          </Button>
          <Button onClick={handleUpgrade} className="w-full sm:w-auto">
            <TrendingUp className="h-4 w-4 mr-2" />
            Upgrade Plan
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Usage Warning Banner Component
interface UsageWarningBannerProps {
  feature: string;
  usagePercentage: number;
  onUpgrade: () => void;
  onDismiss: () => void;
}

export function UsageWarningBanner({
  feature,
  usagePercentage,
  onUpgrade,
  onDismiss,
}: UsageWarningBannerProps) {
  if (usagePercentage < 80) return null;

  const isLimitReached = usagePercentage >= 100;

  return (
    <div className={`p-4 rounded-lg border ${
      isLimitReached
        ? 'bg-red-50 border-red-200'
        : 'bg-yellow-50 border-yellow-200'
    }`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className={`h-5 w-5 mt-0.5 ${
            isLimitReached ? 'text-red-600' : 'text-yellow-600'
          }`} />
          <div className="space-y-1">
            <p className="font-semibold text-sm">
              {isLimitReached ? 'Usage Limit Reached' : 'Approaching Usage Limit'}
            </p>
            <p className="text-sm text-muted-foreground">
              You&apos;ve used {usagePercentage.toFixed(0)}% of your {feature.replace(/_/g, ' ')} limit this month.
              {isLimitReached && ' Upgrade to continue using this feature.'}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={onUpgrade}>
            Upgrade
          </Button>
          {!isLimitReached && (
            <Button size="sm" variant="ghost" onClick={onDismiss}>
              Dismiss
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
