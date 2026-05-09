import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Tailwind class composer used by shadcn/ui copy-paste components and our
 * own components alike. Merges Tailwind classes intelligently so later
 * classes override earlier ones (e.g. `cn("px-2", "px-4")` → `px-4`).
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
