import { ApiError } from "./workspace-api";
import { mediaStrings as s } from "./media-strings";

export async function uploadFile<T>(path: string, file: File): Promise<T> {
  const types: Record<string, string> = {
    wav: "audio/wav",
    mp3: "audio/mpeg",
    m4a: "audio/mp4",
    mp4: "audio/mp4",
    aac: "audio/aac",
    ogg: "audio/ogg",
    opus: "audio/ogg",
    webm: "audio/webm",
    txt: "text/plain",
    pdf: "application/pdf",
    png: "image/png",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
  };
  const csrf = await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
  const token = await csrf.json();
  if (!csrf.ok) throw new ApiError(csrf.status, token.title);
  const response = await fetch("/api/v1" + path, {
    method: "POST",
    credentials: "same-origin",
    body: file,
    headers: {
      "X-CSRF-Token": token.csrf_token,
      "X-Filename": encodeURIComponent(file.name),
      "Content-Type":
        file.type ||
        types[file.name.split(".").pop()?.toLowerCase() || ""] ||
        "application/octet-stream",
    },
    signal: AbortSignal.timeout(60000),
  });
  const body = await response.json();
  if (!response.ok)
    throw new ApiError(response.status, body.title || s.sendError);
  return body as T;
}
