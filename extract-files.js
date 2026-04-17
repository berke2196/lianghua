#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

console.log('🚀 Electron 应用文件提取工具\n');

// Directory structure
const directories = [
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

// 创建所有目录
console.log('📁 Creating directories...');
directories.forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`  ✓ ${dir}`);
  }
});

// 所有源文件内容
const files = {
  // Main process
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

  // Preload
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

  // Frontend entry
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

  // Stores
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

  // i18n
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

  'src/frontend/locales/zh-CN.json': JSON.stringify({
    "app": { "title": "双AI交易策略" },
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
    "portfolio": { "title": "投资组合管理" },
    "backtest": { "title": "策略回测工具", "placeholder": "回测功能开发中..." },
    "settings": { "title": "系统配置", "language": "语言设置" },
    "common": {
      "loading": "加载中...",
      "error": "出错了",
      "success": "成功",
      "cancel": "取消",
      "confirm": "确认"
    }
  }, null, 2),

  'src/frontend/locales/en-US.json': JSON.stringify({
    "app": { "title": "Dual AI Trading Strategy" },
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
    "portfolio": { "title": "Portfolio Management" },
    "backtest": { "title": "Strategy Backtest Tool", "placeholder": "Backtest feature under development..." },
    "settings": { "title": "System Settings", "language": "Language Settings" },
    "common": {
      "loading": "Loading...",
      "error": "Error",
      "success": "Success",
      "cancel": "Cancel",
      "confirm": "Confirm"
    }
  }, null, 2),

  // Styles
  'src/frontend/styles/index.css': \`@import 'tailwindcss/base';
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
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

::-webkit-scrollbar {
  @apply w-2;
}

::-webkit-scrollbar-track {
  @apply bg-gray-100 dark:bg-gray-800;
}

::-webkit-scrollbar-thumb {
  @apply bg-gray-400 dark:bg-gray-600 rounded-full hover:bg-gray-500;
}

@keyframes fadeIn {
  from { @apply opacity-0; }
  to { @apply opacity-100; }
}

@keyframes slideUp {
  from { @apply translate-y-4 opacity-0; }
  to { @apply translate-y-0 opacity-100; }
}

.animate-fadeIn {
  @apply animate-[fadeIn_0.5s_ease-in-out];
}

.animate-slideUp {
  @apply animate-[slideUp_0.5s_ease-out];
}

.card {
  @apply p-6 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700;
}

.card-hover {
  @apply card hover:shadow-xl hover:border-gray-300 dark:hover:border-gray-600 transition-all;
}
\`
};

// 创建所有文件
console.log('\n📝 Creating source files...');
let created = 0;
let skipped = 0;

Object.entries(files).forEach(([filePath, content]) => {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(\`  ✓ \${filePath}\`);
    created++;
  } else {
    console.log(\`  ⚠ \${filePath} (exists)\`);
    skipped++;
  }
});

console.log(\`\n✨ Complete! Created: \${created}, Skipped: \${skipped}\`);
console.log('\\n📖 Next steps:');
console.log('  1. npm install');
console.log('  2. Copy all component files from documentation');
console.log('  3. npm run dev');
