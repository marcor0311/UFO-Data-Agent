export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) { super(message); }
}

const unavailable = "No se pudo conectar con la API del Data Agent. Si trabajas en local, inicia la web y la API con npm run dev y recarga la página.";

function detailOf(body: unknown): { message: string; code?: string } {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return { message: detail };
  if (detail && typeof detail === "object" && "message" in detail) {
    const d = detail as { message: string; code?: string };
    return { message: d.message, code: d.code };
  }
  return { message: "No se pudo completar la solicitud. Vuelve a intentarlo." };
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api/" + path, body === undefined
      ? { cache: "no-store" }
      : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch {
    throw new ApiError(unavailable, 0);
  }
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    if (result === null && response.status >= 500) throw new ApiError(unavailable, response.status);
    const { message, code } = detailOf(result);
    throw new ApiError(message, response.status, code);
  }
  return result as T;
}
