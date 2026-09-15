# Aristeus - Página Web

Página web oficial de Aristeus, plataforma innovadora de soluciones agrícolas basada en inteligencia artificial y visión por computadora.

## 📋 Descripción

Aristeus es una plataforma que ofrece soluciones tecnológicas avanzadas para la agricultura moderna. Este repositorio contiene el código de la página web de presentación del producto, desarrollada con tecnologías web modernas.

## ✨ Características Principales

- **CattleVision**: Solución de monitoreo inteligente para ganado
- **GrassGauge**: Sistema de medición y análisis de pastos
- **Interfaz Multiidioma**: Soporte para español e inglés
- **Diseño Responsivo**: Totalmente adaptable a dispositivos móviles y escritorio
- **Animaciones Fluidas**: Experiencia visual mejorada con scroll reveal
- **Mapa Interactivo**: Visualización de datos geográficos

## 🚀 Tecnologías Utilizadas

- **[Astro](https://astro.build/)** - Framework web estático
- **[Tailwind CSS](https://tailwindcss.com/)** - Framework CSS utility-first
- **[React](https://react.dev/)** - Componentes interactivos
- **[TypeScript](https://www.typescriptlang.org/)** - Tipado estático
- **[Netlify](https://www.netlify.com/)** - Hosting y despliegue

## 📁 Estructura del Proyecto

```
src/
├── components/          # Componentes reutilizables
│   ├── animations/      # Animaciones y efectos visuales
│   ├── home/           # Componentes de página principal
│   ├── products/       # Componentes de productos
│   ├── layout/         # Componentes de diseño (Nav, Footer)
│   └── shared/         # Componentes compartidos
├── pages/              # Páginas del sitio
├── layouts/            # Layouts de página
├── styles/             # Estilos globales
├── utils/              # Utilidades (i18n, etc)
└── data/               # Datos (traducciones)
public/                 # Archivos estáticos
```

## 🛠️ Requisitos Previos

- Node.js 16.x o superior
- npm, yarn o pnpm

## 📦 Instalación

```bash
# Clonar el repositorio
git clone https://github.com/PaulRodriguezAsihama/AristeusWebpage.git
cd AristeusWebpage

# Instalar dependencias
npm install
# o
yarn install
```

## 🔧 Desarrollo

```bash
# Iniciar servidor de desarrollo
npm run dev

# El sitio estará disponible en http://localhost:4321
```

## 🏗️ Build

```bash
# Generar build de producción
npm run build

# Vista previa del build
npm run preview
```

## 🌐 Despliegue

Este proyecto está configurado para desplegar automáticamente en Netlify. Los cambios en la rama `main` se despliegan automáticamente.

### Variables de Entorno

Crear un archivo `.env.local` con las variables necesarias:

```
# Añadir variables según sea necesario
```

## 🌍 Idiomas Soportados

- 🇪🇸 Español
- 🇬🇧 Inglés

## 📝 Páginas Disponibles

- `/` - Página principal
- `/productos` - Catálogo de productos
- `/nosotros` - Información sobre la empresa
- `/contacto` - Formulario de contacto

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo licencia privada. Todos los derechos reservados.

## 📧 Contacto

Para más información, visita [aristeus.com](https://aristeus.com) o contacta a través del formulario en la página web.

---

**Desarrollado por:** Paul Rodríguez Asihama  
**Última actualización:** Junio 2026
