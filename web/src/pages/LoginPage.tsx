import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { useAuth } from "../lib/auth";

export function LoginPage() {
  const { isAuthenticated, isLoading, login, error, configured } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mb-2">
            <span className="text-2xl font-bold text-sangam-600">Sangam</span>
          </div>
          <CardTitle className="text-lg">Sign in</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground text-center">
            Accounts, passwords, and MFA are handled by the self-hosted Zitadel organization.
          </p>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button
            type="button"
            className="w-full"
            disabled={!configured || isLoading}
            onClick={() => {
              void login();
            }}
          >
            {isLoading ? "Please wait…" : "Continue with Zitadel"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
