"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Button,
  Col,
  Form,
  Input,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { SoundOutlined } from "@ant-design/icons";

import { useLanguage } from "@/components/language-provider";
import { listTtsVoices, previewTtsVoice, updateApiKeys } from "@/lib/api";
import type { ProviderOption, SystemSetup, VoiceOption } from "@/lib/types";

type FormValues = {
  llm_provider?: string;
  llm_model?: string;
  llm_api_key?: string;
  image_provider?: string;
  image_model?: string;
  image_gen_api_key?: string;
  video_provider?: string;
  video_model?: string;
  minimax_video_api_key?: string;
  kling_api_key?: string;
  kling_api_secret?: string;
  seedance_api_key?: string;
  tts_provider?: string;
  tts_model?: string;
  tts_api_key?: string;
  tts_default_voice?: string;
  mem0_api_key?: string;
};

function findProviderOption(options: ProviderOption[], value?: string) {
  return options.find((item) => item.value === value);
}

function withCurrentOption(options: ProviderOption[], currentValue?: string) {
  if (!currentValue || options.some((item) => item.value === currentValue)) {
    return options;
  }
  return [{ value: currentValue, label: `${currentValue} (current)`, models: [] }, ...options];
}

export function ConfigurationForm({
  setup,
  submitText = "保存配置",
  onSaved,
  showTitle = false,
}: {
  setup: SystemSetup | null;
  submitText?: string;
  onSaved?: () => Promise<void> | void;
  showTitle?: boolean;
}) {
  const { isZh } = useLanguage();
  const [form] = Form.useForm<FormValues>();
  const [saving, setSaving] = useState(false);
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [voiceFallback, setVoiceFallback] = useState(false);
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [voiceLanguageFilter, setVoiceLanguageFilter] = useState<string>("all");
  const [voiceTagFilter, setVoiceTagFilter] = useState<string>("all");
  const [previewingVoiceId, setPreviewingVoiceId] = useState<string>();
  const [messageApi, contextHolder] = message.useMessage();
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const watchedLlmProvider = Form.useWatch("llm_provider", form);
  const watchedImageProvider = Form.useWatch("image_provider", form);
  const watchedVideoProvider = Form.useWatch("video_provider", form);
  const watchedTtsProvider = Form.useWatch("tts_provider", form);
  const watchedVoiceId = Form.useWatch("tts_default_voice", form);

  useEffect(() => {
    if (!setup) {
      return;
    }
    form.setFieldsValue({
      llm_provider: setup.current.llm_provider,
      llm_model: setup.current.llm_model,
      image_provider: setup.current.image_provider,
      image_model: setup.current.image_model,
      video_provider: setup.current.video_provider,
      video_model: setup.current.video_model,
      tts_provider: setup.current.tts_provider,
      tts_model: setup.current.tts_model,
      tts_default_voice: setup.current.tts_default_voice,
    });
  }, [form, setup]);

  const supportsVoiceCatalog = (watchedTtsProvider || setup?.current.tts_provider || "minimax") === "minimax";

  useEffect(() => {
    if (!setup) {
      return;
    }
    if (!supportsVoiceCatalog) {
      setVoices([]);
      setVoiceFallback(false);
      return;
    }

    let cancelled = false;
    async function loadVoices() {
      setVoiceLoading(true);
      try {
        const result = await listTtsVoices({ source: "system" });
        if (cancelled) {
          return;
        }
        setVoices(result.voices);
        setVoiceFallback(result.fallback);
        const currentVoice = form.getFieldValue("tts_default_voice") || result.default_voice || result.voices[0]?.id;
        if (currentVoice) {
          form.setFieldValue("tts_default_voice", currentVoice);
        }
      } catch (error) {
        if (!cancelled) {
          messageApi.error((error as Error).message);
        }
      } finally {
        if (!cancelled) {
          setVoiceLoading(false);
        }
      }
    }

    void loadVoices();

    return () => {
      cancelled = true;
      audioRef.current?.pause();
      audioRef.current = null;
    };
  }, [form, messageApi, setup, supportsVoiceCatalog]);

  const llmModels = useMemo(
    () => findProviderOption(setup?.options.llm_providers || [], watchedLlmProvider || setup?.current.llm_provider)?.models || [],
    [setup, watchedLlmProvider]
  );
  const imageModels = useMemo(
    () => findProviderOption(setup?.options.image_providers || [], watchedImageProvider || setup?.current.image_provider)?.models || [],
    [setup, watchedImageProvider]
  );
  const videoModels = useMemo(
    () => findProviderOption(setup?.options.video_providers || [], watchedVideoProvider || setup?.current.video_provider)?.models || [],
    [setup, watchedVideoProvider]
  );
  const ttsModels = useMemo(() => {
    const options = setup?.options.tts_providers || [];
    const selected = watchedTtsProvider || setup?.current.tts_provider;
    const matched = findProviderOption(options, selected);
    if (matched) {
      return matched.models;
    }
    return setup?.current.tts_model ? [setup.current.tts_model] : [];
  }, [setup, watchedTtsProvider]);

  const llmProviderOptions = withCurrentOption(setup?.options.llm_providers || [], setup?.current.llm_provider);
  const imageProviderOptions = withCurrentOption(setup?.options.image_providers || [], setup?.current.image_provider);
  const videoProviderOptions = withCurrentOption(setup?.options.video_providers || [], setup?.current.video_provider);
  const ttsProviderOptions = withCurrentOption(setup?.options.tts_providers || [], setup?.current.tts_provider);

  const voiceLanguages = useMemo(
    () => Array.from(new Set(voices.map((item) => item.language).filter(Boolean))).sort(),
    [voices]
  );
  const voiceTags = useMemo(
    () => Array.from(new Set(voices.flatMap((item) => item.tags || []).filter(Boolean))).sort(),
    [voices]
  );
  const visibleVoices = useMemo(() => {
    return voices.filter((voice) => {
      if (voiceLanguageFilter !== "all" && voice.language !== voiceLanguageFilter) {
        return false;
      }
      if (voiceTagFilter !== "all" && !(voice.tags || []).includes(voiceTagFilter)) {
        return false;
      }
      return true;
    });
  }, [voiceLanguageFilter, voiceTagFilter, voices]);
  const groupedVoiceOptions = useMemo(() => {
    const groups = new Map<string, VoiceOption[]>();
    for (const voice of visibleVoices) {
      const key = voice.language || "other";
      const group = groups.get(key) || [];
      group.push(voice);
      groups.set(key, group);
    }
    return Array.from(groups.entries()).map(([language, groupVoices]) => ({
      label: `${language} · ${groupVoices.length} 个音色`,
      options: groupVoices.map((voice) => ({
        value: voice.id,
        label: `${voice.name} · ${voice.tags.slice(0, 2).join(" / ") || "general"}`,
      })),
    }));
  }, [visibleVoices]);

  const selectedVoice = useMemo(
    () => voices.find((voice) => voice.id === watchedVoiceId),
    [voices, watchedVoiceId]
  );

  async function handlePreview() {
    if (!watchedVoiceId) {
      messageApi.warning("请先选择一个默认音色");
      return;
    }
    setPreviewingVoiceId(watchedVoiceId);
    try {
      const result = await previewTtsVoice(watchedVoiceId);
      audioRef.current?.pause();
      audioRef.current = new Audio(result.audio_url);
      audioRef.current.onended = () => setPreviewingVoiceId(undefined);
      audioRef.current.onerror = () => setPreviewingVoiceId(undefined);
      await audioRef.current.play();
    } catch (error) {
      messageApi.error((error as Error).message);
      setPreviewingVoiceId(undefined);
    }
  }

  async function handleSubmit(values: FormValues) {
    setSaving(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(values).filter(([, value]) => typeof value === "string" && value.trim())
      );
      await updateApiKeys(payload);
      messageApi.success(isZh ? "配置已保存" : "Configuration saved");
      await onSaved?.();
    } catch (error) {
      messageApi.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      {contextHolder}
      {showTitle ? (
        <div className="workspace-title">
          <Typography.Title level={3}>{isZh ? "首次配置 LingtiStudio" : "Set up LingtiStudio"}</Typography.Title>
          <Typography.Paragraph type="secondary">
            {isZh
              ? "选择你要用的 provider 和模型，填完必要的密钥后就可以开始生成视频。"
              : "Choose the providers and models you want, fill in the required credentials, and start generating."}
          </Typography.Paragraph>
        </div>
      ) : null}

      {setup?.missing_requirements?.length ? (
        <Alert
          type="warning"
          showIcon
          message={isZh ? "当前配置还不完整" : "Configuration is still incomplete"}
          description={
            <Space direction="vertical" size={4}>
              {setup.missing_requirements.map((item) => (
                <span key={item.key}>{item.message}</span>
              ))}
              <span>{isZh ? "配置将写入" : "Configuration will be written to"}：{setup.config_path}</span>
            </Space>
          }
        />
      ) : null}

      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="llm_provider" label={isZh ? "默认 LLM Provider" : "Default LLM provider"}>
              <Select
                options={llmProviderOptions.map((item) => ({ value: item.value, label: item.label }))}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="llm_model" label={isZh ? "LLM 模型" : "LLM model"}>
              <Select
                showSearch
                options={llmModels.map((item) => ({ value: item, label: item }))}
                placeholder={isZh ? "选择或输入一个模型" : "Select or enter a model"}
              />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="llm_api_key" label="LLM API Key">
              <Input.Password placeholder="sk-..." />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="image_gen_api_key" label="Image API Key">
              <Input.Password placeholder={isZh ? "留空则按 provider 默认逻辑处理" : "Leave empty to use the provider default behavior"} />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="image_provider" label={isZh ? "图片 Provider" : "Image provider"}>
              <Select
                options={imageProviderOptions.map((item) => ({ value: item.value, label: item.label }))}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="image_model" label={isZh ? "图片模型" : "Image model"}>
              <Select
                showSearch
                options={imageModels.map((item) => ({ value: item, label: item }))}
                placeholder={isZh ? "选择图片模型" : "Select an image model"}
              />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="video_provider" label={isZh ? "默认视频 Provider" : "Default video provider"}>
              <Select
                options={videoProviderOptions.map((item) => ({ value: item.value, label: item.label }))}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="video_model" label={isZh ? "视频模型" : "Video model"}>
              <Select
                showSearch
                options={videoModels.map((item) => ({ value: item, label: item }))}
                placeholder={isZh ? "选择视频模型" : "Select a video model"}
              />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="minimax_video_api_key" label="MiniMax Video API Key">
              <Input.Password placeholder={isZh ? "可留空，默认复用 llm.minimax.api_key" : "Optional. Falls back to llm.minimax.api_key by default"} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="kling_api_key" label="Kling API Key">
              <Input.Password />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="kling_api_secret" label="Kling API Secret">
              <Input.Password />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="seedance_api_key" label="Seedance API Key">
              <Input.Password />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="mem0_api_key" label="Mem0 API Key">
              <Input.Password />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="tts_provider" label="TTS Provider">
              <Select
                options={ttsProviderOptions.map((item) => ({ value: item.value, label: item.label }))}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="tts_model" label={isZh ? "TTS 模型" : "TTS model"}>
              <Select
                showSearch
                options={ttsModels.map((item) => ({ value: item, label: item }))}
                placeholder={isZh ? "选择 TTS 模型" : "Select a TTS model"}
              />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="tts_api_key" label="TTS API Key">
              <Input.Password />
            </Form.Item>
          </Col>
        </Row>

        {supportsVoiceCatalog ? (
          <Space direction="vertical" size={14} style={{ width: "100%", marginBottom: 20 }}>
            <Space style={{ width: "100%", justifyContent: "space-between" }} wrap>
              <Space>
                <Typography.Text strong>{isZh ? "默认全局音色" : "Default voice"}</Typography.Text>
                {voiceFallback ? <Tag color="gold">{isZh ? "回退列表" : "Fallback list"}</Tag> : <Tag color="blue">{isZh ? "MiniMax 音色目录" : "MiniMax catalog"}</Tag>}
              </Space>
              <Button
                icon={<SoundOutlined />}
                onClick={() => void handlePreview()}
                loading={Boolean(previewingVoiceId)}
                disabled={!watchedVoiceId}
              >
                {isZh ? "试听默认音色" : "Preview default voice"}
              </Button>
            </Space>
            <Space wrap size={12}>
              <Select
                size="small"
                value={voiceLanguageFilter}
                style={{ width: 156 }}
                onChange={setVoiceLanguageFilter}
                options={[{ value: "all", label: isZh ? "全部语言" : "All languages" }, ...voiceLanguages.map((language) => ({ value: language, label: language }))]}
              />
              <Select
                size="small"
                value={voiceTagFilter}
                style={{ width: 168 }}
                onChange={setVoiceTagFilter}
                options={[{ value: "all", label: isZh ? "全部风格" : "All styles" }, ...voiceTags.map((tag) => ({ value: tag, label: tag }))]}
              />
            </Space>
            <Form.Item name="tts_default_voice" label={isZh ? "默认音色" : "Default voice"}>
              <Select
                showSearch
                loading={voiceLoading}
                optionFilterProp="label"
                placeholder={isZh ? "选择默认旁白音色" : "Select the default narration voice"}
                options={groupedVoiceOptions}
                notFoundContent={voiceLoading ? (isZh ? "音色加载中..." : "Loading voices...") : (isZh ? "当前筛选下没有可用音色" : "No voice found for the current filters")}
              />
            </Form.Item>
            {selectedVoice ? (
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <Space wrap size={[8, 8]}>
                  <Tag color="cyan">{selectedVoice.language}</Tag>
                  {selectedVoice.tags.map((tag) => (
                    <Tag key={tag}>{tag}</Tag>
                  ))}
                </Space>
                <Typography.Text type="secondary">
                  {selectedVoice.description || (isZh ? "这个音色会作为新任务的默认旁白音色。" : "This voice will be used as the default narration voice for new projects.")}
                </Typography.Text>
              </Space>
            ) : null}
          </Space>
        ) : (
          <Form.Item name="tts_default_voice" label={isZh ? "默认 voice_id" : "Default voice_id"}>
            <Input placeholder={isZh ? "当前 TTS provider 不支持内置音色目录，请手动输入 voice_id" : "The current TTS provider does not support a built-in voice catalog. Enter a voice_id manually."} />
          </Form.Item>
        )}

        <Button type="primary" htmlType="submit" loading={saving}>
          {submitText}
        </Button>
      </Form>
    </Space>
  );
}
