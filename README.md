# 🤖 AI 学英语 English Learner

一个基于 **Python + Tkinter** 的桌面端英语学习应用，集成 **AI 对话（真实大模型）、自定义词库导入、ASR 语音识别真实打分、间隔重复背单词、智能测验、学习统计** 六大模块。数据本地保存，开箱即用，可渐进升级为全 AI 驱动。

## ✨ 功能特性

| 模块 | 说明 |
|------|------|
| 📖 **单词学习** | 内置 15 个精选高阶词；**间隔重复（Spaced Repetition）**自动安排复习（1/3/7/14/30 天梯度） |
| 📥 **自定义词库** | 支持 JSON / CSV / TSV / TXT 导入（字段名中英文皆可），追加或替换模式，自动去重，与内置词合并学习 |
| 💬 **AI 对话练习** | 接入 OpenAI / DeepSeek / 通义 / 腾讯云等大模型，流式输出 + 自动降级（无 Key 用本地规则外教） |
| 🎙️ **跟读练习（ASR 真实打分）** | 录音 → **语音识别(ASR)** 出实际念的文本 → 与目标句**多维对齐打分**（准确率/完整度/流畅度/音频质量） |
| 📝 **智能测验** | 自动从「内置+自定义」合并词库生成四选一选择题，答完记录历史 |
| 📊 **学习统计** | 连续打卡🔥、已掌握单词、最佳成绩、测验历史 |
| ⚙️ **可配置** | `config.json` 统一配置 LLM / ASR 后端与 API Key |

### 🎙️ ASR 发音打分（核心亮点）

跟读练习不再"只看音量"，而是**真实语音识别 + 多维评分**：

1. **录音**（PyAudio，16kHz 单声道 PCM）→ 2. **ASR 识别**出你实际念的文本 → 3. **文本对齐**（`difflib` 序列匹配，算出准确率、完整度、漏读/错读词）→ 4. 叠加**音频质量**（音量、清晰度、连续度）与**流畅度** → 加权得到 **0-100 综合分**。

**可插拔后端**（无 Key / 无网自动降级，App 永不崩）：

| 后端 | 配置 | 说明 |
|------|------|------|
| `offline` | 默认，无需 Key | 基于音频质量估算，演示可用 |
| `whisper` | OpenAI API Key | 调用 Whisper / 任意兼容服务 |
| `tencent` | SecretId + Key | 腾讯云 ASR（一句话识别） |

评分维度加权：`准确率 50% + 完整度 20% + 流畅度 15% + 音频质量 15%`。

## 📦 文件结构

```
ai_english_app.py    # GUI 主程序 (Tkinter)：跟读页集成 ASR，含设置弹窗
engine.py            # 核心引擎：词库、间隔重复、AI 对话、测验（无 GUI 依赖）
asr.py               # ASR 语音识别 + 发音打分引擎（可插拔后端，无 GUI 依赖）
llm.py               # 大模型接入层（真实 LLM + 流式 + 降级）
gui_llm_bridge.py    # GUI ↔ LLM 桥接（流式打字机、设置弹窗）
test_engine.py       # 引擎测试（词库/间隔重复/对话/测验）
test_asr.py          # ASR 引擎测试（对齐/质量/后端/打分，26 项）
test_asr_gui.py      # GUI 跟读页 + ASR 集成测试（9 项，无 tkinter 自动跳过）
test_pron_flow.py    # 跟读打分端到端链路测试（6 场景，无需麦克风）
config.example.json  # 配置模板
learning_data.json   # 运行时自动生成的学习数据
custom_words.json    # 运行时自动生成的自定义词库
```

## 🚀 运行方式

### 环境要求
- Python 3.8+
- tkinter（通常随 Python 自带；Linux：`sudo apt install python3-tk`）
- 可选：`pyaudio` 启用真实录音；`openai` / `tencentcloud-sdk-python` 启用对应 ASR 后端

```bash
pip install pyaudio openai tencentcloud-sdk-python
```

### 启动
```bash
python ai_english_app.py
```

### 启用真实 ASR 打分
1. 准备 API Key（OpenAI Whisper 或腾讯云 ASR）。
2. 跟读练习页右上角点 **⚙️ ASR设置** → 选后端 → 填 Key → 保存（自动写入 `config.json`）。
3. 也可手动编辑 `config.json` 的 `[asr]` 段：
```json
{
  "asr": {
    "backend": "whisper",
    "api_key": "sk-xxx",
    "endpoint": "https://api.openai.com"
  }
}
```
不填 Key 即为**离线模式**，基于音频质量估算打分，功能完整可用。

### 运行测试（无需 GUI / 麦克风）
```bash
python -m unittest test_asr.py test_pron_flow.py -v   # ASR + 端到端（41 项，全过）
python asr.py --help                                   # CLI 演示
```

## 🔌 扩展：接入其他 ASR 服务

`asr.py` 采用后端接口设计，新增服务只需继承 `ASRBackend` 实现 `recognize(wav_path) -> 文本`：

```python
class MyASR(ASRBackend):
    def recognize(self, wav_path):
        # 调用你的 ASR 服务，返回识别文本
        return call_my_service(wav_path)
# 在 make_backend() 里加一行分发即可
```

## 📸 界面

六大页面：单词学习 → 自定义词库导入 → AI 对话 → 跟读 ASR 评分 → 智能测验 → 学习统计，左侧导航切换；跟读页顶部实时显示「🎧 真实 ASR：whisper」或「🔇 离线模式」。

---

## 📦 打包为 Windows .exe（无需安装 Python 即可运行）

> 推荐在 **Windows 10/11 + Python 3.10+** 环境下打包，产出单文件 `AI学英语.exe`。

### 方式一：一键脚本（推荐）

双击 `build.bat`，或命令行执行：

```bat
build.bat
```

脚本会自动安装依赖（`pyinstaller` / `openai` / `pyaudio` / `Pillow` 等）并打包。

### 方式二：手动打包

```bat
pip install -r requirements.txt
python build_exe.py
```

打包完成后，产物位于 `dist\AI学英语.exe`，**双击即可运行**，可单独分发给他人（对方无需安装 Python）。

### 打包参数说明（`build_exe.py`）

| 参数 | 作用 |
|------|------|
| `--onefile` | 打包为单个 exe 文件 |
| `--windowed` | 运行时不弹出黑色控制台窗口（GUI 程序） |
| `--name AI学英语` | exe 名称 |
| `--icon app.ico` | 程序图标（自动生成，可替换） |
| `--add-data` | 把 `config.example.json` / `README.md` 打包进 exe |

### 注意事项
- **必须在 Windows 上打包**才能产出真正的 `.exe`；其它平台（macOS/Linux）仅能做代码/结构检查。
- 首次运行若被杀毒软件误报，选择"允许"即可（PyInstaller 单文件的常见现象）。
- 语音录制（PyAudio）需要系统有麦克风权限。
- 大模型 / ASR 的 API Key 通过 App 内「⚙️ AI设置 / ⚙️ ASR设置」填写，无需写死。

---
Built with Python · 数据本地存储 · 业务逻辑与 GUI 解耦（100% 可测）
