"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Row, Space, Tag, Typography } from "antd";
import {
  ApiOutlined,
  CompassOutlined,
  DeploymentUnitOutlined,
  PlaySquareOutlined
} from "@ant-design/icons";

import { ProjectsPanel } from "@/components/projects-panel";
import { getApiBase, getConnectorStatus, getSystemHealth, getSystemSetup } from "@/lib/api";
import type { ConnectorStatus, SystemHealth, SystemSetup } from "@/lib/types";

const entryCards = [
  {
    href: "/create",
    icon: <PlaySquareOutlined />,
    title: "快速生成",
    description: "给运营同学。只填主题、时长和素材，按推荐值启动工作流。"
  },
  {
    href: "/studio",
    icon: <DeploymentUnitOutlined />,
    title: "专业工作台",
    description: "给你和内部团队。集中看日志、审核、恢复、下载和排错。"
  },
  {
    href: "/analyze",
    icon: <CompassOutlined />,
    title: "对标分析",
    description: "上传一个参考视频，自动拆解人物、分镜和风格，再生成新项目。"
  }
];

export default function HomePage() {
  const [refreshToken] = useState(0);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [connectors, setConnectors] = useState<ConnectorStatus | null>(null);
  const [setup, setSetup] = useState<SystemSetup | null>(null);
  const [apiBase, setApiBase] = useState<string>("");

  useEffect(() => {
    setApiBase(getApiBase());
    void Promise.all([getSystemHealth(), getConnectorStatus(), getSystemSetup()])
      .then(([health, nextConnectors, nextSetup]) => {
        setSystemHealth(health);
        setConnectors(nextConnectors);
        setSetup(nextSetup);
      })
      .catch(() => undefined);
  }, []);

  return (
    <Space direction="vertical" size={28} style={{ width: "100%" }}>
      {setup?.onboarding_required ? (
        <Alert
          type="warning"
          showIcon
          message="首次使用前请先完成配置"
          description={
            <Space direction="vertical" size={4}>
              <span>系统已经弹出配置窗口。你也可以进入 Setup 页面继续编辑。</span>
              {!setup.config_exists ? <span>本地 config.yaml 还不存在，第一次保存配置时会自动创建。</span> : null}
              {setup.missing_requirements.map((item) => (
                <span key={item.key}>{item.message}</span>
              ))}
            </Space>
          }
        />
      ) : null}
      <section className="hero-panel">
        <div className="hero-copy">
          <Tag color="blue" bordered={false}>
            LingtiStudio
          </Tag>
          <Typography.Title level={1}>The greyhound-speed AI video workflow</Typography.Title>
          <Typography.Paragraph>
            Lingti means greyhound in Chinese, the fastest dog. LingtiStudio helps you turn an idea into a full video workflow with script generation, review, assets, video clips, recovery, and delivery.
          </Typography.Paragraph>
          <Space wrap>
            <Link href="/create">
              <Button type="primary" size="large">
                进入快速生成
              </Button>
            </Link>
            <Link href="/studio">
              <Button size="large">进入专业工作台</Button>
            </Link>
            <Link href="/settings">
              <Button size="large" icon={<ApiOutlined />}>
                Open Setup
              </Button>
            </Link>
          </Space>
          <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
            当前后端地址：{apiBase || "检测中..."}
          </Typography.Paragraph>
        </div>

        <div className="hero-status">
          <Card className="lingti-card lingti-card-soft">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Typography.Title level={4} style={{ margin: 0 }}>
                系统概览
              </Typography.Title>
              <div className="system-stat-row">
                <span>系统状态</span>
                <strong>{systemHealth?.status || "加载中"}</strong>
              </div>
              <div className="system-stat-row">
                <span>默认视频引擎</span>
                <strong>{connectors?.video.default_provider || systemHealth?.defaults.video_provider || "-"}</strong>
              </div>
              <div className="system-stat-row">
                <span>默认 LLM</span>
                <strong>{connectors?.llm.default_provider || systemHealth?.defaults.llm_provider || "-"}</strong>
              </div>
              <div className="system-stat-row">
                <span>图片服务</span>
                <strong>{connectors?.image.provider || systemHealth?.defaults.image_provider || "-"}</strong>
              </div>
              <div className="system-stat-row">
                <span>TTS 模式</span>
                <strong>{connectors?.tts.voice_catalog_supported ? "MiniMax 音色目录" : "手动 voice_id"}</strong>
              </div>
            </Space>
          </Card>
        </div>
      </section>

      <Row gutter={[24, 24]}>
        {entryCards.map((card) => (
          <Col xs={24} md={8} key={card.href}>
            <Link href={card.href}>
              <Card className="lingti-card lingti-entry-card">
                <Space direction="vertical" size={16}>
                  <div className="entry-icon">{card.icon}</div>
                  <div>
                    <Typography.Title level={3}>{card.title}</Typography.Title>
                    <Typography.Paragraph type="secondary">{card.description}</Typography.Paragraph>
                  </div>
                </Space>
              </Card>
            </Link>
          </Col>
        ))}
      </Row>

      <ProjectsPanel refreshToken={refreshToken} compact />
    </Space>
  );
}
