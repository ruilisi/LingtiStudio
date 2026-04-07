import type { Metadata } from "next";

import { Providers } from "@/components/providers";
import { SetupOnboarding } from "@/components/setup-onboarding";
import { WorkspaceLayout } from "@/components/workspace-layout";

import "./globals.css";

export const metadata: Metadata = {
  title: "LingtiStudio",
  description: "Open-source AI video generation workflow"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <Providers>
          <WorkspaceLayout>
            <SetupOnboarding />
            {children}
          </WorkspaceLayout>
        </Providers>
      </body>
    </html>
  );
}
