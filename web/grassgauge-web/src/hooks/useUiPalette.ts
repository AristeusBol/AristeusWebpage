import { useMemo } from 'react';
import { useTheme } from './useTheme';

type Token = string;

const FN = {
  navy: '--aristeus-navy',
  green: '--aristeus-green',
  secondary: '--aristeus-secondary',
  graphite: '--technical-graphite',
  white: '--mineral-white',
  mist: '--mist-gray',
  navySoft: '--aristeus-navy-soft',
  navyCard: '--aristeus-navy-card',
  navyBorder: '--aristeus-navy-border',
  greenSoft: '--aristeus-green-soft',
  greenBright: '--aristeus-green-bright',
  goldSoft: '--aristeus-gold-soft',
  bgPrimary: '--bg-primary',
  bgSecondary: '--bg-secondary',
  bgCard: '--bg-card',
  textPrimary: '--text-primary',
  textSecondary: '--text-secondary',
  textInverse: '--text-inverse',
  borderSubtle: '--border-subtle',
  mapBg: '--map-bg',
  floatBg: '--float-bg',
  floatBgSoft: '--float-bg-soft',
  statusError: '--status-error',
  statusErrorMid: '--status-error-mid',
  statusErrorDark: '--status-error-dark',
  statusErrorLine: '--status-error-line',
  statusWarningBright: '--status-warning-bright',
  statusSuccessDot: '--status-success-dot',
  textMuted: '--text-muted',
  textFaint: '--text-faint',
  neutralLine: '--neutral-line',
  axisPrimary: '--text-primary',
  mapHintBg: '--map-hint-bg',
  mapHintTitle: '--map-hint-title',
  mapHintText: '--map-hint-text',
} satisfies Record<string, string>;

function cssVar(name: string, fallback: Token): Token {
  if (typeof window === 'undefined') return fallback;
  const v = window.getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function readAll(): Record<string, string> {
  const read = (k: keyof typeof FN) => cssVar(FN[k], '');
  return {
    navy: read('navy') || '#0B2341',
    green: read('green') || '#6BA539',
    secondary: read('secondary') || '#355E3B',
    graphite: read('graphite') || '#2B2F36',
    white: read('white') || '#F5F7F4',
    mist: read('mist') || '#D8DEE3',
    navySoft: read('navySoft') || '#152d4a',
    navyCard: read('navyCard') || '#13203a',
    navyBorder: read('navyBorder') || '#2a3f5e',
    greenSoft: read('greenSoft') || '#8FD14F',
    greenBright: read('greenBright') || '#A8E65D',
    goldSoft: read('goldSoft') || '#D4A84E',
    bgPrimary: read('bgPrimary') || '#F5F7F4',
    bgSecondary: read('bgSecondary') || '#D8DEE3',
    bgCard: read('bgCard') || '#FFFFFF',
    textPrimary: read('textPrimary') || '#2B2F36',
    textSecondary: read('textSecondary') || '#355E3B',
    textInverse: read('textInverse') || '#F5F7F4',
    borderSubtle: read('borderSubtle') || '#D8DEE3',
    mapBg: read('mapBg') || '#0b1f0b',
    floatBg: read('floatBg') || 'rgba(255,255,255,.94)',
    floatBgSoft: read('floatBgSoft') || 'rgba(255,255,255,.92)',
    statusError: read('statusError') || '#dc2626',
    statusErrorMid: read('statusErrorMid') || '#b91c1c',
    statusErrorDark: read('statusErrorDark') || '#991b1b',
    statusErrorLine: read('statusErrorLine') || '#fca5a5',
    statusWarningBright: read('statusWarningBright') || '#f59e0b',
    statusSuccessDot: read('statusSuccessDot') || '#22c55e',
    textMuted: read('textMuted') || '#6b7280',
    textFaint: read('textFaint') || '#9ca3af',
    neutralLine: read('neutralLine') || '#d1d5db',
    axisPrimary: read('axisPrimary') || '#2B2F36',
    mapHintBg: read('mapHintBg') || 'rgba(20,35,20,.92)',
    mapHintTitle: read('mapHintTitle') || '#fff',
    mapHintText: read('mapHintText') || '#e7f6e3',
  };
}

/** Lectura puntual (sin hook) de los UI tokens del tema activo. */
export function uiPalette(): ReturnType<typeof readAll> {
  return readAll();
}

/** Lee los UI tokens del tema activo (una vez por `theme`). */
export function useUiPalette() {
  const { theme } = useTheme();

  return useMemo(readAll, [theme]);
}