# LingtiStudio

Lingti 在中文里是“灵缇”，也就是速度极快的灰狗。  
**LingtiStudio** 的目标不只是“生成一个视频”，而是帮助你更快地把一个想法变成一整条完整的视频生产流程。

从一个主题出发，LingtiStudio 可以把流程串起来：

**脚本 -> 审核 -> 关键帧 -> 配音 -> 视频片段 -> 组装 -> 成片**

它既适合短视频，也适合更长、分镜更多、需要审核与恢复能力的 AI 视频生产场景。

[English README](./README.md)

---

## 截图

<table>
  <tr>
    <td width="33.33%">
      <img src="./screenshots/index_page.png" alt="LingtiStudio 首页" />
    </td>
    <td width="33.33%">
      <img src="./screenshots/video_gen_page.png" alt="LingtiStudio 视频生成页" />
    </td>
    <td width="33.33%">
      <img src="./screenshots/video_done_page.png" alt="LingtiStudio 成片结果页" />
    </td>
  </tr>
  <tr>
    <td align="center"><strong>首页</strong></td>
    <td align="center"><strong>视频生成工作台</strong></td>
    <td align="center"><strong>成片结果页</strong></td>
  </tr>
</table>

---

## 项目简介

LingtiStudio 是一个适合本地运行的开源 AI 视频生产系统。

它不是把几个脚本随便拼在一起，而是把整条生成链路尽量做成“一个产品”：

- 文案 / 选题生成脚本
- 人工审核分镜
- 关键帧图片生成
- TTS 配音
- 图生视频
- FFmpeg 拼接成片
- 字幕导出
- 剪映 / CapCut 草稿生成

你可以用它来做：

- 短视频内容
- 广告风格视频
- 讲解类视频
- 多分镜故事视频
- 更长的视频项目

它更适合“可恢复、可审核、可排错”的创作流程，而不是一次性黑盒生成。

---

## 为什么它更像生产系统

很多 AI 视频产品擅长的是“给你一个结果”。  
LingtiStudio 更强调的是“给你一条完整流程”。

它重点解决的是：

- **可审核**：高成本生成前先看脚本和分镜
- **可恢复**：从脚本、视频阶段或组装阶段继续，而不是从头重来
- **一致性**：让音色、风格、画幅、提示词在多分镜里尽量保持统一
- **更适合长流程**：比起单次 prompt，更适合处理多场景、长一点的视频项目
- **本地可控**：配置、产物、字幕、草稿都在你自己的机器上

---

## 全流程一键化

LingtiStudio 的核心价值，是把长视频 / 多分镜 AI 生成流程尽量一键化：

1. 从主题或对标分析生成脚本
2. 在网页里审核并修改分镜
3. 为每个分镜生成关键帧
4. 为每个分镜生成配音
5. 用 Kling 或 Seedance 生成视频片段
6. 自动组装转场、音频、字幕与最终成片
7. 导出 MP4、字幕文件、剪映 / CapCut 草稿

也就是说，它不是只帮你“生成一段视频”，而是帮你把从脚本到成片的整条 AI 视频工作流整合起来。

---

## 当前技术栈

- 后端：FastAPI
- 前端：Next.js + Ant Design
- LLM：DeepSeek / MiniMax / Gemini / OpenAI / Kimi / Zhipu / Ollama
- 图片：MiniMax Image / Gemini 生图
- 视频：Kling / Seedance
- 配音：MiniMax
- 拼接：FFmpeg

---

## 支持的模型

下面这张表对应的是当前网页 Setup 和运行时配置里内置暴露的 provider / model 选项。

| 阶段 | Provider | 内置模型 |
| --- | --- | --- |
| 脚本 / 规划 | MiniMax | `MiniMax-M2.5`, `MiniMax-M2.7` |
| 脚本 / 规划 | DeepSeek | `deepseek-chat`, `deepseek-reasoner` |
| 脚本 / 规划 | Moonshot Kimi | `moonshot-v1-8k`, `moonshot-v1-32k` |
| 脚本 / 规划 | Zhipu | `glm-4`, `glm-4-air` |
| 脚本 / 规划 | Gemini | `gemini-2.5-flash`, `gemini-1.5-pro` |
| 脚本 / 规划 | OpenAI | `gpt-4o`, `gpt-4.1-mini` |
| 脚本 / 规划 | Ollama | `qwen2.5:latest`, `llama3.1:8b` |
| 关键帧生图 | MiniMax Image | `image-01` |
| 关键帧生图 | Nano Banana / Gemini Image | `gemini-2.0-flash-preview-image-generation`, `gemini-3-pro-image-preview` |
| 配音 / TTS | MiniMax TTS | `speech-2.8-hd`, `speech-02-hd` |
| 视频片段生成 | Kling | `kling-v3` |
| 视频片段生成 | Seedance | `doubao-seedance-1-5-pro-250528`, `Doubao-Seedance-1.0-pro` |
| 组装 / 字幕 / 导出 | 本地 FFmpeg | 取决于本机环境 |

说明：
- 网页里展示的是当前内置的推荐选项；如果你需要，也可以手动编辑 `configs/config.yaml`。
- 当前只有 MiniMax 在前端里提供内置音色目录和试听能力。
- 最终组装依赖本地 FFmpeg，所以字幕烧录和部分转场是否可用，取决于你的 FFmpeg 构建能力。

---

## 首次使用

当网页检测到缺少必要配置时，会自动弹出配置窗口。

你可以直接在网页里选择并配置：

- 默认 LLM provider 与 model
- 图片 provider 与 model
- 视频 provider 与 model
- TTS model
- 对应服务的 API Key

网页保存后的配置默认写入：

```bash
configs/config.yaml
```

如果你更喜欢手动配置，也可以先复制示例文件：

```bash
cp configs/config.example.yaml configs/config.yaml
```

---

## 快速开始

### 1. 依赖要求

- Python 3.10+
- Node.js 18+
- 已安装 FFmpeg，并且可在 PATH 中访问

验证 FFmpeg：

```bash
ffmpeg -version
```

### 2. 安装

```bash
git clone https://github.com/ruilisi/LingtiStudio.git
cd LingtiStudio

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
yarn install
cd ..
```

### 3. 启动后端

```bash
.venv/bin/python -m uvicorn api.server:app --host 0.0.0.0 --port 8000
```

### 4. 启动前端

```bash
cd frontend
yarn dev --port 3001
```

打开：

```text
http://127.0.0.1:3001
```

如果配置不完整，系统会自动弹出引导配置窗口。

---

## Docker

LingtiStudio 现在也提供面向 release 的 Docker 方案，用户可以先把产品跑起来，再在浏览器里完成 API token 配置。

### 方案 1：Docker Compose

```bash
docker compose up -d --build
```

启动后打开：

```text
http://localhost:3000
```

首次使用时：
- LingtiStudio 会自动弹出网页配置窗口
- 用户可以直接在浏览器里选择 provider 和 model
- API token 会写入 `./configs/config.yaml`
- 输出文件、上传素材和本地运行数据会落在 `./data`

默认端口：
- Web UI：`3000`
- API：`8000`

### 方案 2：单 Docker 镜像

构建镜像：

```bash
docker build -t lingtistudio:latest .
```

运行：

```bash
docker run --rm \
  -p 3000:3000 \
  -p 8000:8000 \
  -v "$(pwd)/configs:/app/configs" \
  -v "$(pwd)/data:/app/data" \
  --name lingtistudio \
  lingtistudio:latest
```

然后打开：

```text
http://localhost:3000
```

这条路径适合开源 release 场景：
- 一个镜像即可启动
- 通过浏览器完成首次配置
- 配置和产物都能持久化到宿主机

---

## CLI 用法

直接用命令行发起视频任务：

```bash
.venv/bin/python cli/main.py run --topic "上海附近现代养老酒店，40 秒，横版介绍视频"
```

测试各模块连接情况：

```bash
.venv/bin/python cli/main.py test --module llm
.venv/bin/python cli/main.py test --module image
.venv/bin/python cli/main.py test --module tts
.venv/bin/python cli/main.py test --module video
```

---

## Web 界面

主要页面：

- `/` 首页
- `/create` 快速生成
- `/studio` 专业工作台
- `/analyze` 对标视频分析
- `/settings` 配置与连接器

主要能力：

- 首次使用自动弹出配置
- 更友好的 provider / model 配置界面
- 分镜审核后再继续生成
- 支持中断恢复
- 实时控制台日志
- 成片、字幕、剪映草稿下载

---

## 关于音色选择

当前内置音色目录和试听能力只对 **MiniMax TTS** 生效。

如果当前 TTS provider 不是 MiniMax，前端不会再展示 MiniMax 音色选择框，而是切换为：

- 手动填写 `voice_id`

这样即使你使用自定义或外部维护的 voice_id 方案，界面也不会误导你去选一个不适用的 MiniMax 音色。

---

## 目录结构

```text
api/                FastAPI 后端
cli/                命令行入口
core/               配置加载和共享设置
modules/            LLM / 图片 / TTS / 视频 / 组装模块
frontend/           Next.js 前端
configs/            示例配置和本地配置
data/               输出、上传、缓存等运行数据
```

---

## 说明

- 这个项目当前更偏向本地创作工作流，而不是多租户 SaaS。
- 某些 provider 已经能在界面层配置，但后端仍然以当前已接好的能力为主。
- FFmpeg 功能依赖你的本地构建。如果本机不支持字幕烧录，LingtiStudio 仍然可以输出 MP4 + SRT。

---

## License

MIT
