// API 基础配置
const DEFAULT_CONFIG = {
  host: '127.0.0.1',
  port: '5000',
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

// DOM 元素
const elements = {
  taskList: document.getElementById('task-list'),
  emptyState: document.getElementById('empty-state'),
  loadingState: document.getElementById('loading-state'),
  addTaskModal: document.getElementById('add-task-modal'),
  settingsModal: document.getElementById('settings-modal'),
  cacheModal: document.getElementById('cache-modal'),
  cacheDetailModal: document.getElementById('cache-detail-modal'),
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
  cacheDetailContent: document.getElementById('cache-detail-content')
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
  document.getElementById('setting-host').value = config.host;
  document.getElementById('setting-port').value = config.port;
  document.getElementById('setting-default-threads').value = config.defaultThreads;
  document.getElementById('setting-auto-refresh').value = String(config.autoRefresh);
}

// 获取 API 基础 URL
function getApiBaseUrl() {
  return `http://${config.host}:${config.port}`;
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

  // 设置页面输入变化
  document.getElementById('setting-host').addEventListener('change', (e) => {
    config.host = e.target.value.trim();
  });
  document.getElementById('setting-port').addEventListener('change', (e) => {
    config.port = e.target.value.trim();
  });
  document.getElementById('setting-default-threads').addEventListener('change', (e) => {
    config.defaultThreads = parseInt(e.target.value) || 8;
  });
  document.getElementById('setting-auto-refresh').addEventListener('change', (e) => {
    config.autoRefresh = parseInt(e.target.value) || 0;
    restartAutoRefresh();
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
  await checkServerStatus();
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

// 处理保存设置
async function handleSaveSettings(e) {
  e.preventDefault();

  config.host = document.getElementById('setting-host').value.trim() || '127.0.0.1';
  config.port = document.getElementById('setting-port').value.trim() || '5000';
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
    // 请求失败意味着服务器离线，停止自动刷新
    isServerOnline = false;
    updateButtonStates();
    updateServerStatusUI();
    stopAutoRefresh();
    renderOfflineState();
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
  const progress = task.progress || {};
  const existingStatus = element.dataset.status;
  const existingPercent = element.dataset.progressPercent;
  const existingDownloaded = element.dataset.segmentsDownloaded;

  return (
    existingStatus !== (progress.status || '') ||
    existingPercent !== String(progress.progress_percent || 0) ||
    existingDownloaded !== String(progress.segments_downloaded || 0)
  );
}

// 创建任务元素
function createTaskElement(task) {
  const div = document.createElement('div');
  div.className = 'task-item';
  div.dataset.taskId = task.task_id;
  
  const progress = task.progress || {};
  const statusClass = progress.status || 'pending';
  const progressPercent = progress.progress_percent || 0;
  const currentStep = progress.current_step || '等待中';
  const segmentsDownloaded = progress.segments_downloaded || 0;
  const totalSegments = progress.total_segments || 0;
  const createdAt = progress.created_at ? formatTime(progress.created_at) : '';
  const completedAt = progress.completed_at ? formatTime(progress.completed_at) : '';
  const error = progress.error || '';

  // 存储当前状态用于比较
  div.dataset.status = statusClass;
  div.dataset.progressPercent = String(progressPercent);
  div.dataset.segmentsDownloaded = String(segmentsDownloaded);

  if (task.task_id === selectedTaskId) {
    div.classList.add('selected');
  }

  // 失败任务添加重试按钮
  const retryButton = statusClass === 'failed' ? `
    <button class="retry-btn" title="重试下载" onclick="retryTask('${task.task_id}', '${escapeHtmlForAttr(task.url)}')">
      ↻ 重试
    </button>
  ` : '';

  div.innerHTML = `
    <div class="task-header">
      <span class="task-id">${task.task_id}</span>
      <span class="task-status ${statusClass}">${getStatusText(statusClass)}</span>
    </div>
    <div class="task-url">${escapeHtml(task.url || '未知 URL')}</div>
    <div class="task-progress">
      <div class="progress-bar-container">
        <div class="progress-bar" style="width: ${progressPercent}%"></div>
      </div>
      <div class="progress-info">
        <span class="progress-text">${progressPercent.toFixed(1)}%</span>
        <span class="segments-info">${segmentsDownloaded}/${totalSegments}</span>
      </div>
      <div class="task-step">${escapeHtml(currentStep)}</div>
      ${error ? `<div class="task-error" title="${escapeHtmlForAttr(error)}">错误：${escapeHtml(error)}</div>` : ''}
      ${createdAt ? `<div class="task-time">创建：${createdAt}${completedAt ? ` | 完成：${completedAt}` : ''}</div>` : ''}
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
  const progress = task.progress || {};
  const statusClass = progress.status || 'pending';
  const progressPercent = progress.progress_percent || 0;
  const currentStep = progress.current_step || '等待中';
  const segmentsDownloaded = progress.segments_downloaded || 0;
  const totalSegments = progress.total_segments || 0;
  const error = progress.error || '';

  // 更新状态标记
  element.dataset.status = statusClass;
  element.dataset.progressPercent = String(progressPercent);
  element.dataset.segmentsDownloaded = String(segmentsDownloaded);

  // 更新状态标签
  const statusEl = element.querySelector('.task-status');
  if (statusEl) {
    statusEl.className = `task-status ${statusClass}`;
    statusEl.textContent = getStatusText(statusClass);
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
    taskStep.textContent = escapeHtml(currentStep);
  }

  // 更新或添加错误信息
  let errorEl = element.querySelector('.task-error');
  if (error) {
    if (!errorEl) {
      const progressContainer = element.querySelector('.task-progress');
      if (progressContainer) {
        errorEl = document.createElement('div');
        errorEl.className = 'task-error';
        const taskStepEl = progressContainer.querySelector('.task-step');
        if (taskStepEl) {
          taskStepEl.after(errorEl);
        }
      }
    }
    if (errorEl) {
      errorEl.title = escapeHtmlForAttr(error);
      errorEl.textContent = `错误：${escapeHtml(error)}`;
    }
  } else if (errorEl) {
    errorEl.remove();
  }

  // 更新或添加重试按钮
  let retryBtn = element.querySelector('.retry-btn');
  if (statusClass === 'failed') {
    if (!retryBtn) {
      const progressContainer = element.querySelector('.task-progress');
      if (progressContainer) {
        retryBtn = document.createElement('button');
        retryBtn.className = 'retry-btn';
        retryBtn.title = '重试下载';
        retryBtn.innerHTML = `↻ 重试`;
        retryBtn.onclick = () => retryTask(task.task_id, task.url);
        progressContainer.appendChild(retryBtn);
      }
    }
  } else if (retryBtn) {
    retryBtn.remove();
  }
}

// 重试任务
async function retryTask(taskId, url) {
  if (!confirm(`确定要重试任务 ${taskId} 吗？`)) {
    return;
  }

  const taskData = {
    url: url,
    threads: config.defaultThreads,
    output: 'video.mp4'
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
      showToast(`重试任务已提交：${result.task_id}`, 'success');
      await loadTaskList();
    } else {
      showToast(`重试失败：${result.error || '未知错误'}`, 'error');
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

  try {
    const response = await fetch(`${getApiBaseUrl()}/health`);
    const result = await response.json();

    if (result.status === 'healthy') {
      statusIndicator.className = 'status-indicator online';
      statusText.textContent = `服务器在线 (${config.host}:${config.port})`;
      isServerOnline = true;
      // 从离线恢复在线时，启动自动刷新
      if (!wasOnline) {
        startAutoRefresh();
      }
    } else {
      throw new Error('服务状态异常');
    }
  } catch (error) {
    statusIndicator.className = 'status-indicator offline';
    statusText.textContent = `服务器离线 (${config.host}:${config.port})`;
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
  
  if (isServerOnline) {
    statusIndicator.className = 'status-indicator online';
    statusText.textContent = `服务器在线 (${config.host}:${config.port})`;
  } else {
    statusIndicator.className = 'status-indicator offline';
    statusText.textContent = `服务器离线 (${config.host}:${config.port})`;
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
      // 自动刷新时如果检测到离线，停止定时器
      loadTaskList().then(() => {
        if (!isServerOnline && autoRefreshTimer) {
          stopAutoRefresh();
        }
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

// 获取正在执行任务的 cache ID 集合（根据 URL 生成 MD5）
async function loadActiveTaskCacheIds() {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/task/list`);
    const result = await response.json();
    
    activeTaskCacheIds.clear();
    if (result.success && result.tasks) {
      for (const task of result.tasks) {
        const cacheId = md5(task.url || '').substring(0, 16);
        activeTaskCacheIds.add(cacheId);
      }
    }
  } catch (error) {
    console.error('加载活动任务 cache ID 失败:', error);
  }
}

// 简单的 MD5 哈希函数
function md5(string) {
  function RotateLeft(lValue, iShiftBits) {
    return (lValue << iShiftBits) | (lValue >>> (32 - iShiftBits));
  }

  function AddUnsigned(lX, lY) {
    var lX4, lY4, lX8, lY8, lResult;
    lX8 = (lX & 0x80000000);
    lY8 = (lY & 0x80000000);
    lX4 = (lX & 0x40000000);
    lY4 = (lY & 0x40000000);
    lResult = (lX & 0x3FFFFFFF) + (lY & 0x3FFFFFFF);
    if (lX8 & lY8) {
      return (lResult ^ 0x80000000 ^ lX4 ^ lY4);
    }
    if (lX8 | lY8) {
      if (lResult & 0x40000000) {
        return (lResult ^ 0xC0000000 ^ lX4 ^ lY4);
      } else {
        return (lResult ^ 0x40000000 ^ lX4 ^ lY4);
      }
    } else {
      return lResult;
    }
  }

  function F(x, y, z) { return (x & y) | ((~x) & z); }
  function G(x, y, z) { return (x & z) | (y & (~z)); }
  function H(x, y, z) { return (x ^ y ^ z); }
  function I(x, y, z) { return (y ^ (x | (~z))); }

  function FF(a, b, c, d, x, s, ac) {
    a = AddUnsigned(a, AddUnsigned(AddUnsigned(F(b, c, d), x), ac));
    return AddUnsigned(RotateLeft(a, s), b);
  }

  function GG(a, b, c, d, x, s, ac) {
    a = AddUnsigned(a, AddUnsigned(AddUnsigned(G(b, c, d), x), ac));
    return AddUnsigned(RotateLeft(a, s), b);
  }

  function HH(a, b, c, d, x, s, ac) {
    a = AddUnsigned(a, AddUnsigned(AddUnsigned(H(b, c, d), x), ac));
    return AddUnsigned(RotateLeft(a, s), b);
  }

  function II(a, b, c, d, x, s, ac) {
    a = AddUnsigned(a, AddUnsigned(AddUnsigned(I(b, c, d), x), ac));
    return AddUnsigned(RotateLeft(a, s), b);
  }

  function ConvertToWordArray(string) {
    var lWordCount;
    var lMessageLength = string.length;
    var lNumberOfWords_temp1 = lMessageLength + 8;
    var lNumberOfWords_temp2 = (lNumberOfWords_temp1 - (lNumberOfWords_temp1 % 64)) / 64;
    var lNumberOfWords = (lNumberOfWords_temp2 + 1) * 16;
    var lWordArray = Array(lNumberOfWords - 1);
    var lBytePosition = 0;
    var lByteCount = 0;
    while (lByteCount < lMessageLength) {
      lWordCount = (lByteCount - (lByteCount % 4)) / 4;
      lBytePosition = (lByteCount % 4) * 8;
      lWordArray[lWordCount] = (lWordArray[lWordCount] | (string.charCodeAt(lByteCount) << lBytePosition));
      lByteCount++;
    }
    lWordCount = (lByteCount - (lByteCount % 4)) / 4;
    lBytePosition = (lByteCount % 4) * 8;
    lWordArray[lWordCount] = lWordArray[lWordCount] | (0x80 << lBytePosition);
    lWordArray[lNumberOfWords - 2] = lMessageLength << 3;
    lWordArray[lNumberOfWords - 1] = lMessageLength >>> 29;
    return lWordArray;
  }

  function WordToHex(lValue) {
    var WordToHexValue = "", WordToHexValue_temp = "", lByte, lCount;
    for (lCount = 0; lCount <= 3; lCount++) {
      lByte = (lValue >>> (lCount * 8)) & 255;
      WordToHexValue_temp = "0" + lByte.toString(16);
      WordToHexValue = WordToHexValue + WordToHexValue_temp.substr(WordToHexValue_temp.length - 2, 2);
    }
    return WordToHexValue;
  }

  var x = Array();
  var k, AA, BB, CC, DD, a, b, c, d;
  var S11 = 7, S12 = 12, S13 = 17, S14 = 22;
  var S21 = 5, S22 = 9, S23 = 14, S24 = 20;
  var S31 = 4, S32 = 11, S33 = 16, S34 = 23;
  var S41 = 6, S42 = 10, S43 = 15, S44 = 21;

  x = ConvertToWordArray(string);

  a = 0x67452301; b = 0xEFCDAB89; c = 0x98BADCFE; d = 0x10325476;

  for (k = 0; k < x.length; k += 16) {
    AA = a; BB = b; CC = c; DD = d;
    a = FF(a, b, c, d, x[k + 0], S11, 0xD76AA478);
    d = FF(d, a, b, c, x[k + 1], S12, 0xE8C7B756);
    c = FF(c, d, a, b, x[k + 2], S13, 0x242070DB);
    b = FF(b, c, d, a, x[k + 3], S14, 0xC1BDCEEE);
    a = FF(a, b, c, d, x[k + 4], S11, 0xF57C0FAF);
    d = FF(d, a, b, c, x[k + 5], S12, 0x4787C62A);
    c = FF(c, d, a, b, x[k + 6], S13, 0xA8304613);
    b = FF(b, c, d, a, x[k + 7], S14, 0xFD469501);
    a = FF(a, b, c, d, x[k + 8], S11, 0x698098D8);
    d = FF(d, a, b, c, x[k + 9], S12, 0x8B44F7AF);
    c = FF(c, d, a, b, x[k + 10], S13, 0xFFFF5BB1);
    b = FF(b, c, d, a, x[k + 11], S14, 0x895CD7BE);
    a = FF(a, b, c, d, x[k + 12], S11, 0x6B901122);
    d = FF(d, a, b, c, x[k + 13], S12, 0xFD987193);
    c = FF(c, d, a, b, x[k + 14], S13, 0xA679438E);
    b = FF(b, c, d, a, x[k + 15], S14, 0x49B40821);
    a = GG(a, b, c, d, x[k + 1], S21, 0xF61E2562);
    d = GG(d, a, b, c, x[k + 6], S22, 0xC040B340);
    c = GG(c, d, a, b, x[k + 11], S23, 0x265E5A51);
    b = GG(b, c, d, a, x[k + 0], S24, 0xE9B6C7AA);
    a = GG(a, b, c, d, x[k + 5], S21, 0xD62F105D);
    d = GG(d, a, b, c, x[k + 10], S22, 0x2441453);
    c = GG(c, d, a, b, x[k + 15], S23, 0xD8A1E681);
    b = GG(b, c, d, a, x[k + 4], S24, 0xE7D3FBC8);
    a = GG(a, b, c, d, x[k + 9], S21, 0x21E1CDE6);
    d = GG(d, a, b, c, x[k + 14], S22, 0xC33707D6);
    c = GG(c, d, a, b, x[k + 3], S23, 0xF4D50D87);
    b = GG(b, c, d, a, x[k + 8], S24, 0x455A14ED);
    a = GG(a, b, c, d, x[k + 13], S21, 0xA9E3E905);
    d = GG(d, a, b, c, x[k + 2], S22, 0xFCEFA3F8);
    c = GG(c, d, a, b, x[k + 7], S23, 0x676F02D9);
    b = GG(b, c, d, a, x[k + 12], S24, 0x8D2A4C8A);
    a = HH(a, b, c, d, x[k + 5], S31, 0xFFFA3942);
    d = HH(d, a, b, c, x[k + 8], S32, 0x8771F681);
    c = HH(c, d, a, b, x[k + 11], S33, 0x6D9D6122);
    b = HH(b, c, d, a, x[k + 14], S34, 0xFDE5380C);
    a = HH(a, b, c, d, x[k + 1], S31, 0xA4BEEA44);
    d = HH(d, a, b, c, x[k + 4], S32, 0x4BDECFA9);
    c = HH(c, d, a, b, x[k + 7], S33, 0xF6BB4B60);
    b = HH(b, c, d, a, x[k + 10], S34, 0xBEBFBC70);
    a = HH(a, b, c, d, x[k + 13], S31, 0x289B7EC6);
    d = HH(d, a, b, c, x[k + 0], S32, 0xEAA127FA);
    c = HH(c, d, a, b, x[k + 3], S33, 0xD4EF3085);
    b = HH(b, c, d, a, x[k + 6], S34, 0x4881D05);
    a = HH(a, b, c, d, x[k + 9], S31, 0xD9D4D039);
    d = HH(d, a, b, c, x[k + 12], S32, 0xE6DB99E5);
    c = HH(c, d, a, b, x[k + 15], S33, 0x1FA27CF8);
    b = HH(b, c, d, a, x[k + 2], S34, 0xC4AC5665);
    a = II(a, b, c, d, x[k + 0], S41, 0xF4292244);
    d = II(d, a, b, c, x[k + 7], S42, 0x432AFF97);
    c = II(c, d, a, b, x[k + 14], S43, 0xAB9423A7);
    b = II(b, c, d, a, x[k + 5], S44, 0xFC93A039);
    a = II(a, b, c, d, x[k + 12], S41, 0x655B59C3);
    d = II(d, a, b, c, x[k + 3], S42, 0x8F0CCC92);
    c = II(c, d, a, b, x[k + 10], S43, 0xFFEFF47D);
    b = II(b, c, d, a, x[k + 1], S44, 0x85845DD1);
    a = II(a, b, c, d, x[k + 8], S41, 0x6FA87E4F);
    d = II(d, a, b, c, x[k + 15], S42, 0xFE2CE6E0);
    c = II(c, d, a, b, x[k + 6], S43, 0xA3014314);
    b = II(b, c, d, a, x[k + 13], S44, 0x4E0811A1);
    a = II(a, b, c, d, x[k + 4], S41, 0xF7537E82);
    d = II(d, a, b, c, x[k + 11], S42, 0xBD3AF235);
    c = II(c, d, a, b, x[k + 2], S43, 0x2AD7D2BB);
    b = II(b, c, d, a, x[k + 9], S44, 0xEB86D391);
    a = AddUnsigned(a, AA);
    b = AddUnsigned(b, BB);
    c = AddUnsigned(c, CC);
    d = AddUnsigned(d, DD);
  }

  return (WordToHex(a) + WordToHex(b) + WordToHex(c) + WordToHex(d)).toLowerCase();
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
