"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Collapse,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  Upload,
  message
} from "antd";
import { CustomerServiceOutlined, InboxOutlined, RocketOutlined, SoundOutlined, UploadOutlined } from "@ant-design/icons";
import type { UploadFile, UploadProps } from "antd";

import { useLanguage } from "@/components/language-provider";
import { createProject, getConnectorStatus, isSetupRequiredError, listTtsVoices, previewTtsVoice, uploadReference } from "@/lib/api";
import type { ConnectorStatus, VoiceOption } from "@/lib/types";

interface Props {
  onCreated: (projectId: string) => void;
  variant?: "simple" | "studio";
}

interface FormValues {
  topic: string;
  style?: string;
  target_duration: number;
  voice_id?: string;
  video_engine: "kling" | "seedance" | "minimax" | "auto";
  resolution: "720p" | "1080p" | "4K";
  aspect_ratio: "9:16" | "16:9";
  add_subtitles: boolean;
  global_style_prompt?: string;
}

export function CreateProjectForm({ onCreated, variant = "studio" }: Props) {
  const { isZh } = useLanguage();
  const [form] = Form.useForm<FormValues>();
  const [submitting, setSubmitting] = useState(false);
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [voiceLoading, setVoiceLoading] = useState(true);
  const [voiceFallback, setVoiceFallback] = useState(false);
  const [connectors, setConnectors] = useState<ConnectorStatus | null>(null);
  const [previewingVoiceId, setPreviewingVoiceId] = useState<string>();
  const [voiceLanguageFilter, setVoiceLanguageFilter] = useState<string>("all");
  const [voiceTagFilter, setVoiceTagFilter] = useState<string>("all");
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ uid: string; path: string }>>([]);
  const [messageApi, contextHolder] = message.useMessage();
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>();
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const uploadProps: UploadProps = useMemo(
    () => ({
      multiple: true,
      fileList,
      customRequest: async ({ file, onSuccess, onError }) => {
        try {
          const currentFile = file as UploadFile;
          const result = await uploadReference(file as File);
          setUploadedFiles((prev) => [...prev, { uid: currentFile.uid, path: result.path }]);
          onSuccess?.(result);
          messageApi.success(isZh ? `${result.filename} 上传成功` : `${result.filename} uploaded successfully`);
        } catch (error) {
          onError?.(error as Error);
          messageApi.error((error as Error).message);
        }
      },
      onChange: ({ fileList: nextFileList }) => {
        setFileList(nextFileList);
      },
      onRemove: (file) => {
        setUploadedFiles((prev) => prev.filter((item) => item.uid !== file.uid));
      }
    }),
    [fileList, messageApi]
  );

  useEffect(() => {
    let cancelled = false;

    async function loadConfigAwareVoices() {
      setVoiceLoading(true);
      try {
        const connectorData = await getConnectorStatus();
        if (cancelled) {
          return;
        }
        setConnectors(connectorData);

        const initialVoice = form.getFieldValue("voice_id") || connectorData.tts.default_voice;
        if (initialVoice) {
          form.setFieldValue("voice_id", initialVoice);
          setSelectedVoiceId(initialVoice);
        }

        if (!connectorData.tts.voice_catalog_supported) {
          setVoices([]);
          setVoiceFallback(false);
          return;
        }

        const result = await listTtsVoices({ source: "system" });
        if (cancelled) {
          return;
        }
        setVoices(result.voices);
        setVoiceFallback(result.fallback);
        const catalogVoice = form.getFieldValue("voice_id") || result.default_voice || result.voices[0]?.id;
        if (catalogVoice) {
          form.setFieldValue("voice_id", catalogVoice);
          setSelectedVoiceId(catalogVoice);
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

    void loadConfigAwareVoices();

    return () => {
      cancelled = true;
      audioRef.current?.pause();
      audioRef.current = null;
    };
  }, [form, messageApi]);

  const supportsVoiceCatalog = connectors?.tts.voice_catalog_supported ?? true;

  const selectedVoice = useMemo(
    () => voices.find((item) => item.id === (selectedVoiceId || form.getFieldValue("voice_id"))),
    [form, selectedVoiceId, voices]
  );

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
      const list = groups.get(key) || [];
      list.push(voice);
      groups.set(key, list);
    }
    return Array.from(groups.entries()).map(([language, groupVoices]) => ({
      label: `${language} · ${groupVoices.length} 个音色`,
      options: groupVoices.map((voice) => ({
        value: voice.id,
        label: `${voice.name} · ${voice.tags.slice(0, 2).join(" / ") || "general"}`,
      })),
    }));
  }, [visibleVoices]);

  async function handlePreview() {
    const voiceId = form.getFieldValue("voice_id");
      if (!voiceId) {
      messageApi.warning(isZh ? "请先选择一个音色" : "Select a voice first");
      return;
    }
    setPreviewingVoiceId(voiceId);
    try {
      const result = await previewTtsVoice(voiceId);
      audioRef.current?.pause();
      audioRef.current = new Audio(result.audio_url);
      audioRef.current.onended = () => setPreviewingVoiceId(undefined);
      audioRef.current.onerror = () => setPreviewingVoiceId(undefined);
      await audioRef.current.play();
    } catch (error) {
      messageApi.error((error as Error).message);
      setPreviewingVoiceId(undefined);
      return;
    }
  }

  async function onFinish(values: FormValues) {
    setSubmitting(true);
    try {
      const result = await createProject({
        ...values,
        reference_images: uploadedFiles.map((item) => item.path)
      });
      messageApi.success(result.message);
      onCreated(result.project_id);
      form.resetFields();
      if (selectedVoiceId) {
        form.setFieldValue("voice_id", selectedVoiceId);
      }
      setUploadedFiles([]);
      setFileList([]);
    } catch (error) {
      if (isSetupRequiredError(error)) {
        messageApi.warning(isZh ? "当前配置不完整，已经为你打开 Setup 配置窗口。" : "Configuration is incomplete. The Setup dialog has been opened for you.");
      } else {
        messageApi.error((error as Error).message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  const isSimple = variant === "simple";

  return (
    <Card className={`lingti-card ${isSimple ? "lingti-card-soft" : ""}`}>
      {contextHolder}
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <div className="workspace-title">
          <Typography.Title level={3}>
            {isSimple ? (isZh ? "快速发起一个视频任务" : "Start a video project quickly") : (isZh ? "专业工作台 · 新建任务" : "Studio · Create Project")}
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            {isSimple
              ? (isZh ? "只填核心信息就能开始。高级参数默认走推荐值，需要时再展开。" : "Fill only the essentials to start. Advanced parameters stay on recommended defaults until you need them.")
              : (isZh ? "保留完整控制项，适合频繁创建、排错、恢复和精调工作流。" : "Keep full control over creation, debugging, recovery, and workflow tuning.")}
          </Typography.Paragraph>
        </div>
        <Form<FormValues>
          form={form}
          layout="vertical"
          initialValues={{
            target_duration: isSimple ? 40 : 60,
            video_engine: "kling",
            resolution: "1080p",
            aspect_ratio: "9:16",
            add_subtitles: true
          }}
          onFinish={onFinish}
        >
          <Form.Item
            name="topic"
            label={isZh ? "主题需求" : "Project brief"}
            rules={[{ required: true, message: isZh ? "请输入主题" : "Enter a topic" }]}
          >
            <Input.TextArea
              rows={isSimple ? 5 : 4}
              placeholder={isZh ? "例如：几个老年人在现代化酒店里休闲打牌，前景讲解养老项目，画面高端优雅" : "Example: elderly people playing cards in a modern hotel while a host introduces a retirement service in a premium visual style"}
              showCount
              maxLength={800}
            />
          </Form.Item>
          <Form.Item name="style" label={isZh ? "风格描述" : "Style direction"}>
            <Input placeholder={isZh ? "例如：高级酒店广告、温暖阳光、克制旁白" : "Example: premium hospitality ad, warm sunlight, restrained narration"} />
          </Form.Item>

          <Card className="lingti-mini-card voice-card" size="small">
            <Space direction="vertical" size={14} style={{ width: "100%" }}>
              <div className="voice-card-header">
                <Space>
                  <CustomerServiceOutlined />
                  <Typography.Text strong>{isZh ? "旁白音色" : "Narration voice"}</Typography.Text>
                  {supportsVoiceCatalog ? (
                    voiceFallback ? <Tag color="gold">{isZh ? "回退列表" : "Fallback list"}</Tag> : <Tag color="blue">{isZh ? "MiniMax 官方目录" : "MiniMax official catalog"}</Tag>
                  ) : (
                    <Tag color="default">{isZh ? "手动 voice_id" : "Manual voice_id"}</Tag>
                  )}
                </Space>
                {supportsVoiceCatalog ? (
                  <Button
                    type="default"
                    icon={<SoundOutlined />}
                    loading={Boolean(previewingVoiceId)}
                    onClick={() => void handlePreview()}
                    disabled={!form.getFieldValue("voice_id")}
                  >
                    {isZh ? "试听当前音色" : "Preview selected voice"}
                  </Button>
                ) : null}
              </div>

              {supportsVoiceCatalog ? (
                <Form.Item name="voice_id" label={isZh ? "选择音色" : "Select voice"} style={{ marginBottom: 0 }}>
                  <Select
                    showSearch
                    loading={voiceLoading}
                    optionFilterProp="label"
                    placeholder={isZh ? "请选择一个旁白音色" : "Select a narration voice"}
                    options={groupedVoiceOptions}
                    onChange={(value) => setSelectedVoiceId(value)}
                    notFoundContent={voiceLoading ? (isZh ? "音色加载中..." : "Loading voices...") : (isZh ? "当前筛选下没有可用音色" : "No voice found for the current filters")}
                  />
                </Form.Item>
              ) : (
                <Form.Item name="voice_id" label={isZh ? "填写 voice_id" : "Enter voice_id"} style={{ marginBottom: 0 }}>
                  <Input placeholder={isZh ? "当前 TTS provider 不依赖 MiniMax 音色目录，请手动输入 voice_id" : "The current TTS provider does not use the MiniMax voice catalog. Enter a voice_id manually."} />
                </Form.Item>
              )}

              {supportsVoiceCatalog ? (
                <Space wrap size={12}>
                  <Select
                    size="small"
                    value={voiceLanguageFilter}
                    style={{ width: 156 }}
                    onChange={setVoiceLanguageFilter}
                    options={[
                      { value: "all", label: isZh ? "全部语言" : "All languages" },
                      ...voiceLanguages.map((language) => ({ value: language, label: language })),
                    ]}
                  />
                  <Select
                    size="small"
                    value={voiceTagFilter}
                    style={{ width: 168 }}
                    onChange={setVoiceTagFilter}
                    options={[
                      { value: "all", label: isZh ? "全部风格" : "All styles" },
                      ...voiceTags.map((tag) => ({ value: tag, label: tag })),
                    ]}
                  />
                  <Typography.Text type="secondary">
                    {isZh ? `当前显示 ${visibleVoices.length} / ${voices.length} 个音色` : `Showing ${visibleVoices.length} / ${voices.length} voices`}
                  </Typography.Text>
                </Space>
              ) : null}

              {supportsVoiceCatalog && voiceFallback ? (
                <Alert
                  type="warning"
                  showIcon
                  message={isZh ? "官方音色目录暂时不可用" : "The official voice catalog is temporarily unavailable"}
                  description={isZh ? "当前展示的是本地回退音色列表，你仍然可以继续创建并生成视频。" : "A local fallback voice list is shown right now. You can still continue and generate videos."}
                />
              ) : !supportsVoiceCatalog ? (
                <Alert
                  type="info"
                  showIcon
                  message={isZh ? "当前 TTS provider 不提供内置音色目录" : "The current TTS provider does not expose a built-in voice catalog"}
                  description={isZh ? "创建任务时会直接把你填写的 voice_id 传给后端，不再显示 MiniMax 音色选择器。" : "The voice_id you enter will be passed directly to the backend. The MiniMax voice picker is hidden for this provider."}
                />
              ) : null}

              {supportsVoiceCatalog && selectedVoice ? (
                <div className="voice-card-meta">
                  <Space wrap size={[8, 8]}>
                    <Tag color="cyan">{selectedVoice.language}</Tag>
                    <Tag color={selectedVoice.source_type === "system" ? "blue" : "purple"}>
                      {selectedVoice.source_type}
                    </Tag>
                    {selectedVoice.tags.map((tag) => (
                      <Tag key={tag}>{tag}</Tag>
                    ))}
                  </Space>
                  <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                    {selectedVoice.description || (isZh ? "这个音色适合做视频旁白、讲解或人物对白。" : "This voice works well for narration, explainers, or character dialogue.")}
                  </Typography.Paragraph>
                  <Typography.Text type="secondary">
                    {isZh ? "试听文案固定为一段标准旁白，便于你快速横向比较不同音色。" : "Preview uses a fixed sample script so you can compare voices quickly."}
                  </Typography.Text>
                </div>
              ) : null}
            </Space>
          </Card>

          <Space wrap size={16} style={{ display: "flex", marginBottom: 8 }}>
            <Form.Item name="target_duration" label={isZh ? "目标时长" : "Target duration"}>
              <InputNumber min={15} max={180} />
            </Form.Item>
            <Form.Item name="aspect_ratio" label={isZh ? "画面比例" : "Aspect ratio"}>
              <Select
                style={{ width: 144 }}
                options={[
                  { value: "9:16", label: isZh ? "9:16 竖屏" : "9:16 vertical" },
                  { value: "16:9", label: isZh ? "16:9 横屏" : "16:9 horizontal" }
                ]}
              />
            </Form.Item>
            <Form.Item name="add_subtitles" label={isZh ? "字幕" : "Subtitles"} valuePropName="checked">
              <Switch checkedChildren={isZh ? "开启" : "On"} unCheckedChildren={isZh ? "关闭" : "Off"} />
            </Form.Item>
          </Space>

          <Form.Item label={isZh ? "参考图 / 参考视频" : "Reference images / videos"}>
            <Upload.Dragger {...uploadProps} accept="image/*,video/*">
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">{isZh ? "上传人物图、产品图或参考视频" : "Upload character images, product images, or reference videos"}</p>
              <p className="ant-upload-hint">
                {isZh ? `当前已上传 ${uploadedFiles.length} 个素材，后端会自动用作参考图或截帧。` : `${uploadedFiles.length} assets uploaded. The backend will use them as references or extract frames automatically.`}
              </p>
            </Upload.Dragger>
          </Form.Item>

          <Collapse
            ghost
            className="lingti-collapse"
            items={[
              {
                key: "advanced",
                label: isSimple ? (isZh ? "高级参数" : "Advanced settings") : (isZh ? "引擎与一致性设置" : "Engine and consistency settings"),
                children: (
                  <>
                    <Space wrap size={16} style={{ display: "flex", marginBottom: 8 }}>
                      <Form.Item name="video_engine" label={isZh ? "视频引擎" : "Video engine"}>
                        <Select
                          style={{ width: 144 }}
                          options={[
                            { value: "kling", label: "Kling" },
                            { value: "minimax", label: "MiniMax Video" },
                            { value: "seedance", label: "Seedance" },
                            { value: "auto", label: "Auto" }
                          ]}
                        />
                      </Form.Item>
                      <Form.Item name="resolution" label={isZh ? "分辨率" : "Resolution"}>
                        <Select
                          style={{ width: 144 }}
                          options={[
                            { value: "720p", label: "720p" },
                            { value: "1080p", label: "1080p" },
                            { value: "4K", label: "4K" }
                          ]}
                        />
                      </Form.Item>
                    </Space>
                    <Form.Item name="global_style_prompt" label={isZh ? "全局风格提示词" : "Global style prompt"}>
                      <Input placeholder={isZh ? "用于约束全片风格一致性，可留空" : "Used to keep style consistency across the whole video. Optional."} />
                    </Form.Item>
                  </>
                )
              }
            ]}
          />

          <Button
            type="primary"
            htmlType="submit"
            size="large"
            loading={submitting}
            icon={isSimple ? <RocketOutlined /> : <UploadOutlined />}
          >
            {isSimple ? (isZh ? "开始生成" : "Start generation") : (isZh ? "启动工作流" : "Start workflow")}
          </Button>
        </Form>
      </Space>
    </Card>
  );
}
