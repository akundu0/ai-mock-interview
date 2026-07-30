import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI Mock Interview — Practice with an AI Interviewer',
  description:
    'Practice your software engineering interviews with a real-time AI interviewer powered by LiveKit voice agents and a Tavus digital-human avatar.',
  keywords: ['mock interview', 'AI interview', 'software engineering', 'practice', 'voice AI', 'LiveKit', 'Tavus'],
  openGraph: {
    title: 'AI Mock Interview',
    description: 'Practice your SWE interviews with a real-time AI interviewer.',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        {children}
      </body>
    </html>
  );
}
