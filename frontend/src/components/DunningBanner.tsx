/**
 * Dunning Banner Component
 *
 * P0: Displays payment failure warning banner
 * Shows when subscription is in 'warning' or 'suspended' state
 */

import React from 'react';
import { AlertTriangle, CreditCard, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { billingApi } from '@/lib/api';

interface DunningStatus {
  in_dunning: boolean;
  state: 'active' | 'warning' | 'suspended';
  days_remaining?: number;
  message?: string;
  portal_url?: string;
}

interface DunningBannerProps {
  dunningStatus: DunningStatus;
  onDismiss?: () => void;
}

export function DunningBanner({ dunningStatus, onDismiss }: DunningBannerProps) {
  if (!dunningStatus.in_dunning) {
    return null;
  }

  const isWarning = dunningStatus.state === 'warning';
  const isSuspended = dunningStatus.state === 'suspended';

  return (
    <Alert
      className={`
        border-l-4 mb-4
        ${isWarning ? 'bg-yellow-50 border-yellow-500' : 'bg-red-50 border-red-500'}
      `}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-1">
          <AlertTriangle
            className={`h-5 w-5 ${isWarning ? 'text-yellow-600' : 'text-red-600'}`}
          />
          <div className="flex-1">
            <div className={`font-semibold ${isWarning ? 'text-yellow-900' : 'text-red-900'}`}>
              {isSuspended ? '?뵶 Account Suspended' : '?좑툘 Payment Failed'}
              {isWarning && dunningStatus.days_remaining !== undefined && (
                <span className="ml-2 text-sm font-normal">
                  ({dunningStatus.days_remaining} days remaining)
                </span>
              )}
            </div>
            <AlertDescription className={`text-sm mt-1 ${isWarning ? 'text-yellow-800' : 'text-red-800'}`}>
              {dunningStatus.message || 'Please update your payment method to restore access.'}
            </AlertDescription>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={() => {
              if (dunningStatus.portal_url) {
                window.location.href = dunningStatus.portal_url;
              }
            }}
            variant={isSuspended ? 'destructive' : 'default'}
            size="sm"
            className="whitespace-nowrap"
          >
            <CreditCard className="h-4 w-4 mr-2" />
            Update Payment
          </Button>

          {onDismiss && isWarning && (
            <Button
              onClick={onDismiss}
              variant="ghost"
              size="sm"
              className="text-gray-500 hover:text-gray-700"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </Alert>
  );
}

/**
 * Hook to fetch dunning status
 */
export function useDunningStatus() {
  const [dunningStatus, setDunningStatus] = React.useState<DunningStatus | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    async function fetchDunningStatus() {
      try {
        const response = await billingApi.getDunningStatus();
        setDunningStatus(response.data);
      } catch (error) {
        console.error('Failed to fetch dunning status:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchDunningStatus();
  }, []);

  return { dunningStatus, loading };
}
