import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatNumber(value: number | null | undefined) {
  return (value ?? 0).toLocaleString('es-AR')
}

export function formatCurrency(value: number | null | undefined) {
  return `$${(value ?? 0).toFixed(4)}`
}
