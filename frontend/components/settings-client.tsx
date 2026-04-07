"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Row, Space, Tag, Typography, message } from "antd";
import { CheckCircleOutlined, ReloadOutlined } from "@ant-design/icons";

import { ConfigurationForm } from "@/components/configuration-form";
import { getConnectorStatus, getKeysStatus, getSystemHealth, getSystemSetup, testKey } from "@/lib/api";
import type { ConnectorStatus, KeysStatus, SystemHealth, SystemSetup } from "@/lib/types";

export function SettingsClient() {
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
          <Typography.Title level={2}>Setup and Connectors</Typography.Title>
          <Typography.Paragraph type="secondary">
            配置 LingtiStudio 的默认 provider、模型和密钥。这里的修改会直接写入本地 `configs/config.yaml`。
          </Typography.Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => void refreshAll()}>
          刷新状态
        </Button>
      </div>

      {setup?.onboarding_required ? (
        <Alert
          type="warning"
          showIcon
          message="当前仍有必需配置缺失"
          description={
            <Space direction="vertical" size={4}>
              {!setup.config_exists ? <span>本地 config.yaml 还不存在，保存配置后会自动创建。</span> : null}
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
          message="当前配置可用"
          description={`配置文件位置：${setup?.config_path || "./configs/config.yaml"}`}
        />
      )}

      <Row gutter={[24, 24]}>
        <Col xs={24} xl={8}>
          <Space direction="vertical" size={24} style={{ width: "100%" }}>
            <Card className="lingti-card" title="System Health">
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                <StatusLine label="系统状态" value={systemHealth?.status || "加载中"} />
                <StatusLine label="版本" value={systemHealth?.version || "-"} />
                <StatusLine label="默认视频引擎" value={systemHealth?.defaults.video_provider || "-"} />
                <StatusLine label="默认 LLM" value={systemHealth?.defaults.llm_provider || "-"} />
              </Space>
            </Card>

            <Card className="lingti-card" title="Connector Status">
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                {status ? (
                  <>
                    <StatusRow label={`LLM · ${status.llm.provider}`} configured={status.llm.configured} onTest={() => void handleTest("llm")} />
                    <StatusRow label={`Image · ${status.image_gen.provider}`} configured={status.image_gen.configured} onTest={() => void handleTest("image_gen")} />
                    <StatusRow label={`TTS · ${status.tts.provider}`} configured={status.tts.configured} onTest={() => void handleTest("tts")} />
                    <StatusRow label="Kling" configured={status.kling.configured} onTest={() => void handleTest("kling")} />
                    <StatusRow label="Seedance" configured={status.seedance.configured} onTest={() => void handleTest("seedance")} />
                  </>
                ) : (
                  <Alert type="info" showIcon message="尚未获取到状态" />
                )}
              </Space>
            </Card>

            {connectors ? (
              <Card className="lingti-card" title="Current Defaults">
                <Space direction="vertical" size={10} style={{ width: "100%" }}>
                  <StatusLine label="LLM" value={`${connectors.llm.default_provider} / ${connectors.llm.model}`} />
                  <StatusLine label="图像" value={`${connectors.image.provider} / ${connectors.image.model || "-"}`} />
                  <StatusLine label="TTS" value={`${connectors.tts.provider} / ${connectors.tts.model}`} />
                  <StatusLine label="默认 voice_id" value={connectors.tts.default_voice || "-"} />
                  <StatusLine label="视频" value={`${connectors.video.default_provider} / ${connectors.video.model || "-"}`} />
                  <div className="system-stat-row">
                    <span>音色目录</span>
                    <strong>{connectors.tts.voice_catalog_supported ? "MiniMax 内置音色" : "手动 voice_id"}</strong>
                  </div>
                </Space>
              </Card>
            ) : null}
          </Space>
        </Col>

        <Col xs={24} xl={16}>
          <Card className="lingti-card" title="Edit Config">
            <ConfigurationForm setup={setup} submitText="保存到 config.yaml" onSaved={refreshAll} />
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
  return (
    <Card size="small" className="lingti-mini-card">
      <Space style={{ width: "100%", justifyContent: "space-between" }}>
        <Space>
          <CheckCircleOutlined style={{ color: configured ? "#4ade80" : "#a07575" }} />
          <Typography.Text strong>{label}</Typography.Text>
          <Tag color={configured ? "green" : "default"}>{configured ? "已配置" : "未配置"}</Tag>
        </Space>
        <Button size="small" onClick={onTest}>
          测试
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
