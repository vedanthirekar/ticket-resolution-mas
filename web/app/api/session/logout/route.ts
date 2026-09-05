import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const backendUrl = process.env.LUMA_API_URL ?? "http://127.0.0.1:8000";

export async function POST() {
  const cookieStore = await cookies();
  const token = cookieStore.get("luma_access_token")?.value;
  if (token) {
    await fetch(`${backendUrl}/api/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  }
  cookieStore.delete("luma_access_token");
  return NextResponse.json({ authenticated: false });
}
