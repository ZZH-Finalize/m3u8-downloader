// 初始化右键菜单
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'downloadM3u8',
    title: '下载 m3u8',
    contexts: ['link', 'audio', 'video']
  });
});

// 从 URL 提取文件名（与 popup.js 保持一致）
function extractFilenameFromUrl(url) {
  try {
    const urlObj = new URL(url);
    const pathname = urlObj.pathname;
    const filename = pathname.substring(pathname.lastIndexOf('/') + 1);

    if (!filename || filename === '') {
      return null;
    }

    const decodedFilename = decodeURIComponent(filename);
    const cleanFilename = decodedFilename.split('?')[0];
    const nameWithoutExt = cleanFilename.includes('.')
      ? cleanFilename.substring(0, cleanFilename.lastIndexOf('.'))
      : cleanFilename;

    return nameWithoutExt + '.mp4';
  } catch (e) {
    const match = url.match(/([^\/?#]+)(?:\?.*)?$/);
    if (match && match[1]) {
      const filename = decodeURIComponent(match[1]);
      const nameWithoutExt = filename.includes('.')
        ? filename.substring(0, filename.lastIndexOf('.'))
        : filename;
      return nameWithoutExt + '.mp4';
    }
    return null;
  }
}

// 处理右键菜单点击事件
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'downloadM3u8') {
    let url = null;

    // 根据点击的上下文获取 URL
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

    // 提取文件名
    const filename = extractFilenameFromUrl(url);
    const output = filename || 'video.mp4';

    // 发送消息给 popup 创建下载任务
    try {
      await chrome.tabs.sendMessage(tab.id, {
        action: 'createDownloadTask',
        url: url,
        output: output
      });
    } catch (error) {
      // 如果 popup 未打开，通过 background 直接调用 API
      await createTaskViaApi(url, output);
    }
  }
});

// 通过 API 创建下载任务
async function createTaskViaApi(url, output) {
  try {
    // 从存储中获取配置
    const result = await chrome.storage.sync.get(['m3u8DownloaderConfig']);
    const config = result.m3u8DownloaderConfig || {
      host: '127.0.0.1',
      port: '6900',
      protocol: 'http',
      defaultThreads: 8
    };

    const protocol = config.protocol || 'http';
    const baseUrl = `${protocol}://${config.host}:${config.port}`;

    const response = await fetch(`${baseUrl}/api/download`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        url: url,
        threads: config.defaultThreads || 8,
        output_name: output,
        keep_cache: false,
        queued: false  // 右键菜单默认不使用队列
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

// 在当前标签页显示通知（通过注入内容脚本）
async function showTabNotification(tabId, message, type) {
  try {
    await chrome.tabs.sendMessage(tabId, {
      action: 'showNotification',
      message: message,
      type: type
    });
  } catch (error) {
    // 如果无法发送消息，使用 chrome.notification
    await showGlobalNotification(message, type);
  }
}

// 全局通知（使用 Chrome 通知系统）
async function showGlobalNotification(message, type) {
  // 首先请求通知权限
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
