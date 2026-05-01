import "./globals.css";

export const metadata = {
  title: "Aircraft Carrier Tower",
  description: "Real-time flight ground-station dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
