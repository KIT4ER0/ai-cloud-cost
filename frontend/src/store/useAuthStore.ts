import { create } from 'zustand';

interface User {
    email: string;
    name?: string;
}

interface AuthState {
    isAuthenticated: boolean;
    user: User | null;
    login: (email: string) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    isAuthenticated: false,
    user: null,
    login: (email: string) => set({ isAuthenticated: true, user: { email } }),
    logout: () => set({ isAuthenticated: false, user: null }),
}));
