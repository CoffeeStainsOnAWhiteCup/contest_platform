import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

type Variant = "info" | "error" | "success" | "warning";

const variants: Record<Variant, string> = {
  info: "border-blue-300 bg-blue-50 text-blue-900",
  error: "border-red-300 bg-red-50 text-red-900",
  success: "border-green-300 bg-green-50 text-green-900",
  warning: "border-amber-300 bg-amber-50 text-amber-900",
};

export function Alert({
  variant = "info",
  className,
  children,
}: {
  variant?: Variant;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("rounded border px-3 py-2 text-sm", variants[variant], className)}>
      {children}
    </div>
  );
}
