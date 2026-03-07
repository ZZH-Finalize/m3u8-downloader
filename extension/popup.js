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

// DOM 元素
const elements = {
  taskList: document.getElementById('task-list'),
  emptyState: document.getElementById('empty-state'),
  loadingState: document.getElementById('loading-state'),
  addTaskModal: document.getElementById('add-task-modal'),
  settingsModal: document.getElementById('settings-modal'),
  addTaskForm: document.getElementById('add-task-form'),
  settingsForm: document.getElementById('settings-form'),
  serverStatus: document.getElementById('server-status')
};

// 初始化
document.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();
  setupEventListeners();
  loadTaskList();
  startAutoRefresh();
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
  document.getElementById('btn-add-task').addEventListener('click', showAddTaskModal);
  document.getElementById('btn-delete-task').addEventListener('click', deleteSelectedTask);
  document.getElementById('btn-settings').addEventListener('click', showSettingsModal);
  document.getElementById('btn-refresh').addEventListener('click', loadTaskList);

  // 模态框关闭按钮
  document.getElementById('close-add-modal').addEventListener('click', hideAddTaskModal);
  document.getElementById('close-settings-modal').addEventListener('click', hideSettingsModal);
  document.getElementById('cancel-add-task').addEventListener('click', hideAddTaskModal);
  document.getElementById('cancel-settings').addEventListener('click', hideSettingsModal);

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
  // 重置表单
  document.getElementById('task-url').value = '';
  document.getElementById('task-threads').value = config.defaultThreads;
  document.getElementById('task-output').value = 'video.mp4';
  document.getElementById('task-max-rounds').value = 5;
  document.getElementById('task-keep-cache').value = 'false';
  document.getElementById('task-debug').checked = false;
  
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
    max_rounds: parseInt(document.getElementById('task-max-rounds').value) || 5,
    keep_cache: document.getElementById('task-keep-cache').value === 'true',
    debug: document.getElementById('task-debug').checked
  };

  if (!taskData.url) {
    alert('请输入 m3u8 链接');
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
      alert(`任务已提交：${result.task_id}`);
      hideAddTaskModal();
      await loadTaskList();
    } else {
      alert(`提交失败：${result.error || '未知错误'}`);
    }
  } catch (error) {
    alert(`请求失败：${error.message}`);
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
  await loadTaskList();
  alert('设置已保存');
}

// 加载任务列表
async function loadTaskList() {
  showLoading();
  
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
    renderErrorState(error.message);
  }
}

// 渲染任务列表
function renderTaskList(tasks) {
  elements.taskList.innerHTML = '';
  
  if (tasks.length === 0) {
    renderEmptyState();
    return;
  }
  
  hideLoading();
  
  tasks.forEach(task => {
    const taskElement = createTaskElement(task);
    elements.taskList.appendChild(taskElement);
  });
}

// 创建任务元素
function createTaskElement(task) {
  const div = document.createElement('div');
  div.className = 'task-item';
  if (task.task_id === selectedTaskId) {
    div.classList.add('selected');
  }
  
  const progress = task.progress || {};
  const statusClass = progress.status || 'pending';
  const progressPercent = progress.progress_percent || 0;
  const currentStep = progress.current_step || '等待中';
  const segmentsDownloaded = progress.segments_downloaded || 0;
  const totalSegments = progress.total_segments || 0;
  const createdAt = progress.created_at ? formatTime(progress.created_at) : '';
  const completedAt = progress.completed_at ? formatTime(progress.completed_at) : '';
  
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
      ${createdAt ? `<div class="task-time">创建：${createdAt}${completedAt ? ` | 完成：${completedAt}` : ''}</div>` : ''}
    </div>
  `;
  
  div.addEventListener('click', () => {
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
  hideLoading();
  elements.taskList.innerHTML = '';
  elements.emptyState.style.display = 'flex';
}

// 渲染错误状态
function renderErrorState(errorMsg) {
  hideLoading();
  elements.taskList.innerHTML = `<div class="empty-state"><p style="color: #dc3545;">加载失败：${escapeHtml(errorMsg)}</p></div>`;
  elements.emptyState.style.display = 'none';
}

// 显示加载状态
function showLoading() {
  elements.loadingState.style.display = 'flex';
  elements.emptyState.style.display = 'none';
}

// 隐藏加载状态
function hideLoading() {
  elements.loadingState.style.display = 'none';
  elements.emptyState.style.display = 'none';
}

// 删除选中任务
async function deleteSelectedTask() {
  if (!selectedTaskId) {
    alert('请先选择一个任务');
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
      alert('任务已删除');
      selectedTaskId = null;
      await loadTaskList();
    } else {
      alert(`删除失败：${result.error || '未知错误'}`);
    }
  } catch (error) {
    alert(`请求失败：${error.message}`);
  }
}

// 检查服务器状态
async function checkServerStatus() {
  const statusIndicator = document.querySelector('.status-indicator');
  const statusText = document.querySelector('.status-text');
  
  try {
    const response = await fetch(`${getApiBaseUrl()}/health`);
    const result = await response.json();
    
    if (result.status === 'healthy') {
      statusIndicator.className = 'status-indicator online';
      statusText.textContent = `服务器在线 (${config.host}:${config.port})`;
    } else {
      throw new Error('服务状态异常');
    }
  } catch (error) {
    statusIndicator.className = 'status-indicator offline';
    statusText.textContent = `服务器离线 (${config.host}:${config.port})`;
  }
}

// 启动自动刷新
function startAutoRefresh() {
  if (config.autoRefresh > 0) {
    autoRefreshTimer = setInterval(loadTaskList, config.autoRefresh);
  }
}

// 重启自动刷新
function restartAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
  startAutoRefresh();
}
