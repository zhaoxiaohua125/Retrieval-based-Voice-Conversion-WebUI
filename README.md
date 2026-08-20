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

## 会话总结 - 2026-08-09 (1)

- **会话主要目的**: 修复 AI 跟唱运行一段时间后 callback 广播 shape 报错
- **根因**: `converted_vocal` 比 `instrumental` 短，播放到末尾时 `ref[:got]` 与切片长度不一致
- **修复**: 加载时对齐两轨长度（短则补零、长则截断）；`_playback_chunks` 按实际 `ref_got` 写入
- **修改的文件列表**: app/pitchfix/service.py、README.md

---

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
  2. 修复 _playback_chunks：人声轨短于伴奏时按 
ef_got 切片，避免结尾 ValueError
- **关键决策**: 推荐全链路统一 48000；人声不足部分保持静音填充
- **技术栈**: sounddevice duplex、NumPy 切片、VoiceMeeter WASAPI
- **修改的文件列表**: app/pitchfix/service.py、README.md

---

## 会话总结 - 2026-08-09 (2)

- **会话主要目的**: 按开发大纲分段任务 8 落地 Enhanced LRC / 逐字歌词
- **完成的主要任务**:
  1. 新增 enhanced_lrc / ligner / 
ewrite；扩展 LyricWord 与字级 matcher
  2. 加载行级 LRC 时内存均分字时间轴；「生成逐字」写回 Enhanced LRC；离线做歌复制 LRC 后自动增强
  3. 播放页与悬浮窗逐字高亮；右栏改词保存；验收脚本 scripts/test_task8_lyrics_enhanced.py
- **关键决策**: 主路径为均分字轴（无需网上找 Enhanced LRC）；Whisper 为可选 use_whisper
- **技术栈**: Enhanced LRC、PyQt6 RichText、faster-whisper（可选）
- **修改的文件列表**: app/lyrics/*、app/ui/lyrics_window.py、app/ui/pages/playback_page.py、app/integration/controller.py、scripts/test_task8_lyrics_enhanced.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-09 (3)

- **会话主要目的**: 修复逐字高亮相对歌曲进度滞后
- **完成的主要任务**:
  1. 字轴压缩到行前约 58%（避免句尾空白拖慢）
  2. 加载时自动刷新旧「全行均分」字轴；播放/跟唱 tick 改为 50ms
  3. 增加 lyrics.lead_ms 默认 150ms 提前量
- **修改的文件列表**: app/lyrics/aligner.py、service.py、__init__.py、app/integration/controller.py、app/config_store.py、config/client.json、README.md

---

## 会话总结 - 2026-08-09 (4)

- **会话主要目的**: 修正逐字高亮过快（抢在歌声前）
- **完成的主要任务**: 字轴压缩比 0.58→0.78；默认 lead_ms 改为 0；自动重算过度压缩的旧字轴
- **修改的文件列表**: app/lyrics/aligner.py、service.py、app/config_store.py、config/client.json、README.md

---

## 会话总结 - 2026-08-09 (5)

- **会话主要目的**: 解决逐字高亮时准时不准（均分字轴不稳定）
- **完成的主要任务**: 改用人声能量在行内分配字时间；选歌/生成逐字自动用 converted_vocal 等干声轨；无音频时回退均分
- **关键决策**: 不以固定 sing_ratio/lead 硬调；对齐跟歌声能量走
- **修改的文件列表**: app/lyrics/aligner.py、service.py、__init__.py、app/integration/controller.py、app/ui/pages/playback_page.py、scripts/test_task8_lyrics_enhanced.py、README.md

---

## 会话总结 - 2026-08-09 (6)

- **会话主要目的**: 修复 AI 跟唱时逐字歌词偶发严重滞后
- **完成的主要任务**:
  1. pitchfix 播放头改为墙钟外推 + PortAudio 输出延迟补偿（不再卡在整块末尾）
  2. 跟唱 block_ms 200→100；歌词 tick 30ms
- **修改的文件列表**: app/pitchfix/service.py、app/integration/controller.py、config/client.json、README.md

---

## 会话总结 - 2026-08-09 (7)

- **会话主要目的**: 修复 AI 跟唱歌词卡在某一字不走
- **完成的主要任务**:
  1. 播放头外推不再死顶在已写样本末尾（回调抖动时不再卡进度/歌词）
  2. 过滤异常 output latency；有声区间内改时间均分 + 单字最长 1.25s
- **修改的文件列表**: app/pitchfix/service.py、app/lyrics/aligner.py、README.md

---

## 会话总结 - 2026-08-09 (8)

- **会话主要目的**: 澄清歌词问题不限 AI 跟唱；给 AI 唱歌 WavPlayer 同步平滑播放头
- **完成的主要任务**: WavPlayer 墙钟外推 + latency 过滤；播放 tick 30ms；暂停/seek 重置时钟
- **关键说明**: 跟唱音频是 pitchfix 双工，唱歌是 WavPlayer；歌词 matcher 共用，两边播放头都需平滑
- **修改的文件列表**: app/playback/player.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-09 (9)

- **会话主要目的**: 修复「空凝眸…」处逐字卡住（AI 唱歌/跟唱共用歌词）
- **根因**: 句间 LRC 空白过大时字轴被拉长，单字停留数秒像卡死
- **修复**: 按字数压缩演唱窗（约 0.4s/字）；唱完整句高亮收束；到达即切字
- **修改的文件列表**: app/lyrics/aligner.py、matcher.py、types.py、scripts/test_task8_lyrics_enhanced.py、README.md

---

## 会话总结 - 2026-08-09 (10)

- **会话主要目的**: 字高亮略快于歌声，放慢字轴
- **完成的主要任务**: 每字时长 0.40→0.52s；默认 lead_ms=-80 略延后高亮
- **修改的文件列表**: app/lyrics/aligner.py、app/config_store.py、config/client.json、scripts/test_task8_lyrics_enhanced.py、README.md

---

## 会话总结 - 2026-08-09 (11)

- **会话主要目的**: 实现第 4 档 faster-whisper 字级歌词对齐
- **完成的主要任务**:
  1. lign_with_whisper：ASR 词片拆字 + SequenceMatcher 映射到 LRC 行文本并写 Enhanced LRC
  2. 「生成逐字」默认 Whisper、后台线程、失败回退能量/均分；加载时保留文件内字轴
  3. 安装 faster-whisper；requirements 增加依赖；配置 lyrics.whisper_model=small
- **修改的文件列表**: app/lyrics/aligner.py、service.py、__init__.py、app/integration/controller.py、app/ui/pages/playback_page.py、app/config_store.py、config/client.json、requirments_*.txt、scripts/test_task8_lyrics_enhanced.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-09 (12)

- **会话主要目的**: 排查 Whisper 与能量对齐效果差不多的原因并修复
- **根因**: HuggingFace 模型下载失败 / CUDA cuBLAS 失败后静默回退能量，UI 仍显示 Whisper
- **修复**:
  1. 默认 HF_ENDPOINT=hf-mirror.com；模型已下载 small
  2. CUDA 失败自动 CPU 重试；回报真实 mode（whisper/energy）
  3. ASR 文本不准时改用 Whisper 时间轴加权铺字
- **修改的文件列表**: app/lyrics/aligner.py、app/runtime_env.py、app/integration/controller.py、app/config_store.py、scripts/test_task8_lyrics_enhanced.py、README.md

---

## 会话总结 - 2026-08-09 (13)

- **会话主要目的**: 增加歌词对齐引擎配置，默认人声能量，可选 Whisper
- **完成的主要任务**: 新增 lyrics.align_engine（energy/whisper）；生成逐字读取该配置；按钮 tooltip 说明
- **修改的文件列表**: config/client.json、app/config_store.py、app/integration/controller.py、app/ui/pages/playback_page.py、README.md

---

## �Ự�ܽ� - 2026-08-09 (14)

- **�Ự��ҪĿ��**: �Ų� small Whisper �� energy Ч����ͬ��ԭ���޸�
- **��ɵ���Ҫ����**:
  1. ���� config ��д align_engine=whispera��δ���� Whisper ʵ���� energy������ whisper* ǰ׺
  2. �޸�����հ�ʱ Whisper �����̽�������������ĩ���ϵ���ʮ�룻Ӳ�ض� + ������϶�о� + ����ʱ������
  3. client.json ��Ϊ align_engine=whisper ���ڸ���
- **�ؼ�����**: ��������Լ max(6s, ����*0.85)������>0.75s �о䣻��ʱ���ⶥ 1.8s
- **����ջ**: Python��faster-whisper��Enhanced LRC
- **�޸ĵ��ļ��б�**: app/lyrics/aligner.py��app/integration/controller.py��config/client.json��README.md

---

## �Ự�ܽ� - 2026-08-09 (15)

- **�Ự��ҪĿ��**: �Ų顸��������ÿ������������ģ�͡����������
- **����**: ģ������ HF ���ػ��棻ÿ�� auto �ȼ��� CUDA��cuBLAS ʧ�ܡ���ա��ټ��� CPU���������׸��� ASR��Լ 20s����UI ����ʾ���״λ����ء�
- **��ɵ���Ҫ����**:
  1. �����ñ��� snapshot + local_files_only�����ⷴ������ Hub
  2. ��ס CUDA ʧ�ܣ������̲������ԣ�Ĭ�� whisper_device=cpu
  3. ͬ�� ASR ����ڴ滺�棻���������İ�
- **����ջ**: faster-whisper��HuggingFace Hub ���ػ���
- **�޸ĵ��ļ��б�**: app/lyrics/aligner.py��app/integration/controller.py��app/config_store.py��config/client.json��README.md

---

## �Ự�ܽ� - 2026-08-09 (16)

- **�Ự��ҪĿ��**: �޸��������������ָ������ù��죨energy/whisper ���У�
- **����**:
  1. Whisper �����д����ݣ��ּ��������Լ 0.1s
  2. Enhanced LRC ֻ������㣬ĩ�� end ����������һ����㣨���ϵ���ʮ�룩
  3. ����հ�ѹ�����ͣ�0.52s/�֣�������ƫ��
- **��ɵ���Ҫ����**: �ſ���/���٣�normalize �޸�������ĩ����β������ʱ�Զ�У��������д��ǰ��ͥѩ LRC
- **����ջ**: Enhanced LRC��energy/Whisper ����
- **�޸ĵ��ļ��б�**: app/lyrics/aligner.py��enhanced_lrc.py��service.py��scripts/test_task8_lyrics_enhanced.py��opt/...lrc��README.md

---

## �Ự�ܽ� - 2026-08-09 (17)

- **�Ự��ҪĿ��**: ��������״̬������ʾ�������������֡����������� whisper��
- **����**: ѡ������İ�д�������豾������ Whisper��ֻ�����ļ������ energy��
- **��ɵ���Ҫ����**: �� align_mode/��Դ��ʾ�İ���LRC д�� [al:whisper|energy|even]������ Whisper ����ǰ�� Whisper ʱ��ʾ�㡸�������֡�
- **�޸ĵ��ļ��б�**: app/lyrics/types.py��enhanced_lrc.py��aligner.py��service.py��app/integration/controller.py��app/ui/pages/playback_page.py��README.md

---

## �Ự�ܽ� - 2026-08-09 (18)

- **�Ự��ҪĿ��**: ���͸Ļ� energy ���������ʾ Whisper ��ԭ�򲢸��İ�
- **�ؼ�˵��**: ״̬�������� LRC �� [al:whisper] ʵ�����ᣬ���� align_engine�����������ٵ㡸�������֡���д�ļ�
- **�޸ĵ��ļ��б�**: app/lyrics/aligner.py��app/integration/controller.py��README.md

---

## �Ự�ܽ� - 2026-08-09 (19)

- **�Ự��ҪĿ��**: �����ָ�ʹؼ���������ϵͳ���� UI����������˵��
- **��ɵ���Ҫ����**: ���������ָ�ʡ����飺�������� / Whisper ģ�� / Whisper �豸 / ������ǰ / ����ƫ�ƣ�����д�� client.json������������ٵ��������ֵ���ʾ
- **�޸ĵ��ļ��б�**: app/ui/settings_dialog.py��app/integration/controller.py��app/ui/pages/playback_page.py��README.md
## 会话总结 - 2026-08-10

- **会话主要目的**: 评估播放页「保存改词」功能是否有用
- **完成的主要任务**: 梳理 UI → lyrics_rewrite → save_rewrite → 写回 LRC 的完整链路，并给出使用边界结论
- **关键结论**: 有用，定位为单行纠错（保留行时间轴、重映射字时间）；不替代整体偏移/重新生成逐字
- **技术栈**: PySide UI、Enhanced LRC、lyrics.rewrite
- **修改的文件列表**: README.md（仅追加本总结）

---

## 会话总结 - 2026-08-10 (2)

- **会话主要目的**: 歌库切歌改为双击，并增加切换中提示防重复点击
- **完成的主要任务**:
  1. 歌库单击仅高亮，双击才切换歌曲
  2. 切换中禁用列表/搜索/刷新，标题显示「切换中：歌名…」
  3. 预加载或 mode-switch 完成后 `song_switched` 解除锁定
- **修改的文件列表**: app/ui/pages/playback_page.py、app/integration/controller.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-10 (3)

- **会话主要目的**: 制作歌曲页音高滑条增加 -12/+12 说明（对标声迹）
- **修改**: 标题改为「音高调整(半音):(男转女 +12, 女转男 -12)」；滑条两端标注 -12 / +12；范围改为 -12~12
- **修改的文件列表**: app/ui/pages/song_make_page.py、README.md


---

## 会话总结 - 2026-08-10 (3)

- **会话主要目的**: 对比声迹AI旧版安装目录与新授权版安装目录差异
- **完成的主要任务**:
  1. 对比 F:\zxh\ProgramFiles\SoundTrail (5.1.5) 与 D:\Program Files\SoundTrail2\SoundTrail (5.2.7.4)
  2. 确认新版已内置 msst-reflow（约 9.8GB）及完整 AI 引擎/模型
  3. 梳理壳程序新增依赖（ffmpeg/winrt/opencc 等）与代理分发配置
- **关键决策与解决方案**: 以只读目录对比为主，不涉及授权破解
- **使用的技术栈**: PowerShell 目录/版本信息对比、配置 JSON 读取、二进制关键字检索
- **修改的文件列表**: README.md（仅追加本总结）

---

## 会话总结 - 2026-08-10 (4)

- **会话主要目的**: 制作页 RVC 模型旁「导入…」改为「刷新」
- **修改**: 刷新重扫 assets/weights；导入保留在高级参数设置；更新无模型提示文案
- **修改的文件列表**: app/ui/pages/song_make_page.py、README.md

---

## 会话总结 - 2026-08-10 (6)

- **会话主要目的**: 暂时关闭做歌末尾 F0 `.npz` 生成（加速做歌）
- **原因**: AI 跟唱 Phase 1 为 VAD 门控，不依赖参考旋律缓存
- **修改**: 注释 `offline_pipeline.py` 中「正在生成 AI 跟唱参考旋律…」整段；Phase 2 修音可取消注释恢复
- **修改的文件列表**: app/rvc/offline_pipeline.py、README.md


- **会话主要目的**: 去掉制作页「未匹配 Index」灰色提示
- **修改**: 无 Index 时不显示说明；已匹配时仍显示绿色提示
- **修改的文件列表**: app/ui/pages/song_make_page.py、README.md

---

## 会话总结 - 2026-08-10 (7)

- **会话主要目的**: 歌库右键删除歌曲及本地关联文件
- **完成的主要任务**:
  1. 歌库列表右键「删除歌曲」，二次确认
  2. 删除 cover/converted_vocal/instrumental/vocals/harmony/lrc/f0.npz 等关联文件
  3. 若删当前播放项则停播并刷新歌库
- **修改的文件列表**: app/playback/library.py、app/integration/controller.py、app/ui/pages/playback_page.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-10 (8)

- **会话主要目的**: 修复打包后双击「启动来取文化.bat」闪退（splash 消失、主界面不出现）
- **完成的主要任务**:
  1. `StartClient.bat` 由 `start /B pythonw` 改为 `start /wait`，失败时 pause 并提示查看 `logs/client/startup.log`
  2. `run_ui_skeleton.py` 增加分阶段 startup 日志、启动异常 QMessageBox、打包目录 Qt 插件/DLL 路径补齐
  3. 主窗口 `show()` 后 `raise_`/`activateWindow` 确保前台显示
- **关键决策**: 原后台 detached 启动导致 pythonw 崩溃无可见错误；先让失败可观测再定位根因
- **使用的技术栈**: PyQt6、CondaPack 打包、bat 启动器
- **修改的文件列表**: scripts/run_ui_skeleton.py、scripts/build_client_package.py、README.md

---

## 会话总结 - 2026-08-10 (9)

- **会话主要目的**: 继续修复打包启动闪退（日志停在 `main window created`）
- **根因分析**: 启动卡在主窗口 show 之前；可能原因包括托盘无图标、splash 关闭触发 `quitOnLastWindowClosed`、窗口几何在屏幕外
- **完成的主要任务**:
  1. `setQuitOnLastWindowClosed(False)`，先 show 主窗口再关 splash、再创建托盘
  2. 内嵌 fallback 托盘/窗口图标（Windows 托盘必须有 icon）
  3. 恢复几何时检测并拉回屏幕内
  4. 分步 startup.log（hooks ready / ui wired / main window shown / tray ready）并 flush
  5. 启动阶段 `apply_library(auto_select=False)` 避免 show 前触发切歌
- **修改的文件列表**: scripts/run_ui_skeleton.py、app/ui/tray.py、app/ui/main_window.py、app/ui/pages/playback_page.py、scripts/build_client_package.py、README.md

---

## 会话总结 - 2026-08-10 (10)

- **会话主要目的**: 修复「StartClient_Debug.bat 正常、启动来取文化.bat 不行」
- **根因**: `StartClient.bat` 优先用 `pythonw.exe`（无控制台，`sys.stderr is None`）；Qt 日志过滤器与 logging 仍写 stderr，触发异常导致进程退出；Debug 用 `python.exe` 故正常
- **完成的主要任务**:
  1. 启动最早 `_ensure_stdio()`，pythonw 下重定向到 `logs/client/stderr.log`
  2. Qt 日志 handler 写 stderr 前判空
  3. `rotating_log` 在 stderr 为空时不挂控制台 Handler
  4. 统一 StartClient 启动变量 `LAUNCH`（pythonw 优先，逻辑与 Debug 一致）
- **修改的文件列表**: scripts/run_ui_skeleton.py、app/ops/rotating_log.py、scripts/build_client_package.py、README.md

---

## 会话总结 - 2026-08-10 (11)

- **会话主要目的**: 消除正常启动后 CMD 黑窗口一直驻留
- **根因**: `StartClient.bat` 使用 `start /wait`，bat 会阻塞到客户端退出才关闭控制台
- **完成的主要任务**: 改为 `pythonw` + `start` 不等待、立即 `exit`；「启动来取文化.bat」直接 detached 启动 pythonw
- **修改的文件列表**: scripts/build_client_package.py、README.md

---

## 会话总结 - 2026-08-11

- **会话主要目的**: 设置弹窗改为侧栏 Tab 壳，并新增「播放设置」页收纳现有可配置项
- **完成的主要任务**:
  1. `SettingsDialog` 重构为左侧导航 + `QStackedWidget`（音频与路由 / 播放设置 / 歌词 / 常规 / 快捷键）
  2. 「播放设置」：歌库播放模式、普通说话音量、混响湿度/衰减、AI 跟唱默认混音五项、RVC 高级入口
  3. 「音频与路由」保留设备/采样率/试麦；OSC 端口迁至「歌词」；快捷键独立 Tab
  4. `controller._save_settings` 支持 `playback.play_mode`、`pitchfix.*`、`audio.reverb_*` 持久化并同步运行中服务
- **修改的文件列表**: app/ui/settings_dialog.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-11 (2)

- **会话主要目的**: 增加「智能切模式」开关与自动前奏/间奏切混响说话
- **完成的主要任务**:
  1. 设置 → 播放设置：勾选「智能切模式」+ 间奏判定秒数（默认 3s）
  2. `is_vocal_region()` 按 LRC 行轴判定唱段 vs 前奏/长间奏/尾奏
  3. 播放中若已选 AI 唱歌/跟唱且有歌词：非唱段自动切混响说话，唱段回到所选模式
  4. 手动点混响/普通说话后本首不再自动切；切歌重置
- **配置项**: `playback.smart_switch`、`playback.smart_switch_min_gap_sec`
- **修改的文件列表**: app/lyrics/matcher.py、app/config_store.py、app/ui/settings_dialog.py、app/integration/controller.py、scripts/test_smart_switch.py、README.md

---

## 会话总结 - 2026-08-11 (3)

- **会话主要目的**: 修复智能切模式无效果
- **根因**: LRC 解析把每行 `end_sec` 设为下一句 `start`，旧逻辑把整段间奏都算进唱段，`is_vocal_region` 恒为 True
- **修复**: 用 `_line_sing_end()` 估算实际句末（逐字取最后一字 / 行级按字数估时长），再判长间奏；切换条件改为 `_is_timeline_playing()`；写 client.log 切换日志
- **修改的文件列表**: app/lyrics/matcher.py、app/integration/controller.py、scripts/test_smart_switch.py、README.md

---

## 会话总结 - 2026-08-11 (4)

- **会话主要目的**: 波形 UI 对标声迹（伴奏段平直虚线），说明智能切应基于人声音轨能量而非歌词
- **完成的主要任务**:
  1. 波形优先加载 `vocal_path`（converted_vocal）分析人声能量
  2. 低能量区画水平虚线，高能量区画竖条；播放头处显示「伴奏段」
  3. 底部已播放进度条 + 工具提示说明
- **未改**: 智能切仍用 LRC 句轴（后续可改为人声 peaks 阈值，与波形同源）
- **修改的文件列表**: app/ui/waveform_widget.py、app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-11

- **会话主要目的**: 对比 `打包演示客户端.bat` 与 `build_demo_package.bat` 打出的包是否相同
- **完成的主要任务**: 核对两个 bat 及其调用的 `build_demo_package_menu.bat` / `build_client_package.ps1` 参数差异
- **关键决策与结论**:
  1. 不相同：前者直打 cu118 全量包；后者进入菜单可选 cu118/cu128
  2. 菜单选 [1] 时 CUDA/环境与前者同为 cu118 + rvc312，但版本目录名为 `0.1.0-demo-cu118`（前者为 `0.1.0-demo`）
  3. 前者传了已失效的 `-Zip`（当前 ps1 无该参数，且提示手动 zip）；后者明确不自动 zip
- **使用的技术栈**: Windows bat、PowerShell、conda-pack
- **修改的文件列表**: README.md（仅追加会话总结）

---

## 会话总结 - 2026-08-11 (5)

- **会话主要目的**: 智能切改按 converted_vocal 人声能量，不再依赖 LRC
- **完成的主要任务**:
  1. 抽出 `silence_threshold` / `is_vocal_energy_region`（与波形虚线同源）
  2. 选歌后台加载 vocal peaks；智能切去掉 `loaded_lyrics` 限制
  3. 「静音保持」秒数作连续无人声防抖后再切混响
  4. 设置文案更新为无需歌词
- **修改的文件列表**: app/ui/waveform_widget.py、app/integration/controller.py、app/ui/settings_dialog.py、scripts/test_smart_switch.py、README.md

---

## 会话总结 - 2026-08-11 (6)

- **修复**: 去掉波形播放头旁「伴奏段」文字，仅保留虚线/竖条视觉
- **修改的文件列表**: app/ui/waveform_widget.py、README.md

---

## 会话总结 - 2026-08-11 (7)

- **会话主要目的**: 消除四模式切换时的 stop→start 停顿，尤其混响说话 ↔ 普通说话
- **完成的主要任务**:
  1. `AudioService.start_stream` 流已运行时原地更新混响/增益/伴奏，不再因 reverb 变化重建流
  2. `AudioStreamManager` 记录 `_inst_path`，同曲仅 seek、不重载 WAV
  3. `_start_talk` 说话模式互切走热路径，不 stop 音频流、不重启 tick
  4. handoff 路径 sleep 从 0.15~0.25s 降至 0.03~0.05s；智能切/续播不再先 stop 再 start 说话
- **关键决策**: 混响↔普通仅改回调参数；跨引擎（AI 唱歌/跟唱 ↔ 说话）仍须释放旧源，但缩短等待
- **技术栈**: Python、sounddevice、AudioStreamManager、AppController
- **修改的文件列表**: app/audio/service.py、app/audio/stream_manager.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-11 (7)

- **会话主要目的**: 消除四模式切换时的 stop→start 停顿，尤其混响说话 ↔ 普通说话
- **完成的主要任务**:
  1. `AudioService.start_stream` 流已运行时原地更新混响/增益/伴奏，不再因 reverb 变化重建流
  2. `AudioStreamManager` 记录 `_inst_path`，同曲仅 seek、不重载 WAV
  3. `_start_talk` 说话模式互切走热路径，不 stop 音频流、不重启 tick
  4. handoff 路径 sleep 从 0.15~0.25s 降至 0.03~0.05s；智能切/续播不再先 stop 再 start 说话
- **关键决策**: 混响↔普通仅改回调参数；跨引擎（AI 唱歌/跟唱 ↔ 说话）仍须释放旧源，但缩短等待
- **技术栈**: Python、sounddevice、AudioStreamManager、AppController
- **修改的文件列表**: app/audio/service.py、app/audio/stream_manager.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-11 (8)

- **会话主要目的**: 四模式（AI 唱歌 / AI 跟唱 / 混响说话 / 普通说话）切换与混响↔普通一样无缝
- **完成的主要任务**:
  1. **单流架构**：`AudioStreamManager` 以 `instrumental.wav` 为唯一时间轴，回调内按 `playback_mode` 混音
  2. **AI 唱歌** 改为伴奏 + `converted_vocal` 分轨（切换不再重启 WavPlayer）
  3. **AI 跟唱** VAD 迁入 stream manager，不再独占第二条 sounddevice 流
  4. `switch_playback_mode` + `_switch_unified_playback`：四模式互切只热更新，不 stop_stream
  5. tick / 暂停 / seek / 智能切 / 混音设置统一走 manager
- **关键决策**: 有 inst+vocal 走单流；仅 cover 无分轨时仍 fallback WavPlayer
- **修改的文件列表**: app/audio/stream_manager.py、app/audio/service.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-11 (9)

- **会话主要目的**: 修复智能切模式下切换混乱
- **完成的主要任务**:
  1. 智能切走 `_switch_unified_playback(quiet=True)`，不再发 `passthrough_started`/`playback_started` 导致 UI 按钮乱跳
  2. 新增 `smart_switch_tick`：只更新进度/波形，不改变选中模式按钮
  3. 状态机拆分：智能混响中只判切回唱段；唱段中只判切混响
  4. 切回唱段增加 vocal 防抖（约为「静音保持」的 25%，最少 0.35s）
  5. 手动选模式 / 开关智能切时重置 `_smart_reverb_active` 与累计器
- **修改的文件列表**: app/integration/controller.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-11 (10)

- **问题**: 设置里点保存出现双声，像又播放一遍
- **根因**: 关闭设置弹窗后 `restore_playback_after_settings` 在单流仍在播时，又启动了 WavPlayer / PitchFollow 第二条流
- **修复**: 单流活跃时只热更新混音参数，不再 restore 重建播放；`_save_settings` 同步 pitchfix 混音到 manager
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-11 (11)

- **问题**: 智能切开启后伴奏段实际已是混响说话，但按钮仍高亮 AI 唱歌
- **修复**: `smart_switch_tick` 携带 `overlay_mode`，UI 同步更新按钮选中态（伴奏→混响说话，唱段→AI 唱歌/跟唱）
- **修改的文件列表**: scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-11 (12)

- **问题**: 混响/普通说话模式下歌曲播完重播，歌词仍停在末尾
- **根因**: 单曲循环 `return True` 导致 playback tick 退出；`set_lyric_tick` 在 index=-1 时不刷新 UI
- **修复**: 原地循环 `return False` 保持 tick；`lyrics.reset_sync(0)`；开头位置重置歌词 UI
- **修改的文件列表**: app/integration/controller.py、app/lyrics/service.py、app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-11 (13)

- **会话目的**: 继续打磨智能切与波形，让判定逻辑与 UI 完全一致，减少短间奏误切
- **主要任务**:
  1. `waveform_peaks` 抽出 `peak_energy_at` / `inst_segment_span_at` / `SILENCE_FLOOR`，智能切与波形共用同一阈值
  2. 智能切仅在伴奏段长度 ≥「静音保持」时才累计，跳过极短间奏
  3. 波形绘制改为 `is_vocal_energy_region` 判定（虚线/竖条与智能切 WYSIWYG）
  4. 智能混响覆盖时 playhead 变琥珀色并显示「智能混响」提示
  5. `playback_tick` 携带 `smart_overlay` 供波形实时同步
- **关键决策**: 控制器加载 peaks 时缓存 `silence_threshold`，避免与波形各自算阈值产生偏差
- **技术栈**: Python、NumPy、soundfile、PyQt6
- **修改的文件列表**: app/playback/waveform_peaks.py、app/integration/controller.py、app/ui/waveform_widget.py、app/ui/pages/playback_page.py、scripts/test_smart_switch.py、README.md

---

## 会话总结 - 2026-08-11 (14)

- **会话目的**: 去掉智能混响时波形上的文字提示，保留琥珀色 playhead
- **修改**: `waveform_widget.py` 移除「智能混响」drawText，playhead 琥珀色 `#d97706` 不变
- **修改的文件列表**: app/ui/waveform_widget.py、README.md

---

## 会话总结 - 2026-08-11 (15)

- **问题**: 智能切从混响切回唱段偏慢约 0.5s
- **修复**:
  1. 切回防抖 `vocal_hold` 从 `min_hold×0.25`（约 0.75s）降至 `min_hold×0.08`（约 0.24s），上限 0.25s
  2. 智能混响态下增加 0.25s 唱段前瞻，人声将起时提前累计
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-11 (16)

- **问题**: 播放中双击歌单切歌，歌词已切换但音频仍播上一首
- **根因**:
  1. `_select_song` 仅用 `_active_playback_mode()`（要求未暂停），暂停/智能混响等态下判定为空，只预加载不重启播放
  2. `_switch_unified_playback` 把 `carry_pos=0` 误当「沿用旧进度」，切歌应从 0 开始
- **修复**:
  1. 新增 `_session_playback_mode()`（含暂停/混响覆盖），切歌时用它决定是否重启当前模式
  2. `carry_pos=None` 才沿用进度，显式传 `0.0` 从头播
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-11 (17)

- **会话目的**: 用户确认当前功能稳定，暂无新问题
- **状态**: 智能切/波形、切回唱段、歌单双击切歌等近期修复经用户验证通过
- **修改的文件列表**: README.md

---

## 会话总结 - 2026-08-11 (18)

- **问题**: AI 跟唱 VAD 门控人声检测偶发「顿一下」
- **根因**: 门控 0/1 硬切；字间静音 hangover 偏短；重开需连续 2 块超阈值
- **修复**:
  1. 门控平滑 `_voice_gate_smooth`（快开慢关，避免瞬断）
  2. hangover 延长至约 0.55s+；关断阈值降低（close_gate×0.22）
  3. 唱段内 1.2s 内重开只需 1 块超阈值
- **修改的文件列表**: app/audio/stream_manager.py、app/pitchfix/service.py、README.md

---

## 会话总结 - 2026-08-11 (19)

- **问题**: 跟唱衰减调到 0.1 后，停麦仍约半秒才关 AI 人声
- **根因**: hangover 固定下限 0.55s，与「衰减」滑条语义脱节
- **修复**:
  1. 区分字间短静音（syllable_hold）与持续无声（stop_hold = 衰减×1.0，0.1→约 0.1s）
  2. 连续 3 块低电平后走 stop_hold，否则走 syllable_hold 防唱段内顿
  3. 门控淡出速率随衰减增大而变慢
- **修改的文件列表**: app/audio/stream_manager.py、app/pitchfix/service.py、README.md

---

## 会话总结 - 2026-08-11 (20)

- **诉求**: 跟唱衰减 0.1 时无人声输入后立即停 AI 人声（最灵敏）
- **实现**:
  1. 抽出 `app/audio/follow_vad.py` 共用 VAD/门控平滑
  2. 衰减 ≤0.105：`mic_rms < close_gate` 即关门控，无 hangover
  3. 衰减 ≤0.105：门控淡出瞬间置 0；更大衰减仍保留 hold + 慢淡出
- **修改的文件列表**: app/audio/follow_vad.py、app/audio/stream_manager.py、app/pitchfix/service.py、README.md

---

## 会话总结 - 2026-08-11 (22)

- **诉求**: 按 Git 提交记录自动生成增量更新 zip，避免手工复制易错
- **实现**: `scripts/make_update_zip.py` — 传入 `--since`（tag/commit）对比 `HEAD`，自动筛选 manifest 内客户端路径，打 zip；可选 `--publish` 发布到 server
- **技术栈**: git diff、packaging/manifest.json 复用 `is_client_release_path`
- **修改的文件列表**: scripts/make_update_zip.py、scripts/build_client_package.py、server/README.md、README.md

---

## 会话总结 - 2026-08-11 (23)

- **诉求**: 「我的歌库」拆成「唱歌 / 伴奏」两个 Tab；伴奏为手动放入 `opt/` 的原始音频
- **实现**:
  1. `scan_accompaniment_library` 扫描 `opt/` 根目录 wav/mp3/flac 等，排除离线做歌产物
  2. 控制器分 `_library_sing` / `_library_inst` 一并刷新下发
  3. 播放页 Tab 切换列表；伴奏禁用 AI 跟唱，支持混响/普通说话及播放器播伴奏
- **修改的文件列表**: app/playback/library.py、app/integration/controller.py、app/ui/pages/playback_page.py、app/playback/__init__.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-11 (24)

- **诉求**: 伴奏 Tab 支持扫描 `opt/` 子文件夹
- **实现**: `scan_accompaniment_library` 改为 `rglob` 递归；跳过 `task4_offline`；子目录内文件标题显示为 `子目录/歌名`
- **修改的文件列表**: app/playback/library.py、README.md

---

## 会话总结 - 2026-08-11 (25)

- **诉求**: 歌库 Tab「伴奏」改名为「原唱」
- **修改**: 播放页 Tab 文案、搜索框占位、刷新日志及 AI 跟唱提示
- **修改的文件列表**: app/ui/pages/playback_page.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-11 (26)

- **问题**: 切到「原唱」Tab 列表为空，需手动刷新
- **根因**: 启动时 `apply_library` 只传唱歌列表，未传 `inst_songs`
- **修复**: 启动与离线做歌完成时一并传入 `controller.library_inst`
- **修改的文件列表**: app/integration/controller.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-11 (21)

- **会话目的**: P0 发布与稳定性 — 完成客户端自动更新完整流程，后台服务与 `app/` 分离
- **完成的主要任务**:
  1. 新增 `server/` 更新服务：`GET /version.json`、静态 releases、日志上报、发布脚本 `tools/publish_release.py`
  2. 客户端 `UpdateClient` + `install_root.relaunch_client`：检查 / 下载（进度）/ MD5 / 解压 / 备份 / 写 VERSION
  3. `UpdatePromptDialog`：发现新版本、立即更新 / 稍后 / 跳过；强制更新模式
  4. 修复 `_check_update` 误把元组当 dict；托盘/设置联动；启动 4s 后 `auto_check`
  5. 烟测脚本 `scripts/test_update_flow.py`
- **关键决策**: 服务端独立 `server/` 目录；客户端逻辑留在 `app/ops/` + `app/ui/update_dialog.py`
- **技术栈**: FastAPI、uvicorn、PyQt6、urllib 下载、zip 增量/全量
- **修改的文件列表**: server/main.py、server/tools/publish_release.py、server/data/version.json、app/ops/install_root.py、app/ops/update_client.py、app/ops/updater.py、app/ui/update_dialog.py、app/integration/controller.py、app/ui/settings_dialog.py、app/config_store.py、scripts/run_ui_skeleton.py、scripts/test_update_flow.py、README.md

---

## 会话总结 - 2026-08-11 (27)

- **诉求**: 崩溃日志自动上报
- **实现**:
  1. `app/ops/crash_reporter.py`：异常退出检测、打包上传、sys/thread excepthook
  2. 启动时若上次未正常退出则补传；退出时写 `.last_exit_clean` 标记
  3. 上报地址默认从 `update.check_url` 推导 `/api/logs/upload`；设置页可开关
- **修改的文件列表**: app/ops/crash_reporter.py、app/ops/log_reporter.py、app/config_store.py、scripts/run_ui_skeleton.py、app/ui/settings_dialog.py、app/integration/controller.py、config/client.json、server/README.md、README.md

---

## 会话总结 - 2026-08-11 (28)

- **诉求**: 打包时仅将 `app/` 编译为 `.pyd`
- **实现**: `scripts/compile_app_pyd.py`；`build_client_package.py --pyd` / `-Pyd`；菜单询问；修复 Cython 不兼容 `del`
- **修改的文件列表**: scripts/compile_app_pyd.py、scripts/build_client_package.py、scripts/build_client_package.ps1、build_demo_package_menu.bat、scripts/verify_client_package.py、packaging/INSTALL_RUNTIME.md、app/lyrics/aligner.py、app/playback/player.py、README.md

---

## 会话总结 - 2026-08-11 (29)

- **诉求**: pyd 打包后设置按钮/制作页按钮无反应；将 `scripts/` 也统一编译为 pyd
- **根因**: Cython 编译 PyQt6 类未开 `binding=True`，信号/槽在 `.pyd` 中失效
- **实现**:
  1. `compile_app_pyd.py` 扩展为编译 `app/` + 打包用 `scripts/`（run_ui_skeleton、list_audio_devices、verify_client_package）
  2. Cython `binding=True`；临时目录改短路径；`nthreads=0` 避免 Windows 多进程编译失败
  3. 保留薄入口 `scripts/_launch_ui.py` 等；bat 启动改为 `_launch_ui.py`
  4. pyd 模式下 `write_launcher` 不再复制 `verify_client_package.py` 源码，避免与 `.pyd` 冲突
- **验证**: 80 个 pyd 模块编译成功；HeaderBar 设置按钮与 tab 信号烟测通过
- **技术栈**: Cython、PyQt6 binding、MSVC Build Tools
- **修改的文件列表**: scripts/compile_app_pyd.py、scripts/build_client_package.py、scripts/_launch_ui.py、scripts/_launch_devices.py、scripts/_launch_verify.py、scripts/__init__.py、packaging/INSTALL_RUNTIME.md、README.md

---

## 会话总结 - 2026-08-11 (30)

- **问题**: pyd 打包后设置按钮仍不弹框、制作页按钮无反应
- **根因**: **`app/ui/` 整包编译为 pyd 时 PyQt6 信号槽会硬崩溃**（SettingsDialog 初始化 segfault；SongMakePage 按钮点击崩溃），与 scripts 是否 pyd 无关
- **修复**: `compile_app_pyd.py` **跳过 `app/ui/`**，编译后复制 UI 源码 `.py`；业务层 `app/` 其余模块 + `scripts/` 仍为 pyd
- **验证**: 新产物下设置弹窗可打开、制作页按钮信号正常
- **修改的文件列表**: scripts/compile_app_pyd.py、scripts/build_client_package.py、packaging/INSTALL_RUNTIME.md、README.md

---

## 会话总结 - 2026-08-12 (31)

- **问题**: 旧包 Debug 启动点「设置」报 `TypeError: _open_settings_dialog() takes exactly 1 positional argument (2 given)`
- **根因**: `QPushButton.clicked` 会传入 `checked` 参数，直接 `connect(self._open_settings_dialog)` 参数不匹配
- **修复**: 改为 `lambda *_: self._open_settings_dialog()`
- **修改的文件列表**: app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-12 (32)

- **问题**: 设置修好后制作页按钮仍报 `TypeError: _pick_files() takes exactly 1 positional argument (2 given)`
- **根因**: 打包内 PyQt6 的 `clicked` 信号会传 `checked`，直接 `connect(self._xxx)` 参数不匹配（全 UI 层同类问题）
- **修复**: 新增 `app/ui/qt_util.clicked()`，统一包装所有按钮 `clicked` 连接
- **说明**: **不必重打包 pyd**，只需把 `app/ui/` 下更新后的 `.py` 复制到 dist 包即可
- **修改的文件列表**: app/ui/qt_util.py、app/ui/main_window.py、app/ui/pages/song_make_page.py、app/ui/pages/playback_page.py、app/ui/pages/announce_page.py、app/ui/settings_dialog.py、app/ui/update_dialog.py、app/ui/ai_follow_mix_panel.py、app/ui/rvc_advanced_dialog.py、README.md

---

## 会话总结 - 2026-08-12 (33)

- **诉求**: `compile_app_pyd.py` 增加「业务层 pyd + ui 层 pyc」自动化
- **实现**: 复制 `app/ui/` 源码后 `compileall -b`，生成 `.pyc` 并删除 `.py`；可选 `--keep-ui-py` 调试
- **验证**: 63 pyd + 18 ui pyc；pyc-only 的 ui 可正常 import
- **修改的文件列表**: scripts/compile_app_pyd.py、scripts/build_client_package.py、packaging/INSTALL_RUNTIME.md、README.md

---

## 会话总结 - 2026-08-12 (34)

- **诉求**: 增加登录页作为首屏，登录成功后进入播放页（暂无鉴权业务）
- **实现**: `LoginPage` + `MainWindow.root_stack`（登录 / 主界面）；登录成功切到 `TAB_PLAYBACK`
- **修改的文件列表**: app/ui/pages/login_page.py、app/ui/pages/__init__.py、app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-12 (35)

- **诉求**: 美化登录页；修复登录后进主界面卡顿/未响应
- **根因**: 启动时在主线程构建全部 Tab + 立即 `select_initial_song` 加载歌词/波形；登录后一次性显示过重
- **实现**:
  1. 登录页渐变背景 + 卡片式表单 + 登录中状态
  2. 主界面懒加载：登录后才 `_ensure_main_shell()`，仅先建播放页
  3. 制作/公告 Tab 首次切换再创建；歌库与选歌延后到 `main_entered` + 120ms
- **修改的文件列表**: app/ui/pages/login_page.py、app/ui/main_window.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-12 (36)

- **诉求**: 去掉蓝色 splash「正在扫描歌库…」，启动后立刻显示登录页；初始化与歌库扫描放后台，登录按钮触发后显示进度
- **实现**:
  1. 删除启动 splash 与阻塞式扫描循环
  2. `window.show()` 后立即显示登录页；后台线程 `_bootstrap_thread` 完成 controller 初始化与歌库扫描
  3. `BootSignals.status/done` 更新登录按钮文案（「正在初始化…」「正在扫描歌库…」）；完成后 `mark_backend_ready()`，若用户已点登录则自动进入播放页
- **修改的文件列表**: scripts/run_ui_skeleton.py、app/ui/pages/login_page.py、README.md

---

## 会话总结 - 2026-08-12 (37)

- **问题**: 点击登录后窗口「未响应」，卡在「正在进入…」
- **根因**: `_ensure_main_shell()` 内同步 `_refresh_gpu_status()` 触发 torch/CUDA 检测阻塞主线程；登录页无进度反馈
- **修复**:
  1. 登录页增加蓝色状态框（来取文化 + 正在扫描歌库…）
  2. 后台 boot 状态同步到登录页；点击登录后分步显示进度并 `processEvents`
  3. GPU 检测、歌词窗/托盘延后到 `QTimer`；`mark_backend_ready()` 提前以便登录不等待托盘
- **修改的文件列表**: app/ui/pages/login_page.py、app/ui/main_window.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-12 (38)

- **诉求**: 登录后进度只在按钮上展示，去掉下方重复的蓝色状态框
- **实现**: 移除 `status_box`，加载态仅更新登录按钮文案；后台扫描进度仍通过底部灰色 hint 显示
- **修改的文件列表**: app/ui/pages/login_page.py、README.md

---

## 会话总结 - 2026-08-12 (39)

- **诉求**: 在 `server/` 增加 MySQL 登录验证（`bus_user` 表），模块化实现，使用成熟连接池
- **实现**:
  1. `config/settings.py` 读取 `config/db.json` 或环境变量（默认 localhost:13306）
  2. `db/engine.py` SQLAlchemy QueuePool + `pool_pre_ping`
  3. `auth/service.py` 校验账号密码（明文/MD5）、有效期、更新 `login_time`
  4. `POST /api/auth/login` API
- **技术栈**: FastAPI、SQLAlchemy 2、PyMySQL
- **修改的文件列表**: server/config/、server/db/、server/auth/、server/main.py、server/requirements.txt、server/README.md、README.md

---

## 会话总结 - 2026-08-12 (39)

- **诉求**: 在 `server/` 增加 MySQL 登录验证（`bus_user` 表），模块化实现，使用成熟连接池
- **实现**:
  1. `config/settings.py` 读取 `config/db.json` 或环境变量（默认 localhost:13306）
  2. `db/engine.py` SQLAlchemy QueuePool + `pool_pre_ping`
  3. `auth/service.py` 校验账号密码（明文/MD5）、有效期、更新 `login_time`
  4. `POST /api/auth/login` API
- **技术栈**: FastAPI、SQLAlchemy 2、PyMySQL
- **修改的文件列表**: server/config/、server/db/、server/auth/、server/main.py、server/requirements.txt、server/README.md、README.md


---

## 会话总结 - 2026-08-12 (40)

- **诉求**: 密码仅支持 MD5；登录页对接 server 登录接口
- **实现**:
  1. `server/auth/service.py` 去掉明文比对，仅校验 32 位 MD5
  2. 新增 `app/ops/auth_client.py`，POST `/api/auth/login`
  3. 登录页 emit `login_requested`；主窗口后台线程请求，成功后再进入主界面
  4. `config/client.json` 增加 `auth.login_url`
- **修改的文件列表**: server/auth/service.py、app/ops/auth_client.py、app/config_store.py、app/ui/pages/login_page.py、app/ui/main_window.py、config/client.json、server/README.md、README.md

---

## 会话总结 - 2026-08-12 (41)

- **问题**: 点击登录后一直等待，无任何错误提示
- **根因**: 后台线程使用 `QTimer.singleShot` 回调 UI，Qt 要求 UI 操作必须在主线程
- **修复**: 使用 `MainWindow._login_result` 信号回到主线程；登录失败红色 hint + 弹窗；连接/超时错误文案更明确
- **修改的文件列表**: app/ui/main_window.py、app/ui/pages/login_page.py、app/ops/auth_client.py、README.md

---

## 会话总结 - 2026-08-12 (42)

- **问题**: 用户自检 MySQL 正常，但登录提示「数据库连接失败」
- **根因**: 只改了 `db.json.example`，server 读 `db.json` 缺失时默认连 `changgebanlv`，实际库名为 `aisound`
- **修复**: 无 `db.json` 时回退读 `db.json.example`；默认库改为 `aisound`；连接失败返回具体 MySQL 错误
- **修改的文件列表**: server/config/settings.py、server/db/engine.py、server/auth/router.py、server/config/db.json.example、server/README.md、README.md

---

## 会话总结 - 2026-08-12 (43)

- **问题**: 「原唱」播放后切到「唱歌」再播放，仍播原唱音频
- **根因**: 切 Tab 时 `resume_if_playing=False` 未释放统一音频流/播放器；单击列表未同步 `selected_song`
- **修复**: Tab 切换 `force_switch`；`library_type` 变化时释放并重载；列表 `currentRowChanged` 同步选曲
- **修改的文件列表**: app/ui/pages/playback_page.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-12 (44)

- **问题**: 原唱/唱歌 Tab 切换卡死；播放按钮仍续播旧歌
- **根因**: 切 Tab 在 UI 线程同步释放播放/加载歌词；暂停态 transport 直接 resume 未校验当前歌曲
- **修复**: 歌库切换后台线程处理并停止旧播放；`_playback_matches_selection` + `_active_playback_song_key`；Tab 切换去重信号并同步模式
- **修改的文件列表**: app/integration/controller.py、app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-12 (45)

- **诉求**: 切换「原唱/唱歌」Tab 不要自动停止当前播放
- **实现**: Tab 仅切换列表视图（不通知控制器）；跨歌库选曲时若正在播放则无缝切歌而非 stop
- **修改的文件列表**: app/ui/pages/playback_page.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-12 (46)

- **诉求**: 原唱 Tab 播放时保持「AI 唱歌」模式，不要自动切到「普通说话」
- **实现**: 移除原唱条目强制 `normal_talk`；跨歌库仅 `ai_follow` 降级为 `ai_sing`
- **修改的文件列表**: app/ui/pages/playback_page.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-12 (47)

- **问题**: 跨歌库切歌后两路声音同时播放；进度条不走
- **根因**: 统一音频流（唱歌 AI）未释放即启动 WavPlayer（原唱）；tick 仍读旧流位置
- **修复**: 切到非 unified 歌曲前先 `_release_playback_source`；`_start_ai_sing_impl` 走播放器路径前停统一流
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-12 (48)

- **问题**: 从「唱歌」切到「原唱」后双击歌曲处于暂停就绪态，需手动点播放；反向切回正常
- **根因**: 跨歌库选曲在释放旧播放源之后才读 `autoplay`，释放后 `_is_timeline_playing()` 为 False；空闲态双击未传自动播放意图
- **修复**: 释放前记录 `was_active`；UI 双击传 `autoplay=True`；`autoplay = was_active or user_autoplay`；单击列表不传 autoplay
- **修改的文件列表**: app/ui/pages/playback_page.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-12 (49)

- **问题**: 原唱 Tab 歌词与播放进度匹配不准
- **根因**: 原唱可能误用同目录 AI 人声/缓存逐字轴对齐；LRC 开头词曲/标题行在前奏阶段抢显示；子目录歌曲 title 带路径影响查找
- **修复**: 原唱仅用 play_path 做能量逐字；加载后强制 refresh；strip_lrc_credits 过滤元数据行；song_lookup_stem 统一取文件名
- **修改的文件列表**: app/playback/library.py、app/lyrics/aligner.py、app/lyrics/service.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-12 (50)

- **诉求**: 保留 LRC 中「歌名 - 歌手」「词：」「曲：」等行，不要过滤
- **处理**: 移除 strip_lrc_credits 及 load_lrc 调用，歌词展示恢复完整 LRC 原文
- **保留**: 原唱 play_path 对齐、song_lookup_stem、跨库 autoplay 等此前修复
- **修改的文件列表**: app/lyrics/aligner.py、app/lyrics/service.py、README.md

---

## 会话总结 - 2026-08-12 (51)

- **结论**: 原唱歌词与进度偏差大，主因是 LRC 与音频不匹配（非程序 bug）；换对词后即可
- **保留**: 原唱 play_path 对齐、完整展示词曲/标题行、Tab 切歌 autoplay 等修复
- **修改的文件列表**: README.md

---

## 会话总结 - 2026-08-12 (52)

- **会话主要目的**: 为 server 提供 Docker Compose 部署（仅 API，MySQL 在宿主机/外机）
- **完成的主要任务**: 新增 Dockerfile、docker-compose.yml、.env.example、.dockerignore；补充 server/README Docker 说明；.gitignore 忽略 .env
- **关键决策与解决方案**: 不内置 MySQL；用 MYSQL_* 环境变量连接外库；挂载 ./data 持久化；宿主机库通过 host.docker.internal + extra_hosts
- **使用的技术栈**: Docker / docker-compose、Python 3.11-slim、FastAPI
- **修改的文件列表**: server/Dockerfile、server/docker-compose.yml、server/.env.example、server/.dockerignore、server/README.md、.gitignore、README.md

---

## 会话总结 - 2026-08-12 (53)

- **诉求**: Server 未部署时给客户发版，可配置是否显示登录页；免登录时显示蓝色启动闪屏并自动进主页
- **实现**: `auth.show_login`（true=登录页，false=闪屏+自动进入）；新增 BootSplashPage；后台扫库完成后自动切主界面
- **修改的文件列表**: config/client.json、app/config_store.py、app/ui/pages/boot_splash_page.py、app/ui/pages/__init__.py、app/ui/main_window.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-12 (54)

- **问题**: 免登录启动闪屏背景未渲染成蓝色，白字叠浅灰底难以辨认
- **修复**: autoFillBackground + 渐变蓝底；QStackedWidget/根控件同步设色；居中标题+状态+进度条+版本号
- **修改的文件列表**: app/ui/pages/boot_splash_page.py、app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-12 (55)

- **问题**: 免登录闪屏蓝色样式写在 root_stack/根控件上，进入主页后整页仍偏蓝
- **修复**: 蓝色仅 BootSplashPage 自绘（WA_StyledBackground）；进入主页时 _clear_boot_chrome 恢复默认 palette
- **修改的文件列表**: app/ui/pages/boot_splash_page.py、app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-12 (56)

- **诉求**: 启动闪屏进度条要有动感，减轻等待感（无需真实进度）
- **实现**: 自绘 _BootProgressBar，QTimer 驱动白色滑块左右循环；显示/隐藏时启停定时器
- **修复**: 子控件 showEvent 未触发导致不动；改 BootSplashPage.showEvent + singleShot 显式 start_anim
- **修改的文件列表**: app/ui/pages/boot_splash_page.py、README.md

---

## 会话总结 - 2026-08-12 (57)

- **问题**: 闪屏进度条仍静止（定时器未启动）
- **修复**: BootSplashPage.showEvent/set_status 显式 start_anim；repaint 强制刷新；略提速滑块
- **修改的文件列表**: app/ui/pages/boot_splash_page.py、README.md

---

## 会话总结 - 2026-08-12 (58)

- **问题**: 进度条看似不动（白轨+白块对比弱，paintEvent 刷新不明显）
- **修复**: 改 QFrame move() 滑块 + 深色底轨；状态文字追加点动画；加载主界面时 processEvents
- **修改的文件列表**: app/ui/pages/boot_splash_page.py、app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-12 (59)

- **问题**: 闪屏进度条一闪后卡在「正在加载播放页」；PlaybackPage 同步构建阻塞主线程
- **修复**: 主框架先切换（占位「正在加载播放页」），QTimer 异步构建 PlaybackPage 再 emit main_entered
- **修改的文件列表**: app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-12 (60)

- **问题**: 启动进入主界面报 NameError: Qt is not defined（_build_main_shell_frame）
- **修复**: main_window.py 补充 `from PyQt6.QtCore import Qt`
- **修改的文件列表**: app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-12 (61)

- **问题**: 启动过渡出现空白「正在加载播放页」中间页（闪屏过早关闭）
- **修复**: 保持蓝色闪屏直至主框架+PlaybackPage 全部建好，再一次切换到完整主界面
- **修改的文件列表**: app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-12 (62)

- **问题**: 保持闪屏至加载完成后，进度条不动（PlaybackPage 构建阻塞主线程）
- **修复**: BootSplashPage.pump() 手动推进滑块；PlaybackPage 构建分段 ui_pump + processEvents
- **修改的文件列表**: app/ui/pages/boot_splash_page.py、app/ui/pages/playback_page.py、app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-12 (63)

- **问题**: AI 唱歌 ↔ AI 跟唱切换报 AttributeError: pitch_follow（属性体误并入 _playback_matches_selection）
- **修复**: 恢复 `@property pitch_follow` 懒加载 PitchFollowService
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-12 (64)

- **诉求**: 离线做歌进行中允许听原唱、播已有 AI 成品（非硬性技术限制）
- **实现**: `_offline_allows_playback` 判断原唱/已有 wav；仅 `_start_ai_sing_impl` 放宽；跟唱/说话/实时仍互斥
- **修改的文件列表**: app/integration/controller.py、README.md


---

## 会话总结 - 2026-08-14

- **会话主要目的**: 音频设备改为自动识别 Voicemeeter，client.json 不再保存易变的设备 index
- **完成的主要任务**:
  1. `devices.py` 新增 `resolve_io_devices` / `device_ref_for_config`，支持 `auto`、设备名、兼容旧数字
  2. 默认与 `client.json` 的 `input_device`/`output_device` 改为 `"auto"`
  3. 设置页下拉增加「自动识别 Voicemeeter」，保存时写名称或 auto
  4. stream / player / pitchfix / controller 启动时按名称解析为当前 index
- **关键决策与解决方案**: 配置层存稳定引用（auto/名称），运行时再解析 sounddevice index；失效数字回退 Voicemeeter 推荐
- **使用的技术栈**: sounddevice、PyQt6、现有 AudioStreamManager
- **修改的文件列表**: app/audio/devices.py、stream_manager.py、service.py、__init__.py、app/config_store.py、config/client.json、app/ui/settings_dialog.py、app/integration/controller.py、app/pitchfix/service.py、scripts/list_audio_devices.py、README.md


---

## 会话总结 - 2026-08-14 (2)

- **会话主要目的**: Potato 下 auto 默认改走 Aux，避开抖音占用的主 VAIO Output
- **完成的主要任务**:
  1. `pick_voicemeeter_defaults` 采集优先 Out B1/Aux Output/VAIO3，播放优先 Aux/VAIO3 Input
  2. 设备角色标记区分 aux / vaio3 / vaio
  3. 设置页与 list_audio_devices 文案同步
- **关键决策与解决方案**: 抖音继续采 VoiceMeeter Output；客户端 auto→Aux，两边无需改抖音配置；VM 需将麦勾到 Aux 相关总线并按需混到直播
- **使用的技术栈**: sounddevice、Voicemeeter Potato
- **修改的文件列表**: app/audio/devices.py、app/ui/settings_dialog.py、scripts/list_audio_devices.py、README.md


---

## 会话总结 - 2026-08-14 (3)

- **会话主要目的**: 将界面品牌文案（来趣文化、唱歌伴侣）外置到 client.json，便于随时修改
- **完成的主要任务**:
  1. config/client.json 与 ConfigStore 默认配置增加 brand.app_name / brand.product_name
  2. 窗口标题、登录页标题、退出确认文案读取 brand.app_name
  3. 顶栏「唱歌伴侣」读取 brand.product_name
- **关键决策与解决方案**: 独立 brand 段，避免与 ui 布局持久化互相覆盖；改 JSON 后重启客户端即可生效
- **使用的技术栈**: PyQt6、ConfigStore
- **修改的文件列表**: config/client.json、app/config_store.py、app/ui/main_window.py、app/ui/header_bar.py、app/ui/pages/login_page.py、README.md


---

## 会话总结 - 2026-08-14 (4)

- **会话主要目的**: 将自动更新改为安全流程，避免运行中覆盖被占用的 .pyd
- **完成的主要任务**:
  1. 新增 app/ops/safe_updater.py：下载到临时目录后启动独立脚本，等待进程退出再解压覆盖并自动重启
  2. UpdateClient.apply 改为 pending_apply，不再进程内直接 extractall
  3. 用户点击「立即更新」后自动退出安装并重启，无需再确认
  4. apply_zip_update 增加占用重试；补充 scripts/test_safe_update.py 烟测
- **关键决策与解决方案**: 进程内只负责下载；文件替换放到退出后的独立 Python 进程，绕过 Windows 对已加载 .pyd 的锁定
- **使用的技术栈**: subprocess DETACHED_PROCESS、zipfile、PyQt6 QTimer
- **修改的文件列表**: app/ops/safe_updater.py、install_root.py、update_client.py、updater.py、app/integration/controller.py、scripts/run_ui_skeleton.py、app/ui/update_dialog.py、scripts/test_safe_update.py、README.md


---

## 会话总结 - 2026-08-14 (3)

- **会话主要目的**: 按当前 Potato 路由（B2 干麦 / B1 抖音 / Aux 客户端）重写 Studio One 联调指南
- **完成的主要任务**: 更新 `docs/cn/StudioOne_Voicemeeter_Potato联调指南.md`：总线约定、方案 B/C、AI 跟唱说明、与 S1 互斥、抖音/OBS、验收与排错
- **关键决策与解决方案**: 以现行 auto=Aux 为准，废弃旧文档 H1→B1、OBS 采 B2 的主路径；S1 采 Aux Output、出 Aux Input
- **使用的技术栈**: Markdown 文档、Voicemeeter Potato、Studio One、抖音直播伴侣
- **修改的文件列表**: docs/cn/StudioOne_Voicemeeter_Potato联调指南.md、README.md

---

## 会话总结 - 2026-08-15

- **会话主要目的**: 排查 `run_ui_skeleton.py` 启动变慢，并将 GPU 探测改为异步
- **完成的主要任务**:
  1. 定位卡点：`ui wired` 后进主界面时，UI 线程同步 `import torch` / CUDA 探测导致闪屏卡住约 2 分钟
  2. `MainWindow._refresh_gpu_status` 改为后台线程探测，通过 `_gpu_status_ready` 信号回写状态栏
  3. 探测中显示 `GPU: 检测中…`，并用 `_gpu_probe_busy` 避免 8 秒定时器叠加重入
- **关键决策与解决方案**: 不改启动接线顺序；仅将 `collect_environment_info` 的 GPU 探测移出 UI 线程，避免挡住 `main_entered`
- **使用的技术栈**: PyQt6 信号、threading
- **修改的文件列表**: app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-15 (2)

- **会话主要目的**: 增加 nginx 路径前缀配置，统一推导登录/日志上报 URL
- **完成的主要任务**:
  1. 新增 `server.base_url` + `server.nginx_prefix`（client.json / ConfigStore 默认）
  2. 新增 `app/ops/server_url.py`，登录与崩溃日志上报共用根地址推导
  3. `auth.login_url` / `logs.upload_url` 留空时自动得到 `…/ai-sound/api/...`
  4. 设置页「常规」增加服务器地址、Nginx 前缀；保存写入 config
- **关键决策与解决方案**: 显式 URL 仍优先；否则 `base_url + nginx_prefix` 拼 API；也可从 `update.check_url` 回退推导并带前缀
- **使用的技术栈**: Python urllib.parse、ConfigStore、PyQt6 设置页
- **修改的文件列表**: app/ops/server_url.py、app/ops/auth_client.py、app/ops/crash_reporter.py、app/config_store.py、config/client.json、app/ui/settings_dialog.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-15 (3)

- **诉求**: 制作歌曲完成后不要自动切到播放页，留在当前 Tab，仅日志提示完成
- **实现**: 移除 `offline_finished` 中的 `switch_to_playback`；`bridge.log_message` 输出制作完成
- **修改的文件列表**: scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-15 (4)

- **会话主要目的**: 修复制作页多文件批量做歌只处理第一首的问题
- **完成的主要任务**:
  1. 制作页提交任务时收集 file_list 全部路径为 `inputs` 列表
  2. `_offline_worker` 按队列顺序逐首调用 `OfflineSongPipeline.run`，进度按「第 N/M 首」缩放
  3. 完成后 `offline_finished` 携带 `results` 列表；UI 输出结果区展示每首成品路径
- **关键决策与解决方案**: 单 pipeline 实例复用、worker 内循环；任一首失败或取消则终止整批；歌词仍按每首 stem 复制同一 lrc 源（若提供）
- **使用的技术栈**: PyQt6、OfflineSongPipeline、Controller 线程 worker
- **修改的文件列表**: app/ui/pages/song_make_page.py、app/integration/controller.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-15 (5)

- **会话主要目的**: 批量做歌进度条与单首一致，逐首完成后再处理下一首
- **完成的主要任务**:
  1. 取消整批进度缩放（原先 `(当前首+内层%)/总数` 导致第二首分离阶段显示 75% 等错乱）
  2. 每首开始前重置进度为 0、阶段回到「分离」；状态文案前缀「第 N/M 首 · …」
  3. 非最后一首完成时提示「第 N/M 首已完成」，再进入下一首
- **关键决策与解决方案**: 进度条始终表示当前单曲 0–100%；批量信息仅体现在状态文字，不混入百分比
- **使用的技术栈**: PyQt6、Controller 进度事件
- **修改的文件列表**: app/integration/controller.py、app/ui/pages/song_make_page.py、README.md

---

## 会话总结 - 2026-08-15 (6)

- **会话主要目的**: 做歌成功后自动从待处理列表移除已转换文件
- **完成的主要任务**: `show_offline_result` 根据结果 `source_path` 调用 `_remove_input_paths`，批量/单首成功后清空对应队列项
- **关键决策与解决方案**: 路径用 `normcase+normpath` 比对，避免 Windows 大小写差异；失败/取消不触发清除
- **使用的技术栈**: PyQt6 QListWidget
- **修改的文件列表**: app/ui/pages/song_make_page.py、README.md

---

## 会话总结 - 2026-08-15 (7)

- **会话主要目的**: 恢复歌库列表双击切歌，避免单击误切
- **完成的主要任务**: 移除 `song_list.currentRowChanged` → `_on_song_row_changed` 连接；仅保留 `itemDoubleClicked` 触发 `_apply_row_song`
- **关键决策与解决方案**: 单击只高亮选中行，不通知 controller；程序内切歌（自动下一首、按标题选中）仍走 `_apply_row_song`
- **使用的技术栈**: PyQt6 QListWidget
- **修改的文件列表**: app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-15 (8)

- **会话主要目的**: 客户端单实例运行，重复启动时唤醒已有窗口
- **完成的主要任务**:
  1. 新增 `app/ops/single_instance.py`：`QSharedMemory` 判重 + `QLocalServer/Socket` 发 `raise` 唤醒
  2. `run_ui_skeleton.main` 检测到已有进程则退出；主实例监听并调用 `MainWindow.bring_to_front`
  3. `bring_to_front` 处理最小化恢复与 Windows 前台聚焦
- **关键决策与解决方案**: 实例 key 按安装根目录 MD5，同目录多开互斥；二次启动静默退出 code 0
- **使用的技术栈**: PyQt6 QSharedMemory、QLocalServer、ctypes SetForegroundWindow
- **修改的文件列表**: app/ops/single_instance.py、app/ui/main_window.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-15 (9)

- **会话主要目的**: 单实例重复启动时尽量把已有窗口提到最前
- **完成的主要任务**:
  1. 收到唤醒消息后 `QTimer.singleShot(0)` 延迟到 UI 事件循环再激活
  2. Windows 下 `AttachThreadInput` + `SetForegroundWindow` + `BringWindowToTop`
  3. 仍无法抢焦点时 `FlashWindowEx` 闪烁任务栏提示
- **关键决策与解决方案**: Windows 前台策略限制下无法 100% 保证覆盖全屏应用；闪烁作为兜底
- **使用的技术栈**: PyQt6 QTimer、ctypes user32
- **修改的文件列表**: app/ops/single_instance.py、app/ui/main_window.py、README.md

---

## 会话总结 - 2026-08-15 (10)

- **会话主要目的**: 排查四模式切换/设置改设备后播放界面卡住，并修复根因
- **完成的主要任务**:
  1. 设置保存时检测输入/输出/hostapi/采样率变更，播放中自动 stop+restart 音频流
  2. `restore_playback_after_settings` 支持 unified 流恢复、tick 线程复活
  3. ai_sing tick 停滞约 0.75s 后自动 `playback_stopped`，避免进度条假死
  4. 模式切换被阻断时回滚 `selected_mode` 与 UI 按钮；处理 `playback_blocked`/`realtime_blocked`
- **关键决策与解决方案**: 切 Tab 不影响播放后端；卡住主因是设备热更新不重启流 + tick 线程停更 UI
- **使用的技术栈**: PyQt6、AudioStreamManager、WavPlayer、Controller tick 线程
- **修改的文件列表**: app/integration/controller.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-15 (11)

- **会话主要目的**: 原唱 Tab 从普通说话切 AI 唱歌时不应停播、不应倒退进度
- **完成的主要任务**: `_song_unified_ready` 允许原唱条目（仅伴奏 mp3）走统一流 ai_sing 热切换，避免 stop+WavPlayer 重载
- **关键决策与解决方案**: 原唱 AI 唱歌 = 同一条伴奏 timeline 无缝切模式；唱歌 Tab 仍要求 inst+vocal
- **使用的技术栈**: AudioStreamManager 四模式互切
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-15 (12)

- **会话主要目的**: 修复原唱 Tab 切模式回退、唱歌/原唱 Tab 互切仍后台播放
- **完成的主要任务**:
  1. 切换唱歌/原唱 Tab 时 `playback_lib_tab` 停止当前播放并仅加载新歌单 metadata
  2. 统一流同曲热切换禁止 backward seek（异步 dispatch 携带的旧 position 导致倒退）
  3. 同 timeline 模式切换用 `sync_at` 而非 `reset_sync`；AI 唱歌不再重复 `_select_song` reload 歌词
- **关键决策与解决方案**: Tab 切换=停播+换库；四模式互切保持 inst_pos 只前进不后退
- **使用的技术栈**: PyQt6、AudioStreamManager、Controller
- **修改的文件列表**: app/ui/pages/playback_page.py、app/integration/controller.py、app/audio/stream_manager.py、app/audio/service.py、README.md

---

## 会话总结 - 2026-08-15 (13)

- **会话主要目的**: 纠正 Tab 切换逻辑——切 Tab 不停播；跨库双击新歌时须停掉旧歌
- **完成的主要任务**:
  1. 撤销切 Tab 自动停播与 `playback_lib_tab`；Tab 只换列表 UI
  2. 切 Tab 不再向 controller 写入新歌 metadata（避免 lib_changed 误判）
  3. 双击切歌时 `_stop_prev_if_needed`：跨歌曲/跨库必先 `_release_playback_source` 再播新歌
- **关键决策与解决方案**: 播放会话跟 controller.selected_song 绑定，仅双击切歌才切换
- **使用的技术栈**: PyQt6、Controller 切歌链路
- **修改的文件列表**: app/ui/pages/playback_page.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-17

- **会话主要目的**: 客户端日志按天切分，startup/crash 日志补时间戳
- **完成的主要任务**:
  1. 主日志改为 `client-YYYY-MM-DD.log`（按自然日追加，不再按 5MB 滚动）
  2. `startup-YYYY-MM-DD.log`、`crash-YYYY-MM-DD.log` 等同样按天；每行前缀 `YYYY-MM-DD HH:MM:SS |`
  3. 崩溃上报/打包适配新文件名（兼容旧 `*.log`）
- **关键决策与解决方案**: 统一工具在 `app/ops/rotating_log.py`；faulthandler 用 `TimestampedLogWriter` 包装
- **使用的技术栈**: Python logging、FileHandler
- **修改的文件列表**: app/ops/rotating_log.py、scripts/run_ui_skeleton.py、app/ops/crash_reporter.py、app/ops/log_bundle.py、README.md

---

## 会话总结 - 2026-08-17 (2)

- **会话主要目的**: 日志按天分子目录，避免 logs/client 下文件过多混乱
- **完成的主要任务**: 目录结构改为 `logs/client/YYYY-MM-DD/{client,startup,crash,...}.log`；打包上报保留相对路径；兼容旧扁平 `*-日期.log`
- **关键决策与解决方案**: `daily_log_dir` + 简单文件名；zip 内路径含日期子目录
- **使用的技术栈**: Python logging、Path
- **修改的文件列表**: app/ops/rotating_log.py、app/ops/log_bundle.py、scripts/run_ui_skeleton.py、README.md

- **会话主要目的**: 修复编译为 .pyd 后切换普通/混响说话报 `must be real number, not NoneType`
- **完成的主要任务**:
  1. 定位为 Cython 将 `seek_sec: float` 做运行时强制转换，热切换传入的 `None`（保持进度）被拒收
  2. `set_playback_mode` / `switch_playback_mode` / `load_instrumental` 去掉会拒收 None 的 float 注解；冷启动将 None 按 0 处理
- **关键决策与解决方案**: 保留 `seek_sec is None` 表示同曲不 seek 的语义；避免 Cython 注解 typing 破坏该约定
- **使用的技术栈**: Cython .pyd、AudioStreamManager
- **修改的文件列表**: app/audio/stream_manager.py、app/audio/service.py、README.md

---

## 会话总结 - 2026-08-17

- **会话主要目的**: 客户端日志按天切分，startup/crash 日志带时间戳
- **完成的主要任务**:
  1. `client/startup/crash/stdout/stderr` 改为 `{name}-YYYY-MM-DD.log` 按天追加
  2. `startup` 行格式 `YYYY-MM-DD HH:MM:SS | 消息`；`crash` 用 `TimestampedLogWriter` 前缀时间
  3. 崩溃打包/检测适配新文件名；主日志 Formatter 含完整日期时间
- **使用的技术栈**: logging.FileHandler、app/ops/rotating_log.py
- **修改的文件列表**: app/ops/rotating_log.py、app/ops/crash_reporter.py、app/ops/log_bundle.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-17 (3)

- **会话主要目的**: 桌面悬浮歌词增加横屏/竖屏切换，原有歌词展示逻辑保持不变
- **完成的主要任务**:
  1. `LyricsWindow` 支持横/竖方向切换；竖屏按字换行并保留逐字高亮颜色
  2. 右键菜单可选「横屏展示 / 竖屏展示」；托盘增加「歌词横/竖切换」
  3. 方向与窗口 geometry 写入 `ui.lyrics_window` 持久化；有存档时启动不再强制挪位
- **关键决策与解决方案**: 播放页歌词不动；桌面窗默认仍为横屏；仅切换方向时改尺寸与排版，`set_line` / `set_lyric_tick` API 不变
- **使用的技术栈**: PyQt6（Frameless 置顶窗、QMenu、RichText）
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/tray.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-17 (4)

- **会话主要目的**: 修复客户端启动失败：`TimestampedLogWriter` 无 `fileno` 导致 `faulthandler.enable` 报错
- **完成的主要任务**:
  1. `TimestampedLogWriter` 增加 `fileno()`，委托底层文件描述符
  2. `_install_crash_diagnostics` 用模块级 `_crash_log_file` 持有 writer，避免被 GC 关闭
- **关键决策与解决方案**: `faulthandler` 走 C 层 `fileno`，必须暴露真实 FD；Python `write` 仍可前缀时间戳
- **使用的技术栈**: Python faulthandler
- **修改的文件列表**: app/ops/rotating_log.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-17 (5)

- **会话主要目的**: 用户在主界面找不到「桌面歌词」入口
- **完成的主要任务**:
  1. 说明桌面歌词是独立悬浮窗，原先仅托盘菜单可开关且默认不 show
  2. 启动时默认 `lyrics.show()`；播放页右侧增加「桌面歌词」按钮
  3. 托盘文案改为「显示/隐藏桌面歌词」「桌面歌词横/竖切换」
- **关键决策与解决方案**: 主界面补发现入口；横/竖仍在悬浮窗右键或托盘切换
- **使用的技术栈**: PyQt6
- **修改的文件列表**: app/ui/pages/playback_page.py、scripts/run_ui_skeleton.py、app/ui/tray.py、README.md

---

## 会话总结 - 2026-08-17 (6)

- **会话主要目的**: 桌面歌词悬浮窗无法拖动位置
- **完成的主要任务**: `QLabel` 设置 `WA_TransparentForMouseEvents`，鼠标事件落到窗口以便拖拽
- **关键决策与解决方案**: 拖拽逻辑已在 `LyricsWindow`，被子控件吞事件导致失效
- **使用的技术栈**: PyQt6
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (7)

- **会话主要目的**: 桌面歌词默认不展示，由用户主动点「桌面歌词」打开
- **完成的主要任务**: 去掉启动时 `lyrics.show()`
- **关键决策与解决方案**: 悬浮窗仍创建并接托盘/按钮，仅默认隐藏
- **使用的技术栈**: PyQt6
- **修改的文件列表**: scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-17 (8)

- **会话主要目的**: 桌面歌词改为酷狗式双行，并支持拖拽调整窗口大小
- **完成的主要任务**:
  1. `LyricMatch` 增加 `next_text`（当前行+下一行）
  2. `LyricsWindow` 双行展示：上行当前（可逐字高亮）、下行下一句（右对齐淡色）
  3. 无边框窗口边缘/四角可拖拽缩放，字号随高度变化，尺寸持久化
- **关键决策与解决方案**: 横屏仿酷狗上下错位；竖屏仍两行竖排；默认不自动弹出
- **使用的技术栈**: PyQt6、LyricMatcher
- **修改的文件列表**: app/lyrics/matcher.py、app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (9)

- **会话主要目的**: 修复点「桌面歌词」后跨线程更新 QLabel 报错
- **完成的主要任务**: `set_lyric_tick` 经 `pyqtSignal` 队列切回 UI 线程再改控件
- **关键决策与解决方案**: 歌词同步线程不可直接 `setText`；信号默认 QueuedConnection
- **使用的技术栈**: PyQt6 pyqtSignal
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (10)

- **会话主要目的**: 消除桌面歌词缩放时 `QWindowsWindow::setGeometry` 警告
- **完成的主要任务**: Label 使用 Ignored 尺寸策略；layout SetNoConstraint；覆盖 `minimumSizeHint`；缩放拖动中不改字号、松手再同步
- **关键决策与解决方案**: 大字号 QLabel 的 sizeHint 抬高了实际最小高度，导致系统钳制几何并刷警告
- **使用的技术栈**: PyQt6 QSizePolicy / QLayout
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (11)

- **会话主要目的**: 修复竖屏时双行歌词变成一列
- **完成的主要任务**: 竖屏用 `QBoxLayout.LeftToRight` 左右两列；横屏仍上下两行；最小尺寸按方向区分
- **关键决策与解决方案**: 竖排字再用上下堆叠会视觉合并成一行，改为左右分列
- **使用的技术栈**: PyQt6 QBoxLayout
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (12)

- **会话主要目的**: 修复竖屏切横屏窗口异常变大、横屏切竖屏尺寸不变
- **完成的主要任务**: 横/竖分别持久化 `geometry_h` / `geometry_v`；切换前先保存当前模式尺寸，再恢复目标模式尺寸；宽高比例不符时回退默认
- **关键决策与解决方案**: 不再共用一份 geometry，避免竖屏高度被带到横屏
- **使用的技术栈**: PyQt6、layout_store
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (13)

- **会话主要目的**: 修复运行中横竖屏切换尺寸被竖排 `<br>` 内容撑高，并消除 setGeometry 警告
- **完成的主要任务**: 切换时先清空标签；用 `setMaximumSize` 强制目标宽高后再填歌词；最后放开 max
- **关键决策与解决方案**: 日志里目标 640x180 却变成 640x1570，根因是切换瞬间仍保留逐字竖排富文本
- **使用的技术栈**: PyQt6
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (14)

- **会话主要目的**: 竖屏歌词改为酷狗式左右上下错落，不再两列并排
- **完成的主要任务**: 竖屏改回上下分区；当前句左上对齐、下一句右下对齐；字仍竖排
- **关键决策与解决方案**: 与横屏同为 TopToBottom，仅对齐与竖排文字不同
- **使用的技术栈**: PyQt6 QBoxLayout
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (15)

- **会话主要目的**: 桌面歌词改为酷狗双行翻页：两行都唱完才换下两行
- **完成的主要任务**: `LyricMatcher` 增加 page_top/page_bot；`LyricsWindow` 按页渲染；播放页仍用原逐行 next
- **关键决策与解决方案**: `page_base = index // 2 * 2`；唱上行高亮上、下行待唱；唱下行上行已唱色、下行高亮
- **使用的技术栈**: LyricMatcher、PyQt6
- **修改的文件列表**: app/lyrics/matcher.py、app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (16)

- **会话主要目的**: 横/竖屏切换时分别恢复各自上次的窗口位置
- **完成的主要任务**: `_pick_mode_geometry` 恢复 `geometry_h` / `geometry_v` 的 x,y,w,h；切换前先保存当前方向
- **关键决策与解决方案**: 不再切换时沿用当前坐标，只换尺寸
- **使用的技术栈**: layout_store
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (17)

- **会话主要目的**: 修复竖屏歌词展示不全/被遮挡
- **完成的主要任务**: 竖屏字号按半窗高度与最长句字数自适应；略减内边距；换词后重算字号
- **关键决策与解决方案**: 原先只按宽度定字号，长句竖排超出半区被裁切
- **使用的技术栈**: PyQt6 QFont
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-17 (18)

- **会话主要目的**: 竖屏长句仍被裁切
- **完成的主要任务**: 竖屏改回左右整高两列（左上/右下错落）；字号改 `setPixelSize` 并按整窗高度/字数缩放
- **关键决策与解决方案**: 上下对半导致每句只有半高；且 QFont 点数比像素更大导致低估
- **使用的技术栈**: PyQt6 QFont/QBoxLayout
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-18

- **会话主要目的**: 让自有桌面歌词能被抖音直播伴侣采集，并在设置中可调透明度
- **完成的主要任务**:
  1. 歌词窗改为独立顶层窗口（标题「桌面歌词」），去掉 Tool，Win32 设 WS_EX_APPWINDOW，便于窗口采集
  2. 设置 → 歌词 增加背景/窗口不透明度滑条，拖动即时预览，取消则还原，保存写入配置
- **关键决策与解决方案**: 歌词助手只认酷狗等播放器，本窗走窗口采集；背景 100% 关闭分层透明以便采到；亮度因显示器而异故做成可调
- **使用的技术栈**: PyQt6、Win32 SetWindowLongPtr
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/settings_dialog.py、app/config_store.py、config/client.json、app/integration/controller.py、scripts/run_ui_skeleton.py、app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-19

- **会话主要目的**: 抖音窗口采集桌面歌词仍出现黑底，需要可靠透底方案
- **完成的主要任务**:
  1. 新增「直播抠像（绿幕）」模式：整窗不透明色键底、关闭 WA_Translucent / WS_EX_LAYERED，强制 opacity=1
  2. 设置页增加抠像开关与底色（纯绿/品红/直播绿），普通透明滑条在抠像模式下禁用
  3. 默认配置改为 chroma，本机 client.json 已写入
- **关键决策与解决方案**: 伴侣采不到 Alpha，透明区必变黑；可靠路径是窗口采集 + 绿幕抠色键，而非调背景透明度
- **使用的技术栈**: PyQt6 paintEvent、Win32 SetWindowLongPtr、config/client.json
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/settings_dialog.py、app/config_store.py、app/integration/controller.py、config/client.json、README.md

---

## 会话总结 - 2026-08-19（桌面歌词遮挡修复）

- **会话主要目的**: 修复桌面歌词绿幕竖条在抖音伴侣/主程序上遮挡后面内容、无法点击的问题
- **完成的主要任务**:
  1. 绿幕模式默认关闭「窗口置顶」，打开桌面歌词时不再强制 raise 到最前
  2. 新增「鼠标穿透」（WS_EX_TRANSPARENT），绿条可见但鼠标可点穿到后面界面
  3. 设置 → 歌词 增加「鼠标穿透」「窗口置顶」开关；歌词窗右键菜单也可切换
- **关键决策与解决方案**: 伴侣按窗口名采集，不依赖置顶；物理遮挡用穿透解决，需拖动时临时关穿透
- **使用的技术栈**: PyQt6、Win32 WS_EX_TRANSPARENT / SetWindowLongPtr
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/settings_dialog.py、app/config_store.py、scripts/run_ui_skeleton.py、app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-19（桌面歌词遮挡加强修复）

- **会话主要目的**: 用户反馈 config 已正确但穿透/置底仍无效，需加强桌面歌词不挡主程序与伴侣
- **完成的主要任务**:
  1. 叠加 Qt WA_TransparentForMouseEvents + Win32 WS_EX_TRANSPARENT，延迟重刷样式
  2. 非置顶时 HWND_BOTTOM + lower()，并修复托盘/切歌仍 raise_() 的问题
  3. 检测与主窗重叠时自动挪到主窗旁；设置页新增「歌词窗移到主窗旁」
  4. 设置说明强调：伴侣应采集「桌面歌词」而非 python.exe，抠像色需与 #00B140 一致
- **关键决策与解决方案**: 上次仅改 config 不够，Qt/托盘会把窗拉回最前；需多层穿透 + Z 序置底 + 物理位置错开
- **使用的技术栈**: PyQt6、Win32 SetWindowPos(HWND_BOTTOM)
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/settings_dialog.py、app/ui/tray.py、scripts/run_ui_skeleton.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-19（绿幕抠像文字被吃掉）

- **会话主要目的**: 抖音绿幕抠图后文字透明/发绿，相似度调低才看见但看不清
- **完成的主要任务**:
  1. 根因：逐字高亮色（蓝 #93c5fd、金 #fbbf24）绿色分量大，被当成绿幕抠掉
  2. 抠像模式改为白字 + 黑描边、关抗锯齿；当前字仅加粗区分
  3. 默认/本机抠像底色改纯绿 #00FF00；设置页补充伴侣相似度 300~420 建议
- **关键决策与解决方案**: 绿幕场景禁用含 G 通道的高亮色；broadcast 标准白字黑边
- **使用的技术栈**: PyQt6 RichText text-shadow、QFont.NoAntialias
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/settings_dialog.py、config/client.json、README.md

---

## 会话总结 - 2026-08-19（QPainter 纯色字抠像）

- **会话主要目的**: 伴侣键色与程序一致时字仍被抠没/发绿，白字 QLabel 方案无效
- **完成的主要任务**:
  1. 根因：Windows ClearType 白字叠绿底，采集像素含绿分量，被色度键当背景吃掉
  2. 绿幕模式改 QPainter 直绘：隐藏 QLabel，关抗锯齿，绿幕用纯红字(G=0)，品红幕用纯绿字
  3. 黑边描字仅作本机预览辅助，抠绿后保留红/绿正文
- **关键决策与解决方案**: 抠像场景禁止 QLabel 渲染；文字颜色必须与键色在 RGB 上正交
- **使用的技术栈**: PyQt6 QPainter、QFont.NoAntialias、PreferBitmap
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/settings_dialog.py、README.md

---

## 会话总结 - 2026-08-19（撤销自动缩小 + 酷狗蓝白字）

- **会话主要目的**: 自动缩小窗口导致长短歌词显示不全；用户要酷狗式蓝白渐变字
- **完成的主要任务**:
  1. 移除 _fit_chroma_bounds 自动缩小，窗口恢复手动拖拽定尺寸
  2. 绿幕 QPainter 改蓝→白渐变、深灰描边 + 白边，当前字加亮加粗
  3. 设置页说明窗口需自行调大小、蓝字抠像相似度建议
- **关键决策与解决方案**: 歌词长短不一不宜自动 resize；渐变蓝白近似酷狗，直播相似度可能需微调
- **使用的技术栈**: PyQt6 QLinearGradient、QPainter
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/settings_dialog.py、README.md

---

## 会话总结 - 2026-08-19（绿幕遮挡与直播说明）

- **会话主要目的**: 红字已正常但绿条仍挡桌面；用户担心直播是否挡脸
- **完成的主要任务**:
  1. 说明：伴侣抠绿后直播画面只剩红字，摄像头为独立素材不会被绿条挡
  2. 关闭 autoFillBackground 防白底；窗口随歌词自动缩小到文字范围
  3. 设置页补充本机遮挡 vs 直播画面的区别
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/settings_dialog.py、README.md

---

## 会话总结 - 2026-08-19（歌词清晰度优化）

- **会话主要目的**: 酷狗蓝白字边缘锯齿、发虚，整体不清晰
- **完成的主要任务**:
  1. 去掉 NoAntialias/多层 offset 描边，改 QPainterPath 一次描边+渐变填充
  2. 开启 TextAntialiasing、PreferFullHinting，最小字号提到 10px
  3. 渐变色调微调更接近酷狗实心填充感
- **关键决策与解决方案**: 多层 drawText 叠描边是发虚主因；清晰度优先于极致抠像
- **使用的技术栈**: PyQt6 QPainterPath、TextAntialiasing
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-19（白底对比度）

- **会话主要目的**: 桌面歌词在白底上几乎看不见，黑底尚可
- **完成的主要任务**:
  1. 渐变去掉近白浅色，改为深蓝→中蓝实心渐变
  2. 描边改纯黑加粗，加轻微阴影；当前字改橙黄渐变（与主界面一致）
- **关键决策与解决方案**: 抠像后常叠在浅色画面上，字色不能含大量浅蓝/白
- **使用的技术栈**: PyQt6 QPainterPath、QLinearGradient
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-19（修复纯绿无字）

- **会话主要目的**: QPainterPath 改色后窗口只剩纯绿、歌词完全不显示
- **完成的主要任务**:
  1. 根因：Windows 上 QPainterPath.fillPath 对中文轮廓填充无效
  2. 改回 drawText + 黑描边 + 实心蓝/橙字，恢复可见
  3. _paint_pair 同步写入 _last_text/html，避免状态丢失
- **关键决策与解决方案**: 中文歌词必须用 drawText，不能用 Path 填充
- **使用的技术栈**: PyQt6 QPainter.drawText
- **修改的文件列表**: app/ui/lyrics_window.py、README.md

---

## 会话总结 - 2026-08-19（歌词颜色可配置）

- **会话主要目的**: 用户希望桌面歌词文字颜色可在设置中选择（如直播常用白字）
- **完成的主要任务**:
  1. 新增 lyrics.desktop_chroma_text_color / desktop_chroma_highlight_color 配置
  2. 设置 → 歌词 → 桌面歌词 增加「歌词颜色」「当前字颜色」下拉，切换即时预览
  3. 默认改为纯白字 + 橙黄当前字；保留黑描边
- **关键决策与解决方案**: 颜色写入 config，apply_desktop_style 驱动 QPainter 填色
- **使用的技术栈**: PyQt6 QComboBox、config_store
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/settings_dialog.py、app/config_store.py、README.md

---

## 会话总结 - 2026-08-20（直播伴侣 python.exe 混淆）

- **会话主要目的**: 解决抖音直播伴侣窗口采集时，主程序与桌面歌词同为 python.exe 导致绑错窗口、需反复删素材重加的问题
- **完成的主要任务**:
  1. 桌面歌词默认改为独立子进程（IPC 同步 tick/样式/显隐），与主程序分离 PID
  2. 窗口标题改为「【直播歌词】桌面歌词」，伴侣按窗口名更易识别
  3. 支持项目根目录 `桌面歌词.exe` 作为歌词启动器（复制 python 即可改进程名）
  4. 新增 `scripts/make_desktop_lyrics_exe.bat` 一键生成 `桌面歌词.exe`
  5. 设置页补充伴侣采集说明
- **关键决策与解决方案**: 仅改窗口标题不够；需独立进程 + 可选独立 exe 名，伴侣列表才会稳定显示「桌面歌词.exe 【直播歌词】桌面歌词」
- **使用的技术栈**: PyQt6 QLocalServer/QLocalSocket、subprocess、ConfigStore
- **修改的文件列表**: app/ops/lyrics_ipc.py、scripts/run_desktop_lyrics.py、scripts/run_ui_skeleton.py、app/ui/lyrics_window.py、app/ui/settings_dialog.py、app/ui/main_window.py、app/config_store.py、scripts/make_desktop_lyrics_exe.bat、README.md

---

## 会话总结 - 2026-08-20（修复 make_desktop_lyrics_exe.bat）

- **会话主要目的**: 用户运行 `make_desktop_lyrics_exe.bat` 报「未找到 python.exe」
- **完成的主要任务**: 脚本增加 `C:\Python312` 等常见路径及 `where python` 回退；已成功生成 `桌面歌词.exe`
- **关键决策与解决方案**: 原脚本只查 venv 与 `%LOCALAPPDATA%\Programs\Python`，未覆盖本机 `C:\Python312\python.exe`
- **使用的技术栈**: Windows batch
- **修改的文件列表**: scripts/make_desktop_lyrics_exe.bat、README.md

---

## 会话总结 - 2026-08-20（桌面歌词任务栏图标）

- **会话主要目的**: 桌面歌词进程在任务栏显示默认空白图标，不便区分
- **完成的主要任务**:
  1. 新增绿色圆角「词」字 `desktop_lyrics_icon()`，主/子进程歌词窗均设置窗口图标
  2. 生成 `assets/desktop_lyrics.ico`，`make_desktop_lyrics_exe.bat` 用 rcedit 嵌入 exe 图标
  3. 歌词子进程设置独立 AppUserModelID，任务栏与主程序分开
- **关键决策与解决方案**: 窗口图标 + exe 嵌入双保险；更新 exe 前需先关闭正在运行的桌面歌词进程
- **使用的技术栈**: PyQt6 QIcon、rcedit、ICO(PNG) 生成
- **修改的文件列表**: app/ui/tray.py、app/ui/lyrics_window.py、scripts/run_desktop_lyrics.py、scripts/gen_desktop_lyrics_ico.py、scripts/make_desktop_lyrics_exe.bat、assets/desktop_lyrics.ico、README.md

---

## 会话总结 - 2026-08-20（主程序「趣」图标）

- **会话主要目的**: 主程序任务栏/托盘图标与桌面歌词统一风格，文字改为「趣」
- **完成的主要任务**:
  1. 新增蓝色圆角「趣」字 `main_app_icon()`，替换原白框蓝块 fallback 图标
  2. 主程序设置 AppUserModelID，任务栏与歌词进程区分
  3. `gen_app_icons.py` 同时生成 `assets/main_app.ico` 与 `desktop_lyrics.ico`
- **关键决策与解决方案**: 主程序蓝底「趣」、歌词绿底「词」，共用 `_char_round_icon` 绘制
- **使用的技术栈**: PyQt6 QIcon
- **修改的文件列表**: app/ui/tray.py、scripts/run_ui_skeleton.py、scripts/gen_app_icons.py、scripts/make_desktop_lyrics_exe.bat、assets/main_app.ico、README.md

---

## 会话总结 - 2026-08-20（启动预加载与首播加速）

- **会话主要目的**: 加载页进主页卡顿、点播放等 10~30 秒，需把重活提前到 loading 阶段
- **完成的主要任务**:
  1. bootstrap 增加 `warmup_startup`：预热音频模块、预加载首曲 WAV/统一流（暂停待命）、歌词 energy align
  2. 新增 `app/audio/wav_cache.py`，stream / pitchfix / 歌词对齐共享 WAV 解码缓存，避免同一文件重复读盘
  3. 选歌 `_select_song_apply` 一律后台线程，避免 energy align 卡 UI
  4. 修复统一流 autoplay 时 paused 状态不自动 unpause
- **关键决策与解决方案**: 30s 根因是首播冷启动两次全量 WAV 解码；loading 页预加载 + 缓存后点播放应近秒开
- **使用的技术栈**: threading、soundfile/librosa 缓存、AudioStreamManager
- **修改的文件列表**: app/audio/wav_cache.py、app/audio/stream_manager.py、app/pitchfix/service.py、app/lyrics/aligner.py、app/integration/controller.py、scripts/run_ui_skeleton.py、README.md

---

## 会话总结 - 2026-08-20（登录后首曲歌词不显示）

- **会话主要目的**: 登录后默认首曲显示「暂无歌词」，实际 LRC 已存在
- **完成的主要任务**: 预加载阶段已在后台 load_lrc，但选首曲时因同路径跳过 `lyrics_loaded` 推送；增加 `_lyrics_ui_path` 追踪 UI 是否已同步，未同步则补发
- **关键决策与解决方案**: 保留同曲不重复推送（避免重置到第一句），仅首进/未同步时补发
- **使用的技术栈**: ClientController 状态追踪
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-20（桌面歌词首曲空白）

- **会话主要目的**: 主界面歌词已显示，桌面歌词窗仍空白
- **完成的主要任务**:
  1. `lyrics_loaded` 后调用 `_reset_playback_lyrics` 推送桌面 tick
  2. 歌词窗 IPC 就绪后 350ms 再补同步一次
  3. IPC 未连接时缓存 tick，子进程连上后自动补发
- **关键决策与解决方案**: 播放页走 lines 列表，桌面窗走 tick；预加载只更新了 matcher 未推 tick
- **使用的技术栈**: LyricsService.reset_sync、QLocalSocket 待发队列
- **修改的文件列表**: scripts/run_ui_skeleton.py、app/ops/lyrics_ipc.py、README.md

---

## 会话总结 - 2026-08-20（播放时间轴不动）

- **会话主要目的**: 预加载后点播放，音频在播但主界面进度条停在 00:00
- **完成的主要任务**: `_resume_timeline` 恢复统一流播放时补启 `_restart_playback_tick`（与 WavPlayer 路径一致）
- **关键决策与解决方案**: 预加载只 pause 流未启动 tick；resume 只 unpause 不发 periodic playback_tick
- **使用的技术栈**: playback-tick 线程
- **修改的文件列表**: app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-20（设置关闭后桌面歌词消失）

- **会话主要目的**: 打开设置后直接关闭，桌面歌词不再显示且按钮无效
- **完成的主要任务**:
  1. 取消设置时 `apply_desktop_style` 重设窗口 flags，Windows 上 hide/show 后子进程窗体丢失
  2. 子进程/Proxy 样式应用后强制 `showNormal` + sync；取消时补推歌词 tick
  3. 桌面歌词切换按钮显示时同步 tick
- **关键决策与解决方案**: Proxy 仅转发 style 未恢复可见性；reject 改为关键字参数并显式 reshow
- **使用的技术栈**: PyQt6 窗口 flags、Lyrics IPC
- **修改的文件列表**: app/ui/lyrics_window.py、app/ui/settings_dialog.py、app/ops/lyrics_ipc.py、scripts/run_desktop_lyrics.py、scripts/run_ui_skeleton.py、app/ui/tray.py、README.md

---

## 会话总结 - 2026-08-20（设置关闭 IPC 管道断开）

- **会话主要目的**: 打开设置直接关闭后桌面歌词消失，再点按钮报 QWindowsPipeWriter 管道已结束
- **完成的主要任务**:
  1. 取消设置时未改歌词也会 `apply_desktop_style`，重设 flags 导致子进程崩溃
  2. 仅在实际预览过歌词样式时（`_lyric_style_preview`）才在 reject 恢复
  3. IPC 增加 `ensure_alive` 自动重启子进程、写失败入队、断线重连后补发
- **关键决策与解决方案**: 根因是无变更也触发样式重载；管道错误是子进程已退出仍写入
- **使用的技术栈**: QLocalSocket、subprocess 重启
- **修改的文件列表**: app/ui/settings_dialog.py、app/ops/lyrics_ipc.py、app/ui/lyrics_window.py、scripts/run_ui_skeleton.py、app/ui/tray.py、README.md

---

## 会话总结 - 2026-08-20（桌面歌词不跟随主歌词）

- **会话主要目的**: 播放时主界面歌词正常滚动，桌面歌词不再随主歌词变动
- **完成的主要任务**:
  1. 定位根因：`playback-tick` 后台线程直接调用 `LyricsWindowProxy.set_lyric_tick`，`QLocalSocket` 必须在主线程写入
  2. 独立进程桌面歌词改为经 scheduler → UI 线程 bridge 转发 tick（与主界面同路径）
  3. `LyricsWindowProxy` 禁用 `tick_handler` 直连，避免跨线程 IPC 写入
- **关键决策与解决方案**: 主界面 tick 走 Qt signal 线程安全；IPC Proxy 无 signal 包装，须主线程 send
- **使用的技术栈**: PyQt6 QLocalSocket 线程约束、scheduler STATUS 总线
- **修改的文件列表**: scripts/run_ui_skeleton.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-20（歌库当前播放标识）

- **会话主要目的**: 歌库列表中当前加载/播放的歌曲左侧增加颜色标识，便于快速识别
- **完成的主要任务**: 歌库 `QListWidget` 为当前歌曲项设置蓝色竖条 icon（`#2563eb`），切歌、刷新、删除后同步更新
- **关键决策与解决方案**: 用 `QListWidgetItem.setIcon` + 窄 pixmap 实现左侧色条，避免自定义 Delegate
- **使用的技术栈**: PyQt6 QIcon / QPixmap
- **修改的文件列表**: app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-20（普通说话音量可设 0）

- **会话主要目的**: 「普通说话音量」最低从 50% 改为 0%，便于关闭耳机内干声监听
- **完成的主要任务**: 设置滑块范围 0～200%；`passthrough_gain_from_audio` 增益下限改为 0
- **关键决策与解决方案**: 仍用 `ui/50` 映射增益，0%=静音、100%=2x、200%=4x
- **使用的技术栈**: PyQt6 QSlider、音频 passthrough_gain
- **修改的文件列表**: app/ui/settings_dialog.py、app/audio/service.py、README.md

---

## 会话总结 - 2026-08-20（双路监听不含干声）

- **会话主要目的**: 直播输出含完整麦克风，耳机监听在普通/混响说话时不含干声
- **完成的主要任务**:
  1. 新增第二路 `OutputStream` 监听输出（默认 VAIO，直播输出默认 Aux）
  2. 普通/混响说话：直播混音含干声，监听混音仅伴奏；AI 唱歌/跟唱两路相同
  3. 设置页增加「监听设备」「双路监听」开关与 Voicemeeter 路由说明
- **关键决策与解决方案**: 同一次 callback 读一次伴奏帧，分别混两路避免进度错位
- **使用的技术栈**: sounddevice 双 OutputStream、Voicemeeter Aux/B1 + VAIO/A1
- **修改的文件列表**: app/audio/stream_manager.py、app/audio/devices.py、app/audio/service.py、app/config_store.py、app/ui/settings_dialog.py、app/integration/controller.py、README.md

---

## 会话总结 - 2026-08-20（伴奏盖人声 + 播放条伴奏音量）

- **会话主要目的**: 有伴奏时直播间听不到普通说话；播放页增加酷狗式伴奏音量；更新开发大纲双路监听
- **完成的主要任务**:
  1. 根因：普通/混响说话混音用硬 clip，伴奏峰值高时削掉人声；改为与 AI 模式相同的峰值归一化
  2. 播放条进度旁增加「伴奏」滑块（0~100%），实时写 `pitchfix.inst_ui` 并更新流
  3. `开发大纲.md` 补充双路监听、VM 路由、混音与排错表
- **关键决策与解决方案**: 直播路 normalize 保人声比例；用户可再降伴奏滑块
- **使用的技术栈**: numpy 峰值归一化、playback_ai_follow_mix 复用
- **修改的文件列表**: app/audio/stream_manager.py、app/ui/pages/playback_page.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-20（伴奏 0 仍出声 / 直播无人声）

- **会话主要目的**: 伴奏滑块为 0 仍有声音；普通说话直播间听不见
- **完成的主要任务**:
  1. 根因：`inst_gain or 0.77` 在增益为 0 时误用 0.77，伴奏无法静音且盖过人声
  2. 新增 `_cfg_gain` 正确支持 0；说话混音改人声优先（伴奏自动让位，不再整体 peak 归一化压人声）
  3. 滑块变更时立即写 `mgr.config.inst_gain`
- **关键决策与解决方案**: 波形条是文件能量显示，与伴奏输出音量无关
- **修改的文件列表**: app/audio/stream_manager.py、app/integration/controller.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-20（直播普通说话音量偏低）

- **会话主要目的**: 普通说话音量 200% 时直播间人声仍偏小
- **完成的主要任务**:
  1. 去掉混音前硬 clip，允许增益把人声顶满后再限幅
  2. 直播路检测到人声时自动补增益（峰值目标约 92%）
  3. 「普通说话音量」上限 200%→400%（增益最高 8x）
- **关键决策与解决方案**: VM B2 输入电平偏低时靠客户端补增益；仍不够可调 Potato H1 推子
- **修改的文件列表**: app/audio/stream_manager.py、app/audio/service.py、app/ui/settings_dialog.py、app/integration/controller.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-20（双路监听 AI 唱歌回响）

- **会话主要目的**: 开启双路监听后 AI 唱歌耳机有回响，关闭则正常
- **完成的主要任务**: 首版改为 talk 才写监听路，导致 AI 模式耳机无声；后调整为 AI 也写 VAIO
- **关键决策与解决方案**: 回响来自 AUX 与 VAIO 同进 A1，非双路本身
- **修改的文件列表**: app/audio/stream_manager.py、README.md

---

## 会话总结 - 2026-08-20（双路 AI 唱歌耳机无声）

- **会话主要目的**: 修复双路监听下 AI 唱歌耳机无声（此前为消回响关闭了 AI 监听路）
- **完成的主要任务**: AI 唱歌/跟唱恢复 VAIO 监听完整混音；talk 仍监听仅伴奏；复用同帧 stream_mix 避免重复读轨
- **关键决策与解决方案**: 回响根因是 AUX 勾 A1，不是双路本身；须 VM：AUX 只 B1、VAIO 只 A1
- **修改的文件列表**: app/audio/stream_manager.py、app/ui/settings_dialog.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-20（直播间 AI 唱歌回响）

- **会话主要目的**: 双路监听开启时直播间 AI 唱歌/跟唱有回响（非耳机）；VM 已 AUX→B1、VAIO→A1
- **完成的主要任务**: AI 模式完全关闭 VAIO 监听 OutputStream；仅 talk 模式双路；切模式时 `_sync_monitor_stream` 动态开关
- **关键决策与解决方案**: Potato 双虚拟输入同内容时 B1 可能叠音；AI 耳机可 AUX 勾 A1+B1 同源；跟唱 orig_ui>0 也会叠原唱
- **修改的文件列表**: app/audio/stream_manager.py、app/ui/settings_dialog.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-20（AI 耳机直连免改 VM）

- **会话主要目的**: AI 唱歌/跟唱戴耳机监听时，避免用户手动给 AUX 勾选 A1
- **完成的主要任务**: AI 模式监听改直连物理耳机（WASAPI），不经 Voicemeeter VAIO；直播仍只走 Aux→B1；切模式时自动切换监听设备
- **关键决策与解决方案**: 回响根因是 Aux+VAIO 双虚拟输入同内容叠进 B1；AI 监听绕过 VM 虚拟输入即可既无回响又无需改条带勾选
- **使用的技术栈**: sounddevice 双 OutputStream、WASAPI 默认输出设备解析
- **修改的文件列表**: app/audio/devices.py、app/audio/stream_manager.py、app/ui/settings_dialog.py、README.md

---

## 会话总结 - 2026-08-20（AI 耳机无声修复）

- **会话主要目的**: AI 唱歌时耳机无声音（用户 VM 耳机走 VAIO→A1）
- **完成的主要任务**: 查日志定位 AI 监听误选 Realtek Digital Output(23) 而非 VAIO Input(22)；改回 auto 优先 VAIO；监听流打开失败时自动 fallback
- **关键决策与解决方案**: 用户耳机经 Voicemeeter A1 监听，直连物理声卡无效；须与 talk 同走 VAIO Input
- **修改的文件列表**: app/audio/devices.py、app/audio/stream_manager.py、app/ui/settings_dialog.py、README.md

---

## 会话总结 - 2026-08-20（模式切换后直播音量偏小）

- **会话主要目的**: 普通说话→AI 唱歌→普通说话后，直播间听感变小
- **完成的主要任务**: 离开 talk 时快照 `_talk_inst_gain`，从 AI 回到 talk 时恢复；AI↔talk 切换清空 output/monitor 环缓并重置淡出；回到 talk 强制刷新 `passthrough_gain`
- **关键决策与解决方案**: AI 与 talk 共用 pitchfix 伴奏滑块，AI 常设 0 导致回 talk 后直播无伴奏；快照隔离两模式伴奏增益
- **修改的文件列表**: app/audio/stream_manager.py、app/audio/service.py、README.md

---

## 会话总结 - 2026-08-20（双路监听终版文档）

- **会话主要目的**: 双路监听验收通过后，整理最终实现并写入开发大纲
- **完成的主要任务**: 开发大纲新增「双路监听（已验收）」专节：软件双 OutputStream、按模式分混音、VM 条带路由、配置项与踩坑；更新联调表与任务 3 模块说明
- **关键决策与解决方案**: 直播 Aux→B1（talk 含干声/AI 完整混音）；监听 VAIO→A1（talk 仅伴奏/AI 完整混音）；AUX 只 B1、VAIO 只 A1
- **修改的文件列表**: 开发大纲.md、README.md

---

## 会话总结 - 2026-08-20（AI 直播人声音量）

- **会话主要目的**: AI 唱歌/跟唱直播人声可独立调节，与普通人说话音量对齐
- **完成的主要任务**: 新增 `ai_vocal_ui`（0～400%）播放条+设置页滑块；AI 混音改用人声优先（复用 `_mix_talk`），去掉 `_normalize_peak` 压满
- **关键决策与解决方案**: 原 AI 混音 normalize 导致电平恒满、与 mic 说话听感不一致；AI 直播人声与普通说话音量分开配置
- **修改的文件列表**: app/audio/stream_manager.py、app/audio/service.py、app/config_store.py、app/ui/pages/playback_page.py、app/ui/settings_dialog.py、app/integration/controller.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-20（AI 高音量耳机回响）

- **会话主要目的**: AI人声 400% 时耳机出现回响；200/400 听感曾相同（自动压限）
- **完成的主要任务**: AI 专用 `_mix_ai_live` 线性增益；ai_vocal 改 ui/100；>100% 时直播全量、耳机 VAIO 仅伴奏防叠音
- **关键决策与解决方案**: 高 AI 人声同时走 Aux+VAIO 易在 A1 叠音；与普通说话一致，超 100% 监听路不含 AI 人声
- **修改的文件列表**: app/audio/stream_manager.py、app/audio/service.py、app/ui/pages/playback_page.py、app/ui/settings_dialog.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-20（AI 伴奏耳机回响）

- **会话主要目的**: AI 人声回响修好后，耳机里伴奏也有回响
- **完成的主要任务**: AI 唱歌/跟唱关闭 VAIO 监听路，仅 Aux 单路输出；文档说明 AI 戴耳机用 AUX 勾 A1+B1 同源
- **关键决策与解决方案**: 伴奏同时从 Aux+VAIO 进 A1 会叠音；AI 与普通说话分路，AI 不再送 VAIO
- **修改的文件列表**: app/audio/stream_manager.py、app/ui/settings_dialog.py、app/ui/pages/playback_page.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-20（AI 耳机恢复无回响）

- **会话主要目的**: 关 VAIO 后 AI 耳机无声，需恢复监听且保持无叠音回响
- **完成的主要任务**: 恢复 AI 模式 VAIO 监听完整混音；AI人声>100% 时耳机路径增益封顶 100%、直播仍可调至 400%
- **关键决策与解决方案**: 无回响靠 VM 分路（AUX 只 B1、VAIO 只 A1、AUX 勿勾 A1）；不需用户 AUX 勾 A1
- **修改的文件列表**: app/audio/stream_manager.py、app/ui/settings_dialog.py、app/ui/pages/playback_page.py、开发大纲.md、README.md

---

## 会话总结 - 2026-08-20（回音确认为 VM 误勾 A1）

- **会话主要目的**: 用户确认 AI 双路监听暂正常；回溯早前伴奏/人声回响原因
- **完成的主要任务**: 无代码改动；确认 AUX 误勾 A1 会导致 Aux+VAIO 叠进耳机产生回响
- **关键决策与解决方案**: 固定路由 AUX 只 B1、VAIO 只 A1、H1 只 B2 即可稳定使用当前软件双路方案
- **修改的文件列表**: README.md

---

## 会话总结 - 2026-08-20（AI/说话直播音量刻度对齐）

- **会话主要目的**: AI 人声 400% 明显响于普通说话 400%，同刻度听感不一致
- **完成的主要任务**: AI 直播路 RVC 干声先归一化至 25% 峰值再乘增益，并复用 `_mix_talk` 自动补增益/限幅；耳机监听仍走 `_mix_ai_live`
- **关键决策与解决方案**: RVC 预渲染干声电平远高于麦克风干声，旧 `_mix_ai_live` 线性放大导致 AI 400% 过响；现与普通说话共用直播混音逻辑，400% 目标电平一致
- **使用的技术栈**: numpy 混音、sounddevice 双路输出
- **修改的文件列表**: app/audio/stream_manager.py、app/ui/settings_dialog.py、app/ui/pages/playback_page.py、README.md

---

## 会话总结 - 2026-08-20（修复 AI 直播呲呲电流声）

- **会话主要目的**: 音量对齐改动后出现呲呲呲电流声
- **完成的主要任务**: 去掉每 100ms 音频块单独峰值归一化及 `_mix_talk` 自动补增益；改为加载 RVC 干声时记录整轨峰值，直播路用固定比例缩放 + `_mix_ai_live` 整段限幅
- **关键决策与解决方案**: 分块增益突变会放大底噪并产生 zipper noise；整轨校准增益稳定，仅混音后峰值>1 时归一
- **修改的文件列表**: app/audio/stream_manager.py、README.md
