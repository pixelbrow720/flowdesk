"use client";

import { useTheme } from "./theme-provider";
import { SegmentedControl } from "./ui/segmented-control";

/** Reusable theme switch (dark default). Used in /preview and the topbar. */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  return (
    <SegmentedControl
      ariaLabel="Theme"
      className={className}
      value={theme}
      onChange={setTheme}
      options={[
        { value: "dark", label: "DARK" },
        { value: "light", label: "LIGHT" },
      ]}
    />
  );
}
