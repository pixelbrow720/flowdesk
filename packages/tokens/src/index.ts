/**
 * @flowdesk/tokens — public surface.
 *
 * - Token constants: `import { TURQUOISE, spacing, typeScale } from "@flowdesk/tokens"`
 * - Tailwind preset:  `import flowdeskPreset from "@flowdesk/tokens/tailwind-preset"`
 *                     (also re-exported here as `flowdeskPreset`)
 * - CSS variables:    `import "@flowdesk/tokens/tokens.css"`
 * - Font faces:       `import "@flowdesk/tokens/fonts.css"`
 */
export * from "./tokens";
export { default as flowdeskPreset } from "./tailwind-preset";
