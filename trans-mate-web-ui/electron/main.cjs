const { app, BrowserWindow } = require('electron');
const path = require('node:path');
// v3 为具名导出；兼容旧版默认导出
const _updateModule = require('update-electron-app');
const updateElectronApp =
  typeof _updateModule === 'function' ? _updateModule : _updateModule.updateElectronApp;

// Windows Squirrel 安装/卸载事件处理(forge 默认依赖)
if (require('electron-squirrel-startup')) {
  app.quit();
}

// forge 打包后 app.isPackaged === true;开发态直接 electron . 运行时为 false
const isDev = !app.isPackaged;

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
    // macOS 隐藏标题栏区域:红绿灯按钮浮于内容之上,页面样式已预留空间(见 App.vue / AppHeader.vue)
    ...(process.platform === 'darwin' && {
      titleBarStyle: 'hiddenInset',
      trafficLightPosition: { x: 16, y: 14 },
    }),
  });

  if (isDev) {
    // 开发:加载 Vite dev server,享受 HMR
    win.loadURL('http://localhost:3000');
    win.webContents.openDevTools();
  } else {
    // 生产:加载 vite build 产物
    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }
}

app.whenReady().then(() => {
  // 窗口创建放在最前，任何更新逻辑异常都不能阻止界面显示
  createWindow();

  // 自动更新：从 update.electronjs.org 检查 GitHub Release 新版本（仅打包后生效）
  if (!isDev && typeof updateElectronApp === 'function') {
    try {
      updateElectronApp({
        updateInterval: '1 hour',
        notifyUser: true,
      });
    } catch (err) {
      console.error('自动更新初始化失败(不影响使用):', err);
    }
  }

  // macOS:点击 dock 图标时重新创建窗口
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  // macOS:窗口关闭后应用常驻
  if (process.platform !== 'darwin') app.quit();
});
