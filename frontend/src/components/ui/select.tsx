import * as React from "react";

import { cn } from "@/lib/utils";

/** Thin Tailwind skin over the native <select> — full Radix Select isn't worth the weight here. */
function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-8 rounded-md border border-input bg-card px-2 text-sm shadow-xs outline-none transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30",
        className,
      )}
      {...props}
    />
  );
}

export { Select };
