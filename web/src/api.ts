export interface ServerInfo {
  product: string;
  api_version: string;
  instance_id: string;
  mode: "community" | "cloud";
  capabilities: string[];
}

export async function loadStatus(signal?: AbortSignal): Promise<ServerInfo> {
  const timeout = AbortSignal.timeout(8000);
  const options = {
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  };
  const [healthResponse, infoResponse] = await Promise.all([
    fetch("/api/v1/health", options),
    fetch("/api/v1/server-info", options),
  ]);
  if (!healthResponse.ok || !infoResponse.ok)
    throw new Error("Servidor indisponível");
  const health = await healthResponse.json();
  const info = await infoResponse.json();
  if (
    health.status !== "ok" ||
    typeof info.instance_id !== "string" ||
    typeof info.api_version !== "string" ||
    !["community", "cloud"].includes(info.mode) ||
    info.product !== "SolDesk" ||
    !Array.isArray(info.capabilities)
  ) {
    throw new Error("Resposta incompatível");
  }
  return info as ServerInfo;
}
