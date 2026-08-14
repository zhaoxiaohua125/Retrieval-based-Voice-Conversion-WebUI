# Studio One + Voicemeeter Potato + RVC 联调指南

> 适用：Windows 10/11 · Voicemeeter **Potato** · Studio One 6/7 64 位 · 本仓库客户端 + `RVCRealtimeVST`  
> 目标：在「抖音采 B1、干麦走 B2、客户端/处理走 Aux」前提下跑通直播与可选 S1 变声；后期再在客户端内 1:1 复刻声迹 Pro。

---

## 〇、当前推荐总线约定（先看这个）

本机已按 **错开抖音主麦** 固定如下（与客户端 `audio.input_device` / `output_device` = `"auto"` 一致）：

| 总线 | Windows 录音设备名（WASAPI 常见） | 用途 |
| --- | --- | --- |
| **B1** | `VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)` | **抖音直播伴侣**主麦（或「系统默认」，且系统默认录音已设为此设备） |
| **B2** | `VoiceMeeter Aux Output (VB-Audio VoiceMeeter AUX VAIO)` | **干麦专用**：H1 只勾 B2；客户端 / S1 从这里采集 |
| **B3** | `VoiceMeeter VAIO3 Output` | 备用 |

| 虚拟输入条带 | Windows 播放设备名 | 用途 |
| --- | --- | --- |
| **VAIO** | `VoiceMeeter Input` | 系统软件（浏览器、微信等），通常只勾 **A1** |
| **AUX** | `VoiceMeeter Aux Input` | **唱歌伴侣**（`auto` 默认 OUT）；S1 实时变声时也可占用此条（与客户端实时模式互斥） |
| **VAIO3** | `VoiceMeeter VAIO3 Input` | 备用（S1 与客户端要同时播时，把其中一路改到这里） |

**Potato 勾选模板（日常直播 + 客户端）**

1. **Hardware Input 1（物理麦）**：只亮 **B2**（不要亮 A1，避免干声直出耳机；不要亮 B1，避免干麦进抖音）。  
2. **Voicemeeter AUX**：亮 **A1 + B1**（自己听 + 送给抖音）。  
3. **AUX 不要勾 B2**（播放条带禁止回到自己的采集总线）。  
4. **VAIO**：按需亮 **A1**（桌面声只进耳机，默认不进抖音）。  
5. A1 硬件输出选你的耳机 / Realtek 扬声器。

```
物理麦 H1 ──只勾 B2──► B2 (= Aux Output)
                              │
              客户端 / S1 采集 ◄─┘
                              │
              处理后播放进 AUX Input
                              │
                    AUX：A1 + B1
                         ├─ A1 → 耳机
                         └─ B1 → 抖音（VoiceMeeter Output）
```

> 旧版文档「H1→B1、直播/OBS 采 B2」与当前约定 **相反**，请以本节为准。

---

## 一、整体分工

| 软件 | 负责什么 |
| --- | --- |
| **唱歌伴侣客户端** | 离线做歌、**AI 唱歌**（播成品）、**AI 跟唱**（麦端 VAD 检测到人声后加大 AI 人声轨，不是 S1 实时 RVC）、普通/混响说话、歌词窗 |
| **Studio One**（可选） | 播伴奏；音轨加载 **RVC Realtime VST3** 做**实时变声说话** |
| **Voicemeeter Potato** | 汇总麦克风 / 客户端 / S1 → 耳机（A1）与抖音（B1） |
| **抖音直播伴侣** | 主麦 = `VoiceMeeter Output` 或「系统默认」（系统默认录音须为该设备）；扬声器可用 Realtek |
| **OBS**（可选） | 若仍用 OBS，单独规划一条总线（见第五节），**不要**再占用 B2 干麦 |

建议 **分步联调**，不要一次全开。

**互斥铁律**

- **AI 跟唱 / 普通说话 / 客户端实时变声** 与 **S1+RVC 实时变声** 不要同时抢同一条麦处理链（都是采 B2、出 Aux 时必冲突）。  
- 开 S1 变声时：关掉客户端「普通说话 / AI 跟唱 / 实时变声」；客户端可只留 **歌词 OSC**。  
- 开客户端 AI 跟唱时：不必开 S1 变声轨（跟唱已是「检测人声 → 播 AI 成品」）。

---

## 二、Voicemeeter Potato 通道速查

| 条带 / 总线 | 作用 | Windows 里常见设备名 |
| --- | --- | --- |
| **Hardware Input 1~5** | 物理麦克风进 VM | 条带顶部选 Realtek / USB 麦等 |
| **Voicemeeter Input (VAIO)** | 第一路 App 播放进 VM | 播放：`VoiceMeeter Input (… VAIO)` |
| **Voicemeeter AUX** | 第二路 App（客户端 / S1） | 播放：`VoiceMeeter Aux Input`；录音：`VoiceMeeter Aux Output` **= B2** |
| **VAIO3** | 第三路 App | 播放：`VoiceMeeter VAIO3 Input`；录音：`VoiceMeeter VAIO3 Output` **= B3** |
| **A1~A5** | 物理耳机 / 音箱 | 例如 A1 = Realtek 扬声器 |
| **B1~B3** | 虚拟输出，给别的软件当「麦克风」 | B1≈`VoiceMeeter Output`；B2≈`Aux Output`；B3≈`VAIO3 Output` |

**防啸叫**

1. **干麦采集总线（B2）** 与 **处理后回灌总线（B1）** 必须分开。  
2. 客户端 / S1 的 **播放条带（AUX）禁止勾 B2**。  
3. H1 不要勾 B1（除非你有意把干麦直接送直播）。  
4. 客户端配置用 `"auto"` 或**设备名**，不要写易变的 index；查设备：

```powershell
cd F:\zxh\workspace\Retrieval-based-Voice-Conversion-WebUI-Self
python scripts\list_audio_devices.py
```

`config/client.json` 示例：

```json
"audio": {
  "input_device": "auto",
  "output_device": "auto",
  "hostapi": "Windows WASAPI"
}
```

`auto` 在 Potato 下优先：**IN = Aux Output（B2）**，**OUT = Aux Input**，从而避开抖音占用的主 VAIO Output（B1）。

---

## 三、推荐路由方案

### 方案 A：最简（只做 AI 唱歌，不用 VM 复杂路由）

1. 客户端「制作歌曲」→ 生成 `*_cover.wav`  
2. 「播放」→ **AI 唱歌**，同目录放 `.lrc`  
3. 可不依赖 Studio One；若要进抖音，仍建议走 Potato（方案 B）

适合：先验证做歌与歌词。

---

### 方案 B：Potato + 客户端（日常直播主路径）

适用于：**普通说话 / 混响说话 / AI 唱歌 / AI 跟唱**。

```
物理麦克风 → Hardware Input 1 → 只勾 B2
客户端 IN  = auto → VoiceMeeter Aux Output（B2）
客户端 OUT = auto → VoiceMeeter Aux Input
                      └─ AUX 条带勾 A1（耳机）+ B1（抖音）
抖音主麦   = VoiceMeeter Output（B1）或「系统默认」
```

**Potato 操作**

1. 打开 Voicemeeter Potato，确认驱动正常。  
2. **H1** 选真实麦克风；只点亮 **B2**。  
3. **AUX** 点亮 **A1 + B1**；确认未点亮 B2。  
4. **VAIO** 仅 A1（系统声）。  
5. 客户端设置 → 音频：输入/输出选 **「自动识别 Voicemeeter（优先 Aux）」** 或保持 `"auto"`。  
6. Windows「声音 → 录制」：默认设备 = `VoiceMeeter Output`（便于抖音用「系统默认」）。  
7. 抖音直播伴侣：主麦 = `VoiceMeeter Output` 或「系统默认」；扬声器可用 Realtek。

**AI 跟唱说明**

- 实现是：采 B2 干麦 → **VAD 检测到人声** → 加大已生成的 AI 人声轨（并播伴奏），**不是** Studio One 里的实时 RVC。  
- 因此「跟唱」不要求安装 S1 / VST；线路与普通说话相同（都走 Aux）。  
- 需要伴奏轨 + `converted_vocal`（或文档要求的人声成品路径）。

验收：对着麦说话，AUX / B1 电平有变化；耳机能听到；抖音预览能听到处理后的声（跟唱时为人声门控后的 AI 轨）。

---

### 方案 C：Potato + Studio One + RVC VST3（可选实时变声）

在方案 B 总线不变的前提下，用 S1 做**实时变声说话**（与客户端 AI 跟唱互斥）。

```
物理麦克风 → H1 → 只勾 B2
Studio One 变声轨输入 = VoiceMeeter Aux Output（采 B2）
Studio One 插入 RVC Realtime VST3 → 变声后
Studio One 主输出 = VoiceMeeter Aux Input
AUX 条带 → A1 + B1（耳机 + 抖音）
客户端：关闭普通说话 / AI 跟唱 / 实时变声；可选 OSC 歌词跟随 S1
```

**不要**让 S1 输出条带勾 **B2**（禁止变声后再进自己的输入）。

#### C.1 安装 RVC VST3

```powershell
cd F:\zxh\workspace\Retrieval-based-Voice-Conversion-WebUI-Self\RVCRealtimeVST
.\scripts\build.ps1
```

将 `dist\RVCRealtime.vst3` **整个文件夹**复制到：

```text
C:\Program Files\Common Files\VST3\RVCRealtime.vst3
```

Studio One：**选项 → 位置 → VST 插件** → 确认含 `Common Files\VST3` → **重新扫描**。  
详见：`RVCRealtimeVST/resources/README.txt`

#### C.2 Studio One 工程

1. 新建工程：音频轨（变声）+ 可选伴奏轨。  
2. 变声轨插入 **RVC Realtime** → **RVC ROOT** 指向项目根（含 `infer/`、`assets/`）→ 选 `.pth` → **ENGINE** 至 READY。  
3. **变声轨输入** = `VoiceMeeter Aux Output`（**不是**旧文档的 Out B1 / 主 Output）。  
4. **主输出 / 音频设备** = `VoiceMeeter Aux Input`。  
5. 伴奏放在 S1 内一起从主输出出去最简单。  
6. VM：**H1 只勾 B2**；**AUX 勾 A1+B1**。

#### C.3 与客户端同时播成品时

不要和 S1 抢 AUX：把其中一路改到 **VAIO3**。

| 角色 | 播放设备 | 条带勾选 |
| --- | --- | --- |
| S1 变声 + 伴奏 | `VAIO3 Input` | VAIO3 → A1 + B1 |
| 客户端 AI 唱歌 | `Aux Input`（保持 auto） | AUX → A1；若也要进直播再勾 B1 |
| 干麦 | H1 → B2 | S1 采 `Aux Output` |

两边都勾 B1 时抖音听到的是混合，注意避免双人声。

#### C.4 设备对照（当前约定）

| 用途 | VM | 软件里选什么 |
| --- | --- | --- |
| 干麦 | H1 → **B2** | 客户端 / S1 输入 = `VoiceMeeter Aux Output` |
| 处理后进耳机+抖音 | AUX → **A1 + B1** | 客户端 / S1 输出 = `VoiceMeeter Aux Input` |
| 抖音主麦 | 采 **B1** | `VoiceMeeter Output` 或系统默认 |
| 系统软件 | VAIO → A1 | （一般不用改） |
| 备用第三路 | VAIO3 | 见 C.3 |

---

## 四、Studio One → 客户端 歌词 OSC（可选）

客户端 `config/client.json`：

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

1. 依赖：`pip install python-osc`  
2. `clock_source` 改为 `"osc"`，保存后重启。  
3. 打开悬浮歌词；S1 播放时看行是否高亮。

### 4.2 Studio One（6.x 思路）

1. **外部设备** 添加 **OSC** 控制面。  
2. 目标 **127.0.0.1**，端口 **9000**。  
3. 映射播放时间（秒，浮点）→ `/studioone/transport/time`（或与 `osc_addresses` 一致的地址）。  
4. 不同步时查 OSC 是否发包，并微调 `offset_ms`。

**不想配 OSC**：保持 `clock_source: "manual"`，用客户端 **AI 唱歌 / AI 跟唱** 播成品，歌词跟客户端播放头。

---

## 五、OBS 采集（可选）

当前主直播已用 **抖音采 B1**，B2 专供干麦，**不要**再按旧文档「OBS 采 B2」去勾 H1→B2 以外的回灌。

若仍需要 OBS：

1. 优先让 OBS 也采 **`VoiceMeeter Output`（B1）**（与抖音同源），或  
2. 另开 **B3**：把需要进 OBS 的条带（如 AUX）勾上 **B3**，OBS 选 `VoiceMeeter VAIO3 Output`，且 **不要**把干麦 H1 勾到 B3 造成双重。

---

## 六、分步验收清单

| 步骤 | 验收 |
| --- | --- |
| 0 | 客户端离线做歌成功，`*_cover.wav` 可播 |
| 1 | VM：H1→仅 B2；AUX→A1+B1；AUX 未勾 B2 |
| 2 | 客户端 `auto`：普通说话 / AI 唱歌有声；抖音预览能听到（走 B1） |
| 3 | AI 跟唱：说话时 AI 人声门控响起，不啸叫 |
| 4 | （可选）S1：ENGINE=READY；输入 Aux Output；输出 Aux Input；关客户端实时模式后无啸叫 |
| 5 | （可选）OSC：`clock_source=osc`，S1 播放时歌词高亮 |
| 6 | 抖音主麦为 Output 或系统默认，且系统默认录音为 `VoiceMeeter Output` |

---

## 七、常见问题

| 现象 | 处理 |
| --- | --- |
| 啸叫 / 回声 | AUX 是否误勾 **B2**；H1 是否误勾 B1 又被处理链回灌 |
| 抖音有声、耳机没有 | AUX 是否勾了 **A1** |
| 耳机有声、抖音没有 | AUX 是否勾了 **B1**；抖音是否采到 `VoiceMeeter Output`；系统默认录音是否被改掉 |
| 客户端 / 抖音抢设备 | 确认客户端 `auto` 为 Aux，抖音为 Output（B1）；勿都绑主 VAIO Output |
| AI 跟唱与 S1 同时怪声 | 关掉其中一条实时链；二者互斥 |
| S1 找不到 RVC | 复制整个 `RVCRealtime.vst3` 文件夹；重新扫描 VST3 |
| ENGINE 失败 | RVC ROOT 指向项目根；Python 环境正确 |
| 客户端没声 | `list_audio_devices.py` 核对 Aux；设置里选自动识别；hostapi 用 WASAPI |
| 歌词不动 | 是否 `osc`；防火墙 UDP 9000；S1 地址与 json 一致 |
| GPU 占满 | S1 插件与客户端不要同时开重负载引擎 |

---

## 八、与产品路线图关系

| 现阶段（外置） | 后期 1:1（客户端内） |
| --- | --- |
| 客户端 AI 唱歌 / AI 跟唱（VAD+成品） | 内置跟唱与修音完善 |
| S1 + RVC VST3 实时变声（可选） | 任务 9 内置实时路径 |
| VM 混音 + 抖音采 B1 | 内置混音面板 |
| S1 OSC 歌词 | 保留 OSC + 本机播放头 |
| 外置 VST 混响 | Phase 3+ 可选 VST3 宿主 |

总线约定（B2 干麦 / B1 直播 / Aux 处理）在迁到内置架构时仍适用。

---

## 九、相关文件

| 文件 | 说明 |
| --- | --- |
| `scripts/list_audio_devices.py` | 枚举设备并打印 `auto` 推荐（优先 Aux） |
| `config/client.json` | 音频（`auto`）/ 歌词 OSC |
| `app/audio/devices.py` | Voicemeeter 标记与 `pick_voicemeeter_defaults` |
| `RVCRealtimeVST/resources/README.txt` | VST 安装 |
| `RVCRealtimeVST/README.md` | 插件编译与开发 |
| `app/lyrics/osc_client.py` | OSC 监听 |
| `开发大纲.md` | 任务规划 |
