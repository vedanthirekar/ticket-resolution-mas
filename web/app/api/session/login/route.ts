import { NextResponse } from "next/server";

const backendUrl = process.env.LUMA_API_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  const response = await fetch(`${backendUrl}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await response.json();
  if (!response.ok) return NextResponse.json(payload, { status: response.status });
  const result = NextResponse.json({ authenticated: true });
  result.cookies.set("luma_access_token", payload.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: payload.expires_in_seconds,
    path: "/",
  });
  return result;
}
