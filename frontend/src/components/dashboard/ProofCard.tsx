'use client';

import { Card, CardContent } from '@/components/ui/card';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ProofCardProps {
  title: string;
  value: number | string;
  previousValue?: number;
  format?: 'number' | 'currency' | 'percent' | 'rating';
  icon: React.ReactNode;
  iconBgColor?: string;
  showDelta?: boolean;
  subtitle?: string;
}

export function ProofCard({
  title,
  value,
  previousValue,
  format = 'number',
  icon,
  iconBgColor = 'bg-violet-100',
  showDelta = true,
  subtitle,
}: ProofCardProps) {
  const numValue = typeof value === 'number' ? value : parseFloat(value) || 0;
  const delta = previousValue !== undefined ? numValue - previousValue : 0;
  const percentChange = previousValue && previousValue > 0
    ? ((delta / previousValue) * 100).toFixed(1)
    : '0';

  const isPositive = delta > 0;
  const isNegative = delta < 0;
  const isNeutral = delta === 0;

  const formatValue = (val: number | string): string => {
    if (typeof val === 'string') return val;
    switch (format) {
      case 'currency':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          maximumFractionDigits: 0,
        }).format(val);
      case 'percent':
        return `${val.toFixed(1)}%`;
      case 'rating':
        return val.toFixed(1);
      default:
        return new Intl.NumberFormat('en-US').format(val);
    }
  };

  return (
    <Card className="relative overflow-hidden group hover:shadow-lg transition-shadow">
      {/* Gradient accent */}
      <div className={cn(
        "absolute top-0 left-0 right-0 h-1",
        isPositive && "bg-gradient-to-r from-green-500 to-emerald-500",
        isNegative && "bg-gradient-to-r from-red-500 to-rose-500",
        isNeutral && "bg-gradient-to-r from-gray-300 to-gray-400",
      )} />

      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold tracking-tight">{formatValue(value)}</p>

            {showDelta && previousValue !== undefined && (
              <div className={cn(
                "flex items-center gap-1.5 text-sm font-medium",
                isPositive && "text-green-600",
                isNegative && "text-red-600",
                isNeutral && "text-gray-500",
              )}>
                {isPositive && <TrendingUp className="w-4 h-4" />}
                {isNegative && <TrendingDown className="w-4 h-4" />}
                {isNeutral && <Minus className="w-4 h-4" />}
                <span>
                  {isPositive && '+'}{delta} ({isPositive && '+'}{percentChange}%)
                </span>
                <span className="text-muted-foreground font-normal">vs last week</span>
              </div>
            )}

            {subtitle && (
              <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
            )}
          </div>

          <div className={cn(
            "w-12 h-12 rounded-xl flex items-center justify-center shrink-0",
            iconBgColor
          )}>
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
