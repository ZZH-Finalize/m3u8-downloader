/**
 * m3u8 下载器扩展 - Popup 主脚本
 * 依赖：utils.js（需在 HTML 中先加载）
 */

// API 基础配置
const DEFAULT_CONFIG = {
  host: '127.0.0.1',
  port: '6900',
  defaultThreads: 8,
  defaultEncoding: 'copy',
  defaultEncoder: 'software',
  autoRefresh: 2000
};

// 全局状态
let selectedTaskId = null;
let autoRefreshTimer = null;
let config = { ...DEFAULT_CONFIG };
let isServerOnline = false;
let consecutiveOfflineCount = 0;
const MAX_OFFLINE_TOLERANCE = 3;

// 缓存管理状态
let selectedCacheId = null;
let currentCaches = [];
let activeTaskCacheIds = new Set();

// 任务详情状态
let selectedTaskIdForDetail = null;

// DOM 元素
let elements;

function initElements() {
  elements = {
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
    btnRefresh: document.getElementById('btn-refresh'),
    btnSettings: document.getElementById('btn-settings'),
    btnCache: document.getElementById('btn-cache'),
    cacheList: document.getElementById('cache-list'),
    cacheEmptyState: document.getElementById('cache-empty-state'),
    cacheLoadingState: document.getElementById('cache-loading-state'),
    cacheDetailContent: document.getElementById('cache-detail-content'),
    taskDetailContent: document.getElementById('task-detail-content')
  };
}

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  initElements();
  await loadConfig();
  setupEventListeners();
  showLoading();
  await checkServerStatus();
  hideLoading();
  await loadTaskList();
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
  document.getElementById('setting-default-encoding').value = config.defaultEncoding || 'copy';
  document.getElementById('setting-default-encoder').value = config.defaultEncoder || 'software';
  document.getElementById('setting-auto-refresh').value = String(config.autoRefresh);
}

// 获取 API 基础 URL
function getApiBaseUrl() {
  return `${config.protocol || 'http'}://${config.host}:${config.port}`;
}

// 设置事件监听器
function setupEventListeners() {
  // 工具栏按钮
  elements.btnAddTask.addEventListener('click', showAddTaskModal);
  elements.btnSettings.addEventListener('click', showSettingsModal);
  elements.btnRefresh.addEventListener('click', handleRefresh);
  elements.btnCache.addEventListener('click', showCacheModal);

  // 模态框关闭按钮
  ['close-add-modal', 'close-settings-modal', 'close-cache-modal', 
   'close-cache-detail-modal', 'close-task-detail-modal',
   'cancel-add-task', 'cancel-settings', 'close-cache', 
   'close-cache-detail', 'close-task-detail'].forEach(id => {
    document.getElementById(id).addEventListener('click', 
      id.includes('add') ? hideAddTaskModal :
      id.includes('settings') ? hideSettingsModal :
      id.includes('cache-detail') ? hideCacheDetailModal :
      id.includes('task-detail') ? hideTaskDetailModal : hideCacheModal);
  });

  // 任务详情操作按钮
  document.getElementById('btn-cancel-task').addEventListener('click', handleCancelTaskFromDetail);
  document.getElementById('btn-action-task-detail').addEventListener('click', handleActionTaskFromDetail);

  // 缓存管理按钮
  document.getElementById('btn-refresh-cache').addEventListener('click', loadCacheList);
  document.getElementById('btn-clear-cache').addEventListener('click', handleClearCache);
  document.getElementById('btn-delete-cache').addEventListener('click', handleDeleteCache);
  document.getElementById('btn-redownload-cache').addEventListener('click', handleRedownloadCache);

  // 表单提交
  elements.addTaskForm.addEventListener('submit', handleAddTask);
  elements.settingsForm.addEventListener('submit', handleSaveSettings);

  // 点击模态框外部关闭
  [elements.addTaskModal, elements.settingsModal, elements.cacheModal, 
   elements.cacheDetailModal, elements.taskDetailModal].forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        if (modal === elements.addTaskModal) hideAddTaskModal();
        else if (modal === elements.settingsModal) hideSettingsModal();
        else if (modal === elements.cacheModal) hideCacheModal();
        else if (modal === elements.cacheDetailModal) hideCacheDetailModal();
        else hideTaskDetailModal();
      }
    });
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
  document.getElementById('setting-default-encoding').addEventListener('change', (e) => {
    config.defaultEncoding = e.target.value || 'copy';
  });
  document.getElementById('setting-default-encoder').addEventListener('change', (e) => {
    config.defaultEncoder = e.target.value || 'software';
  });
  document.getElementById('setting-auto-refresh').addEventListener('change', (e) => {
    config.autoRefresh = parseInt(e.target.value) || 0;
    restartAutoRefresh();
  });

  // URL 输入框自动解析文件名
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
      handleQuickDownload(message.url, message.output, message.queued || false);
      sendResponse({ success: true });
    } else if (message.action === 'showNotification') {
      showToast(message.message, message.type);
      sendResponse({ success: true });
    }
    return true;
  });
}

// 显示/隐藏模态框
function showAddTaskModal() {
  if (!isServerOnline) {
    showToast('服务器离线，无法添加任务', 'error');
    return;
  }
  document.getElementById('task-url').value = '';
  document.getElementById('task-threads').value = config.defaultThreads;
  document.getElementById('task-output').value = 'video.mp4';
  document.getElementById('task-output-encoding').value = config.defaultEncoding || 'copy';
  document.getElementById('task-keep-cache').checked = false;
  document.getElementById('task-queued').checked = false;
  elements.addTaskModal.style.display = 'flex';
  document.getElementById('task-url').focus();
}

function hideAddTaskModal() {
  elements.addTaskModal.style.display = 'none';
}

function showSettingsModal() {
  applyConfigToUI();
  elements.settingsModal.style.display = 'flex';
}

function hideSettingsModal() {
  elements.settingsModal.style.display = 'none';
}

// 处理添加任务
async function handleAddTask(e) {
  e.preventDefault();

  const taskData = {
    url: document.getElementById('task-url').value.trim(),
    threads: parseInt(document.getElementById('task-threads').value) || config.defaultThreads,
    output_name: document.getElementById('task-output').value.trim() || 'video.mp4',
    encoder: config.defaultEncoder || 'software',
    output_encoding: document.getElementById('task-output-encoding').value,
    keep_cache: document.getElementById('task-keep-cache').checked,
    queued: document.getElementById('task-queued').checked
  };

  if (!taskData.url) {
    showToast('请输入 m3u8 链接', 'error');
    return;
  }

  await submitTask(taskData, true);
}

// 快速下载（右键菜单）
async function handleQuickDownload(url, output, queued = false) {
  if (!url) {
    showToast('无效的链接', 'error');
    return;
  }

  const taskData = {
    url,
    threads: config.defaultThreads || 8,
    output_name: output || 'video.mp4',
    encoder: config.defaultEncoder || 'software',
    output_encoding: config.defaultEncoding || 'copy',
    keep_cache: false,
    queued
  };

  await submitTask(taskData, false);
}

// 提交任务到服务器
async function submitTask(taskData, closeModal) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(taskData)
    });

    const result = await response.json();

    if (response.ok) {
      showToast(`任务已创建：${result.task_id || taskData.output_name}`, 'success');
      if (closeModal) hideAddTaskModal();
      await loadTaskList();
    } else {
      showToast(`创建失败：${result.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// 处理保存设置
async function handleSaveSettings(e) {
  e.preventDefault();

  const parsed = parseServerAddress(document.getElementById('setting-address').value.trim());
  config.protocol = parsed.protocol;
  config.host = parsed.host;
  config.port = parsed.port;
  config.defaultThreads = parseInt(document.getElementById('setting-default-threads').value) || 8;
  config.defaultEncoding = document.getElementById('setting-default-encoding').value || 'copy';
  config.defaultEncoder = document.getElementById('setting-default-encoder').value || 'software';
  config.autoRefresh = parseInt(document.getElementById('setting-auto-refresh').value) || 0;

  await saveConfig();
  hideSettingsModal();
  await checkServerStatus();
  await loadTaskList();
  showToast('设置已保存', 'success');
}

// 加载任务列表
async function loadTaskList() {
  if (!isServerOnline) {
    renderOfflineState();
    return;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks`, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const result = await response.json();
    renderTaskList(result.tasks || []);
  } catch (error) {
    clearTimeout(timeoutId);
    console.error('加载任务列表失败:', error);
    renderEmptyState();
  }
}

// 渲染任务列表
function renderTaskList(tasks) {
  if (tasks.length === 0) {
    elements.taskList.innerHTML = '';
    elements.taskList.style.display = 'none';
    elements.emptyState.style.display = 'flex';
    elements.loadingState.style.display = 'none';
    return;
  }

  elements.taskList.style.display = 'block';
  elements.emptyState.style.display = 'none';
  elements.loadingState.style.display = 'none';

  const existingTaskElements = new Map();
  elements.taskList.querySelectorAll('.task-item').forEach(el => {
    const taskId = el.dataset.taskId;
    if (taskId) existingTaskElements.set(taskId, el);
  });

  const taskIdsInNewList = new Set();

  tasks.forEach((task) => {
    const taskId = task.task_id;
    const existingEl = existingTaskElements.get(taskId);

    if (existingEl) {
      if (shouldUpdateTask(existingEl, task)) updateTaskElement(existingEl, task);
      if (taskId === selectedTaskId) existingEl.classList.add('selected');
      taskIdsInNewList.add(taskId);
    } else {
      elements.taskList.appendChild(createTaskElement(task));
    }
  });

  existingTaskElements.forEach((el, taskId) => {
    if (!taskIdsInNewList.has(taskId)) el.remove();
  });
}

// 判断任务是否需要更新
function shouldUpdateTask(element, task) {
  const segmentsDownloaded = task.segments_downloaded || 0;
  const totalSegments = task.total_segments || 0;
  const progressPercent = totalSegments > 0 ? (segmentsDownloaded / totalSegments) * 100 : 0;
  
  return (
    element.dataset.state !== task.state ||
    element.dataset.progressPercent !== String(progressPercent) ||
    element.dataset.segmentsDownloaded !== String(segmentsDownloaded)
  );
}

// 创建任务元素
function createTaskElement(task) {
  const div = document.createElement('div');
  div.className = 'task-item';
  div.dataset.taskId = task.task_id;

  const segmentsDownloaded = task.segments_downloaded || 0;
  const totalSegments = task.total_segments || 0;
  const progressPercent = calculateProgressPercent(task.state, segmentsDownloaded, totalSegments);
  const state = task.state || 'pending';

  div.dataset.progressPercent = String(progressPercent);
  div.dataset.segmentsDownloaded = String(segmentsDownloaded);
  div.dataset.state = state;

  if (task.task_id === selectedTaskId) div.classList.add('selected');

  const isCompleted = state === 'completed';
  const isPaused = state === 'paused';
  const isFailed = state === 'failed';

  let actionBtnHtml = '';
  if (!isCompleted) {
    const btnConfig = isFailed ? { icon: '🔄', title: '重试任务', action: 'retry' } :
                      isPaused ? { icon: '▶️', title: '恢复任务', action: 'resume' } :
                                 { icon: '⏸️', title: '暂停任务', action: 'pause' };
    actionBtnHtml = `<button class="task-action-btn action-btn" title="${btnConfig.title}" data-action="${btnConfig.action}">${btnConfig.icon}</button>`;
  }

  div.innerHTML = `
    <div class="task-header">
      <div class="task-header-left">
        <span class="task-id">${task.task_id}</span>
        <span class="task-status ${state}">${getTaskStateText(state)}</span>
      </div>
      <div class="task-actions">
        ${actionBtnHtml}
        <button class="task-action-btn delete-btn" title="删除任务" data-action="delete">🗑️</button>
      </div>
    </div>
    <div class="task-output">${escapeHtml(task.output_name || 'video.mp4')}</div>
    ${shouldShowProgress(state) ? `
    <div class="task-progress">
      <div class="progress-bar-container">
        <div class="progress-bar ${isPaused ? 'paused' : ''}" style="width: ${progressPercent}%"></div>
      </div>
      <div class="progress-info">
        <span class="progress-text">${progressPercent.toFixed(1)}%</span>
        <span class="segments-info">${segmentsDownloaded}/${totalSegments}</span>
      </div>
    </div>
    ` : ''}
  `;

  // 绑定事件
  const actionBtn = div.querySelector('.action-btn');
  if (actionBtn) {
    actionBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const action = actionBtn.dataset.action;
      if (action === 'pause') handlePauseTaskById(task.task_id);
      else if (action === 'resume') handleResumeTaskById(task.task_id);
      else if (action === 'retry') handleRetryTaskById(task.task_id);
    });
  }

  div.querySelector('.delete-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    handleDeleteTaskById(task.task_id);
  });

  div.addEventListener('click', () => {
    document.querySelectorAll('.task-item').forEach(item => item.classList.remove('selected'));
    div.classList.add('selected');
    selectedTaskId = task.task_id;
  });

  div.addEventListener('dblclick', () => showTaskDetail(task.task_id));

  return div;
}

// 更新任务元素
function updateTaskElement(element, task) {
  const segmentsDownloaded = task.segments_downloaded || 0;
  const totalSegments = task.total_segments || 0;
  const progressPercent = calculateProgressPercent(task.state, segmentsDownloaded, totalSegments);
  const state = task.state || 'pending';
  const isPaused = state === 'paused';
  const isFailed = state === 'failed';
  const isCompleted = state === 'completed';

  element.dataset.progressPercent = String(progressPercent);
  element.dataset.segmentsDownloaded = String(segmentsDownloaded);
  element.dataset.state = state;

  // 更新状态标签
  const statusSpan = element.querySelector('.task-status');
  if (statusSpan) {
    statusSpan.className = `task-status ${state}`;
    statusSpan.textContent = getTaskStateText(state);
  }

  // 更新操作按钮
  const actionBtnContainer = element.querySelector('.task-actions');
  if (actionBtnContainer) {
    const oldActionBtn = actionBtnContainer.querySelector('.action-btn');
    let newActionBtnHtml = '';
    
    if (!isCompleted) {
      const btnConfig = isFailed ? { icon: '🔄', title: '重试任务', action: 'retry' } :
                        isPaused ? { icon: '▶️', title: '恢复任务', action: 'resume' } :
                                   { icon: '⏸️', title: '暂停任务', action: 'pause' };
      newActionBtnHtml = `<button class="task-action-btn action-btn" title="${btnConfig.title}" data-action="${btnConfig.action}">${btnConfig.icon}</button>`;
    }

    if (oldActionBtn) {
      if (newActionBtnHtml) {
        const needsUpdate = oldActionBtn.dataset.action !== (isFailed ? 'retry' : isPaused ? 'resume' : 'pause');
        if (needsUpdate) oldActionBtn.outerHTML = newActionBtnHtml;
      } else {
        oldActionBtn.remove();
      }
    } else if (newActionBtnHtml) {
      const deleteBtn = actionBtnContainer.querySelector('.delete-btn');
      if (deleteBtn) deleteBtn.insertAdjacentHTML('beforebegin', newActionBtnHtml);
    }

    const newActionBtn = actionBtnContainer.querySelector('.action-btn');
    if (newActionBtn) {
      newActionBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = newActionBtn.dataset.action;
        if (action === 'pause') handlePauseTaskById(task.task_id);
        else if (action === 'resume') handleResumeTaskById(task.task_id);
        else if (action === 'retry') handleRetryTaskById(task.task_id);
      });
    }
  }

  // 更新进度条
  const showProgress = shouldShowProgress(state);
  const taskProgress = element.querySelector('.task-progress');

  if (showProgress) {
    if (!taskProgress) {
      element.querySelector('.task-output').insertAdjacentHTML('afterend', `
        <div class="task-progress">
          <div class="progress-bar-container">
            <div class="progress-bar ${isPaused ? 'paused' : ''}" style="width: ${progressPercent}%"></div>
          </div>
          <div class="progress-info">
            <span class="progress-text">${progressPercent.toFixed(1)}%</span>
            <span class="segments-info">${segmentsDownloaded}/${totalSegments}</span>
          </div>
        </div>
      `);
    } else {
      const progressBar = element.querySelector('.progress-bar');
      if (progressBar) {
        progressBar.className = `progress-bar ${isPaused ? 'paused' : ''}`;
        progressBar.style.width = `${progressPercent}%`;
      }
      const progressText = element.querySelector('.progress-text');
      if (progressText) progressText.textContent = `${progressPercent.toFixed(1)}%`;
      const segmentsInfo = element.querySelector('.segments-info');
      if (segmentsInfo) segmentsInfo.textContent = `${segmentsDownloaded}/${totalSegments}`;
    }
  } else if (taskProgress) {
    taskProgress.remove();
  }

  // 更新输出文件名
  const taskOutput = element.querySelector('.task-output');
  if (taskOutput) taskOutput.textContent = escapeHtml(task.output_name || 'video.mp4');
}

// 渲染状态
function renderEmptyState() {
  elements.taskList.innerHTML = '';
  elements.taskList.style.display = 'none';
  elements.emptyState.style.display = 'flex';
  elements.loadingState.style.display = 'none';
}

function renderOfflineState() {
  elements.taskList.style.display = 'none';
  elements.emptyState.style.display = 'none';
  elements.loadingState.style.display = 'none';
  elements.taskList.innerHTML = `<div class="empty-state"><p>服务器离线，无法加载任务列表</p></div>`;
  elements.taskList.style.display = 'block';
}

function showLoading() {
  elements.taskList.style.display = 'none';
  elements.emptyState.style.display = 'none';
  elements.loadingState.style.display = 'flex';
}

function hideLoading() {
  elements.loadingState.style.display = 'none';
}

// 任务操作函数
async function handleDeleteTaskById(taskId) {
  if (!isServerOnline) {
    showToast('服务器离线，无法操作', 'error');
    return;
  }

  if (!confirm(`确定要删除任务 ${taskId} 吗？`)) return;

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}`, { method: 'DELETE' });

    if (response.ok) {
      showToast('任务已删除', 'success');
      if (selectedTaskId === taskId) selectedTaskId = null;
      await loadTaskList();
    } else {
      const result = await response.json();
      showToast(`删除失败：${result.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

async function handlePauseTaskById(taskId) {
  if (!isServerOnline) {
    showToast('服务器离线，无法操作', 'error');
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}/pause`, { method: 'POST' });

    if (response.ok) {
      showToast('任务已暂停', 'success');
      await loadTaskList();
    } else {
      const result = await response.json();
      showToast(`暂停失败：${result.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

async function handleResumeTaskById(taskId) {
  if (!isServerOnline) {
    showToast('服务器离线，无法操作', 'error');
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}/resume`, { method: 'POST' });

    if (response.ok) {
      showToast('任务已恢复', 'success');
      await loadTaskList();
    } else {
      const result = await response.json();
      showToast(`恢复失败：${result.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

async function handleRetryTaskById(taskId) {
  if (!isServerOnline) {
    showToast('服务器离线，无法操作', 'error');
    return;
  }

  if (!confirm(`确定要重试任务 ${taskId} 吗？`)) return;

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    
    const task = await response.json();

    const retryResponse = await fetch(`${getApiBaseUrl()}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: task.url,
        threads: 8,
        output_name: task.output_name,
        keep_cache: true,
        queued: false
      })
    });

    if (retryResponse.ok) {
      showToast('任务已重试', 'success');
      await loadTaskList();
    } else {
      const result = await retryResponse.json();
      showToast(`重试失败：${result.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// 服务器状态检测
async function checkServerStatus(useTolerance = false) {
  const statusIndicator = document.querySelector('.status-indicator');
  const statusText = document.querySelector('.status-text');
  const wasOnline = isServerOnline;
  const protocol = config.protocol || 'http';

  statusIndicator.className = 'status-indicator';
  statusText.textContent = `检查中...`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(`${getApiBaseUrl()}/health`, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const result = await response.json();

    if (result && result.version) {
      statusIndicator.className = 'status-indicator online';
      statusText.textContent = `服务器在线 (${protocol}://${config.host}:${config.port})`;
      isServerOnline = true;
      consecutiveOfflineCount = 0;
      if (!wasOnline) startAutoRefresh();
    } else {
      throw new Error('服务状态异常');
    }
  } catch (error) {
    clearTimeout(timeoutId);
    console.error('检查服务器状态失败:', error);
    consecutiveOfflineCount++;

    const shouldGoOffline = useTolerance ? consecutiveOfflineCount >= MAX_OFFLINE_TOLERANCE : true;

    if (shouldGoOffline) {
      statusIndicator.className = 'status-indicator offline';
      statusText.textContent = `服务器离线 (${protocol}://${config.host}:${config.port})`;
      isServerOnline = false;
      if (wasOnline) stopAutoRefresh();
    }
  }

  updateButtonStates();
}

async function pollServerStatus() {
  const protocol = config.protocol || 'http';
  const statusIndicator = document.querySelector('.status-indicator');
  const statusText = document.querySelector('.status-text');

  try {
    const response = await fetch(`${getApiBaseUrl()}/health`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const result = await response.json();
    if (result && result.version) {
      consecutiveOfflineCount = 0;
    }
  } catch (error) {
    consecutiveOfflineCount++;
    console.log(`轮询检测失败，连续失败次数：${consecutiveOfflineCount}/${MAX_OFFLINE_TOLERANCE}`);

    if (consecutiveOfflineCount >= MAX_OFFLINE_TOLERANCE) {
      statusIndicator.className = 'status-indicator offline';
      statusText.textContent = `服务器离线 (${protocol}://${config.host}:${config.port})`;
      isServerOnline = false;
      stopAutoRefresh();
      updateButtonStates();
    }
  }
}

function updateButtonStates() {
  [elements.btnAddTask, elements.btnCache].forEach(btn => {
    if (isServerOnline) {
      btn.classList.remove('disabled');
      btn.disabled = false;
    } else {
      btn.classList.add('disabled');
      btn.disabled = true;
    }
  });
}

async function handleRefresh() {
  if (!isServerOnline) {
    await checkServerStatus();
    if (isServerOnline) {
      await loadTaskList();
    } else {
      showToast('服务器离线，无法刷新', 'error');
    }
    return;
  }
  await loadTaskList();
}

// 提示气泡
function showToast(message, type = 'success') {
  const toast = elements.toast;
  toast.textContent = message;
  toast.className = 'toast';
  if (type === 'success') toast.classList.add('success');
  else if (type === 'error') toast.classList.add('error');
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}

// 自动刷新
function startAutoRefresh() {
  stopAutoRefresh();
  if (config.autoRefresh > 0 && isServerOnline) {
    autoRefreshTimer = setInterval(() => {
      loadTaskList().catch(() => pollServerStatus());
    }, config.autoRefresh);
  }
}

function stopAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
}

function restartAutoRefresh() {
  startAutoRefresh();
}

// ==================== 缓存管理 ====================

async function showCacheModal() {
  if (!isServerOnline) {
    showToast('服务器离线，无法访问缓存', 'error');
    return;
  }
  selectedCacheId = null;
  elements.cacheModal.style.display = 'flex';
  await loadActiveTaskCacheIds();
  await loadCacheList();
}

function hideCacheModal() {
  elements.cacheModal.style.display = 'none';
}

function showCacheDetailModal() {
  elements.cacheDetailModal.style.display = 'flex';
}

function hideCacheDetailModal() {
  elements.cacheDetailModal.style.display = 'none';
}

async function loadActiveTaskCacheIds() {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks`);
    if (!response.ok) return;

    const result = await response.json();
    activeTaskCacheIds.clear();
    if (result.tasks) {
      for (const task of result.tasks) {
        activeTaskCacheIds.add(task.task_id);
      }
    }
  } catch (error) {
    console.error('加载活动任务 cache ID 失败:', error);
  }
}

async function loadCacheList() {
  if (!isServerOnline) {
    renderCacheOfflineState();
    return;
  }

  try {
    elements.cacheList.style.display = 'none';
    elements.cacheEmptyState.style.display = 'none';
    elements.cacheLoadingState.style.display = 'flex';

    const response = await fetch(`${getApiBaseUrl()}/api/cache/list`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const result = await response.json();
    currentCaches = result.caches || [];
    renderCacheList(currentCaches);
  } catch (error) {
    console.error('加载缓存列表失败:', error);
    renderCacheErrorState(error.message);
  }
}

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
    elements.cacheList.appendChild(createCacheElement(cache));
  });
}

function createCacheElement(cache) {
  const div = document.createElement('div');
  div.className = 'cache-item';
  div.dataset.cacheId = cache.id;

  const isLocked = activeTaskCacheIds.has(cache.id);
  if (isLocked) div.classList.add('locked');
  if (cache.id === selectedCacheId) div.classList.add('selected');

  // 缓存 API 已移除 state 字段，只显示锁定状态
  const lockedBadge = isLocked ? '<span class="cache-status locked">🔒 锁定</span>' : '';

  div.innerHTML = `
    <div class="cache-item-header">
      <span class="cache-id">${cache.id}</span>
      ${lockedBadge}
    </div>
    <div class="cache-url">${escapeHtml(cache.url || '未知 URL')}</div>
    <div class="cache-info">
      <span class="cache-count">${cache.segments_num || 0} 分片</span>
    </div>
    <div class="cache-created">创建：${formatTime(cache.created_at)}</div>
  `;

  div.addEventListener('click', () => {
    document.querySelectorAll('.cache-item').forEach(item => item.classList.remove('selected'));
    div.classList.add('selected');
    selectedCacheId = cache.id;
    showCacheDetail(cache, isLocked);
  });

  return div;
}

async function showCacheDetail(cache, isLocked) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/cache/${cache.id}`);
    const result = await response.json();

    if (!response.ok) {
      showToast('获取缓存详情失败', 'error');
      return;
    }

    const detail = result;
    const locked = isLocked || activeTaskCacheIds.has(cache.id);
    const downloadedCount = parseDownloadedMask(detail.downloaded_mask);

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
        <span class="cache-detail-value">${detail.segments_num || 0}</span>
      </div>
      <div class="cache-detail-row">
        <span class="cache-detail-label">已下载</span>
        <span class="cache-detail-value">${downloadedCount} / ${detail.segments_num || 0}</span>
      </div>
      <div class="cache-detail-row">
        <span class="cache-detail-label">创建时间</span>
        <span class="cache-detail-value">${formatTime(detail.created_at)}</span>
      </div>
    `;

    if (locked) {
      html += `<div class="cache-locked-badge">🔒 正在执行的任务锁定，仅允许查看</div>`;
    }

    elements.cacheDetailContent.innerHTML = html;

    const deleteBtn = document.getElementById('btn-delete-cache');
    const redownloadBtn = document.getElementById('btn-redownload-cache');

    deleteBtn.disabled = locked;
    redownloadBtn.disabled = locked;
    deleteBtn.title = locked ? '正在执行的任务锁定，无法删除' : '删除此缓存';
    redownloadBtn.title = locked ? '正在执行的任务锁定，无法重新下载' : '使用此缓存的信息重新创建下载任务';

    showCacheDetailModal();
  } catch (error) {
    console.error('获取缓存详情失败:', error);
    showToast('获取缓存详情失败', 'error');
  }
}

async function handleClearCache() {
  if (!confirm('确定要清空所有缓存吗？此操作不可恢复！')) return;

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/cache/clear`, { method: 'POST' });

    if (response.ok) {
      showToast('已清空所有缓存', 'success');
      await loadCacheList();
      await loadActiveTaskCacheIds();
    } else {
      const result = await response.json();
      showToast(`清空失败：${result.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

async function handleDeleteCache() {
  if (!selectedCacheId) {
    showToast('请先选择一个缓存', 'error');
    return;
  }

  if (activeTaskCacheIds.has(selectedCacheId)) {
    showToast('无法删除：该缓存正被活动任务使用', 'error');
    return;
  }

  if (!confirm(`确定要删除缓存 ${selectedCacheId} 吗？`)) return;

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/cache/${selectedCacheId}`, { method: 'DELETE' });

    if (response.ok) {
      showToast('缓存已删除', 'success');
      hideCacheDetailModal();
      selectedCacheId = null;
      await loadCacheList();
      await loadActiveTaskCacheIds();
    } else {
      const result = await response.json();
      showToast(`删除失败：${result.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

async function handleRedownloadCache() {
  if (!selectedCacheId) {
    showToast('请先选择一个缓存', 'error');
    return;
  }

  if (!confirm(`确定要使用缓存 ${selectedCacheId} 的信息重新创建下载任务吗？`)) return;

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/cache/${selectedCacheId}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    
    const cache = await response.json();

    const downloadResponse = await fetch(`${getApiBaseUrl()}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: cache.url,
        threads: config.defaultThreads || 8,
        output_name: extractFilenameFromUrl(cache.url) || 'video.mp4',
        keep_cache: false,
        queued: false
      })
    });

    if (downloadResponse.ok) {
      const result = await downloadResponse.json();
      showToast(`任务已创建：${result.task_id}`, 'success');
      hideCacheDetailModal();
      selectedCacheId = null;
      await loadTaskList();
    } else {
      const result = await downloadResponse.json();
      showToast(`创建失败：${result.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

function renderCacheEmptyState() {
  elements.cacheList.style.display = 'none';
  elements.cacheEmptyState.style.display = 'flex';
  elements.cacheLoadingState.style.display = 'none';
}

function renderCacheOfflineState() {
  elements.cacheList.style.display = 'none';
  elements.cacheEmptyState.style.display = 'none';
  elements.cacheLoadingState.style.display = 'none';
  elements.cacheList.innerHTML = `<div class="empty-state"><p>服务器离线，无法加载缓存列表</p></div>`;
  elements.cacheList.style.display = 'block';
}

function renderCacheErrorState(errorMsg) {
  elements.cacheList.style.display = 'none';
  elements.cacheEmptyState.style.display = 'none';
  elements.cacheLoadingState.style.display = 'none';
  elements.cacheList.innerHTML = `<div class="empty-state"><p style="color: #dc3545;">加载失败：${escapeHtml(errorMsg)}</p></div>`;
  elements.cacheList.style.display = 'block';
}

// ==================== 任务详情 ====================

async function showTaskDetail(taskId) {
  if (!isServerOnline) {
    showToast('服务器离线，无法获取任务详情', 'error');
    return;
  }

  selectedTaskIdForDetail = taskId;

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const result = await response.json();
    renderTaskDetail(result);
    elements.taskDetailModal.style.display = 'flex';
  } catch (error) {
    console.error('获取任务详情失败:', error);
    showToast('获取任务详情失败', 'error');
  }
}

function hideTaskDetailModal() {
  elements.taskDetailModal.style.display = 'none';
  selectedTaskIdForDetail = null;
}

function renderTaskDetail(taskData) {
  const { task_id, url, output_name, segments_downloaded, total_segments, state } = taskData;

  const progressPercent = calculateProgressPercent(state, segments_downloaded, total_segments);
  const showProgress = shouldShowProgress(state);
  const isPaused = state === 'paused';
  const isFailed = state === 'failed';
  const isCompleted = state === 'completed';

  const actionBtn = document.getElementById('btn-action-task-detail');

  if (isCompleted) {
    actionBtn.style.display = 'none';
  } else {
    actionBtn.style.display = 'inline-block';
    if (isFailed) {
      actionBtn.textContent = '重试任务';
      actionBtn.className = 'btn btn-primary';
      actionBtn.dataset.action = 'retry';
    } else if (isPaused) {
      actionBtn.textContent = '恢复任务';
      actionBtn.className = 'btn btn-success';
      actionBtn.dataset.action = 'resume';
    } else {
      actionBtn.textContent = '暂停任务';
      actionBtn.className = 'btn btn-warning';
      actionBtn.dataset.action = 'pause';
    }
  }

  let html = `
    <div class="task-detail-section">
      <h4 class="task-detail-section-title">基本信息</h4>
      <div class="task-detail-row">
        <span class="task-detail-label">任务 ID</span>
        <span class="task-detail-value mono">${escapeHtml(task_id)}</span>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">状态</span>
        <span class="task-detail-value">
          <span class="task-status ${state || 'pending'}">${getTaskStateText(state || 'pending')}</span>
        </span>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">输出文件名</span>
        <span class="task-detail-value">${escapeHtml(output_name || 'video.mp4')}</span>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">m3u8 URL</span>
        <span class="task-detail-value url">${escapeHtml(url)}</span>
      </div>
    </div>
  `;

  if (showProgress) {
    html += `
    <div class="task-detail-section">
      <h4 class="task-detail-section-title">下载进度</h4>
      <div class="task-detail-row">
        <span class="task-detail-label">进度</span>
        <div class="task-detail-progress">
          <div class="progress-bar-container" style="flex: 1; margin-right: 10px;">
            <div class="progress-bar ${isPaused ? 'paused' : ''}" style="width: ${progressPercent}%"></div>
          </div>
          <span class="task-detail-value">${progressPercent.toFixed(1)}%</span>
        </div>
      </div>
      <div class="task-detail-row">
        <span class="task-detail-label">分片下载</span>
        <span class="task-detail-value">${segments_downloaded || 0} / ${total_segments || 0}</span>
      </div>
    </div>
    `;
  }

  elements.taskDetailContent.innerHTML = html;
}

async function handleCancelTaskFromDetail() {
  if (!selectedTaskIdForDetail) {
    showToast('没有可取消的任务', 'error');
    return;
  }

  if (!confirm(`确定要取消任务 ${selectedTaskIdForDetail} 吗？`)) return;

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${selectedTaskIdForDetail}`, { method: 'DELETE' });

    if (response.ok) {
      showToast('任务已删除', 'success');
      hideTaskDetailModal();
      await loadTaskList();
    } else {
      const result = await response.json();
      showToast(`删除失败：${result.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

async function handleActionTaskFromDetail() {
  if (!isServerOnline) {
    showToast('服务器离线，无法操作', 'error');
    return;
  }
  if (!selectedTaskIdForDetail) {
    showToast('没有可操作的任务', 'error');
    return;
  }

  const actionBtn = document.getElementById('btn-action-task-detail');
  const action = actionBtn.dataset.action;

  if (action === 'pause') {
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/tasks/${selectedTaskIdForDetail}/pause`, { method: 'POST' });

      if (response.ok) {
        showToast('任务已暂停', 'success');
        await showTaskDetail(selectedTaskIdForDetail);
        await loadTaskList();
      } else {
        const result = await response.json();
        showToast(`暂停失败：${result.msg || '未知错误'}`, 'error');
      }
    } catch (error) {
      showToast(`请求失败：${error.message}`, 'error');
    }
  } else if (action === 'resume') {
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/tasks/${selectedTaskIdForDetail}/resume`, { method: 'POST' });

      if (response.ok) {
        showToast('任务已恢复', 'success');
        await showTaskDetail(selectedTaskIdForDetail);
        await loadTaskList();
      } else {
        const result = await response.json();
        showToast(`恢复失败：${result.msg || '未知错误'}`, 'error');
      }
    } catch (error) {
      showToast(`请求失败：${error.message}`, 'error');
    }
  } else if (action === 'retry') {
    await handleRetryTaskById(selectedTaskIdForDetail);
    if (isServerOnline) {
      await showTaskDetail(selectedTaskIdForDetail);
    }
  }
}
