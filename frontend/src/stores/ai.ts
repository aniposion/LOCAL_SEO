/**
 * P6: AI Content Store
 */
import { create } from 'zustand';
import { api } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

// Types
export interface GeneratedContent {
  content: string;
  platform: string;
  characterCount: number;
  wordCount: number;
  keywordsUsed: string[];
  seoScore: number;
  readabilityScore: number;
  suggestions: string[];
}

export interface ContentGenerateRequest {
  locationId: string;
  contentType?: 'post' | 'reply' | 'description' | 'faq';
  topic?: string;
  occasion?: string;
  keywords?: string[];
  platforms?: string[];
  tone?: string;
  length?: 'short' | 'medium' | 'long';
  includeCta?: boolean;
  ctaType?: string;
  numVariations?: number;
  language?: string;
}

export interface GenerateResponse {
  requestId: string;
  locationId: string;
  variations: GeneratedContent[];
  modelUsed: string;
  tokensUsed: number;
  generationTimeMs: number;
  createdAt: string;
}

export interface ReviewReplyRequest {
  locationId: string;
  reviewerName: string;
  starRating: number;
  reviewText: string;
  tone?: string;
  includeName?: boolean;
  includeInvitation?: boolean;
  offerResolution?: boolean;
  resolutionType?: string;
}

export interface ReviewReplyResponse {
  reply: string;
  sentimentDetected: string;
  keyPointsAddressed: string[];
  alternatives: string[];
  modelUsed: string;
  createdAt: string;
}

export interface ContentAnalysis {
  overallScore: number;
  isSafeToPublish: boolean;
  needsReview: boolean;

  seo?: {
    score: number;
    keywordsFound: string[];
    keywordsMissing: string[];
    keywordDensity: number;
    hasCta: boolean;
    hasLocalMention: boolean;
    suggestions: string[];
  };

  compliance: Array<{
    type: string;
    severity: 'low' | 'medium' | 'high';
    text: string;
    suggestion: string;
  }>;

  tone?: {
    detectedTone: string;
    expectedTone: string;
    matchScore: number;
    issues: string[];
  };

  readability?: {
    score: number;
    gradeLevel: string;
    avgSentenceLength: number;
    avgWordLength: number;
    complexWords: string[];
    suggestions: string[];
  };

  suggestedRevision?: string;
  analyzedAt: string;
}

export interface TopicSuggestion {
  topic: string;
  type: string;
}

export interface ContentTemplate {
  name: string;
  prompt?: string;
  tone?: string;
}

interface AIState {
  // Generation results
  generatedContent: GeneratedContent[];
  reviewReply: ReviewReplyResponse | null;
  analysis: ContentAnalysis | null;

  // Suggestions
  suggestions: TopicSuggestion[];
  templates: ContentTemplate[];

  // Loading
  isGenerating: boolean;
  isAnalyzing: boolean;

  // Error
  error: string | null;

  // Actions
  generateContent: (request: ContentGenerateRequest) => Promise<GenerateResponse>;
  quickGenerate: (locationId: string, topic?: string, platform?: string) => Promise<string>;

  generateReviewReply: (request: ReviewReplyRequest) => Promise<ReviewReplyResponse>;
  quickReviewReply: (
    locationId: string,
    reviewerName: string,
    starRating: number,
    reviewText: string
  ) => Promise<string>;

  analyzeContent: (content: string, locationId?: string) => Promise<ContentAnalysis>;
  quickAnalyze: (content: string, locationId?: string) => Promise<{
    score: number;
    isSafe: boolean;
    issuesCount: number;
  }>;

  fetchSuggestions: (locationId: string) => Promise<void>;
  fetchTemplates: (locationId: string, contentType?: string) => Promise<void>;

  clearResults: () => void;
  clearError: () => void;
}

export const useAIStore = create<AIState>((set) => ({
  // Initial state
  generatedContent: [],
  reviewReply: null,
  analysis: null,
  suggestions: [],
  templates: [],
  isGenerating: false,
  isAnalyzing: false,
  error: null,

  // Generate content
  generateContent: async (request: ContentGenerateRequest) => {
    set({ isGenerating: true, error: null, generatedContent: [] });
    try {
      const response = await api.post('/ai/generate', {
        location_id: request.locationId,
        content_type: request.contentType,
        topic: request.topic,
        occasion: request.occasion,
        keywords: request.keywords,
        platforms: request.platforms,
        tone: request.tone,
        length: request.length,
        include_cta: request.includeCta,
        cta_type: request.ctaType,
        num_variations: request.numVariations,
        language: request.language,
      });
      set({
        generatedContent: response.data.variations,
        isGenerating: false
      });
      return response.data;
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to generate content'),
        isGenerating: false
      });
      throw error;
    }
  },

  // Quick generate
  quickGenerate: async (locationId: string, topic?: string, platform = 'google') => {
    set({ isGenerating: true, error: null });
    try {
      const response = await api.post('/ai/generate/quick', null, {
        params: { location_id: locationId, topic, platform },
      });
      set({ isGenerating: false });
      return response.data.content;
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to generate quick content'),
        isGenerating: false
      });
      throw error;
    }
  },

  // Generate review reply
  generateReviewReply: async (request: ReviewReplyRequest) => {
    set({ isGenerating: true, error: null, reviewReply: null });
    try {
      const response = await api.post('/ai/review-reply', {
        location_id: request.locationId,
        reviewer_name: request.reviewerName,
        star_rating: request.starRating,
        review_text: request.reviewText,
        tone: request.tone,
        include_name: request.includeName,
        include_invitation: request.includeInvitation,
        offer_resolution: request.offerResolution,
        resolution_type: request.resolutionType,
      });
      set({ reviewReply: response.data, isGenerating: false });
      return response.data;
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to generate reply'),
        isGenerating: false
      });
      throw error;
    }
  },

  // Quick review reply
  quickReviewReply: async (
    locationId: string,
    reviewerName: string,
    starRating: number,
    reviewText: string
  ) => {
    set({ isGenerating: true, error: null });
    try {
      const response = await api.post('/ai/review-reply/quick', null, {
        params: {
          location_id: locationId,
          reviewer_name: reviewerName,
          star_rating: starRating,
          review_text: reviewText,
        },
      });
      set({ isGenerating: false });
      return response.data.reply;
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to generate a quick reply'),
        isGenerating: false
      });
      throw error;
    }
  },

  // Analyze content
  analyzeContent: async (content: string, locationId?: string) => {
    set({ isAnalyzing: true, error: null, analysis: null });
    try {
      const response = await api.post('/ai/analyze', {
        content,
        location_id: locationId,
      });
      set({ analysis: response.data, isAnalyzing: false });
      return response.data;
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to analyze content'),
        isAnalyzing: false
      });
      throw error;
    }
  },

  // Quick analyze
  quickAnalyze: async (content: string, locationId?: string) => {
    try {
      const response = await api.post('/ai/analyze/quick', null, {
        params: { content, location_id: locationId },
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Fetch topic suggestions
  fetchSuggestions: async (locationId: string) => {
    try {
      const response = await api.get(`/ai/suggestions/${locationId}`);
      set({ suggestions: response.data.suggestions });
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to fetch suggestions') });
    }
  },

  // Fetch templates
  fetchTemplates: async (locationId: string, contentType = 'post') => {
    try {
      const response = await api.get(`/ai/templates/${locationId}`, {
        params: { content_type: contentType },
      });
      set({ templates: response.data.templates });
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to fetch templates') });
    }
  },

  clearResults: () => set({
    generatedContent: [],
    reviewReply: null,
    analysis: null
  }),
  clearError: () => set({ error: null }),
}));
