import type { ReactNode } from 'react'
import { useState } from 'react'
import type { NavItem } from './Sidebar.types'
import { Button } from './Button'
import { Badge } from './Badge'
import { useTheme } from '../../hooks/useTheme'

export interface SidebarProps {
  items: NavItem[]
  collapsed?: boolean
  onCollapseChange?: (collapsed: boolean) => void
  brand?: {
    logo?: ReactNode
    name: string
    tagline?: string
  }
  user?: {
    name: string
    email: string
    avatar?: string
  }
  syncStatus?: {
    status: 'synced' | 'syncing' | 'error'
    lastSync?: string
  }
  className?: string
}

export function Sidebar({
  items,
  collapsed = false,
  onCollapseChange,
  brand,
  user,
  syncStatus,
  className = '',
}: SidebarProps) {
  const [isMobileOpen, setIsMobileOpen] = useState(false)
  const { theme, toggleTheme } = useTheme()

  const navSections = items.reduce((acc, item) => {
    if (!acc[item.section]) acc[item.section] = []
    acc[item.section].push(item)
    return acc
  }, {} as Record<string, NavItem[]>)

  if (collapsed) {
    return (
      <aside
        className={`
          fixed lg:static z-40 h-full bg-[var(--bg-card)] border-r border-[var(--border-subtle)]
          transition-all duration-300 ease-out
          ${collapsed ? 'w-16' : 'w-64'}
          ${className}
        `}
        aria-label="Navegación principal colapsada"
      >
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-center h-16 border-b border-[var(--border-subtle)]">
            {brand?.logo && (
              <span className="text-2xl">{brand.logo}</span>
            )}
          </div>

          <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-1" aria-label="Navegación">
            {Object.entries(navSections).map(([section, sectionItems]) => (
              <div key={section} className="space-y-1">
                {sectionItems.map((item) => (
                  <button
                    key={item.id}
                    onClick={item.onClick}
                    disabled={item.disabled || item.comingSoon}
                    className={`
                      w-full flex items-center justify-center px-3 py-2.5 rounded-xl
                      text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                      hover:bg-[var(--bg-secondary)]
                      transition-colors duration-200
                      disabled:opacity-50 disabled:cursor-not-allowed
                      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gg-green-mid)]
                      ${item.active ? 'bg-[var(--gg-green-dark)] text-white' : ''}
                    `}
                    title={item.label}
                    aria-label={item.label}
                    aria-current={item.active ? 'page' : undefined}
                  >
                    {item.icon}
                    {item.badge && (
                      <Badge variant="gg" size="sm" className="ml-auto">
                        {item.badge}
                      </Badge>
                    )}
                  </button>
                ))}
              </div>
            ))}
          </nav>

          <div className="p-3 border-t border-[var(--border-subtle)] space-y-2">
            <Button
              variant="ghost"
              size="sm"
              fullWidth
              onClick={toggleTheme}
              aria-label={theme === 'light' ? 'Cambiar a modo oscuro' : 'Cambiar a modo claro'}
            >
              {theme === 'light' ? '🌙' : '☀️'}
            </Button>

            {syncStatus && (
              <div className="flex items-center gap-2 px-2 py-2 bg-[var(--bg-secondary)] rounded-xl">
                <span
                  className={`
                    w-2 h-2 rounded-full
                    ${syncStatus.status === 'synced' && 'bg-green-500'}
                    ${syncStatus.status === 'syncing' && 'bg-yellow-500 animate-pulse'}
                    ${syncStatus.status === 'error' && 'bg-red-500'}
                  `}
                />
                <span className="text-xs text-[var(--text-secondary)] flex-1 truncate">
                  {syncStatus.status === 'synced' && 'Sincronizado'}
                  {syncStatus.status === 'syncing' && 'Sincronizando...'}
                  {syncStatus.status === 'error' && 'Error de sync'}
                </span>
              </div>
            )}

            <Button
              variant="ghost"
              size="sm"
              fullWidth
              onClick={() => onCollapseChange?.(false)}
              aria-label="Expandir menú"
            >
              ◀
            </Button>
          </div>
        </div>
      </aside>
    )
  }

  return (
    <>
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setIsMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={`
          fixed lg:static z-40 h-full bg-[var(--bg-card)] border-r border-[var(--border-subtle)]
          transition-all duration-300 ease-out
          ${collapsed ? 'w-16' : 'w-64'}
          ${isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          ${className}
        `}
        aria-label="Navegación principal"
      >
        <div className="flex flex-col h-full">
          <div className="flex items-center gap-3 h-16 px-4 border-b border-[var(--border-subtle)]">
            <div className="flex-shrink-0">
              {brand?.logo ? (
                <span className="text-2xl">{brand.logo}</span>
              ) : (
                <div className="w-8 h-8 rounded-xl bg-[var(--gg-green-dark)] flex items-center justify-center">
                  <span className="text-white font-bold">GG</span>
                </div>
              )}
            </div>
            {!collapsed && brand && (
              <div className="flex-1 min-w-0">
                <p className="font-heading font-semibold text-[var(--text-primary)] truncate">
                  {brand.name}
                </p>
                {brand.tagline && (
                  <p className="text-xs text-[var(--text-secondary)] truncate">
                    {brand.tagline}
                  </p>
                )}
              </div>
            )}
          </div>

          <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-4" aria-label="Navegación">
            {Object.entries(navSections).map(([section, sectionItems]) => (
              <div key={section} className="space-y-1">
                <p className="px-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  {section}
                </p>
                {sectionItems.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => {
                      item.onClick?.()
                      setIsMobileOpen(false)
                    }}
                    disabled={item.disabled || item.comingSoon}
                    className={`
                      w-full flex items-center gap-3 px-3 py-2.5 rounded-xl
                      text-[var(--text-secondary)] hover:text-[var(--text-primary)]
                      hover:bg-[var(--bg-secondary)]
                      transition-colors duration-200
                      disabled:opacity-50 disabled:cursor-not-allowed
                      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gg-green-mid)]
                      ${item.active ? 'bg-[var(--gg-green-dark)] text-white' : ''}
                    `}
                    aria-current={item.active ? 'page' : undefined}
                  >
                    <span className="flex-shrink-0" aria-hidden="true">{item.icon}</span>
                    {!collapsed && (
                      <>
                        <span className="flex-1 truncate">{item.label}</span>
                        {item.badge && (
                          <Badge variant="gg" size="sm">
                            {item.badge}
                          </Badge>
                        )}
                      </>
                    )}
                  </button>
                ))}
              </div>
            ))}
          </nav>

          <div className="p-3 border-t border-[var(--border-subtle)] space-y-2">
            {user && !collapsed && (
              <div className="flex items-center gap-3 px-2 py-2 bg-[var(--bg-secondary)] rounded-xl">
                <div className="w-8 h-8 rounded-full bg-[var(--gg-green-dark)] flex items-center justify-center text-white font-semibold text-sm">
                  {user.name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[var(--text-primary)] truncate">{user.name}</p>
                  <p className="text-xs text-[var(--text-secondary)] truncate">{user.email}</p>
                </div>
              </div>
            )}

            <Button
              variant="ghost"
              size="sm"
              fullWidth
              onClick={toggleTheme}
              aria-label={theme === 'light' ? 'Cambiar a modo oscuro' : 'Cambiar a modo claro'}
            >
              <span className="flex items-center gap-2">
                {theme === 'light' ? '🌙' : '☀️'}
                {!collapsed && (
                  <span>{theme === 'light' ? 'Modo oscuro' : 'Modo claro'}</span>
                )}
              </span>
            </Button>

            {syncStatus && !collapsed && (
              <div className="flex items-center gap-2 px-2 py-2 bg-[var(--bg-secondary)] rounded-xl">
                <span
                  className={`
                    w-2 h-2 rounded-full
                    ${syncStatus.status === 'synced' && 'bg-green-500'}
                    ${syncStatus.status === 'syncing' && 'bg-yellow-500 animate-pulse'}
                    ${syncStatus.status === 'error' && 'bg-red-500'}
                  `}
                />
                <span className="text-xs text-[var(--text-secondary)] flex-1 truncate">
                  {syncStatus.status === 'synced' && `Sincronizado ${syncStatus.lastSync ? `· ${syncStatus.lastSync}` : ''}`}
                  {syncStatus.status === 'syncing' && 'Sincronizando...'}
                  {syncStatus.status === 'error' && 'Error de sincronización'}
                </span>
              </div>
            )}

            <Button
              variant="ghost"
              size="sm"
              fullWidth
              onClick={() => onCollapseChange?.(!collapsed)}
              aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}
            >
              <span className="flex items-center justify-center gap-2">
                {collapsed ? '▶' : '◀'}
                {!collapsed && <span>Colapsar</span>}
              </span>
            </Button>
          </div>
        </div>
      </aside>
    </>
  )
}