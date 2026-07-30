'use client';

import { useState, useEffect, useRef, FormEvent } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoTrack,
  useTracks,
  useRoomContext,
} from '@livekit/components-react';
import { Track, RoomEvent, TranscriptionSegment } from 'livekit-client';
import {
  Mic,
  Video,
  Brain,
  ArrowRight,
  Sparkles,
  MessageSquare,
  Timer,
  LogOut,
  Loader2,
  ChevronRight,
  ExternalLink,
  Bot,
  User,
} from 'lucide-react';
import { cn } from './utils/cn';

const AVATAR_PARTICIPANT_NAME =
  process.env.NEXT_PUBLIC_TAVUS_AVATAR_NAME ?? 'Tavus-avatar-agent';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type AppView = 'landing' | 'connect' | 'interview';

interface TranscriptEntry {
  id: string;
  speaker: 'agent' | 'user';
  text: string;
  timestamp: Date;
}

// ---------------------------------------------------------------------------
// Root page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const [view, setView] = useState<AppView>('landing');
  const [username, setUsername] = useState('');
  const [token, setToken] = useState<string | null>(null);
  const [serverUrl, setServerUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);

  const handleStartClick = () => setView('connect');

  async function handleConnect(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setConnecting(true);
    try {
      const res = await fetch(
        `/api/token?username=${encodeURIComponent(username || 'candidate')}`,
      );
      if (!res.ok) throw new Error(`Token endpoint returned ${res.status}`);
      const data = (await res.json()) as { token: string; url: string };
      setToken(data.token);
      setServerUrl(data.url);
      setView('interview');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConnecting(false);
    }
  }

  function handleLeave() {
    setToken(null);
    setServerUrl(null);
    setView('landing');
  }

  if (view === 'interview' && token && serverUrl) {
    return (
      <LiveKitRoom
        token={token}
        serverUrl={serverUrl}
        connect
        video
        audio
        onDisconnected={handleLeave}
      >
        <InterviewRoom onLeave={handleLeave} username={username} />
      </LiveKitRoom>
    );
  }

  if (view === 'connect') {
    return (
      <ConnectView
        username={username}
        setUsername={setUsername}
        error={error}
        connecting={connecting}
        onSubmit={handleConnect}
        onBack={() => setView('landing')}
      />
    );
  }

  return <LandingPage onStart={handleStartClick} />;
}

// ---------------------------------------------------------------------------
// Landing page
// ---------------------------------------------------------------------------

function LandingPage({ onStart }: { onStart: () => void }) {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 md:px-12 border-b border-border/50">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-primary/20 flex items-center justify-center">
            <Bot className="h-4 w-4 text-primary" />
          </div>
          <span className="font-semibold text-sm tracking-tight">AI Mock Interview</span>
        </div>
        <a
          href="https://github.com/akundu0/ai-mock-interview"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Source</span>
        </a>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex items-center justify-center px-6 py-16 md:py-24">
        <div className="max-w-3xl mx-auto text-center space-y-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border text-xs text-muted-foreground">
            <Sparkles className="h-3 w-3 text-primary" />
            Powered by LiveKit Agents + Tavus Avatar
          </div>

          <h1 className="text-4xl md:text-6xl font-bold tracking-tight leading-tight">
            Practice interviews with a{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">
              real-time AI interviewer
            </span>
          </h1>

          <p className="text-lg text-muted-foreground max-w-xl mx-auto leading-relaxed">
            Get instant practice for software engineering interviews. A digital-human
            interviewer guides you through self-introduction and past-experience
            stages with real-time voice conversation.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={onStart}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-primary text-primary-foreground font-semibold text-sm hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20"
            >
              Start Interview
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </main>

      {/* Features */}
      <section className="border-t border-border/50 bg-card/30 px-6 py-16 md:py-20">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-center text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-10">
            How it works
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <FeatureCard
              icon={<Video className="h-5 w-5" />}
              title="Digital-Human Avatar"
              description="A Tavus Phoenix-3 PRO avatar renders in real-time with lip-synced speech — it feels like a real conversation."
            />
            <FeatureCard
              icon={<Brain className="h-5 w-5" />}
              title="Multi-Stage Interview"
              description="The AI runs a structured flow: self-introduction, then deep-dive into your past projects with targeted follow-ups."
            />
            <FeatureCard
              icon={<Timer className="h-5 w-5" />}
              title="Smart Pacing"
              description="A time-based watchdog ensures the interview keeps moving — gentle nudges if you pause, automatic stage transitions."
            />
          </div>
        </div>
      </section>

      {/* Tech stack */}
      <section className="border-t border-border/50 px-6 py-12">
        <div className="max-w-5xl mx-auto text-center">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-6">
            Built with
          </h2>
          <div className="flex flex-wrap justify-center gap-3">
            {[
              'LiveKit Agents',
              'Tavus Phoenix-3 PRO',
              'Next.js 14',
              'Groq (Llama 3.1)',
              'Deepgram STT',
              'Cartesia TTS',
              'Python asyncio',
              'Tailwind CSS',
            ].map((tech) => (
              <span
                key={tech}
                className="px-3 py-1.5 rounded-lg bg-muted/50 text-xs font-medium text-muted-foreground border border-border/50"
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/50 px-6 py-6 text-center text-xs text-muted-foreground">
        AI Mock Interview &mdash; Open-source project for interview practice
      </footer>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="group p-6 rounded-xl border border-border/50 bg-card/50 hover:bg-card hover:border-border transition-colors">
      <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary mb-4 group-hover:bg-primary/20 transition-colors">
        {icon}
      </div>
      <h3 className="font-semibold text-sm mb-2">{title}</h3>
      <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Connect view
// ---------------------------------------------------------------------------

function ConnectView({
  username,
  setUsername,
  error,
  connecting,
  onSubmit,
  onBack,
}: {
  username: string;
  setUsername: (v: string) => void;
  error: string | null;
  connecting: boolean;
  onSubmit: (e: FormEvent) => void;
  onBack: () => void;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md space-y-6">
        <button
          onClick={onBack}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
        >
          &larr; Back
        </button>

        <div className="rounded-2xl border border-border bg-card p-8 shadow-2xl shadow-black/40">
          <div className="flex items-center gap-3 mb-6">
            <div className="h-10 w-10 rounded-xl bg-primary/20 flex items-center justify-center">
              <Mic className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Join Interview</h1>
              <p className="text-xs text-muted-foreground">
                Enter your name to start the session
              </p>
            </div>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="username" className="text-sm font-medium">
                Your name
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. Alex Chen"
                className="w-full px-4 py-2.5 rounded-xl bg-background border border-border text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={connecting}
              className={cn(
                'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-semibold text-sm transition-colors',
                connecting
                  ? 'bg-muted text-muted-foreground cursor-not-allowed'
                  : 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20',
              )}
            >
              {connecting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  Start Interview
                  <ChevronRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-border">
            <div className="flex items-start gap-3 text-xs text-muted-foreground">
              <MessageSquare className="h-4 w-4 mt-0.5 shrink-0" />
              <p>
                Your microphone will be used for the interview. Camera is not required.
                The AI interviewer will guide you through two stages.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Interview room
// ---------------------------------------------------------------------------

const STAGES = [
  { label: 'Self-Introduction', description: 'Name, role & career snapshot' },
  { label: 'Past Experience', description: 'Deep-dive into a recent project' },
];

function InterviewRoom({
  onLeave,
  username,
}: {
  onLeave: () => void;
  username: string;
}) {
  const tracks = useTracks([Track.Source.Camera]);
  const room = useRoomContext();
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [currentStage, setCurrentStage] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Elapsed timer
  useEffect(() => {
    const interval = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  // Listen for transcription events to build live transcript
  useEffect(() => {
    if (!room) return;

    const handleTranscription = (
      segments: TranscriptionSegment[],
      participant: { identity: string } | undefined,
    ) => {
      const isAgent =
        participant?.identity === AVATAR_PARTICIPANT_NAME ||
        participant?.identity === 'agent';

      for (const seg of segments) {
        if (!seg.final) continue;
        const text = seg.text.trim();
        if (!text) continue;

        setTranscript((prev) => {
          const existing = prev.find((e) => e.id === seg.id);
          if (existing) {
            return prev.map((e) =>
              e.id === seg.id ? { ...e, text } : e,
            );
          }
          return [
            ...prev,
            {
              id: seg.id,
              speaker: isAgent ? 'agent' : 'user',
              text,
              timestamp: new Date(),
            },
          ];
        });

        // Heuristic: detect stage transition from agent speech
        if (
          isAgent &&
          currentStage === 0 &&
          (text.toLowerCase().includes('past experience') ||
            text.toLowerCase().includes('recent project') ||
            text.toLowerCase().includes('walk me through') ||
            text.toLowerCase().includes('stage 2') ||
            text.toLowerCase().includes("let's transition") ||
            text.toLowerCase().includes('dive deeper'))
        ) {
          setCurrentStage(1);
        }
      }
    };

    room.on(RoomEvent.TranscriptionReceived, handleTranscription);
    return () => {
      room.off(RoomEvent.TranscriptionReceived, handleTranscription);
    };
  }, [room, currentStage]);

  // Avatar track
  const avatarTrack = tracks.find(
    (t) =>
      t.participant.identity === AVATAR_PARTICIPANT_NAME ||
      t.participant.name === AVATAR_PARTICIPANT_NAME,
  );

  const formatTime = (s: number) =>
    `${Math.floor(s / 60)
      .toString()
      .padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-border/50 bg-card/30 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-red-500 relative">
              <div className="absolute inset-0 rounded-full bg-red-500 animate-pulse-ring" />
            </div>
            <span className="text-xs font-medium text-muted-foreground">LIVE</span>
          </div>
          <div className="h-4 w-px bg-border" />
          <span className="text-xs font-mono text-muted-foreground">
            {formatTime(elapsed)}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {username || 'Candidate'}
          </span>
          <button
            onClick={onLeave}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-destructive hover:bg-destructive/10 border border-destructive/20 transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            Leave
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col lg:flex-row">
        {/* Left: Avatar + Stage Indicator */}
        <div className="flex-1 flex flex-col p-4 md:p-6 gap-4">
          {/* Stage indicator */}
          <div className="flex items-center gap-2">
            {STAGES.map((stage, i) => (
              <div key={i} className="flex items-center gap-2">
                {i > 0 && (
                  <div
                    className={cn(
                      'h-px w-6 transition-colors',
                      i <= currentStage ? 'bg-primary' : 'bg-border',
                    )}
                  />
                )}
                <div
                  className={cn(
                    'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                    i === currentStage
                      ? 'bg-primary/15 text-primary border border-primary/30'
                      : i < currentStage
                        ? 'bg-muted/50 text-muted-foreground'
                        : 'text-muted-foreground/50',
                  )}
                >
                  <span
                    className={cn(
                      'h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold',
                      i === currentStage
                        ? 'bg-primary text-primary-foreground'
                        : i < currentStage
                          ? 'bg-muted-foreground/30 text-muted-foreground'
                          : 'bg-muted text-muted-foreground/50',
                    )}
                  >
                    {i + 1}
                  </span>
                  <span className="hidden sm:inline">{stage.label}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Avatar video */}
          <div className="flex-1 relative rounded-2xl overflow-hidden border border-border/50 bg-black min-h-[300px]">
            {avatarTrack ? (
              <VideoTrack
                trackRef={avatarTrack}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  position: 'absolute',
                  inset: 0,
                }}
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                <div className="h-16 w-16 rounded-2xl bg-muted/50 flex items-center justify-center">
                  <Loader2 className="h-8 w-8 text-muted-foreground animate-spin" />
                </div>
                <p className="text-sm text-muted-foreground">
                  Connecting to interviewer...
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right: Transcript */}
        <div className="w-full lg:w-96 border-t lg:border-t-0 lg:border-l border-border/50 flex flex-col bg-card/20">
          <div className="px-4 py-3 border-b border-border/50">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold">Live Transcript</h2>
              <span className="ml-auto text-xs text-muted-foreground">
                {transcript.length} messages
              </span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto transcript-scroll p-4 space-y-3 max-h-[40vh] lg:max-h-none">
            {transcript.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <MessageSquare className="h-8 w-8 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">
                  Transcript will appear here as the interview progresses.
                </p>
              </div>
            ) : (
              transcript.map((entry) => (
                <div
                  key={entry.id}
                  className={cn(
                    'flex gap-2.5',
                    entry.speaker === 'user' ? 'flex-row-reverse' : 'flex-row',
                  )}
                >
                  <div
                    className={cn(
                      'h-6 w-6 rounded-full flex items-center justify-center shrink-0 mt-0.5',
                      entry.speaker === 'agent'
                        ? 'bg-primary/20 text-primary'
                        : 'bg-muted text-muted-foreground',
                    )}
                  >
                    {entry.speaker === 'agent' ? (
                      <Bot className="h-3.5 w-3.5" />
                    ) : (
                      <User className="h-3.5 w-3.5" />
                    )}
                  </div>
                  <div
                    className={cn(
                      'max-w-[80%] px-3 py-2 rounded-xl text-sm leading-relaxed',
                      entry.speaker === 'agent'
                        ? 'bg-muted/50 text-foreground'
                        : 'bg-primary/15 text-foreground',
                    )}
                  >
                    {entry.text}
                  </div>
                </div>
              ))
            )}
            <div ref={transcriptEndRef} />
          </div>
        </div>
      </div>

      <RoomAudioRenderer />
    </div>
  );
}
