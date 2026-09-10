import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "心迹银龄 家属关怀台",
  description: "在授权范围内了解老人近况并完成关怀行动"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
