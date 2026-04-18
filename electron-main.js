const { app, BrowserWindow, Menu, ipcMain } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');

let mainWindow;

// 创建主窗口
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: 'AsterDex HFT Trader v5.0',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      webSecurity: true,                     // ✅ FIXED: Enable web security
      allowRunningInsecureContent: false,    // ✅ FIXED: Disable mixed content
      sandbox: true,                         // ✅ ADDED: Enable sandbox
      preload: path.join(__dirname, 'preload.js')  // ✅ ADDED: Safe IPC bridge
    }
  });

  // 始终加载新的 React 前端（端口 3000）
  const startUrl = 'http://localhost:3000';
  console.log('Loading URL:', startUrl);
  mainWindow.loadURL(startUrl);

  // 开发调试工具（按 F12 手动开启即可）
  // mainWindow.webContents.openDevTools();

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  mainWindow.on('ready-to-show', () => {
    mainWindow.show();
  });
}

// App事件
app.on('ready', createWindow);
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

// IPC处理
ipcMain.handle('get-trading-data', async () => {
  try {
    const response = await fetch('http://localhost:8000/api/trading/status');
    return await response.json();
  } catch (error) {
    console.error('获取数据失败:', error);
    return null;
  }
});

// 菜单
const template = [
  {
    label: '文件',
    submenu: [{ label: '退出', accelerator: 'CmdOrCtrl+Q', click: () => app.quit() }]
  },
  {
    label: '编辑',
    submenu: [
      { label: '撤销', accelerator: 'CmdOrCtrl+Z', role: 'undo' },
      { label: '重做', accelerator: 'CmdOrCtrl+Y', role: 'redo' },
      { type: 'separator' },
      { label: '剪切', accelerator: 'CmdOrCtrl+X', role: 'cut' },
      { label: '复制', accelerator: 'CmdOrCtrl+C', role: 'copy' },
      { label: '粘贴', accelerator: 'CmdOrCtrl+V', role: 'paste' }
    ]
  },
  {
    label: '查看',
    submenu: [
      { label: '重新加载', accelerator: 'CmdOrCtrl+R', role: 'reload' },
      { label: '全屏', accelerator: 'F11', role: 'togglefullscreen' }
    ]
  }
];

Menu.setApplicationMenu(Menu.buildFromTemplate(template));

console.log('Electron 主进程已启动');

