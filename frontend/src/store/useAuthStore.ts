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
    logout: () => Promise<void>;
    initialize: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    isAuthenticated: false,
    user: null,
    token: localStorage.getItem('token'),
    initialize: async () => {
        try {
            const { data: { session } } = await supabase.auth.getSession();
            if (session) {
                const token = session.access_token;
                localStorage.setItem('token', token);
                set({ 
                    isAuthenticated: true, 
                    user: { email: session.user.email || '' }, 
                    token 
                });
            } else {
                // Fallback to localStorage token if session is not immediately available
                // but usually getSession handles this.
                const token = localStorage.getItem('token');
                if (token) {
                    const { data: { user } } = await supabase.auth.getUser(token);
                    if (user) {
                        set({ 
                            isAuthenticated: true, 
                            user: { email: user.email || '' }, 
                            token 
                        });
                    } else {
                        localStorage.removeItem('token');
                        set({ isAuthenticated: false, user: null, token: null });
                    }
                } else {
                    set({ isAuthenticated: false, user: null, token: null });
                }
            }
        } catch (error) {
            console.error("Initialization failed:", error);
            set({ isAuthenticated: false, user: null, token: null });
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
