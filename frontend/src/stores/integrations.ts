/**
 * P4: Integrations & OAuth Store
 */
import { create } from 'zustand';
import { api } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

// Types
export interface OAuthToken {
  id: string;
  provider: 'google' | 'facebook' | 'instagram';
  email?: string;
  status: 'active' | 'expired' | 'refresh_failed' | 'revoked';
  scopes: string[];
  expiresAt?: string;
  lastUsedAt?: string;
  createdAt: string;
}

export interface ConnectionStatus {
  googleConnected: boolean;
  facebookConnected: boolean;
  instagramConnected: boolean;
  googleLocations: number;
  needsAttention: string[];
}

export interface GBPLocation {
  name: string;
  title: string;
  storeCode?: string;
  address: Record<string, unknown>;
  phone?: string;
  website?: string;
  categories: string[];
  isVerified: boolean;
}

interface IntegrationsState {
  // Data
  tokens: OAuthToken[];
  status: ConnectionStatus | null;
  gbpLocations: GBPLocation[];

  // Loading
  isLoading: boolean;
  isConnecting: boolean;

  // Error
  error: string | null;

  // Actions
  fetchTokens: () => Promise<void>;
  fetchStatus: () => Promise<void>;

  connect: (provider: string, redirectUri: string) => Promise<string>;
  disconnect: (provider: string) => Promise<void>;
  refreshToken: (provider: string) => Promise<void>;

  fetchGBPLocations: () => Promise<void>;
  linkGBPLocation: (locationId: string, gbpLocationName: string) => Promise<void>;

  clearError: () => void;
}

export const useIntegrationsStore = create<IntegrationsState>((set, get) => ({
  // Initial state
  tokens: [],
  status: null,
  gbpLocations: [],
  isLoading: false,
  isConnecting: false,
  error: null,

  // Fetch all tokens
  fetchTokens: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get('/oauth/tokens');
      set({
        tokens: response.data.items,
        isLoading: false
      });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch tokens'),
        isLoading: false
      });
    }
  },

  // Fetch connection status
  fetchStatus: async () => {
    try {
      const response = await api.get('/oauth/status');
      set({ status: response.data });
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to fetch integration status') });
    }
  },

  // Initiate OAuth connection
  connect: async (provider: string, redirectUri: string) => {
    set({ isConnecting: true, error: null });
    try {
      const response = await api.post(`/oauth/connect/${provider}`, null, {
        params: { redirect_uri: redirectUri },
      });
      set({ isConnecting: false });
      return response.data.auth_url;
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to initiate the connection'),
        isConnecting: false
      });
      throw error;
    }
  },

  // Disconnect provider
  disconnect: async (provider: string) => {
    set({ isLoading: true, error: null });
    try {
      await api.post(`/oauth/disconnect-provider/${provider}`);
      // Refresh data
      await Promise.all([
        get().fetchTokens(),
        get().fetchStatus(),
      ]);
      set({ isLoading: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to disconnect the provider'),
        isLoading: false
      });
      throw error;
    }
  },

  // Manual token refresh
  refreshToken: async (provider: string) => {
    try {
      await api.post(`/oauth/refresh-token/${provider}`);
      await get().fetchTokens();
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to refresh the token') });
      throw error;
    }
  },

  // Fetch GBP locations
  fetchGBPLocations: async () => {
    set({ isLoading: true });
    try {
      const response = await api.get('/oauth/google/locations');
      set({ gbpLocations: response.data.locations, isLoading: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch Google Business Profile locations'),
        isLoading: false
      });
    }
  },

  // Link GBP location to our location
  linkGBPLocation: async (locationId: string, gbpLocationName: string) => {
    try {
      await api.post(`/locations/${locationId}/link-gbp`, {
        gbp_location_name: gbpLocationName,
      });
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to link the GBP location') });
      throw error;
    }
  },

  clearError: () => set({ error: null }),
}));
