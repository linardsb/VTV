/**
 * Returns an array of page numbers and ellipsis markers for compact pagination.
 * Always shows first page, last page, current page ± 1 neighbor, and ellipsis gaps.
 * Maximum 7 items rendered (e.g., [1, "…", 4, 5, 6, "…", 84]).
 */
export function getPageRange(
  current: number,
  total: number,
): (number | "ellipsis")[] {
  if (total <= 5) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | "ellipsis")[] = [];
  const showLeftEllipsis = current > 3;
  const showRightEllipsis = current < total - 2;

  // Always show first page
  pages.push(1);

  if (showLeftEllipsis) {
    pages.push("ellipsis");
  } else {
    // Show pages 2, 3 when near the start
    for (let i = 2; i < Math.min(current, 4); i++) {
      pages.push(i);
    }
  }

  // Current page and neighbors (ensure within bounds and not duplicating first/last)
  const rangeStart = Math.max(2, current - 1);
  const rangeEnd = Math.min(total - 1, current + 1);
  for (let i = rangeStart; i <= rangeEnd; i++) {
    if (!pages.includes(i)) {
      pages.push(i);
    }
  }

  if (showRightEllipsis) {
    pages.push("ellipsis");
  } else {
    // Show pages near the end
    for (let i = Math.max(total - 2, current + 1); i < total; i++) {
      if (!pages.includes(i)) {
        pages.push(i);
      }
    }
  }

  // Always show last page
  if (!pages.includes(total)) {
    pages.push(total);
  }

  return pages;
}
