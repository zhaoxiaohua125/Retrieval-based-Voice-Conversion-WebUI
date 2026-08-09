<div align="center">

<h1>Retrieval-based-Voice-Conversion-WebUI</h1>
简单易用的 语音音色转换/变声器 框架<br><br>

[![madewithlove](https://img.shields.io/badge/made_with-%E2%9D%A4-red?style=for-the-badge&labelColor=orange
)](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI)

<img src="https://counter.seku.su/cmoe?name=rvc&theme=r34" /><br>

[![Licence](https://img.shields.io/badge/LICENSE-MIT-green.svg?style=for-the-badge)](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/LICENSE)
[![Huggingface](https://img.shields.io/badge/🤗%20-Models-yellow.svg?style=for-the-badge)](https://huggingface.co/lj1995/VoiceConversionWebUI/tree/main/)


[**更新日志**](./docs/cn/Changelog_CN.md) | [**常见问题解答**](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/wiki/%E5%B8%B8%E8%A7%81%E9%97%AE%E9%A2%98%E8%A7%A3%E7%AD%94) | [**AutoDL·5毛钱训练AI歌手**](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/wiki/Autodl%E8%AE%AD%E7%BB%83RVC%C2%B7AI%E6%AD%8C%E6%89%8B%E6%95%99%E7%A8%8B) | [**对照实验记录**](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/wiki/%E5%AF%B9%E7%85%A7%E5%AE%9E%E9%AA%8C%C2%B7%E5%AE%9E%E9%AA%8C%E8%AE%B0%E5%BD%95) | [**在线演示**](https://modelscope.cn/studios/FlowerCry/RVCv2demo)

[**English**](./docs/en/README.en.md) | [**中文简体**](./README.md) | [**日本語**](./docs/jp/README.ja.md) | [**한국어**](./docs/kr/README.ko.md) ([**韓國語**](./docs/kr/README.ko.han.md)) | [**Français**](./docs/fr/README.fr.md) | [**Türkçe**](./docs/tr/README.tr.md) | [**Português**](./docs/pt/README.pt.md)

</div>

> 底模使用接近50小时的开源高质量VCTK训练集训练，无版权方面的顾虑，请大家放心使用

> 请期待RVCv3的底模，参数更大，数据更大，效果更好，基本持平的推理速度，需要训练数据量更少。

<table>
   <tr>
		<td align="center">训练推理界面</td>
		<td align="center">实时变声界面</td>
	</tr>
  <tr>
		<td align="center"><img src="https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/assets/129054828/092e5c12-0d49-4168-a590-0b0ef6a4f630"></td>
    <td align="center"><img src="https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/assets/129054828/730b4114-8805-44a1-ab1a-04668f3c30a6"></td>
	</tr>
	<tr>
		<td align="center">go-webui.bat</td>
		<td align="center">go-realtime_gui.bat</td>
	</tr>
  <tr>
    <td align="center">可以自由选择想要执行的操作。</td>
		<td align="center">我们已经实现端到端170ms延迟。如使用ASIO输入输出设备，已能实现端到端90ms延迟，但非常依赖硬件驱动支持。</td>
	</tr>
</table>

## 简介
本仓库具有以下特点
+ 使用top1检索替换输入源特征为训练集特征来杜绝音色泄漏
+ 即便在相对较差的显卡上也能快速训练
+ 使用少量数据进行训练也能得到较好结果(推荐至少收集10分钟低底噪语音数据)
+ 可以通过模型融合来改变音色(借助ckpt处理选项卡中的ckpt-merge)
+ 简单易用的网页界面
+ 可调用pymss/MSST模型来快速分离人声和伴奏
+ 使用最先进的[人声音高提取算法InterSpeech2023-RMVPE](#参考项目)根绝哑音问题，速度快、资源占用小
+ A卡/I卡使用 CPU 依赖方案；Windows 可使用 DirectML，Linux 使用 CPU

点此查看我们的[演示视频](https://www.bilibili.com/video/BV1pm4y1z7Gm/) !

## 环境配置

本分支面向 **Python 3.12 x64**，请先进入仓库根目录。Ubuntu 推荐使用 Ubuntu 24.04 x86_64。

### Ubuntu 24.04

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev ffmpeg unzip libsndfile1 libportaudio2

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

### Windows

安装 Python 3.12 x64 后创建虚拟环境：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
```

### 按硬件选择依赖

| 硬件 | 安装方式 |
| --- | --- |
| CPU、AMD、Intel | 使用 `requirments_cpu_py312.txt`；Windows 可使用 DirectML，Linux 使用 CPU |
| NVIDIA RTX 50 系 | 先安装 CUDA 12.8 版 Torch，再安装 `requirments_cu128_py312.txt` |
| NVIDIA RTX 50 系以前 | 先安装 CUDA 11.8 版 Torch，再安装 `requirments_cu118_py312.txt` |

#### CPU、AMD、Intel

```bash
python -m pip install -r requirments_cpu_py312.txt
```

#### NVIDIA RTX 50 系：两阶段安装

```bash
python -m pip install torch==2.7.1+cu128 torchaudio==2.7.1+cu128 \
  --index-url https://download.pytorch.org/whl/cu128 \
  --extra-index-url https://pypi.org/simple
python -m pip install -r requirments_cu128_py312.txt
```

#### NVIDIA RTX 50 系以前：两阶段安装

```bash
python -m pip install torch==2.7.1+cu118 torchaudio==2.7.1+cu118 \
  --index-url https://download.pytorch.org/whl/cu118 \
  --extra-index-url https://pypi.org/simple
python -m pip install -r requirments_cu118_py312.txt
```

检查 Torch 与 CUDA 状态：

```bash
python -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.version.cuda); print('cuda available:', torch.cuda.is_available())"
```


### 修改下载源

三个 `requirments_*.txt` 顶部已经包含下载源。中国大陆用户可保留默认镜像；需要使用官方源时，只替换 `--index-url` 和 `--extra-index-url`，保留包版本、CUDA 后缀和两阶段顺序。

| Default mirror | Official source |
| --- | --- |
| `https://mirrors.pku.edu.cn/pypi/simple` | `https://pypi.org/simple` |
| `https://mirrors.nju.edu.cn/pytorch/whl/cpu` | `https://download.pytorch.org/whl/cpu` |
| `https://mirrors.nju.edu.cn/pytorch/whl/cu118` | `https://download.pytorch.org/whl/cu118` |
| `https://mirrors.nju.edu.cn/pytorch/whl/cu128` | `https://download.pytorch.org/whl/cu128` |

## 模型与运行目录

WebUI 会自动创建运行目录。模型请从 [Hugging Face 模型仓库](https://huggingface.co/lj1995/VoiceConversionWebUI/tree/main) 下载，并保持以下路径：

```text
assets/
├── hubert_base/
│   ├── config.json
│   ├── preprocessor_config.json
│   └── pytorch_model.bin
├── rmvpe/rmvpe.pt
├── pretrained/
├── pretrained_v2/
├── pymss_weights/
├── weights/        # user RVC .pth models
└── indices/        # user .index files
logs/
└── mute/           # training silence samples

# Exact paths used by the code
assets/hubert_base/config.json
assets/hubert_base/preprocessor_config.json
assets/hubert_base/pytorch_model.bin
assets/rmvpe/rmvpe.pt
assets/pretrained/*.pth
assets/pretrained_v2/*.pth
assets/pymss_weights/*
assets/weights/*.pth
assets/indices/*.index
logs/mute/*
```

### 下载模型

```bash
python -m pip install --upgrade huggingface_hub

# Required for inference and feature extraction
hf download lj1995/VoiceConversionWebUI --revision main \
  --include "hubert_base/*" --local-dir assets
hf download lj1995/VoiceConversionWebUI rmvpe.pt --revision main \
  --local-dir assets/rmvpe

# Required for v1/v2 training
hf download lj1995/VoiceConversionWebUI --revision main \
  --include "pretrained/*" "pretrained_v2/*" --local-dir assets
hf download lj1995/VoiceConversionWebUI mute.zip --revision main \
  --local-dir .model-downloads
python -m zipfile -e .model-downloads/mute.zip logs

# Required only for pymss/MSST vocal separation
hf download lj1995/VoiceConversionWebUI --revision main \
  --include "pymss_weights/*" --local-dir assets
```

仅 Windows AMD/Intel DirectML 环境还需要：

```bash
hf download lj1995/VoiceConversionWebUI rmvpe.onnx --revision main \
  --local-dir assets/rmvpe
```

### FFmpeg

Ubuntu 已在前面的系统依赖命令中安装 FFmpeg。Windows 用户可把下面两个文件放到项目根目录：

- [ffmpeg.exe](https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/ffmpeg.exe?download=true)
- [ffprobe.exe](https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/ffprobe.exe?download=true)

## 开始使用

启动 WebUI：

```bash
python webui.py
```

无桌面的 Ubuntu 服务器：

```bash
python webui.py --noautoopen
```

默认服务监听端口为 `7865`。用户自己的 `.pth` 模型放入 `assets/weights/`，`.index` 文件放入 `assets/indices/`。

## 参考项目
+ [ContentVec](https://github.com/auspicious3000/contentvec/)
+ [VITS](https://github.com/jaywalnut310/vits)
+ [HIFIGAN](https://github.com/jik876/hifi-gan)
+ [Gradio](https://github.com/gradio-app/gradio)
+ [FFmpeg](https://github.com/FFmpeg/FFmpeg)
+ [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui)
+ [pymss-project/pymss](https://github.com/pymss-project/pymss)
+ [audio-slicer](https://github.com/openvpi/audio-slicer)
+ [Vocal pitch extraction:RMVPE](https://github.com/Dream-High/RMVPE)
  + The pretrained model is trained and tested by [yxlllc](https://github.com/yxlllc/RMVPE) and [RVC-Boss](https://github.com/RVC-Boss).

## 感谢所有贡献者作出的努力
<a href="https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/graphs/contributors" target="_blank">
  <img src="https://contrib.rocks/image?repo=RVC-Project/Retrieval-based-Voice-Conversion-WebUI" />
</a>

---

## 会话总结 - 2026-08-01

- **会话主要目的**: 分析当前程序（RVC WebUI）的功能
- **完成的主要任务**: 梳理入口、模块结构、WebUI 选项卡与核心推理/训练流程，输出功能分析
- **关键决策与解决方案**: 基于 README、webui.py、infer/、train/、realtime_gui.py 与启动脚本归纳；未改业务代码
- **使用的技术栈**: Gradio、PyTorch、HuBERT、FAISS、RMVPE、VITS/NSF、pymss、FreeSimpleGUI、sounddevice
- **修改的文件列表**: README.md（追加本总结）


---

## 会话总结 - 2026-08-01 (2)

- **会话主要目的**: 确认项目是否开源及能否修改代码
- **完成的主要任务**: 查阅 LICENSE（MIT）与相关协议说明，给出开源与修改权限结论
- **关键决策与解决方案**: 项目主体为 MIT 开源许可，可自由修改；需保留版权声明，并注意依赖库与训练数据版权
- **使用的技术栈**: 无（仅许可证分析）
- **修改的文件列表**: README.md（追加本总结）


---

## 会话总结 - 2026-08-01 (3)

- **会话主要目的**: 确认是否具备人声+伴奏混音/一键合并导出能力
- **完成的主要任务**: 检索 webui/infer/tools，确认仅有分离与变声，无轨道混音合并导出
- **关键决策与解决方案**: 结论为当前不支持；现有流程为「分离→推理人声→外部软件合并」；若用户需要可后续实现自动合并
- **使用的技术栈**: 无（功能调研）
- **修改的文件列表**: README.md（追加本总结）


---

## 会话总结 - 2026-08-01 (4)

- **会话主要目的**: 实现「分离 → 变声 → 自动叠伴奏」一键翻唱流水线
- **完成的主要任务**:
  1. 新增 	ools/song_cover.py：复用 pymss 分离与 VC 推理，混音导出成品
  2. 在 WebUI「模型推理」下增加「一键翻唱」选项卡
  3. 补充中英 i18n 文案
- **关键决策与解决方案**: 采用整曲一键流水线；中间茎干默认清理，可勾选保留；人声/伴奏音量可调；成品输出到指定文件夹
- **使用的技术栈**: Gradio、pymss/MSST、RVC VC、librosa、soundfile、numpy
- **修改的文件列表**:
  - tools/song_cover.py（新增）
  - webui.py
  - i18n/locale/zh_CN.json
  - i18n/locale/en_US.json
  - README.md（追加本总结）


---

## 会话总结 - 2026-08-01 (5)

- **会话主要目的**: 排查一键翻唱点击后界面像卡住的问题
- **完成的主要任务**:
  1. 确认并非死锁：PyMSS 子进程仍在运行，但环境为 `torch 2.13.0+cpu`，RTX 3060 未被使用
  2. 修复 `pymss_separate` 在无 `event_callback` 时丢弃 progress 事件，导致一键翻唱文本框无进度刷新
  3. 一键翻唱在 CPU 模式下增加慢速提示；补充中英 i18n
- **关键决策与解决方案**: UI 假死主因是进度未回传；速度慢主因是 CPU 版 PyTorch。建议安装 CUDA 版 Torch 后重启 WebUI
- **使用的技术栈**: Gradio、pymss、PyTorch、i18n
- **修改的文件列表**:
  - tools/pymss_webui.py
  - tools/song_cover.py
  - i18n/locale/zh_CN.json
  - i18n/locale/en_US.json
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-01 (6)

- **会话主要目的**: 在 conda 环境 rvc312 中安装 CUDA 版 PyTorch
- **完成的主要任务**:
  1. 分析上次失败原因：环境为 `torch 2.13.0+cpu`，与官方 cu118 轮子最高 `2.7.1` 版本不匹配；WebUI/PyMSS 进程占用 DLL 也会导致覆盖失败
  2. 停止 rvc312 相关 Python 进程后卸载 CPU 版 torch/torchaudio/torchvision
  3. 按项目要求安装 `torch==2.7.1+cu118`、`torchaudio==2.7.1+cu118`（南大镜像）
  4. 验证：`cuda available=True`，GPU 为 RTX 3060，`config.device=cuda:0`
- **关键决策与解决方案**: 不追新版 2.13 CUDA（官方 cu118 索引无对应轮子），改用项目锁定的 2.7.1+cu118；安装前必须先停 WebUI
- **使用的技术栈**: conda rvc312、PyTorch 2.7.1+cu118、pip 镜像
- **修改的文件列表**:
  - README.md（追加本总结）
  - 环境变更：rvc312 中 torch/torchaudio

---

## 会话总结 - 2026-08-03

- **会话主要目的**: 修复一键翻唱只出干声、缺少伴奏背景的问题，并对齐 Replay 式多音轨输出
- **完成的主要任务**:
  1. 强化流水线：分离人声/伴奏 → RVC 变声 → 叠伴奏导出成品
  2. 始终导出四路文件到输出目录：成品、转换后人声、原始人声、伴奏音乐
  3. WebUI「一键翻唱」改为音轨列表展示，可分别试听/下载
  4. 补充中英 i18n
- **关键决策与解决方案**: 以文件路径回传 Gradio Audio，避免只显示干声；成品为变声人声+伴奏混音，三轨对应 Replay 面板
- **使用的技术栈**: Gradio 3.14、pymss、RVC VC、soundfile、librosa
- **修改的文件列表**:
  - tools/song_cover.py
  - webui.py
  - i18n/locale/zh_CN.json
  - i18n/locale/en_US.json
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-03 (2)

- **会话主要目的**: 确认一键翻唱修改后是否漏加进度条
- **完成的主要任务**:
  1. 核对 webui.py「一键翻唱」与 PyMSS 分离页组件
  2. 确认一键翻唱仅有文本状态框与四路音轨，未挂载 HTML 进度条
- **关键决策与解决方案**: 结论为漏加；可视化进度条仅存在于 PyMSS 页（`render_pymss_progress` / `pymss_progress`）；一键翻唱分离阶段进度目前只写进 `cover_info` 文本。待用户确认后可复用同一进度条组件接入
- **使用的技术栈**: Gradio、tools/song_cover.py、webui.py
- **修改的文件列表**:
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-03 (3)

- **会话主要目的**: 为一键翻唱补进度条，并排查 CUDA OOM
- **完成的主要任务**:
  1. 一键翻唱按钮下方接入 HTML 进度条，分离阶段跟随 PyMSS 事件刷新
  2. 分析 OOM：RTX 3060 12GB 上 RVC 与 BS-RoFormer 争用显存；默认 chunk=352800 峰值过高
  3. 修复 `istft_roformer`：CUDA OOM 时原先非 MPS 仍在 GPU 重试（无效），改为 CPU fallback
  4. 分离前临时把 VC/Hubert 卸到 CPU；12GB 及以下自动降 chunk/overlap/batch
- **关键决策与解决方案**: 根因是显存争用 + 大 chunk，不是随机 bug；进度条复用 `render_pymss_progress`
- **使用的技术栈**: Gradio、PyTorch CUDA、PyMSS BS-RoFormer、i18n
- **修改的文件列表**:
  - tools/song_cover.py
  - tools/pymss_webui.py
  - tools/pymss_core/modules/bs_roformer/common.py
  - webui.py
  - i18n/locale/zh_CN.json
  - i18n/locale/en_US.json
  - README.md（追加本总结）

## 会话总结 - 2026-08-03 (4)

- **会话主要目的**: 排查「成品」未合并伴奏是系统不支持还是缺依赖
- **完成的主要任务**:
  1. 确认系统已支持混音（`mix_vocal_instrumental`），无需额外依赖
  2. 定位根因：RVC 输出 int16（±32768）与伴奏 float（±1）直接相加，峰值归一化后伴奏被压到几乎听不见
  3. 修复混音前音量归一化；已用现有分离结果重写本次 `_cover.wav`
- **关键决策与解决方案**: 在混音前统一把人声/伴奏转到 float [-1,1]（int16 / 32768），不引入新库
- **使用的技术栈**: soundfile、numpy、librosa、tools/song_cover.py
- **修改的文件列表**:
  - tools/song_cover.py
  - README.md（追加本总结）
  - opt/*_cover.wav（本地重混修复，未纳入版本库）

---

## 会话总结 - 2026-08-03 (5)

- **会话主要目的**: 将一键翻唱从 webui.py 拆出，降低与官方上游合并冲突
- **完成的主要任务**:
  1. 新增 `tools/song_cover_webui.py`：承载一键翻唱 Tab UI 与事件绑定
  2. 新增 `webui_cover.py`：启动时向官方 webui.py 注入 Tab（不改官方文件内容落盘）
  3. 从 `webui.py` 移除一键翻唱相关 import/Tab/`infer_change_voice` 改写，恢复官方 `sid0.change(vc.get_vc, ...)`
  4. `go-webui.bat` 改为启动 `webui_cover.py`
- **关键决策与解决方案**: 用启动器字符串注入锚点「人声伴奏分离&去混响」前插入 `build_song_cover_tab`；音色切换通过监听 `file_index1`/`protect0` 同步，避免二次 `get_vc`
- **使用的技术栈**: Gradio、functools.partial、exec 注入启动
- **修改的文件列表**:
  - tools/song_cover_webui.py（新增）
  - webui_cover.py（新增）
  - webui.py（移除一键翻唱）
  - go-webui.bat
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-04

- **会话主要目的**: 根据 `ai制作歌曲过程.docx` 中 SoundTrail 声迹 AI 的界面与日志，推断其开源技术栈，并对照本仓库 RVC-webui 评估 AI 跟唱实现路径
- **完成的主要任务**:
  1. 解析 docx 内 15 张截图：UI 参数、模型目录、处理日志与输出 JSON
  2. 推断 SoundTrail 离线做歌链路为 MSST 多阶段分离（伴奏/和声/去混响）+ RVC（HuBERT + RMVPE）+ FFmpeg
  3. 对照本仓库已有 `tools/song_cover.py`（一键翻唱）、`tools/pymss_webui.py`（MSST/pymss）、`RVCRealtimeVST`（实时变声）
  4. 给出基于 RVC-webui 补齐多轨/去混响/实时跟唱的实现建议
- **关键决策与解决方案**: SoundTrail 核心开源栈与 RVC 生态高度重合；`.model` 为封装格式，日志中 `infer.modules.vc.*` 与 `msst\separator.py` 为直接证据；实时修音/四轨播放为其自研层
- **使用的技术栈**: MSST/pymss、RVC、HuBERT、RMVPE、PyWorld、FFmpeg、PyTorch
- **修改的文件列表**:
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-04 (2)

- **会话主要目的**: 审查并修订 `开发大纲.md`，对齐 SoundTrail 实际链路与本仓库现有代码
- **完成的主要任务**:
  1. 指出原稿 10 处关键问题：离线缺去混响、`other` 误当和声、任务顺序与优先级矛盾、MSST/RVC 依赖错误、采样率/缓冲参数不合理等
  2. 补充对标范围表：实时 RVC 与声迹预渲染+修音路径差异
  3. 重写离线链路为 Stage1~3 + 四轨导出，映射 pymss 现有模型
  4. 调整任务顺序（0 调度骨架 → 离线优先 → 实时），拆分 RVC 4A/4B，补充代码复用表与打包风险
- **关键决策与解决方案**: 首版在 `tools/song_cover.py` 扩展而非重写；音频热路径允许内核直连；字级 F0 约束标为 Phase 2 自研
- **使用的技术栈**: PyQt6、MSST/pymss、RVC、sounddevice、OSC/MTC、Nuitka
- **修改的文件列表**:
  - 开发大纲.md
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-04 (3)

- **会话主要目的**: 按开发大纲阶段 0 实现调度骨架 + 配置/日志基座
- **完成的主要任务**:
  1. 新增 `app/` 包：`events.py` 信号协议、`config_store.py` JSON 配置、`log_setup.py` 分级日志、`scheduler.py` 单例调度总线
  2. 新增验收脚本 `scripts/test_task0_scheduler.py`（调度启停、配置读写、信号转发、shutdown hook）
  3. 日志模块独立实现，避免 import pymss 连带加载 torch
- **关键决策与解决方案**: 控制消息走 `AppScheduler.publish/subscribe`；配置默认写 `config/client.json`；阶段 0 零 UI/零音频依赖
- **使用的技术栈**: Python 3.12、stdlib logging/threading/json
- **修改的文件列表**:
  - app/__init__.py、events.py、config_store.py、log_setup.py、scheduler.py（新增）
  - scripts/test_task0_scheduler.py（新增）
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-04 (4)

- **会话主要目的**: 完成开发大纲分段任务 1（系统运维工具模块），遵守「新功能写新模块、不改上游已有代码」
- **完成的主要任务**:
  1. 新增 `app/ops/`：分级滚动日志、硬件信息采集、异常装饰器、日志打包/HTTP 上报、自动更新（版本/MD5/下载/回滚）
  2. 新增验收脚本 `scripts/test_task1_ops.py`（本地 mock 更新包 + 内置 HTTP 上传测试）
  3. 阶段 0 的 `app/` 文件未改动
- **关键决策与解决方案**: 运维能力全部落在 `app/ops/`；torch/sounddevice/httpx 按需 import，无依赖时降级不崩溃
- **使用的技术栈**: Python 3.12、RotatingFileHandler、httpx、urllib、zipfile
- **修改的文件列表**:
  - app/ops/*.py（新增）
  - scripts/test_task1_ops.py（新增）
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-04 (5)

- **会话主要目的**: 完成分段任务 5（MSST 人声分离内核），封装 pymss 实现普通/强力两套预设
- **完成的主要任务**:
  1. 新增 `app/msst/`：`presets.py` 预设、`types.py` 结果结构、`pipeline.py` 多阶段流水线
  2. 普通做歌：去伴奏 + 去混响；强力做歌：激进分离 + 激进去混响 + 提主旋律（和声轨）
  3. 支持进度回调、取消（`stop_pymss_separation`）、临时目录自动清理
  4. 新增 `scripts/test_task5_msst.py`（默认结构验收；`--live` 可选真实分离）
- **关键决策与解决方案**: 仅封装调用 `tools.pymss_webui`，不改上游；输出统一命名为 `*_vocals.wav` / `*_instrumental.wav` / `*_vocals_noreverb.wav` / `*_harmony.wav`
- **使用的技术栈**: pymss/MSST、Python dataclass
- **修改的文件列表**:
  - app/msst/*.py（新增）
  - scripts/test_task5_msst.py（新增）
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-04 (6)

- **会话主要目的**: 完成分段任务 4A（离线 RVC 翻唱流水线），串联 MSST 与 RVC 四轨导出
- **完成的主要任务**:
  1. 说明 task5 `--live` 输出在系统临时目录，脚本结束即删除（不影响功能验收）
  2. 新增 `app/rvc/`：`types.py`、`vc_context.py`、`offline_pipeline.py`
  3. 复用 `app/msst` 多阶段分离 + `tools/song_cover` GPU 释放/混音 + `infer.vc.modules.VC`
  4. 新增 `scripts/test_task4_offline.py`；`--live` 默认输出到 `opt/task4_offline/` 可持久查看
- **关键决策与解决方案**: 不改上游 song_cover/pymss；Config/VC 加载与 pymss 同样清理 sys.argv；formant 离线暂沿用 WebUI vc_single 能力
- **使用的技术栈**: RVC VC、MSST、pymss、soundfile
- **修改的文件列表**:
  - app/rvc/*.py（新增）
  - scripts/test_task4_offline.py（新增）
  - scripts/test_task5_msst.py（补充临时目录说明）
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-04 (7)

- **会话主要目的**: 完成分段任务 2（PyQt6 UI 骨架），对标 SoundTrail 布局并接入调度总线
- **完成的主要任务**:
  1. 新增 `app/ui/`：主窗口、悬浮歌词、系统托盘、UiBridge、布局持久化
  2. 四 Tab + 左资源栏 + 右参数面板 + 底日志与 GPU 状态
  3. `scripts/run_ui_skeleton.py` 交互启动；`scripts/test_task2_ui.py` 无头验收
  4. 新增 `requirments_client_ui.txt`（PyQt6）
- **关键决策与解决方案**: UI 仅 emit_action 至 AppScheduler；离线/实时按钮占位，集成阶段再接 MSST/RVC
- **使用的技术栈**: PyQt6、AppScheduler、ConfigStore
- **修改的文件列表**:
  - app/ui/*.py、requirments_client_ui.txt（新增）
  - scripts/run_ui_skeleton.py、scripts/test_task2_ui.py（新增）
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-04 (8)

- **会话主要目的**: 修正 UI 主界面结构，对齐 SoundTrail 一级三 Tab（播放 / 制作歌曲 / 公告），并更新开发大纲
- **完成的主要任务**:
  1. 重构 `app/ui/main_window.py` 为 Shell：顶栏 `HeaderBar` + `QStackedWidget` + 底状态栏/日志
  2. 新增 `app/ui/pages/`：`playback_page.py`、`song_make_page.py`（三栏离线做歌骨架）、`announce_page.py`
  3. 原「实时/离线/模型/设置」四 Tab 逻辑迁移：离线做歌 → 制作歌曲页；设置/模型导入 → 顶栏设置对话框
  4. 更新 `开发大纲.md` 分段任务 2 的 UI 结构与验收说明；`test_task2_ui.py` 改为校验 3 个顶层页
- **关键决策与解决方案**: 播放 Tab 承载 AI 跟唱/改词；制作歌曲 Tab 仅负责离线做歌三栏；公告 Tab 列表+详情占位；先骨架后功能
- **使用的技术栈**: PyQt6、QStackedWidget、UiBridge、AppScheduler
- **修改的文件列表**:
  - app/ui/main_window.py、app/ui/header_bar.py（新增/重构）
  - app/ui/pages/*.py（新增）
  - scripts/test_task2_ui.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-04 (9)

- **会话主要目的**: 完成分段任务 3（音频硬件 IO 调度模块）
- **完成的主要任务**:
  1. 新增 `app/audio/`：`devices.py`、`ring_buffer.py`、`stream_manager.py`、`service.py`
  2. Voicemeeter/VB-Cable/WASAPI 设备标记与默认设备推荐
  3. duplex 流 + 500ms 环形缓冲 + watchdog 热插拔重连 + 欠载 fade 平滑
  4. `AudioService` 对接 `AppScheduler`；扩展 `config/client.json` 的 `audio.*` 配置
  5. 新增 `scripts/test_task3_audio.py`（可选 `--live 3` passthrough 验收）
- **关键决策与解决方案**: PCM 热路径在 `AudioStreamManager` 内核直连环形缓冲；控制消息经调度层；WASAPI 独占仅可选开启并 fallback
- **使用的技术栈**: sounddevice、numpy、AppScheduler、ConfigStore
- **修改的文件列表**:
  - app/audio/*.py（新增）
  - app/config_store.py、scripts/test_task3_audio.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-04 (10)

- **会话主要目的**: 完成分段任务 4B（实时 RVC 流式推理）
- **完成的主要任务**:
  1. 新增 `app/rvc/realtime_config.py`、`realtime_engine.py`、`realtime_service.py`
  2. 封装 `infer.rtrvc.RVC` + SOLA/crossfade（逻辑对齐 `realtime_gui.py`）
  3. `RealtimeModelPool` 支持多模型预加载与热切换（共享 HuBERT）
  4. `RealtimeRvcService` 推理线程对接 `AudioStreamManager` 环形缓冲
  5. 新增 `scripts/test_task4_realtime.py`（块级推理 + 可选 `--live`）
  6. 扩展 `config/client.json` → `realtime.*`
- **关键决策与解决方案**: 不改上游 rtrvc；PCM 热路径 input_ring→推理→output_ring；index_rate 默认 0 便于无 index 验收
- **使用的技术栈**: PyTorch、infer.rtrvc、sounddevice 环形缓冲、AppScheduler
- **修改的文件列表**:
  - app/rvc/realtime_*.py、app/rvc/__init__.py、app/config_store.py（新增/更新）
  - scripts/test_task4_realtime.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-04 (11)

- **会话主要目的**: 完成分段任务 6（歌词同步 & Studio One 时间同步）
- **完成的主要任务**:
  1. 新增 `app/lyrics/`：LRC 解析、匹配器、OSC/MTC/仿真时钟、`LyricsService`
  2. 调度总线推送 `lyric_tick`（索引 + 文本 + 时间）
  3. `run_ui_skeleton.py` 接入悬浮歌词窗高亮
  4. 扩展 `config/client.json` → `lyrics.*`；`requirments_client_ui.txt` 增加 python-osc
  5. 新增 `scripts/test_task6_lyrics.py`（可选 `--osc` mock）
- **关键决策与解决方案**: 延迟补偿用 `offset_ms` 而非改 LRC 文件；OSC 地址可配置；MTC 为可选骨架
- **使用的技术栈**: python-osc、AppScheduler、PyQt6 LyricsWindow
- **修改的文件列表**:
  - app/lyrics/*.py、scripts/test_task6_lyrics.py（新增）
  - app/config_store.py、scripts/run_ui_skeleton.py、requirments_client_ui.txt、开发大纲.md、README.md

---

## 会话总结 - 2026-08-04 (12)

- **会话主要目的**: 完成分段任务 7（全量集成），串联 UI → 调度层 → 各内核模块
- **完成的主要任务**:
  1. 新增 `app/integration/ClientController` 统一路由 UI action
  2. 接入离线做歌、AI 跟唱（音频+RVC）、歌词加载、更新检查
  3. `run_ui_skeleton.py` 改为集成入口；托盘/播放 Tab 去掉占位提示
  4. 新增 `scripts/test_task7_integration.py`
- **关键决策与解决方案**: 控制器只做路由与生命周期；Studio One OSC 联调留待人工整体测试
- **使用的技术栈**: AppScheduler、ClientController、PyQt6 UiBridge
- **修改的文件列表**:
  - app/integration/*.py、scripts/test_task7_integration.py（新增）
  - scripts/run_ui_skeleton.py、app/ui/tray.py、app/ui/pages/playback_page.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-04 (13)

- **问题**: 点击「开始处理」报 `FileNotFoundError: ./i18n/locale/en_US.json`
- **原因**: 从 IDE/`scripts/` 启动时 cwd 不在项目根，上游 `I18nAuto` 用相对路径读 i18n
- **修复**: 新增 `upstream_import_context()`（env + chdir 项目根 + 清理 argv）；`song_cover`/`pymss` 导入前调用；`run_ui_skeleton.py` 启动时 `os.chdir(ROOT)`
- **修改文件**: `app/rvc/vc_context.py`、`upstream_imports.py`、`app/msst/pipeline.py`、`scripts/run_ui_skeleton.py`

---

## 会话总结 - 2026-08-04 (14)

- **会话主要目的**: AI 跟唱实机联调遇循环声；用户决定该项最后再做，并明确下一步方向
- **完成的主要任务**:
  1. 核对 `client.json`（input=1 / output=10 合理）与 Voicemeeter 反馈环根因（变声回灌 B1）
  2. 在 `开发大纲.md` 链路 1 / 任务 7 标注：**AI 跟唱 + Voicemeeter 联调挂起，最后再做**
  3. 列出任务 0~7 之后的建议顺序：UI 完善 → OSC 真机 → AI 跟唱路由 → 打包
- **关键决策与解决方案**: 实时跟唱代码保留；实机路由联调延后；离线做歌已可用
- **修改的文件列表**: 开发大纲.md、README.md

---

## 会话总结 - 2026-08-04 (15)

- **会话主要目的**: UI 完善，优先完成「AI 唱歌」功能（播放离线成品，非实时 RVC）
- **完成的主要任务**:
  1. 新增 `app/playback/`：`scan_song_library` 扫描 `opt/` 与 `opt/task4_offline/` 的 `*_cover.wav` / `*_converted_vocal.wav`
  2. 新增 `WavPlayer`（sounddevice 流式播放，支持暂停/停止/拖动进度）
  3. 重写 `playback_page.py`：歌库列表、搜索、刷新、大歌词区、进度条、AI 唱歌高亮按钮
  4. `ClientController` 接入 `playback_ai_sing` / 选歌 / 暂停 / 停止 / 拖动；播放时 manual 时钟驱动歌词
  5. 离线做歌完成后自动刷新歌库；`run_ui_skeleton.py` 绑定 UI 状态回传
  6. 扩展 `test_task7_integration.py` 歌库与 AI 唱歌路由验收
- **关键决策与解决方案**: AI 唱歌优先播放 `cover.wav`（无则 fallback `converted_vocal.wav`）；AI 跟唱保留但标注 Voicemeeter 待联调
- **使用的技术栈**: sounddevice、soundfile、PyQt6、AppScheduler、LyricsService ManualClock
- **修改的文件列表**:
  - app/playback/*.py、app/ui/pages/playback_page.py（新增/重写）
  - app/integration/controller.py、app/integration/state.py
  - scripts/run_ui_skeleton.py、scripts/test_task7_integration.py、README.md

---

## 会话总结 - 2026-08-04 (16)

- **会话主要目的**: 排查 MP3（11MB《星星点灯》）离线做歌 RVC 转换失败原因并修复
- **完成的主要任务**:
  1. 核对 `opt/task4_offline/`：MSST 四轨已全部生成，仅 RVC 阶段失败 → **非 MP3 格式/文件大小问题**
  2. 根因：歌曲约 **303 秒**，RMVPE 对整段干声做 F0 时 GPU 显存不足（15s 片段可成功）
  3. `offline_pipeline.py` 新增 **45 秒分段 RVC 推理**（`_vc_infer`），长歌自动分段再拼接
  4. 失败时 UI 日志输出完整 `detail` 堆栈，便于后续排查
- **关键决策与解决方案**: MP3 由 MSST/ffmpeg 正常读取；瓶颈在 RVC 长音频显存；分段推理不改上游 infer/
- **使用的技术栈**: soundfile、PyTorch/RVC、RMVPE、RTX 3060 12GB
- **修改的文件列表**:
  - app/rvc/offline_pipeline.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-04 (17)

- **会话主要目的**: 排查播放页找不到 LRC 歌词的原因
- **完成的主要任务**:
  1. 确认命名规则：LRC 须与 WAV **主文件名**一致，如 `星星点灯-郑智化.lrc`；用户误命名为 `*_cover.lrc`
  2. 扩展 `find_lrc_in_dir`：兼容 `{stem}_cover.lrc` 等同目录变体
  3. 选歌时重新扫描 LRC 并 `isfile` 校验，避免路径不存在时抛错
- **修改的文件列表**: app/playback/library.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-04 (18)

- **会话主要目的**: 播放页歌词应显示在中间主区域，而非仅在右侧列表
- **完成的主要任务**:
  1. 修复 `lyric_tick` 事件路由：原仅监听 SCHEDULER，歌词模块 LYRICS 发出的 tick 未到达播放页
  2. 中间区改为 K 歌布局：上一句（灰）/ 当前句（大字蓝）/ 下一句（灰）
  3. 加载 LRC 后中间立即显示首句；播放时随进度高亮并滚动右侧进度列表
- **修改的文件列表**: app/ui/pages/playback_page.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-04 (19)

- **会话主要目的**: 播放页波形可视化（替换占位符）
- **完成的主要任务**:
  1. 新增 `app/ui/waveform_widget.py`：soundfile 分块峰值采样 + QPainter 绘制
  2. 后台 QThread 加载长音频，避免阻塞 UI
  3. 已播放区域深蓝 / 未播放浅蓝，竖线指示播放头
  4. 点击波形可 seek；选歌自动加载 `cover.wav` 波形
- **使用的技术栈**: PyQt6、numpy、soundfile
- **修改的文件列表**: app/ui/waveform_widget.py、app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-04 (20)

- **会话主要目的**: 波形可视化随歌曲「动起来」，避免静态假波形感
- **完成的主要任务**:
  1. 改为**滚动视窗**：播放头固定在左侧 36%，波形向左滚动
  2. **33ms 帧动画**：播放时在两次 tick 之间线性插值，播放头连续移动
  3. 播放头附近柱条脉冲提亮；已播/未播分色；点击仍可 seek
- **修改的文件列表**: app/ui/waveform_widget.py、app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-04 (21)

- **会话主要目的**: 禁用「服务器制作」占位功能；制作页增加 RVC 模型/Index 导入
- **完成的主要任务**:
  1. 「服务器制作」勾选框禁用并标注「暂未开放」；提交任务时不再携带 `server_mode`
  2. 制作页「基础参数」区新增 **RVC 模型** 下拉 + **导入…** 按钮（不再藏在折叠的高级参数里）
  3. 导入逻辑修正：`.pth` → `assets/weights/`，`.index` → `assets/indices/`；支持多选与导入完成提示
  4. 选中模型后自动检测并显示 Index 匹配状态（绿/灰提示）
  5. 设置对话框「导入 RVC 模型…」复用同一入口
- **关键决策与解决方案**: 沿用 `resolve_index_for_model` 匹配规则；设置与制作页共用 `import_models()`
- **使用的技术栈**: PyQt6、RVC vc_context
- **修改的文件列表**: app/ui/pages/song_make_page.py、app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-04 (22)

- **会话主要目的**: 隐藏制作页未实现的「是否分离伴奏」「服务器制作」选项
- **完成的主要任务**:
  1. 从制作页「基础参数设置」移除两个勾选框及相关 payload 字段
  2. 清理未使用的 `QCheckBox` 导入
- **关键决策与解决方案**: 两项均为占位/无效逻辑，直接隐藏而非禁用，避免界面干扰
- **修改的文件列表**: app/ui/pages/song_make_page.py、README.md

---

## 会话总结 - 2026-08-04 (23)

- **会话主要目的**: 隐藏离线做歌无效的「声音粗细」控件
- **完成的主要任务**: 从制作页右栏移除 formant 滑条及标签（离线 RVC 未接入该参数）
- **修改的文件列表**: app/ui/pages/song_make_page.py、README.md

---

## 会话总结 - 2026-08-04 (28)

- **会话主要目的**: 完成阶段性演示打包，便于客户体验 AI 唱歌
- **完成的主要任务**:
  1. 新增 `scripts/build_client_package.py` + `build_client_package.ps1`：staging、启动 bat、VERSION、可选 zip/lite/conda-pack
  2. `packaging/DEMO_README.md` 客户演示说明（做歌 → AI 唱歌流程）
  3. `packaging/manifest.json` / `version.json` / `INSTALL_RUNTIME.md`
  4. 窗口标题显示版本号（`app/ops/version.py` 读 VERSION 文件）
- **打包命令**: `.\scripts\build_client_package.ps1 -Zip`（含 assets）；`-Lite` 精简；`-CondaPack` 内置 Python
- **修改的文件列表**: scripts/build_client_package.py、scripts/build_client_package.ps1、packaging/*、app/ops/version.py、app/ui/main_window.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-04 (29)

- **会话主要目的**: 内置 FFmpeg 到 `tools/ffmpeg`，客户无需配置 PATH
- **完成的主要任务**:
  1. 新增 `app/runtime_env.py`：启动时 prepend `tools/ffmpeg` 到 PATH
  2. `run_ui_skeleton.py` / 启动 bat / `pymss_webui.py` 统一走内置路径
- **修改的文件列表**: app/runtime_env.py、scripts/run_ui_skeleton.py、tools/pymss_webui.py、scripts/build_client_package.py、packaging/DEMO_README.md、tools/ffmpeg/README.txt

---

## 会话总结 - 2026-08-05 (1)

- **会话主要目的**: 修复打包后启动客户端时的 Qt 日志过滤器崩溃
- **完成的主要任务**:
  1. 修复 `scripts/run_ui_skeleton.py` 中 `QtMsgType` 不支持 `>=` 比较导致的 `TypeError`
  2. 最终改为枚举白名单 `mode in (Warning, Critical, Fatal)`：`>=` 与 `int()` 在该 PyQt6 版本均不可用
  3. 同步更新 `dist/RVC-Client-0.1.0-demo/scripts/run_ui_skeleton.py`，无需重新打包即可验证
- **关键决策与解决方案**: 用 `in` 判断 Qt 日志级别，跨版本最稳妥
- **使用的技术栈**: PyQt6
- **修改的文件列表**: scripts/run_ui_skeleton.py、dist/RVC-Client-0.1.0-demo/scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-05 (2)

- **会话主要目的**: 修复打包后「开始处理」报 `No module named 'torch'`
- **完成的主要任务**:
  1. 确认 dist 包未含 `python/`（打包时未执行 CondaPack），启动器误用无 torch 的系统 Python
  2. 新增 `scripts/resolve_launch_python.ps1`：自动查找内置或 conda 中带 PyTorch 的 Python
  3. 重写 `StartClient.bat` / `StartClient_Debug.bat`，启动前校验 torch
  4. 启动与做歌失败时增加中文提示；打包脚本无 `python/` 时输出 WARNING
  5. 更新 `DEMO_README.md`：发客户必须用 `build_demo_package.bat`
- **关键决策与解决方案**: 做歌依赖 PyTorch，演示包必须 CondaPack 打入 `python/` 或本机有 rvc312
- **使用的技术栈**: PowerShell、conda-pack、PyTorch
- **修改的文件列表**: scripts/resolve_launch_python.ps1、scripts/build_client_package.py、scripts/run_ui_skeleton.py、app/integration/controller.py、packaging/DEMO_README.md、dist/RVC-Client-0.1.0-demo/*

---

## 会话总结 - 2026-08-05 (3)

- **会话主要目的**: 将用户 conda 路径 `F:\zxh\anaconda3\envs\rvc312` 纳入启动器自动查找
- **完成的主要任务**:
  1. `resolve_launch_python.ps1` 增加 `F:\zxh\anaconda3`，并优先尝试 `rvc312`
  2. 优化查找顺序，避免扫描全部 env 导致启动等待 ~90s
  3. 已验证可解析到 `F:\zxh\anaconda3\envs\rvc312\python.exe`
- **修改的文件列表**: scripts/resolve_launch_python.ps1、dist/RVC-Client-0.1.0-demo/scripts/resolve_launch_python.ps1、README.md

---

## 会话总结 - 2026-08-05 (4)

- **会话主要目的**: 客户开箱即用，将 rvc312 conda 环境打入演示包
- **完成的主要任务**:
  1. 重写 `build_client_package.ps1`：自动找 `F:\zxh\anaconda3`、安装 conda-pack、解压后 conda-unpack、验证 torch
  2. 修复大 zip 用 Python `make_archive` 替代 `Compress-Archive`（避免 2GB 限制）
  3. 更新 `build_demo_package.bat`、`INSTALL_RUNTIME.md`、`DEMO_README.md` 客户/开发者说明
- **客户侧流程**: 解压 zip → 双击启动，优先用包内 `python\python.exe`，无需装 conda
- **开发者操作**: 双击 `build_demo_package.bat`（约 10~30 分钟，4~8GB）
- **修改的文件列表**: scripts/build_client_package.ps1、build_demo_package.bat、packaging/INSTALL_RUNTIME.md、packaging/DEMO_README.md、README.md

---

## 会话总结 - 2026-08-05 (5)

- **会话主要目的**: 修复 CondaPack 打包失败（tar 打不开、python.exe 不存在）
- **根因**:
  1. `conda pack -n rvc312` 找不到环境（conda 不在 PATH）→ 改 `--prefix F:\zxh\anaconda3\envs\rvc312`
  2. rvc312 有 pip/conda 冲突（torchvision/torchaudio）→ 加 `--ignore-missing-files --force`
- **完成的主要任务**: 重写 build_client_package.ps1，每步校验产物；实测 pack 成功约 6.24GB
- **修改的文件列表**: scripts/build_client_package.ps1、packaging/INSTALL_RUNTIME.md、README.md

---

## 会话总结 - 2026-08-05 (6)

- **会话主要目的**: 修复 CondaPack 打包失败；去掉自动 zip
- **根因**: `Invoke-Conda` 参数名 `$Args` 与 PowerShell 内置变量冲突，导致 conda 无参运行只打印 help
- **完成的主要任务**:
  1. 参数改为 `$CondaArgs`，conda install/pack 可正常执行
  2. 移除 `-Zip` 及自动压缩逻辑，打包完成后手动压缩文件夹
  3. 更新 `build_demo_package.bat`、`INSTALL_RUNTIME.md`
- **修改的文件列表**: scripts/build_client_package.ps1、build_demo_package.bat、packaging/INSTALL_RUNTIME.md、README.md

---

## 会话总结 - 2026-08-05 (7)

- **会话主要目的**: 打包后启动主界面过慢
- **根因**: 启动前同步 `import torch`（打包版 Python 首次加载约 10~30s）；启动器也对内置 python 做 torch 检测；MainWindow 初始化即查 GPU
- **完成的主要任务**:
  1. 移除 run_ui_skeleton 启动时阻塞式 import torch
  2. MainWindow GPU 状态改为 8 秒后首次刷新，不阻塞首屏
  3. 内置 `python\python.exe` 直接启动，跳过 torch 检测；StartClient.bat 优先用内置 python
- **说明**: 点「开始处理」时仍会加载 torch，仅优化首屏；打包版 Python 本身比 conda 原生略慢属正常
- **修改的文件列表**: scripts/run_ui_skeleton.py、app/ui/main_window.py、scripts/resolve_launch_python.ps1、scripts/build_client_package.py

---

## 会话总结 - 2026-08-05 (8)

- **会话主要目的**: 双包打包脚本，按显卡选择 cu118 / cu128
- **完成的主要任务**:
  1. `build_client_package.ps1` 增加 `-CudaVariant cu118|cu128`，自动映射 conda 环境与版本号
  2. 新增 `build_demo_package_menu.bat`、`build_demo_package_cu118.bat`、`build_demo_package_cu128.bat`
  3. 新增 `setup_conda_cu128.ps1` / `setup_conda_cu128.bat` 创建 50 系环境
  4. 打包产物含 `GPU_VARIANT.txt`；更新 INSTALL_RUNTIME.md、DEMO_README.md
- **修改的文件列表**: scripts/build_client_package.ps1、scripts/build_client_package.py、scripts/setup_conda_cu128.ps1、build_demo_package*.bat、packaging/*

---

## 会话总结 - 2026-08-05 (8)

- **会话主要目的**: 修复 GitHub push 因大文件被拒（ffprobe.exe > 100MB）
- **完成的主要任务**:
  1. 新增根目录 `.gitignore`（忽略 ffmpeg exe、`__pycache__`、大模型权重、本地构建目录等）
  2. 用 `git filter-branch` 从 3 个未推送本地提交中移除 `tools/ffmpeg/ffmpeg.exe`、`ffprobe.exe`（工作区 exe 已恢复并被 ignore）
  3. 取消已 staged 的全部 `__pycache__/*.pyc`
- **关键决策**: 不把 FFmpeg 二进制进仓库/LFS，本地保留 + 打包时拷贝；仅重写未推送提交
- **技术栈**: Git filter-branch、.gitignore
- **修改的文件列表**: .gitignore、README.md（本总结）；历史重写涉及 `eaf4ccc` 等 3 个本地提交（现哈希已变）

---

## 会话总结 - 2026-08-05 (9)

- **会话主要目的**: 排查客户端「运行一段时间后崩溃」问题
- **完成的主要任务**:
  1. 分析 `logs/client/client.log`：16:20 JSON 语法错误（`zh_CN.json` 已修复）；16:52/16:56 做歌完成后 `QListWidgetItem` 未导入导致 UI 回调失败（源码已含 import）；16:25 离线任务约 3 分钟无 traceback 即退出，疑为后台线程直接更新 PyQt 控件
  2. `run_ui_skeleton.py`：STATUS/PROGRESS 回调经 `QTimer.singleShot(0, …)` 切回主线程；增加 `faulthandler` + `threading.excepthook` 写入 `logs/client/crash.log`
  3. `offline_pipeline.py`：MSST/RVC 各阶段增加 INFO 日志便于定位卡点
- **关键决策**: 离线 worker 经 scheduler 回调 UI 必须在 Qt 主线程执行，避免随机闪退
- **技术栈**: PyQt6 QTimer、Python faulthandler、RotatingFileHandler
- **修改的文件列表**: scripts/run_ui_skeleton.py、app/rvc/offline_pipeline.py、README.md

---

## 会话总结 - 2026-08-05 (10)

- **会话主要目的**: 修复上次主线程改动后制作进度条不更新
- **完成的主要任务**:
  1. 根因：工作线程里 `QTimer.singleShot` 无法可靠把 UI 更新投递到 Qt 主线程，进度条停在 0%
  2. `UiBridge` 新增 `ui_status` / `ui_progress` 信号，经 `pyqtSignal` 跨线程安全更新 UI
  3. 进度条增加高度、百分比文字与蓝色 chunk 样式；`apply_offline_progress` 兼容 `stage_start` 事件
- **关键决策**: 后台线程更新 PyQt 控件必须用 Signal，不能用裸 QTimer
- **修改的文件列表**: app/ui/bridge.py、scripts/run_ui_skeleton.py、app/ui/pages/song_make_page.py、README.md

---

## 会话总结 - 2026-08-05 (11)

- **会话主要目的**: 修复点击窗口关闭后 `python.exe` 进程仍驻留
- **完成的主要任务**:
  1. 根因：系统托盘图标存在时，Qt 关主窗口不会退出事件循环
  2. `MainWindow.closeEvent`：停止 GPU 定时器、关闭歌词窗、隐藏托盘，并调用 `QApplication.quit()`
  3. `aboutToQuit` 统一执行 `controller.shutdown()` / `scheduler.shutdown()`，避免重复清理
- **关键决策**: 点右上角 × 即完全退出；需后台驻留时改从托盘「打开主界面」
- **修改的文件列表**: app/ui/main_window.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-06

- **会话主要目的**: 关闭客户端时消除卡顿，并增加误触确认
- **完成的主要任务**:
  1. 关闭时 `scheduler.shutdown()` 改在后台线程执行，主线程仅轮询并显示「正在退出，请稍候…」
  2. 点右上角 × 弹出确认对话框，默认「否」；托盘「退出」同样走确认 + 异步退出
  3. `aboutToQuit` 保留兜底清理，异步已完成时不再重复阻塞
- **关键决策**: 重资源释放异步化，UI 只负责确认与状态提示
- **修改的文件列表**: app/ui/main_window.py、scripts/run_ui_skeleton.py、app/ui/tray.py、README.md

---

## 会话总结 - 2026-08-06 (2)

- **会话主要目的**: 确认 Voicemeeter Potato 下 Studio One + RVC 外置联调方案，并编写可交付文档
- **完成的主要任务**:
  1. 说明 VST3 插件（已有）与 VST3 宿主（后期 1:1）区别；外置 VM+S1 为过渡路线
  2. 新增 `docs/cn/StudioOne_Voicemeeter_Potato联调指南.md`：Potato 条带/B1/VAIO/AUX 路由、S1 VST3、OSC 歌词、OBS、验收清单与排错
- **关键决策**: 用户 Voicemeeter 版本为 Potato；直播变声优先 S1+RVC VST3，客户端负责做歌/AI唱歌/歌词
- **修改的文件列表**: docs/cn/StudioOne_Voicemeeter_Potato联调指南.md、README.md

---

## 会话总结 - 2026-08-06 (3)

- **会话主要目的**: 实现 AI 跟唱 MVP（任务 9），对标声迹「预渲染旋律 + 实时修音」
- **完成的主要任务**:
  1. 新增 `app/pitchfix/`：`f0_curve`（converted_vocal RMVPE/pyin 参考曲线）、`corrector`（块级 pitch_shift）、`PitchFollowService`（伴奏+修音麦 duplex 输出）
  2. `playback_ai_follow` 改走修音跟唱；托盘 `ai_toggle` 仍为实时 RVC 变声（`_start_realtime_voice`）
  3. `config/client.json` 增加 `pitchfix.*`；`scripts/test_task9_pitchfix.py` 烟测通过
- **关键决策**: 首版用 librosa pyin/yin + pitch_shift，强度/半音上限可配置；需歌库条目含 instrumental + converted_vocal
- **修改的文件列表**: app/pitchfix/*、app/integration/controller.py、app/integration/state.py、app/ui/pages/playback_page.py、scripts/run_ui_skeleton.py、config/client.json、scripts/test_task9_pitchfix.py、README.md

---

## 会话总结 - 2026-08-06 (4)

- **会话主要目的**: 修复 AI 跟唱点击卡 UI；同步讨论结论到开发大纲
- **完成的主要任务**:
  1. F0 提取改后台线程 `ai-follow-prepare`；即时提示「正在加载参考旋律…」；按钮显示「加载中…」
  2. F0 降采样 22050 + 磁盘缓存 `.f0.npz`，二次启动显著加快
  3. `开发大纲.md` 增补 2026-08-06 审查：不做项、VST3 策略、VM+S1 过渡、任务 9 MVP 进度
- **修改的文件列表**: app/pitchfix/f0_curve.py、app/pitchfix/service.py、app/integration/controller.py、app/integration/state.py、app/ui/pages/playback_page.py、scripts/run_ui_skeleton.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-05 (12)

- **会话主要目的**: 复核声迹技术栈分析遗漏点，并澄清歌词格式能否对标声迹需求
- **完成的主要任务**:
  1. 确认离线核心推断（MSST + RVC）仍成立；补充产品层差异：逐字歌词、改词轨、LUFS、平台歌词下载、自研修音/云端 SVC 等
  2. 明确传统行级 LRC 仅够行高亮；声迹宣传「逐字高亮 / 5ms 级」需 Enhanced LRC（`<mm:ss>` 字标记）或 KRC/QRC 类格式
  3. 对照本仓库：当前 `lrc_parser.py` 只解析行级，字级标签会被剥掉
- **关键决策**: 首版继续用标准 LRC 做行同步即可；要对齐声迹嘴型/逐字体验需升级为 Enhanced LRC（或同等字级时间轴）+ UI 逐字渲染，属 Phase 2
- **使用的技术栈**: 无代码改动（分析）
- **修改的文件列表**:
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-05 (13)

- **会话主要目的**: 评估后期修词是否应改用 Enhanced LRC，以及字级歌词能否自动生成
- **完成的主要任务**:
  1. 建议：对外交换/落盘用 Enhanced LRC；内存用字级结构；兼容导入标准 LRC
  2. 说明字级歌词可自生成：人声轨 + 文本（可选）→ Whisper/强制对齐 → 导出 Enhanced LRC
  3. 修词流程：改文本后按旧时间轴重映射或局部重对齐，不必依赖网上难找的 Enhanced LRC
- **关键决策**: 不现在改解析器；修词/逐字作为 Phase 2，以「自动对齐生成 + Enhanced LRC 落盘」为主路径
- **使用的技术栈**: 无代码改动（方案讨论）
- **修改的文件列表**:
  - README.md（追加本总结）

---

## 会话总结 - 2026-08-05 (14)

- **会话主要目的**: 按近期结论与 AI 跟唱思路修订 `开发大纲.md`，为后期 Enhanced LRC/修词留任务，暂不改业务代码
- **完成的主要任务**:
  1. 增加 2026-08-05 审查修订记录；文档说明区分 Phase 1（0~7）与 Phase 2（8+）
  2. 更新对标表与「AI 跟唱实现思路」；链路 3 拆 Phase 1/2；新增分段任务 8（Enhanced LRC/对齐/修词）
  3. 进度与下一步：先收尾 OSC/Voicemeeter 联调，再开任务 8；明确不做酷狗 KRC 主路径
- **关键决策**: 落盘 Enhanced LRC + 人声自动对齐；修词与改词轨音频分阶段
- **修改的文件列表**:
  - 开发大纲.md、README.md

---

## 会话总结 - 2026-08-05 (15)

- **会话主要目的**: 按用户目标将 AI 跟唱主路径改为「预渲染 AI 人声 + 内置实时修音」，并修订开发大纲
- **完成的主要任务**:
  1. 确认可行：离线预渲染已有；缺自研修音模块（任务 9）；实时 RVC 降为说话变声辅路径
  2. 重写链路 1、对标表、热路径；新增 `app/pitchfix/` 分段任务 9 与验收标准
  3. 更新进度/下一步：先稳 AI 唱歌播放，再开任务 9
- **关键决策**: 产品验收以预渲染+内置修音为准，禁止用整段实时 RVC 冒充跟唱
- **修改的文件列表**:
  - 开发大纲.md、README.md

---

## 会话总结 - 2026-08-06 (16)

- **会话主要目的**: 修复 AI 跟唱运行一段时间后界面卡住/转圈
- **完成的主要任务**:
  1. 修音核心改用 `scipy.signal.resample` 轻量变调，替换每块 `librosa.effects.pitch_shift`（CPU/GIL 过重）
  2. F0 估计改为降采样自相关，每 3 块估一次；积压时直通麦克风避免 worker 拖死
  3. AI 跟唱关闭歌词 20Hz 独立线程，改 follow tick 250ms 统一刷进度与歌词
- **关键决策**: 卡顿主因是实时修音 + 高频 UI 信号，而非启动阶段 F0 缓存
- **技术栈**: NumPy、SciPy、PyQt 信号节流
- **修改的文件列表**:
  - app/pitchfix/corrector.py、app/pitchfix/service.py
  - app/lyrics/service.py、app/integration/controller.py
  - README.md

---

## 会话总结 - 2026-08-06 (17)

- **会话主要目的**: 评估并将 F0 缓存（`.f0.npz`）前移到离线做歌，避免 AI 跟唱点击后卡顿
- **完成的主要任务**:
  1. 确认卡顿主因：无缓存时 `ReferenceF0Curve.from_wav` 在跟唱启动阶段跑整段 `librosa pyin`（约 10s CPU 占满）
  2. 离线流水线 RVC/混音完成后自动 `ReferenceF0Curve.from_wav(converted_vocal)`
  3. AI 跟唱启动提示区分「有缓存 / 无缓存」；新增 `scripts/build_f0_cache.py` 给旧歌补缓存
- **关键决策**: F0 属于离线可预计算资产，不应在跟唱热路径首次生成
- **修改的文件列表**:
  - app/rvc/offline_pipeline.py、app/pitchfix/f0_curve.py
  - app/integration/controller.py、scripts/build_f0_cache.py
  - README.md

---

## 会话总结 - 2026-08-06 (19)

- **会话主要目的**: 做歌末尾生成 `.f0.npz` 时 UI「未响应」，需慢但不卡界面
- **完成的主要任务**:
  1. 定位原因：虽在后台线程，但 `librosa pyin` 占 GIL/CPU，Qt 主线程得不到调度
  2. F0 生成改 **子进程**（`f0_build_cli.py` + `build_f0_cache_isolated`），与 UI 进程隔离
  3. 等待期间 heartbeat 刷进度；取消制作会 terminate 子进程
- **关键决策**: 用子进程而非再加线程/async；做歌线程可阻塞，UI 进程不能
- **修改的文件列表**:
  - app/pitchfix/f0_curve.py、app/pitchfix/f0_build_cli.py
  - app/rvc/offline_pipeline.py、README.md

---

## 会话总结 - 2026-08-07 (20)

- **会话主要目的**: 对标声迹 AI，增加 AI 跟唱混音调节面板（喇叭按钮）
- **完成的主要任务**:
  1. 播放页控制条增加 🔊 按钮，弹出混音浮层（伴奏/人声/原唱/阈值/衰减 + 重置）
  2. 滑块实时写入 `config/client.json` 并 `apply_settings` 到运行中的 `PitchFollowService`
  3. 混音支持 AI 原唱轨叠加；阈值控制修音门限；衰减影响修音强度
- **修改的文件列表**:
  - app/ui/ai_follow_mix_panel.py、app/ui/pages/playback_page.py
  - app/pitchfix/service.py、app/integration/controller.py、config/client.json、README.md

---

## 会话总结 - 2026-08-07 (21)

- **会话主要目的**: MVP 实现声迹「AI 跑调模式」并更新开发大纲待办
- **完成的主要任务**:
  1. 新增 `app/pitchfix/detune.py`：8 种 LFO 预设，对目标 F0 叠加音分抖动
  2. 🔊 混音面板增加「AI跑调模式」下拉，实时写入 config 并生效
  3. `开发大纲.md` §任务9 补充已完成/未完成清单（RMVPE、播放设置 Tab、智能切换等）
- **技术栈**: LFO、音分→Hz 换算、PyQt6 QComboBox
- **修改的文件列表**:
  - app/pitchfix/detune.py、service.py
  - app/ui/ai_follow_mix_panel.py、app/integration/controller.py
  - config/client.json、scripts/test_task9_pitchfix.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-07 (22)

- **会话主要目的**: 修复开发环境首次启动 UI 需 1 分钟+的问题
- **完成的主要任务**:
  1. 定位根因：`SongMakePage` 启动时 `resolve_index_for_model` 导入 `infer.hubert` → 连带加载 PyTorch（~7s+）
  2. 新增 `app/rvc/index_lookup.py` 轻量 Index 查找，不导入 torch
  3. 启动 splash「正在启动…」；烟测启动从 ~10s 降至 ~3.5s
- **修改的文件列表**:
  - app/rvc/index_lookup.py、app/rvc/vc_context.py
  - app/ui/pages/song_make_page.py、scripts/run_ui_skeleton.py
  - scripts/profile_ui_startup.py、README.md

---

## 会话总结 - 2026-08-06 (18)

- **会话主要目的**: 根据日志修复 AI 跟唱几秒后自动停止的线程 bug
- **完成的主要任务**:
  1. 定位 `ai-follow-tick` 结束时调用 `stop_ai_follow()` → `join` 自身 → `RuntimeError: cannot join current thread`
  2. 拆分 `_release_ai_follow()`；tick 线程在 `finally` 里收尾，禁止 join 当前线程
  3. 外部 `stop_ai_follow` 仅 join 其他线程，避免重复清理
- **关键决策**: 日志中 21:46:17 启动、21:46:31 报错并非 F0 慢，而是 tick 线程崩溃导致跟唱被误停
- **修改的文件列表**:
  - app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-07

- **会话主要目的**: 记录 Voicemeeter 联调问题；修复 AI 跟唱与 AI 唱歌切换不同步、跟唱后无法点「AI 唱歌」
- **完成的主要任务**:
  1. `开发大纲.md` 追加 VM/VAIO 路由与听感联调备注（AUX 误选、H1 A1 回音、VAIO 推子）
  2. 跟唱↔唱歌切换共用播放头：`PitchFollowService.seek` + controller 携带 `carry_pos`
  3. 播放页按钮互锁调整：跟唱/唱歌可互相切换，不再 disable
  4. 跟唱模式下进度条 seek 同步伴奏参考轨
- **关键决策**: 对标声迹「唱到 A 切模式从 A 继续」；VM 问题暂搁置文档化
- **技术栈**: PyQt6、PitchFollowService、WavPlayer、Voicemeeter Potato
- **修改的文件列表**:
  - app/pitchfix/service.py、app/integration/controller.py、app/ui/pages/playback_page.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-07 (2)

- **会话主要目的**: AI 跟唱/唱歌切换时歌词不同步，改为共用歌词会话
- **完成的主要任务**:
  1. `LyricsService.sync_at(force)` + 同路径 LRC 跳过重复 load
  2. 模式切换 `handoff`：不 stop 歌词、不重发 `playback_stopped`/`ai_follow_stopped`
  3. 跟唱/唱歌统一由播放 tick 驱动 `sync_at`（无独立 lyrics 线程）
- **关键决策**: 对标声迹「同一播放头 T + 同一套歌词」；仅用户点停止或换歌才 teardown
- **修改的文件列表**:
  - app/lyrics/service.py、app/integration/controller.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-07 (3)

- **会话主要目的**: 修复唱歌→跟唱切换时歌词仍跳回开头
- **完成的主要任务**:
  1. `_select_song` 同路径 LRC 不再重复发 `lyrics_loaded`（根因：UI 被重置到第一句）
  2. 唱歌→跟唱 handoff 后立即 `sync_at` + 发 `playback_tick` 锁定进度
  3. `ai_follow_preparing` 时 UI 提前切到跟唱模式并保持进度条
- **修改的文件列表**:
  - app/integration/controller.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-07 (4)

- **会话主要目的**: 跟唱→唱歌按钮无选中态；唱歌→跟唱切换不够丝滑
- **完成的主要任务**:
  1. 修复 handoff 竞态：tick 线程 `finally` 误发 `ai_follow_stopped` 导致 UI 回 idle、AI 唱歌失蓝
  2. 跟唱 **先出声再加载 F0**（伴奏/原唱轨立即播放，F0 后台加载）
  3. `PitchFollowService.start(song, seek_sec)` 切换时直接 seek，减少静音间隙
- **修改的文件列表**:
  - app/integration/controller.py、app/pitchfix/service.py、README.md

---

## 会话总结 - 2026-08-07 (5)

- **会话主要目的**: 修复 🔊 混音面板拖动参数时偶发 `[WinError 5] 拒绝访问` 导致跟唱停止
- **完成的主要任务**:
  1. `ConfigStore.save()` 增加线程锁、重试与直接写 `client.json` 回退
  2. `_update_ai_follow_mix` 先 `apply_settings` 再 **350ms 防抖写盘**；写盘失败仅 warning，不抛错中断跟唱
- **关键决策**: 滑条拖动实时改听感，落盘合并为单次；Windows 文件占用时不阻断播放
- **技术栈**: PyQt6、threading.Timer、ConfigStore
- **修改的文件列表**:
  - app/config_store.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-07 (6)

- **会话主要目的**: 修复点击「普通说话」报 `NameError: passthrough_gain_from_audio is not defined`
- **完成的主要任务**: 在 `controller.py` 顶部补充 `from app.audio.service import passthrough_gain_from_audio`
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-07 (7)

- **会话主要目的**: 播放控制对标声迹——合并播放/停止为单按钮，播放中显示选中态
- **完成的主要任务**:
  1. 移除「停止」按钮，`▶`/`⏸` 可切换单按钮（播放中蓝色选中）
  2. AI 唱歌/跟唱播放时同步 transport 选中；跟唱播放中再点 = 停止
  3. AI 唱歌播放中再点 = 暂停/继续
- **修改的文件列表**:
  - app/ui/pages/playback_page.py、app/integration/controller.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-07 (8)

- **会话主要目的**: 新增「混响说话」并按声迹 AI 顺序排列播放栏按钮
- **完成的主要任务**:
  1. 播放栏顺序：▶ → AI跟唱 → AI唱歌 → 混响说话 → 普通说话 → 🔊
  2. 混响说话：直通 + 4 路 comb 延迟混响（`audio.reverb_mix` / `reverb_decay`）
  3. 模式独立：`normal_talk` / `reverb_talk` 互斥切换，UI 选中态同步
- **修改的文件列表**:
  - app/audio/stream_manager.py、app/audio/service.py、app/config_store.py
  - app/integration/controller.py、app/ui/pages/playback_page.py
  - scripts/run_ui_skeleton.py、scripts/test_task7_integration.py、README.md

---

## 会话总结 - 2026-08-07 (9)

- **会话主要目的**: 对标声迹——混响说话与 AI 唱歌可互切，混响模式下保留伴奏
- **完成的主要任务**:
  1. 混响说话播放 `instrumental.wav` + 混响麦（同一条音频流混音）
  2. AI 唱歌 ↔ 混响说话 handoff：播放头同步，互切不停歌
  3. UI：混响与 AI 唱歌按钮可同时可点；transport/进度条在混响伴奏下可用
- **修改的文件列表**:
  - app/audio/stream_manager.py、app/audio/service.py
  - app/integration/controller.py、app/ui/pages/playback_page.py
  - scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-07 (10)

- **会话主要目的**: 修复混响说话 → AI 唱歌切换卡死、两按钮同时变蓝
- **完成的主要任务**:
  1. handoff 时先切 `mode`、`_release_playback_tick` 短超时 join，避免 UI 线程死锁
  2. 混响→唱歌跳过重复 `_stop_playback`；`_ensure_playback_tick` 防止双 tick
  3. UI 互斥：点模式按钮立刻取消另一模式选中
- **修改的文件列表**: app/integration/controller.py、app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-08

- **会话主要目的**: 普通说话与混响说话行为一致，切换模式时伴奏不断
- **完成的主要任务**:
  1. 普通说话始终加载 instrumental（与混响说话相同），不再依赖 playback_running
  2. 普通↔混响、普通→AI唱歌/跟唱 均 handoff 播放头；先取 pos 再停流
  3. 普通说话走 mode-switch 队列；stop_passthrough 对两种 talk 模式统一 tick/时间轴处理
- **修改的文件列表**: app/integration/controller.py、app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-08 (2)

- **会话主要目的**: 修复普通说话→混响说话切换后歌曲从头播放
- **根因**: `_current_song_position()` 仅在 `reverb_talk` 下读伴奏进度，普通说话返回 0
- **修复**: 两种 talk 模式均从 `audio.manager.inst_position` 取播放头
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-08 (3)

- **会话主要目的**: 播放页 5 按钮支持键盘快捷键，映射可配置
- **完成的主要任务**:
  1. 默认快捷键：Space 播放/暂停，1～4 对应跟唱/唱歌/混响/普通说话
  2. 系统设置新增「播放页快捷键」分组，QKeySequenceEdit 可改键或留空禁用
  3. 配置写入 `config/client.json` 的 `shortcuts` 段；保存后立即重载
- **修改的文件列表**: app/ui/playback_shortcuts.py、app/ui/settings_dialog.py、app/ui/main_window.py、app/ui/pages/playback_page.py、app/config_store.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-08 (4)

- **会话主要目的**: 修复打开系统设置后播放停止且关闭后不恢复
- **根因**: `list_devices()` / `list_hostapis()` 调用 `sd._terminate()`，设置页初始化枚举设备时杀掉所有音频流
- **修复**: 去掉枚举时的 PortAudio 重初始化；设置关闭前快照播放状态，若流已断则自动恢复
- **修改的文件列表**: app/audio/devices.py、app/integration/controller.py、app/ui/main_window.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-08 (5)

- **会话主要目的**: 歌曲播完后自动续播，并增加播放模式切换（对标声迹 AI）
- **完成的主要任务**:
  1. 控制条「普通说话」与混音按钮之间新增播放模式按钮，点击循环切换：顺序播放 🔁 / 单曲循环 🔂 / 随机播放 🔀
  2. 配置持久化至 `config/client.json` → `playback.play_mode`
  3. 播完统一走 `_handle_track_end()`：AI 唱歌、AI 跟唱、混响/普通说话（伴奏轨）三种结束路径均支持续播
  4. 单曲循环在 talk 模式下直接 `replay_instrumental()` 重播伴奏；切歌时同步更新歌库选中项
- **关键决策**: AI 跟唱自然结束时通过 mode-switch 队列延迟续播，避免在 follow tick 线程内 stop/start 死锁
- **技术栈**: PyQt6、sounddevice、soundfile、现有 Controller 模式切换队列
- **修改的文件列表**: app/audio/stream_manager.py、app/config_store.py、app/integration/controller.py、app/ui/pages/playback_page.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-08 (6)

- **会话主要目的**: 修复单曲循环时播放头未重置、日志显示「从 05:02 继续」的 bug
- **根因**: 续播传入 `position=0` 时仍被 `_current_song_position()` 覆盖为歌曲末尾；同路径 `load()` 不重置 `_pos`，再 seek 到末尾导致瞬间再次触发结束
- **修复**: 仅当 payload 未显式带 `position` 时才继承当前进度；显式 `position=0` 时 `seek_ratio(0)` 从头播放；AI 跟唱续播同样处理
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-08 (7)

- **会话主要目的**: 播放中点击歌库切换歌曲时，新歌曲应立即开始播放
- **根因**: `_select_song` 仅更新选中项与预加载，未在当前播放模式下重启
- **修复**: 检测到切歌且处于 AI 唱歌/跟唱/混响/普通说话时，调用 `_continue_mode_with_song` 从 0 秒播放新歌；自动切歌路径传 `resume_if_playing=False` 避免重复启动
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-08 (8)

- **会话主要目的**: 修复启动后或切歌/切模式时界面偶发「未响应」
- **根因**: 调度器在 UI 线程同步执行 handler；切歌续播、停止跟唱/直通里的 `join`/`sleep` 阻塞主线程；启动时同步选歌与波形 `wait(200)` 进一步卡住界面
- **修复**:
  1. `_continue_mode_with_song` 统一走 mode-switch 后台队列（`_continue_mode_with_song_impl`）
  2. 启动页关闭前后台扫描歌库并 `processEvents`；首曲选择延后到 `QTimer.singleShot(0)`
  3. 波形加载取消 UI 线程 `wait(200)`；刷新歌库改为后台线程
- **修改的文件列表**: app/integration/controller.py、app/ui/pages/playback_page.py、app/ui/waveform_widget.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-08 (9)

- **会话主要目的**: 修复切换歌曲后歌词未刷新、无歌词歌曲仍显示上一首歌词
- **根因**: 无 LRC 时未清空 `LyricsService` 与 UI；UI 层 `lyrics_loaded` 在 `lines` 为空时不更新
- **修复**: 新增 `LyricsService.clear()`；切歌时无歌词发布 `lyrics_loaded lines=[]`；有歌词且切歌时强制刷新 UI
- **修改的文件列表**: app/lyrics/service.py、app/integration/controller.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-08 (10)

- **会话主要目的**: 无歌词歌曲的歌词区显示「暂无歌词」而非横线
- **修改的文件列表**: app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-08 (11)

- **会话主要目的**: 非播放状态下点击模式按钮不要自动开始播放
- **修复**: 新增 `_is_timeline_playing()` / `autoplay` 标志；暂停/停止时切模式仅切换就绪，按 ▶ 才开始；切歌续播仍仅在播放中触发
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-08 (12)

- **会话主要目的**: 模式按钮仅负责选中，播放/暂停统一由左侧 ▶ 控制；播放中切模式不中断
- **完成的主要任务**:
  1. 四模式按钮改为纯选中（QButtonGroup），不再启停音频
  2. 新增 `playback_transport` / `_select_mode`：▶ 开始/暂停/继续，`selected_mode` 持久化
  3. 播放中切换模式自动 handoff 并保持播放；暂停时切换仅换模式不自动播
  4. 停止播放后保留模式按钮选中态，不再全部置灰为 idle
- **修改的文件列表**: app/integration/controller.py、app/integration/state.py、app/ui/pages/playback_page.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-08 (13)

- **会话主要目的**: AI 跟唱改为声迹 Phase 1 方案（预渲染 AI 人声 + VAD 门控），并更新开发大纲
- **完成的主要任务**:
  1. 重写 `PitchFollowService`：输出 = 伴奏 + converted_vocal(按 T) × VAD门控 × AI人声音量；麦仅作 RMS 开关
  2. 移除热路径 F0 加载/修音/detune；保留 `f0_curve`/`corrector`/`detune` 供 Phase 2
  3. 🔊 混音面板文案对齐 VAD（AI人声音量/跟唱阈值/衰减）；移除跑调模式 UI
  4. 更新 `开发大纲.md`：任务 9 拆 Phase 1（VAD）与 Phase 2（可选修音）
- **关键决策**: Phase 1 对标声迹当前听感路径；条件允许再通过 `follow_engine=pitch_correct` 集成原修音引擎
- **技术栈**: sounddevice duplex、RingBuffer、librosa/soundfile 按 T 读轨、RMS VAD + hangover
- **修改的文件列表**: app/pitchfix/service.py、app/integration/controller.py、app/ui/ai_follow_mix_panel.py、app/ui/pages/playback_page.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-08 (14)

- **会话主要目的**: 跟唱衰减上限改为 0.2；修复耳麦电平偏低时 VAD 不触发
- **完成的主要任务**:
  1. 跟唱衰减滑条改为 0.10~0.20（步进 0.01），修复旧映射最大到 10.0 的 bug
  2. VAD 阈值系数 0.03→0.002，并叠加 peak×0.35 检测，降低触发门槛
  3. 阈值 tooltip 提示耳麦电平低时可调到 30~50
- **修改的文件列表**: app/pitchfix/service.py、app/ui/ai_follow_mix_panel.py、README.md

---

## 会话总结 - 2026-08-08 (15)

- **会话主要目的**: 降低 VAD 对喘气/气声的误触发
- **修复**: 改回 RMS 检测（去掉峰值）；阈值系数 0.002→0.006；连续 2 个音频块超阈才开门控
- **修改的文件列表**: app/pitchfix/service.py、app/ui/ai_follow_mix_panel.py、README.md

---

## 会话总结 - 2026-08-08 (16)

- **会话主要目的**: 修复跟唱过程中 AI 人声偶发停顿
- **根因**: 字间电平回落触发关门；衰减 0.10 时释放仅 ~0.15s；重开需 2 块造成断句
- **修复**: 开/关双阈值（关阈=开阈×0.35）；释放 max(0.25s, 衰减×2.5)；grace 内 1 块即可重开
- **修改的文件列表**: app/pitchfix/service.py、app/ui/ai_follow_mix_panel.py、README.md

---

---

## 会话总结 - 2026-08-09

- **会话主要目的**: 排查 AI 跟唱启动失败，并修复播完时 callback 崩溃
- **完成的主要任务**:
  1. 定位 PortAudio -9993/-9997 为本地设备组合与采样率不一致（VoiceMeeter/Windows 共享格式）
  2. 修复 _playback_chunks：人声轨短于伴奏时按 ef_got 切片，避免结尾 ValueError
- **关键决策**: 推荐全链路统一 48000；人声不足部分保持静音填充
- **技术栈**: sounddevice duplex、NumPy 切片、VoiceMeeter WASAPI
- **修改的文件列表**: app/pitchfix/service.py、README.md
