/**
 * P3: Calls & SMS Store
 */
import { create } from 'zustand';
import { api } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

// Types
export interface CallLog {
  id: string;
  locationId: string;
  callerPhone: string;
  maskedPhone: string;
  direction: 'inbound' | 'outbound';
  status: 'answered' | 'missed' | 'busy' | 'failed';
  durationSeconds?: number;
  callStartedAt: string;
  callEndedAt?: string;
  textBackSent: boolean;
  textBackAt?: string;
  createdAt: string;
}

export interface SMSThread {
  id: string;
  locationId: string;
  customerPhone: string;
  maskedPhone: string;
  customerName?: string;
  status: 'active' | 'archived' | 'blocked';
  unreadCount: number;
  lastMessageAt: string;
  lastMessagePreview: string;
}

export interface SMSMessage {
  id: string;
  direction: 'inbound' | 'outbound';
  body: string;
  sentAt: string;
  status: 'queued' | 'sent' | 'delivered' | 'failed' | 'received';
  isRead: boolean;
}

export interface TextBackSettings {
  id: string;
  locationId: string;
  enabled: boolean;
  delaySeconds: number;
  respectBusinessHours: boolean;
  defaultMessage: string;
  afterHoursMessage: string;
  enableQuickReplies: boolean;
  quickReplyOptions: string[];
  twilioNumber?: string;
  forwardingNumber?: string;
}

export interface CallStats {
  totalCalls: number;
  answeredCalls: number;
  missedCalls: number;
  textBacksSent: number;
  textBackRate: number;
}

interface CallsState {
  // Data
  callLogs: CallLog[];
  threads: SMSThread[];
  messages: SMSMessage[];
  settings: TextBackSettings | null;
  stats: CallStats | null;

  // Selected
  selectedThread: SMSThread | null;

  // Loading
  isLoading: boolean;
  isLoadingMessages: boolean;
  isSending: boolean;

  // Counts
  totalUnread: number;

  // Error
  error: string | null;

  // Actions
  fetchCallLogs: (locationId: string, days?: number) => Promise<void>;
  fetchStats: (locationId: string, days?: number) => Promise<void>;

  fetchThreads: (locationId: string, unreadOnly?: boolean) => Promise<void>;
  fetchMessages: (locationId: string, threadId: string) => Promise<void>;
  sendMessage: (locationId: string, threadId: string, body: string) => Promise<void>;
  markThreadRead: (locationId: string, threadId: string) => Promise<void>;

  fetchSettings: (locationId: string) => Promise<void>;
  updateSettings: (locationId: string, data: Partial<TextBackSettings>) => Promise<void>;

  selectThread: (thread: SMSThread | null) => void;
  clearError: () => void;
}

export const useCallsStore = create<CallsState>((set, get) => ({
  // Initial state
  callLogs: [],
  threads: [],
  messages: [],
  settings: null,
  stats: null,
  selectedThread: null,
  isLoading: false,
  isLoadingMessages: false,
  isSending: false,
  totalUnread: 0,
  error: null,

  // Call Logs
  fetchCallLogs: async (locationId: string, days = 30) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get(`/calls/${locationId}/logs`, {
        params: { days },
      });
      set({
        callLogs: response.data.items,
        isLoading: false
      });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch call logs'),
        isLoading: false
      });
    }
  },

  fetchStats: async (locationId: string, days = 30) => {
    try {
      const response = await api.get(`/calls/${locationId}/stats`, {
        params: { days },
      });
      set({ stats: response.data });
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to fetch call stats') });
    }
  },

  // SMS Threads
  fetchThreads: async (locationId: string, unreadOnly = false) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get(`/calls/${locationId}/threads`, {
        params: { unread_only: unreadOnly },
      });
      set({
        threads: response.data.items,
        totalUnread: response.data.totalUnread,
        isLoading: false
      });
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch threads'),
        isLoading: false
      });
    }
  },

  fetchMessages: async (locationId: string, threadId: string) => {
    set({ isLoadingMessages: true });
    try {
      const response = await api.get(`/calls/${locationId}/threads/${threadId}`);
      set({
        messages: response.data.messages,
        isLoadingMessages: false
      });
      // Mark as read
      await get().markThreadRead(locationId, threadId);
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to fetch messages'),
        isLoadingMessages: false
      });
    }
  },

  sendMessage: async (locationId: string, threadId: string, body: string) => {
    set({ isSending: true, error: null });
    try {
      const response = await api.post(`/calls/${locationId}/threads/${threadId}/send`, {
        body,
      });
      // Add message to list
      set((state) => ({
        messages: [...state.messages, {
          id: response.data.messageId,
          direction: 'outbound',
          body,
          sentAt: new Date().toISOString(),
          status: response.data.status,
          isRead: true,
        }],
        isSending: false,
      }));
    } catch (error) {
      set({
        error: getApiErrorMessage(error, 'Failed to send message'),
        isSending: false
      });
      throw error;
    }
  },

  markThreadRead: async (locationId: string, threadId: string) => {
    try {
      await api.post(`/calls/${locationId}/threads/${threadId}/read`);
      set((state) => ({
        threads: state.threads.map((t) =>
          t.id === threadId ? { ...t, unreadCount: 0 } : t
        ),
        totalUnread: Math.max(0, state.totalUnread - (
          state.threads.find((t) => t.id === threadId)?.unreadCount || 0
        )),
      }));
    } catch {
      // Silent fail for mark read
    }
  },

  // Settings
  fetchSettings: async (locationId: string) => {
    try {
      const response = await api.get(`/calls/${locationId}/settings`);
      set({ settings: response.data });
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to fetch call settings') });
    }
  },

  updateSettings: async (locationId: string, data: Partial<TextBackSettings>) => {
    try {
      const response = await api.put(`/calls/${locationId}/settings`, data);
      set({ settings: response.data });
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Failed to update call settings') });
      throw error;
    }
  },

  selectThread: (thread) => set({ selectedThread: thread, messages: [] }),
  clearError: () => set({ error: null }),
}));
