import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/context";
import { Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";

const MESSAGES: Record<string, string> = {
  INVALID_OAUTH_TICKET: "Ссылка входа устарела или уже использована. Попробуйте снова.",
  OAUTH_EMAIL_CONFLICT: "Этот email уже привязан к другому аккаунту.",
  OAUTH_VERIFIED_EMAIL_REQUIRED: "GitHub не подтвердил основной email.",
};

function describe(error: unknown): string {
  const code = (error as { code?: string } | null)?.code;
  if (code && MESSAGES[code]) {
    return MESSAGES[code];
  }
  return "Не удалось завершить вход через GitHub.";
}

export function CallbackPage() {
  const { loginWithGitHub, user } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) {
      return;
    }
    started.current = true;
    loginWithGitHub()
      .then(() => navigate("/", { replace: true }))
      .catch((err: unknown) => setError(describe(err)));
  }, [loginWithGitHub, navigate]);

  return (
    <div className="mx-auto max-w-sm">
      <Card title="Вход через GitHub">
        {error ? (
          <div className="space-y-3">
            <Alert variant="error">{error}</Alert>
            <Link to="/login">Вернуться ко входу</Link>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {user ? "Вход выполнен, перенаправляем…" : "Завершаем вход…"}
          </p>
        )}
      </Card>
    </div>
  );
}
