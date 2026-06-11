import { cn } from "../../lib/cn";

export interface DividerProps {
  orientation?: "horizontal" | "vertical";
  className?: string;
}

/** 1px hairline divider in the subtle border token. */
export function Divider({ orientation = "horizontal", className }: DividerProps) {
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      className={cn(
        "bg-border",
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        className,
      )}
    />
  );
}
