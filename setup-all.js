#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

// Directory structure
const dirs = [
  'src/main',
  'src/preload',
  'src/frontend',
  'src/frontend/components',
  'src/frontend/components/pages',
  'src/frontend/components/dashboard',
  'src/frontend/hooks',
  'src/frontend/store',
  'src/frontend/utils',
  'src/frontend/styles',
  'src/frontend/locales',
  'src/frontend/types',
  'src/frontend/services'
];

// Create directories
dirs.forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

// File contents
const files = {
  'src/main/index.ts': `import { BrowserWindow, app, ipcMain } from 'electron'
import { createRequire } from 'module'
import { fileURLToPath } from 'url'
import path from 'path'

const require = createRequire(import.meta.url)
const __dirname = path.dirname(fileURLToPath(import.meta.url))

if (require('electron-squirrel-startup')) {
  app.quit()
}

let mainWindow: BrowserWindow | null

const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      sandbox: true
    }
  })

  if (MAIN_WINDOW_VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL)
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(
      path.join(__dirname, \`../renderer/\${MAIN_WINDOW_VITE_NAME}/index.html\`)
    )
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.on('ready', createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})

ipcMain.handle('get-market-data', async (event, symbol) => {
  return { symbol, price: 0, change: 0 }
})

ipcMain.handle('execute-trade', async (event, order) => {
  return { success: true, orderId: '123456' }
})

ipcMain.handle('get-strategy-analysis', async (event) => {
  return {
    aggressive: { confidence: 82, signal: '做多', pnl: '+2.5%' },
    conservative: { confidence: 65, signal: '持有', pnl: '+1.8%' }
  }
})

declare const MAIN_WINDOW_VITE_DEV_SERVER_URL: string
declare const MAIN_WINDOW_VITE_NAME: string
`,

  'src/preload/index.ts': `import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electron', {
  getMarketData: (symbol: string) =>
    ipcRenderer.invoke('get-market-data', symbol),
  executeTrade: (order: any) =>
    ipcRenderer.invoke('execute-trade', order),
  getStrategyAnalysis: () =>
    ipcRenderer.invoke('get-strategy-analysis'),
  onStrategyUpdate: (callback: any) =>
    ipcRenderer.on('strategy-update', callback),
  onTradeUpdate: (callback: any) =>
    ipcRenderer.on('trade-update', callback),
  removeAllListeners: (channel: string) =>
    ipcRenderer.removeAllListeners(channel)
})

declare global {
  interface Window {
    electron: {
      getMarketData: (symbol: string) => Promise<any>
      executeTrade: (order: any) => Promise<any>
      getStrategyAnalysis: () => Promise<any>
      onStrategyUpdate: (callback: any) => void
      onTradeUpdate: (callback: any) => void
      removeAllListeners: (channel: string) => void
    }
  }
}
`,

  'src/frontend/index.html': `<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <title>双AI交易策略 - 智能交易系统</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="./index.tsx"></script>
  </body>
</html>
`,

  'src/frontend/index.tsx': `import React from 'react'
import ReactDOM from 'react-dom/client'
import { I18nextProvider } from 'react-i18next'
import App from './App'
import i18n from './locales/i18n'
import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nextProvider i18n={i18n}>
      <App />
    </I18nextProvider>
  </React.StrictMode>
)
`,

  'src/frontend/App.tsx': `import React, { useEffect } from 'react'
import { useThemeStore } from '@store/themeStore'
import { useTradeStore } from '@store/tradeStore'
import Navigation from '@components/Navigation'
import Dashboard from '@pages/Dashboard'
import DualStrategyPanel from '@pages/DualStrategyPanel'
import PortfolioView from '@pages/PortfolioView'
import BacktestView from '@pages/BacktestView'
import SettingsView from '@pages/SettingsView'

export default function App() {
  const { darkMode } = useThemeStore()
  const { currentPage } = useTradeStore()

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard />
      case 'strategy':
        return <DualStrategyPanel />
      case 'portfolio':
        return <PortfolioView />
      case 'backtest':
        return <BacktestView />
      case 'settings':
        return <SettingsView />
      default:
        return <Dashboard />
    }
  }

  return (
    <div className={darkMode ? 'dark' : ''}>
      <div className="min-h-screen bg-white dark:bg-gray-900">
        <Navigation />
        <main className="pt-16">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}
`,

  'src/frontend/components/Navigation.tsx': `import React from 'react'
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
                  className={\`px-4 py-2 rounded-lg flex items-center gap-2 transition-all \${
                    currentPage === item.id
                      ? 'bg-blue-500 text-white'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }\`}
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
`,

  'src/frontend/components/pages/Dashboard.tsx': `import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import RealTimeChart from '@components/dashboard/RealTimeChart'
import OrderBook from '@components/dashboard/OrderBook'
import TradeHistory from '@components/dashboard/TradeHistory'
import RiskMonitor from '@components/dashboard/RiskMonitor'
import PerformanceMetrics from '@components/dashboard/PerformanceMetrics'

export default function Dashboard() {
  const { t } = useTranslation()
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)
      try {
        // 获取实时数据
        await new Promise(resolve => setTimeout(resolve, 500))
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="p-6 space-y-6"
    >
      <div className="grid grid-cols-4 gap-4">
        <PerformanceMetrics />
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <RealTimeChart />
        </div>
        <div>
          <OrderBook />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <TradeHistory />
        <RiskMonitor />
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/pages/DualStrategyPanel.tsx': `import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { FiTrendingUp, FiTrendingDown, FiZap } from 'react-icons/fi'
import StrategyCard from '@components/dashboard/StrategyCard'
import FusedDecision from '@components/dashboard/FusedDecision'
import StrategyChart from '@components/dashboard/StrategyChart'

interface StrategyAnalysis {
  confidence: number
  signal: string
  pnl: string
  reasoning: string
  nextAction: string
}

export default function DualStrategyPanel() {
  const { t } = useTranslation()
  const [aggressiveStrategy, setAggressiveStrategy] = useState<StrategyAnalysis | null>(null)
  const [conservativeStrategy, setConservativeStrategy] = useState<StrategyAnalysis | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStrategies = async () => {
      try {
        const analysis = await window.electron?.getStrategyAnalysis?.()
        if (analysis) {
          setAggressiveStrategy({
            confidence: 82,
            signal: t('strategy.signals.longPosition'),
            pnl: '+2.5%',
            reasoning: t('strategy.reasoning.aggressive'),
            nextAction: t('strategy.actions.continueLong')
          })
          setConservativeStrategy({
            confidence: 65,
            signal: t('strategy.signals.hold'),
            pnl: '+1.8%',
            reasoning: t('strategy.reasoning.conservative'),
            nextAction: t('strategy.actions.wait')
          })
        }
      } finally {
        setLoading(false)
      }
    }

    fetchStrategies()
  }, [t])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin">
          <FiZap size={48} className="text-blue-500" />
        </div>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="p-6 space-y-6 max-w-7xl mx-auto"
    >
      {/* 标题 */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          {t('strategy.title')}
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          {t('strategy.description')}
        </p>
      </div>

      {/* 双策略面板 */}
      <div className="grid grid-cols-2 gap-6">
        <motion.div
          initial={{ x: -20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          <StrategyCard
            title={t('strategy.aggressive')}
            icon={<FiTrendingUp size={24} />}
            strategy={aggressiveStrategy}
            variant="aggressive"
          />
        </motion.div>

        <motion.div
          initial={{ x: 20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <StrategyCard
            title={t('strategy.conservative')}
            icon={<FiTrendingDown size={24} />}
            strategy={conservativeStrategy}
            variant="conservative"
          />
        </motion.div>
      </div>

      {/* 融合决策 */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        <FusedDecision
          aggressive={aggressiveStrategy}
          conservative={conservativeStrategy}
        />
      </motion.div>

      {/* 策略图表 */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        <StrategyChart />
      </motion.div>
    </motion.div>
  )
}
`,

  'src/frontend/components/pages/PortfolioView.tsx': `import React from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import PortfolioChart from '@components/dashboard/PortfolioChart'
import PositionsList from '@components/dashboard/PositionsList'

export default function PortfolioView() {
  const { t } = useTranslation()

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="p-6 space-y-6"
    >
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {t('portfolio.title')}
        </h1>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <PortfolioChart />
        <PositionsList />
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/pages/BacktestView.tsx': `import React from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'

export default function BacktestView() {
  const { t } = useTranslation()

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-6"
    >
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
        {t('backtest.title')}
      </h1>
      <div className="mt-6 p-6 bg-gray-100 dark:bg-gray-800 rounded-lg">
        <p className="text-gray-600 dark:text-gray-400">
          {t('backtest.placeholder')}
        </p>
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/pages/SettingsView.tsx': `import React from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import LanguageSettings from '@components/dashboard/LanguageSettings'

export default function SettingsView() {
  const { t } = useTranslation()

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-6 max-w-2xl"
    >
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
        {t('settings.title')}
      </h1>

      <div className="space-y-6">
        <LanguageSettings />
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/dashboard/StrategyCard.tsx': `import React from 'react'
import { motion } from 'framer-motion'

interface StrategyCardProps {
  title: string
  icon: React.ReactNode
  strategy: any
  variant: 'aggressive' | 'conservative'
}

export default function StrategyCard({
  title,
  icon,
  strategy,
  variant
}: StrategyCardProps) {
  const isBullish = variant === 'aggressive'

  return (
    <motion.div
      className={\`p-6 rounded-lg border-2 \${
        isBullish
          ? 'bg-green-50 dark:bg-green-900/20 border-green-300 dark:border-green-700'
          : 'bg-blue-50 dark:bg-blue-900/20 border-blue-300 dark:border-blue-700'
      }\`}
      whileHover={{ scale: 1.02 }}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          {icon}
          {title}
        </h3>
        <div className={\`px-3 py-1 rounded-full text-sm font-bold \${
          isBullish
            ? 'bg-green-500 text-white'
            : 'bg-blue-500 text-white'
        }\`}>
          {strategy?.confidence}%
        </div>
      </div>

      <div className="space-y-3">
        <div>
          <p className="text-sm text-gray-600 dark:text-gray-400">信号</p>
          <p className="text-base font-semibold text-gray-900 dark:text-white">
            {strategy?.signal}
          </p>
        </div>

        <div>
          <p className="text-sm text-gray-600 dark:text-gray-400">P&L</p>
          <p className="text-lg font-bold text-green-600 dark:text-green-400">
            {strategy?.pnl}
          </p>
        </div>

        <div>
          <p className="text-sm text-gray-600 dark:text-gray-400">推理</p>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            {strategy?.reasoning}
          </p>
        </div>

        <div className="pt-2 border-t border-gray-300 dark:border-gray-600">
          <p className="text-xs font-semibold text-gray-600 dark:text-gray-400">
            下一步: {strategy?.nextAction}
          </p>
        </div>
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/dashboard/FusedDecision.tsx': `import React from 'react'
import { motion } from 'framer-motion'
import { FiCheck, FiAlertCircle } from 'react-icons/fi'

interface FusedDecisionProps {
  aggressive: any
  conservative: any
}

export default function FusedDecision({
  aggressive,
  conservative
}: FusedDecisionProps) {
  const avgConfidence = ((aggressive?.confidence || 0) + (conservative?.confidence || 0)) / 2
  const riskLevel = avgConfidence > 75 ? '低' : avgConfidence > 60 ? '中' : '高'

  return (
    <motion.div
      className="p-6 bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 border-2 border-purple-300 dark:border-purple-700 rounded-lg"
      initial={{ scale: 0.95, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
    >
      <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        🤖 融合决策
      </h3>

      <div className="grid grid-cols-3 gap-6">
        <div>
          <p className="text-sm text-gray-600 dark:text-gray-400">最终信号</p>
          <p className="text-2xl font-bold text-green-600 dark:text-green-400">
            做多
          </p>
        </div>

        <div>
          <p className="text-sm text-gray-600 dark:text-gray-400">信心指数</p>
          <div className="flex items-center gap-2">
            <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">
              {Math.round(avgConfidence)}%
            </p>
            <FiCheck className="text-green-500" />
          </div>
        </div>

        <div>
          <p className="text-sm text-gray-600 dark:text-gray-400">风险等级</p>
          <div className="flex items-center gap-2">
            <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">
              {riskLevel}
            </p>
            <FiAlertCircle className="text-orange-500" />
          </div>
        </div>
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/dashboard/RealTimeChart.tsx': `import React from 'react'
import { motion } from 'framer-motion'

export default function RealTimeChart() {
  return (
    <motion.div
      className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        📊 K线图表
      </h3>
      <div className="h-96 flex items-center justify-center bg-gray-50 dark:bg-gray-700 rounded">
        <p className="text-gray-500 dark:text-gray-400">图表加载中...</p>
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/dashboard/OrderBook.tsx': `import React from 'react'
import { motion } from 'framer-motion'

export default function OrderBook() {
  const orders = [
    { price: 50000, amount: 1.2, side: 'buy' },
    { price: 49980, amount: 0.8, side: 'buy' },
    { price: 50020, amount: 0.6, side: 'sell' }
  ]

  return (
    <motion.div
      className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        📖 委托簿
      </h3>
      <div className="space-y-2">
        {orders.map((order, i) => (
          <div key={i} className="flex justify-between text-sm">
            <span className="text-gray-600 dark:text-gray-400">\${order.price}</span>
            <span className={order.side === 'buy' ? 'text-green-500' : 'text-red-500'}>
              {order.amount} BTC
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/dashboard/TradeHistory.tsx': `import React from 'react'
import { motion } from 'framer-motion'

export default function TradeHistory() {
  return (
    <motion.div
      className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        📝 成交记录
      </h3>
      <div className="text-gray-500 dark:text-gray-400 text-center py-8">
        暂无成交记录
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/dashboard/RiskMonitor.tsx': `import React from 'react'
import { motion } from 'framer-motion'

export default function RiskMonitor() {
  return (
    <motion.div
      className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        ⚠️ 风险监控
      </h3>
      <div className="space-y-3">
        <div className="flex justify-between">
          <span className="text-gray-600 dark:text-gray-400">最大回撤</span>
          <span className="font-semibold text-gray-900 dark:text-white">2.3%</span>
        </div>
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/dashboard/PerformanceMetrics.tsx': `import React from 'react'
import { motion } from 'framer-motion'

export default function PerformanceMetrics() {
  const metrics = [
    { label: '账户净值', value: '\$125,430.00', change: '+5.2%' },
    { label: '日收益', value: '\$2,150.00', change: '+1.8%' },
    { label: '周收益率', value: '3.2%', change: '+0.5%' },
    { label: '月收益率', value: '8.7%', change: '+1.2%' }
  ]

  return (
    <>
      {metrics.map((metric, i) => (
        <motion.div
          key={i}
          className="col-span-1 p-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1 }}
        >
          <p className="text-sm text-gray-600 dark:text-gray-400">{metric.label}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">
            {metric.value}
          </p>
          <p className="text-xs text-green-600 dark:text-green-400 mt-1">
            {metric.change}
          </p>
        </motion.div>
      ))}
    </>
  )
}
`,

  'src/frontend/components/dashboard/StrategyChart.tsx': `import React from 'react'
import { motion } from 'framer-motion'

export default function StrategyChart() {
  return (
    <motion.div
      className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        📈 策略对比分析
      </h3>
      <div className="h-64 flex items-center justify-center bg-gray-50 dark:bg-gray-700 rounded">
        <p className="text-gray-500 dark:text-gray-400">分析图表加载中...</p>
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/dashboard/PortfolioChart.tsx': `import React from 'react'
import { motion } from 'framer-motion'

export default function PortfolioChart() {
  return (
    <motion.div
      className="col-span-2 p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        💼 投资组合分布
      </h3>
      <div className="h-64 flex items-center justify-center bg-gray-50 dark:bg-gray-700 rounded">
        <p className="text-gray-500 dark:text-gray-400">投资组合图表加载中...</p>
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/dashboard/PositionsList.tsx': `import React from 'react'
import { motion } from 'framer-motion'

export default function PositionsList() {
  return (
    <motion.div
      className="col-span-1 p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        📊 持仓列表
      </h3>
      <div className="text-gray-500 dark:text-gray-400 text-center py-8">
        暂无持仓
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/components/dashboard/LanguageSettings.tsx': `import React from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'

export default function LanguageSettings() {
  const { i18n, t } = useTranslation()

  return (
    <motion.div
      className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        🌐 {t('settings.language')}
      </h3>

      <div className="space-y-3">
        {['zh-CN', 'en-US'].map((lang) => (
          <label key={lang} className="flex items-center cursor-pointer">
            <input
              type="radio"
              name="language"
              value={lang}
              checked={i18n.language === lang}
              onChange={() => i18n.changeLanguage(lang)}
              className="w-4 h-4"
            />
            <span className="ml-3 text-gray-700 dark:text-gray-300">
              {lang === 'zh-CN' ? '简体中文' : 'English'}
            </span>
          </label>
        ))}
      </div>
    </motion.div>
  )
}
`,

  'src/frontend/store/themeStore.ts': `import create from 'zustand'

interface ThemeStore {
  darkMode: boolean
  toggleDarkMode: () => void
}

export const useThemeStore = create<ThemeStore>((set) => ({
  darkMode: localStorage.getItem('darkMode') === 'true',
  toggleDarkMode: () =>
    set((state) => {
      const newValue = !state.darkMode
      localStorage.setItem('darkMode', String(newValue))
      return { darkMode: newValue }
    })
}))
`,

  'src/frontend/store/tradeStore.ts': `import create from 'zustand'

interface TradeStore {
  currentPage: string
  setCurrentPage: (page: string) => void
  selectedSymbol: string
  setSelectedSymbol: (symbol: string) => void
}

export const useTradeStore = create<TradeStore>((set) => ({
  currentPage: 'dashboard',
  setCurrentPage: (page: string) => set({ currentPage: page }),
  selectedSymbol: 'BTC/USDT',
  setSelectedSymbol: (symbol: string) => set({ selectedSymbol: symbol })
}))
`,

  'src/frontend/locales/i18n.ts': `import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import zhCN from './zh-CN.json'
import enUS from './en-US.json'

const resources = {
  'zh-CN': { translation: zhCN },
  'en-US': { translation: enUS }
}

i18n.use(initReactI18next).init({
  resources,
  lng: localStorage.getItem('language') || 'zh-CN',
  fallbackLng: 'zh-CN',
  interpolation: {
    escapeValue: false
  }
})

export default i18n
`,

  'src/frontend/locales/zh-CN.json': `{
  "app": {
    "title": "双AI交易策略"
  },
  "nav": {
    "dashboard": "仪表板",
    "strategy": "双AI策略",
    "portfolio": "投资组合",
    "backtest": "回测工具",
    "settings": "配置"
  },
  "strategy": {
    "title": "双AI策略面板",
    "description": "激进策略与保守策略的实时分析与融合决策",
    "aggressive": "激进策略 AI",
    "conservative": "保守策略 AI",
    "signals": {
      "longPosition": "做多",
      "shortPosition": "做空",
      "hold": "持有",
      "exit": "平仓"
    },
    "reasoning": {
      "aggressive": "基于技术指标与高频数据的积极交易信号",
      "conservative": "基于风险管理与长期趋势的保守交易建议"
    },
    "actions": {
      "continueLong": "继续加仓",
      "wait": "等待确认",
      "exit": "逐步平仓"
    }
  },
  "portfolio": {
    "title": "投资组合管理"
  },
  "backtest": {
    "title": "策略回测工具",
    "placeholder": "回测功能开发中..."
  },
  "settings": {
    "title": "系统配置",
    "language": "语言设置"
  },
  "common": {
    "loading": "加载中...",
    "error": "出错了",
    "success": "成功",
    "cancel": "取消",
    "confirm": "确认"
  }
}
`,

  'src/frontend/locales/en-US.json': `{
  "app": {
    "title": "Dual AI Trading Strategy"
  },
  "nav": {
    "dashboard": "Dashboard",
    "strategy": "Dual AI",
    "portfolio": "Portfolio",
    "backtest": "Backtest",
    "settings": "Settings"
  },
  "strategy": {
    "title": "Dual AI Strategy Panel",
    "description": "Real-time analysis and fused decisions from aggressive and conservative strategies",
    "aggressive": "Aggressive AI",
    "conservative": "Conservative AI",
    "signals": {
      "longPosition": "Long",
      "shortPosition": "Short",
      "hold": "Hold",
      "exit": "Exit"
    },
    "reasoning": {
      "aggressive": "Active trading signals based on technical indicators and high-frequency data",
      "conservative": "Conservative trading advice based on risk management and long-term trends"
    },
    "actions": {
      "continueLong": "Continue Long",
      "wait": "Wait for Confirmation",
      "exit": "Gradual Exit"
    }
  },
  "portfolio": {
    "title": "Portfolio Management"
  },
  "backtest": {
    "title": "Strategy Backtest Tool",
    "placeholder": "Backtest feature under development..."
  },
  "settings": {
    "title": "System Settings",
    "language": "Language Settings"
  },
  "common": {
    "loading": "Loading...",
    "error": "Error",
    "success": "Success",
    "cancel": "Cancel",
    "confirm": "Confirm"
  }
}
`,

  'src/frontend/styles/index.css': `@import 'tailwindcss/base';
@import 'tailwindcss/components';
@import 'tailwindcss/utilities';

* {
  @apply transition-colors duration-200;
}

html {
  scroll-behavior: smooth;
}

body {
  @apply bg-white dark:bg-gray-900 text-gray-900 dark:text-white;
}

/* Custom scrollbar */
::-webkit-scrollbar {
  @apply w-2;
}

::-webkit-scrollbar-track {
  @apply bg-gray-100 dark:bg-gray-800;
}

::-webkit-scrollbar-thumb {
  @apply bg-gray-400 dark:bg-gray-600 rounded-full hover:bg-gray-500 dark:hover:bg-gray-500;
}

/* Animations */
@keyframes fadeIn {
  from {
    @apply opacity-0;
  }
  to {
    @apply opacity-100;
  }
}

@keyframes slideUp {
  from {
    @apply translate-y-4 opacity-0;
  }
  to {
    @apply translate-y-0 opacity-100;
  }
}

.animate-fadeIn {
  @apply animate-[fadeIn_0.5s_ease-in-out];
}

.animate-slideUp {
  @apply animate-[slideUp_0.5s_ease-out];
}

/* Grid utilities */
.grid-auto-fit {
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}

/* Card styles */
.card {
  @apply p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700;
}

.card-hover {
  @apply card hover:shadow-xl hover:border-gray-300 dark:hover:border-gray-600 transition-all;
}
`,

  'tailwind.config.js': `/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './src/frontend/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: '#3B82F6',
        secondary: '#10B981',
        danger: '#EF4444',
        warning: '#F59E0B',
      },
      fontFamily: {
        sans: ['system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
`,

  'postcss.config.js': `export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
`,

  'tsconfig.json': `{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowJs": true,
    "allowSyntheticDefaultImports": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/frontend/*"],
      "@components/*": ["src/frontend/components/*"],
      "@pages/*": ["src/frontend/components/pages/*"],
      "@hooks/*": ["src/frontend/hooks/*"],
      "@store/*": ["src/frontend/store/*"],
      "@utils/*": ["src/frontend/utils/*"],
      "@types/*": ["src/frontend/types/*"],
      "@services/*": ["src/frontend/services/*"],
      "@locales/*": ["src/frontend/locales/*"]
    }
  },
  "include": ["src"],
  "exclude": ["node_modules", "out", "dist"]
}
`
}

// Write all files
Object.entries(files).forEach(([filePath, content]) => {
  const dir = path.dirname(filePath)
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, content)
    console.log(\`✓ Created: \${filePath}\`)
  }
})

console.log('\\n✨ All files created successfully!')
