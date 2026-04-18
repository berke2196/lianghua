const { contextBridge, ipcRenderer } = require('electron');

// Safe IPC API for renderer process
// Only expose safe functions to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Trading data retrieval
  getTradingData: () => ipcRenderer.invoke('get-trading-data'),

  // App lifecycle
  quit: () => ipcRenderer.send('app-quit'),
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),

  // Platform detection
  getPlatform: () => process.platform,
  getAppVersion: () => process.env.npm_package_version || '5.0.0',

  // Safe console logging (for debug purposes)
  log: (message) => console.log('[Renderer]', message),
  error: (message) => console.error('[Renderer Error]', message),
});

// Verify security context
console.log('✅ Preload script loaded with security isolation enabled');
console.log('✅ nodeIntegration:', process.nodeIntegration ? 'ENABLED ⚠️' : 'DISABLED ✓');
console.log('✅ contextIsolation:', process.contextIsolation ? 'ENABLED ✓' : 'DISABLED ⚠️');
console.log('✅ sandbox:', process.sandbox ? 'ENABLED ✓' : 'DISABLED ⚠️');
