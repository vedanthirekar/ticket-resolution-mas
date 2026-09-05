import { cookies } from "next/headers";

const backendUrl = process.env.LUMA_API_URL ?? "http://127.0.0.1:8000";

export async function serverApi<T>(path: string): Promise<T> {
  const token = (await cookies()).get("luma_access_token")?.value;
  const response = await fetch(`${backendUrl}/api/${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Luma API returned ${response.status}`);
  return response.json() as Promise<T>;
}
