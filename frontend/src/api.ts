const BASE = import.meta.env.VITE_API_BASE ?? "";

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} on ${path}`);
  }
  return (await response.json()) as T;
}
