// Source: WebRPA@5ccb900e, lib/utils.ts; see SOURCE.md for license and adaptation boundaries.
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
