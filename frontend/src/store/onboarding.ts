import { create } from 'zustand';

export interface OnboardingCandidate {
  place_id: string;
  name: string;
  address: string;
  rating?: number | null;
  review_count?: number | null;
}

export interface OnboardingAuditIssue {
  message: string;
}

export interface OnboardingAuditRecommendation {
  priority: number;
  category: string;
  status: string;
  title: string;
  description: string;
  action: string;
}

export interface OnboardingAuditResult {
  business: {
    name: string;
    address: string;
    category?: string | null;
    rating?: number | null;
    review_count?: number | null;
    photo_count?: number | null;
  };
  scores: {
    total: number;
    grade?: string | null;
    review: number;
    activity: number;
    completeness: number;
    competition: number;
  };
  diagnosis: {
    review_gap: number;
    days_since_post?: number | null;
    missing_info: string[];
  };
  estimated_loss: {
    monthly_dollars?: number | null;
    missed_calls?: number | null;
  };
  summary: string;
  recommendations: OnboardingAuditRecommendation[];
  recommended_plan?: string | null;
}

export interface OnboardingSolutionStep {
  emoji: string;
  title: string;
  description?: string;
  subtitle?: string;
  benefit?: string;
}

export interface OnboardingSolutionPresentation {
  opening?: {
    headline?: string;
    message?: string;
  };
  solutions?: OnboardingSolutionStep[];
  projection?: {
    headline?: string;
    expected_results?: {
      calls?: number | string;
      directions?: number | string;
    };
  };
  cta?: {
    headline?: string;
    features?: string[];
    button_text?: string;
  };
  pricing?: {
    recommended_plan?: string;
    plan_name?: string;
    price_monthly?: number;
    setup_fee?: number;
    positioning?: string;
    sales_motion?: string;
  };
}

interface OnboardingState {
  step: number;
  auditId: string | null;
  businessName: string;
  address: string;
  candidates: OnboardingCandidate[];
  selectedBusiness: OnboardingCandidate | null;
  auditResult: OnboardingAuditResult | null;
  solutionPresentation: OnboardingSolutionPresentation | null;
  isAnalyzing: boolean;
  analysisProgress: number;

  setStep: (step: number) => void;
  setAuditId: (id: string) => void;
  setBusinessInfo: (name: string, address: string) => void;
  setCandidates: (candidates: OnboardingCandidate[]) => void;
  setSelectedBusiness: (business: OnboardingCandidate) => void;
  setAuditResult: (result: OnboardingAuditResult) => void;
  setSolutionPresentation: (presentation: OnboardingSolutionPresentation) => void;
  setAnalyzing: (analyzing: boolean) => void;
  setAnalysisProgress: (progress: number) => void;
  reset: () => void;
}

export const useOnboardingStore = create<OnboardingState>((set) => ({
  step: 1,
  auditId: null,
  businessName: '',
  address: '',
  candidates: [],
  selectedBusiness: null,
  auditResult: null,
  solutionPresentation: null,
  isAnalyzing: false,
  analysisProgress: 0,

  setStep: (step) => set({ step }),
  setAuditId: (auditId) => set({ auditId }),
  setBusinessInfo: (businessName, address) => set({ businessName, address }),
  setCandidates: (candidates) => set({ candidates }),
  setSelectedBusiness: (selectedBusiness) => set({ selectedBusiness }),
  setAuditResult: (auditResult) => set({ auditResult }),
  setSolutionPresentation: (solutionPresentation) => set({ solutionPresentation }),
  setAnalyzing: (isAnalyzing) => set({ isAnalyzing }),
  setAnalysisProgress: (analysisProgress) => set({ analysisProgress }),
  reset: () => set({
    step: 1,
    auditId: null,
    businessName: '',
    address: '',
    candidates: [],
    selectedBusiness: null,
    auditResult: null,
    solutionPresentation: null,
    isAnalyzing: false,
    analysisProgress: 0,
  }),
}));
