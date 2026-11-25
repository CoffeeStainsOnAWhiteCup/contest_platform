import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { API_BASE } from "@/api/config";
import { errorMessage } from "@/api/errors";
import { useAuth } from "@/auth/context";
import { Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/form";
import { Button } from "@/components/ui/button";

const schema = z.object({
  email: z.string().min(1, "Введите email").email("Некорректный email"),
  password: z.string().min(1, "Введите пароль"),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  const from = (location.state as { from?: string } | null)?.from ?? "/";

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      await login(values.email, values.password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <Card title="Вход">
        <form className="space-y-3" onSubmit={handleSubmit(onSubmit)} noValidate>
          {error && <Alert variant="error">{error}</Alert>}
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" {...register("email")} />
            <FieldError>{errors.email?.message}</FieldError>
          </div>
          <div>
            <Label htmlFor="password">Пароль</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...register("password")}
            />
            <FieldError>{errors.password?.message}</FieldError>
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Входим…" : "Войти"}
          </Button>
          <a
            href={`${API_BASE}/auth/github`}
            className="flex h-9 w-full items-center justify-center rounded border border-border bg-background text-sm font-medium hover:bg-muted"
          >
            Войти через GitHub
          </a>
          <p className="text-center text-sm text-muted-foreground">
            Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
          </p>
        </form>
      </Card>
    </div>
  );
}
