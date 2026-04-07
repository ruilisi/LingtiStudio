"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Layout, Menu, Space, Tag, Typography } from "antd";
import {
  ApiOutlined,
  CompassOutlined,
  HomeOutlined,
  RocketOutlined,
  ThunderboltOutlined
} from "@ant-design/icons";

const { Sider, Content } = Layout;

export function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const selectedKey = pathname.startsWith("/projects/") ? "/studio" : pathname;

  return (
    <Layout className="app-shell">
      <Sider breakpoint="lg" collapsedWidth="0" width={292} className="app-sider">
        <div className="app-brand">
          <Space direction="vertical" size={10}>
            <Tag color="blue" bordered={false} style={{ width: "fit-content", margin: 0 }}>
              LingtiStudio
            </Tag>
            <Typography.Title level={3} style={{ color: "#f5edec", margin: 0 }}>
              LingtiStudio
            </Typography.Title>
            <Typography.Paragraph style={{ color: "#c8a8a8", margin: 0 }}>
              The greyhound-speed AI video workflow for creation, review, recovery, and delivery.
            </Typography.Paragraph>
          </Space>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={[
            {
              key: "/",
              icon: <HomeOutlined />,
              label: <Link href="/">首页</Link>
            },
            {
              key: "/create",
              icon: <ThunderboltOutlined />,
              label: <Link href="/create">快速生成</Link>
            },
            {
              key: "/studio",
              icon: <RocketOutlined />,
              label: <Link href="/studio">专业工作台</Link>
            },
            {
              key: "/analyze",
              icon: <CompassOutlined />,
              label: <Link href="/analyze">对标分析</Link>
            },
            {
              key: "/settings",
              icon: <ApiOutlined />,
              label: <Link href="/settings">Setup</Link>
            }
          ]}
        />
        <div className="app-sider-note">
          <Space direction="vertical" size={8}>
            <span>普通运营优先用“快速生成”。</span>
            <span>需要审核、恢复和日志排错时切到“专业工作台”。</span>
          </Space>
        </div>
      </Sider>
      <Layout className="app-main">
        <Content className="app-content">
          <div className="app-content-inner">{children}</div>
        </Content>
      </Layout>
    </Layout>
  );
}
