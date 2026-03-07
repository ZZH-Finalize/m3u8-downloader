const fs = require('fs');
const path = require('path');
const archiver = require('archiver');

const DIST_DIR = path.join(__dirname, 'dist');
const BUILD_DIR = path.join(__dirname, '..', 'build');
const ZIP_FILE = path.join(BUILD_DIR, 'm3u8-downloader-extension.zip');

// 需要打包的文件和目录
const FILES_TO_COPY = [
  'manifest.json',
  'popup.html',
  'popup.css',
  'popup.js',
  'icons'
];

// 清理旧的构建文件
function clean() {
  if (fs.existsSync(DIST_DIR)) {
    fs.rmSync(DIST_DIR, { recursive: true, force: true });
    console.log('已清理 dist 目录');
  }
  if (!fs.existsSync(BUILD_DIR)) {
    fs.mkdirSync(BUILD_DIR, { recursive: true });
  }
}

// 复制文件到 dist 目录
function copyFiles() {
  fs.mkdirSync(DIST_DIR, { recursive: true });
  
  for (const item of FILES_TO_COPY) {
    const srcPath = path.join(__dirname, item);
    const destPath = path.join(DIST_DIR, item);
    
    if (fs.existsSync(srcPath)) {
      fs.cpSync(srcPath, destPath, { recursive: true });
      console.log(`已复制：${item}`);
    } else {
      console.warn(`警告：文件不存在 - ${item}`);
    }
  }
}

// 创建 zip 压缩包
function createZip() {
  return new Promise((resolve, reject) => {
    const output = fs.createWriteStream(ZIP_FILE);
    const archive = archiver('zip', { zlib: { level: 9 } });
    
    output.on('close', () => {
      const size = (archive.pointer() / 1024 / 1024).toFixed(2);
      console.log(`打包完成：${ZIP_FILE} (${size} MB)`);
      resolve();
    });
    
    archive.on('error', (err) => {
      reject(err);
    });
    
    archive.pipe(output);
    archive.directory(DIST_DIR, false);
    archive.finalize();
  });
}

// 清理 dist 目录
function cleanup() {
  if (fs.existsSync(DIST_DIR)) {
    fs.rmSync(DIST_DIR, { recursive: true, force: true });
    console.log('已清理临时 dist 目录');
  }
}

async function main() {
  try {
    console.log('开始构建扩展程序...\n');
    
    clean();
    copyFiles();
    await createZip();
    cleanup();
    
    console.log('\n构建成功！');
  } catch (error) {
    console.error('构建失败:', error);
    process.exit(1);
  }
}

main();
