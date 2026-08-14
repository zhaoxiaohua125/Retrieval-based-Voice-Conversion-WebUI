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

1. 复制应用 + assets（可选 `-Pyd`：业务层 `app/`（除 `ui/`）与 `scripts/` 编译为 `.pyd`；**`app/ui/` 保留 `.py`**，避免 PyQt 信号槽崩溃）
2. `conda pack` 导出对应 conda 环境（约 10 分钟）
3. 解压到 `python/` → `conda-unpack` → 验证 torch
4. 生成 `GPU_VARIANT.txt` 标明版本
5. **手动压缩**文件夹发给客户

### app/ + scripts/ 编译为 pyd（可选）

PyQt6 界面层 **`app/ui/` 不编译 pyd**（会信号槽崩溃），脚本自动 **`compileall` 为 `.pyc` 并删除 `.py`**；其余 `app/` 与打包用 `scripts/` 为 `.pyd`。

打包前需：**与目标 conda 环境相同的 Python**、**Cython**、**Windows MSVC 编译工具**。

```powershell
# 菜单 build_demo_package.bat 会询问 Compile app/ to pyd?
# 或手动（app/ + scripts/ → pyd，PyQt binding=True）：
powershell -File scripts\build_client_package.ps1 -CudaVariant cu118 -CondaPack -Pyd

# 仅编译到 dist\pyd_pack_test（调试，约 90s；ui 输出 .pyc）：
F:\zxh\anaconda3\envs\rvc312\python.exe scripts\compile_app_pyd.py --output dist\pyd_pack_test

# ui 保留 .py 不转 pyc（调试 UI）：
F:\zxh\anaconda3\envs\rvc312\python.exe scripts\compile_app_pyd.py --output dist\pyd_pack_test --keep-ui-py
```

`infer/`、`tools/` 仍为 `.py`；入口为 `scripts/_launch_ui.py`（逻辑在 `run_ui_skeleton.pyd`）。

## 客户侧

解压 → 双击 `启动来取文化.bat`，包内 `python/` 已含对应 CUDA 版 PyTorch。

## 前置条件（打包机）

- Anaconda：`F:\zxh\anaconda3`（其他路径改 `-CondaBase`）
- cu118：`envs/rvc312` 已存在且 `import torch` 为 `2.7.1+cu118`
- cu128：`envs/rvc312_cu128` 需先 `setup_conda_cu128.bat`
- 磁盘剩余 ≥ 20GB
- 使用 `-Pyd` 时另需：Cython + Visual Studio Build Tools（C++ 桌面开发）
