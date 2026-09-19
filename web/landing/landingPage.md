Crea una landing page profesional multi-producto para ARISTEUS, una startup
de agtech boliviana que aplica Machine Learning y visión satelital/aérea
a la ganadería.

═══════════════════════════════════════════════════════════════
CONTEXTO DE MARCA
═══════════════════════════════════════════════════════════════

ARISTEUS es la empresa madre. Tiene dos productos:

1. GRASS GAUGE — Producto principal (listo para mercado)
   Usa ML + visión computacional para medir biomasa de pastizales,
   determinar contenido nutricional y generar planes de pastoreo
   optimizados. Evita la degradación de tierras por sobrepastoreo.

2. CATTLEVISION — Producto secundario (próximamente)
   Usa drones + LiDAR + visión artificial para estimar el peso
   del ganado sin estrés animal ni manejo físico.

LOGOS:
- Aristeus: letra "A" estilizada como compás de precisión en azul
  marino, con trazo curvo verde lima. Logotipo completo tiene
  detalles ganaderos (cuernos en T, cola en S).
  Archivos: aristeus-icon.png, aristeus-logo-full.png
  Ubicar en: public/images/logos/

- Grass Gauge: hojas verdes fusionadas con barras de gráfica
  y flechas ascendentes. Tipografía redondeada verde oscuro.
  Archivo: grassgauge-logo.png
  Ubicar en: public/images/logos/

- CattleVision: cabeza de toro en wireframe/polígonos low-poly,
  gris carbón con líneas doradas, lente de targeting en el ojo.
  Tipografía condensada técnica.
  Archivo: cattlevision-logo.png
  Ubicar en: public/images/logos/

═══════════════════════════════════════════════════════════════
STACK TÉCNICO
═══════════════════════════════════════════════════════════════

- Astro como framework
- Tailwind CSS para estilos
- Leaflet para mapas interactivos (con tiles oscuros CartoDB Dark Matter)
- Componentes .astro modulares
- Estructura multi-página: Home, Productos (Grass Gauge + CattleVision),
  Nosotros, Contacto
- Formulario con Netlify Forms (name="contact" netlify)
- i18n básico español/inglés con selector en header
- Deploy target: Netlify

═══════════════════════════════════════════════════════════════
IDENTIDAD VISUAL — EXTRAÍDA DE LOS LOGOS REALES
═══════════════════════════════════════════════════════════════

PALETA PRINCIPAL (Aristeus corporativa):
  --aristeus-navy:     #1B2A4A   (azul marino del logo - primario)
  --aristeus-green:    #7AB929   (verde lima del logo - secundario)
  --bg-primary:        #0D1117   (fondo principal oscuro)
  --bg-secondary:      #161B22   (fondo cards/secciones alternas)
  --bg-card:           #1C2333   (fondo glassmorphism cards)
  --text-primary:      #E8ECF1   (texto principal)
  --text-secondary:    #8B949E   (texto secundario)
  --border-subtle:     #30363D   (bordes sutiles)

PALETA GRASS GAUGE (secciones del producto pastoreo):
  --gg-green-dark:     #1B7A2B   (verde bosque)
  --gg-green-mid:      #4CAF50   (verde medio)
  --gg-green-light:    #7AB929   (verde lima)
  --gg-gradient:       linear-gradient(135deg, #1B7A2B, #7AB929)

PALETA CATTLEVISION (secciones del producto pesaje):
  --cv-charcoal:       #2C3E3E   (gris carbón)
  --cv-gold:           #B8963E   (dorado/ocre)
  --cv-dark:           #1A2424   (fondo oscuro tech)
  --cv-gradient:       linear-gradient(135deg, #2C3E3E, #B8963E)

TIPOGRAFÍA:
  --font-heading: 'Space Grotesk', sans-serif  (tech, precisa)
  --font-body: 'Inter', sans-serif             (legible, moderna)
  --font-data: 'JetBrains Mono', monospace     (datos, métricas)

ESTILO GENERAL:
  - Dark mode predominante
  - Glassmorphism sutil: background rgba + backdrop-blur + border sutil
  - Gradientes suaves para acentos
  - Cards con borde sutil (#30363D) y hover glow del color del producto
  - Imágenes con overlay oscuro (bg-primary con 60-70% opacidad)
  - Animaciones sobrias con Intersection Observer (fade-up, fade-in)
  - Transiciones suaves en hover (300ms ease)

═══════════════════════════════════════════════════════════════
ESTRUCTURA DE CARPETAS
═══════════════════════════════════════════════════════════════

aristeus-landing/
├─ public/
│  ├─ images/
│  │  ├─ logos/
│  │  │  ├─ aristeus-icon.png
│  │  │  ├─ aristeus-logo-full.png
│  │  │  ├─ grassgauge-logo.png
│  │  │  └─ cattlevision-logo.png
│  │  ├─ hero/
│  │  │  └─ (placeholder satelital)
│  │  ├─ products/
│  │  │  └─ (placeholders pastizales, ganado, drones)
│  │  └─ icons/
│  │     └─ (iconos SVG inline preferiblemente)
│  └─ favicon.svg (usar forma del ícono Aristeus)
├─ src/
│  ├─ components/
│  │  ├─ layout/
│  │  │  ├─ Nav.astro
│  │  │  ├─ Footer.astro
│  │  │  └─ Layout.astro
│  │  ├─ home/
│  │  │  ├─ Hero.astro
│  │  │  ├─ Problem.astro
│  │  │  ├─ Solution.astro
│  │  │  ├─ HowItWorks.astro
│  │  │  ├─ Products.astro
│  │  │  ├─ Benefits.astro
│  │  │  ├─ Technology.astro
│  │  │  ├─ Backing.astro
│  │  │  └─ CTAFinal.astro
│  │  ├─ products/
│  │  │  ├─ GrassGaugeHero.astro
│  │  │  ├─ GrassGaugeFeatures.astro
│  │  │  ├─ CattleVisionHero.astro
│  │  │  └─ CattleVisionFeatures.astro
│  │  ├─ shared/
│  │  │  ├─ FeatureCard.astro
│  │  │  ├─ MetricCard.astro
│  │  │  ├─ SectionTitle.astro
│  │  │  ├─ Button.astro
│  │  │  ├─ ContactForm.astro
│  │  │  ├─ MapDemo.astro (React island)
│  │  │  └─ LanguageSwitch.astro
│  │  └─ animations/
│  │     └─ ScrollReveal.astro
│  ├─ layouts/
│  │  └─ BaseLayout.astro
│  ├─ pages/
│  │  ├─ index.astro          (Home)
│  │  ├─ productos.astro      (Productos)
│  │  ├─ nosotros.astro       (Nosotros)
│  │  └─ contacto.astro       (Contacto)
│  ├─ styles/
│  │  └─ global.css           (variables CSS, base styles)
│  ├─ data/
│  │  ├─ es.json              (textos español)
│  │  └─ en.json              (textos inglés)
│  └─ utils/
│     └─ i18n.ts              (helper de idioma)
├─ astro.config.mjs
├─ tailwind.config.mjs
├─ netlify.toml
├─ package.json
└─ tsconfig.json

═══════════════════════════════════════════════════════════════
HOME PAGE — SECCIONES EN ORDEN
═══════════════════════════════════════════════════════════════

SECCIÓN 1: HERO
─────────────────
- Fondo: imagen satelital de pastizales vista desde arriba,
  oscurecida con overlay gradient (from #0D1117/80% to #0D1117/40%)
- Esquina superior: Nav con logo Aristeus (ícono + texto),
  menú (Inicio, Productos, Nosotros, Contacto), switch ES/EN,
  botón CTA "Solicitar Demo"
- Centro de la pantalla:
  - Badge pequeño: "🛰️ Tecnología validada en 3 continentes"
    con borde sutil y glassmorphism
  - Headline H1: "Inteligencia Artificial y visión computacional para una ganadería
    más rentable y sostenible"
  - Subheadline: "Medimos la biomasa de tus pastizales con
    Machine Learning para que cada hectárea rinda al máximo
    sin degradar tu tierra"
  - Dos botones:
    - Primario (verde #7AB929): "Solicita tu análisis gratuito"
    - Secundario (outline blanco): "Ver cómo funciona ↓"
- Abajo del hero: barra de métricas horizontal con glassmorphism:
  "10,000+ ha analizadas" | "94% precisión" | "3 continentes"
  Números en font-data (monospace), animados con counter al entrar

SECCIÓN 2: EL PROBLEMA
─────────────────────────
- Fondo: #161B22
- SectionTitle: "El sobrepastoreo está destruyendo las tierras
  ganaderas de Bolivia"
- Layout: dos columnas
  - Izquierda: imagen de tierra degradada/desertificada con
    overlay y stat grande superpuesta: "70%" con subtexto
    "de las tierras ganaderas sufren degradación"
  - Derecha: 3 pain points en lista con íconos rojos/naranjas:
    - "Pérdida de \$120 USD/ha/año por sobrepastoreo"
    - "Reducción de capacidad de carga año tras año"
    - "Decisiones de rotación basadas solo en intuición"
- Al final: frase puente: "¿Y si pudieras ver exactamente
  cuánto pasto tiene cada potrero antes de decidir?"

SECCIÓN 3: NUESTROS PRODUCTOS
────────────────────────────────
- Fondo: #0D1117
- SectionTitle: "Dos soluciones. Un objetivo: ganadería de precisión basada en datos."
- Layout: dos cards grandes lado a lado

  CARD GRASS GAUGE (borde izquierdo con --gg-gradient):
  - Logo Grass Gauge arriba
  - Título: "Grass Gauge"
  - Subtítulo: "Planificación de pastoreo con visión computacional"
  - Descripción breve: "Estimamos biomasa disponible (t MS/ha), calidad forrajera y generamos tu plan de rotación optimizado."
  - 3 features mini con ícono:
    - 🛰️ Relevamiento aéreo de alta resolución por ciclo de pastoreo
    - 🧠 ML para estimación de biomasa y nutrientes
    - 📋 Plan de pastoreo listo para ejecutar
  - Badge: "ACCESO ANTICIPADO"
  - Botón: "Explorar Grass Gauge →" (verde)

  CARD CATTLEVISION (borde izquierdo con --cv-gradient):
  - Logo CattleVision arriba
  - Título: "Cattle Vision"
  - Subtítulo: "Pesaje de ganado con drones y visión artificial"
  - Descripción breve: "Monitoreamos la ganancia de peso y condición corporal con visión computacional, sin estrés ni pesaje en brete."
  - 3 features mini con ícono:
    - 🚁 Fotogrametría y reconstrucción volumétrica 3D
    - 👁️ Modelos biométricos de estimación de peso individual
    - ⚖️ Curvas de evolución y ganancia diaria de peso (GDP)
  - Badge: "PRÓXIMAMENTE" (con borde dorado)
  - Botón: "Conocer Cattle Vision →" (dorado/outline)

SECCIÓN 4: CÓMO FUNCIONA GRASS GAUGE (producto principal)
──────────────────────────────────────────────────────────────
- Fondo: #161B22
- SectionTitle: "De la imagen aérea a tu plan de pastoreo
  en 3 pasos"
- Layout: 3 cards conectadas con línea/flecha horizontal
  - Paso 1: "Capturamos"
    Ícono: satélite
    "Obtenemos imágenes multiespectrales de tus potreros
    Relevamiento aéreo de alta resolución por ciclo de pastoreo vía satélite"
  - Paso 2: "Analizamos"
    Ícono: cerebro/red neuronal
    "Nuestro modelo de ML procesa las imágenes para estimar
    biomasa disponible y contenido nutricional"
  - Paso 3: "Planificamos"
    Ícono: clipboard/mapa
    "Recibes un plan de rotación optimizado: qué potrero
    usar, cuántas cabezas, por cuántos días"
- Animación: cada card aparece secuencialmente al scroll

SECCIÓN 5: DEMO VISUAL — MAPA INTERACTIVO
────────────────────────────────────────────
- Fondo: #0D1117
- SectionTitle: "Visualiza tu campo como nunca antes"
- Mapa Leaflet ocupando ~70% del ancho, centrado en
  coordenadas de Santa Cruz, Bolivia (-17.78, -63.18)
- Tiles: CartoDB Dark Matter
- 3 botones toggle arriba del mapa:
  - "Vista Satelital" → cambia tiles a Esri World Imagery
  - "Biomasa" → overlay heatmap simulado (verde a rojo)
  - "Plan Pastoreo" → polígonos de potreros con colores
    (verde = disponible, amarillo = en descanso, rojo = agotado)
- Card lateral (o inferior en mobile) mostrando datos ficticios:
  - Potrero seleccionado: "Potrero Norte - 45 ha"
  - Biomasa estimada: "2,450 kg MS/ha"
  - Estado nutricional: "Alto ●"
  - Recomendación: "Listo para pastoreo — 120 cabezas x 8 días"
- Nota al pie sutil: "Demo ilustrativa con datos de ejemplo"

SECCIÓN 6: BENEFICIOS TANGIBLES
─────────────────────────────────
- Fondo: #161B22
- SectionTitle: "Resultados que impactan tu operación"
- 4 MetricCards en grid (2x2 desktop, 1 col mobile):
  - Card 1: número "+40%" | "aumento en capacidad de carga"
    hover glow verde
  - Card 2: número "\$45 USD" | "ahorro por hectárea al año"
    hover glow verde
  - Card 3: número "5 años" | "más de vida útil del pastizal"
    hover glow verde
  - Card 4: número "15 días" | "frecuencia de actualización"
    hover glow verde
- Cada número en font-data, grande, con animación counter
- Debajo: mini calculadora ROI simple:
  "Ingresa tus hectáreas: [input] → Ahorro anual estimado: $X"

SECCIÓN 7: TECNOLOGÍA (sin saturar)
──────────────────────────────────────
- Fondo: #0D1117
- SectionTitle: "Tecnología de precisión para el campo"
- Layout: 3 columnas minimalistas
  - Columna 1: ícono dron + "Sensores Multiespectrales y RGB"
    + "Relevamiento aéreo centimétrico adaptado a la velocidad de rebrote y rotación de cada potrero."
  - Columna 2: ícono cerebro + "Visión Computacional e IA"
    + "Algoritmos avanzados calibrados para estimar biomasa disponible (kg MS/ha) y densidad forrajera."
  - Columna 3: ícono gráfica + "Modelación de Pastoreo Racional"
    + "Simulación de tasas de crecimiento, balance forrajero y asignación de carga animal en tiempo real."
- Abajo: línea visual tipo pipeline simplificado:
  Vuelo de Dron → Fotogrametría Cloud → Algoritmos IA → Plataforma Web → Plan de Pastoreo
- Badge: "Algoritmos entrenados con datasets forrajeros internacionales y calibrados en estancias de Bolivia."

SECCIÓN 8: RESPALDO
─────────────────────
- Fondo: #161B22
- SectionTitle: "Respaldados por"
- Grid de logos en escala de grises (placeholders por ahora):
  - Incubadoras
  - Clientes piloto
- Texto: "Más de 10,000 hectáreas analizadas en pilotos"

SECCIÓN 9: CTA FINAL
───────────────────────
- Fondo: gradient sutil desde #0D1117 hacia #1B2A4A
- Headline: "Solicita tu análisis gratuito de 100 hectáreas"
- Subheadline: "Sin compromiso. Recibe un reporte de biomasa
  de tu campo en 72 horas."
- Formulario Netlify Forms centrado:
  - Nombre completo
  - Email
  - Teléfono / WhatsApp
  - Nombre de la propiedad
  - Hectáreas aproximadas
  - Departamento/Región (dropdown: Santa Cruz, Beni, Pando, Otro)
  - Mensaje (opcional, textarea)
  - Checkbox: "Acepto ser contactado por Aristeus"
  - Botón submit verde (#7AB929): "Solicitar Análisis Gratuito"

FOOTER:
─────────
- Fondo: #0A0E14
- Logo Aristeus (versión clara)
- Columnas:
  - Productos: Grass Gauge, CattleVision
  - Empresa: Nosotros, Contacto
  - Legal: Términos, Privacidad
- Redes sociales (placeholders)
- "© 2025 Aristeus. Tecnología para una ganadería sostenible."
- "Santa Cruz de la Sierra, Bolivia"

═══════════════════════════════════════════════════════════════
PÁGINA PRODUCTOS (/productos)
═══════════════════════════════════════════════════════════════

GRASS GAUGE SECTION:
- Hero propio con logo GG + fondo pastizal oscurecido
- Headline: "Grass Gauge — Sabe exactamente cuánto pasto tienes"
- Features expandidas (6 cards):
  - Estimación de biomasa por potrero
  - Análisis nutricional (proteína, fibra, energía)
  - Plan de rotación automático
  - Alertas de sobrepastoreo
  - Historial y tendencias por potrero
  - Reportes descargables
- Proceso completo visual (5 pasos con timeline)
- CTA: "Prueba Grass Gauge en tu campo"

CATTLEVISION SECTION:
- Hero propio con logo CV + fondo oscuro tech
- Headline: "CattleVision — El peso de tu ganado, sin tocarlo"
- Features (más conceptuales, es producto futuro):
  - Vuelo autónomo de drones
  - Escaneo LiDAR 3D
  - Modelo de estimación de peso por morfología
  - Dashboard de seguimiento de engorde
- Badge prominente: "En desarrollo — Registro para acceso temprano"
- CTA: formulario corto de early access

═══════════════════════════════════════════════════════════════
PÁGINA NOSOTROS (/nosotros)
═══════════════════════════════════════════════════════════════

- Hero simple con headline: "Tecnología boliviana para
  el campo latinoamericano"
- Misión: texto breve
- Visión: texto breve
- Timeline con hitos (validación Australia, piloto Bolivia, etc.)
- Logos de respaldo (incubadoras)
- Mapa: Santa Cruz como base, con indicaciones de pilotos
- CTA: "Trabaja con nosotros" o "Contáctanos"

═══════════════════════════════════════════════════════════════
PÁGINA CONTACTO (/contacto)
═══════════════════════════════════════════════════════════════

- Formulario completo (mismo del CTA final de home)
- Info de contacto: email, teléfono, ubicación
- Mapa Leaflet con pin en Santa Cruz
- Horario de atención (opcional)

═══════════════════════════════════════════════════════════════
COMPONENTES COMPARTIDOS (shared/)
═══════════════════════════════════════════════════════════════

Button.astro:
  Props: text, href, variant (primary/secondary/outline),
  color (green/gold/navy), size (sm/md/lg)
  Primary: fondo sólido, hover brightness
  Secondary: outline con hover fill
  Transición 300ms

FeatureCard.astro:
  Props: icon, title, description, accentColor
  Glassmorphism: bg rgba(28,35,51,0.6), backdrop-blur-md,
  border 1px solid var(--border-subtle)
  Hover: borde cambia al accentColor, box-shadow glow sutil

MetricCard.astro:
  Props: number, label, prefix, suffix
  Número grande en font-data
  Animación counter al entrar en viewport
  Hover glow

SectionTitle.astro:
  Props: title, subtitle, align (center/left)
  H2 con accent line (barra verde debajo)
  Subtitle en text-secondary

ContactForm.astro:
  Props: formName, variant (compact/full)
  Integrado con Netlify Forms
  Validación HTML5 básica
  Estilos de inputs oscuros con borde sutil

MapDemo.astro:
  Componente React island (client:visible)
  Leaflet con controles de capa
  3 modos de visualización
  Card de datos lateral
  Responsive

ScrollReveal.astro:
  Wrapper con Intersection Observer
  Animaciones: fade-up, fade-in, slide-left, slide-right
  Threshold configurable

LanguageSwitch.astro:
  Toggle ES/EN
  Guarda preferencia en localStorage
  Cambia textos sin reload (usando data attributes o json swap)

═══════════════════════════════════════════════════════════════
ARCHIVOS DE CONFIGURACIÓN
═══════════════════════════════════════════════════════════════

netlify.toml:
  [build]
    command = "npm run build"
    publish = "dist"

astro.config.mjs:
  - integrations: tailwind, react (para Leaflet island)
  - output: 'static'

tailwind.config.mjs:
  - extend colors con todas las variables de la paleta
  - extend fontFamily con Space Grotesk, Inter, JetBrains Mono
  - extend animation para fade-up, fade-in

global.css:
  - CSS custom properties con toda la paleta
  - Importar Google Fonts (Space Grotesk, Inter, JetBrains Mono)
  - Scrollbar personalizada oscura
  - Selection color con verde Aristeus
  - Smooth scroll en html

═══════════════════════════════════════════════════════════════
CONTENIDO i18n — TEXTOS PRINCIPALES
═══════════════════════════════════════════════════════════════

Generar es.json y en.json con todos los textos de la landing
traducidos. Usar una estructura tipo:
{
  "nav": { ... },
  "hero": { "badge", "headline", "subheadline", "cta1", "cta2" },
  "problem": { ... },
  "products": { ... },
  "howItWorks": { ... },
  ...
}

═══════════════════════════════════════════════════════════════
NOTAS IMPORTANTES
═══════════════════════════════════════════════════════════════

- NO saturar de imágenes. Usar espacios, tipografía grande
  y datos como elementos visuales principales.
- El mapa interactivo es un diferenciador clave. Debe verse
  profesional y funcionar bien en mobile.
- Las métricas deben parecer reales y específicas, no genéricas.
- Cada producto (Grass Gauge, CattleVision) debe tener su
  personalidad visual propia dentro de la identidad Aristeus.
- El formulario debe tener fricción mínima pero capturar
  los datos necesarios para calificar al lead.
- Mobile-first: todo debe verse impecable en celular.
- Performance: Lighthouse score > 90 como objetivo.
- Usar imágenes placeholder de Unsplash:
  temas: cattle, pasture, satellite view, drone, ranch, grassland
  Siempre con overlay oscuro.

Genera el proyecto completo con todos los archivos funcionando.
Usa inglés para código/comentarios, español para contenido
por defecto.