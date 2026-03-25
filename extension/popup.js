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
let consecutiveOfflineCount = 0;  // 连续离线检测次数
const MAX_OFFLINE_TOLERANCE = 3;  // 最大容忍连续离线次数

// 缓存管理状态
let selectedCacheId = null;
let currentCaches = [];
let activeTaskCacheIds = new Set();  // 正在执行任务的 cache ID 集合

// 任务详情状态
let selectedTaskIdForDetail = null;  // 当前打开详情的任务 ID

// DOM 元素（在 DOM 加载后初始化）
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
    output_name: document.getElementById('task-output').value.trim() || 'video.mp4',
    keep_cache: document.getElementById('task-keep-cache').checked,
    queued: document.getElementById('task-queued').checked
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

    if (response.ok) {
      showToast(`任务已提交：${result.task_id}`, 'success');
      hideAddTaskModal();
      await loadTaskList();
    } else {
      showToast(`提交失败：${result.msg || '未知错误'}`, 'error');
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
    output_name: output || 'video.mp4',
    keep_cache: false,
    queued: false  // 右键菜单默认不使用队列
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

    if (response.ok) {
      showToast(`任务已创建：${output}`, 'success');
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

  // 创建带超时的 fetch 请求
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);  // 5 秒超时

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks`, {
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();
    renderTaskList(result.tasks || []);
  } catch (error) {
    clearTimeout(timeoutId);
    console.error('加载任务列表失败:', error);
    // 加载失败不立即进入离线状态，保持当前状态
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
  const existingStatus = element.dataset.state;
  const existingPercent = element.dataset.progressPercent;
  const existingDownloaded = element.dataset.segmentsDownloaded;

  const segmentsDownloaded = task.segments_downloaded || 0;
  const totalSegments = task.total_segments || 0;
  const progressPercent = totalSegments > 0 ? (segmentsDownloaded / totalSegments) * 100 : 0;
  const state = task.state || 'pending';

  return (
    existingStatus !== state ||
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
  const progressPercent = calculateProgressPercent(task.state, segmentsDownloaded, totalSegments);
  const outputName = task.output_name || 'video.mp4';
  const state = task.state || 'pending';

  // 存储当前状态用于比较
  div.dataset.progressPercent = String(progressPercent);
  div.dataset.segmentsDownloaded = String(segmentsDownloaded);
  div.dataset.state = state;

  if (task.task_id === selectedTaskId) {
    div.classList.add('selected');
  }

  // 根据状态决定是否显示进度条
  const showProgress = shouldShowProgress(state);
  const isPaused = state === 'paused';
  const isFailed = state === 'failed';
  const isCompleted = state === 'completed';
  
  // 判断按钮显示逻辑：
  // - failed 状态：显示重试按钮
  // - paused 状态：显示恢复按钮
  // - 其他非完成状态：显示暂停按钮
  // - completed 状态：不显示按钮
  let actionBtnHtml = '';
  if (!isCompleted) {
    let btnIcon, btnTitle, btnAction;
    if (isFailed) {
      btnIcon = '🔄';
      btnTitle = '重试任务';
      btnAction = 'retry';
    } else if (isPaused) {
      btnIcon = '▶️';
      btnTitle = '恢复任务';
      btnAction = 'resume';
    } else {
      btnIcon = '⏸️';
      btnTitle = '暂停任务';
      btnAction = 'pause';
    }
    actionBtnHtml = `<button class="task-action-btn action-btn" title="${btnTitle}" data-action="${btnAction}">${btnIcon}</button>`;
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
    <div class="task-output">${escapeHtml(outputName)}</div>
    ${showProgress ? `
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

  // 绑定操作按钮事件
  const actionBtn = div.querySelector('[data-action="pause"], [data-action="resume"], [data-action="retry"]');
  const deleteBtn = div.querySelector('[data-action="delete"]');

  if (actionBtn) {
    actionBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const taskId = task.task_id;
      const action = actionBtn.dataset.action;
      if (action === 'pause') {
        handlePauseTaskById(taskId);
      } else if (action === 'resume') {
        handleResumeTaskById(taskId);
      } else if (action === 'retry') {
        handleRetryTaskById(taskId);
      }
    });
  }

  deleteBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    handleDeleteTaskById(task.task_id);
  });

  div.addEventListener('click', () => {
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

  return div;
}

// 更新任务元素（只更新变化的部分）
function updateTaskElement(element, task) {
  const segmentsDownloaded = task.segments_downloaded || 0;
  const totalSegments = task.total_segments || 0;
  const progressPercent = calculateProgressPercent(task.state, segmentsDownloaded, totalSegments);
  const outputName = task.output_name || 'video.mp4';
  const state = task.state || 'pending';

  // 更新状态标记
  element.dataset.progressPercent = String(progressPercent);
  element.dataset.segmentsDownloaded = String(segmentsDownloaded);
  element.dataset.state = state;

  // 更新状态标签
  const statusSpan = element.querySelector('.task-status');
  if (statusSpan) {
    statusSpan.className = `task-status ${state}`;
    statusSpan.textContent = getTaskStateText(state);
  }

  // 更新操作按钮状态（暂停/恢复/重试）
  const isPaused = state === 'paused';
  const isFailed = state === 'failed';
  const isCompleted = state === 'completed';
  const actionBtnContainer = element.querySelector('.task-actions');
  
  if (actionBtnContainer) {
    const oldActionBtn = actionBtnContainer.querySelector('[data-action="pause"], [data-action="resume"], [data-action="retry"]');
    
    // 构建新的按钮 HTML
    let newActionBtnHtml = '';
    if (!isCompleted) {
      let btnIcon, btnTitle, btnAction;
      if (isFailed) {
        btnIcon = '🔄';
        btnTitle = '重试任务';
        btnAction = 'retry';
      } else if (isPaused) {
        btnIcon = '▶️';
        btnTitle = '恢复任务';
        btnAction = 'resume';
      } else {
        btnIcon = '⏸️';
        btnTitle = '暂停任务';
        btnAction = 'pause';
      }
      newActionBtnHtml = `<button class="task-action-btn action-btn" title="${btnTitle}" data-action="${btnAction}">${btnIcon}</button>`;
    }
    
    if (oldActionBtn) {
      if (newActionBtnHtml) {
        // 检查按钮是否需要更新
        const needsUpdate = oldActionBtn.dataset.action !== (isFailed ? 'retry' : isPaused ? 'resume' : 'pause');
        if (needsUpdate) {
          oldActionBtn.outerHTML = newActionBtnHtml;
        }
      } else {
        oldActionBtn.remove();
      }
    } else if (newActionBtnHtml) {
      // 按钮不存在但需要添加
      const deleteBtn = actionBtnContainer.querySelector('[data-action="delete"]');
      if (deleteBtn) {
        deleteBtn.insertAdjacentHTML('beforebegin', newActionBtnHtml);
      }
    }
    
    // 重新绑定事件
    const newActionBtn = actionBtnContainer.querySelector('[data-action="pause"], [data-action="resume"], [data-action="retry"]');
    if (newActionBtn) {
      newActionBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const taskId = task.task_id;
        const action = newActionBtn.dataset.action;
        if (action === 'pause') {
          handlePauseTaskById(taskId);
        } else if (action === 'resume') {
          handleResumeTaskById(taskId);
        } else if (action === 'retry') {
          handleRetryTaskById(taskId);
        }
      });
    }
  }

  // 根据状态处理进度条显示
  const showProgress = shouldShowProgress(state);
  // isPaused 已在函数开头声明，这里复用
  const taskProgress = element.querySelector('.task-progress');

  if (showProgress) {
    // 需要显示进度条
    if (!taskProgress) {
      // 当前没有进度条，需要添加
      const taskOutput = element.querySelector('.task-output');
      if (taskOutput) {
        taskOutput.insertAdjacentHTML('afterend', `
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
      }
    } else {
      // 已有进度条，更新状态
      const progressBar = element.querySelector('.progress-bar');
      const progressText = element.querySelector('.progress-text');
      const segmentsInfo = element.querySelector('.segments-info');

      // 更新进度条样式（包括 paused 状态）
      if (progressBar) {
        progressBar.className = `progress-bar ${isPaused ? 'paused' : ''}`;
        progressBar.style.width = `${progressPercent}%`;
      }

      // 更新进度文本
      if (progressText) {
        progressText.textContent = `${progressPercent.toFixed(1)}%`;
      }

      // 更新分片信息
      if (segmentsInfo) {
        segmentsInfo.textContent = `${segmentsDownloaded}/${totalSegments}`;
      }
    }
  } else {
    // 不需要显示进度条，移除
    if (taskProgress) {
      taskProgress.remove();
    }
  }

  // 更新输出文件名
  const taskOutput = element.querySelector('.task-output');
  if (taskOutput) {
    taskOutput.textContent = escapeHtml(outputName);
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

// 获取任务状态文本
function getTaskStateText(state) {
  const stateMap = {
    pending: '等待中',
    parsing: '解析中',
    downloading: '下载中',
    merging: '合并中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败'
  };
  return stateMap[state] || state || '未知';
}

// 计算进度百分比（根据状态返回不同值）
function calculateProgressPercent(state, segmentsDownloaded, totalSegments) {
  // MERGING 和 COMPLETED 状态固定显示 100%
  if (state === 'merging' || state === 'completed') {
    return 100;
  }
  
  // FAILED 状态不显示进度（返回 0）
  if (state === 'failed') {
    return 0;
  }
  
  // 其他状态按实际下载进度计算
  if (totalSegments > 0) {
    return (segmentsDownloaded / totalSegments) * 100;
  }
  return 0;
}

// 判断是否显示进度条
function shouldShowProgress(state) {
  // FAILED 状态不显示进度条
  if (state === 'failed') {
    return false;
  }
  // 其他状态都显示进度条
  return true;
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
  elements.taskList.innerHTML = `<div class="empty-state"><p>服务器离线，无法加载任务列表</p></div>`;
  elements.taskList.style.display = 'block';
}

// 渲染错误状态
function renderErrorState(errorMsg) {
  elements.taskList.style.display = 'none';
  elements.emptyState.style.display = 'none';
  elements.loadingState.style.display = 'none';
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

// 删除指定任务（通过任务 ID）
async function handleDeleteTaskById(taskId) {
  if (!isServerOnline) {
    showToast('服务器离线，无法操作', 'error');
    return;
  }

  if (!confirm(`确定要删除任务 ${taskId} 吗？`)) {
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}`, {
      method: 'DELETE'
    });

    if (response.ok) {
      showToast('任务已删除', 'success');
      if (selectedTaskId === taskId) {
        selectedTaskId = null;
      }
      await loadTaskList();
    } else {
      const result = await response.json();
      showToast(`删除失败：${result.msg || '未知错误'}`, 'error');
    }
  } catch (error) {
    showToast(`请求失败：${error.message}`, 'error');
  }
}

// 暂停指定任务（通过任务 ID）
async function handlePauseTaskById(taskId) {
  if (!isServerOnline) {
    showToast('服务器离线，无法操作', 'error');
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}/pause`, {
      method: 'POST'
    });

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

// 恢复指定任务（通过任务 ID）
async function handleResumeTaskById(taskId) {
  if (!isServerOnline) {
    showToast('服务器离线，无法操作', 'error');
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}/resume`, {
      method: 'POST'
    });

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

// 重试指定任务（通过任务 ID）- 重新提交下载请求
async function handleRetryTaskById(taskId) {
  if (!isServerOnline) {
    showToast('服务器离线，无法操作', 'error');
    return;
  }

  if (!confirm(`确定要重试任务 ${taskId} 吗？`)) {
    return;
  }

  try {
    // 先获取任务详情，获取 URL 和配置
    const response = await fetch(`${getApiBaseUrl()}/api/tasks/${taskId}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const task = await response.json();

    // 重新提交下载请求
    const retryResponse = await fetch(`${getApiBaseUrl()}/api/download`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        url: task.url,
        threads: 8,  // 使用默认线程数
        output_name: task.output_name,
        keep_cache: true,  // 重试时保留缓存
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

// 检查服务器状态（只在打开插件页面和保存设置时调用）
// 此函数可以改变在线/离线状态
// useTolerance: 是否使用三次容忍机制（仅自动轮询时使用）
async function checkServerStatus(useTolerance = false) {
  const statusIndicator = document.querySelector('.status-indicator');
  const statusText = document.querySelector('.status-text');
  const wasOnline = isServerOnline;
  const protocol = config.protocol || 'http';

  // 显示正在检查的状态
  statusIndicator.className = 'status-indicator';
  statusText.textContent = `检查中...`;

  // 创建带超时的 fetch 请求
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);  // 5 秒超时

  try {
    const response = await fetch(`${getApiBaseUrl()}/health`, {
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();

    if (result && result.version) {
      statusIndicator.className = 'status-indicator online';
      statusText.textContent = `服务器在线 (${protocol}://${config.host}:${config.port})`;
      isServerOnline = true;
      consecutiveOfflineCount = 0;  // 重置离线计数
      if (!wasOnline) {
        startAutoRefresh();
      }
    } else {
      throw new Error('服务状态异常');
    }
  } catch (error) {
    clearTimeout(timeoutId);
    console.error('检查服务器状态失败:', error);
    // 增加连续离线计数
    consecutiveOfflineCount++;

    // 只有自动轮询使用三次容忍，其他情况一次失败就进入离线
    const shouldGoOffline = useTolerance ? consecutiveOfflineCount >= MAX_OFFLINE_TOLERANCE : true;

    if (shouldGoOffline) {
      statusIndicator.className = 'status-indicator offline';
      statusText.textContent = `服务器离线 (${protocol}://${config.host}:${config.port})`;
      isServerOnline = false;
      if (wasOnline) {
        stopAutoRefresh();
      }
    } else {
      // 还未达到容忍上限，保持当前状态但显示警告
      console.log(`服务器检测失败，连续失败次数：${consecutiveOfflineCount}/${MAX_OFFLINE_TOLERANCE}`);
    }
  }

  updateButtonStates();
}

// 定时轮询检查服务器状态（不改变在线/离线状态，只用于检测是否恢复在线）
// 当连续失败达到 3 次时，进入离线状态
async function pollServerStatus() {
  const protocol = config.protocol || 'http';
  const statusIndicator = document.querySelector('.status-indicator');
  const statusText = document.querySelector('.status-text');

  try {
    const response = await fetch(`${getApiBaseUrl()}/health`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();

    if (result && result.version) {
      // 服务器恢复在线，重置计数
      consecutiveOfflineCount = 0;
    }
  } catch (error) {
    // 定时轮询失败，增加计数
    consecutiveOfflineCount++;
    console.log(`轮询检测失败，连续失败次数：${consecutiveOfflineCount}/${MAX_OFFLINE_TOLERANCE}`);
    
    // 连续失败达到 3 次，进入离线状态
    if (consecutiveOfflineCount >= MAX_OFFLINE_TOLERANCE) {
      statusIndicator.className = 'status-indicator offline';
      statusText.textContent = `服务器离线 (${protocol}://${config.host}:${config.port})`;
      isServerOnline = false;
      stopAutoRefresh();
      updateButtonStates();
      console.log('连续失败 3 次，进入离线状态');
    }
  }
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
    elements.btnCache.classList.remove('disabled');
    elements.btnAddTask.disabled = false;
    elements.btnCache.disabled = false;
  } else {
    elements.btnAddTask.classList.add('disabled');
    elements.btnCache.classList.add('disabled');
    elements.btnAddTask.disabled = true;
    elements.btnCache.disabled = true;
  }
}

// 处理刷新按钮点击
async function handleRefresh() {
  if (!isServerOnline) {
    // 离线时，刷新按钮可以尝试恢复在线状态
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

// 显示提示气泡
function showToast(message, type = 'success') {
  const toast = elements.toast;
  toast.textContent = message;
  toast.className = 'toast';

  if (type === 'success') {
    toast.classList.add('success');
  } else if (type === 'error') {
    toast.classList.add('error');
  }

  toast.classList.add('show');

  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

// 启动自动刷新（只在服务器在线时启动）
function startAutoRefresh() {
  stopAutoRefresh();
  if (config.autoRefresh > 0 && isServerOnline) {
    autoRefreshTimer = setInterval(() => {
      // 定时轮询只加载任务列表，不检查服务器状态
      // 服务器状态由 checkServerStatus 在特定时机检查
      loadTaskList().catch(() => {
        // 加载失败时不立即改变状态，由轮询计数累积
        pollServerStatus();
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
  await loadActiveTaskCacheIds();  // 先加载活动任务 ID
  await loadCacheList();  // 再加载缓存列表
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
    
    if (!response.ok) {
      console.warn('加载活动任务 cache ID 失败：HTTP', response.status);
      return;
    }
    
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

// 加载缓存列表
async function loadCacheList() {
  if (!isServerOnline) {
    renderCacheOfflineState();
    return;
  }

  try {
    // 先显示加载状态
    elements.cacheList.style.display = 'none';
    elements.cacheEmptyState.style.display = 'none';
    elements.cacheLoadingState.style.display = 'flex';

    const response = await fetch(`${getApiBaseUrl()}/api/cache/list`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();
    console.log('缓存列表 API 响应:', result);
    currentCaches = result.caches || [];
    console.log('解析后的缓存列表:', currentCaches);
    renderCacheList(currentCaches);
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

  const stateText = getStateText(cache.state);
  const lockedBadge = isLocked ? '<span class="cache-status locked">🔒 锁定</span>' : `<span class="cache-status">${stateText}</span>`;

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
    document.querySelectorAll('.cache-item').forEach(item => {
      item.classList.remove('selected');
    });
    div.classList.add('selected');
    selectedCacheId = cache.id;
    showCacheDetail(cache, isLocked);
  });

  return div;
}

// 获取状态文本
function getStateText(state) {
  const stateMap = {
    pending: '等待中',
    parsing: '解析中',
    downloading: '下载中',
    merging: '合并中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败'
  };
  return stateMap[state] || state || '未知';
}

// 显示缓存详情
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

    // 解析 downloaded_mask
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
        <span class="cache-detail-label">状态</span>
        <span class="cache-detail-value">${getStateText(detail.state)}</span>
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
      html += `
        <div class="cache-locked-badge">🔒 正在执行的任务锁定，仅允许查看</div>
      `;
    }

    elements.cacheDetailContent.innerHTML = html;

    // 更新操作按钮状态
    const deleteBtn = document.getElementById('btn-delete-cache');
    const redownloadBtn = document.getElementById('btn-redownload-cache');
    
    deleteBtn.disabled = locked;
    redownloadBtn.disabled = locked;

    if (locked) {
      deleteBtn.title = '正在执行的任务锁定，无法删除';
      redownloadBtn.title = '正在执行的任务锁定，无法重新下载';
    } else {
      deleteBtn.title = '删除此缓存';
      redownloadBtn.title = '使用此缓存的信息重新创建下载任务';
    }

    showCacheDetailModal();
  } catch (error) {
    console.error('获取缓存详情失败:', error);
    showToast('获取缓存详情失败', 'error');
  }
}

// 解析 downloaded_mask（十六进制字符串），计算已下载数量
function parseDownloadedMask(mask) {
  if (!mask) return 0;
  let count = 0;
  for (const char of mask) {
    const value = parseInt(char, 16);
    if (!isNaN(value)) {
      for (let i = 0; i < 4; i++) {
        if (value & (1 << i)) count++;
      }
    }
  }
  return count;
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

// 处理重新下载缓存
async function handleRedownloadCache() {
  if (!selectedCacheId) {
    showToast('请先选择一个缓存', 'error');
    return;
  }

  if (!confirm(`确定要使用缓存 ${selectedCacheId} 的信息重新创建下载任务吗？`)) {
    return;
  }

  try {
    // 先获取缓存详情，获取 URL
    const response = await fetch(`${getApiBaseUrl()}/api/cache/${selectedCacheId}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const cache = await response.json();

    // 使用缓存的 URL 重新提交下载任务
    const downloadResponse = await fetch(`${getApiBaseUrl()}/api/download`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
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
  const { task_id, url, output_name, segments_downloaded, total_segments, state } = taskData;

  const progressPercent = calculateProgressPercent(state, segments_downloaded, total_segments);
  const showProgress = shouldShowProgress(state);
  const isPaused = state === 'paused';
  const isFailed = state === 'failed';
  const isCompleted = state === 'completed';

  // 根据任务状态更新按钮可见性和文本
  const actionBtn = document.getElementById('btn-action-task-detail');
  
  if (isCompleted) {
    // 完成状态：隐藏按钮
    actionBtn.style.display = 'none';
  } else {
    actionBtn.style.display = 'inline-block';
    if (isFailed) {
      // 失败状态：显示重试
      actionBtn.textContent = '重试任务';
      actionBtn.className = 'btn btn-primary';
      actionBtn.dataset.action = 'retry';
    } else if (isPaused) {
      // 暂停状态：显示恢复
      actionBtn.textContent = '恢复任务';
      actionBtn.className = 'btn btn-success';
      actionBtn.dataset.action = 'resume';
    } else {
      // 其他状态：显示暂停
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

  // 根据状态决定是否显示进度部分
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

// 从任务详情中操作任务（暂停/恢复/重试）
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
      const response = await fetch(`${getApiBaseUrl()}/api/tasks/${selectedTaskIdForDetail}/pause`, {
        method: 'POST'
      });

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
      const response = await fetch(`${getApiBaseUrl()}/api/tasks/${selectedTaskIdForDetail}/resume`, {
        method: 'POST'
      });

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
