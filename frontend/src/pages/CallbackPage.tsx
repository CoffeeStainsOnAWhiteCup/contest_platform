import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "@/auth/context";
import { Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";

const MESSAGES: Record<string, string> = {
  OAUTH_ACCESS_DENIED: "Вы отменили вход через GitHub.",
  INVALID_OAUTH_STATE: "Ссылка входа устарела. Начните вход ещё раз.",
  INVALID_OAUTH_CODE: "Код входа недействителен. Начните вход ещё раз.",
  OAUTH_CONFIG_ERROR: "Вход через GitHub сейчас не настроен.",
  OAUTH_PROVIDER_UNAVAILABLE: "GitHub временно недоступен. Попробуйте позже.",
  INVALID_OAUTH_TICKET: "Ссылка входа устарела или уже использована. Попробуйте снова.",
  OAUTH_EMAIL_CONFLICT: "Этот email уже привязан к другому аккаунту.",
  OAUTH_VERIFIED_EMAIL_REQUIRED: "GitHub не подтвердил основной email.",
};

function describe(error: unknown): string {
  const code = (error as { code?: string } | null)?.code;
  if (code && Object.prototype.hasOwnProperty.call(MESSAGES, code)) {
    return MESSAGES[code];
  }
  return "Не удалось завершить вход через GitHub.";
}

export function CallbackPage() {
  const { loginWithGitHub, user } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const providerError = params.get("error");
  const [exchangeError, setError] = useState<string | null>(null);
  const error = providerError !== null ? describe({ code: providerError }) : exchangeError;
  const started = useRef(false);

  useEffect(() => {
    if (providerError !== null || started.current) {
      return;
    }
    started.current = true;
    loginWithGitHub()
      .then(() => navigate("/", { replace: true }))
      .catch((err: unknown) => setError(describe(err)));
  }, [loginWithGitHub, navigate, providerError]);

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
