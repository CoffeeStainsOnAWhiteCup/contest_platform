import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

type Variant = "neutral" | "success" | "danger" | "warning" | "info";

const variants: Record<Variant, string> = {
  neutral: "border-border bg-muted text-muted-foreground",
  success: "border-green-300 bg-green-50 text-green-800",
  danger: "border-red-300 bg-red-50 text-red-800",
  warning: "border-amber-300 bg-amber-50 text-amber-800",
  info: "border-blue-300 bg-blue-50 text-blue-800",
};

export function Badge({
  variant = "neutral",
  className,
  children,
}: {
  variant?: Variant;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
