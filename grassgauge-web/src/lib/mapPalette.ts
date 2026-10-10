// Chrome de mapa (MapLibre paint): colores FIJOS de contraste sobre satélite.
// EXCEPCIÓN TÉCNICA DOCUMENTADA: los paints MapLibre se construyen una sola vez
// y deben verse sobre la imagen satelital en ambos temas (light/dark), por lo
// que NO siguen la paleta de marca ni el tema activo. Centralizados aquí para
// no esparcir literales en los componentes.
// Origen de cada valor: versiones anteriores de GestionMapa/MapaMasaSeca/
// MapaRotacion/MapaPunto (no cambiar el look).

export const MAP_CHROME = {
  // Líneas base del potrero/pastura sobre satélite
  potreroLine: '#ffffff',
  potreroFill: '#ffffff',
  // Borde "casco" oscuro que separa la línea blanca del fondo
  potreroCasing: '#052e16',
  // Fondo oscuro del potrero (rotación muestra potrero lleno)
  potreroFillOscuro: '#233D39',
  // Selección: amarillo / cian según contexto (contraste alto)
  seleccionAmarillo: '#facc15',
  seleccionCyan: '#22d3ee',
  seleccionAmarilloLuz: '#fde047',
  // Destructivo / dibujo
  exclusionesRelleno: '#dc2626',
  exclusionesTexto: '#fecaca',
  exclusionesOscuro: '#111827',
  dibujoVerde: '#22c55e',
  dibujoBorde: '#f59e0b',
  // Texto y halo sobre satélite
  textoSatelite: '#ffffff',
  textoParcela: '#fefce8',
  halo: 'rgba(0,0,0,0.65)',
  haloFuerte: 'rgba(0,0,0,0.7)',
  // Borde de parcelas no seleccionadas
  parcelaLinea: '#e2e8f0',
  // Vértices del dibujo en curso
  verticeStroke: 'rgba(255,255,255,0.9)',
} as const;

/** Estados categóricos (rotación / masa seca): paleta de datos, excepción de marca. */
export const MAP_ESTADOS = {
  critico: '#ef4444',
  desarrollo: '#facc15',
  optimo: '#22c55e',
  maduro: '#8b5cf6',
  pasado: '#86198f',
  sinDato: '#9ca3af',
} as const;