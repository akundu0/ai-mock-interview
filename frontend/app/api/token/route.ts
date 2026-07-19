import { AccessToken } from 'livekit-server-sdk';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: Request): Promise<NextResponse> {
  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  const livekitUrl = process.env.LIVEKIT_URL;

  if (!apiKey || !apiSecret || !livekitUrl) {
    return NextResponse.json(
      {
        error:
          'Missing LIVEKIT_API_KEY / LIVEKIT_API_SECRET / LIVEKIT_URL. ' +
          'Set them in your Vercel project (server-only) and reload.',
      },
      { status: 500 },
    );
  }

  const { searchParams } = new URL(req.url);
  const room = searchParams.get('room') || 'ai-mock-interview';
  const username =
    searchParams.get('username') ||
    `candidate-${Math.random().toString(36).slice(2, 8)}`;

  const at = new AccessToken(apiKey, apiSecret, {
    identity: username,
    name: username,
    ttl: '1h',
  });
  at.addGrant({
    roomJoin: true,
    room,
    canPublish: true,
    canSubscribe: true,
  });

  const token = await at.toJwt();
  return NextResponse.json({ token, url: livekitUrl, room, identity: username });
}
