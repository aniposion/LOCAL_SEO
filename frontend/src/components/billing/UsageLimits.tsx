'use client';

import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import Link from 'next/link';
import { AlertTriangle, FileText, TrendingUp, Zap } from 'lucide-react';

import { billingApi } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';

interface UsageItem {
  name: string;
  used: number;
  limit: number;
  icon: LucideIcon;
  color: 'violet' | 'blue' | 'green';
  description: string;
}

interface UsageLimitsProps {
  compact?: boolean;
  showUpgrade?: boolean;
}

const COLOR_STYLES = {
  violet: {
    badge: 'bg-violet-100 text-violet-700',
    iconBg: 'bg-violet-100',
    iconText: 'text-violet-600',
  },
  blue: {
    badge: 'bg-blue-100 text-blue-700',
    iconBg: 'bg-blue-100',
    iconText: 'text-blue-600',
  },
  green: {
    badge: 'bg-green-100 text-green-700',
    iconBg: 'bg-green-100',
    iconText: 'text-green-600',
  },
} as const;

export function UsageLimits({ compact = false, showUpgrade = true }: UsageLimitsProps) {
  const [loading, setLoading] = useState(true);
  const [usage, setUsage] = useState<UsageItem[]>([]);
  const [plan, setPlan] = useState('free');
  const [resetDate, setResetDate] = useState('');

  useEffect(() => {
    void fetchUsage();
  }, []);

  const fetchUsage = async () => {
    try {
      const response = await billingApi.getUsage();
      const data = response.data;

      setUsage([
        {
          name: 'AI Posts',
          used: data.posts_this_month || 0,
          limit: data.posts_limit ?? 0,
          icon: FileText,
          color: 'violet',
          description: 'Monthly AI-generated post usage.',
        },
        {
          name: 'Locations',
          used: data.locations_used || 0,
          limit: data.locations_limit ?? 0,
          icon: TrendingUp,
          color: 'blue',
          description: 'Connected business locations.',
        },
        {
          name: 'API Calls',
          used: data.api_calls_today || 0,
          limit: data.api_calls_limit ?? 0,
          icon: Zap,
          color: 'green',
          description: 'Daily API request allowance.',
        },
      ]);
      setPlan(data.plan || 'free');
    } catch {
      setUsage([]);
      setPlan('free');
    } finally {
      const now = new Date();
      const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
      setResetDate(nextMonth.toLocaleDateString());
      setLoading(false);
    }
  };

  const getPercentage = (used: number, limit: number) => {
    if (limit <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((used / limit) * 100));
  };

  const getStatusColor = (percentage: number) => {
    if (percentage >= 90) return 'text-red-500';
    if (percentage >= 75) return 'text-amber-500';
    return 'text-green-500';
  };

  const getProgressColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 75) return 'bg-amber-500';
    return 'bg-green-500';
  };

  const formatLimit = (limit: number) => {
    if (limit < 0) {
      return 'Unlimited';
    }
    return limit.toString();
  };

  const formatRemaining = (used: number, limit: number) => {
    if (limit < 0) {
      return 'Unlimited';
    }
    return Math.max(0, limit - used).toString();
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (usage.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5" />
            Usage
          </CardTitle>
          <CardDescription>Usage data is not available right now.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (compact) {
    return (
      <div className="space-y-3 rounded-lg bg-gray-50 p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Usage</span>
          <Badge variant="outline" className="text-xs">
            {plan.toUpperCase()}
          </Badge>
        </div>
        {usage.map((item) => {
          const percentage = getPercentage(item.used, item.limit);
          return (
            <div key={item.name} className="space-y-1" title={`${item.description} Reset: ${resetDate}`}>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-600">{item.name}</span>
                <span className={getStatusColor(percentage)}>
                  {item.used}/{formatLimit(item.limit)}
                </span>
              </div>
              <Progress value={percentage} className="h-1.5" />
            </div>
          );
        })}
        {showUpgrade && (
          <Link href="/dashboard/billing">
            <Button size="sm" variant="outline" className="mt-2 w-full text-xs">
              <Zap className="mr-1 h-3 w-3" />
              View plans
            </Button>
          </Link>
        )}
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              Monthly usage
            </CardTitle>
            <CardDescription>Usage resets on {resetDate}.</CardDescription>
          </div>
          <Badge className="bg-violet-100 text-violet-700">{plan.toUpperCase()}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {usage.map((item) => {
            const percentage = getPercentage(item.used, item.limit);
            const Icon = item.icon;
            const isWarning = item.limit > 0 && percentage >= 75;
            const isCritical = item.limit > 0 && percentage >= 90;
            const colorStyles = COLOR_STYLES[item.color];

            return (
              <div key={item.name} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${colorStyles.iconBg}`}>
                      <Icon className={`h-5 w-5 ${colorStyles.iconText}`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 font-medium">
                        {item.name}
                        {isCritical ? <AlertTriangle className="h-4 w-4 text-red-500" /> : null}
                      </div>
                      <div className="text-sm text-gray-500">{item.description}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`font-semibold ${getStatusColor(percentage)}`}>
                      {item.used} / {formatLimit(item.limit)}
                    </div>
                    <div className="text-sm text-gray-500">
                      {formatRemaining(item.used, item.limit)} remaining
                    </div>
                  </div>
                </div>

                <div className="relative">
                  <Progress value={percentage} className="h-2" />
                  <div
                    className={`absolute left-0 top-0 h-full rounded-full transition-all ${getProgressColor(percentage)}`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>

                {isWarning ? (
                  <p className={`text-xs ${isCritical ? 'text-red-600' : 'text-amber-600'}`}>
                    {isCritical
                      ? 'You are close to your limit. Consider upgrading before work is interrupted.'
                      : 'You have used more than 75% of this allowance.'}
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>

        {showUpgrade ? (
          <div className="mt-6 rounded-lg bg-gradient-to-r from-violet-50 to-indigo-50 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Need more capacity?</p>
                <p className="text-sm text-gray-600">Upgrade your plan to unlock higher limits.</p>
              </div>
              <Link href="/dashboard/billing">
                <Button className="bg-gradient-to-r from-violet-600 to-indigo-600">
                  <Zap className="mr-2 h-4 w-4" />
                  Upgrade
                </Button>
              </Link>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
