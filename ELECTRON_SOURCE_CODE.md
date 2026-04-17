# 完整 Electron 桌面应用源代码文档
# ====================================
# 此文件包含所有必需的源文件，请按照 FILE_PATH 指示保存到相应位置

## ============ src/main/index.ts ============
```typescript
import { BrowserWindow, app, ipcMain } from 'electron'
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
      path.join(__dirname, `../renderer/${MAIN_WINDOW_VITE_NAME}/index.html`)
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
```

## ============ src/preload/index.ts ============
```typescript
import { contextBridge, ipcRenderer } from 'electron'

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
```

## ============ src/frontend/index.html ============
```html
<!DOCTYPE html>
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
```

## ============ src/frontend/index.tsx ============
```typescript
import React from 'react'
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
```

## ============ src/frontend/App.tsx ============
```typescript
import React, { useEffect } from 'react'
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
```

## ============ 完整文件列表和说明 ============

需要创建的文件结构：
```
src/
├── main/
│   └── index.ts
├── preload/
│   └── index.ts
└── frontend/
    ├── index.html
    ├── index.tsx
    ├── App.tsx
    ├── components/
    │   ├── Navigation.tsx
    │   ├── pages/
    │   │   ├── Dashboard.tsx
    │   │   ├── DualStrategyPanel.tsx
    │   │   ├── PortfolioView.tsx
    │   │   ├── BacktestView.tsx
    │   │   └── SettingsView.tsx
    │   └── dashboard/
    │       ├── StrategyCard.tsx
    │       ├── FusedDecision.tsx
    │       ├── RealTimeChart.tsx
    │       ├── OrderBook.tsx
    │       ├── TradeHistory.tsx
    │       ├── RiskMonitor.tsx
    │       ├── PerformanceMetrics.tsx
    │       ├── StrategyChart.tsx
    │       ├── PortfolioChart.tsx
    │       ├── PositionsList.tsx
    │       └── LanguageSettings.tsx
    ├── store/
    │   ├── themeStore.ts
    │   └── tradeStore.ts
    ├── locales/
    │   ├── i18n.ts
    │   ├── zh-CN.json
    │   └── en-US.json
    └── styles/
        └── index.css
```
