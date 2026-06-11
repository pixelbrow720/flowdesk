"use client";

import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-turquoise text-base hover:opacity-90 border border-transparent",
  secondary:
    "bg-surface text-fg border border-border hover:border-turquoise/60",
  ghost: "bg-transparent text-fg border border-transparent hover:bg-surface",
  danger: "bg-crimson text-white hover:opacity-90 border border-transparent",
};

const SIZES: Record<Size, string> = {
  sm: "h-24 px-12 text-caption",
  md: "h-32 px-16 text-body",
};

/** Token-driven button. No hard-coded color/spacing. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", className, type = "button", ...rest }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-8 rounded font-display font-medium",
        "transition-[background,opacity,border] duration-base ease-standard",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise focus-visible:ring-offset-0",
        "disabled:cursor-not-allowed disabled:opacity-40",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    />
  ),
);
Button.displayName = "Button";
