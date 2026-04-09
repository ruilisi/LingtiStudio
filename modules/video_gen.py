"""
噼哩噼哩 Pilipili-AutoVideo
视频生成模块 - Kling Omni / Kling v3 / Seedance 1.5

v2.0 改动：
- 新增 Kling Omni API（/v1/videos/omni-video）支持
  - 多镜头模式（multi_shot=true，最多6个分镜一次调用）
  - 多参考图（image_list，最多3个主体）
  - 首尾帧控制（first_frame_image + end_frame_image）
  - 文生视频（无参考图）
- 新增 shot_mode 自动判断逻辑
  - multi_ref：有固定人物 + 动作场景 → Omni 多参考生视频
  - first_end_frame：场景转换/运镜 → Omni 首尾帧生视频
  - t2v：纯风景/氛围 → Omni 文生视频
  - i2v：兼容旧版图生视频（默认回退）
- 保留 Seedance 1.5 作为备选引擎
"""

import os
import asyncio
import aiohttp
import json
import time
import jwt
import base64
import requests
import subprocess
import tempfile
import hashlib
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime

from core.config import PilipiliConfig, get_config
from modules.llm import Scene


# ============================================================
# shot_mode 类型定义
# ============================================================

ShotMode = Literal["multi_ref", "first_end_frame", "t2v", "i2v"]
_CDN_UPLOAD_LOCK: Optional[asyncio.Lock] = None


def auto_detect_shot_mode(scene: Scene) -> ShotMode:
    """
    根据分镜内容自动判断最优的生成模式

    判断规则：
    - 有角色参考图 + 有人物动作 → multi_ref（Omni 多参考生视频）
    - 有首尾帧关键词（转场/运镜/过渡）→ first_end_frame（Omni 首尾帧）
    - 纯风景/氛围/无人物 → t2v（Omni 文生视频）
    - 其他（默认）→ i2v（传统图生视频，兼容旧版）
    """
    # 如果 scene 已经有 shot_mode 字段，直接使用
    if hasattr(scene, "shot_mode") and scene.shot_mode:
        return scene.shot_mode

    prompt_lower = (scene.video_prompt + " " + scene.image_prompt + " " + " ".join(scene.style_tags)).lower()

    # 有角色参考图 → 优先使用 multi_ref
    if scene.reference_character:
        return "multi_ref"

    # 转场/运镜/过渡关键词 → first_end_frame
    transition_keywords = [
        "transition", "morph", "transform", "cut to", "fade to",
        "time lapse", "timelapse", "time-lapse", "dissolve",
        "转场", "过渡", "变换", "延时", "时光流逝"
    ]
    if any(kw in prompt_lower for kw in transition_keywords):
        return "first_end_frame"

    # 纯风景/氛围/无人物 → t2v
    landscape_keywords = [
        "landscape", "scenery", "nature", "sky", "ocean", "mountain",
        "forest", "sunset", "sunrise", "clouds", "aerial", "drone",
        "风景", "自然", "天空", "海洋", "山脉", "森林", "日落", "日出",
        "云彩", "航拍", "无人机", "空镜"
    ]
    person_keywords = [
        "person", "people", "man", "woman", "character", "figure",
        "人物", "人", "男", "女", "角色", "主角"
    ]
    has_landscape = any(kw in prompt_lower for kw in landscape_keywords)
    has_person = any(kw in prompt_lower for kw in person_keywords)

    if has_landscape and not has_person:
        return "t2v"

    # 默认回退到传统 i2v
    return "i2v"


# ============================================================
# 视频引擎路由逻辑
# ============================================================

def smart_route_engine(scene: Scene, default: str = "kling") -> str:
    """
    根据场景内容智能选择视频引擎

    规则：
    - 包含对话/口型同步关键词 → Seedance（原生音素级口型同步）
    - 包含多人/多角色场景 → Seedance（多主体一致性更强）
    - 包含动作/运动/体育 → Kling（动态能量更强）
    - 其他 → 使用默认引擎
    """
    seedance_keywords = [
        "talking", "speaking", "dialogue", "conversation", "lip sync",
        "multiple characters", "crowd", "group", "people talking",
        "interview", "narration", "说话", "对话", "多人", "人群"
    ]

    kling_keywords = [
        "action", "running", "jumping", "sports", "explosion", "fast",
        "dynamic", "energetic", "chase", "fight", "dance",
        "动作", "奔跑", "跳跃", "运动", "爆炸", "快速", "舞蹈"
    ]

    prompt_lower = (scene.video_prompt + " " + " ".join(scene.style_tags)).lower()

    seedance_score = sum(1 for kw in seedance_keywords if kw.lower() in prompt_lower)
    kling_score = sum(1 for kw in kling_keywords if kw.lower() in prompt_lower)

    if seedance_score > kling_score:
        return "seedance"
    elif kling_score > seedance_score:
        return "kling"
    else:
        return default


# ============================================================
# Kling JWT 认证
# ============================================================

def _generate_kling_jwt(api_key: str, api_secret: str) -> str:
    """生成 Kling API JWT Token（遵循官方文档，显式传 headers）"""
    jwt_headers = {
        "alg": "HS256",
        "typ": "JWT",
    }
    payload = {
        "iss": api_key,
        "exp": int(time.time()) + 1800,
        "nbf": int(time.time()) - 5,
    }
    return jwt.encode(payload, api_secret, algorithm="HS256", headers=jwt_headers)


def _image_to_base64(image_path: str) -> str:
    """将图片转为纯 base64 字符串（不含 data URI 前缀）"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _image_to_data_url(image_path: str) -> str:
    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(ext, "image/png")
    return f"data:{mime_type};base64,{_image_to_base64(image_path)}"


def _resolve_minimax_video_api_key(config: PilipiliConfig) -> str:
    return (config.video_gen.minimax.api_key or config.llm.minimax.api_key or "").strip()


def _map_minimax_resolution(resolution: Optional[str]) -> str:
    if not resolution:
        return "1080P"
    normalized = resolution.strip().lower()
    if normalized == "720p":
        return "768P"
    if normalized == "4k":
        return "1080P"
    return "1080P"


# ============================================================
# Kling Omni API（v2.0 新增）
# ============================================================

def _build_omni_prompt(
    scene: Scene,
    shot_mode: str,
    reference_images: Optional[list[str]] = None,
    image_index_offset: int = 0,
) -> tuple[str, list[str]]:
    """
    构建 Kling Omni 导演式提示词，使用 <<<image_N>>> 格式引用参考图

    Returns:
        (prompt_text, image_b64_list)
        - prompt_text: 包含 <<<image_1>>> 等占位符的提示词
        - image_b64_list: 对应的 base64 图片列表（按顺序）
    """
    image_b64_list = []
    image_refs = []  # 用于收集 <<<image_N>>> 引用

    # 收集参考图（角色参考优先）
    ref_paths = []
    if scene.character_refs:
        ref_paths.extend(scene.character_refs[:3])
    elif scene.reference_character and os.path.exists(scene.reference_character):
        ref_paths.append(scene.reference_character)
    elif reference_images:
        ref_paths.extend([p for p in reference_images[:3] if os.path.exists(p)])

    for i, ref_path in enumerate(ref_paths):
        idx = image_index_offset + i + 1
        image_b64_list.append(_image_to_base64(ref_path))
        image_refs.append(f"<<<image_{idx}>>>")

    # 构建导演式提示词
    # 格式：[全局背景] + [主体引用] + [时序动作] + [运镜]
    base_prompt = scene.video_prompt

    if image_refs and shot_mode == "multi_ref":
        # 导演式结构：将角色引用嵌入提示词
        char_ref_str = " and ".join(image_refs)
        prompt = (
            f"{base_prompt}. "
            f"Main character: {char_ref_str}. "
            f"Maintain character consistency throughout all shots."
        )
    else:
        prompt = base_prompt

    return prompt, image_b64_list


async def _upload_image_to_cdn(
    image_path: str,
    session: aiohttp.ClientSession,
    aspect_ratio: str = "9:16",
) -> str:
    """
    将本地图片压缩后上传到 catbox.moe 免费 CDN，返回可公开访问的 URL。
    纯 Python + HTTP 实现，Windows / Linux 均兼容。
    catbox.moe 文件永久保存，无需账号，支持最大 200MB。
    """
    import io as _io
    from PIL import Image as _PILImage

    # 根据 aspect_ratio 决定压缩目标尺寸
    if aspect_ratio in ("9:16", "3:4"):
        max_size = (540, 960)  # 竖屏
    else:
        max_size = (960, 540)  # 横屏

    # 压缩图片，JPEG quality=75，确保上传快速
    img = _PILImage.open(image_path)
    img.thumbnail(max_size, _PILImage.LANCZOS)
    buf = _io.BytesIO()
    img.save(buf, "JPEG", quality=75)
    if buf.tell() > 400 * 1024:  # 超过 400KB 继续降质量
        buf = _io.BytesIO()
        img.save(buf, "JPEG", quality=55)
    buf.seek(0)

    upload_bytes = buf.read()
    digest = hashlib.sha256(upload_bytes).hexdigest()[:16]
    cache_path = f"{image_path}.{digest}.cdn_url"

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            cached_url = f.read().strip()
        if cached_url.startswith("http"):
            return cached_url

    async def _upload_once_with_aiohttp() -> str:
        form = aiohttp.FormData()
        form.add_field("reqtype", "fileupload")
        form.add_field("fileToUpload", upload_bytes, filename="frame.jpg", content_type="image/jpeg")
        async with session.post(
            "https://catbox.moe/user/api.php",
            data=form,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            cdn_url = (await resp.text()).strip()
        if not cdn_url.startswith("http"):
            raise RuntimeError(f"catbox.moe 返回异常: {cdn_url[:200]}")
        return cdn_url

    def _upload_once_with_requests() -> str:
        requests_session = requests.Session()
        requests_session.trust_env = False
        response = requests_session.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": ("frame.jpg", upload_bytes, "image/jpeg")},
            timeout=30
        )
        response.raise_for_status()
        cdn_url = response.text.strip()
        if not cdn_url.startswith("http"):
            raise RuntimeError(f"catbox.moe 返回异常: {cdn_url[:200]}")
        return cdn_url

    def _upload_once_with_curl() -> str:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(upload_bytes)
                tmp_path = tmp.name
            result = subprocess.run(
                [
                    "curl",
                    "--proxy",
                    "",
                    "--http1.1",
                    "-sS",
                    "--retry",
                    "3",
                    "--retry-delay",
                    "2",
                    "--connect-timeout",
                    "15",
                    "--max-time",
                    "45",
                    "-A",
                    "Mozilla/5.0",
                    "-F",
                    "reqtype=fileupload",
                    "-F",
                    f"fileToUpload=@{tmp_path};type=image/jpeg",
                    "https://catbox.moe/user/api.php",
                ],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or f"curl exit {result.returncode}")
            cdn_url = result.stdout.strip()
            if not cdn_url.startswith("http"):
                raise RuntimeError(f"catbox.moe 返回异常: {cdn_url[:200]}")
            return cdn_url
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    global _CDN_UPLOAD_LOCK
    if _CDN_UPLOAD_LOCK is None:
        _CDN_UPLOAD_LOCK = asyncio.Lock()

    last_error = None
    async with _CDN_UPLOAD_LOCK:
        for attempt in range(1, 6):
            try:
                url = await _upload_once_with_aiohttp()
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(url)
                return url
            except Exception as aiohttp_error:
                last_error = f"aiohttp: {aiohttp_error}"
                try:
                    url = await asyncio.to_thread(_upload_once_with_requests)
                    with open(cache_path, "w", encoding="utf-8") as f:
                        f.write(url)
                    return url
                except Exception as requests_error:
                    last_error = f"{last_error}; requests: {requests_error}"
                    try:
                        url = await asyncio.to_thread(_upload_once_with_curl)
                        with open(cache_path, "w", encoding="utf-8") as f:
                            f.write(url)
                        return url
                    except Exception as curl_error:
                        last_error = f"{last_error}; curl: {curl_error}"
                        if attempt < 5:
                            await asyncio.sleep(min(attempt * 2, 8))

    raise RuntimeError(f"图片上传 CDN 失败: {last_error}")


def _create_http_session() -> aiohttp.ClientSession:
    # 对外部 API 直连，避免误走本地失效代理；同时限制长时间悬挂连接。
    timeout = aiohttp.ClientTimeout(total=900, connect=30, sock_connect=30, sock_read=300)
    connector = aiohttp.TCPConnector(ttl_dns_cache=300)
    return aiohttp.ClientSession(timeout=timeout, trust_env=False, connector=connector)


async def _submit_kling_omni(
    scenes: list[Scene],
    image_paths: dict[int, str],
    config: PilipiliConfig,
    session: aiohttp.ClientSession,
    reference_images: Optional[list[str]] = None,
    aspect_ratio: Optional[str] = None,
) -> str:
    """
    提交 Kling Omni 多镜头任务（修复版），返回 task_id

    修复要点（基于官方文档）：
    - model_name: "kling-v3-omni"（多镜头专用，支持 multi_shot）
    - multi_shot: true + shot_type: "customize"（自定义分镜，需传 multi_prompt）
    - multi_prompt 中 duration 必须是字符串（"3" 等）
    - 所有分镜时长之和 = 顶层 duration，最大 15s（kling-v3-omni 支持）
    - image_list 使用公开 URL（先压缩图片再上传，避免 base64 过大导致超时）
    - 无需 negative_prompt / cfg_scale / resolution（Omni 接口不支持这些字段）
    - 不降级！Omni 失败直接抛异常
    """
    from PIL import Image as PILImage

    api_key = config.video_gen.kling.api_key
    api_secret = config.video_gen.kling.api_secret

    if not api_key or not api_secret:
        raise ValueError("Kling API Key/Secret 未配置")

    token = _generate_kling_jwt(api_key, api_secret)

    # 收集所有分镜的关键帧图片，压缩后上传到 catbox.moe CDN，获取公开 URL
    # Kling Omni 要求 image_list 使用公开 URL（image_url），不接受 base64
    image_list = []
    image_path_to_idx = {}  # path -> 1-based index

    for scene in scenes:
        kf_path = image_paths.get(scene.scene_id)
        if kf_path and os.path.exists(kf_path) and kf_path not in image_path_to_idx:
            idx = len(image_list) + 1
            image_path_to_idx[kf_path] = idx

            # 上传到 catbox.moe CDN，获取公开 URL（纯 Python，Windows 兼容）
            _ar = aspect_ratio or config.video_gen.kling.default_ratio or "9:16"
            cdn_url = await _upload_image_to_cdn(kf_path, session, aspect_ratio=_ar)
            image_list.append({"image_url": cdn_url})

    # 构建 multi_prompt 列表（每个分镜一条）
    # Kling Omni 规则（基于官方文档）：
    # - kling-v3-omni 支持最长 15s（相比 o1 的 10s 延长）
    # - 顶层 duration = 所有分镜时长之和，取值范围 3~15（字符串）
    # - multi_prompt 中每个分镜必须传 duration（字符串）
    # - 最多支持 6 个分镜
    num_scenes = len(scenes)
    # kling-v3-omni 支持最长 15s，每个分镜最少 3s
    # 关键约束：multi_prompt 中各分镜 duration 之和必须严格等于顶层 duration
    # 做法：先算出顶层 total_duration（限制在 3~15s），再均分给每个分镜
    # 均分时用整数除法，余数加到最后一个分镜，确保严格相等
    ideal_total = num_scenes * 3
    total_duration = max(3, min(15, ideal_total))
    total_duration_str = str(total_duration)

    # 将 total_duration 均分给 num_scenes 个分镜
    base_dur = total_duration // num_scenes          # 每个分镜的基础时长（整数）
    remainder = total_duration - base_dur * num_scenes  # 余数加到最后一个分镜
    scene_durs = [base_dur] * num_scenes
    scene_durs[-1] += remainder  # 最后一个分镜承接余数，保证总和严格相等

    multi_prompt = []
    for i, scene in enumerate(scenes):
        # 构建提示词：如果有对应关键帧，用 <<<image_N>>> 引用
        kf_path = image_paths.get(scene.scene_id)
        if kf_path and kf_path in image_path_to_idx:
            img_ref = f"<<<image_{image_path_to_idx[kf_path]}>>>"
            prompt = f"{img_ref} {scene.video_prompt}"
        else:
            prompt = scene.video_prompt

        # 截断提示词到 512 字符（官方限制）
        prompt = prompt[:512]

        multi_prompt.append({
            "index": i + 1,
            "prompt": prompt,
            "duration": str(scene_durs[i]),  # 必须传，字符串格式，且总和 == total_duration
        })

    payload = {
        "model_name": "kling-v3-omni",   # 多镜头专用模型，支持最长 15s
        "multi_shot": True,
        "shot_type": "customize",          # customize = 自定义分镜（需传 multi_prompt）
        "prompt": "",                      # multi_shot=true 时顶层 prompt 无效
        "multi_prompt": multi_prompt,
        "image_list": image_list,          # 关键帧图片列表（公开 URL）
        "mode": "pro",
        "aspect_ratio": aspect_ratio or config.video_gen.kling.default_ratio or "9:16",
        "duration": total_duration_str,    # 各分镜时长之和，3~15s
    }

    url = f"{config.video_gen.kling.base_url}/v1/videos/omni-video"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with session.post(url, json=payload, headers=headers) as resp:
        resp_text = await resp.text()
        try:
            result = json.loads(resp_text)
        except json.JSONDecodeError:
            raise RuntimeError(f"Kling Omni API 返回非 JSON 响应 (HTTP {resp.status}): {resp_text[:200]}")

    if result.get("code") != 0:
        raise RuntimeError(
            f"Kling Omni 任务提交失败 (code={result.get('code')}, msg={result.get('message')}): {resp_text[:500]}"
        )

    return result["data"]["task_id"]


async def _poll_kling_omni_task(
    task_id: str,
    config: PilipiliConfig,
    session: aiohttp.ClientSession,
    timeout: int = 900,
    poll_interval: int = 10,
) -> list[str]:
    """
    轮询 Kling Omni 任务状态，返回视频 URL 列表（多镜头）

    Returns:
        list[str]: 按分镜顺序排列的视频 URL 列表
    """
    api_key = config.video_gen.kling.api_key
    api_secret = config.video_gen.kling.api_secret

    url = f"{config.video_gen.kling.base_url}/v1/videos/omni-video/{task_id}"
    start_time = time.time()

    while time.time() - start_time < timeout:
        token = _generate_kling_jwt(api_key, api_secret)
        headers = {"Authorization": f"Bearer {token}"}

        async with session.get(url, headers=headers) as resp:
            resp_text = await resp.text()
            try:
                result = json.loads(resp_text)
            except json.JSONDecodeError:
                raise RuntimeError(f"Kling Omni 轮询返回非 JSON 响应 (HTTP {resp.status}): {resp_text[:200]}")

        if result.get("code") != 0:
            raise RuntimeError(
                f"Kling Omni 任务查询失败 (code={result.get('code')}, msg={result.get('message')}): {result}"
            )

        status = result["data"]["task_status"]

        if status == "succeed":
            videos = result["data"]["task_result"]["videos"]
            if videos:
                return [v["url"] for v in videos]
            raise RuntimeError("Kling Omni 任务成功但无视频 URL")

        elif status == "failed":
            raise RuntimeError(f"Kling Omni 任务失败: {result['data'].get('task_status_msg', '未知错误')}")

        elapsed = int(time.time() - start_time)
        print(f"[VideoGen] Omni 任务 {task_id} 状态: {status} ({elapsed}s/{timeout}s)")
        await asyncio.sleep(poll_interval)

    raise TimeoutError(f"Kling Omni 任务 {task_id} 超时（{timeout}s）")


# ============================================================
# Kling v3 API（旧版，单镜头图生视频，保留作为回退）
# ============================================================

async def _submit_kling_i2v(
    image_path: str,
    scene: Scene,
    config: PilipiliConfig,
    session: aiohttp.ClientSession,
    resolution: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
) -> str:
    """提交 Kling v3 I2V 任务，返回 task_id（旧版接口，作为 Omni 回退）"""
    api_key = config.video_gen.kling.api_key
    api_secret = config.video_gen.kling.api_secret

    if not api_key or not api_secret:
        raise ValueError("Kling API Key/Secret 未配置")

    token = _generate_kling_jwt(api_key, api_secret)
    img_b64 = _image_to_base64(image_path)

    duration = 5 if scene.duration <= 7 else 10
    # 优先使用传入的 resolution，否则从配置推导
    if resolution is None:
        quality = config.video_gen.kling.default_quality or "high"
        resolution = "1080p" if quality == "high" else "720p"

    payload = {
        "model_name": config.video_gen.kling.model or "kling-v3",
        "image": img_b64,
        "prompt": scene.video_prompt,
        "negative_prompt": "blurry, low quality, distorted, deformed, ugly, bad anatomy",
        "cfg_scale": 0.5,
        "mode": "std",
        "duration": str(duration),
        "aspect_ratio": aspect_ratio or config.video_gen.kling.default_ratio or "9:16",
    }

    url = f"{config.video_gen.kling.base_url}/v1/videos/image2video"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with session.post(url, json=payload, headers=headers) as resp:
        resp_text = await resp.text()
        try:
            result = json.loads(resp_text)
        except json.JSONDecodeError:
            raise RuntimeError(f"Kling API 返回非 JSON 响应 (HTTP {resp.status}): {resp_text[:200]}")

    if result.get("code") != 0:
        raise RuntimeError(f"Kling 任务提交失败 (code={result.get('code')}, msg={result.get('message')}): {result}")

    return result["data"]["task_id"]


async def _poll_kling_task(
    task_id: str,
    config: PilipiliConfig,
    session: aiohttp.ClientSession,
    timeout: int = 600,
    poll_interval: int = 10,
) -> str:
    """轮询 Kling v3 任务状态，返回视频 URL"""
    api_key = config.video_gen.kling.api_key
    api_secret = config.video_gen.kling.api_secret

    url = f"{config.video_gen.kling.base_url}/v1/videos/image2video/{task_id}"
    start_time = time.time()

    while time.time() - start_time < timeout:
        token = _generate_kling_jwt(api_key, api_secret)
        headers = {"Authorization": f"Bearer {token}"}

        async with session.get(url, headers=headers) as resp:
            resp_text = await resp.text()
            try:
                result = json.loads(resp_text)
            except json.JSONDecodeError:
                raise RuntimeError(f"Kling 轮询返回非 JSON 响应 (HTTP {resp.status}): {resp_text[:200]}")

        if result.get("code") != 0:
            raise RuntimeError(f"Kling 任务查询失败 (code={result.get('code')}, msg={result.get('message')}): {result}")

        status = result["data"]["task_status"]

        if status == "succeed":
            videos = result["data"]["task_result"]["videos"]
            if videos:
                return videos[0]["url"]
            raise RuntimeError("Kling 任务成功但无视频 URL")

        elif status == "failed":
            raise RuntimeError(f"Kling 任务失败: {result['data'].get('task_status_msg', '未知错误')}")

        elapsed = int(time.time() - start_time)
        print(f"[VideoGen] v3 任务 {task_id} 状态: {status} ({elapsed}s/{timeout}s)")
        await asyncio.sleep(poll_interval)

    raise TimeoutError(f"Kling 任务 {task_id} 超时（{timeout}s）")


# ============================================================
# Seedance 1.5 API
# ============================================================


async def _submit_minimax_i2v(
    image_path: str,
    scene: Scene,
    config: PilipiliConfig,
    session: aiohttp.ClientSession,
    resolution: Optional[str] = None,
) -> str:
    api_key = _resolve_minimax_video_api_key(config)
    if not api_key:
        raise ValueError("MiniMax Video API Key 未配置")

    payload = {
        "model": config.video_gen.minimax.model or "MiniMax-Hailuo-2.3-Fast",
        "prompt": scene.video_prompt,
        "first_frame_image": _image_to_data_url(image_path),
        "duration": 6 if scene.duration <= 8 else 10,
        "resolution": _map_minimax_resolution(resolution),
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with session.post("https://api.minimax.io/v1/video_generation", json=payload, headers=headers) as resp:
        resp_text = await resp.text()
        try:
            result = json.loads(resp_text)
        except json.JSONDecodeError:
            raise RuntimeError(f"MiniMax Video API 返回非 JSON 响应 (HTTP {resp.status}): {resp_text[:200]}")

    if isinstance(result.get("base_resp"), dict) and result["base_resp"].get("status_code") not in {None, 0}:
        raise RuntimeError(
            f"MiniMax Video 任务提交失败 (code={result['base_resp'].get('status_code')}, "
            f"msg={result['base_resp'].get('status_msg')}): {resp_text[:500]}"
        )

    task_id = result.get("task_id")
    if not task_id:
        raise RuntimeError(f"MiniMax Video 任务提交失败: {resp_text[:500]}")
    return task_id


async def _retrieve_minimax_file_url(
    file_id: str,
    config: PilipiliConfig,
    session: aiohttp.ClientSession,
) -> str:
    api_key = _resolve_minimax_video_api_key(config)
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"file_id": file_id}

    async with session.get("https://api.minimax.io/v1/files/retrieve", params=params, headers=headers) as resp:
        resp_text = await resp.text()
        try:
            result = json.loads(resp_text)
        except json.JSONDecodeError:
            raise RuntimeError(f"MiniMax File API 返回非 JSON 响应 (HTTP {resp.status}): {resp_text[:200]}")

    file_info = result.get("file") or result.get("data") or {}
    download_url = file_info.get("download_url") or file_info.get("url")
    if not download_url:
        raise RuntimeError(f"MiniMax File API 未返回下载地址: {resp_text[:500]}")
    return download_url


async def _poll_minimax_task(
    task_id: str,
    config: PilipiliConfig,
    session: aiohttp.ClientSession,
    timeout: int = 900,
    poll_interval: int = 8,
) -> str:
    api_key = _resolve_minimax_video_api_key(config)
    headers = {"Authorization": f"Bearer {api_key}"}
    start_time = time.time()

    while time.time() - start_time < timeout:
        async with session.get(
            "https://api.minimax.io/v1/query/video_generation",
            params={"task_id": task_id},
            headers=headers,
        ) as resp:
            resp_text = await resp.text()
            try:
                result = json.loads(resp_text)
            except json.JSONDecodeError:
                raise RuntimeError(f"MiniMax Video 查询返回非 JSON 响应 (HTTP {resp.status}): {resp_text[:200]}")

        if isinstance(result.get("base_resp"), dict) and result["base_resp"].get("status_code") not in {None, 0}:
            raise RuntimeError(
                f"MiniMax Video 任务查询失败 (code={result['base_resp'].get('status_code')}, "
                f"msg={result['base_resp'].get('status_msg')}): {resp_text[:500]}"
            )

        status = (result.get("status") or result.get("task_status") or "").lower()
        if status in {"success", "succeed", "completed", "finished"}:
            file_id = result.get("file_id") or (result.get("data") or {}).get("file_id")
            if not file_id:
                raise RuntimeError(f"MiniMax Video 任务成功但未返回 file_id: {resp_text[:500]}")
            return await _retrieve_minimax_file_url(file_id, config, session)
        if status in {"failed", "fail"}:
            raise RuntimeError(f"MiniMax Video 任务失败: {resp_text[:500]}")

        await asyncio.sleep(poll_interval)

    raise TimeoutError(f"MiniMax Video 任务 {task_id} 超时（{timeout}s）")


# ============================================================
# Seedance 1.5 API
# ============================================================

async def _submit_seedance_i2v(
    image_path: str,
    scene: Scene,
    config: PilipiliConfig,
    session: aiohttp.ClientSession,
    aspect_ratio: Optional[str] = None,
) -> str:
    """提交 Seedance I2V 任务，返回 task_id"""
    api_key = config.video_gen.seedance.api_key

    if not api_key:
        raise ValueError("Seedance (Volcengine) API Key 未配置")

    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(ext, "image/jpeg")
    img_b64 = _image_to_base64(image_path)
    image_data_url = f"data:{mime_type};base64,{img_b64}"

    duration = 5 if scene.duration <= 7 else 10

    payload = {
        "model": config.video_gen.seedance.model or "doubao-seedance-1-5-pro-250528",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": image_data_url}
            },
            {
                "type": "text",
                "text": scene.video_prompt
            }
        ],
        "duration": duration,
        "ratio": aspect_ratio or config.video_gen.seedance.default_ratio or "9:16",
        "seed": -1,
    }

    url = f"{config.video_gen.seedance.base_url}/contents/generations/tasks"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with session.post(url, json=payload, headers=headers) as resp:
        resp_text = await resp.text()
        try:
            result = json.loads(resp_text)
        except json.JSONDecodeError:
            raise RuntimeError(f"Seedance API 返回非 JSON 响应 (HTTP {resp.status}): {resp_text[:200]}")

    if "id" not in result:
        raise RuntimeError(f"Seedance 任务提交失败: {result}")

    return result["id"]


async def _poll_seedance_task(
    task_id: str,
    config: PilipiliConfig,
    session: aiohttp.ClientSession,
    timeout: int = 300,
    poll_interval: int = 5,
) -> str:
    """轮询 Seedance 任务状态，返回视频 URL"""
    api_key = config.video_gen.seedance.api_key
    url = f"{config.video_gen.seedance.base_url}/contents/generations/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    start_time = time.time()

    while time.time() - start_time < timeout:
        async with session.get(url, headers=headers) as resp:
            resp_text = await resp.text()
            try:
                result = json.loads(resp_text)
            except json.JSONDecodeError:
                raise RuntimeError(f"Seedance 轮询返回非 JSON 响应 (HTTP {resp.status}): {resp_text[:200]}")

        status = result.get("status", "")

        if status == "succeeded":
            video_url = _extract_seedance_video_url(result)
            if video_url:
                return video_url
            raise RuntimeError(f"Seedance 任务成功但无视频 URL: {result}")

        elif status == "failed":
            raise RuntimeError(f"Seedance 任务失败: {result.get('error', '未知错误')}")

        await asyncio.sleep(poll_interval)

    raise TimeoutError(f"Seedance 任务 {task_id} 超时（{timeout}s）")


def _extract_seedance_video_url(result: dict) -> Optional[str]:
    """从 Seedance 成功响应中提取视频 URL，兼容多种返回结构"""
    content = result.get("content", [])

    if isinstance(content, str):
        return content if content.startswith("http") else None

    if isinstance(content, dict):
        if isinstance(content.get("video_url"), dict):
            return content["video_url"].get("url")
        if isinstance(content.get("video_url"), str):
            return content.get("video_url")
        if isinstance(content.get("url"), str):
            return content.get("url")

    if isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                if item.startswith("http"):
                    return item
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") == "video_url":
                video_url = item.get("video_url")
                if isinstance(video_url, dict):
                    return video_url.get("url")
                if isinstance(video_url, str):
                    return video_url
            if isinstance(item.get("url"), str):
                return item.get("url")

    if isinstance(result.get("video_url"), dict):
        return result["video_url"].get("url")
    if isinstance(result.get("video_url"), str):
        return result.get("video_url")
    if isinstance(result.get("url"), str):
        return result.get("url")

    return None


# ============================================================
# 统一视频生成接口
# ============================================================

async def generate_video_clip(
    scene: Scene,
    image_path: str,
    output_dir: str,
    engine: Optional[str] = None,
    auto_route: bool = True,
    config: Optional[PilipiliConfig] = None,
    verbose: bool = False,
    reference_images: Optional[list[str]] = None,
    aspect_ratio: Optional[str] = None,
) -> str:
    """
    为单个分镜生成视频片段（使用旧版 i2v 接口）

    Args:
        scene: 分镜场景对象
        image_path: 首帧关键图路径
        output_dir: 输出目录
        engine: 指定引擎 "kling" / "kling_omni" / "seedance"（可选）
        auto_route: 是否启用智能路由
        config: 配置对象
        verbose: 是否打印调试信息
        reference_images: 角色参考图路径列表（用于 Omni multi_ref 模式）

    Returns:
        本地视频文件路径
    """
    if config is None:
        config = get_config()

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"scene_{scene.scene_id:03d}_clip.mp4")

    # 断点续传
    if os.path.exists(output_path):
        if verbose:
            print(f"[VideoGen] Scene {scene.scene_id} 视频片段已存在，跳过")
        return output_path

    # 选择引擎
    if engine:
        selected_engine = engine
    elif auto_route:
        selected_engine = smart_route_engine(scene, config.video_gen.default_provider)
    else:
        selected_engine = config.video_gen.default_provider

    if verbose:
        shot_mode = auto_detect_shot_mode(scene)
        print(f"[VideoGen] Scene {scene.scene_id} 使用引擎: {selected_engine}, shot_mode: {shot_mode}")
        print(f"[VideoGen] 视频提示词: {scene.video_prompt[:80]}...")

    async with _create_http_session() as session:
        if selected_engine in ("kling", "kling_omni"):
            # 单分镜也走 Omni 接口（更好的角色一致性）
            try:
                task_id = await _submit_kling_omni(
                    scenes=[scene],
                    image_paths={scene.scene_id: image_path},
                    config=config,
                    session=session,
                    reference_images=reference_images,
                    aspect_ratio=aspect_ratio,
                )
                if verbose:
                    print(f"[VideoGen] Kling Omni 任务已提交: {task_id}")
                video_urls = await _poll_kling_omni_task(task_id, config, session)
                video_url = video_urls[0] if video_urls else None
                if not video_url:
                    raise RuntimeError("Kling Omni 返回空视频 URL")
            except Exception as omni_err:
                if verbose:
                    print(f"[VideoGen] Kling Omni 失败，回退到 v3 image2video: {omni_err}")
                try:
                    task_id = await _submit_kling_i2v(
                        image_path=image_path,
                        scene=scene,
                        config=config,
                        session=session,
                        aspect_ratio=aspect_ratio,
                    )
                    if verbose:
                        print(f"[VideoGen] Kling v3 任务已提交: {task_id}")
                    video_url = await _poll_kling_task(task_id, config, session)
                except Exception as v3_err:
                    raise RuntimeError(
                        f"[VideoGen] Kling Omni 与 v3 均失败: omni={omni_err}; v3={v3_err}"
                    ) from v3_err

        elif selected_engine == "minimax":
            task_id = await _submit_minimax_i2v(
                image_path=image_path,
                scene=scene,
                config=config,
                session=session,
                resolution=resolution,
            )
            if verbose:
                print(f"[VideoGen] MiniMax Video 任务已提交: {task_id}")
            video_url = await _poll_minimax_task(task_id, config, session)

        elif selected_engine == "seedance":
            task_id = await _submit_seedance_i2v(image_path, scene, config, session, aspect_ratio=aspect_ratio)
            if verbose:
                print(f"[VideoGen] Seedance 任务已提交: {task_id}")
            video_url = await _poll_seedance_task(task_id, config, session)
        else:
            raise ValueError(f"不支持的视频引擎: {selected_engine}")

        # 下载视频
        if verbose:
            print(f"[VideoGen] Scene {scene.scene_id} 生成完成，下载中...")

        async with session.get(video_url) as resp:
            video_data = await resp.read()

    with open(output_path, "wb") as f:
        f.write(video_data)

    if verbose:
        print(f"[VideoGen] Scene {scene.scene_id} 视频已保存: {output_path}")

    return output_path


async def generate_video_clips_omni_batch(
    scenes: list[Scene],
    keyframe_paths: dict[int, str],
    output_dir: str,
    config: PilipiliConfig,
    reference_images: Optional[list[str]] = None,
    batch_size: int = 6,
    verbose: bool = False,
    resolution: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
) -> dict[int, str]:
    """
    使用 Kling Omni 多镜头模式批量生成视频片段
    每次最多6个分镜一起提交，大幅减少 API 调用次数

    Args:
        scenes: 所有分镜列表
        keyframe_paths: {scene_id: keyframe_path}
        output_dir: 输出目录
        config: 配置
        reference_images: 全局角色参考图
        batch_size: 每批最多分镜数（Omni 最大6）
        verbose: 是否打印调试信息

    Returns:
        {scene_id: video_path} 字典
    """
    os.makedirs(output_dir, exist_ok=True)
    results = {}

    # 检查哪些分镜已经有缓存
    pending_scenes = []
    for scene in scenes:
        output_path = os.path.join(output_dir, f"scene_{scene.scene_id:03d}_clip.mp4")
        if os.path.exists(output_path):
            results[scene.scene_id] = output_path
            if verbose:
                print(f"[VideoGen] Scene {scene.scene_id} 视频片段已存在，跳过")
        else:
            pending_scenes.append(scene)

    if not pending_scenes:
        return results

    # 按 batch_size 分批处理
    async with _create_http_session() as session:
        for i in range(0, len(pending_scenes), batch_size):
            batch = pending_scenes[i:i + batch_size]

            if verbose:
                scene_ids = [s.scene_id for s in batch]
                print(f"[VideoGen] Omni 批次 {i // batch_size + 1}: 分镜 {scene_ids}")

            try:
                task_id = await _submit_kling_omni(
                    scenes=batch,
                    image_paths=keyframe_paths,
                    config=config,
                    session=session,
                    reference_images=reference_images,
                    aspect_ratio=aspect_ratio,
                )

                if verbose:
                    print(f"[VideoGen] Kling Omni 批次任务已提交: {task_id}")

                video_urls = await _poll_kling_omni_task(task_id, config, session)

                if len(video_urls) != len(batch):
                    raise RuntimeError(
                        f"Kling Omni 批量模式返回了 {len(video_urls)} 个视频，但当前批次有 {len(batch)} 个分镜"
                    )

                # 下载并保存每个分镜的视频
                for j, scene in enumerate(batch):
                    if j >= len(video_urls):
                        if verbose:
                            print(f"[VideoGen] Scene {scene.scene_id} 无对应视频 URL，跳过")
                        continue

                    video_url = video_urls[j]
                    output_path = os.path.join(output_dir, f"scene_{scene.scene_id:03d}_clip.mp4")

                    async with session.get(video_url) as resp:
                        video_data = await resp.read()

                    with open(output_path, "wb") as f:
                        f.write(video_data)

                    results[scene.scene_id] = output_path

                    if verbose:
                        print(f"[VideoGen] Scene {scene.scene_id} 视频已保存: {output_path}")

            except Exception as e:
                # 不降级！直接抛出异常，确保全程使用 kling-v3-omni
                raise RuntimeError(f"[VideoGen] Kling Omni 批次失败，不降级处理: {e}") from e

    return results


async def generate_all_video_clips(
    scenes: list[Scene],
    keyframe_paths: dict[int, str],
    output_dir: str,
    engine: Optional[str] = None,
    auto_route: bool = True,
    config: Optional[PilipiliConfig] = None,
    max_concurrent: int = 3,
    verbose: bool = False,
    reference_images: Optional[list[str]] = None,
    use_omni_batch: bool = True,
    resolution: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
) -> dict[int, str]:
    """
    生成所有分镜的视频片段

    v2.0 改动：
    - 默认使用 Kling Omni 批量模式（use_omni_batch=True）
    - 每批最多6个分镜，大幅减少 API 调用次数
    - 回退策略：Omni 失败 → 逐个 v3 i2v → Seedance

    Returns:
        {scene_id: video_path} 字典
    """
    if config is None:
        config = get_config()

    # 确定是否使用 Omni 批量模式
    selected_engine = engine or (config.video_gen.default_provider if not auto_route else None)
    use_omni = (
        use_omni_batch
        and selected_engine in (None, "kling", "kling_omni", "auto")
        and config.video_gen.kling.api_key
        and config.video_gen.kling.api_secret
    )

    if use_omni:
        if verbose:
            print(f"[VideoGen] 使用 Kling Omni 批量模式（每批最多6个分镜）")
        try:
            return await generate_video_clips_omni_batch(
                scenes=scenes,
                keyframe_paths=keyframe_paths,
                output_dir=output_dir,
                config=config,
                reference_images=reference_images,
                verbose=verbose,
                resolution=resolution,
                aspect_ratio=aspect_ratio,
            )
        except Exception as batch_error:
            if verbose:
                print(f"[VideoGen] Kling Omni 批量模式不可用，回退逐个生成: {batch_error}")

    # 回退到逐个生成模式（并发）
    if selected_engine in ("kling", "kling_omni", "minimax") and max_concurrent > 1:
        max_concurrent = 1
        if verbose:
            print("[VideoGen] Kling 逐个生成模式已降为串行，避免第三方 CDN 上传抖动")

    if verbose:
        print(f"[VideoGen] 使用逐个生成模式（并发数: {max_concurrent}）")

    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def _generate_with_semaphore(scene: Scene):
        async with semaphore:
            image_path = keyframe_paths.get(scene.scene_id)
            if not image_path or not os.path.exists(image_path):
                raise FileNotFoundError(f"Scene {scene.scene_id} 关键帧图片不存在: {image_path}")

            path = await generate_video_clip(
                scene=scene,
                image_path=image_path,
                output_dir=output_dir,
                engine=engine,
                auto_route=auto_route,
                config=config,
                verbose=verbose,
                reference_images=reference_images,
                aspect_ratio=aspect_ratio,
            )
            results[scene.scene_id] = path

    tasks = [_generate_with_semaphore(scene) for scene in scenes]
    await asyncio.gather(*tasks)

    return results


def generate_all_video_clips_sync(
    scenes: list[Scene],
    keyframe_paths: dict[int, str],
    output_dir: str,
    engine: Optional[str] = None,
    auto_route: bool = True,
    config: Optional[PilipiliConfig] = None,
    max_concurrent: int = 3,
    verbose: bool = False,
    reference_images: Optional[list[str]] = None,
    use_omni_batch: bool = True,
    resolution: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
) -> dict[int, str]:
    """generate_all_video_clips 的同步版本"""
    return asyncio.run(generate_all_video_clips(
        scenes=scenes,
        keyframe_paths=keyframe_paths,
        output_dir=output_dir,
        engine=engine,
        auto_route=auto_route,
        config=config,
        max_concurrent=max_concurrent,
        verbose=verbose,
        reference_images=reference_images,
        use_omni_batch=use_omni_batch,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
    ))
