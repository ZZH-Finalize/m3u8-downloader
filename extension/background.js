/**
 * m3u8 下载器扩展 - Background 服务脚本
 */

// 加载工具模块
importScripts('utils.js');

// 初始化右键菜单
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'downloadM3u8',
    title: '下载 m3u8',
    contexts: ['link', 'audio', 'video']
  });
  chrome.contextMenus.create({
    id: 'downloadM3u8Queued',
    title: '下载 m3u8（队列模式）',
    contexts: ['link', 'audio', 'video']
  });
});

// 处理右键菜单点击事件
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'downloadM3u8' || info.menuItemId === 'downloadM3u8Queued') {
    let url = null;
    const useQueue = info.menuItemId === 'downloadM3u8Queued';

    if (info.linkUrl) {
      url = info.linkUrl;
    } else if (info.srcUrl) {
      url = info.srcUrl;
    } else if (info.pageUrl) {
      url = info.pageUrl;
    }

    if (!url) {
      await showTabNotification(tab.id, '无法获取链接地址', 'error');
      return;
    }

    const filename = extractFilenameFromUrl(url);
    const output = filename || 'video.mp4';

    try {
      await chrome.tabs.sendMessage(tab.id, {
        action: 'createDownloadTask',
        url: url,
        output: output,
        queued: useQueue
      });
    } catch (error) {
      await createTaskViaApi(url, output, useQueue);
    }
  }
});

// 通过 API 创建下载任务
async function createTaskViaApi(url, output, queued = false) {
  try {
    const result = await chrome.storage.sync.get(['m3u8DownloaderConfig']);
    const config = result.m3u8DownloaderConfig || {
      host: '127.0.0.1',
      port: '6900',
      protocol: 'http',
      defaultThreads: 8,
      defaultEncoding: 'copy',
      defaultEncoder: 'software'
    };

    const protocol = config.protocol || 'http';
    const baseUrl = `${protocol}://${config.host}:${config.port}`;

    const response = await fetch(`${baseUrl}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        threads: config.defaultThreads || 8,
        output_name: output,
        encoder: config.defaultEncoder || 'software',
        output_encoding: config.defaultEncoding || 'copy',
        keep_cache: false,
        queued: queued
      })
    });

    const resultData = await response.json();

    if (response.ok) {
      await showGlobalNotification(`任务已创建：${output}`, 'success');
    } else {
      await showGlobalNotification(`创建失败：${resultData.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    await showGlobalNotification(`请求失败：${error.message}`, 'error');
  }
}

// 在当前标签页显示通知
async function showTabNotification(tabId, message, type) {
  try {
    await chrome.tabs.sendMessage(tabId, {
      action: 'showNotification',
      message: message,
      type: type
    });
  } catch (error) {
    await showGlobalNotification(message, type);
  }
}

// 全局通知（使用 Chrome 通知系统）
async function showGlobalNotification(message, type) {
  if (Notification.permission !== 'granted') {
    await Notification.requestPermission();
  }

  if (Notification.permission === 'granted') {
    new Notification('m3u8 下载器', {
      body: message,
      icon: 'icons/icon48.png'
    });
  }
}
