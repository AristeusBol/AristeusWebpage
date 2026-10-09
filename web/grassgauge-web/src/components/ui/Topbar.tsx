import type { ReactNode } from 'react'
import { useRef, useState, useEffect } from 'react'
import { Button } from './Button'
import { Input } from './Input'
import { useTheme } from '../../hooks/useTheme'

export interface TopbarProps {
  title?: string
  breadcrumbs?: Array<{ label: string; href?: string }>
  searchPlaceholder?: string
  onSearch?: (query: string) => void
  actions?: ReactNode
  user?: {
    name: string
    email: string
    avatar?: string
    notifications?: number
  }
  onMenuClick?: () => void
  className?: string
}

export function Topbar({
  title,
  breadcrumbs,
  searchPlaceholder = 'Buscar...',
  onSearch,
  actions,
  user,
  onMenuClick,
  className = '',
}: TopbarProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)
  const notificationsRef = useRef<HTMLDivElement>(null)
  const { theme, toggleTheme } = useTheme()

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false)
      }
      if (notificationsRef.current && !notificationsRef.current.contains(event.target as Node)) {
        setShowNotifications(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSearch?.(searchQuery)
  }

  return (
    <header
      className={`
        sticky top-0 z-30 flex items-center gap-4
        bg-[var(--bg-card)] border-b border-[var(--border-subtle)]
        px-4 py-3
        ${className}
      `}
      role="banner"
    >
      <Button
        variant="ghost"
        size="sm"
        className="lg:hidden"
        onClick={onMenuClick}
        aria-label="Abrir menú"
        aria-expanded="false"
      >
        ☰
      </Button>

      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="flex items-center gap-2 text-sm flex-1 lg:hidden" aria-label="Ruta de navegación">
          {breadcrumbs.map((crumb, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <span className="text-[var(--text-secondary)]">/</span>}
              {crumb.href ? (
                <a href={crumb.href} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                  {crumb.label}
                </a>
              ) : (
                <span className="font-medium text-[var(--text-primary)]">{crumb.label}</span>
              )}
            </span>
          ))}
        </nav>
      )}

      <div className="flex-1 flex items-center gap-4 min-w-0">
        {title && (
          <h1 className="font-heading text-lg font-semibold text-[var(--text-primary)] truncate lg:block hidden">
            {title}
          </h1>
        )}

        <form onSubmit={handleSearchSubmit} className="flex-1 max-w-md hidden md:block">
          <Input
            type="search"
            placeholder={searchPlaceholder}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full"
            aria-label="Buscar"
          />
        </form>
      </div>

      <div className="flex items-center gap-2">
        {actions}

        <Button
          variant="ghost"
          size="sm"
          onClick={toggleTheme}
          aria-label={theme === 'light' ? 'Cambiar a modo oscuro' : 'Cambiar a modo claro'}
          className="hidden sm:flex"
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </Button>

        {user && (
          <>
            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowNotifications(!showNotifications)
                  setShowUserMenu(false)
                }}
                aria-label={`Notificaciones${user.notifications ? ` (${user.notifications})` : ''}`}
                aria-expanded={showNotifications}
                aria-haspopup="true"
              >
                <span className="relative">
                  🔔
                  {user.notifications && user.notifications > 0 && (
                    <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                      {user.notifications > 9 ? '9+' : user.notifications}
                    </span>
                  )}
                </span>
              </Button>

              {showNotifications && (
                <div
                  ref={notificationsRef}
                  className="absolute right-0 top-full mt-2 w-80 glass rounded-xl shadow-xl py-2 z-50 animate-fade-in"
                  role="menu"
                >
                  <div className="px-4 py-2 border-b border-[var(--border-subtle)]">
                    <h3 className="font-semibold text-[var(--text-primary)]">Notificaciones</h3>
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    <div className="py-4 text-center text-[var(--text-secondary)]">
                      No hay notificaciones nuevas
                    </div>
                  </div>
                  <div className="px-4 py-2 border-t border-[var(--border-subtle)]">
                    <Button variant="ghost" size="sm" fullWidth>Ver todas</Button>
                  </div>
                </div>
              )}
            </div>

            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowUserMenu(!showUserMenu)
                  setShowNotifications(false)
                }}
                aria-label="Menú de usuario"
                aria-expanded={showUserMenu}
                aria-haspopup="true"
                className="flex items-center gap-2"
              >
                {user.avatar ? (
                  <img src={user.avatar} alt="" className="w-8 h-8 rounded-full" />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-[var(--gg-green-dark)] flex items-center justify-center text-white font-semibold text-sm">
                    {user.name.charAt(0).toUpperCase()}
                  </div>
                )}
                <span className="hidden md:block text-sm font-medium text-[var(--text-primary)]">
                  {user.name}
                </span>
              </Button>

              {showUserMenu && (
                <div
                  ref={userMenuRef}
                  className="absolute right-0 top-full mt-2 w-48 glass rounded-xl shadow-xl py-2 z-50 animate-fade-in"
                  role="menu"
                >
                  <div className="px-4 py-3 border-b border-[var(--border-subtle)]">
                    <p className="text-sm font-medium text-[var(--text-primary)]">{user.name}</p>
                    <p className="text-xs text-[var(--text-secondary)] truncate">{user.email}</p>
                  </div>
                  <button
                    role="menuitem"
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]"
                  >
                    ⚙️ Configuración
                  </button>
                  <button
                    role="menuitem"
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]"
                  >
                    📖 Ayuda
                  </button>
                  <hr className="my-2 border-[var(--border-subtle)]" />
                  <button
                    role="menuitem"
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-500/10"
                  >
                    🚪 Cerrar sesión
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </header>
  )
}