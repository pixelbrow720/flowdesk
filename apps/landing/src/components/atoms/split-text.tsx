"use client";

import { motion } from "motion/react";
import { stagger, ease } from "@/lib/motion-presets";
import clsx from "clsx";

/**
 * Split text into spans, masked, rises from below.
 * Use for hero/section headlines where you want operator-grade reveal.
 */
export function SplitText({
  text,
  as: Tag = "span",
  className,
  delay = 0,
  by = "word",
  once = true,
}: {
  text: string;
  as?: keyof React.JSX.IntrinsicElements;
  className?: string;
  delay?: number;
  by?: "word" | "char" | "line";
  once?: boolean;
}) {
  const tokens =
    by === "char" ? text.split("") : by === "line" ? text.split(/\n/) : text.split(" ");
  const stride = by === "char" ? 0.012 : by === "line" ? stagger.line : stagger.word;

  // motion can't render arbitrary tag string easily — use span wrapper to be safe
  const Wrapper = Tag as React.ElementType;

  return (
    <Wrapper className={clsx("inline-block", className)} aria-label={text}>
      {tokens.map((tok, i) => (
        <span key={i} className="inline-block overflow-hidden align-baseline">
          <motion.span
            aria-hidden
            className="inline-block will-change-transform"
            initial={{ y: "110%" }}
            whileInView={{ y: "0%" }}
            viewport={{ once, margin: "0px 0px -10% 0px" }}
            transition={{ duration: 0.9, ease, delay: delay + i * stride }}
            style={{ transition: undefined }}
          >
            {tok}
            {by === "word" && i < tokens.length - 1 ? "\u00A0" : ""}
          </motion.span>
        </span>
      ))}
    </Wrapper>
  );
}
