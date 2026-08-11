# 客户演示包 — 内置 Python 运行时

## 显卡版本（二选一）

| 脚本 | 目标显卡 | Conda 环境 | 输出目录 |
|------|----------|------------|----------|
| `build_demo_package_cu118.bat` | RTX 50 **及以前**（含 3060/40 系） | `rvc312` | `dist/RVC-Client-0.1.0-demo-cu118` |
| `build_demo_package_cu128.bat` | RTX 50 **及以后** | `rvc312_cu128` | `dist/RVC-Client-0.1.0-demo-cu128` |
| `build_demo_package_menu.bat` | 交互选择 1/2 | 同上 | 同上 |

> **不能混用**：cu118 包装了 cu128 的 torch，50 系会报错；反之 30/40 系用 cu128 也可能不兼容。

## 一键打包

```text
build_demo_package.bat          # 弹出菜单选择
build_demo_package_cu118.bat    # 直接打 50 系以前包（你当前 3060 用这个）
build_demo_package_cu128.bat    # 直接打 50 系及以上包
```

## 首次打 cu128 包（50 系客户）

若尚无 `rvc312_cu128` 环境，先执行一次：

```text
setup_conda_cu128.bat
```

会创建环境并安装 `torch==2.7.1+cu128` + `requirments_cu128_py312.txt`（PyTorch 从南京大学镜像下载，约 3.3GB）。

## 打包过程

1. 复制应用 + assets
2. `conda pack` 导出对应 conda 环境（约 10 分钟）
3. 解压到 `python/` → `conda-unpack` → 验证 torch
4. 生成 `GPU_VARIANT.txt` 标明版本
5. **手动压缩**文件夹发给客户

## 客户侧

解压 → 双击 `启动唱歌伴侣客户端.bat`，包内 `python/` 已含对应 CUDA 版 PyTorch。

## 前置条件（打包机）

- Anaconda：`F:\zxh\anaconda3`（其他路径改 `-CondaBase`）
- cu118：`envs/rvc312` 已存在且 `import torch` 为 `2.7.1+cu118`
- cu128：`envs/rvc312_cu128` 需先 `setup_conda_cu128.bat`
- 磁盘剩余 ≥ 20GB
