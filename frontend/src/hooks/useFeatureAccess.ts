'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export interface FeatureAccess {
  plan: string;
  status: string;
  is_trial: boolean;
  trial_end: string | null;
  features: {
    google_posts: boolean;
    review_collection: boolean;
    ai_review_response: boolean;
    basic_dashboard: boolean;
    weekly_report: boolean;
    instagram_upload: boolean;
    content_scheduler: boolean;
    qa_auto_response: boolean;
    competitor_analysis: boolean;
    website_seo_basic: boolean;
    website_seo_full: boolean;
    missed_call_text_back: boolean;
    review_booster: boolean;
    social_auto_responder: boolean;
    video_generator: boolean;
    white_label: boolean;
    team_management: boolean;
    multi_location: boolean;
    locations_limit: number;
    posts_per_month: number;
  };
  active_addons: string[];
  monthly_price: number;
  current_period_end: string | null;
}

export function useFeatureAccess() {
  return useQuery<FeatureAccess>({
    queryKey: ['featureAccess'],
    queryFn: async () => {
      const response = await api.get('/billing/features');
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 1,
  });
}

export function useHasFeature(feature: keyof FeatureAccess['features']) {
  const { data, isLoading } = useFeatureAccess();

  return {
    hasAccess: data?.features?.[feature] ?? false,
    isLoading,
    plan: data?.plan ?? 'free',
    isTrial: data?.is_trial ?? false,
  };
}

export function useCheckFeature(feature: string) {
  return useQuery<{ feature: string; has_access: boolean }>({
    queryKey: ['featureCheck', feature],
    queryFn: async () => {
      const response = await api.get(`/billing/features/${feature}`);
      return response.data;
    },
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

// Feature names for display
export const FEATURE_NAMES: Record<string, { name: string; description: string }> = {
  basic_dashboard: {
    name: 'Dashboard Preview',
    description: 'Review setup health, next actions, and local performance context.',
  },
  weekly_report: {
    name: 'Weekly Reports',
    description: 'Generate weekly summaries that connect activity to business outcomes.',
  },
  google_posts: {
    name: 'Google Business Profile Posts',
    description: 'Create, approve, and publish Google Business Profile post drafts.',
  },
  review_collection: {
    name: 'Review Collection',
    description: 'Request, track, and manage customer reviews and private feedback.',
  },
  ai_review_response: {
    name: 'AI Review Responses',
    description: 'Draft review replies for human review before publishing.',
  },
  instagram_upload: {
    name: 'Instagram Publishing',
    description: 'Publish approved content to connected Instagram accounts.',
  },
  content_scheduler: {
    name: 'Content Scheduler',
    description: 'Schedule approved content so publishing stays consistent.',
  },
  qa_auto_response: {
    name: 'Google Q&A Answers',
    description: 'Sync Google Q&A questions and prepare answer drafts.',
  },
  competitor_analysis: {
    name: 'Competitor Analysis',
    description: 'Compare competitors so local growth gaps are easier to prioritize.',
  },
  website_seo_basic: {
    name: 'Website SEO Basics',
    description: 'Create local SEO metadata and page improvement ideas.',
  },
  website_seo_full: {
    name: 'Website SEO Workflows',
    description: 'Generate deeper SEO recommendations, page drafts, and blog content.',
  },
  missed_call_text_back: {
    name: 'Missed Call Text Back',
    description: 'Automatically follow up when a customer call is missed.',
  },
  review_booster: {
    name: 'Review Booster',
    description: 'Send review request campaigns by SMS or email.',
  },
  social_auto_responder: {
    name: 'Social Auto-Responder',
    description: 'Draft or automate replies for social DMs and comments.',
  },
  video_generator: {
    name: 'Video Generator',
    description: 'Create reusable short-form video assets from approved content.',
  },
  white_label: {
    name: 'White Label',
    description: 'Use agency branding on reports and client-facing workflows.',
  },
  team_management: {
    name: 'Team Management',
    description: 'Invite teammates and manage role-based access.',
  },
  multi_location: {
    name: 'Multi-Location Management',
    description: 'Manage multiple business locations from one workspace.',
  },
};

// Plan upgrade suggestions
export const UPGRADE_SUGGESTIONS: Record<string, string> = {
  google_posts: 'Starter',
  review_collection: 'Starter',
  ai_review_response: 'Starter',
  weekly_report: 'Starter',
  instagram_upload: 'Pro',
  content_scheduler: 'Pro',
  qa_auto_response: 'Pro',
  competitor_analysis: 'Pro',
  website_seo_basic: 'Pro',
  website_seo_full: 'Premium',
  missed_call_text_back: 'Premium',
  review_booster: 'Premium',
  social_auto_responder: 'Premium',
  video_generator: 'Agency',
  white_label: 'Agency',
  team_management: 'Agency',
  multi_location: 'Agency',
};
