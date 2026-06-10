import { create } from 'zustand';

import { clearAccessToken, hasAccessToken, setAccessToken } from '@/lib/auth-token';

interface User {
  id: string;
  email: string;
  full_name?: string;
  company_name?: string;
  role: string;
  notification_channel: string;
  phone?: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  login: (token: string, user?: User | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  isAuthenticated: hasAccessToken(),
  isLoading: true,
  setUser: (user) =>
    set({
      user,
      isAuthenticated: !!user || hasAccessToken(),
    }),
  setLoading: (isLoading) => set({ isLoading }),
  login: (token, user = null) => {
    setAccessToken(token);
    set({ user, isAuthenticated: true, isLoading: false });
  },
  logout: () => {
    clearAccessToken();
    set({ user: null, isAuthenticated: false, isLoading: false });
  },
}));
