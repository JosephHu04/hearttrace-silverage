import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "心迹银龄 管理工作台",
  description: "风险复核、处置与审计工作台"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
