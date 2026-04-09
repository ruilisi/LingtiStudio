"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Empty,
  Form,
  Input,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  Upload,
  message
} from "antd";
import {
  InboxOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SwapOutlined,
  UploadOutlined
} from "@ant-design/icons";

import { useLanguage } from "@/components/language-provider";
import {
  createProjectFromAnalysis,
  getAnalysisTask,
  removeAnalysisCharacter,
  replaceAnalysisCharacter,
  uploadAnalysisVideo
} from "@/lib/api";
import type { AnalysisTask } from "@/lib/types";

export function AnalysisClient() {
  const { isZh } = useLanguage();
  const [task, setTask] = useState<AnalysisTask | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm<{ topic?: string; video_engine?: "kling" | "seedance" | "minimax" | "auto" }>();

  async function refreshTask(analysisId?: string) {
    const id = analysisId || task?.analysis_id;
    if (!id) {
      return;
    }
    try {
      const next = await getAnalysisTask(id);
      setTask(next);
    } catch (error) {
      messageApi.error((error as Error).message);
    }
  }

  useEffect(() => {
    if (!task?.analysis_id || task.status !== "processing") {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshTask(task.analysis_id);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [task?.analysis_id, task?.status]);

  async function handleUpload(file: File) {
    setLoading(true);
    try {
      const result = await uploadAnalysisVideo(file);
      setTask({
        analysis_id: result.analysis_id,
        status: "processing"
      });
      messageApi.success(result.message);
    } catch (error) {
      messageApi.error((error as Error).message);
    } finally {
      setLoading(false);
    }
    return false;
  }

  async function handleReplace(characterId: number, file: File) {
    if (!task?.analysis_id) {
      return false;
    }
    try {
      await replaceAnalysisCharacter(task.analysis_id, characterId, file);
      messageApi.success(isZh ? "人物替换参考图已更新" : "Replacement character image updated");
      await refreshTask();
    } catch (error) {
      messageApi.error((error as Error).message);
    }
    return false;
  }

  async function handleRemove(characterId: number) {
    if (!task?.analysis_id) {
      return;
    }
    try {
      await removeAnalysisCharacter(task.analysis_id, characterId);
      messageApi.success(isZh ? "已删除替换参考图" : "Replacement image removed");
      await refreshTask();
    } catch (error) {
      messageApi.error((error as Error).message);
    }
  }

  async function handleCreateProject(values: { topic?: string; video_engine?: "kling" | "seedance" | "minimax" | "auto" }) {
    if (!task?.analysis_id) {
      return;
    }
    setCreating(true);
    try {
      const result = await createProjectFromAnalysis(task.analysis_id, {
        topic: values.topic,
        video_engine: values.video_engine || "kling",
        add_subtitles: true
      });
      messageApi.success(isZh ? `${result.message}，项目 ${result.project_id}` : `${result.message}, project ${result.project_id}`);
    } catch (error) {
      messageApi.error((error as Error).message);
    } finally {
      setCreating(false);
    }
  }

  const sceneItems = useMemo(
    () =>
      (task?.result?.scenes || []).map((scene) => ({
        key: String(scene.scene_id),
        label: `Scene ${scene.scene_id} · ${scene.duration}s`,
        children: (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <Typography.Text>{scene.voiceover}</Typography.Text>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              图像提示词：{scene.image_prompt}
            </Typography.Paragraph>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              视频提示词：{scene.video_prompt}
            </Typography.Paragraph>
          </Space>
        )
      })),
    [task]
  );

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      {contextHolder}
      <div className="workspace-header">
        <div className="workspace-title">
          <Typography.Title level={2}>对标视频分析</Typography.Title>
          <Typography.Paragraph type="secondary">
            {isZh
              ? "上传一个参考视频，自动拆解人物、分镜、提示词和整体风格，再直接创建新项目。"
              : "Upload a reference video to break down characters, scenes, prompts, and overall style, then create a new project directly."}
          </Typography.Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => void refreshTask()} disabled={!task?.analysis_id}>
          {isZh ? "刷新" : "Refresh"}
        </Button>
      </div>

      <Card className="lingti-card">
        <Upload.Dragger accept="video/*" beforeUpload={handleUpload} showUploadList={false} disabled={loading}>
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">{isZh ? "拖入或点击上传对标视频" : "Drop or click to upload a reference video"}</p>
          <p className="ant-upload-hint">{isZh ? "支持 mp4 / mov / avi / mkv / webm / flv" : "Supports mp4 / mov / avi / mkv / webm / flv"}</p>
        </Upload.Dragger>
      </Card>

      {task ? (
        <Row gutter={[24, 24]}>
          <Col xs={24} xl={8}>
            <Space direction="vertical" size={24} style={{ width: "100%" }}>
              <Card className="lingti-card" title={isZh ? "分析状态" : "Analysis Status"}>
                <DescriptionsBlock
                  rows={[
                    [isZh ? "任务 ID" : "Task ID", task.analysis_id],
                    [isZh ? "状态" : "Status", task.status],
                    [isZh ? "文件名" : "Filename", task.filename || "-"],
                    [isZh ? "创建时间" : "Created at", task.created_at || "-"]
                  ]}
                />
                {task.status === "processing" ? (
                  <Alert
                    style={{ marginTop: 16 }}
                    type="info"
                    showIcon
                    message={isZh ? "Gemini 分析中" : "Gemini is analyzing"}
                    description={isZh ? "页面会自动轮询结果。" : "The page will poll for results automatically."}
                  />
                ) : null}
                {task.status === "failed" ? (
                  <Alert
                    style={{ marginTop: 16 }}
                    type="error"
                    showIcon
                    message={isZh ? "分析失败" : "Analysis failed"}
                    description={task.error || (isZh ? "未知错误" : "Unknown error")}
                  />
                ) : null}
              </Card>

              <Card className="lingti-card" title={isZh ? "基于分析创建项目" : "Create project from analysis"}>
                <Form form={form} layout="vertical" onFinish={handleCreateProject} initialValues={{ video_engine: "kling" }}>
                  <Form.Item name="topic" label={isZh ? "新项目主题" : "New project topic"}>
                    <Input placeholder={isZh ? "留空则使用分析出的标题" : "Leave empty to use the analyzed title"} />
                  </Form.Item>
                  <Form.Item name="video_engine" label={isZh ? "视频引擎" : "Video engine"}>
                    <Select
                      options={[
                        { value: "kling", label: "Kling" },
                        { value: "minimax", label: "MiniMax Video" },
                        { value: "seedance", label: "Seedance" },
                        { value: "auto", label: "Auto" }
                      ]}
                    />
                  </Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<PlayCircleOutlined />}
                    loading={creating}
                    disabled={task.status !== "completed"}
                  >
                    {isZh ? "创建项目" : "Create project"}
                  </Button>
                </Form>
              </Card>
            </Space>
          </Col>

          <Col xs={24} xl={16}>
            {task.status === "completed" && task.result ? (
              <Space direction="vertical" size={24} style={{ width: "100%" }}>
                <Card className="lingti-card" title={isZh ? "整体分析" : "Overall Analysis"}>
                  <Space direction="vertical" size={10} style={{ width: "100%" }}>
                    <Typography.Title level={4} style={{ margin: 0 }}>
                      {task.result.title}
                    </Typography.Title>
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      {task.result.style}
                    </Typography.Paragraph>
                    <Space wrap>
                      <Tag color="blue">{task.result.aspect_ratio}</Tag>
                      <Tag color="cyan">{task.result.total_duration}s</Tag>
                      <Tag color="geekblue">{task.result.color_grade}</Tag>
                    </Space>
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      {isZh ? "全局风格提示词：" : "Global style prompt: "}{task.result.overall_prompt}
                    </Typography.Paragraph>
                  </Space>
                </Card>

                <Card className="lingti-card" title={isZh ? "人物替换" : "Character Replacement"}>
                  {task.result.characters.length ? (
                    <Space direction="vertical" size={16} style={{ width: "100%" }}>
                      {task.result.characters.map((character) => (
                        <div key={character.character_id} className="artifact-item">
                          <Space direction="vertical" size={10} style={{ width: "100%" }}>
                            <Space wrap>
                              <Tag color="blue">{character.name}</Tag>
                              {character.replacement_image ? <Tag color="green">{isZh ? "已替换" : "Replaced"}</Tag> : <Tag>{isZh ? "使用原人物" : "Using original character"}</Tag>}
                            </Space>
                            <Typography.Text>{character.description}</Typography.Text>
                            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                              {character.appearance_prompt}
                            </Typography.Paragraph>
                            <Space wrap>
                              <Upload beforeUpload={(file) => handleReplace(character.character_id, file)} showUploadList={false}>
                                <Button icon={<UploadOutlined />}>{isZh ? "上传替换图" : "Upload replacement image"}</Button>
                              </Upload>
                              {character.replacement_image ? (
                                <Button icon={<SwapOutlined />} onClick={() => void handleRemove(character.character_id)}>
                                  {isZh ? "移除替换图" : "Remove replacement"}
                                </Button>
                              ) : null}
                            </Space>
                          </Space>
                        </div>
                      ))}
                    </Space>
                  ) : (
                    <Empty description={isZh ? "没有识别到可替换人物" : "No replaceable characters detected"} />
                  )}
                </Card>

                <Card className="lingti-card" title={isZh ? "分镜拆解" : "Scene Breakdown"}>
                  <Collapse items={sceneItems} />
                </Card>
              </Space>
            ) : (
              <Card className="lingti-card">
                <Empty description={isZh ? "上传视频后，这里会显示人物、分镜和提示词分析结果。" : "After uploading a video, this section will show characters, scenes, and prompt analysis."} />
              </Card>
            )}
          </Col>
        </Row>
      ) : null}
    </Space>
  );
}

function DescriptionsBlock({ rows }: { rows: Array<[string, string | number]> }) {
  return (
    <Space direction="vertical" size={10} style={{ width: "100%" }}>
      {rows.map(([label, value]) => (
        <div key={label} className="system-stat-row">
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </Space>
  );
}
