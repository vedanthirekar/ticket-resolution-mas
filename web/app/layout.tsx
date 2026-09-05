import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Luma Resolution Center",
  description: "Evidence-grounded case operations",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
