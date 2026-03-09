import { useEffect, useState } from "react"
import { useAuthStore } from "@/store/useAuthStore"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { User, Mail, Key, IdCard, Loader2, Eye, EyeOff } from "lucide-react"
import { api } from "@/lib/api"

interface UserProfileData {
    aws_role_arn?: string | null;
    aws_external_id?: string | null;
}

function MaskedField({ value, fallback }: { value?: string | null; fallback: string }) {
    const [visible, setVisible] = useState(false);

    if (!value) {
        return <span className="text-muted-foreground italic">{fallback}</span>;
    }

    return (
        <span className="flex items-center justify-between gap-2">
            <span className="min-w-0 break-all">
                {visible ? value : "••••••••••••••••"}
            </span>
            <button
                type="button"
                onClick={() => setVisible((v) => !v)}
                className="shrink-0 p-1 rounded-md hover:bg-accent transition-colors"
                aria-label={visible ? "Hide value" : "Show value"}
            >
                {visible ? (
                    <EyeOff className="h-4 w-4 text-muted-foreground" />
                ) : (
                    <Eye className="h-4 w-4 text-muted-foreground" />
                )}
            </button>
        </span>
    );
}

export default function Profile() {
    const user = useAuthStore((state) => state.user)
    const [profileData, setProfileData] = useState<UserProfileData | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const data = await api.auth.me();
                setProfileData(data);
            } catch (error) {
                console.error("Failed to fetch profile:", error);
            } finally {
                setLoading(false);
            }
        };

        if (user) {
            fetchProfile();
        } else {
            setLoading(false);
        }
    }, [user]);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">User Profile</h1>
                <p className="text-muted-foreground mt-2">
                    Manage your account settings and preferences.
                </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">
                            Account Detail
                        </CardTitle>
                        <User className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center space-x-2 mt-4">
                            <Mail className="h-5 w-5 text-muted-foreground shrink-0" />
                            <div className="text-lg font-medium truncate" title={user?.email || ""}>
                                {user?.email || "No email found"}
                            </div>
                        </div>

                        <div className="mt-6 space-y-4">
                            <div className="space-y-1">
                                <div className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                                    <Key className="h-4 w-4" />
                                    External ID
                                </div>
                                <div className="text-sm font-mono bg-muted p-2 rounded-md break-all">
                                    {loading ? (
                                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                    ) : (
                                        <MaskedField value={profileData?.aws_external_id} fallback="Not generated" />
                                    )}
                                </div>
                            </div>

                            <div className="space-y-1">
                                <div className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                                    <IdCard className="h-4 w-4" />
                                    AWS Role ARN
                                </div>
                                <div className="text-sm font-mono bg-muted p-2 rounded-md break-all">
                                    {loading ? (
                                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                    ) : (
                                        <MaskedField value={profileData?.aws_role_arn} fallback="Not connected" />
                                    )}
                                </div>
                            </div>
                        </div>

                        <CardDescription className="mt-6">
                            This is the account currently authenticated with Supabase.
                        </CardDescription>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
