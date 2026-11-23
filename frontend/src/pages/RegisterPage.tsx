import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/auth/context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/form";

const schema = z
  .object({
    name: z.string().trim().min(1, "Введите имя").max(100, "Не более 100 символов"),
    email: z.string().min(1, "Введите email").email("Некорректный email"),
    password: z
      .string()
      .min(8, "Минимум 8 символов")
      .max(128, "Не более 128 символов")
      .regex(/[A-Za-z]/, "Нужна хотя бы одна буква")
      .regex(/[0-9]/, "Нужна хотя бы одна цифра"),
    confirm: z.string().min(1, "Повторите пароль"),
  })
  .refine((data) => data.password === data.confirm, {
    path: ["confirm"],
    message: "Пароли не совпадают",
  });

type FormValues = z.infer<typeof schema>;

export function RegisterPage() {
  const { register: registerUser } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", email: "", password: "", confirm: "" },
  });

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      await registerUser(values.name, values.email, values.password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <Card title="Регистрация">
        <form className="space-y-3" onSubmit={handleSubmit(onSubmit)} noValidate>
          {error && <Alert variant="error">{error}</Alert>}
          <div>
            <Label htmlFor="name">Имя</Label>
            <Input id="name" autoComplete="name" {...register("name")} />
            <FieldError>{errors.name?.message}</FieldError>
          </div>
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
              autoComplete="new-password"
              {...register("password")}
            />
            <FieldError>{errors.password?.message}</FieldError>
          </div>
          <div>
            <Label htmlFor="confirm">Повторите пароль</Label>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              {...register("confirm")}
            />
            <FieldError>{errors.confirm?.message}</FieldError>
          </div>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Создаём…" : "Создать аккаунт"}
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Уже есть аккаунт? <Link to="/login">Войти</Link>
          </p>
        </form>
      </Card>
    </div>
  );
}
