import * as ProgressPrimitive from "@radix-ui/react-progress";
import * as React from "react";

import { cn } from "@/lib/utils";

function Progress({
  className,
  value,
  indeterminate,
  ...props
}: React.ComponentProps<typeof ProgressPrimitive.Root> & { indeterminate?: boolean }) {
  return (
    <ProgressPrimitive.Root
      className={cn("relative h-1 w-full overflow-hidden rounded-full bg-secondary", className)}
      value={value}
      {...props}
    >
      {indeterminate ? (
        <span className="absolute inset-y-0 left-0 w-1/3 animate-indeterminate-bar rounded-full bg-primary" />
      ) : (
        <ProgressPrimitive.Indicator
          className="h-full w-full flex-1 rounded-full bg-primary transition-transform duration-300"
          style={{ transform: `translateX(-${100 - (value ?? 0)}%)` }}
        />
      )}
    </ProgressPrimitive.Root>
  );
}

export { Progress };
