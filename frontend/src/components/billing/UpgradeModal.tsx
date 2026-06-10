'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Lock,
  Zap,
  Star,
  Crown,
  Building2,
  Check,
  ArrowRight,
  Sparkles,
} from 'lucide-react';

interface UpgradeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  feature: string;
  requiredPlan: 'pro' | 'premium' | 'agency';
  currentPlan?: string;
}

const planDetails = {
  pro: {
    name: 'Pro',
    price: 149,
    icon: Star,
    color: 'violet',
    benefits: [
      'Instagram Publishing Tools',
      'Content Scheduler',
      'Q&A Response Drafts',
      'Review Trend Analysis',
      'Website SEO Tools (Beta)',
    ],
  },
  premium: {
    name: 'Premium',
    price: 249,
    icon: Crown,
    color: 'amber',
    benefits: [
      'All Pro features',
      'Missed Call Text Back',
      'Review Booster (SMS/Email)',
      'Website SEO Workflows (Beta)',
      'Advanced Response Automation',
    ],
  },
  agency: {
    name: 'Agency',
    price: 499,
    icon: Building2,
    color: 'indigo',
    benefits: [
      'All Premium features',
      'White Label Reports',
      'Multi-Location Dashboard',
      'Team Permission Management',
    ],
  },
};

const featureNames: Record<string, string> = {
  instagram_upload: 'Instagram Publishing Tools',
  content_scheduler: 'Content Scheduler',
  qa_auto_response: 'Q&A Response Drafts',
  competitor_analysis: 'Competitor Analysis',
  website_seo_basic: 'Website SEO Tools',
  website_seo_advanced: 'Website SEO Workflows',
  missed_call_text_back: 'Missed Call Text Back',
  review_booster_campaigns: 'Review Booster',
  social_auto_responder: 'Advanced Response Automation',
  video_generation: 'Video Generation',
  white_label: 'White Label Reports',
  multi_location: 'Multi-Location Management',
};

export function UpgradeModal({
  open,
  onOpenChange,
  feature,
  requiredPlan,
}: UpgradeModalProps) {
  const plan = planDetails[requiredPlan];
  const Icon = plan.icon;
  const featureName = featureNames[feature] || feature;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader className="text-center">
          <div className="mx-auto w-16 h-16 bg-gradient-to-br from-violet-100 to-indigo-100 rounded-2xl flex items-center justify-center mb-4">
            <Lock className="w-8 h-8 text-violet-600" />
          </div>
          <DialogTitle className="text-xl">Upgrade Required</DialogTitle>
          <DialogDescription>
            <span className="font-semibold text-violet-600">{featureName}</span> is available on the{' '}
            <Badge variant="secondary">{plan.name}</Badge> plan or higher.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <div className="p-4 bg-gradient-to-br from-violet-50 to-indigo-50 rounded-xl border border-violet-200">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-violet-100 rounded-lg flex items-center justify-center">
                  <Icon className="w-5 h-5 text-violet-600" />
                </div>
                <div>
                  <h3 className="font-semibold">{plan.name} Plan</h3>
                  <p className="text-sm text-gray-500">Monthly billing</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold">${plan.price}</p>
                <p className="text-xs text-gray-500">/mo</p>
              </div>
            </div>

            <div className="space-y-2">
              {plan.benefits.map((benefit) => (
                <div key={benefit} className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-500" />
                  <span className="text-sm">{benefit}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-start gap-2">
              <Sparkles className="w-4 h-4 text-amber-500 mt-0.5" />
              <p className="text-sm text-amber-800">
                <strong>Note:</strong> Some higher-tier workflows are still being hardened for broader production rollout.
              </p>
            </div>
          </div>
        </div>

        <DialogFooter className="flex flex-col gap-2">
          <Link href="/dashboard/billing" className="w-full">
            <Button className="w-full bg-gradient-to-r from-violet-600 to-indigo-600">
              <Zap className="w-4 h-4 mr-2" />
              Upgrade to {plan.name}
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Link>
          <Button variant="ghost" className="w-full" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function useUpgradeModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [modalProps, setModalProps] = useState<{
    feature: string;
    requiredPlan: 'pro' | 'premium' | 'agency';
  }>({
    feature: '',
    requiredPlan: 'pro',
  });

  const showUpgradeModal = (feature: string, requiredPlan: 'pro' | 'premium' | 'agency') => {
    setModalProps({ feature, requiredPlan });
    setIsOpen(true);
  };

  const UpgradeModalComponent = () => (
    <UpgradeModal
      open={isOpen}
      onOpenChange={setIsOpen}
      feature={modalProps.feature}
      requiredPlan={modalProps.requiredPlan}
    />
  );

  return {
    showUpgradeModal,
    UpgradeModalComponent,
    isOpen,
    setIsOpen,
  };
}
