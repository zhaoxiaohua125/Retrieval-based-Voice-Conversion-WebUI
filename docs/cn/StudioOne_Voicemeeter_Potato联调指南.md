# Studio One + Voicemeeter Potato + RVC 联调指南

> 适用：Windows 10/11 · Voicemeeter **Potato** · Studio One 6/7 64 位 · 本仓库 RVC 声迹客户端 + `RVCRealtimeVST`  
> 目标：过渡方案跑通直播链路；后期再在客户端内 1:1 复刻声迹 Pro（内置修音 / VST 宿主）。

---

## 一、整体分工

| 软件 | 负责什么 |
| --- | --- |
| **RVC 声迹客户端** | 离线做歌、AI 唱歌（播成品）、歌词悬浮窗、（可选）普通说话直通 |
| **Studio One** | 播伴奏、音轨加载 **RVC Realtime VST3** 做实时变声 |
| **Voicemeeter Potato** | 汇总麦克风 / 客户端 / S1 输出 → 耳机监听 & OBS 采集 |
| **OBS**（可选） | 采集 VM 的 B2 虚拟声卡 |

建议 **分步联调**，不要一次全开。

---

## 二、Voicemeeter Potato 通道速查

Potato 界面从左到右大致为：

| 条带名称 | 作用 | Windows 里常见设备名 |
| --- | --- | --- |
| **Hardware Input 1~3** | 物理麦克风、乐器进 VM | （条带顶部的 A1/A2/A3 选物理设备） |
| **Voicemeeter Input** | 虚拟输入 **VAIO**，App 播放进 VM | 播放设备：`Voicemeeter Input (VB-Audio Voicemeeter VAIO)` |
| **Voicemeeter AUX Input** | 虚拟输入 **AUX**，第二路 App（如 S1 伴奏） | 播放设备：`Voicemeeter AUX Input` |
| **Hardware Out A1~A3** | 物理耳机 / 音箱 | 条带右侧 **A1** 列 |
| **Virtual Out B1~B3** | 虚拟输出，给别的软件当「麦克风/采集」 | 录音设备：`Voicemeeter Out B1` 等 |

**铁律（防啸叫 / 反馈环）**

1. **采集用 B1，播放用 VAIO**，不要混用同一条回灌。  
2. **RVC / 客户端输出条带（VAIO 或 AUX）不要勾 B1** 再进自己的采集，否则必啸叫。  
3. 客户端日志若大量 `audio reconnect failed`，优先查 VM 路由与 `input_device` / `output_device` index。

---

## 三、推荐路由方案

### 方案 A：最简（只做 AI 唱歌，不用 S1）

1. 客户端「制作歌曲」→ 生成 `*_cover.wav`  
2. 「播放」→ **AI 唱歌**，同目录放 `.lrc`  
3. **不需要** Voicemeeter / Studio One  

适合：先验证做歌与歌词。

---

### 方案 B：Potato + 客户端「普通说话 / 实时变声（过渡）」

```
物理麦克风 → Hardware Input 1
                └─ 只勾 B1（不勾 A1，避免干声直出）

客户端 采集 IN  = Voicemeeter Out B1
客户端 播放 OUT = Voicemeeter Input (VAIO)
                      └─ VAIO 条带勾 A1（耳机）+ 可选 B2（OBS）
```

**Potato 操作步骤**

1. 打开 Voicemeeter Potato，菜单 **System Settings / Restart** 确保驱动正常。  
2. **Hardware Input 1** 顶部下拉：选你的真实麦克风（如 USB 麦）。  
3. **Hardware Input 1** 右侧：只点亮 **B1**，**不要**点亮 A1（初调阶段）。  
4. **Voicemeeter Input (VAIO)** 右侧：点亮 **A1**（监听变声后声音）；若 OBS 采集，再点亮 **B2**。  
5. 客户端 **设置** → 音频：  
   - 输入 = 带 `Out B1` 的设备  
   - 输出 = 带 `Voicemeeter Input` / `VAIO` 的设备  

查设备编号：

```powershell
cd F:\zxh\workspace\Retrieval-based-Voice-Conversion-WebUI-Self
F:\zxh\anaconda3\envs\rvc312\python.exe scripts\list_audio_devices.py
```

把输出的 `input_device` / `output_device` 写入 `config/client.json` 的 `audio` 段，或在设置对话框里改完保存。

6. 客户端点 **普通说话** 或（过渡）**AI 跟唱**：应能在 A1 耳机听到声；VM 电平条随说话跳动。

> **注意**：当前「AI 跟唱」按钮仍是**实时 RVC 过渡实现**，不是最终修音跟唱（任务 9）。直播变声更推荐方案 C 用 S1 插件。

---

### 方案 C：Potato + Studio One + RVC VST3（推荐直播变声）

```
物理麦克风 → Hardware Input 1 → B1
Studio One 该轨输入 = Voicemeeter Out B1（录音设备）
Studio One 该轨插入 RVC Realtime VST3 → 变声后
Studio One 主输出 / 该轨输出 → Voicemeeter AUX Input（伴奏也可走此路）
AUX 条带 → A1 耳机 + B2 OBS
（可选）客户端只开悬浮歌词，OSC 跟 S1 播放头
```

**不要**让 S1 变声后再送回 B1 给 S1 同一轨输入。

#### C.1 安装 RVC VST3

```powershell
cd F:\zxh\workspace\Retrieval-based-Voice-Conversion-WebUI-Self\RVCRealtimeVST
.\scripts\build.ps1
```

将 `dist\RVCRealtime.vst3` **整个文件夹**复制到：

```text
C:\Program Files\Common Files\VST3\RVCRealtime.vst3
```

Studio One：**Studio One → 选项 → 位置 → VST 插件** → 确认含 `Common Files\VST3` → **重新扫描**。

详细说明见：`RVCRealtimeVST/resources/README.txt`

#### C.2 Studio One 工程

1. 新建工程，添加 **音频轨**（变声）+ **音频轨**（伴奏，可选）。  
2. 变声轨：插入 **RVC Realtime** → **RVC ROOT** 选本项目根目录（含 `infer/`、`assets/`）→ 选 `.pth` → **ENGINE** 至 READY。  
3. **变声轨输入**：设备选 **Voicemeeter Out B1**（或你在 VM 上给麦用的那条 B 总线）。  
4. **伴奏轨**：导入客户端输出的 `*_instrumental.wav`；或整轨 `*_cover.wav` 仅作监听。  
5. **S1 音频输出**：  
   - 简单做法：主输出 → **Voicemeeter AUX Input**  
   - 在 Potato **Voicemeeter AUX Input** 条带勾 **A1** + **B2**  

6. VM **Hardware Input 1** 仍只勾 **B1**，麦只进 S1 变声轨，不直出 A1。

#### C.3 Potato 与 S1 设备对照

| 用途 | VM 条带 / 总线 | S1 或客户端选什么 |
| --- | --- | --- |
| 麦克风进 S1 | H1 → B1 | S1 轨输入 = Voicemeeter Out B1 |
| S1 进耳机/OBS | AUX → A1, B2 | S1 主输出 = Voicemeeter AUX Input |
| 客户端播声进 VM | VAIO → A1 | 客户端 OUT = Voicemeeter Input (VAIO) |
| 客户端采 VM 里某路 | H1→B1 等 | 客户端 IN = Voicemeeter Out B1 |

---

## 四、Studio One → 客户端 歌词 OSC（可选）

客户端默认在 `config/client.json`：

```json
"lyrics": {
  "clock_source": "manual",
  "osc_port": 9000,
  "osc_addresses": [
    "/transport/time",
    "/studioone/transport/time",
    "/time"
  ],
  "offset_ms": 0
}
```

### 4.1 客户端

1. 安装依赖：`pip install python-osc`  
2. 将 `clock_source` 改为 `"osc"`，保存后重启客户端。  
3. 打开悬浮歌词窗；S1 播放时看行是否高亮。

### 4.2 Studio One（6.x 思路）

1. **外部设备** 中添加 **OSC** 控制面（名称自定）。  
2. 目标主机 **127.0.0.1**，端口 **9000**（与 `osc_port` 一致）。  
3. 映射 **播放时间（秒，浮点）** → OSC 地址 `/studioone/transport/time`（或 `/transport/time`，需与 `osc_addresses` 一致）。  
4. S1 播放 / 暂停 / 拖动播放头，客户端歌词应跟随。  
5. 若不同步：在 S1 OSC 监视里确认有发包；微调 `offset_ms`（设置对话框或 json）。

**不想配 OSC**：保持 `clock_source: "manual"`，用客户端 **AI 唱歌** 播成品即可，歌词跟客户端播放器。

---

## 五、OBS 采集（可选）

1. OBS 来源 → **音频输入捕获**  
2. 设备选 **Voicemeeter Out B2**（需在 Potato 里把 VAIO/AUX/H1 需要进 OBS 的条带勾上 **B2**）  
3. 仅勾需要的路，避免把 B1 干麦再采一遍造成双重变声  

---

## 六、分步验收清单

| 步骤 | 验收 |
| --- | --- |
| 0 | 客户端离线做歌成功，`*_cover.wav` 可播 |
| 1 | S1 单独加载 RVC VST3，ENGINE=READY，戴耳机能听到变声 |
| 2 | VM：H1→B1，S1 输入 B1，S1 输出 AUX→A1，无啸叫 |
| 3 | 客户端 `list_audio_devices.py` index 与设置一致，普通说话有声 |
| 4 | OSC：`clock_source=osc`，S1 播放时悬浮歌词高亮 |
| 5 | OBS 采 B2，直播能听到伴奏+人声 |

---

## 七、常见问题

| 现象 | 处理 |
| --- | --- |
| 啸叫 / 回声 | VAIO 或 S1 输出是否误勾 **B1**；客户端 OUT 是否回到 IN 同一路 |
| S1 找不到 RVC | 复制整个 `RVCRealtime.vst3` 文件夹；重新扫描 VST3 |
| ENGINE 失败 | RVC ROOT 指向项目根；Python 选 `rvc312` 或打包目录 `python\python.exe` |
| 客户端没声 | 重跑 `list_audio_devices.py`，更新 `input_device` / `output_device` |
| VM 条不动 | System Settings 里选对 A1 物理输出；Windows 隐私里允许麦克风 |
| 歌词不动 | 是否 `osc` 模式；防火墙是否拦 UDP 9000；S1 地址是否与 json 一致 |
| GPU 占满 | S1 插件与客户端不要同时开 ENGINE；直播只保留一条变声路径 |

---

## 八、与产品路线图关系

| 现阶段（外置） | 后期 1:1（客户端内） |
| --- | --- |
| S1 播伴奏 | 多轨同步播放 |
| RVC VST3 变声 | 任务 9 内置修音跟唱 |
| VM 混音 / OBS | 内置混音面板 |
| S1 OSC 歌词 | 保留 OSC + 本机播放头双支持 |
| 外置 VST 混响 | Phase 3+ 可选 VST3 宿主 |

外置联调的路由与设备 index 经验，后期迁移到内置架构时仍适用。

---

## 九、相关文件

| 文件 | 说明 |
| --- | --- |
| `scripts/list_audio_devices.py` | 查 VM 设备 index |
| `config/client.json` | 音频 / 歌词 OSC 配置 |
| `RVCRealtimeVST/resources/README.txt` | VST2/VST3 安装 |
| `RVCRealtimeVST/README.md` | 插件编译与开发 |
| `app/lyrics/osc_client.py` | OSC 监听实现 |
| `开发大纲.md` | 任务 9 / 8 / VST 宿主规划 |
