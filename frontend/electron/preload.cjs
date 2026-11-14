const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('devharborDesktop', Object.freeze({
  getRuntime: () => ipcRenderer.invoke('devharbor:runtime'),
  restart: () => ipcRenderer.invoke('devharbor:restart'),
}));
