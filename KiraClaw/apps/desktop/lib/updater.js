function setupAutoUpdater() {
  let autoUpdater;
  let log;
  let updateLifecycle = null;

  try {
    ({ autoUpdater } = require("electron-updater"));
    log = require("electron-log");
  } catch {
    return;
  }

  const fs = require("fs");
  const path = require("path");
  const { app, dialog, BrowserWindow } = require("electron");
  if (!app.isPackaged) {
    return;
  }

  const updateConfigPath = path.join(process.resourcesPath, "app-update.yml");
  if (!fs.existsSync(updateConfigPath)) {
    return;
  }

  autoUpdater.logger = log;
  autoUpdater.logger.transports.file.level = "info";
  autoUpdater.logger.info(`Using packaged app-update.yml: ${updateConfigPath}`);
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;
  app.on("before-quit-for-update", () => {
    updateLifecycle = "installing";
    log.info("Auto-update: before-quit-for-update");
  });
  let promptingForDownload = false;
  let promptingForRestart = false;

  autoUpdater.on("checking-for-update", () => {
    log.info("Auto-update: checking for update");
  });

  autoUpdater.on("update-available", async (info) => {
    log.info("Auto-update: update available", info);
    if (promptingForDownload) {
      return;
    }
    promptingForDownload = true;
    try {
      const focusedWindow = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0] || null;
      const result = await dialog.showMessageBox(focusedWindow, {
        type: "info",
        buttons: ["Download Now", "Later"],
        defaultId: 0,
        cancelId: 1,
        title: "Update Available",
        message: `Version ${info.version} is available.`,
        detail: "Download the latest KiraClaw update in the background?",
      });
      if (result.response === 0) {
        await autoUpdater.downloadUpdate();
      }
    } catch (error) {
      log.error("Auto-update available dialog failed:", error);
    } finally {
      promptingForDownload = false;
    }
  });

  autoUpdater.on("update-not-available", (info) => {
    log.info("Auto-update: no update available", info);
  });

  autoUpdater.on("download-progress", (progress) => {
    log.info("Auto-update: download progress", progress);
  });

  autoUpdater.on("update-downloaded", async (info) => {
    log.info("Auto-update: update downloaded", info);
    if (promptingForRestart) {
      return;
    }
    promptingForRestart = true;
    try {
      const focusedWindow = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0] || null;
      const result = await dialog.showMessageBox(focusedWindow, {
        type: "info",
        buttons: ["Restart Now", "Later"],
        defaultId: 0,
        cancelId: 1,
        title: "Update Ready",
        message: `Version ${info.version} has been downloaded.`,
        detail: "Restart now to apply the latest KiraClaw update.",
      });
      if (result.response === 0) {
        setImmediate(() => autoUpdater.quitAndInstall(false, true));
      }
    } catch (error) {
      log.error("Auto-update dialog failed:", error);
    } finally {
      promptingForRestart = false;
    }
  });

  autoUpdater.on("error", (error) => {
    log.error("Auto-update error:", error);
  });

  autoUpdater.checkForUpdatesAndNotify().catch((error) => {
    log.error("Auto-update check failed:", error);
  });

  return {
    isInstallingUpdate() {
      return updateLifecycle === "installing";
    },
  };
}

module.exports = {
  setupAutoUpdater,
};
