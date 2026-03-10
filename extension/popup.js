// API 基础配置
const DEFAULT_CONFIG = {
  host: '127.0.0.1',
  port: '6900',
  defaultThreads: 8,
  autoRefresh: 2000
};

// 全局状态
let selectedTaskId = null;
let autoRefreshTimer = null;
let config = { ...DEFAULT_CONFIG };
let isServerOnline = false;  // 服务器在线状态

// 缓存管理状态
let selectedCacheId = null;
let currentCaches = [];
let activeTaskCacheIds = new Set();  // 正在执行任务的 cache ID 集合

// 任务详情状态
let selectedTaskIdForDetail = null;  // 当前打开详情的任务 ID

// DOM 元素
const elements = {
  taskList: document.getElementById('task-list'),
  emptyState: document.getElementById('empty-state'),
  loadingState: document.getElementById('loading-state'),
  addTaskModal: document.getElementById('add-task-modal'),
  settingsModal: document.getElementById('settings-modal'),
  cacheModal: document.getElementById('cache-modal'),
  cacheDetailModal: document.getElementById('cache-detail-modal'),
  taskDetailModal: document.getElementById('task-detail-modal'),
  addTaskForm: document.getElementById('add-task-form'),
  settingsForm: document.getElementById('settings-form'),
  serverStatus: document.getElementById('server-status'),
  toast: document.getElementById('toast'),
  btnAddTask: document.getElementById('btn-add-task'),
  btnDeleteTask: document.getElementById('btn-delete-task'),
  btnRefresh: document.getElementById('btn-refresh'),
  btnSettings: document.getElementById('btn-settings'),
  btnCache: document.getElementById('btn-cache'),
  cacheList: document.getElementById('cache-list'),
  cacheEmptyState: document.getElementById('cache-empty-state'),
  cacheLoadingState: document.getElementById('cache-loading-state'),
  cacheDetailContent: document.getElementById('cache-detail-content'),
  taskDetailContent: document.getElementById('task-detail-content')
};

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();
  setupEventListeners();
  await checkServerStatus();  // 先检查服务器状态
  await loadTaskList();  // 再加载任务列表
  // startAutoRefresh 已在 checkServerStatus 中根据状态自动处理
});

// 加载配置
async function loadConfig() {
  try {
    const result = await chrome.storage.sync.get(['m3u8DownloaderConfig']);
    if (result.m3u8DownloaderConfig) {
      config = { ...DEFAULT_CONFIG, ...result.m3u8DownloaderConfig };
    }
    applyConfigToUI();
  } catch (error) {
    console.error('加载配置失败:', error);
  }
}

// 保存配置
async function saveConfig() {
  try {
    await chrome.storage.sync.set({ m3u8DownloaderConfig: config });
  } catch (error) {
    console.error('保存配置失败:', error);
  }
}

// 应用配置到 UI
function applyConfigToUI() {
  const protocol = config.protocol || 'http';
  document.getElementById('setting-address').value = `${protocol}://${config.host}:${config.port}`;
  document.getElementById('setting-default-threads').value = config.defaultThreads;
  document.getElementById('setting-auto-refresh').value = String(config.autoRefresh);
}

// 获取 API 基础 URL
function getApiBaseUrl() {
  return `${config.protocol || 'http'}://${config.host}:${config.port}`;
}

// 解析服务器地址，自动识别协议、主机和端口
function parseServerAddress(address) {
  let protocol = 'http';
  let host = '127.0.0.1';
  let port = '6900';
  
  if (!address || !address.trim()) {
    return { protocol, host, port };
  }
  
  let trimmed = address.trim();
  
  // 检查是否包含协议前缀
  const protocolMatch = trimmed.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):\/\//);
  if (protocolMatch) {
    protocol = protocolMatch[1].toLowerCase();
    trimmed = trimmed.substring(protocolMatch[0].length);
  }
  
  // 检查是否包含端口
  const portMatch = trimmed.match(/:(\d+)$/);
  if (portMatch) {
    port = portMatch[1];
    trimmed = trimmed.substring(0, trimmed.length - portMatch[0].length);
  }
  
  // 剩余部分为主机名（IP 或域名）
  host = trimmed || '127.0.0.1';
  
  return { protocol, host, port };
}

// 设置事件监听器
function setupEventListeners() {
  // 工具栏按钮
  elements.btnAddTask.addEventListener('click', showAddTaskModal);
  elements.btnDeleteTask.addEventListener('click', deleteSelectedTask);
  elements.btnSettings.addEventListener('click', showSettingsModal);
  elements.btnRefresh.addEventListener('click', handleRefresh);
  elements.btnCache.addEventListener('click', showCacheModal);

  // 模态框关闭按钮
  document.getElementById('close-add-modal').addEventListener('click', hideAddTaskModal);
  document.getElementById('close-settings-modal').addEventListener('click', hideSettingsModal);
  document.getElementById('cancel-add-task').addEventListener('click', hideAddTaskModal);
  document.getElementById('cancel-settings').addEventListener('click', hideSettingsModal);
  document.getElementById('close-cache-modal').addEventListener('click', hideCacheModal);
  document.getElementById('close-cache-detail-modal').addEventListener('click', hideCacheDetailModal);
  document.getElementById('close-cache').addEventListener('click', hideCacheModal);
  document.getElementById('close-cache-detail').addEventListener('click', hideCacheDetailModal);
  document.getElementById('close-task-detail-modal').addEventListener('click', hideTaskDetailModal);
  document.getElementById('close-task-detail').addEventListener('click', hideTaskDetailModal);

  // 任务详情操作按钮
  document.getElementById('btn-cancel-task').addEventListener('click', handleCancelTaskFromDetail);

  // 缓存管理按钮
  document.getElementById('btn-refresh-cache').addEventListener('click', loadCacheList);
  document.getElementById('btn-clear-cache').addEventListener('click', handleClearCache);
  document.getElementById('btn-update-cache').addEventListener('click', handleUpdateCache);
  document.getElementById('btn-delete-cache').addEventListener('click', handleDeleteCache);

  // 表单提交
  elements.addTaskForm.addEventListener('submit', handleAddTask);
  elements.settingsForm.addEventListener('submit', handleSaveSettings);

  // 点击模态框外部关闭
  elements.addTaskModal.addEventListener('click', (e) => {
    if (e.target === elements.addTaskModal) hideAddTaskModal();
  });
  elements.settingsModal.addEventListener('click', (e) => {
    if (e.target === elements.settingsModal) hideSettingsModal();
  });
  elements.cacheModal.addEventListener('click', (e) => {
    if (e.target === elements.cacheModal) hideCacheModal();
  });
  elements.cacheDetailModal.addEventListener('click', (e) => {
    if (e.target === elements.cacheDetailModal) hideCacheDetailModal();
  });
  elements.taskDetailModal.addEventListener('click', (e) => {
    if (e.target === elements.taskDetailModal) hideTaskDetailModal();
  });

  // 设置页面输入变化
  document.getElementById('setting-address').addEventListener('change', (e) => {
    const parsed = parseServerAddress(e.target.value);
    config.protocol = parsed.protocol;
    config.host = parsed.host;
    config.port = parsed.port;
  });
  document.getElementById('setting-default-threads').addEventListener('change', (e) => {
    config.defaultThreads = parseInt(e.target.value) || 8;
  });
  document.getElementById('setting-auto-refresh').addEventListener('change', (e) => {
    config.autoRefresh = parseInt(e.target.value) || 0;
    restartAutoRefresh();
  });

  // URL 输入框变化时自动解析文件名
  document.getElementById('task-url').addEventListener('input', (e) => {
    const url = e.target.value.trim();
    if (url) {
      const filename = extractFilenameFromUrl(url);
      if (filename) {
        document.getElementById('task-output').value = filename;
      }
    }
  });

  // 监听来自 background 的消息
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'createDownloadTask') {
      handleQuickDownload(message.url, message.output);
      sendResponse({ success: true });
    } else if (message.action === 'showNotification') {
      showToast(message.message, message.type);
      sendResponse({ success: true });
    }
    return true; // 保持消息通道开启
  });
}

// 显示添加任务模态框
function showAddTaskModal() {
  // 服务器离线时不响应
  if (!isServerOnline) {
    showToast('服务器离线，无法添加任务', 'error');
    return;
  }
  // 重置表单
  document.getElementById('task-url').value = '';
  document.getElementById('task-threads').value = config.defaultThreads;
  document.getElementById('task-output').value = 'video.mp4';

  elements.addTaskModal.style.display = 'flex';
  document.getElementById('task-url').focus();
}

// 隐藏添加任务模态框
function hideAddTaskModal() {
  elements.addTaskModal.style.display = 'none';
}

// 显示设置模态框
async function showSettingsModal() {
  applyConfigToUI();
  elements.settingsModal.style.display = 'flex';
}

// 隐藏设置模态框
function hideSettingsModal() {
  elements.settingsModal.style.display = 'none';
}

// 处理添加任务
async function handleAddTask(e) {
  e.preventDefault();

  const taskData = {
    url: document.getElementById('task-url').value.trim(),
    threads: parseInt(document.getElementById('task-threads').value) || config.defaultThreads,
    output: document.getElementById('task-output').value.trim() || 'video.mp4',
    keep_cache: document.getElementById('task-keep-cache').checked
  };

  if (!taskData.url) {
    showToast('请输入 m3u8 链接', 'error');
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/download`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(taskData)
    });

    const result = await response.json();

    if (result.success) {
      showToast(`任务已提交：${result.task_id}`, 'success');
      hideAddTaskModal();
      await loadTaskList();
    } else {
      showToast(`提交失败：${result.error || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// 快速下载（用于右键菜单）
async function handleQuickDownload(url, output) {
  if (!url) {
    showToast('无效的链接', 'error');
    return;
  }

  const taskData = {
    url: url,
    threads: config.defaultThreads || 8,
    output: output || 'video.mp4',
    keep_cache: false
  };

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/download`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(taskData)
    });

    const result = await response.json();

    if (result.success) {
      showToast(`任务已创建：${output}`, 'success');
      await loadTaskList();
    } else {
      showToast(`创建失败：${result.error || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// 处理保存设置
async function handleSaveSettings(e) {
  e.preventDefault();

  const address = document.getElementById('setting-address').value.trim();
  const parsed = parseServerAddress(address);
  
  config.protocol = parsed.protocol;
  config.host = parsed.host;
  config.port = parsed.port;
  config.defaultThreads = parseInt(document.getElementById('setting-default-threads').value) || 8;
  config.autoRefresh = parseInt(document.getElementById('setting-auto-refresh').value) || 0;

  await saveConfig();
  hideSettingsModal();
  await checkServerStatus();
  await loadTaskList();
  showToast('设置已保存', 'success');
}

// 加载任务列表
async function loadTaskList() {
  // 只在服务器在线时加载任务列表
  if (!isServerOnline) {
    renderOfflineState();
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();

    if (result.success) {
      renderTaskList(result.tasks || []);
    } else {
      renderEmptyState();
    }
  } catch (error) {
    console.error('加载任务列表失败:', error);
    // 请求失败时不更新服务器状态，直接显示空状态
    renderEmptyState();
  }
}

// 渲染任务列表（增量更新，避免闪烁）
function renderTaskList(tasks) {
  // 处理空状态
  if (tasks.length === 0) {
    elements.taskList.innerHTML = '';
    elements.taskList.style.display = 'none';
    elements.emptyState.style.display = 'flex';
    elements.loadingState.style.display = 'none';
    return;
  }

  // 有任务时，确保任务列表可见，空状态和加载状态隐藏
  elements.taskList.style.display = 'block';
  elements.emptyState.style.display = 'none';
  elements.loadingState.style.display = 'none';

  // 获取现有任务元素
  const existingTaskElements = new Map();
  elements.taskList.querySelectorAll('.task-item').forEach(el => {
    const taskId = el.dataset.taskId;
    if (taskId) {
      existingTaskElements.set(taskId, el);
    }
  });

  const taskIdsInNewList = new Set();

  // 遍历新任务数据，更新或创建任务元素
  tasks.forEach((task) => {
    const taskId = task.task_id;
    const existingEl = existingTaskElements.get(taskId);

    if (existingEl) {
      // 任务已存在，检查是否需要更新
      if (shouldUpdateTask(existingEl, task)) {
        updateTaskElement(existingEl, task);
      }
      // 保持选中状态
      if (taskId === selectedTaskId) {
        existingEl.classList.add('selected');
      }
      taskIdsInNewList.add(taskId);
    } else {
      // 新任务，创建元素
      const taskElement = createTaskElement(task);
      elements.taskList.appendChild(taskElement);
    }
  });

  // 删除不再存在的任务元素
  existingTaskElements.forEach((el, taskId) => {
    if (!taskIdsInNewList.has(taskId)) {
      el.remove();
    }
  });
}

// 判断任务是否需要更新
function shouldUpdateTask(element, task) {
  const existingStatus = element.dataset.status;
  const existingPercent = element.dataset.progressPercent;
  const existingDownloaded = element.dataset.segmentsDownloaded;

  const segmentsDownloaded = task.segments_downloaded || 0;
  const totalSegments = task.total_segments || 0;
  const progressPercent = totalSegments > 0 ? (segmentsDownloaded / totalSegments) * 100 : 0;
  const status = task.status || 'downloading';

  return (
    existingStatus !== status ||
    existingPercent !== String(progressPercent) ||
    existingDownloaded !== String(segmentsDownloaded)
  );
}

// 创建任务元素
function createTaskElement(task) {
  const div = document.createElement('div');
  div.className = 'task-item';
  div.dataset.taskId = task.task_id;

  const segmentsDownloaded = task.segments_downloaded || 0;
  const totalSegments = task.total_segments || 0;
  const progressPercent = totalSegments > 0 ? (segmentsDownloaded / totalSegments) * 100 : 0;
  const outputName = task.output_name || 'video.mp4';
  const status = task.status || 'downloading';

  // 存储当前状态用于比较
  div.dataset.status = status;
  div.dataset.progressPercent = String(progressPercent);
  div.dataset.segmentsDownloaded = String(segmentsDownloaded);

  if (task.task_id === selectedTaskId) {
    div.classList.add('selected');
  }

  // 失败任务添加重试按钮
  const retryButton = status === 'failed' ? `
    <button class="retry-btn" title="重试下载" data-task-id="${task.task_id}">
      ↻ 重试
    </button>
  ` : '';

  div.innerHTML = `
    <div class="task-header">
      <span class="task-id">${task.task_id}</span>
      <span class="task-status ${status}">${getStatusText(status)}</span>
    </div>
    <div class="task-output">${escapeHtml(outputName)}</div>
    <div class="task-progress">
      <div class="progress-bar-container">
        <div class="progress-bar" style="width: ${progressPercent}%"></div>
      </div>
      <div class="progress-info">
        <span class="progress-text">${progressPercent.toFixed(1)}%</span>
        <span class="segments-info">${segmentsDownloaded}/${totalSegments}</span>
      </div>
      <div class="task-step">${escapeHtml(getStatusText(status))}</div>
      ${retryButton}
    </div>
  `;

  div.addEventListener('click', (e) => {
    // 如果点击的是重试按钮，不触发选中
    if (e.target.classList.contains('retry-btn')) {
      return;
    }
    // 取消之前的选中状态
    document.querySelectorAll('.task-item').forEach(item => {
      item.classList.remove('selected');
    });

    // 选中当前任务
    div.classList.add('selected');
    selectedTaskId = task.task_id;
  });

  // 双击打开任务详情
  div.addEventListener('dblclick', () => {
    showTaskDetail(task.task_id);
  });

  // 为重试按钮添加事件监听器
  const retryBtn = div.querySelector('.retry-btn');
  if (retryBtn) {
    retryBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const taskId = retryBtn.dataset.taskId;
      retryTask(taskId);
    });
  }

  return div;
}

// 获取状态文本
function getStatusText(status) {
  const statusMap = {
    pending: '等待中',
    parsing: '解析中',
    downloading: '下载中',
    merging: '合并中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  };
  return statusMap[status] || status;
}

// 更新任务元素（只更新变化的部分）
function updateTaskElement(element, task) {
  const segmentsDownloaded = task.segments_downloaded || 0;
  const totalSegments = task.total_segments || 0;
  const progressPercent = totalSegments > 0 ? (segmentsDownloaded / totalSegments) * 100 : 0;
  const outputName = task.output_name || 'video.mp4';
  const status = task.status || 'downloading';

  // 更新状态标记
  element.dataset.status = status;
  element.dataset.progressPercent = String(progressPercent);
  element.dataset.segmentsDownloaded = String(segmentsDownloaded);

  // 更新状态标签
  const statusEl = element.querySelector('.task-status');
  if (statusEl) {
    statusEl.className = `task-status ${status}`;
    statusEl.textContent = getStatusText(status);
  }

  // 更新进度条
  const progressBar = element.querySelector('.progress-bar');
  if (progressBar) {
    progressBar.style.width = `${progressPercent}%`;
  }

  // 更新进度文本
  const progressText = element.querySelector('.progress-text');
  if (progressText) {
    progressText.textContent = `${progressPercent.toFixed(1)}%`;
  }

  // 更新分片信息
  const segmentsInfo = element.querySelector('.segments-info');
  if (segmentsInfo) {
    segmentsInfo.textContent = `${segmentsDownloaded}/${totalSegments}`;
  }

  // 更新当前步骤
  const taskStep = element.querySelector('.task-step');
  if (taskStep) {
    taskStep.textContent = escapeHtml(getStatusText(status));
  }

  // 更新输出文件名
  const taskOutput = element.querySelector('.task-output');
  if (taskOutput) {
    taskOutput.textContent = escapeHtml(outputName);
  }

  // 更新或添加重试按钮
  let retryBtn = element.querySelector('.retry-btn');
  if (status === 'failed') {
    if (!retryBtn) {
      const progressContainer = element.querySelector('.task-progress');
      if (progressContainer) {
        retryBtn = document.createElement('button');
        retryBtn.className = 'retry-btn';
        retryBtn.title = '重试下载';
        retryBtn.dataset.taskId = task.task_id;
        retryBtn.innerHTML = `↻ 重试`;
        retryBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const taskId = retryBtn.dataset.taskId;
          retryTask(taskId);
        });
        progressContainer.appendChild(retryBtn);
      }
    }
  } else if (retryBtn) {
    retryBtn.remove();
  }
}

// 重试任务
async function retryTask(taskId) {
  if (!confirm(`确定要重试任务 ${taskId} 吗？`)) {
    return;
  }

  try {
    // 先查询任务详情获取 URL
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const result = await response.json();
    
    if (!result.success) {
      showToast(`获取任务详情失败：${result.error || '未知错误'}`, 'error');
      return;
    }
    
    const url = result.url;
    const output = result.output_name || 'video.mp4';
    
    if (!url) {
      showToast('无法获取任务 URL', 'error');
      return;
    }
    
    // 使用获取到的 URL 提交下载请求
    const taskData = {
      url: url,
      threads: config.defaultThreads,
      output: output
    };
    
    const downloadResponse = await fetch(`${getApiBaseUrl()}/api/download`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(taskData)
    });
    
    const downloadResult = await downloadResponse.json();
    
    if (downloadResult.success) {
      showToast(`重试任务已提交：${downloadResult.task_id}`, 'success');
      await loadTaskList();
    } else {
      showToast(`重试失败：${downloadResult.error || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// HTML 转义（用于属性值）
function escapeHtmlForAttr(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// 格式化时间
function formatTime(isoString) {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return isoString;
  }
}

// HTML 转义
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 从 URL 提取文件名（统一输出为 .mp4）
function extractFilenameFromUrl(url) {
  try {
    // 处理相对路径和带查询参数的 URL
    const urlObj = new URL(url);
    const pathname = urlObj.pathname;
    
    // 从路径中提取文件名
    const filename = pathname.substring(pathname.lastIndexOf('/') + 1);
    
    // 如果文件名为空或只是斜杠，返回 null
    if (!filename || filename === '') {
      return null;
    }
    
    // 解码 URL 编码的字符
    const decodedFilename = decodeURIComponent(filename);
    
    // 移除查询参数（如果有的话）
    const cleanFilename = decodedFilename.split('?')[0];
    
    // 移除原有扩展名，统一添加 .mp4
    const nameWithoutExt = cleanFilename.includes('.') 
      ? cleanFilename.substring(0, cleanFilename.lastIndexOf('.'))
      : cleanFilename;
    
    return nameWithoutExt + '.mp4';
  } catch (e) {
    // URL 格式不正确，尝试从原始字符串提取
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

// 渲染空状态
function renderEmptyState() {
  elements.taskList.innerHTML = '';
  elements.taskList.style.display = 'none';
  elements.emptyState.style.display = 'flex';
  elements.loadingState.style.display = 'none';
}

// 渲染离线状态
function renderOfflineState() {
  elements.taskList.style.display = 'none';
  elements.emptyState.style.display = 'none';
  elements.loadingState.style.display = 'none';
  // 在任务列表容器中显示离线消息
  elements.taskList.innerHTML = `<div class="empty-state"><p>服务器离线，无法加载任务列表</p></div>`;
  elements.taskList.style.display = 'block';
}

// 渲染错误状态
function renderErrorState(errorMsg) {
  elements.taskList.style.display = 'none';
  elements.emptyState.style.display = 'none';
  elements.loadingState.style.display = 'none';
  // 在任务列表容器中显示错误消息
  elements.taskList.innerHTML = `<div class="empty-state"><p style="color: #dc3545;">加载失败：${escapeHtml(errorMsg)}</p></div>`;
  elements.taskList.style.display = 'block';
}

// 显示加载状态
function showLoading() {
  elements.taskList.style.display = 'none';
  elements.emptyState.style.display = 'none';
  elements.loadingState.style.display = 'flex';
}

// 隐藏加载状态
function hideLoading() {
  elements.loadingState.style.display = 'none';
}

// 删除选中任务
async function deleteSelectedTask() {
  if (!selectedTaskId) {
    showToast('请先选择一个任务', 'error');
    return;
  }

  if (!confirm(`确定要删除任务 ${selectedTaskId} 吗？`)) {
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${selectedTaskId}`, {
      method: 'DELETE'
    });

    const result = await response.json();

    if (result.success) {
      showToast('任务已删除', 'success');
      selectedTaskId = null;
      await loadTaskList();
    } else {
      showToast(`删除失败：${result.error || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// 检查服务器状态
async function checkServerStatus() {
  const statusIndicator = document.querySelector('.status-indicator');
  const statusText = document.querySelector('.status-text');
  const wasOnline = isServerOnline;
  const protocol = config.protocol || 'http';

  try {
    const response = await fetch(`${getApiBaseUrl()}/health`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const result = await response.json();

    if (result && result.status === 'healthy') {
      statusIndicator.className = 'status-indicator online';
      statusText.textContent = `服务器在线 (${protocol}://${config.host}:${config.port})`;
      isServerOnline = true;
      // 从离线恢复在线时，启动自动刷新
      if (!wasOnline) {
        startAutoRefresh();
      }
    } else {
      throw new Error('服务状态异常');
    }
  } catch (error) {
    console.error('检查服务器状态失败:', error);
    statusIndicator.className = 'status-indicator offline';
    statusText.textContent = `服务器离线 (${protocol}://${config.host}:${config.port})`;
    isServerOnline = false;
    // 从在线变为离线时，停止自动刷新
    if (wasOnline) {
      stopAutoRefresh();
    }
  }

  // 更新按钮状态
  updateButtonStates();
}

// 更新服务器状态 UI（不改变在线状态）
function updateServerStatusUI() {
  const statusIndicator = document.querySelector('.status-indicator');
  const statusText = document.querySelector('.status-text');
  const protocol = config.protocol || 'http';

  if (isServerOnline) {
    statusIndicator.className = 'status-indicator online';
    statusText.textContent = `服务器在线 (${protocol}://${config.host}:${config.port})`;
  } else {
    statusIndicator.className = 'status-indicator offline';
    statusText.textContent = `服务器离线 (${protocol}://${config.host}:${config.port})`;
  }
}

// 更新按钮状态
function updateButtonStates() {
  if (isServerOnline) {
    elements.btnAddTask.classList.remove('disabled');
    elements.btnDeleteTask.classList.remove('disabled');
    elements.btnAddTask.disabled = false;
    elements.btnDeleteTask.disabled = false;
  } else {
    elements.btnAddTask.classList.add('disabled');
    elements.btnDeleteTask.classList.add('disabled');
    elements.btnAddTask.disabled = true;
    elements.btnDeleteTask.disabled = true;
  }
}

// 处理刷新按钮点击
async function handleRefresh() {
  // 如果服务器离线，先尝试连接
  if (!isServerOnline) {
    await checkServerStatus();
    // 如果连接成功，继续刷新列表
    if (isServerOnline) {
      await loadTaskList();
    } else {
      showToast('服务器离线，无法刷新', 'error');
    }
  } else {
    // 服务器在线时，先检查状态再刷新
    const wasOnline = isServerOnline;
    await checkServerStatus();
    if (isServerOnline) {
      await loadTaskList();
    } else {
      // 从在线变为离线，已停止自动刷新
      showToast('服务器已离线，已停止自动刷新', 'error');
    }
  }
}

// 显示提示气泡
function showToast(message, type = 'success') {
  const toast = elements.toast;
  toast.textContent = message;
  toast.className = 'toast';
  
  // 添加类型样式
  if (type === 'success') {
    toast.classList.add('success');
  } else if (type === 'error') {
    toast.classList.add('error');
  }

  // 显示气泡
  toast.classList.add('show');

  // 3 秒后自动隐藏
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

// 启动自动刷新（只在服务器在线时启动）
function startAutoRefresh() {
  stopAutoRefresh();  // 先停止之前的定时器
  if (config.autoRefresh > 0 && isServerOnline) {
    autoRefreshTimer = setInterval(() => {
      // 自动刷新时 API 请求失败，调用 checkServerStatus 更新服务器状态
      loadTaskList().catch(() => {
        checkServerStatus();
      });
    }, config.autoRefresh);
  }
}

// 停止自动刷新
function stopAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
}

// 重启自动刷新
function restartAutoRefresh() {
  startAutoRefresh();
}

// ==================== 缓存管理功能 ====================

// 显示缓存管理模态框
async function showCacheModal() {
  if (!isServerOnline) {
    showToast('服务器离线，无法访问缓存', 'error');
    return;
  }
  selectedCacheId = null;
  elements.cacheModal.style.display = 'flex';
  await loadCacheList();
  await loadActiveTaskCacheIds();  // 加载正在执行任务的 cache ID
}

// 隐藏缓存管理模态框
function hideCacheModal() {
  elements.cacheModal.style.display = 'none';
}

// 显示缓存详情模态框
function showCacheDetailModal() {
  elements.cacheDetailModal.style.display = 'flex';
}

// 隐藏缓存详情模态框
function hideCacheDetailModal() {
  elements.cacheDetailModal.style.display = 'none';
}

// 获取正在执行任务的 cache ID 集合（task_id 即 cache_id）
async function loadActiveTaskCacheIds() {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks`);
    const result = await response.json();

    activeTaskCacheIds.clear();
    if (result.success && result.tasks) {
      for (const task of result.tasks) {
        // task_id 即 cache_id（URL 的 MD5 哈希）
        activeTaskCacheIds.add(task.task_id);
      }
    }
  } catch (error) {
    console.error('加载活动任务 cache ID 失败:', error);
  }
}

// 加载缓存列表
async function loadCacheList() {
  if (!isServerOnline) {
    renderCacheOfflineState();
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/cache/list`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();

    if (result.success) {
      currentCaches = result.caches || [];
      renderCacheList(currentCaches);
    } else {
      renderCacheEmptyState();
    }
  } catch (error) {
    console.error('加载缓存列表失败:', error);
    renderCacheErrorState(error.message);
  }
}

// 渲染缓存列表
function renderCacheList(caches) {
  if (caches.length === 0) {
    renderCacheEmptyState();
    return;
  }

  elements.cacheList.style.display = 'block';
  elements.cacheEmptyState.style.display = 'none';
  elements.cacheLoadingState.style.display = 'none';

  elements.cacheList.innerHTML = '';

  caches.forEach(cache => {
    const cacheElement = createCacheElement(cache);
    elements.cacheList.appendChild(cacheElement);
  });
}

// 创建缓存项元素
function createCacheElement(cache) {
  const div = document.createElement('div');
  div.className = 'cache-item';
  div.dataset.cacheId = cache.id;

  const isLocked = activeTaskCacheIds.has(cache.id);
  if (isLocked) {
    div.classList.add('locked');
  }

  if (cache.id === selectedCacheId) {
    div.classList.add('selected');
  }

  const statusClass = cache.is_complete !== false ? 'complete' : 'incomplete';
  const statusText = cache.is_complete !== false ? '已完成' : '下载中';
  const lockedBadge = isLocked ? '<span class="cache-status locked">🔒 锁定</span>' : `<span class="cache-status ${statusClass}">${statusText}</span>`;

  div.innerHTML = `
    <div class="cache-item-header">
      <span class="cache-id">${cache.id}</span>
      ${lockedBadge}
    </div>
    <div class="cache-url">${escapeHtml(cache.url || '未知 URL')}</div>
    <div class="cache-info">
      <span class="cache-size">${(cache.total_size_mb || 0).toFixed(2)} MB</span>
      <span class="cache-count">${cache.segment_count || 0} 分片 | ${cache.m3u8_count || 0} m3u8</span>
    </div>
    <div class="cache-created">创建：${formatTime(cache.created_at)}</div>
  `;

  div.addEventListener('click', () => {
    document.querySelectorAll('.cache-item').forEach(item => {
      item.classList.remove('selected');
    });
    div.classList.add('selected');
    selectedCacheId = cache.id;
    showCacheDetail(cache, isLocked);
  });

  return div;
}

// 显示缓存详情
async function showCacheDetail(cache, isLocked) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/cache/${cache.id}`);
    const result = await response.json();

    if (!result.success) {
      showToast('获取缓存详情失败', 'error');
      return;
    }

    const detail = result.cache;
    const locked = isLocked || activeTaskCacheIds.has(cache.id);
    
    let html = `
      <div class="cache-detail-row">
        <span class="cache-detail-label">缓存 ID</span>
        <span class="cache-detail-value" style="font-family: monospace; font-size: 12px;">${detail.id}</span>
      </div>
      <div class="cache-detail-row">
        <span class="cache-detail-label">原始 URL</span>
        <span class="cache-detail-value url">${escapeHtml(detail.url)}</span>
      </div>
      <div class="cache-detail-row">
        <span class="cache-detail-label">基准 URL</span>
        <span class="cache-detail-value url">${escapeHtml(detail.base_url || 'N/A')}</span>
      </div>
      <div class="cache-detail-row">
        <span class="cache-detail-label">分片数量</span>
        <span class="cache-detail-value">${detail.segment_count || 0}</span>
      </div>
      <div class="cache-detail-row">
        <span class="cache-detail-label">m3u8 文件数</span>
        <span class="cache-detail-value">${detail.m3u8_count || 0}</span>
      </div>
      <div class="cache-detail-row">
        <span class="cache-detail-label">总大小</span>
        <span class="cache-detail-value">${(detail.total_size_mb || 0).toFixed(2)} MB</span>
      </div>
      <div class="cache-detail-row">
        <span class="cache-detail-label">已下载</span>
        <span class="cache-detail-value">${detail.downloaded_count || 0} / ${detail.segment_count || 0}</span>
      </div>
      <div class="cache-detail-row">
        <span class="cache-detail-label">完成状态</span>
        <span class="cache-detail-value">${detail.is_complete !== false ? '✅ 已完成' : '⏳ 下载中'}</span>
      </div>
      <div class="cache-detail-row">
        <span class="cache-detail-label">创建时间</span>
        <span class="cache-detail-value">${formatTime(detail.created_at)}</span>
      </div>
    `;

    if (locked) {
      html += `
        <div class="cache-locked-badge">🔒 正在执行的任务锁定，仅允许查看</div>
      `;
    }

    elements.cacheDetailContent.innerHTML = html;

    // 更新操作按钮状态
    const updateBtn = document.getElementById('btn-update-cache');
    const deleteBtn = document.getElementById('btn-delete-cache');
    
    updateBtn.disabled = locked;
    deleteBtn.disabled = locked;
    
    if (locked) {
      updateBtn.title = '正在执行的任务锁定，无法更新';
      deleteBtn.title = '正在执行的任务锁定，无法删除';
    } else {
      updateBtn.title = '更新缓存元数据';
      deleteBtn.title = '删除此缓存';
    }

    showCacheDetailModal();
  } catch (error) {
    console.error('获取缓存详情失败:', error);
    showToast('获取缓存详情失败', 'error');
  }
}

// 处理清空缓存
async function handleClearCache() {
  if (!confirm('确定要清空所有缓存吗？此操作不可恢复！')) {
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/cache/clear`, {
      method: 'POST'
    });

    const result = await response.json();

    if (result.success) {
      showToast(`已清空 ${result.deleted_count || 0} 个缓存`, 'success');
      await loadCacheList();
      await loadActiveTaskCacheIds();
    } else {
      showToast(`清空失败：${result.error || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// 处理删除缓存
async function handleDeleteCache() {
  if (!selectedCacheId) {
    showToast('请先选择一个缓存', 'error');
    return;
  }

  if (activeTaskCacheIds.has(selectedCacheId)) {
    showToast('无法删除：该缓存正被活动任务使用', 'error');
    return;
  }

  if (!confirm(`确定要删除缓存 ${selectedCacheId} 吗？`)) {
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/cache/${selectedCacheId}`, {
      method: 'DELETE'
    });

    const result = await response.json();

    if (result.success) {
      showToast('缓存已删除', 'success');
      hideCacheDetailModal();
      selectedCacheId = null;
      await loadCacheList();
      await loadActiveTaskCacheIds();
    } else {
      showToast(`删除失败：${result.error || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// 处理更新缓存
async function handleUpdateCache() {
  if (!selectedCacheId) {
    showToast('请先选择一个缓存', 'error');
    return;
  }

  if (activeTaskCacheIds.has(selectedCacheId)) {
    showToast('无法更新：该缓存正被活动任务使用', 'error');
    return;
  }

  // 获取当前缓存的 URL
  const cache = currentCaches.find(c => c.id === selectedCacheId);
  if (!cache || !cache.url) {
    showToast('无法获取缓存 URL', 'error');
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/cache/update`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ url: cache.url })
    });

    const result = await response.json();

    if (result.success) {
      showToast(`缓存已更新：${result.segment_count || 0} 个分片`, 'success');
      hideCacheDetailModal();
      selectedCacheId = null;
      await loadCacheList();
      await loadActiveTaskCacheIds();
    } else {
      showToast(`更新失败：${result.error || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// 渲染缓存空状态
function renderCacheEmptyState() {
  elements.cacheList.style.display = 'none';
  elements.cacheEmptyState.style.display = 'flex';
  elements.cacheLoadingState.style.display = 'none';
}

// 渲染缓存离线状态
function renderCacheOfflineState() {
  elements.cacheList.style.display = 'none';
  elements.cacheEmptyState.style.display = 'none';
  elements.cacheLoadingState.style.display = 'none';
  elements.cacheList.innerHTML = `<div class="empty-state"><p>服务器离线，无法加载缓存列表</p></div>`;
  elements.cacheList.style.display = 'block';
}

// 渲染缓存错误状态
function renderCacheErrorState(errorMsg) {
  elements.cacheList.style.display = 'none';
  elements.cacheEmptyState.style.display = 'none';
  elements.cacheLoadingState.style.display = 'none';
  elements.cacheList.innerHTML = `<div class="empty-state"><p style="color: #dc3545;">加载失败：${escapeHtml(errorMsg)}</p></div>`;
  elements.cacheList.style.display = 'block';
}

// ==================== 任务详情功能 ====================

// 显示任务详情
async function showTaskDetail(taskId) {
  if (!isServerOnline) {
    showToast('服务器离线，无法获取任务详情', 'error');
    return;
  }

  selectedTaskIdForDetail = taskId;

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();

    if (!result.success) {
      showToast(`获取任务详情失败：${result.error || '未知错误'}`, 'error');
      return;
    }

    renderTaskDetail(result);
    elements.taskDetailModal.style.display = 'flex';
  } catch (error) {
    console.error('获取任务详情失败:', error);
    showToast('获取任务详情失败', 'error');
  }
}

// 隐藏任务详情模态框
function hideTaskDetailModal() {
  elements.taskDetailModal.style.display = 'none';
  selectedTaskIdForDetail = null;
}

// 渲染任务详情内容
function renderTaskDetail(taskData) {
  const { task_id, url, output_name, progress } = taskData;

  const status = progress?.status || 'unknown';
  const progressPercent = progress?.progress_percent || 0;
  const segmentsDownloaded = progress?.segments_downloaded || 0;
  const totalSegments = progress?.total_segments || 0;
  const error = progress?.error;
  const result = progress?.result;
  const createdAt = progress?.created_at;
  const startedAt = progress?.started_at;
  const completedAt = progress?.completed_at;

  const statusClassMap = {
    pending: 'status-pending',
    parsing: 'status-parsing',
    downloading: 'status-downloading',
    merging: 'status-merging',
    completed: 'status-completed',
    failed: 'status-failed',
    cancelled: 'status-cancelled'
  };

  const statusTextMap = {
    pending: '等待中',
    parsing: '解析中',
    downloading: '下载中',
    merging: '合并中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  };

  const statusClass = statusClassMap[status] || 'status-unknown';
  const statusText = statusTextMap[status] || status;

  let html = `
    <div class="task-detail-section">
      <h4 class="task-detail-section-title">基本信息</h4>
      <div class="task-detail-row">
        <span class="task-detail-label">任务 ID</span>
        <span class="task-detail-value mono">${escapeHtml(task_id)}</span>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">状态</span>
        <span class="task-detail-value status-badge ${statusClass}">${statusText}</span>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">输出文件名</span>
        <span class="task-detail-value">${escapeHtml(output_name || 'N/A')}</span>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">m3u8 URL</span>
        <span class="task-detail-value url">${escapeHtml(url)}</span>
      </div>
    </div>

    <div class="task-detail-section">
      <h4 class="task-detail-section-title">下载进度</h4>
      <div class="task-detail-row">
        <span class="task-detail-label">当前步骤</span>
        <span class="task-detail-value">${escapeHtml(progress?.current_step || '-')}</span>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">进度</span>
        <div class="task-detail-progress">
          <div class="progress-bar-container" style="flex: 1; margin-right: 10px;">
            <div class="progress-bar" style="width: ${progressPercent}%"></div>
          </div>
          <span class="task-detail-value">${progressPercent.toFixed(1)}%</span>
        </div>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">分片下载</span>
        <span class="task-detail-value">${segmentsDownloaded} / ${totalSegments}</span>
      </div>
    </div>

    <div class="task-detail-section">
      <h4 class="task-detail-section-title">时间信息</h4>
      <div class="task-detail-row">
        <span class="task-detail-label">创建时间</span>
        <span class="task-detail-value">${formatDateTime(createdAt)}</span>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">开始时间</span>
        <span class="task-detail-value">${formatDateTime(startedAt)}</span>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">完成时间</span>
        <span class="task-detail-value">${formatDateTime(completedAt)}</span>
      </div>
    </div>
  `;

  // 错误信息（如果有）
  if (error) {
    html += `
      <div class="task-detail-section">
        <h4 class="task-detail-section-title text-danger">错误信息</h4>
        <div class="task-detail-row">
          <span class="task-detail-value text-danger">${escapeHtml(error)}</span>
        </div>
      </div>
    `;
  }

  // 最终结果（如果有）
  if (result) {
    html += `
      <div class="task-detail-section">
        <h4 class="task-detail-section-title text-success">下载结果</h4>
        <div class="task-detail-row">
          <span class="task-detail-value text-success">${JSON.stringify(result, null, 2)}</span>
        </div>
      </div>
    `;
  }

  elements.taskDetailContent.innerHTML = html;
}

// 从任务详情中取消任务
async function handleCancelTaskFromDetail() {
  if (!selectedTaskIdForDetail) {
    showToast('没有可取消的任务', 'error');
    return;
  }

  if (!confirm(`确定要取消任务 ${selectedTaskIdForDetail} 吗？`)) {
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${selectedTaskIdForDetail}`, {
      method: 'DELETE'
    });

    const result = await response.json();

    if (result.success) {
      showToast('任务已取消', 'success');
      hideTaskDetailModal();
      await loadTaskList();
    } else {
      showToast(`取消失败：${result.error || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// 格式化日期时间（包含日期）
function formatDateTime(isoString) {
  if (!isoString) return '-';
  try {
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN');
  } catch {
    return isoString;
  }
}
