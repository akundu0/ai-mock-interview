import type { Metadata } from 'next';
import '@livekit/components-styles';

export const metadata: Metadata = {
  title: 'AI Mock Interview',
  description:
    'Join a real-time mock interview with a Tavus virtual avatar powered by LiveKit Agents.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: 'system-ui, sans-serif' }}>
        {children}
      </body>
    </html>
  );
}
