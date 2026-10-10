# Aristeus Landing — Build Plan

## Validation Notes
- REMOVED: `Solution.astro` (no section describes it)
- REMOVED: `components/layout/Layout.astro` (redundant with `BaseLayout.astro`)
- MapDemo requires: @astrojs/react, react, react-dom, leaflet, react-leaflet, @types/leaflet
- i18n: client-side DOM swap approach with data-i18n attributes
- Images: Unsplash URLs with CSS overlay, no downloads

## Execution Order (6 phases, 35 files)

### PHASE 1 — Project Scaffold (5 files)
> Goal: `npm install` works, `npm run dev` boots empty site
> Dependencies: none

```
1.1  package.json
1.2  tsconfig.json
1.3  astro.config.mjs          (astro + tailwind + react integrations)
1.4  tailwind.config.mjs       (full color palette, fonts, animations)
1.5  netlify.toml
```
**Checkpoint**: run `npm install && npm run dev` — should start on localhost

### PHASE 2 — Foundation: Styles + Data + Utils (4 files)
> Goal: design system tokens available, i18n data ready
> Dependencies: Phase 1

```
2.1  src/styles/global.css      (CSS vars, Google Fonts, scrollbar, selection)
2.2  src/data/es.json           (all Spanish content)
2.3  src/data/en.json           (all English content)
2.4  src/utils/i18n.ts          (language helper, localStorage, DOM swap)
```

### PHASE 3 — Shared Components + Animations (8 files)
> Goal: reusable building blocks ready
> Dependencies: Phase 2 (global.css, i18n)

```
3.1  src/components/shared/Button.astro
3.2  src/components/shared/SectionTitle.astro
3.3  src/components/shared/FeatureCard.astro
3.4  src/components/shared/MetricCard.astro
3.5  src/components/shared/ContactForm.astro
3.6  src/components/shared/LanguageSwitch.astro
3.7  src/components/animations/ScrollReveal.astro
3.8  public/favicon.svg
```

### PHASE 4 — Layout Shell (3 files)
> Goal: full page shell renders (nav + content slot + footer)
> Dependencies: Phase 3 (Button, LanguageSwitch)

```
4.1  src/components/layout/Nav.astro
4.2  src/components/layout/Footer.astro
4.3  src/layouts/BaseLayout.astro
```
**Checkpoint**: create minimal `src/pages/index.astro` with BaseLayout — full shell renders

### PHASE 5 — Section Components (12 files)
> Goal: all visual sections exist as independent components
> Dependencies: Phase 3 + 4

Home sections (8):
```
5.1  src/components/home/Hero.astro
5.2  src/components/home/Problem.astro
5.3  src/components/home/Products.astro
5.4  src/components/home/HowItWorks.astro
5.5  src/components/home/Benefits.astro
5.6  src/components/home/Technology.astro
5.7  src/components/home/Backing.astro
5.8  src/components/home/CTAFinal.astro
```

Product page sections (4):
```
5.9  src/components/products/GrassGaugeHero.astro
5.10 src/components/products/GrassGaugeFeatures.astro
5.11 src/components/products/CattleVisionHero.astro
5.12 src/components/products/CattleVisionFeatures.astro
```

### PHASE 6 — Pages + MapDemo (5 files)
> Goal: all pages assemble their sections, site is complete
> Dependencies: Phase 5

```
6.1  src/components/shared/MapDemo.astro   (React island — Leaflet)
6.2  src/pages/index.astro                 (Home — all 9 sections + MapDemo)
6.3  src/pages/productos.astro             (GG + CV sections)
6.4  src/pages/nosotros.astro              (About page)
6.5  src/pages/contacto.astro              (Contact + Leaflet map)
```
**Final checkpoint**: full site works, all pages navigate, form submits, map renders

## Estimated Complexity per Phase
| Phase | Files | Complexity | Notes |
|-------|-------|------------|-------|
| 1     | 5     | Low        | Boilerplate config |
| 2     | 4     | Medium     | i18n JSON is verbose, ~200 keys each |
| 3     | 8     | Medium     | MetricCard counter animation, ScrollReveal observer |
| 4     | 3     | Medium     | Nav responsive burger menu, sticky behavior |
| 5     | 12    | High       | Most visual work, Unsplash images, glassmorphism |
| 6     | 5     | High       | MapDemo is the hardest (Leaflet + 3 layers + React) |

## Context Window Strategy
Given ~35 files and limited context per conversation:
- **Phases 1-3** can be done in one conversation (17 files, mostly config/data/small components)
- **Phase 4** in same conversation if context allows
- **Phase 5** may need a new conversation (12 section components, each ~50-100 lines)
- **Phase 6** may need its own conversation (MapDemo is complex)
