const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

async function main() {
  const iconsDir = path.join(__dirname, 'icons');
  const sourcePath = path.join(iconsDir, 'icon.png');

  if (!fs.existsSync(sourcePath)) {
    console.error(`错误：找不到源图标文件 ${sourcePath}`);
    console.log('请将您的大尺寸 icon.png 放在 icons/ 目录下');
    process.exit(1);
  }

  // 获取源图像尺寸
  const metadata = await sharp(sourcePath).metadata();
  console.log(`源图标尺寸：${metadata.width}x${metadata.height}`);

  const sizes = [16, 48, 128];

  console.log('正在生成图标...');

  for (const size of sizes) {
    await sharp(sourcePath)
      .resize(size, size)
      .png()
      .toFile(path.join(iconsDir, `icon${size}.png`));
    console.log(`[OK] 已生成：icon${size}.png (${size}x${size})`);
  }

  console.log('\n图标生成完成！');
}

main().catch(err => {
  console.error('生成失败:', err.message);
  process.exit(1);
});
