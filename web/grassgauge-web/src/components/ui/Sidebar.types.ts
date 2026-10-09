export interface NavItem {
  id: string
  label: string
  icon: React.ReactNode
  section: string
  onClick?: () => void
  active?: boolean
  disabled?: boolean
  comingSoon?: boolean
  badge?: string | number
}