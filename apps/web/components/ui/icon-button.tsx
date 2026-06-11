"use client";

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "../../lib/cn";

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Accessible label — required since the button has no text. */
  label: string;
  children: ReactNode;
}

/** Square icon-only button. `label` becomes aria-label + title. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ label, children, className, type = "button", ...rest }, ref) => (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex h-32 w-32 items-center justify-center rounded text-fg",
        "border border-transparent bg-transparent hover:bg-surface",
        "transition-[background,border] duration-base ease-standard",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise",
        "disabled:cursor-not-allowed disabled:opacity-40",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  ),
);
IconButton.displayName = "IconButton";
