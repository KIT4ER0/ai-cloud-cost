import { create } from 'zustand';
import { api } from '@/lib/api';

interface User {
    email: string;
}

interface AuthState {
    isAuthenticated: boolean;
    user: User | null;
    token: string | null;
    login: (data: any) => Promise<void>;
    logout: () => void;
    initialize: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    isAuthenticated: false,
    user: null,
    token: localStorage.getItem('token'),
    initialize: () => {
        const token = localStorage.getItem('token');
        if (token) {
            set({ isAuthenticated: true, token });
        }
    },
    login: async (data) => {
        try {
            const response = await api.auth.login({ email: data.email, password: data.password });
            const token = response.access_token;
            localStorage.setItem('token', token);
            set({ isAuthenticated: true, user: { email: data.email }, token });
        } catch (error) {
            console.error("Login failed:", error);
            throw error;
        }
    },
    logout: () => {
        localStorage.removeItem('token');
        set({ isAuthenticated: false, user: null, token: null });
    },
}));

