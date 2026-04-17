import React from 'react'
import { useTranslation } from 'react-i18next'
import { useTradeStore } from '@store/tradeStore'
import { useThemeStore } from '@store/themeStore'
import {
  FiDashboard,
  FiTrendingUp,
  FiBriefcase,
  FiBarChart2,
  FiSettings,
  FiMoon,
  FiSun
} from 'react-icons/fi'

export default function Navigation() {
  const { t } = useTranslation()
  const { setCurrentPage, currentPage } = useTradeStore()
  const { darkMode, toggleDarkMode } = useThemeStore()

  const navItems = [
    { id: 'dashboard', label: t('nav.dashboard'), icon: FiDashboard },
    { id: 'strategy', label: t('nav.strategy'), icon: FiTrendingUp },
    { id: 'portfolio', label: t('nav.portfolio'), icon: FiBriefcase },
    { id: 'backtest', label: t('nav.backtest'), icon: FiBarChart2 },
    { id: 'settings', label: t('nav.settings'), icon: FiSettings }
  ]

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
      <div className="px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">
            🤖 {t('app.title')}
          </h1>
          <div className="flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <button
                  key={item.id}
                  onClick={() => setCurrentPage(item.id as any)}
                  className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-all ${
                    currentPage === item.id
                      ? 'bg-blue-500 text-white'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  <Icon size={18} />
                  <span className="text-sm">{item.label}</span>
                </button>
              )
            })}
          </div>
        </div>

        <button
          onClick={toggleDarkMode}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          {darkMode ? (
            <FiSun className="text-yellow-400" size={20} />
          ) : (
            <FiMoon className="text-gray-700" size={20} />
          )}
        </button>
      </div>
    </nav>
  )
}
