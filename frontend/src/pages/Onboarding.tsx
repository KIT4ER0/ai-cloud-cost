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
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';

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

    // Step 2 State
    const [externalId] = useState("APP-12345-XYZ"); // Mocked ID
    const [roleArn, setRoleArn] = useState("");
    const [isVerifying, setIsVerifying] = useState(false);
    const [isCopied, setIsCopied] = useState(false);

    // Form Hook
    const { register, handleSubmit, formState: { errors } } = useForm<AccountFormValues>({
        resolver: zodResolver(accountSchema),
    });

    const onAccountSubmit = async (data: AccountFormValues) => {
        try {
            await api.auth.register({ email: data.email, password: data.password });
            setStep(2);
        } catch (error: any) {
            console.error("Registration failed:", error);
            // You might want to set a form error here if you had a general error field
            alert(error.message || "Registration failed");
        }
    };

    const copyToClipboard = () => {
        navigator.clipboard.writeText(externalId);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
    };

    const handleVerify = () => {
        if (!roleArn) return; // Add better validation if needed
        setIsVerifying(true);
        // Simulate verification
        setTimeout(() => {
            setIsVerifying(false);
            navigate('/'); // Redirect to dashboard after success
        }, 2000);
    };

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
            <div className="max-w-md w-full">
                {/* Stepper / Progress */}
                <div className="mb-8 flex items-center justify-center space-x-4">
                    <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 ${step >= 1 ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-300 text-slate-400'}`}>
                        1
                    </div>
                    <div className={`h-1 w-16 ${step >= 2 ? 'bg-blue-600' : 'bg-slate-300'}`} />
                    <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 ${step >= 2 ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-300 text-slate-400'}`}>
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
                            <Card className="shadow-lg border-slate-200">
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
                                    <CardFooter>
                                        <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700">
                                            Create Account
                                        </Button>
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
                            <Card className="shadow-lg border-slate-200">
                                <CardHeader>
                                    <CardTitle className="text-2xl font-bold text-slate-800 flex items-center gap-2">
                                        <Cloud className="h-6 w-6 text-blue-600" />
                                        Connect AWS
                                    </CardTitle>
                                    <CardDescription>
                                        Securely connect your AWS account using IAM Role Delegation.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    {/* Action 1: External ID */}
                                    <div className="space-y-2">
                                        <div className="flex justify-between items-center">
                                            <Label className="font-semibold text-slate-700">External ID</Label>
                                            <span className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded">Required for Security</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <code className="flex-1 bg-slate-100 p-2 rounded border border-slate-200 text-sm font-mono text-slate-600">
                                                {externalId}
                                            </code>
                                            <Button variant="outline" size="icon" onClick={copyToClipboard} title="Copy External ID">
                                                {isCopied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                                            </Button>
                                        </div>
                                        <p className="text-xs text-slate-500 mt-1">
                                            Use this ID when creating your IAM Role to prevent the "Confused Deputy" problem.
                                        </p>
                                    </div>

                                    {/* Action 2: AWS Console Link */}
                                    <div className="pt-2">
                                        <Button variant="outline" className="w-full border-dashed border-slate-300 text-slate-600 hover:text-blue-600 hover:border-blue-300" asChild>
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
                                        className="w-full bg-blue-600 hover:bg-blue-700"
                                        onClick={handleVerify}
                                        disabled={isVerifying || !roleArn}
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
