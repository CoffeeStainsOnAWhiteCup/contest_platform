import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="space-y-2">
      <h1 className="text-xl font-semibold">Страница не найдена</h1>
      <p className="text-sm text-muted-foreground">
        <Link to="/">Вернуться на главную</Link>
      </p>
    </div>
  );
}
