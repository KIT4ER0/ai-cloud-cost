import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, Copy, ExternalLink, Cloud, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/useAuthStore';
import { supabase } from '@/lib/supabase';

// --- Step 1: Account Creation Schema ---
const accountSchema = z.object({
    email: z.string().email({ message: "Invalid email address" }),
    password: z.string().min(8, { message: "Password must be at least 8 characters" }),
    confirmPassword: z.string()
}).refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
});

type AccountFormValues = z.infer<typeof accountSchema>;

export default function Onboarding() {
    const [step, setStep] = useState(1);
    const navigate = useNavigate();
    const initialize = useAuthStore((state) => state.initialize);

    // Step 2 State
    const [externalId, setExternalId] = useState("");
    const [isLoadingExternalId, setIsLoadingExternalId] = useState(false);
    const [roleArn, setRoleArn] = useState("");
    const [isVerifying, setIsVerifying] = useState(false);
    const [isCopied, setIsCopied] = useState(false);
    const [error, setError] = useState("");

    // Form Hook
    const { register, handleSubmit, formState: { errors } } = useForm<AccountFormValues>({
        resolver: zodResolver(accountSchema),
    });

    const onAccountSubmit = async (data: AccountFormValues) => {
        try {
            setError("");
            const { data: authData, error: authError } = await supabase.auth.signUp({ 
                email: data.email, 
                password: data.password 
            });
            if (authError) throw authError;

            // Auto-login the user after registration
            const token = authData.session?.access_token;
            if (token) {
                localStorage.setItem('token', token);
            } else if (authData.user) {
                console.log("Registered without immediate session. May require email verification.");
            }

            // Generate external ID from backend
            setStep(2);
            setIsLoadingExternalId(true);
            try {
                const awsResp = await api.aws.generateExternalId();
                setExternalId(awsResp.external_id);
            } catch (err: any) {
                setError(err.message || "Failed to generate External ID");
            } finally {
                setIsLoadingExternalId(false);
            }
        } catch (error: any) {
            console.error("Registration failed:", error);
            alert(error.message || "Registration failed");
        }
    };

    const copyToClipboard = () => {
        navigator.clipboard.writeText(externalId);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
    };

    const handleVerify = async () => {
        if (!roleArn) return;
        setIsVerifying(true);
        setError("");
        try {
            await api.aws.connect({ role_arn: roleArn });
            initialize(); // Set auth state from saved token
            navigate('/');
        } catch (err: any) {
            setError(err.message || "Failed to connect AWS account");
        } finally {
            setIsVerifying(false);
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
            </div>

            {/* CSS keyframes */}
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
                <div className="text-center mb-6">
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
                        Get started in just 2 steps
                    </p>
                </div>

                {/* Stepper / Progress */}
                <div className="mb-6 flex items-center justify-center space-x-4">
                    <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 text-sm font-semibold transition-colors ${step >= 1 ? 'border-purple-400 bg-purple-500 text-white' : 'border-white/20 text-white/40'}`}>
                        1
                    </div>
                    <div className={`h-1 w-16 rounded-full transition-colors ${step >= 2 ? 'bg-purple-400' : 'bg-white/20'}`} />
                    <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 text-sm font-semibold transition-colors ${step >= 2 ? 'border-purple-400 bg-purple-500 text-white' : 'border-white/20 text-white/40'}`}>
                        2
                    </div>
                </div>

                <AnimatePresence mode="wait">
                    {step === 1 && (
                        <motion.div
                            key="step1"
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 20 }}
                            transition={{ duration: 0.3 }}
                        >
                            <Card className="shadow-2xl border-0 bg-white rounded-xl">
                                <CardHeader>
                                    <CardTitle className="text-2xl font-bold text-slate-800">Create Account</CardTitle>
                                    <CardDescription>Sign up to start managing your cloud costs.</CardDescription>
                                </CardHeader>
                                <form onSubmit={handleSubmit(onAccountSubmit)}>
                                    <CardContent className="space-y-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="email">Email</Label>
                                            <Input id="email" type="email" placeholder="you@company.com" {...register("email")} />
                                            {errors.email && <p className="text-sm text-red-500">{errors.email.message}</p>}
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="password">Password</Label>
                                            <Input id="password" type="password" {...register("password")} />
                                            {errors.password && <p className="text-sm text-red-500">{errors.password.message}</p>}
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="confirmPassword">Confirm Password</Label>
                                            <Input id="confirmPassword" type="password" {...register("confirmPassword")} />
                                            {errors.confirmPassword && <p className="text-sm text-red-500">{errors.confirmPassword.message}</p>}
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
                                        >
                                            Create Account
                                        </Button>
                                        <div className="text-center text-sm text-slate-500">
                                            Already have an account?{' '}
                                            <Link to="/signin" className="text-purple-600 hover:text-purple-800 font-medium transition-colors">
                                                Sign in
                                            </Link>
                                        </div>
                                    </CardFooter>
                                </form>
                            </Card>
                        </motion.div>
                    )}

                    {step === 2 && (
                        <motion.div
                            key="step2"
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 20 }}
                            transition={{ duration: 0.3 }}
                        >
                            <Card className="shadow-2xl border-0 bg-white rounded-xl">
                                <CardHeader>
                                    <CardTitle className="text-2xl font-bold text-slate-800 flex items-center gap-2">
                                        <Cloud className="h-6 w-6 text-purple-600" />
                                        Connect AWS
                                    </CardTitle>
                                    <CardDescription>
                                        Securely connect your AWS account using IAM Role Delegation.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    {/* Error Banner */}
                                    {error && (
                                        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded p-3">
                                            {error}
                                        </div>
                                    )}

                                    {/* Action 1: External ID */}
                                    <div className="space-y-2">
                                        <div className="flex justify-between items-center">
                                            <Label className="font-semibold text-slate-700">External ID</Label>
                                            <span className="text-xs text-purple-600 bg-purple-50 px-2 py-1 rounded font-medium">Required for Security</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <code className="flex-1 bg-slate-100 p-2 rounded border border-slate-200 text-sm font-mono text-slate-600">
                                                {isLoadingExternalId ? (
                                                    <span className="flex items-center gap-2 text-slate-400">
                                                        <Loader2 className="h-3 w-3 animate-spin" /> Generating...
                                                    </span>
                                                ) : (
                                                    externalId || "—"
                                                )}
                                            </code>
                                            <Button variant="outline" size="icon" onClick={copyToClipboard} disabled={isLoadingExternalId || !externalId} title="Copy External ID">
                                                {isCopied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                                            </Button>
                                        </div>
                                        <p className="text-xs text-slate-500 mt-1">
                                            Use this ID when creating your IAM Role to prevent the "Confused Deputy" problem.
                                        </p>
                                    </div>

                                    {/* Action 2: AWS Console Link */}
                                    <div className="pt-2">
                                        <Button variant="outline" className="w-full border-dashed border-slate-300 text-slate-600 hover:text-purple-600 hover:border-purple-300" asChild>
                                            <a href="https://console.aws.amazon.com/iam/home#/roles/create" target="_blank" rel="noopener noreferrer">
                                                <ExternalLink className="mr-2 h-4 w-4" />
                                                Go to AWS Console to Create Role
                                            </a>
                                        </Button>
                                    </div>

                                    {/* Action 3: Role ARN Input */}
                                    <div className="space-y-2 pt-2">
                                        <Label htmlFor="roleArn">Role ARN</Label>
                                        <Input
                                            id="roleArn"
                                            placeholder="arn:aws:iam::123456789012:role/MyCostToolRole"
                                            value={roleArn}
                                            onChange={(e) => setRoleArn(e.target.value)}
                                        />
                                        <p className="text-xs text-slate-500">
                                            Paste the ARN of the role you created.
                                        </p>
                                    </div>
                                </CardContent>
                                <CardFooter>
                                    <Button
                                        className="w-full font-semibold text-white transition-all duration-200"
                                        style={{
                                            background: 'linear-gradient(135deg, #7c3aed 0%, #6d28d9 50%, #5b21b6 100%)',
                                            boxShadow: '0 4px 15px rgba(124, 58, 237, 0.4)',
                                        }}
                                        onClick={handleVerify}
                                        disabled={isVerifying || !roleArn || isLoadingExternalId}
                                    >
                                        {isVerifying ? (
                                            <>
                                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                Verifying...
                                            </>
                                        ) : (
                                            "Connect & Verify"
                                        )}
                                    </Button>
                                </CardFooter>
                            </Card>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}
