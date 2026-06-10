/**
 * P2: Review Booster Store
 */
import { create } from 'zustand';

import { reviewCampaignsApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

export interface ReviewCampaign {
  id: string;
  location_id: string;
  name: string;
  status: 'active' | 'paused' | 'completed';
  sms_template?: string | null;
  email_template?: string | null;
  email_subject?: string | null;
  delay_hours: number;
  channels: string[];
  google_review_url: string;
  private_feedback_url?: string | null;
  total_sent: number;
  total_clicked: number;
  total_reviews_estimated: number;
  created_at: string;
  updated_at: string;
}

export interface BoosterRequest {
  id: string;
  campaign_id: string;
  location_id: string;
  customer_name?: string | null;
  customer_phone?: string | null;
  customer_email?: string | null;
  status: 'pending' | 'sent' | 'delivered' | 'failed' | 'opted_out';
  channel: 'sms' | 'email';
  consent_given: boolean;
  consent_method?: string | null;
  google_link_included: boolean;
  sent_at?: string | null;
  delivered_at?: string | null;
  last_attempt_at?: string | null;
  next_retry_at?: string | null;
  retry_count: number;
  last_error?: string | null;
  google_link_clicked_at?: string | null;
  created_at: string;
}

export interface PrivateFeedback {
  id: string;
  location_id: string;
  customer_name?: string | null;
  rating?: number | null;
  feedback_text?: string | null;
  status: 'new' | 'in_progress' | 'resolved' | 'closed';
  assigned_to?: string | null;
  notes?: string | null;
  resolved_at?: string | null;
  created_at: string;
}

export interface OptoutStatus {
  is_opted_out: boolean;
  opted_out_at?: string | null;
}

export interface CreateCampaignInput {
  name: string;
  google_review_url: string;
  sms_template?: string;
  email_template?: string;
  email_subject?: string;
  delay_hours?: number;
  channels?: string[];
  private_feedback_url?: string | null;
}

export interface SendRequestInput {
  locationId: string;
  campaign_id: string;
  customer_name: string;
  customer_phone?: string;
  customer_email?: string;
  channel: 'sms' | 'email';
  consent_given: boolean;
  consent_method: string;
}

interface ReviewsState {
  campaigns: ReviewCampaign[];
  requests: BoosterRequest[];
  feedback: PrivateFeedback[];
  optoutStatus: OptoutStatus | null;
  selectedCampaign: ReviewCampaign | null;
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
  fetchCampaigns: (locationId: string) => Promise<void>;
  createCampaign: (locationId: string, data: CreateCampaignInput) => Promise<ReviewCampaign>;
  updateCampaign: (id: string, data: Partial<CreateCampaignInput & { status: ReviewCampaign['status'] }>) => Promise<void>;
  deleteCampaign: (id: string) => Promise<void>;
  fetchRequests: (locationId: string, campaignId?: string, status?: BoosterRequest['status']) => Promise<void>;
  sendRequest: (data: SendRequestInput) => Promise<BoosterRequest>;
  sendBulkRequests: (locationId: string, requests: Array<Omit<SendRequestInput, 'locationId'>>) => Promise<BoosterRequest[]>;
  fetchFeedback: (locationId: string, status?: PrivateFeedback['status']) => Promise<void>;
  resolveFeedback: (id: string, notes: string) => Promise<PrivateFeedback>;
  addOptout: (locationId: string, data: { phone?: string; email?: string; reason?: string }) => Promise<OptoutStatus>;
  checkOptout: (locationId: string, phone?: string, email?: string) => Promise<OptoutStatus>;
  selectCampaign: (campaign: ReviewCampaign | null) => void;
  clearError: () => void;
}

export const useReviewsStore = create<ReviewsState>((set) => ({
  campaigns: [],
  requests: [],
  feedback: [],
  optoutStatus: null,
  selectedCampaign: null,
  isLoading: false,
  isSending: false,
  error: null,

  fetchCampaigns: async (locationId: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await reviewCampaignsApi.list(locationId);
      set({ campaigns: response.data.items, isLoading: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch campaigns'),
        isLoading: false,
      });
    }
  },

  createCampaign: async (locationId: string, data: CreateCampaignInput) => {
    try {
      const response = await reviewCampaignsApi.create(locationId, data);
      const newCampaign = response.data as ReviewCampaign;
      set((state) => ({ campaigns: [newCampaign, ...state.campaigns] }));
      return newCampaign;
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to create campaign');
      set({ error: message });
      throw error;
    }
  },

  updateCampaign: async (id: string, data) => {
    try {
      const response = await reviewCampaignsApi.update(id, data);
      const updatedCampaign = response.data as ReviewCampaign;
      set((state) => ({
        campaigns: state.campaigns.map((campaign) =>
          campaign.id === id ? updatedCampaign : campaign
        ),
        selectedCampaign: state.selectedCampaign?.id === id ? updatedCampaign : state.selectedCampaign,
      }));
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to update campaign');
      set({ error: message });
      throw error;
    }
  },

  deleteCampaign: async (id: string) => {
    try {
      await reviewCampaignsApi.delete(id);
      set((state) => ({
        campaigns: state.campaigns.filter((campaign) => campaign.id !== id),
        selectedCampaign: state.selectedCampaign?.id === id ? null : state.selectedCampaign,
      }));
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to archive campaign');
      set({ error: message });
      throw error;
    }
  },

  fetchRequests: async (locationId: string, campaignId?: string, status?: BoosterRequest['status']) => {
    set({ isLoading: true, error: null });
    try {
      const response = await reviewCampaignsApi.getRequests(locationId, campaignId, status);
      set({ requests: response.data.items, isLoading: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch requests'),
        isLoading: false,
      });
    }
  },

  sendRequest: async (data: SendRequestInput) => {
    set({ isSending: true, error: null });
    try {
      const response = await reviewCampaignsApi.sendRequest(data.locationId, {
        campaign_id: data.campaign_id,
        customer_name: data.customer_name,
        customer_email: data.customer_email,
        customer_phone: data.customer_phone,
        channel: data.channel,
        consent_given: data.consent_given,
        consent_method: data.consent_method,
      });
      const createdRequest = response.data as BoosterRequest;
      set((state) => ({
        requests: [createdRequest, ...state.requests],
        isSending: false,
      }));
      return createdRequest;
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to send the request'),
        isSending: false,
      });
      throw error;
    }
  },

  sendBulkRequests: async (locationId: string, requests) => {
    set({ isSending: true, error: null });
    try {
      const createdRequests = await Promise.all(
        requests.map(async (request) => {
          const response = await reviewCampaignsApi.sendRequest(locationId, request);
          return response.data as BoosterRequest;
        })
      );
      set((state) => ({
        requests: [...createdRequests, ...state.requests],
        isSending: false,
      }));
      return createdRequests;
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to send bulk requests'),
        isSending: false,
      });
      throw error;
    }
  },

  fetchFeedback: async (locationId: string, status?: PrivateFeedback['status']) => {
    set({ isLoading: true, error: null });
    try {
      const response = await reviewCampaignsApi.getFeedbacks(locationId, status);
      set({ feedback: response.data.items, isLoading: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch feedback'),
        isLoading: false,
      });
    }
  },

  resolveFeedback: async (id: string, notes: string) => {
    try {
      const response = await reviewCampaignsApi.updateFeedback(id, {
        status: 'resolved',
        notes,
      });
      const updatedFeedback = response.data as PrivateFeedback;
      set((state) => ({
        feedback: state.feedback.map((item) => (item.id === id ? updatedFeedback : item)),
      }));
      return updatedFeedback;
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to resolve feedback');
      set({ error: message });
      throw error;
    }
  },

  addOptout: async (locationId: string, data) => {
    try {
      const response = await reviewCampaignsApi.addOptout(locationId, data);
      const optoutStatus = response.data as OptoutStatus;
      set({ optoutStatus });
      return optoutStatus;
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to add opt-out');
      set({ error: message });
      throw error;
    }
  },

  checkOptout: async (locationId: string, phone?: string, email?: string) => {
    try {
      const response = await reviewCampaignsApi.checkOptout(locationId, phone, email);
      const optoutStatus = response.data as OptoutStatus;
      set({ optoutStatus });
      return optoutStatus;
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to check opt-out status');
      set({ error: message });
      throw error;
    }
  },

  selectCampaign: (campaign) => set({ selectedCampaign: campaign }),
  clearError: () => set({ error: null }),
}));
