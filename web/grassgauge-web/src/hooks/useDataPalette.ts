import { useMemo } from 'react'
import { useTheme } from './useTheme'

function resolveCSSVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const v = window.getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

export interface DataPalette {
  verde: string
  muerta: string
  total: string
  deltaUp: string
  deltaDown: string
  swatchOff: string
}

/** Colores de datos (masa seca) resueltos del tema activo, para usar en
 *  atributos SVG/Canvas donde `var()` no se evalúa.
 *  Fuente de valores: web/shared/brand.tokens.css (sección data semantics). */
export function useDataPalette(): DataPalette {
  const { theme } = useTheme()
  return useMemo(
    () => ({
      verde: resolveCSSVar('--densidad-verde', '#059669'),
      muerta: resolveCSSVar('--densidad-muerta', '#78350f'),
      total: resolveCSSVar('--densidad-total', '#111827'),
      deltaUp: resolveCSSVar('--delta-up', '#15803d'),
      deltaDown: resolveCSSVar('--delta-down', '#b91c1c'),
      swatchOff: '#d4dcd3',
    }),
    [theme],
  )
}