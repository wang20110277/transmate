const { app, BrowserWindow } = require('electron');
const path = require('node:path');

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
  createWindow();

  // macOS:点击 dock 图标时重新创建窗口
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  // macOS:窗口关闭后应用常驻
  if (process.platform !== 'darwin') app.quit();
});
