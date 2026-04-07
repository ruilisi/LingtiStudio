"""
噼哩噼哩 Pilipili-AutoVideo
TTS 配音模块 - MiniMax Speech

职责：
- 将旁白文案转换为语音
- 测量精确音频时长（用于动态控制视频 duration）
- 支持 MiniMax Speech-02-HD（默认）
- 支持声音克隆（传入参考音频）
- 支持情绪控制
"""

import os
import asyncio
import aiohttp
import json
import hashlib
import struct
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from core.config import PilipiliConfig, get_config
from modules.llm import Scene


# ============================================================
# MiniMax TTS API 常量
# ============================================================

MINIMAX_TTS_URL = "https://api.minimax.chat/v1/t2a_v2"
MINIMAX_CATALOG_URL = "https://api.minimax.io/v1/get_voice"
MINIMAX_PREVIEW_URL = "https://api.minimax.io/v1/t2a_v2"
DEFAULT_PREVIEW_TEXT = "您好，这里是灵缇音色试听。这个音色适合用来做短视频旁白和讲解。"

# 可用音色列表（MiniMax 系统音色，已验证存在）
VOICE_OPTIONS = {
    # 女声
    "female_shaonv": "female-shaonv",      # 少女音（默认）
    "female_yujie": "female-yujie",        # 御姐音
    "female_chengshu": "female-chengshu",  # 成熟女声
    "female_tianmei": "female-tianmei",    # 甜美音
    # 男声
    "male_qn_qingse": "male-qn-qingse",    # 青涩青年音色
    "male_qn_jingying": "male-qn-jingying", # 精英青年音色
    "male_qn_badao": "male-qn-badao",      # 霸道青年音色
    "male_qn_daxuesheng": "male-qn-daxuesheng", # 青年大学生音色
}

# 情绪选项
EMOTION_OPTIONS = ["neutral", "happy", "sad", "angry", "fearful", "disgusted", "surprised"]

FALLBACK_VOICE_SEEDS = [
    ("female-shaonv", "少女音", "经典少女旁白", "zh-CN", ["female", "young", "soft"]),
    ("female-yujie", "御姐音", "成熟自信，适合产品讲解", "zh-CN", ["female", "mature", "confident"]),
    ("female-chengshu", "成熟女声", "稳定旁白，适合叙述和纪录片", "zh-CN", ["female", "narrator", "warm"]),
    ("female-tianmei", "甜美女声", "轻快柔和，适合生活方式内容", "zh-CN", ["female", "sweet", "soft"]),
    ("male-qn-qingse", "青涩青年", "轻松自然的年轻男声", "zh-CN", ["male", "young", "casual"]),
    ("male-qn-jingying", "精英青年", "沉稳商务风，适合讲解和主持", "zh-CN", ["male", "executive", "professional"]),
    ("male-qn-badao", "霸道青年", "力量感明显，适合强节奏内容", "zh-CN", ["male", "strong", "dramatic"]),
    ("male-qn-daxuesheng", "大学生男声", "轻快日常，适合口播和剧情", "zh-CN", ["male", "student", "casual"]),
    ("Chinese (Mandarin)_Reliable_Executive", "Reliable Executive", "理性可靠，适合讲解与商务旁白", "zh-CN", ["male", "executive", "professional"]),
    ("Chinese (Mandarin)_News_Anchor", "News Anchor", "新闻主播风格，吐字清晰", "zh-CN", ["narrator", "news", "professional"]),
    ("Chinese (Mandarin)_Mature_Woman", "Mature Woman", "沉稳成熟，适合品牌叙事", "zh-CN", ["female", "mature", "calm"]),
    ("Chinese (Mandarin)_Kind-hearted_Antie", "Kind-hearted Antie", "亲切生活感，适合社区和养老内容", "zh-CN", ["female", "warm", "casual"]),
    ("Chinese (Mandarin)_Humorous_Elder", "Humorous Elder", "长者感明显，语气轻松", "zh-CN", ["male", "warm", "casual"]),
    ("Chinese (Mandarin)_Gentleman", "Gentleman", "温和稳重，适合高端介绍", "zh-CN", ["male", "calm", "professional"]),
    ("Chinese (Mandarin)_Warm_Bestie", "Warm Bestie", "亲近自然，适合情感化口播", "zh-CN", ["female", "warm", "casual"]),
    ("Chinese (Mandarin)_Sweet_Lady", "Sweet Lady", "轻柔甜美，适合生活方式和带货", "zh-CN", ["female", "sweet", "soft"]),
    ("Chinese (Mandarin)_Gentle_Youth", "Gentle Youth", "温柔青年感，适合轻剧情和Vlog", "zh-CN", ["male", "young", "calm"]),
    ("Chinese (Mandarin)_Warm_Girl", "Warm Girl", "自然元气，适合轻松内容", "zh-CN", ["female", "young", "warm"]),
    ("Chinese (Mandarin)_Male_Announcer", "Male Announcer", "广播感强，适合正式播报", "zh-CN", ["male", "news", "professional"]),
    ("Chinese (Mandarin)_Radio_Host", "Radio Host", "电台主持风格，适合陪伴感内容", "zh-CN", ["narrator", "warm", "professional"]),
    ("Chinese (Mandarin)_Lyrical_Voice", "Lyrical Voice", "抒情细腻，适合情绪化旁白", "zh-CN", ["female", "soft", "dramatic"]),
    ("Chinese (Mandarin)_Straightforward_Boy", "Straightforward Boy", "直给年轻感，适合短视频口播", "zh-CN", ["male", "young", "casual"]),
    ("Chinese (Mandarin)_Sincere_Adult", "Sincere Adult", "真诚平稳，适合品牌故事", "zh-CN", ["male", "calm", "warm"]),
    ("Chinese (Mandarin)_Gentle_Senior", "Gentle Senior", "成熟柔和，适合访谈和纪录片", "zh-CN", ["female", "mature", "narrator"]),
    ("Chinese (Mandarin)_Crisp_Girl", "Crisp Girl", "清脆干净，适合信息类口播", "zh-CN", ["female", "young", "professional"]),
    ("Chinese (Mandarin)_Soft_Girl", "Soft Girl", "轻柔安静，适合温和节奏内容", "zh-CN", ["female", "soft", "young"]),
    ("Chinese (Mandarin)_IntellectualGirl", "Intellectual Girl", "知性表达，适合知识讲解", "zh-CN", ["female", "professional", "calm"]),
    ("Chinese (Mandarin)_Warm_HeartedGirl", "Warm-hearted Girl", "温暖陪伴感，适合情绪价值内容", "zh-CN", ["female", "warm", "casual"]),
    ("Chinese (Mandarin)_Laid_BackGirl", "Laid-back Girl", "松弛感明显，适合轻松分享", "zh-CN", ["female", "casual", "young"]),
    ("Chinese (Mandarin)_BashfulGirl", "Bashful Girl", "害羞可爱，适合角色化内容", "zh-CN", ["female", "young", "soft"]),
    ("English_expressive_narrator", "Expressive Narrator", "Expressive English narrator", "en-US", ["narrator", "dramatic"]),
    ("English_radiant_girl", "Radiant Girl", "Bright, upbeat female English voice", "en-US", ["female", "young", "warm"]),
    ("English_magnetic_voiced_man", "Magnetic-voiced Male", "Confident English male voice", "en-US", ["male", "professional", "calm"]),
    ("English_compelling_lady1", "Compelling Lady", "Confident English female storyteller", "en-US", ["female", "professional", "narrator"]),
    ("English_Upbeat_Woman", "Upbeat Woman", "Energetic English female host", "en-US", ["female", "warm", "casual"]),
    ("English_Trustworth_Man", "Trustworthy Man", "Reliable English male presenter", "en-US", ["male", "executive", "professional"]),
    ("English_CalmWoman", "Calm Woman", "Steady English female narrator", "en-US", ["female", "calm", "narrator"]),
    ("English_CaptivatingStoryteller", "Captivating Storyteller", "English story-driven narrator", "en-US", ["narrator", "dramatic"]),
    ("English_ConfidentWoman", "Confident Woman", "Direct and clear English female voice", "en-US", ["female", "professional", "confident"]),
    ("English_WiseScholar", "Wise Scholar", "Measured English explainer voice", "en-US", ["male", "calm", "professional"]),
]

LEGACY_VOICE_CATALOG = [
    {
        "id": voice_id,
        "name": name,
        "description": description,
        "language": language,
        "tags": tags,
        "source_type": "system",
        "created_time": None,
        "preview_available": True,
    }
    for voice_id, name, description, language, tags in FALLBACK_VOICE_SEEDS
]


def _base_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }


def _candidate_api_keys(config: PilipiliConfig) -> list[str]:
    candidates = [config.tts.api_key, getattr(config.llm.minimax, "api_key", "")]
    seen: set[str] = set()
    result: list[str] = []
    for key in candidates:
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _parse_minimax_error(result: dict[str, Any], fallback: str = "未知错误") -> str:
    base_resp = result.get("base_resp", {})
    code = base_resp.get("status_code", -1)
    msg = base_resp.get("status_msg", fallback)
    return f"{msg} (code={code})"


def _infer_language(text: str) -> str:
    value = (text or "").lower()
    if any(token in value for token in ["mandarin", "chinese", "普通话", "中文", "zh-"]):
        return "zh-CN"
    if any(token in value for token in ["english", "en-", "英文"]):
        return "en-US"
    if any(token in value for token in ["japanese", "日语", "ja-"]):
        return "ja-JP"
    if any(token in value for token in ["korean", "韩语", "ko-"]):
        return "ko-KR"
    if any(token in value for token in ["cantonese", "粤语", "yue"]):
        return "zh-HK"
    return "unknown"


def _extract_voice_tags(voice_id: str, voice_name: str, description: str) -> list[str]:
    text = " ".join([voice_id or "", voice_name or "", description or ""]).lower()
    tags: list[str] = []
    mapping = {
        "female": ["female", "woman", "女", "御姐", "少女"],
        "male": ["male", "man", "男"],
        "young": ["young", "teen", "youth", "青涩", "少女", "大学生"],
        "mature": ["mature", "成熟", "御姐"],
        "narrator": ["narrator", "旁白", "播报", "纪录片"],
        "news": ["news", "播音", "新闻"],
        "executive": ["executive", "jingying", "精英", "商务"],
        "warm": ["warm", "温暖", "亲和"],
        "sweet": ["sweet", "甜美"],
        "calm": ["calm", "steady", "沉稳"],
        "dramatic": ["dramatic", "霸道", "强势"],
        "casual": ["casual", "自然", "日常"],
    }
    for tag, keywords in mapping.items():
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    if not tags:
        tags.append("general")
    return tags


def _normalize_voice_entry(entry: dict[str, Any], source_type: str) -> Optional[dict[str, Any]]:
    voice_id = entry.get("voice_id") or entry.get("id") or entry.get("voice_code")
    if not voice_id:
        return None

    voice_name = entry.get("voice_name") or entry.get("name") or voice_id
    raw_description = (
        entry.get("description")
        or entry.get("desc")
        or entry.get("introduction")
        or entry.get("intro")
        or ""
    )
    if isinstance(raw_description, list):
        description = " ".join(str(item) for item in raw_description if item)
    else:
        description = str(raw_description)
    language = _infer_language(" ".join([voice_id, voice_name, description]))
    tags = _extract_voice_tags(voice_id, voice_name, description)
    return {
        "id": voice_id,
        "name": voice_name,
        "description": description,
        "language": language,
        "tags": tags,
        "source_type": source_type,
        "created_time": entry.get("created_time") or entry.get("created_at"),
        "preview_available": True,
    }


def _filter_voice_catalog(
    voices: list[dict[str, Any]],
    q: Optional[str] = None,
    language: Optional[str] = None,
) -> list[dict[str, Any]]:
    query = (q or "").strip().lower()
    lang = (language or "").strip().lower()
    filtered = []
    for voice in voices:
        if lang and voice.get("language", "").lower() != lang:
            continue
        if query:
            haystack = " ".join(
                [
                    voice.get("id", ""),
                    voice.get("name", ""),
                    voice.get("description", ""),
                    " ".join(voice.get("tags", [])),
                ]
            ).lower()
            if query not in haystack:
                continue
        filtered.append(voice)
    return filtered


def _preview_cache_dir(config: PilipiliConfig) -> Path:
    output_dir = Path(config.local.output_dir).resolve()
    cache_dir = output_dir.parent / "tts_previews"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _preview_cache_key(voice_id: str, model: str, preview_text: str) -> str:
    raw = f"{voice_id}|{model}|{preview_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _preview_meta_path(cache_dir: Path, cache_key: str) -> Path:
    return cache_dir / f"{cache_key}.json"


def _preview_audio_path(cache_dir: Path, cache_key: str) -> Path:
    return cache_dir / f"{cache_key}.mp3"


def _parse_url_expiry(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
        expires = parse_qs(parsed.query).get("Expires")
        if not expires:
            return None
        ts = int(expires[0])
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return None


def _load_cached_preview(cache_dir: Path, cache_key: str) -> Optional[dict[str, Any]]:
    meta_path = _preview_meta_path(cache_dir, cache_key)
    audio_path = _preview_audio_path(cache_dir, cache_key)
    if not meta_path.exists():
        return None

    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    expires_at = payload.get("expires_at")
    if expires_at:
        try:
            expire_dt = datetime.fromisoformat(expires_at)
            if expire_dt.tzinfo is None:
                expire_dt = expire_dt.replace(tzinfo=timezone.utc)
            if expire_dt <= datetime.now(timezone.utc):
                return None
        except ValueError:
            return None

    if payload.get("kind") == "file" and not audio_path.exists():
        return None

    return payload


def _save_cached_preview(cache_dir: Path, cache_key: str, payload: dict[str, Any]) -> None:
    meta_path = _preview_meta_path(cache_dir, cache_key)
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def list_available_voices(
    source: str = "system",
    q: Optional[str] = None,
    language: Optional[str] = None,
    config: Optional[PilipiliConfig] = None,
) -> dict[str, Any]:
    if config is None:
        config = get_config()

    api_keys = _candidate_api_keys(config)
    if not api_keys:
        return {
            "provider": "minimax",
            "default_voice": config.tts.default_voice,
            "voices": _filter_voice_catalog(LEGACY_VOICE_CATALOG, q=q, language=language),
            "source": source,
            "fallback": True,
        }

    payload = {"voice_type": "all" if source == "all" else "system"}

    for api_key in api_keys:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(auto_decompress=True, timeout=timeout) as session:
                async with session.post(
                    MINIMAX_CATALOG_URL,
                    json=payload,
                    headers=_base_headers(api_key),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise RuntimeError(f"MiniMax Voice API 错误 {resp.status}: {error_text}")
                    result = await resp.json()

            base_resp = result.get("base_resp", {})
            if base_resp.get("status_code", 0) != 0:
                raise RuntimeError(_parse_minimax_error(result, "拉取音色目录失败"))

            voices: list[dict[str, Any]] = []

            for key, source_type in [
                ("system_voice", "system"),
                ("voice_cloning", "voice_cloning"),
                ("voice_generation", "voice_generation"),
            ]:
                for entry in result.get(key, []) or []:
                    normalized = _normalize_voice_entry(entry, source_type)
                    if normalized:
                        voices.append(normalized)

            if not voices:
                raise RuntimeError("MiniMax 未返回任何音色")

            voices = sorted(voices, key=lambda item: (item["source_type"] != "system", item["name"]))
            return {
                "provider": "minimax",
                "default_voice": config.tts.default_voice,
                "voices": _filter_voice_catalog(voices, q=q, language=language),
                "source": source,
                "fallback": False,
            }
        except Exception:
            continue

    return {
        "provider": "minimax",
        "default_voice": config.tts.default_voice,
        "voices": _filter_voice_catalog(LEGACY_VOICE_CATALOG, q=q, language=language),
        "source": source,
        "fallback": True,
    }


def list_available_voices_sync(
    source: str = "system",
    q: Optional[str] = None,
    language: Optional[str] = None,
    config: Optional[PilipiliConfig] = None,
) -> dict[str, Any]:
    return asyncio.run(list_available_voices(source=source, q=q, language=language, config=config))


async def generate_voice_preview(
    voice_id: str,
    preview_text: Optional[str] = None,
    config: Optional[PilipiliConfig] = None,
) -> dict[str, Any]:
    if config is None:
        config = get_config()

    api_keys = _candidate_api_keys(config)
    if not api_keys:
        raise ValueError("MiniMax TTS API Key 未配置，无法试听")

    text = (preview_text or DEFAULT_PREVIEW_TEXT).strip()
    cache_dir = _preview_cache_dir(config)
    cache_key = _preview_cache_key(voice_id, config.tts.model, text)
    cached = _load_cached_preview(cache_dir, cache_key)
    if cached:
        if cached["kind"] == "url":
            return {
                "voice_id": voice_id,
                "preview_text": text,
                "cache_key": cache_key,
                "audio_url": cached["audio_url"],
                "cached": True,
            }
        return {
            "voice_id": voice_id,
            "preview_text": text,
            "cache_key": cache_key,
            "audio_url": f"/api/tts/previews/{cache_key}",
            "cached": True,
        }

    payload = {
        "model": config.tts.model,
        "text": text,
        "stream": False,
        "output_format": "url",
        "voice_setting": {
            "voice_id": voice_id,
            "speed": config.tts.speed,
            "vol": 1.0,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
    }

    async def _request_preview(request_payload: dict[str, Any], api_key: str, url: str) -> dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(auto_decompress=True, timeout=timeout) as session:
            async with session.post(
                url,
                json=request_payload,
                headers=_base_headers(api_key),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"MiniMax TTS Preview API 错误 {resp.status}: {error_text}")
                return await resp.json()

    result: dict[str, Any] | None = None
    last_error: Exception | None = None
    for api_key in api_keys:
        for url in [MINIMAX_PREVIEW_URL, MINIMAX_TTS_URL]:
            try:
                try:
                    result = await _request_preview(payload, api_key, url)
                    base_resp = result.get("base_resp", {})
                    if base_resp.get("status_code", 0) != 0:
                        raise RuntimeError(_parse_minimax_error(result, "MiniMax 试听生成失败"))
                except Exception:
                    fallback_payload = dict(payload)
                    fallback_payload.pop("output_format", None)
                    result = await _request_preview(fallback_payload, api_key, url)
                    base_resp = result.get("base_resp", {})
                    if base_resp.get("status_code", 0) != 0:
                        raise RuntimeError(_parse_minimax_error(result, "MiniMax 试听生成失败"))
                break
            except Exception as exc:
                last_error = exc
                result = None
                continue
        if result is not None:
            break

    if result is None:
        raise RuntimeError(str(last_error or "MiniMax 试听生成失败"))

    data = result.get("data") or {}
    audio_field = data.get("audio") or data.get("audio_url") or data.get("url")
    if not audio_field:
        raise RuntimeError(f"MiniMax 试听响应格式异常: {json.dumps(result, ensure_ascii=False)[:200]}")

    if isinstance(audio_field, str) and audio_field.startswith("http"):
        expires_at = _parse_url_expiry(audio_field) or (
            datetime.now(timezone.utc) + timedelta(hours=23)
        ).isoformat()
        _save_cached_preview(
            cache_dir,
            cache_key,
            {
                "kind": "url",
                "audio_url": audio_field,
                "expires_at": expires_at,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "voice_id": voice_id,
            "preview_text": text,
            "cache_key": cache_key,
            "audio_url": audio_field,
            "cached": False,
        }

    audio_bytes = bytes.fromhex(audio_field)
    audio_path = _preview_audio_path(cache_dir, cache_key)
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    _save_cached_preview(
        cache_dir,
        cache_key,
        {
            "kind": "file",
            "audio_path": str(audio_path),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {
        "voice_id": voice_id,
        "preview_text": text,
        "cache_key": cache_key,
        "audio_url": f"/api/tts/previews/{cache_key}",
        "cached": False,
    }


def generate_voice_preview_sync(
    voice_id: str,
    preview_text: Optional[str] = None,
    config: Optional[PilipiliConfig] = None,
) -> dict[str, Any]:
    return asyncio.run(generate_voice_preview(voice_id=voice_id, preview_text=preview_text, config=config))


# ============================================================
# 核心生成函数
# ============================================================

async def generate_voiceover(
    scene: Scene,
    output_dir: str,
    voice_id: Optional[str] = None,
    emotion: Optional[str] = None,
    speed: Optional[float] = None,
    config: Optional[PilipiliConfig] = None,
    verbose: bool = False,
) -> tuple[str, float]:
    """
    为单个分镜生成配音

    Args:
        scene: 分镜场景对象
        output_dir: 输出目录
        voice_id: 音色 ID（可选，默认使用配置）
        emotion: 情绪（可选）
        speed: 语速（可选，0.5-2.0）
        config: 配置对象
        verbose: 是否打印调试信息

    Returns:
        (音频文件路径, 精确时长秒数) 元组
    """
    if config is None:
        config = get_config()

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"scene_{scene.scene_id:03d}_voiceover.mp3")

    # 断点续传
    if os.path.exists(output_path):
        duration = get_audio_duration(output_path)
        if verbose:
            print(f"[TTS] Scene {scene.scene_id} 配音已存在，时长: {duration:.2f}s")
        return output_path, duration

    if not (scene.voiceover or "").strip():
        if verbose:
            print(f"[TTS] Scene {scene.scene_id} 无旁白文案，跳过")
        return "", 0.0

    api_key = config.tts.api_key
    if not api_key:
        raise ValueError("MiniMax API Key 未配置，请在 config.yaml 中设置 tts.minimax.api_key")

    # 参数
    voice = voice_id or config.tts.default_voice
    emo = emotion or config.tts.emotion
    spd = speed or config.tts.speed

    if verbose:
        print(f"[TTS] Scene {scene.scene_id} 生成配音: {scene.voiceover[:30]}...")

    payload = {
        "model": config.tts.model,
        "text": scene.voiceover,
        "stream": False,
        "voice_setting": {
            "voice_id": voice,
            "speed": spd,
            "vol": 1.0,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        }
    }

    # 添加情绪（如果不是 neutral）
    if emo and emo != "neutral":
        payload["voice_setting"]["emotion"] = emo

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate",  # 禁用 br 编码，避免 aiohttp brotli 解码问题
    }

    # 请求重试：遇到 RPM/TPM 限速（status_code 1002）时指数退避等待，最多重试 4 次
    MAX_RETRIES = 4
    result = None
    for attempt in range(MAX_RETRIES):
        async with aiohttp.ClientSession(auto_decompress=True) as session:
            async with session.post(MINIMAX_TTS_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"MiniMax TTS API 错误 {resp.status}: {error_text}")
                result = await resp.json()

        # 检查是否限速
        base_resp = result.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code in (1002, 1004):  # 1002=RPM限速, 1004=TPM限速
            wait_sec = 2 ** attempt * 5  # 5s, 10s, 20s, 40s
            if verbose:
                print(f"[TTS] Scene {scene.scene_id} 限速 ({base_resp.get('status_msg', '')})，{wait_sec}s 后重试 (attempt {attempt+1}/{MAX_RETRIES})...")
            await asyncio.sleep(wait_sec)
            result = None
            continue
        break  # 成功或其他错误，退出重试循环

    if result is None:
        raise RuntimeError(f"MiniMax TTS Scene {scene.scene_id} 重试 {MAX_RETRIES} 次后仍限速，请稍后再试")

    # 提取音频数据
    if "data" not in result or "audio" not in result["data"]:
        raise RuntimeError(f"MiniMax TTS 响应格式异常: {json.dumps(result)[:200]}")

    audio_hex = result["data"]["audio"]
    audio_bytes = bytes.fromhex(audio_hex)

    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    # 测量精确时长
    duration = get_audio_duration(output_path)

    if verbose:
        print(f"[TTS] Scene {scene.scene_id} 配音完成，时长: {duration:.2f}s，保存至: {output_path}")

    return output_path, duration


# 性别默认音色映射（MiniMax 系统音色，已验证存在）
DEFAULT_VOICE_BY_GENDER = {
    "male": "male-qn-qingse",   # 青涩青年音色
    "female": "female-shaonv",  # 少女音色
}

NARRATOR_VOICE = "female-chengshu"  # 旁白默认回退音色


def _infer_voice_from_voiceover(voiceover: str) -> str:
    """
    对标分析模式下，speaker_id=None 时根据旁白内容自动推断音色。

    规则：
    - 纯旁白（无男：/女：前缀）→ 旁白成熟女声
    - 仅含男：→ 男声
    - 仅含女：→ 少女音
    - 混合对话（同时含男：和女：）→ 旁白成熟女声（单段无法拆分时的回退）
    """
    import re
    has_male = bool(re.search(r'男[（(\w]*[）)]?[：:]', voiceover))
    has_female = bool(re.search(r'女[（(\w]*[）)]?[：:]', voiceover))

    if has_male and not has_female:
        return DEFAULT_VOICE_BY_GENDER["male"]   # 纯男声台词
    elif has_female and not has_male:
        return DEFAULT_VOICE_BY_GENDER["female"]  # 纯女声台词
    else:
        # 纯旁白 或 男女混合对话 → 旁白成熟女声
        return NARRATOR_VOICE


def _resolve_narrator_voice(config: Optional[PilipiliConfig], requested_voice_id: Optional[str]) -> str:
    requested = (requested_voice_id or "").strip()
    if requested:
        return requested
    if config is None:
        config = get_config()
    configured = (config.tts.default_voice or "").strip()
    if configured:
        return configured
    return NARRATOR_VOICE


def _split_voiceover_by_speaker(voiceover: str) -> list[tuple[str, str]]:
    """
    将旁白文案按说话人拆分成多段，每段包含（说话人类型, 文本）。

    说话人类型：
    - 'male'   → 男声（男：、男（英语）： 等）
    - 'female' → 女声（女：、女（英语）： 等）
    - 'narrator' → 旁白成熟女声（无前缀的纯旁白）

    支持多语言标记（如 男（英语）：、女（日语）：），
    语言标记仅用于区分说话人，不过滤任何内容。

    示例：
    "女：你好。男：你好啊。女：再见。" →
    [('female', '你好。'), ('male', '你好啊。'), ('female', '再见。')]
    """
    import re
    # 匹配说话人前缀：男： / 女： / 男（xxx）： / 女（xxx）：
    SPEAKER_PATTERN = re.compile(r'(男[\uff08(][^\uff09)]*[\uff09)]\uff1a|女[\uff08(][^\uff09)]*[\uff09)]\uff1a|男[\uff1a:]|女[\uff1a:])')

    segments = []
    last_end = 0
    current_speaker = 'narrator'  # 开头无前缀就是旁白

    for m in SPEAKER_PATTERN.finditer(voiceover):
        # 先把前一段文本存起来
        text_before = voiceover[last_end:m.start()].strip()
        if text_before:
            segments.append((current_speaker, text_before))

        # 确定当前说话人
        tag = m.group(0)
        if '男' in tag:
            current_speaker = 'male'
        else:
            current_speaker = 'female'
        last_end = m.end()

    # 最后一段
    remaining = voiceover[last_end:].strip()
    if remaining:
        segments.append((current_speaker, remaining))

    return segments if segments else [('narrator', voiceover)]


async def _call_minimax_tts(
    text: str,
    voice_id: str,
    api_key: str,
    model: str,
    speed: float,
    emotion: Optional[str],
    scene_id: int,
    seg_idx: int,
) -> bytes:
    """单次 MiniMax TTS 请求，返回音频字节。"""
    payload = {
        "model": model,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": 1.0,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        }
    }
    if emotion and emotion != "neutral":
        payload["voice_setting"]["emotion"] = emotion

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }

    MAX_RETRIES = 4
    result = None
    for attempt in range(MAX_RETRIES):
        async with aiohttp.ClientSession(auto_decompress=True) as session:
            async with session.post(MINIMAX_TTS_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"MiniMax TTS API 错误 {resp.status}: {error_text}")
                result = await resp.json()

        base_resp = result.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code in (1002, 1004):
            wait_sec = 2 ** attempt * 5
            await asyncio.sleep(wait_sec)
            result = None
            continue
        break

    if result is None:
        raise RuntimeError(f"MiniMax TTS Scene {scene_id} seg{seg_idx} 限速重试失败")

    if "data" not in result or "audio" not in result["data"]:
        raise RuntimeError(f"MiniMax TTS 响应格式异常: {json.dumps(result)[:200]}")

    return bytes.fromhex(result["data"]["audio"])


def _concat_mp3_with_ffmpeg(segment_paths: list[str], output_path: str) -> None:
    """
    用 ffmpeg 将多段 MP3 拼接成一个文件。
    Windows 和 Linux 均兼容（纯 Python subprocess）。
    """
    import subprocess
    import tempfile
    import os

    if len(segment_paths) == 1:
        import shutil
        shutil.copy2(segment_paths[0], output_path)
        return

    # 创建临时文件列表
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        for p in segment_paths:
            # ffmpeg concat 要求路径用单引号包裹
            f.write(f"file '{p}'\n")
        list_file = f.name

    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 拼接失败: {result.stderr[:300]}")
    finally:
        os.unlink(list_file)


async def generate_voiceover_multi_speaker(
    scene: Scene,
    output_dir: str,
    emotion: Optional[str] = None,
    speed: Optional[float] = None,
    config: Optional[PilipiliConfig] = None,
    verbose: bool = False,
    char_voice_map: Optional[dict] = None,
) -> tuple[str, float]:
    """
    多人声线拆分合成：将旁白按男：/女：拆分成多段，分别合成，再用 ffmpeg 拼接。

    如果旁白中没有说话人前缀，则直接调用单音色版本。
    """
    if config is None:
        config = get_config()

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"scene_{scene.scene_id:03d}_voiceover.mp3")

    # 断点续传
    if os.path.exists(output_path):
        duration = get_audio_duration(output_path)
        if verbose:
            print(f"[TTS] Scene {scene.scene_id} 配音已存在，时长: {duration:.2f}s")
        return output_path, duration

    voiceover_text = (scene.voiceover or "").strip()
    if not voiceover_text:
        if verbose:
            print(f"[TTS] Scene {scene.scene_id} 无旁白文案，跳过")
        return "", 0.0

    api_key = config.tts.api_key
    if not api_key:
        raise ValueError("MiniMax API Key 未配置")

    spd = speed or config.tts.speed
    emo = emotion or config.tts.emotion
    model = config.tts.model

    # 拆分旁白
    segments = _split_voiceover_by_speaker(voiceover_text)

    # 确定每段的音色
    def _resolve_voice(speaker_type: str) -> str:
        if char_voice_map:
            # 如果有角色映射，用角色映射
            if speaker_type == 'male':
                # 找第一个男性角色
                for cid, voice in char_voice_map.items():
                    if voice == DEFAULT_VOICE_BY_GENDER['male']:
                        return voice
            elif speaker_type == 'female':
                for cid, voice in char_voice_map.items():
                    if voice == DEFAULT_VOICE_BY_GENDER['female']:
                        return voice
        # 默认映射
        if speaker_type == 'male':
            return DEFAULT_VOICE_BY_GENDER['male']
        elif speaker_type == 'female':
            return DEFAULT_VOICE_BY_GENDER['female']
        else:
            return (char_voice_map or {}).get(0, NARRATOR_VOICE)

    if verbose:
        print(f"[TTS] Scene {scene.scene_id} 拆分成 {len(segments)} 段: {[(s[0], s[1][:15]) for s in segments]}")

    # 并发合成所有段
    seg_dir = os.path.join(output_dir, f"scene_{scene.scene_id:03d}_segments")
    os.makedirs(seg_dir, exist_ok=True)

    async def _gen_segment(idx: int, speaker_type: str, text: str) -> str:
        seg_path = os.path.join(seg_dir, f"seg_{idx:03d}.mp3")
        if os.path.exists(seg_path):
            return seg_path
        voice = _resolve_voice(speaker_type)
        audio_bytes = await _call_minimax_tts(
            text=text,
            voice_id=voice,
            api_key=api_key,
            model=model,
            speed=spd,
            emotion=emo,
            scene_id=scene.scene_id,
            seg_idx=idx,
        )
        with open(seg_path, 'wb') as f:
            f.write(audio_bytes)
        if verbose:
            print(f"[TTS] Scene {scene.scene_id} seg{idx} ({speaker_type}/{voice}) 完成")
        return seg_path

    seg_tasks = [_gen_segment(i, spk, txt) for i, (spk, txt) in enumerate(segments)]
    seg_paths = await asyncio.gather(*seg_tasks)

    # 用 ffmpeg 拼接
    _concat_mp3_with_ffmpeg(list(seg_paths), output_path)

    duration = get_audio_duration(output_path)
    if verbose:
        print(f"[TTS] Scene {scene.scene_id} 多人声线合成完成，时长: {duration:.2f}s，保存至: {output_path}")

    return output_path, duration


async def generate_all_voiceovers(
    scenes: list[Scene],
    output_dir: str,
    voice_id: Optional[str] = None,
    emotion: Optional[str] = None,
    speed: Optional[float] = None,
    config: Optional[PilipiliConfig] = None,
    max_concurrent: int = 5,
    verbose: bool = False,
    characters: Optional[list] = None,  # list[CharacterInfo]
) -> dict[int, tuple[str, float]]:
    """
    并发生成所有分镜的配音

    如果传入 characters 列表，将根据 scene.speaker_id 自动分配对应性别的音色。

    Returns:
        {scene_id: (audio_path, duration)} 字典
    """
    narrator_voice = _resolve_narrator_voice(config, voice_id)

    # 构建 character_id -> voice_id 映射
    char_voice_map: dict[int, str] = {}
    # speaker_id=0 始终为旁白音色，不受 characters 列表影响
    char_voice_map[0] = narrator_voice
    if characters:
        for char in characters:
            cid = char.character_id if hasattr(char, 'character_id') else char.get('character_id')
            if cid == 0:
                # character_id=0 是旁白，优先使用用户显式选择的 voice_id
                char_voice_map[0] = narrator_voice
                continue
            gender = (char.gender if hasattr(char, 'gender') else char.get('gender', 'female')) or 'female'
            char_voice_map[cid] = DEFAULT_VOICE_BY_GENDER.get(gender.lower(), "female-shaonv")
    if verbose:
        print(f"[TTS] char_voice_map: {char_voice_map}")
        for s in scenes:
            resolved = char_voice_map.get(s.speaker_id, voice_id or 'default(config)')
            print(f"[TTS] Scene {s.scene_id} speaker_id={s.speaker_id} -> voice={resolved}")

    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def _generate_with_semaphore(scene: Scene):
        async with semaphore:
            voiceover_text = (scene.voiceover or "").strip()
            if scene.speaker_id is None and voiceover_text:
                # speaker_id=None（对标分析模式）：检查是否有多人对话
                segments = _split_voiceover_by_speaker(voiceover_text)
                has_multi_speaker = len(segments) > 1 or (len(segments) == 1 and segments[0][0] != 'narrator')
                if has_multi_speaker:
                    # 有多人对话：用拆分合成方案
                    path, duration = await generate_voiceover_multi_speaker(
                        scene=scene,
                        output_dir=output_dir,
                        emotion=emotion,
                        speed=speed,
                        config=config,
                        verbose=verbose,
                        char_voice_map=char_voice_map if char_voice_map else None,
                    )
                else:
                    # 纯旁白：优先使用用户显式选择的 voice_id
                    path, duration = await generate_voiceover(
                        scene=scene,
                        output_dir=output_dir,
                        voice_id=narrator_voice,
                        emotion=emotion,
                        speed=speed,
                        config=config,
                        verbose=verbose,
                    )
            else:
                # 有 speaker_id：按角色映射选音色
                scene_voice = voice_id
                if char_voice_map and scene.speaker_id is not None:
                    scene_voice = char_voice_map.get(scene.speaker_id, voice_id)
                path, duration = await generate_voiceover(
                    scene=scene,
                    output_dir=output_dir,
                    voice_id=scene_voice,
                    emotion=emotion,
                    speed=speed,
                    config=config,
                    verbose=verbose,
                )
            results[scene.scene_id] = (path, duration)

    tasks = [_generate_with_semaphore(scene) for scene in scenes]
    await asyncio.gather(*tasks)

    return results


def generate_all_voiceovers_sync(
    scenes: list[Scene],
    output_dir: str,
    voice_id: Optional[str] = None,
    emotion: Optional[str] = None,
    speed: Optional[float] = None,
    config: Optional[PilipiliConfig] = None,
    max_concurrent: int = 5,
    verbose: bool = False,
    characters: Optional[list] = None,
) -> dict[int, tuple[str, float]]:
    """generate_all_voiceovers 的同步版本"""
    return asyncio.run(generate_all_voiceovers(
        scenes=scenes,
        output_dir=output_dir,
        voice_id=voice_id,
        emotion=emotion,
        speed=speed,
        config=config,
        max_concurrent=max_concurrent,
        verbose=verbose,
        characters=characters,
    ))


# ============================================================
# 音频工具函数
# ============================================================

def get_audio_duration(audio_path: str) -> float:
    """
    获取音频文件的精确时长（秒）
    支持 MP3 / WAV / M4A
    """
    try:
        # 优先使用 mutagen（更准确）
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        from mutagen.wave import WAVE

        ext = Path(audio_path).suffix.lower()
        if ext == ".mp3":
            audio = MP3(audio_path)
            return audio.info.length
        elif ext in [".m4a", ".mp4"]:
            audio = MP4(audio_path)
            return audio.info.length
        elif ext == ".wav":
            audio = WAVE(audio_path)
            return audio.info.length
    except ImportError:
        pass

    # 回退：使用 wave 标准库（仅支持 WAV）
    try:
        if audio_path.endswith(".wav"):
            with wave.open(audio_path, "r") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                return frames / float(rate)
    except Exception:
        pass

    # 最后回退：使用 ffprobe
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass

    # 无法获取时长，返回估算值（每字约 0.3 秒）
    return 5.0


def update_scene_durations(
    scenes: list[Scene],
    voiceover_results: dict[int, tuple[str, float]],
    padding: float = 0.5,
) -> list[Scene]:
    """
    根据 TTS 实际时长更新分镜的 duration 字段

    Args:
        scenes: 分镜列表
        voiceover_results: TTS 生成结果 {scene_id: (path, duration)}
        padding: 额外缓冲时间（秒），避免画面切换太急

    Returns:
        更新后的分镜列表
    """
    for scene in scenes:
        if scene.scene_id in voiceover_results:
            _, tts_duration = voiceover_results[scene.scene_id]
            if tts_duration > 0:
                # 视频时长 = TTS 时长 + 缓冲
                # 向上取整到最近的 0.5 秒
                raw_duration = tts_duration + padding
                scene.duration = round(raw_duration * 2) / 2  # 取最近的 0.5 倍数

    return scenes
