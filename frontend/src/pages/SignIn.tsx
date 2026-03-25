import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useNavigate, Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, Cloud } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';

const signInSchema = z.object({
    email: z.string().email({ message: "Invalid email address" }),
    password: z.string().min(1, { message: "Password is required" }),
});

type SignInFormValues = z.infer<typeof signInSchema>;

export default function SignIn() {
    const navigate = useNavigate();
    const login = useAuthStore((state) => state.login);
    const [isLoading, setIsLoading] = useState(false);

    const { register, handleSubmit, formState: { errors } } = useForm<SignInFormValues>({
        resolver: zodResolver(signInSchema),
    });

    const onSubmit = async (data: SignInFormValues) => {
        setIsLoading(true);
        try {
            await login(data);
            navigate('/');
        } catch (error: any) {
            console.error("Login failed:", error);
            alert(error.message || "Invalid email or password");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen relative flex items-center justify-center p-4 overflow-hidden"
             style={{ background: 'linear-gradient(135deg, #1a0033 0%, #49068C 40%, #6b21a8 70%, #3b0764 100%)' }}>

            {/* Animated floating orbs */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute -top-20 -left-20 w-72 h-72 rounded-full opacity-20"
                     style={{
                         background: 'radial-gradient(circle, rgba(168,85,247,0.6) 0%, transparent 70%)',
                         animation: 'float 8s ease-in-out infinite',
                     }} />
                <div className="absolute top-1/3 -right-16 w-96 h-96 rounded-full opacity-15"
                     style={{
                         background: 'radial-gradient(circle, rgba(139,92,246,0.5) 0%, transparent 70%)',
                         animation: 'float 10s ease-in-out infinite reverse',
                     }} />
                <div className="absolute -bottom-32 left-1/4 w-80 h-80 rounded-full opacity-20"
                     style={{
                         background: 'radial-gradient(circle, rgba(192,132,252,0.4) 0%, transparent 70%)',
                         animation: 'float 12s ease-in-out infinite 2s',
                     }} />
                <div className="absolute top-10 right-1/3 w-48 h-48 rounded-full opacity-10"
                     style={{
                         background: 'radial-gradient(circle, rgba(233,213,255,0.5) 0%, transparent 70%)',
                         animation: 'float 7s ease-in-out infinite 1s',
                     }} />
            </div>

            {/* CSS keyframes for floating animation */}
            <style>{`
                @keyframes float {
                    0%, 100% { transform: translateY(0px) scale(1); }
                    50% { transform: translateY(-30px) scale(1.05); }
                }
                @keyframes fadeInUp {
                    from { opacity: 0; transform: translateY(24px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `}</style>

            {/* Main content */}
            <div className="relative z-10 w-full max-w-md"
                 style={{ animation: 'fadeInUp 0.6s ease-out' }}>

                {/* Branding */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
                         style={{
                             background: 'linear-gradient(135deg, rgba(168,85,247,0.3) 0%, rgba(139,92,246,0.2) 100%)',
                             backdropFilter: 'blur(12px)',
                             border: '1px solid rgba(255,255,255,0.15)',
                         }}>
                        <Cloud className="h-8 w-8 text-purple-200" />
                    </div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">
                        Cloud Cost Optimization Tool
                    </h1>
                    <p className="text-purple-200/70 text-sm mt-1">
                        Manage and optimize your cloud spending
                    </p>
                </div>

                {/* Sign In Card — Glassmorphism */}
                <Card className="border-0 shadow-2xl rounded-xl" style={{ backgroundColor: '#ffffff' }}>
                    <CardHeader>
                        <CardTitle className="text-xl font-bold text-slate-800">Sign In</CardTitle>
                        <CardDescription className="text-slate-500">
                            Welcome back! Please sign in to continue.
                        </CardDescription>
                    </CardHeader>
                    <form onSubmit={handleSubmit(onSubmit)}>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="email">Email</Label>
                                <Input
                                    id="email"
                                    type="email"
                                    placeholder="you@company.com"
                                    {...register("email")}
                                />
                                {errors.email && <p className="text-sm text-red-500">{errors.email.message}</p>}
                            </div>
                            <div className="space-y-2">
                                <div className="flex justify-between items-center">
                                    <Label htmlFor="password">Password</Label>
                                    <Link to="#" className="text-xs text-purple-600 hover:text-purple-800 transition-colors">
                                        Forgot password?
                                    </Link>
                                </div>
                                <Input
                                    id="password"
                                    type="password"
                                    {...register("password")}
                                />
                                {errors.password && <p className="text-sm text-red-500">{errors.password.message}</p>}
                            </div>
                        </CardContent>
                        <CardFooter className="flex flex-col gap-4">
                            <Button
                                type="submit"
                                className="w-full font-semibold text-white transition-all duration-200"
                                style={{
                                    background: 'linear-gradient(135deg, #7c3aed 0%, #6d28d9 50%, #5b21b6 100%)',
                                    boxShadow: '0 4px 15px rgba(124, 58, 237, 0.4)',
                                }}
                                disabled={isLoading}
                            >
                                {isLoading ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Signing in...
                                    </>
                                ) : (
                                    "Sign In"
                                )}
                            </Button>
                            <div className="text-center text-sm text-slate-500">
                                Don't have an account?{' '}
                                <Link to="/onboarding" className="text-purple-600 hover:text-purple-800 font-medium transition-colors">
                                    Sign up
                                </Link>
                            </div>
                        </CardFooter>
                    </form>
                </Card>
            </div>
        </div>
    );
}
