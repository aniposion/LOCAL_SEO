'use client';

import { useCallback, useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Phone,
  Star,
  Globe,
  MessageSquare,
  Loader2,
  Lock,
  AlertCircle,
} from 'lucide-react';
import { billingApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { toast } from 'sonner';

interface Addon {
  id: string;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  min_plan: string;
  is_attached: boolean;
  is_pending_cancel: boolean;
  is_eligible: boolean;
  feature_flag: string;
}

interface AddonsSectionProps {
  currentPlan: string;
  onAddonChange?: () => void;
}

interface AddonPreviewData {
  proration_amount: number;
  note?: string;
}

const addonIcons: Record<string, LucideIcon> = {
  missed_call_text_back: Phone,
  review_booster: Star,
  website_seo_upgrade: Globe,
  social_auto_responder: MessageSquare,
};

const isVisibleAddon = (addon: Addon) =>
  addon.feature_flag !== 'video_generation' && addon.id !== 'short_video_generator';

export function AddonsSection({ currentPlan, onAddonChange }: AddonsSectionProps) {
  const [addons, setAddons] = useState<Addon[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [selectedAddon, setSelectedAddon] = useState<Addon | null>(null);
  const [previewAction, setPreviewAction] = useState<'attach' | 'detach'>('attach');
  const [previewData, setPreviewData] = useState<AddonPreviewData | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [processing, setProcessing] = useState(false);

  const fetchAddons = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const response = await billingApi.getAddons();
      setAddons((response.data.addons || []).filter(isVisibleAddon));
    } catch (error) {
      setAddons([]);
      setErrorMessage(
        getApiErrorMessage(error, `Add-ons for the ${currentPlan.toUpperCase()} plan are unavailable right now.`)
      );
    } finally {
      setLoading(false);
    }
  }, [currentPlan]);

  useEffect(() => {
    void fetchAddons();
  }, [fetchAddons]);

  const handleAddonClick = async (addon: Addon, action: 'attach' | 'detach') => {
    if (!addon.is_eligible && action === 'attach') {
      toast.error(`This add-on requires ${addon.min_plan.toUpperCase()} or higher.`);
      return;
    }

    setSelectedAddon(addon);
    setPreviewAction(action);
    setShowPreviewModal(true);
    setPreviewLoading(true);

    try {
      const response = await billingApi.previewAddon(addon.id, action);
      setPreviewData(response.data);
    } catch (error) {
      setPreviewData(null);
      setShowPreviewModal(false);
      toast.error(getApiErrorMessage(error, 'Live add-on preview is unavailable right now.'));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!selectedAddon) return;

    setProcessing(true);
    try {
      if (previewAction === 'attach') {
        await billingApi.attachAddon(selectedAddon.id);
        toast.success(`${selectedAddon.name} added.`);
      } else {
        await billingApi.detachAddon(selectedAddon.id, false);
        toast.success(`${selectedAddon.name} will be removed at period end.`);
      }
      setShowPreviewModal(false);
      fetchAddons();
      onAddonChange?.();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Request failed.'));
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        {errorMessage}
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {addons.filter(isVisibleAddon).map((addon) => {
          const Icon = addonIcons[addon.id] || Star;
          const isAttached = addon.is_attached;
          const isPendingCancel = addon.is_pending_cancel;

          return (
            <div
              key={addon.id}
              className={`p-4 rounded-lg border transition-all ${
                isAttached
                  ? isPendingCancel
                    ? 'bg-yellow-50 border-yellow-200'
                    : 'bg-green-50 border-green-200'
                  : addon.is_eligible
                    ? 'bg-white border-gray-200 hover:border-violet-300 hover:shadow-sm'
                    : 'bg-gray-50 border-gray-200 opacity-60'
              }`}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-gray-100 rounded-lg">
                    <Icon className="w-5 h-5 text-gray-700" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-sm">{addon.name}</h3>
                      {isAttached && <Badge variant="secondary">Active</Badge>}
                      {isPendingCancel && <Badge variant="outline">Pending cancel</Badge>}
                    </div>
                    <p className="text-sm text-gray-600 mt-1">{addon.description}</p>
                  </div>
                </div>
                {!addon.is_eligible && <Lock className="w-4 h-4 text-gray-400" />}
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-lg font-bold">${addon.price_monthly}</p>
                  <p className="text-xs text-gray-500">Requires {addon.min_plan.toUpperCase()}+</p>
                </div>

                {isAttached ? (
                  <Button variant="outline" size="sm" onClick={() => handleAddonClick(addon, 'detach')}>
                    Remove
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={() => handleAddonClick(addon, 'attach')}
                    disabled={!addon.is_eligible}
                  >
                    Add
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <Dialog open={showPreviewModal} onOpenChange={setShowPreviewModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {previewAction === 'attach' ? 'Add add-on' : 'Remove add-on'}
            </DialogTitle>
            <DialogDescription>
              Review the billing impact before confirming.
            </DialogDescription>
          </DialogHeader>

          {previewLoading ? (
            <div className="py-6 flex items-center justify-center">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          ) : selectedAddon ? (
            <div className="space-y-4">
              <div className="rounded-lg border p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{selectedAddon.name}</p>
                    <p className="text-sm text-gray-500">{selectedAddon.description}</p>
                  </div>
                  <p className="font-semibold">${selectedAddon.price_monthly}/mo</p>
                </div>
              </div>

              <div className="rounded-lg bg-gray-50 p-4 text-sm text-gray-700">
                <p>Proration: ${previewData?.proration_amount ?? 0}</p>
                {previewData?.note && <p className="mt-2">{previewData.note}</p>}
              </div>

              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                <div className="flex gap-2">
                  <AlertCircle className="w-4 h-4 mt-0.5" />
                  <p>
                    Some workflows are still being hardened for broader production use. Use add-ons that match your current operating process.
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowPreviewModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleConfirm} disabled={processing || previewLoading}>
              {processing && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {previewAction === 'attach' ? 'Confirm Add' : 'Confirm Remove'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
