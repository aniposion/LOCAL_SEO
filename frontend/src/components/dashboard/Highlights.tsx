'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Trophy, Star, Phone, Navigation } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Highlight {
  type: 'increase' | 'decrease' | 'milestone';
  metric: string;
  message: string;
  value: number;
  percent: number;
}

interface HighlightsProps {
  highlights: Highlight[];
}

const metricIcons: Record<string, React.ReactNode> = {
  calls: <Phone className="h-4 w-4" />,
  directions: <Navigation className="h-4 w-4" />,
  reviews: <Star className="h-4 w-4" />,
  default: <Trophy className="h-4 w-4" />,
};

const typeConfig = {
  increase: {
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
    textColor: 'text-green-700',
    badgeVariant: 'default' as const,
    icon: <TrendingUp className="h-4 w-4 text-green-600" />,
  },
  decrease: {
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    textColor: 'text-red-700',
    badgeVariant: 'destructive' as const,
    icon: <TrendingDown className="h-4 w-4 text-red-600" />,
  },
  milestone: {
    bgColor: 'bg-violet-50',
    borderColor: 'border-violet-200',
    textColor: 'text-violet-700',
    badgeVariant: 'secondary' as const,
    icon: <Trophy className="h-4 w-4 text-violet-600" />,
  },
};

export function Highlights({ highlights }: HighlightsProps) {
  if (!highlights || highlights.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Trophy className="h-5 w-5 text-yellow-500" />
          This Week&apos;s Highlights
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {highlights.map((highlight, index) => {
            const config = typeConfig[highlight.type];
            const icon = metricIcons[highlight.metric] || metricIcons.default;

            return (
              <div
                key={index}
                className={cn('flex items-center gap-3 rounded-lg border p-3', config.bgColor, config.borderColor)}
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white shadow-sm">
                  {icon}
                </div>

                <div className="flex-1">
                  <p className={cn('font-medium', config.textColor)}>{highlight.message}</p>
                </div>

                {highlight.type !== 'milestone' && (
                  <Badge variant={config.badgeVariant} className="shrink-0">
                    {config.icon}
                    <span className="ml-1">
                      {highlight.percent > 0 && '+'}
                      {highlight.percent.toFixed(1)}%
                    </span>
                  </Badge>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
