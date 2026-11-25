export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  readonly retryAfter?: number;

  constructor(message: string, status: number, detail: unknown, retryAfter?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.retryAfter = retryAfter;
  }

  /** Machine-readable code when the backend returns a plain string detail. */
  get code(): string | null {
    return typeof this.detail === "string" ? this.detail : null;
  }
}

const detailLabels = new Map([
  ["Account blocked", "Аккаунт заблокирован."],
  ["Email is already registered", "Этот email уже зарегистрирован."],
]);

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) {
      const wait = error.retryAfter ?? 60;
      return `Слишком много запросов. Повторите через ${wait} с.`;
    }
    if (typeof error.detail === "string") {
      return detailLabels.get(error.detail) ?? error.detail;
    }
    return `Ошибка ${error.status}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Неизвестная ошибка";
}
