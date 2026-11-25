import { Link } from "react-router-dom";

import { useAuth } from "@/auth/context";

export function HomePage() {
  const { user } = useAuth();

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Платформа олимпиад и хакатонов</h1>
      <p className="max-w-2xl text-sm text-muted-foreground">
        Сдача решений, автоматическая проверка кода и рейтинг. Выберите конкурс, откройте
        задачу и отправьте решение.
      </p>
      <div className="flex gap-3 text-sm">
        <Link to="/contests">Открыть список конкурсов</Link>
        <Link to="/rating">Глобальный рейтинг</Link>
      </div>
      {!user && (
        <p className="text-sm text-muted-foreground">
          Чтобы отправлять решения, <Link to="/login">войдите</Link> или{" "}
          <Link to="/register">зарегистрируйтесь</Link>.
        </p>
      )}
    </div>
  );
}
