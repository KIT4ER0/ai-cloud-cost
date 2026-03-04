import { create } from 'zustand';
import { supabase } from '@/lib/supabase';

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
            const { data: authData, error } = await supabase.auth.signInWithPassword({
                email: data.email,
                password: data.password,
            });
            
            if (error) throw error;
            
            const token = authData.session?.access_token;
            if (token) {
                localStorage.setItem('token', token);
                set({ isAuthenticated: true, user: { email: data.email }, token });
            } else {
                throw new Error("No access token returned");
            }
        } catch (error) {
            console.error("Login failed:", error);
            throw error;
        }
    },
    logout: async () => {
        await supabase.auth.signOut();
        localStorage.removeItem('token');
        set({ isAuthenticated: false, user: null, token: null });
    },
}));
