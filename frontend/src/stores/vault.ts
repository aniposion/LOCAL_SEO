/**
 * P5: Entity Vault Store
 */
import { create } from 'zustand';
import { api } from '@/lib/api';
import { getApiErrorMessage, getApiErrorStatus } from '@/lib/api-errors';

// Types
export interface Address {
  street1: string;
  street2?: string;
  city: string;
  state: string;
  postalCode: string;
  country: string;
}

export interface BusinessHours {
  monday: DayHours;
  tuesday: DayHours;
  wednesday: DayHours;
  thursday: DayHours;
  friday: DayHours;
  saturday: DayHours;
  sunday: DayHours;
  timezone: string;
}

export interface DayHours {
  isOpen: boolean;
  openTime?: string;
  closeTime?: string;
}

export interface ContactInfo {
  primaryPhone?: string;
  secondaryPhone?: string;
  email?: string;
  website?: string;
  facebookUrl?: string;
  instagramUrl?: string;
}

export interface Service {
  name: string;
  description?: string;
  priceRange?: string;
  keywords?: string[];
}

export interface EntityVault {
  id: string;
  locationId: string;

  // Basic
  businessName: string;
  tagline?: string;
  description?: string;
  primaryCategory?: string;
  secondaryCategories: string[];

  // Location
  address?: string;
  fullAddress?: Address;
  city?: string;
  state?: string;
  zipCode?: string;
  coordinates?: { latitude: number; longitude: number };

  // Contact
  phone?: string;
  website?: string;
  contactInfo?: ContactInfo;

  // Hours
  businessHours?: BusinessHours;
  specialHours?: Array<{
    date: string;
    isClosed: boolean;
    openTime?: string;
    closeTime?: string;
    reason?: string;
  }>;
  hoursTimezone?: string;

  // Attributes
  paymentMethods?: Record<string, boolean>;
  amenities?: Record<string, boolean>;
  serviceArea?: {
    type: string;
    radiusMiles?: number;
    zipCodes?: string[];
  };

  // Content
  services: Service[];
  tone: string;
  forbiddenPhrases: string[];
  requiredPhrases: string[];
  faq: Array<{ question: string; answer: string }>;

  // SEO
  primaryKeywords: string[];
  secondaryKeywords: string[];
  localKeywords: string[];

  // Media
  logoUrl?: string;
  coverPhotoUrl?: string;
  photoUrls: string[];

  // Sync
  gbpSyncStatus?: string;
  gbpLastSyncedAt?: string;

  createdAt: string;
  updatedAt: string;
}

export interface NAPConsistencyReport {
  locationId: string;
  masterName: string;
  masterAddress: string;
  masterPhone?: string;
  consistencyScore: number;
  totalSources: number;
  consistentCount: number;
  inconsistentCount: number;
  issues: Array<{
    source: string;
    issue: string;
  }>;
  generatedAt: string;
}

interface VaultState {
  // Data
  vault: EntityVault | null;
  napReport: NAPConsistencyReport | null;
  isOpen: boolean | null;

  // Loading
  isLoading: boolean;
  isSaving: boolean;
  isSyncing: boolean;

  // Error
  error: string | null;

  // Actions
  fetchVault: (locationId: string) => Promise<void>;
  createVault: (locationId: string, data: Partial<EntityVault>) => Promise<void>;
  updateVault: (locationId: string, data: Partial<EntityVault>) => Promise<void>;

  updateAddress: (locationId: string, address: Address) => Promise<void>;
  updateHours: (locationId: string, hours: BusinessHours) => Promise<void>;
  updateContact: (locationId: string, contact: ContactInfo) => Promise<void>;

  syncToGoogle: (locationId: string) => Promise<void>;
  importFromGoogle: (locationId: string, gbpLocationName: string) => Promise<void>;

  checkNAP: (locationId: string) => Promise<void>;
  checkIsOpen: (locationId: string) => Promise<void>;

  clearError: () => void;
}

export const useVaultStore = create<VaultState>((set, get) => ({
  // Initial state
  vault: null,
  napReport: null,
  isOpen: null,
  isLoading: false,
  isSaving: false,
  isSyncing: false,
  error: null,

  // Fetch vault
  fetchVault: async (locationId: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get(`/entity-vault/${locationId}`);
      set({ vault: response.data, isLoading: false });
    } catch (error) {
      if (getApiErrorStatus(error) === 404) {
        set({ vault: null, isLoading: false });
      } else {
        set({
          error: getApiErrorMessage(error, 'Failed to fetch vault'),
          isLoading: false
        });
      }
    }
  },

  // Create vault
  createVault: async (locationId: string, data: Partial<EntityVault>) => {
    set({ isSaving: true, error: null });
    try {
      await api.post(`/entity-vault/${locationId}`, data);
      await get().fetchVault(locationId);
      set({ isSaving: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to create the vault'),
        isSaving: false
      });
      throw error;
    }
  },

  // Update vault
  updateVault: async (locationId: string, data: Partial<EntityVault>) => {
    set({ isSaving: true, error: null });
    try {
      await api.put(`/entity-vault/${locationId}`, data);
      await get().fetchVault(locationId);
      set({ isSaving: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to update the vault'),
        isSaving: false
      });
      throw error;
    }
  },

  // Update address
  updateAddress: async (locationId: string, address: Address) => {
    set({ isSaving: true });
    try {
      await api.put(`/entity-vault/${locationId}/address`, address);
      set((state) => ({
        vault: state.vault ? { ...state.vault, fullAddress: address } : null,
        isSaving: false,
      }));
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to update the address'), isSaving: false });
      throw error;
    }
  },

  // Update hours
  updateHours: async (locationId: string, hours: BusinessHours) => {
    set({ isSaving: true });
    try {
      await api.put(`/entity-vault/${locationId}/hours`, hours);
      set((state) => ({
        vault: state.vault ? { ...state.vault, businessHours: hours } : null,
        isSaving: false,
      }));
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to update the business hours'), isSaving: false });
      throw error;
    }
  },

  // Update contact
  updateContact: async (locationId: string, contact: ContactInfo) => {
    set({ isSaving: true });
    try {
      await api.put(`/entity-vault/${locationId}/contact`, contact);
      set((state) => ({
        vault: state.vault ? { ...state.vault, contactInfo: contact } : null,
        isSaving: false,
      }));
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to update the contact info'), isSaving: false });
      throw error;
    }
  },

  // Sync to Google
  syncToGoogle: async (locationId: string) => {
    set({ isSyncing: true, error: null });
    try {
      await api.post(`/entity-vault/${locationId}/sync/google`);
      await get().fetchVault(locationId);
      set({ isSyncing: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to sync to Google'),
        isSyncing: false
      });
      throw error;
    }
  },

  // Import from Google
  importFromGoogle: async (locationId: string, gbpLocationName: string) => {
    set({ isLoading: true, error: null });
    try {
      await api.post(`/entity-vault/${locationId}/import/google`, null, {
        params: { gbp_location_name: gbpLocationName },
      });
      await get().fetchVault(locationId);
      set({ isLoading: false });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to import from Google'),
        isLoading: false
      });
      throw error;
    }
  },

  // Check NAP consistency
  checkNAP: async (locationId: string) => {
    try {
      const response = await api.get(`/entity-vault/${locationId}/nap-check`);
      set({ napReport: response.data });
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to check NAP consistency') });
    }
  },

  // Check if open
  checkIsOpen: async (locationId: string) => {
    try {
      const response = await api.get(`/entity-vault/${locationId}/is-open`);
      set({ isOpen: response.data.is_open });
    } catch {
      set({ isOpen: null });
    }
  },

  clearError: () => set({ error: null }),
}));
