'use client';

import { useState, FormEvent } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoTrack,
  useTracks,
} from '@livekit/components-react';
import { Track } from 'livekit-client';

const DEFAULT_LIVEKIT_URL =
  process.env.NEXT_PUBLIC_LIVEKIT_URL ?? 'wss://localhost:7880';
const AVATAR_PARTICIPANT_NAME =
  process.env.NEXT_PUBLIC_TAVUS_AVATAR_NAME ?? 'Tavus-avatar-agent';

export default function HomePage() {
  const [roomName, setRoomName] = useState('ai-mock-interview');
  const [username, setUsername] = useState(
    `candidate-${Math.random().toString(36).slice(2, 8)}`,
  );
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);

  async function handleConnect(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setConnecting(true);
    try {
      const res = await fetch(
        `/api/token?room=${encodeURIComponent(roomName)}&username=${encodeURIComponent(username)}`,
      );
      if (!res.ok) {
        throw new Error(`Token endpoint returned ${res.status}`);
      }
      const data = (await res.json()) as { token: string; url: string };
      setToken(data.token);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConnecting(false);
    }
  }

  if (token) {
    return (
      <main style={{ minHeight: '100vh', background: '#0b0d12', color: '#f0f2f8' }}>
        <LiveKitRoom
          token={token}
          serverUrl={DEFAULT_LIVEKIT_URL}
          connect
          video
          audio
          onDisconnected={() => setToken(null)}
        >
          <RoomStage onLeave={() => setToken(null)} />
        </LiveKitRoom>
      </main>
    );
  }

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        background: '#0b0d12',
        color: '#f0f2f8',
        padding: 24,
      }}
    >
      <form
        onSubmit={handleConnect}
        style={{
          width: 'min(420px, 100%)',
          padding: 24,
          borderRadius: 12,
          background: '#15181f',
          boxShadow: '0 12px 40px rgba(0,0,0,0.35)',
        }}
      >
        <h1 style={{ fontSize: 22, margin: '0 0 4px' }}>AI Mock Interview</h1>
        <p style={{ opacity: 0.7, fontSize: 13, margin: '0 0 20px' }}>
          You'll speak with a digital-human interviewer; your camera stays off.
        </p>
        <label style={fieldStyle}>
          <span>Room name</span>
          <input
            value={roomName}
            onChange={(e) => setRoomName(e.target.value)}
            required
            style={inputStyle}
          />
        </label>
        <label style={fieldStyle}>
          <span>Candidate name</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            style={inputStyle}
          />
        </label>
        {error && (
          <p style={{ color: '#ff8a80', fontSize: 13, margin: '4px 0 12px' }}>
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={connecting}
          style={{
            marginTop: 16,
            padding: '10px 18px',
            border: 'none',
            borderRadius: 8,
            background: '#4864ff',
            color: 'white',
            fontWeight: 600,
            cursor: connecting ? 'wait' : 'pointer',
            opacity: connecting ? 0.7 : 1,
          }}
        >
          {connecting ? 'Connecting…' : 'Start interview'}
        </button>
      </form>
    </main>
  );
}function RoomStage({ onLeave }: { onLeave: () => void }) {
  const tracks = useTracks([Track.Source.Camera]);
  // Exact-name match (no loose substring check). The agent sets the
  // avatar's participant identity to this string via
  // `tavus.AvatarSession(avatar_participant_name=...)` and TAVUS_AVATAR_NAME.
  const avatarTrack = tracks.find(
    (t) => t.participant.identity === AVATAR_PARTICIPANT_NAME ||
           t.participant.name === AVATAR_PARTICIPANT_NAME,
  );

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr',
        gap: 12,
        padding: 24,
        minHeight: '100vh',
      }}
    >
      <div
        style={{
          position: 'relative',
          aspectRatio: '16/9',
          background: '#0b0d12',
          borderRadius: 12,
          overflow: 'hidden',
        }}
      >
        {avatarTrack ? (
          <VideoTrack
            trackRef={avatarTrack}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'grid',
              placeItems: 'center',
              opacity: 0.6,
            }}
          >
            Waiting for interviewer avatar…
          </div>
        )}
      </div>
      <RoomAudioRenderer />
      <button
        onClick={onLeave}
        style={{
          justifySelf: 'end',
          padding: '8px 14px',
          borderRadius: 8,
          border: '1px solid #3a3f4b',
          background: 'transparent',
          color: '#f0f2f8',
          cursor: 'pointer',
        }}
      >
        Leave
      </button>
    </div>
  );
}

const fieldStyle: React.CSSProperties = {
  display: 'block',
  marginBottom: 12,
  fontSize: 13,
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  marginTop: 4,
  padding: '8px 10px',
  borderRadius: 6,
  border: '1px solid #2a2f3a',
  background: '#0e1118',
  color: '#f0f2f8',
};
