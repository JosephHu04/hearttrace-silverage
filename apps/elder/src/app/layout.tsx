import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "遥遥 · 心迹银龄",
  description: "尊重、耐心并保护隐私的老人陪伴对话"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
