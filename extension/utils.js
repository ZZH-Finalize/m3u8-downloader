/**
 * m3u8 下载器扩展 - 共享工具模块
 * 以普通脚本方式加载，所有函数暴露到全局作用域
 */

// 任务状态映射
const TASK_STATE_MAP = {
  pending: '等待中',
  parsing: '解析中',
  downloading: '下载中',
  merging: '合并中',
  paused: '已暂停',
  completed: '已完成',
  failed: '失败'
};

// 缓存 API 已移除 state 字段

/**
 * 从 URL 提取文件名
 * @param {string} url - 视频 URL
 * @returns {string|null} 提取的文件名（.mp4 格式）
 */
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

/**
 * HTML 转义
 * @param {string} text - 需要转义的文本
 * @returns {string} 转义后的文本
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * 格式化时间
 * @param {string} isoString - ISO 格式的时间字符串
 * @returns {string} 格式化后的时间（HH:MM:SS）
 */
function formatTime(isoString) {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    });
  } catch {
    return isoString;
  }
}

/**
 * 获取任务状态文本
 * @param {string} state - 任务状态
 * @returns {string} 状态文本
 */
function getTaskStateText(state) {
  return TASK_STATE_MAP[state] || state || '未知';
}

/**
 * 计算进度百分比
 * @param {string} state - 任务状态
 * @param {number} segmentsDownloaded - 已下载分片数
 * @param {number} totalSegments - 总分片数
 * @returns {number} 进度百分比
 */
function calculateProgressPercent(state, segmentsDownloaded, totalSegments) {
  if (state === 'merging' || state === 'completed') {
    return 100;
  }
  if (state === 'failed') {
    return 0;
  }
  if (totalSegments > 0) {
    return (segmentsDownloaded / totalSegments) * 100;
  }
  return 0;
}

/**
 * 判断是否显示进度条
 * @param {string} state - 任务状态
 * @returns {boolean} 是否显示进度条
 */
function shouldShowProgress(state) {
  return state !== 'failed';
}

/**
 * 解析服务器地址
 * @param {string} address - 服务器地址字符串
 * @returns {{protocol: string, host: string, port: string}} 解析后的地址信息
 */
function parseServerAddress(address) {
  let protocol = 'http';
  let host = '127.0.0.1';
  let port = '6900';

  if (!address || !address.trim()) {
    return { protocol, host, port };
  }

  let trimmed = address.trim();

  const protocolMatch = trimmed.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):\/\//);
  if (protocolMatch) {
    protocol = protocolMatch[1].toLowerCase();
    trimmed = trimmed.substring(protocolMatch[0].length);
  }

  const portMatch = trimmed.match(/:(\d+)$/);
  if (portMatch) {
    port = portMatch[1];
    trimmed = trimmed.substring(0, trimmed.length - portMatch[0].length);
  }

  host = trimmed || '127.0.0.1';

  return { protocol, host, port };
}

/**
 * 解析 downloaded_mask（十六进制字符串），计算已下载数量
 * @param {string} mask - 十六进制掩码字符串
 * @returns {number} 已下载数量
 */
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
