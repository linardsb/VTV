/**
 * Convert a backend color string (e.g. "FF7043") to CSS hex (e.g. "#FF7043").
 * Returns a default color if the input is null/undefined/empty.
 */
export function toHexColor(
  color: string | null | undefined,
  fallback = "#888888",
): string {
  if (!color) return fallback;
  return color.startsWith("#") ? color : `#${color}`;
}

/**
 * Convert a CSS hex color (e.g. "#FF7043") to the backend format (e.g. "FF7043").
 * Strips the leading "#" if present.
 */
export function fromHexColor(color: string): string {
  return color.startsWith("#") ? color.slice(1) : color;
}
