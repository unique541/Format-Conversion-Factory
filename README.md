---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 3b8ddf290b7a1c33bf8fdf1e3c983246_efe1285dd4dd11f1a0da525400393706
    ReservedCode1: t2LTiX3JVZAIUwfDq29YewQ54CNK5rLfJtrq52RLe986YtIBsV/jFQ8/MnGUT1QkdFVrhOUCOcMSH/cS5rZDW8mwy8Hyvl7Y65eE/c+fqGjaA1H3jOke3DC0iIUxEecbxR8Z7dE27yLsdD/KJlLVMGDW3dPFjA2MycEY9yO6flxSG4FKsZbNerg/j40=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 3b8ddf290b7a1c33bf8fdf1e3c983246_efe1285dd4dd11f1a0da525400393706
    ReservedCode2: t2LTiX3JVZAIUwfDq29YewQ54CNK5rLfJtrq52RLe986YtIBsV/jFQ8/MnGUT1QkdFVrhOUCOcMSH/cS5rZDW8mwy8Hyvl7Y65eE/c+fqGjaA1H3jOke3DC0iIUxEecbxR8Z7dE27yLsdD/KJlLVMGDW3dPFjA2MycEY9yO6flxSG4FKsZbNerg/j40=
---











# 格式转换工厂 (Format Conversion Factory) v2.5

轻量级桌面文件格式转换工具，图形化界面，图片 / 文档 / 音频三大类格式互转，**默认无损优先**，体积小、零额外框架负担。v2.0 新增音乐软件专属加密音频格式解密与互转、界面丝滑动画、配置持久化等能力；v2.1 增强 ffmpeg 检测与报错指引、新增酷狗 kgg（KGMv2）解密支持、统一滚动条等控件样式；v2.2 全面强化启动稳定性：修复依赖缺失（未安装 tkinterdnd2 / pydub / Pillow / reportlab 等）时启动即闪退的问题，最简环境下优雅降级、正常启动，缺失功能给出明确提示而非崩溃。**v2.3 全界面控件风格统一**：在滚动条基础上，将滑条、下拉框（含下拉列表）、输入框、进度条、列表、复选框、按钮等所有控件统一为蓝色圆角主题，无默认系统控件样式残留。**v2.4 修复 KGM 等加密格式转换**：加密格式参与同格式判定一律视为“不同格式”（兼容扩展名大小写，KGM/Kgm/kgm 均不再误报“已是目标格式”），且解密后输出文件扩展名一律按目标格式生成（如 out.flac / out.wav），绝不保留加密源后缀。**v2.5 输出命名彻底修复 + 新增反向转换**：所有音频转换路径（含加密源解密链路）输出文件后缀严格等于所选目标格式，文件已存在时自动重命名为 `原名_1.后缀 / 原名_2.后缀`（后缀仍为目标格式）；新增「普通音频 → 音乐软件专属格式」反向转换（KGM / KGMA / KGG / NCM / QMC0 / QMC2 / QMC3 / QMCFLAC / QMCOGG / KWM），加密方向与解密互为逆操作，明文可转专属格式、专属格式也可解密回明文，双向实测可逆。

## 一、功能总览

| 类别 | 支持格式 | 转换能力 | 附加设置 |
|---|---|---|---|
| 图片 | JPG / PNG / BMP / WebP / GIF / TIFF | 任意互转 | 转换后自定义宽高（可保持纵横比）、压缩开关 + 质量滑块 |
| 文档 | Word(.docx) / TXT / PDF | 任意互转 | 压缩开关（DOCX 重打包 / PDF 压缩内容流） |
| 音频 | MP3 / WAV / OGG / FLAC / M4A / AAC / WMA / APE / OPUS（输入）/ NCM / QMC0 / QMC3 / QMCFLAC / QMCOGG / MFLAC / MGG / KGM / KGMA / KGG / KWM（加密输入） | 任意互转；**双向**：普通↔专属格式 | 压缩开关 + 码率滑块（64-320kbps） |

主界面布局：
- **左侧**：大上传方框 —— 点击上传，或直接拖拽文件到框内（需安装可选依赖 tkinterdnd2）；下方为已添加文件列表。
- **右侧**：转换设置区 —— 目标格式下拉、图片尺寸、压缩选项、输出目录、开始转换按钮。
- **底部**：进度条 + 运行日志。

### 界面特性（v2.0）
- 上传框提示文字**自动换行/缩字号**，多行提示完整显示在框内，不再溢出。
- 「保持纵横比」「启用压缩」等复选框勾选后显示**对勾（✓）**而非叉号。
- **丝滑动画**：按钮悬停渐变变色、上传框悬停描边高亮、设置区显隐过渡、转换完成提示过渡（纯 tkinter 定时器实现，无重型动画库）。
- 上传框悬停时高亮描边，拖入文件时外框提示。

### 界面特性（v2.1）
- **滚动条等控件样式统一**：文件列表、日志区、设置面板滚动条统一为圆角蓝色滑块（主题主色）+ 浅色轨道，悬停高亮，与整体界面风格一致（ttk clam 主题化，日志区原生滚动条同步配色）。

### 界面特性（v2.3）
- **全界面控件风格统一（蓝色圆角主题）**：在 v2.1 滚动条基础上，本次将所有控件彻底统一，无默认系统控件残留：
  - **滑条（Scale）**：质量 / 码率滑条统一为主题蓝色滑块 + 浅色轨道，悬停高亮。
  - **下拉框（Combobox）**：目标格式下拉统一白底 + 深色文字 + 蓝色箭头；下拉列表（popdown）白底、浅蓝选中高亮、内部滚动条复用主题蓝色样式。
  - **输入框（Entry）**：输出目录 / 宽高输入统一白底、浅灰边框、聚焦主色描边。
  - **进度条（Progressbar）**：底部进度统一为主题蓝色填充 + 浅色轨道。
  - **列表（Listbox）**：文件列表统一浅灰底、深色文字、蓝色选中高亮、无系统虚线框（activestyle=none），与滚动条无缝衔接。
  - **复选框 / 按钮**：延续 v2.0 自定义样式（✓ 对勾、悬停渐变），整体协调。

## 二、安装与运行

### 0. 依赖一览（必装 / 可选）

| 依赖 | 是否必需 | 提供功能 | 缺失时表现（v2.2 起） |
|---|---|---|---|
| Python 3.8+（含 tkinter） | **必装** | 程序本体 | 无法运行（需安装 Python 并勾选 tcl/tk） |
| Pillow | **必装** | 图片转换 | 图片功能提示"缺少 Pillow"；程序仍正常启动 |
| python-docx | **必装** | Word 文档读写 | 文档功能提示"缺少 python-docx"；程序仍正常启动 |
| pypdf | **必装** | PDF 读写 | 文档功能提示"缺少 pypdf"；程序仍正常启动 |
| reportlab | **必装** | 生成 PDF | 文档功能提示"缺少 reportlab"；程序仍正常启动 |
| pydub | 可选 | 注入 ffmpeg 路径（仅音频相关辅助） | 自动跳过，不影响音频转换（音频直调 ffmpeg） |
| imageio-ffmpeg | 可选 | 内置 ffmpeg 二进制 | 未检测到 ffmpeg 时音频转换给出安装指引 |
| tkinterdnd2 | 可选 | 拖拽上传 | 自动降级为点击上传 |
| pycryptodome | 可选 | NCM 解密 | 仅 .ncm 文件无法解密，其余功能正常 |

> 说明：**图片转换需要 Pillow；文档转换需要 python-docx / pypdf / reportlab**；这些"必装"依赖在缺失时程序**仍会正常启动**（v2.2 起优雅降级），仅对应功能给出安装提示。若只做单一类型转换，可只安装对应依赖 + 必需项。

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 音频转换需要 ffmpeg（仅音频功能需要）

音频转换**直接调用 ffmpeg 命令行**完成编码（无需 pydub / ffprobe），这是最轻量可靠的方案。

- 推荐：`pip install imageio-ffmpeg`（程序自动使用其内置 ffmpeg 二进制）；
- 或安装系统 ffmpeg：Windows `winget install ffmpeg` / `choco install ffmpeg`，或从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载解压后把 `bin` 目录加入 PATH。
- 程序启动时自动检测（v2.1 增强）：
  1. `PATH` 中的 `ffmpeg` / `ffmpeg.exe`；
  2. 环境变量 `FFMPEG_BIN` / `FFMPEG_PATH`（指向 ffmpeg 可执行文件或所在目录）；
  3. 常见安装路径（如 `C:\ffmpeg\bin`、`D:\ffmpeg\bin`、Linux/macOS 的 `/usr/bin/ffmpeg` 等）；
  4. imageio-ffmpeg 内置二进制（自动安装并定位）。
- **所有音频格式转换（含加密格式解密后转码）都统一走 ffmpeg 检测与调用逻辑**，不再出现「mp3 可转、其他格式报未检测到 ffmpeg」的差异。
- 未检测到 ffmpeg 时，图片和文档转换不受影响；音频转换会给出**清晰指引**（含下载/安装/PATH/环境变量配置说明），而不是一句笼统报错。

### 3. 可选：启用拖拽上传

```bash
pip install tkinterdnd2
```

不安装时上传框仍可点击选择文件，功能不缺失。

### 4. 运行

```bash
python main.py
```

### 5. 启动排障（程序打开即闪退 / 自动退出）

> 以下要点基于 v2.2 修复：**正常情况下，即使未安装任何可选依赖（tkinterdnd2 / pydub / imageio-ffmpeg），甚至未安装图片/文档第三方库，程序也能正常启动**，只会在用到对应功能时给出安装提示。若仍然出现"刚打开就退出"，请按顺序排查：

| 现象 | 原因 | 处理 |
|---|---|---|
| 双击后窗口一闪而过，无任何提示 | 旧版本（< v2.2）在依赖缺失时无兜底，初始化异常直接退出 | 升级到 v2.2；`python -m py_compile main.py` 确认语法；命令行 `python main.py` 查看完整报错 |
| 提示"缺少 Pillow / python-docx / pypdf / reportlab" | 对应必装依赖未安装 | `pip install -r requirements.txt`（或只装对应包） |
| 提示"缺少 tkinterdnd2"或无法拖拽 | 可选依赖未安装 | 功能降级为点击上传；需要拖拽则 `pip install tkinterdnd2` |
| 音频转换提示"未检测到 ffmpeg" | 未安装 ffmpeg / imageio-ffmpeg | `pip install imageio-ffmpeg` 或安装系统 ffmpeg 并加入 PATH（见上方第 2 节） |
| `python main.py` 命令行报 `ImportError: No module named 'tkinter'` | Python 未安装 tcl/tk 组件 | 重新安装 Python 时勾选 tcl/tk，或系统安装 `python3-tk` |
| 命令行报 `AttributeError: 'NoneType' object has no attribute 'converter'` | 旧版本 pydub 缺失时 `_set_pydub_ffmpeg` 未判空 | 升级到 v2.2（已修复） |
| 命令行报其他 `AttributeError` / `ImportError` | 依赖版本不兼容或 Python 环境异常 | 将完整报错（traceback）贴出反馈；可先 `pip install --upgrade` 各依赖再试 |

**排查顺序建议**：
1. 命令行运行 `python main.py`，看是否有红色 traceback——闪退根因都在报错最后一行；
2. 确认依赖：`pip list` 对比上方依赖一览表；
3. 若命令行正常但双击闪退，检查快捷方式/启动脚本是否指向正确 Python 环境（如虚拟环境 venv 未激活）。

## 三、加密音频格式（ncm / qmc / kgm / kgg / kwm）

v2.0 内置**纯 Python 解密模块 `audio_decrypt.py`**，对主流音乐软件专属加密格式进行解密后再转换，拖拽与点击上传均接受这些格式。v2.1 新增酷狗 **kgg（KGMv2 加密）** 支持。

> **v2.4 加密格式同格式判定与输出命名修复**：
> - 加密格式（ncm/qmc/kgm/kgma/kgg/kwm 等）参与同格式比较时**一律返回“不是同一格式”**（兼容扩展名大小写，KGM / Kgm / kgm 均生效），因此选择任一目标格式都不会被误报“所选文件已是目标格式”而跳过转换；
> - 加密源解密后输出文件扩展名**一律按目标格式生成**（如 `song.kgm → song.flac / song.wav / song.mp3`），解密链路临时明文不会以 .kgm 后缀命名，最终产物始终是目标格式文件，可直接播放。

| 来源 | 格式 | 解密方式 | 限制 |
|---|---|---|---|
| 网易云音乐 | `.ncm` | AES-128 密钥派生 + RC4 流解密 + 元数据剥离，需 pycryptodome | 依赖 pycryptodome 库 |
| QQ 音乐 | `.qmc0/.qmc3/.qmflac/.qmcogg`（QMCv1） | 静态映射表（smb 表）逐字节异或还原 | 仅 QMCv1（旧版加密） |
| QQ 音乐 | `.mflac/.mgg`（QMCv2） | **不支持**：新版使用 4 字节版本标识 + 密钥难以静态推导 | 会给出明确错误提示 |
| 酷狗音乐 | `.kgm/.kgma` | 2 字节掩码查找表 + 16 字节块解交错还原 | 无 |
| 酷狗音乐 | `.kgg`（KGMv2） | 按 2 字节掩码查找表逐字节异或 + 16 字节块解交错还原（无版本/密钥区时直接静态还原；带密钥区时先解析版本头与掩码） | 完整解密依赖算法表；常见 kgg 可正常还原为 FLAC/WAV 后转码 |
| 酷我音乐 | `.kwm` | 3 字节表线性变换还原 | 无 |

> **说明**：解密仅针对文件加密层，不涉及任何会员权益破解；解密后得到的是文件本身包含的音频流，可正常转换为常见格式。由于版权原因，请只处理你本人拥有合法获取渠道的音频文件。

> **kgg（KGMv2）原理与限制（v2.1）**：
> - kgg 是酷狗音乐客户端新加密容器，与 kgm 同源但结构升级（可选版本头 + 密钥区 + 掩码区）。程序优先按 KGMv1 掩码表还原；无掩码/密钥区的样本直接按偏移异或解交错还原。
> - **限制**：部分带强密钥/动态掩码的 kgg（尤其新版本客户端下载的文件）可能无法 100% 还原；此时会回退为「剥离头 + 静态异或」的尽力还原，若还原后仍无法被 ffmpeg 识别将给出明确错误提示。该实现已通过 kgg→mp3 全链路实测。

### 反向转换：普通音频 → 专属格式（v2.5）

v2.5 起，目标格式下拉列表新增音乐软件专属格式作为**输出目标**，支持将普通明文音频（MP3 / WAV / FLAC / OGG / M4A / AAC / WMA / OPUS 等）封装为专属格式，与现有解密方向互为**逆操作**：`普通音频 → 专属格式 → 解密 → 原音频`，双向可逆（已实测通过）。

| 目标格式 | 来源 | 封装方式 | 可逆性 |
|---|---|---|---|
| `.kgm / .kgma` | 酷狗音乐 | 16 字节静态异或表循环加密 + 交错 | 本工具解密可完整还原 |
| `.kgg`（KGMv2） | 酷狗音乐 | 版本头 + 掩码流加密（简化变体） | 本工具解密可还原 |
| `.qmc0 / .qmc2 / .qmc3 / .qmcflac / .qmcogg` | QQ 音乐（QMCv1） | 按固定字节（0xAC 等）逐字节异或封装 | 本工具解密可完整还原 |
| `.kwm` | 酷我音乐 | 内嵌 key + 魔改 RC4 加密 | 本工具解密可完整还原 |
| `.ncm` | 网易云音乐 | 内嵌测试密钥的 AES/RC4 容器结构 | 本工具解密可完整还原 |

> **可行性边界（如实说明，不虚报功能）**：
> - 上述专属格式**反向封装使用本地内嵌密钥**（非平台真实私钥），生成的文件**结构完整、可被本工具自身解密还原为原音频**，但**不一定能被对应官方播放器（网易云 / QQ音乐 / 酷狗 / 酷我客户端）识别播放**。原因：官方客户端校验需要平台侧真实密钥/版权签名，本地无法获取。
> - 特别地：**NCM** 官方识别依赖平台密钥加密（真实 key box 由服务端下发），本工具生成的是"结构完整但使用测试密钥"的 ncm 文件，**官方播放器无法识别**；**QMCv2（mflac/mgg）** 依赖平台私钥，**不提供反向转换**（也不在输出目标列表中）。
> - 适用场景：个人本地归档 / 自建播放器兼容 / 格式结构研究。**请勿将生成的专属格式文件用于绕过版权保护或冒充正版渠道文件**；请仅处理你本人拥有合法获取渠道的音频。

## 四、输出目录与配置持久化（v2.0）

- 输出目录**默认系统下载文件夹**：Windows `%USERPROFILE%\Downloads`（macOS/Linux 相应 Downloads）。
- 用户在界面更改输出目录后，会自动写入配置文件持久化（Windows：`%APPDATA%\FormatConverterFactory\config.json`；macOS/Linux：`~/.config/FormatConverterFactory/config.json`），下次启动自动使用上次的目录。
- 配置项：`output_dir`（输出目录）、`target_format`（记忆上次目标格式）、压缩选项与码率等，修改即保存。

## 五、无损 / 压缩说明

程序默认**关闭压缩 = 无损优先**，各类型行为如下：

| 类型 | 无损模式（默认） | 压缩模式（手动开启） |
|---|---|---|
| 图片 | PNG/BMP 无损保存；WebP 无损编码(lossless)；JPEG 高质量 95 | JPEG/WebP 按质量滑块(5-100)有损压缩；PNG 无损优化(optimize)；TIFF 走 LZW 压缩 |
| 文档 | 不额外压缩 | DOCX 以 ZIP 最大压缩级别重新打包（无损）；PDF 压缩内容流（无损重构） |
| 音频 | WAV(PCM)/FLAC 完全无损；MP3/M4A/AAC/WMA 以最高码率 320kbps 编码（近似无损）；OGG 上限 192kbps、OPUS 上限 256kbps | 有损格式按码率滑块(64-320kbps)编码；WAV/FLAC 始终无损 |

> 提示：任何格式转换本身都可能引入理论上的编码差异（如 JPEG→PNG 后 PNG 是无损容器，但源 JPEG 已是压缩过的数据）。本工具保证「转换引擎层面不主动损失质量」。

## 六、已知限制（轻量方案的取舍）

1. **DOCX → PDF**：基于 reportlab 对文本重新排版（段落 + 表格文本），**图片、复杂样式、页眉页脚不保留**。中文字体自动使用系统字体（Windows：微软雅黑/宋体；macOS：苹方；Linux：文泉驿/Noto）。
2. **PDF → DOCX**：提取纯文本重建 Word 文档，**图片、表格结构、排版样式不保留**；扫描版 PDF（纯图片无文字层）无法提取文本。
3. **GIF/TIFF 多帧动画**：转换为其他格式时取**第一帧**；其他格式转 GIF 为静态 GIF。
4. **音频格式**：
   - **APE 仅支持作为输入**：ffmpeg 无内置 APE 编码器，无法输出 .ape 文件；
   - **MFLAC/MGG（QMCv2 加密）不支持解密**，其余加密格式解密依赖对应算法（见第三节）；
   - **kgg（KGMv2）解密为尽力还原**：依赖掩码算法表，强密钥/动态掩码样本可能无法完整还原（见第三节）；
   - **反向转换（普通→专属格式）生成的专属文件使用本地内嵌密钥，结构完整且可被本工具解密还原，但官方播放器可能无法识别**（尤其 NCM；QMCv2 类不提供反向转换，见第三节）；
   - WAV/FLAC 为无损；MP3/M4A/AAC/OGG/WMA 为有损格式，无损模式下以各自最高码率保证听感；OGG(Vorbis) 编码上限 192kbps、OPUS 上限 256kbps；
   - **NCM 解密依赖 pycryptodome**（requirements 已包含）。
5. 同名输出文件**自动重命名**（v2.5）：若目标目录已存在同名文件，自动追加序号生成 `原名_1.后缀 / 原名_2.后缀`（后缀恒为目标格式），**不会覆盖已有文件**（目标格式与源相同不会转换）。

## 七、项目结构

```
格式转换工厂/
├── main.py            # 程序主文件（GUI + 全部转换逻辑，单文件）
├── audio_decrypt.py   # 加密音频模块：解密方向（ncm/qmc/kgm/kgg/kwm）+ 反向封装方向（v2.5，明文→专属格式），纯 Python + pycryptodome
├── requirements.txt   # Python 依赖清单
└── README.md          # 本说明
```

## 八、体积说明

- Python 依赖均为轻量库：Pillow / python-docx / pypdf / reportlab / pycryptodome，总计约几十 MB 级别安装体积。
- 不捆绑 LibreOffice 等重型转换套件。
- ffmpeg 为可选外部二进制（或 imageio-ffmpeg 小体积内置包），仅在需要音频转换时使用。

