"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Modal, Space, Typography } from "antd";

import { ConfigurationForm } from "@/components/configuration-form";
import { getSystemSetup } from "@/lib/api";
import type { SystemSetup } from "@/lib/types";

export function SetupOnboarding() {
  const [setup, setSetup] = useState<SystemSetup | null>(null);
  const [open, setOpen] = useState(false);

  async function refreshSetup() {
    const nextSetup = await getSystemSetup();
    setSetup(nextSetup);
    setOpen(nextSetup.onboarding_required);
  }

  useEffect(() => {
    void refreshSetup().catch(() => undefined);
  }, []);

  useEffect(() => {
    function handleOpen(event: Event) {
      const nextSetup = (event as CustomEvent<SystemSetup | null>).detail;
      if (nextSetup) {
        setSetup(nextSetup);
        setOpen(true);
        return;
      }
      void refreshSetup().catch(() => undefined);
    }

    window.addEventListener("lingti:open-setup", handleOpen as EventListener);
    return () => {
      window.removeEventListener("lingti:open-setup", handleOpen as EventListener);
    };
  }, []);

  return (
    <Modal
      open={open}
      onCancel={() => setOpen(false)}
      footer={null}
      width={920}
      maskClosable={false}
      title="欢迎使用 LingtiStudio"
      destroyOnHidden
    >
      <Space direction="vertical" size={18} style={{ width: "100%" }}>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          在开始生成视频前，先完成最小可用配置。你可以选择默认 provider、模型，并把配置直接写入本地 `configs/config.yaml`。如果本地还没有这个文件，这里保存后会自动创建。
        </Typography.Paragraph>
        {setup?.missing_requirements?.length ? (
          <Alert
            type="warning"
            showIcon
            message="当前项目还缺少必需配置"
            description={
              <Space direction="vertical" size={4}>
                {setup.missing_requirements.map((item) => (
                  <span key={item.key}>{item.message}</span>
                ))}
              </Space>
            }
          />
        ) : null}
        <ConfigurationForm
          setup={setup}
          submitText="保存并开始使用"
          showTitle
          onSaved={async () => {
            await refreshSetup();
            setOpen(false);
          }}
        />
        <Button type="text" onClick={() => setOpen(false)}>
          稍后再配
        </Button>
      </Space>
    </Modal>
  );
}
