"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Row, Space, Tag, Typography, message } from "antd";
import { CheckCircleOutlined, ReloadOutlined } from "@ant-design/icons";

import { ConfigurationForm } from "@/components/configuration-form";
import { useLanguage } from "@/components/language-provider";
import { getConnectorStatus, getKeysStatus, getSystemHealth, getSystemSetup, testKey } from "@/lib/api";
import type { ConnectorStatus, KeysStatus, SystemHealth, SystemSetup } from "@/lib/types";

export function SettingsClient() {
  const { isZh } = useLanguage();
  const [status, setStatus] = useState<KeysStatus | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [connectors, setConnectors] = useState<ConnectorStatus | null>(null);
  const [setup, setSetup] = useState<SystemSetup | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

  async function refreshAll() {
    try {
      const [keys, health, connectorData, setupData] = await Promise.all([
        getKeysStatus(),
        getSystemHealth(),
        getConnectorStatus(),
        getSystemSetup(),
      ]);
      setStatus(keys);
      setSystemHealth(health);
      setConnectors(connectorData);
      setSetup(setupData);
    } catch (error) {
      messageApi.error((error as Error).message);
    }
  }

  useEffect(() => {
    void refreshAll();
  }, []);

  async function handleTest(service: string) {
    try {
      const result = await testKey(service);
      if (result.success) {
        messageApi.success(result.message);
      } else {
        messageApi.error(result.message);
      }
    } catch (error) {
      messageApi.error((error as Error).message);
    }
  }

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      {contextHolder}
      <div className="workspace-header">
        <div className="workspace-title">
          <Typography.Title level={2}>{isZh ? "设置与连接器" : "Setup and Connectors"}</Typography.Title>
          <Typography.Paragraph type="secondary">
            {isZh
              ? "配置 LingtiStudio 的默认 provider、模型和密钥。这里的修改会直接写入本地 `configs/config.yaml`。"
              : "Configure LingtiStudio providers, models, and credentials. Changes are written directly to your local `configs/config.yaml`."}
          </Typography.Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => void refreshAll()}>
          {isZh ? "刷新状态" : "Refresh"}
        </Button>
      </div>

      {setup?.onboarding_required ? (
        <Alert
          type="warning"
          showIcon
          message={isZh ? "当前仍有必需配置缺失" : "Required configuration is still missing"}
          description={
            <Space direction="vertical" size={4}>
              {!setup.config_exists ? <span>{isZh ? "本地 config.yaml 还不存在，保存配置后会自动创建。" : "No local config.yaml was found. It will be created automatically after you save setup."}</span> : null}
              {setup.missing_requirements.map((item) => (
                <span key={item.key}>{item.message}</span>
              ))}
            </Space>
          }
        />
      ) : (
        <Alert
          type="success"
          showIcon
          message={isZh ? "当前配置可用" : "Current configuration is valid"}
          description={`${isZh ? "配置文件位置" : "Config path"}：${setup?.config_path || "./configs/config.yaml"}`}
        />
      )}

      <Row gutter={[24, 24]}>
        <Col xs={24} xl={8}>
          <Space direction="vertical" size={24} style={{ width: "100%" }}>
            <Card className="lingti-card" title={isZh ? "系统健康" : "System Health"}>
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                <StatusLine label={isZh ? "系统状态" : "Status"} value={systemHealth?.status || (isZh ? "加载中" : "Loading")} />
                <StatusLine label={isZh ? "版本" : "Version"} value={systemHealth?.version || "-"} />
                <StatusLine label={isZh ? "默认视频引擎" : "Default video provider"} value={systemHealth?.defaults.video_provider || "-"} />
                <StatusLine label={isZh ? "默认 LLM" : "Default LLM"} value={systemHealth?.defaults.llm_provider || "-"} />
              </Space>
            </Card>

            <Card className="lingti-card" title={isZh ? "连接器状态" : "Connector Status"}>
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                {status ? (
                  <>
                    <StatusRow label={`LLM · ${status.llm.provider}`} configured={status.llm.configured} onTest={() => void handleTest("llm")} />
                    <StatusRow label={`Image · ${status.image_gen.provider}`} configured={status.image_gen.configured} onTest={() => void handleTest("image_gen")} />
                    <StatusRow label={`TTS · ${status.tts.provider}`} configured={status.tts.configured} onTest={() => void handleTest("tts")} />
                    <StatusRow label="MiniMax Video" configured={status.minimax_video.configured} onTest={() => void handleTest("minimax_video")} />
                    <StatusRow label="Kling" configured={status.kling.configured} onTest={() => void handleTest("kling")} />
                    <StatusRow label="Seedance" configured={status.seedance.configured} onTest={() => void handleTest("seedance")} />
                  </>
                ) : (
                  <Alert type="info" showIcon message={isZh ? "尚未获取到状态" : "Status not loaded yet"} />
                )}
              </Space>
            </Card>

            {connectors ? (
              <Card className="lingti-card" title={isZh ? "当前默认配置" : "Current Defaults"}>
                <Space direction="vertical" size={10} style={{ width: "100%" }}>
                  <StatusLine label="LLM" value={`${connectors.llm.default_provider} / ${connectors.llm.model}`} />
                  <StatusLine label={isZh ? "图像" : "Image"} value={`${connectors.image.provider} / ${connectors.image.model || "-"}`} />
                  <StatusLine label="TTS" value={`${connectors.tts.provider} / ${connectors.tts.model}`} />
                  <StatusLine label={isZh ? "默认 voice_id" : "Default voice_id"} value={connectors.tts.default_voice || "-"} />
                  <StatusLine label={isZh ? "视频" : "Video"} value={`${connectors.video.default_provider} / ${connectors.video.model || "-"}`} />
                  <div className="system-stat-row">
                    <span>{isZh ? "音色目录" : "Voice catalog"}</span>
                    <strong>{connectors.tts.voice_catalog_supported ? (isZh ? "MiniMax 内置音色" : "MiniMax built-in catalog") : (isZh ? "手动 voice_id" : "Manual voice_id")}</strong>
                  </div>
                </Space>
              </Card>
            ) : null}
          </Space>
        </Col>

        <Col xs={24} xl={16}>
          <Card className="lingti-card" title={isZh ? "编辑配置" : "Edit Config"}>
            <ConfigurationForm setup={setup} submitText={isZh ? "保存到 config.yaml" : "Save to config.yaml"} onSaved={refreshAll} />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}

function StatusRow({
  label,
  configured,
  onTest,
}: {
  label: string;
  configured: boolean;
  onTest: () => void;
}) {
  const { isZh } = useLanguage();
  return (
    <Card size="small" className="lingti-mini-card">
      <Space style={{ width: "100%", justifyContent: "space-between" }}>
        <Space>
          <CheckCircleOutlined style={{ color: configured ? "#4ade80" : "#a07575" }} />
          <Typography.Text strong>{label}</Typography.Text>
          <Tag color={configured ? "green" : "default"}>{configured ? (isZh ? "已配置" : "Configured") : (isZh ? "未配置" : "Missing")}</Tag>
        </Space>
        <Button size="small" onClick={onTest}>
          {isZh ? "测试" : "Test"}
        </Button>
      </Space>
    </Card>
  );
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="system-stat-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
