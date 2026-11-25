import type { BadgeVariant } from "@/components/ui/badge";
import type { ContestStatus, Language, SubmissionStatus, VerdictStatus } from "@/api/types";

type ContestPhase = ContestStatus | "scheduled";

const CONTEST_LABELS: Record<ContestPhase, string> = {
  scheduled: "Ожидает старта",
  draft: "Черновик",
  published: "Опубликован",
  active: "Идёт",
  finished: "Завершён",
  archived: "В архиве",
};

const CONTEST_VARIANTS: Record<ContestPhase, BadgeVariant> = {
  scheduled: "info",
  draft: "neutral",
  published: "info",
  active: "success",
  finished: "neutral",
  archived: "neutral",
};

export function contestStatusLabel(status: ContestPhase): string {
  return CONTEST_LABELS[status];
}

export function contestStatusVariant(status: ContestPhase): BadgeVariant {
  return CONTEST_VARIANTS[status];
}

export const VERDICT_LABELS: Record<VerdictStatus, string> = {
  ACCEPTED: "Принято",
  WRONG_ANSWER: "Неверный ответ",
  COMPILE_ERROR: "Ошибка компиляции",
  RUNTIME_ERROR: "Ошибка выполнения",
  TIME_LIMIT_EXCEEDED: "Превышен лимит времени",
  MEMORY_LIMIT_EXCEEDED: "Превышен лимит памяти",
  SYSTEM_ERROR: "Системная ошибка",
};

const VERDICT_VARIANTS: Record<VerdictStatus, BadgeVariant> = {
  ACCEPTED: "success",
  WRONG_ANSWER: "danger",
  COMPILE_ERROR: "warning",
  RUNTIME_ERROR: "danger",
  TIME_LIMIT_EXCEEDED: "warning",
  MEMORY_LIMIT_EXCEEDED: "warning",
  SYSTEM_ERROR: "neutral",
};

export function verdictLabel(status: VerdictStatus): string {
  return VERDICT_LABELS[status];
}

export function verdictVariant(status: VerdictStatus): BadgeVariant {
  return VERDICT_VARIANTS[status];
}

export const SUBMISSION_LABELS: Record<SubmissionStatus, string> = {
  PENDING: "В очереди",
  RUNNING: "Проверяется",
  ...VERDICT_LABELS,
};

export function submissionLabel(status: SubmissionStatus): string {
  return SUBMISSION_LABELS[status];
}

export function submissionVariant(status: SubmissionStatus): BadgeVariant {
  if (status === "PENDING" || status === "RUNNING") {
    return "info";
  }
  return VERDICT_VARIANTS[status];
}

export function isInProgress(status: SubmissionStatus): boolean {
  return status === "PENDING" || status === "RUNNING";
}

export const LANGUAGE_LABELS: Record<Language, string> = {
  python: "Python",
  cpp: "C++",
  java: "Java",
};
