const fs = require('fs');
const path = require('path');

// 创建所有目录
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

console.log('📁 Creating directories...');
dirs.forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`  ✓ ${dir}`);
  }
});

// 所有文件内容
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
`
};

console.log('\n📝 Creating source files...');
Object.entries(files).forEach(([filePath, content]) => {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  
  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`  ✓ ${filePath}`);
  } else {
    console.log(`  ⚠ ${filePath} (exists)`);
  }
});

console.log('\n✨ Setup complete!');
