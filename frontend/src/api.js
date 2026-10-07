const API_BASE =
  import.meta.env.VITE_API_URL || "";

async function call(path, opts = {}) {
  const r = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
    ...opts,
  });

  if (!r.ok) {
    throw new Error(`HTTP ${r.status}`);
  }

  return r.json();
}

export const health = () =>
  call("/api/health");

export const createMission = (body) =>
  call("/api/missions", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const completeMission = (id, body) =>
  call(`/api/missions/${id}/complete`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getHistory = () =>
  call("/api/history");

export async function transcribe(blob) {
  const r = await fetch(
    `${API_BASE}/api/transcribe`,
    {
      method: "POST",
      body: blob,
    }
  );

  if (!r.ok) {
    throw new Error(`HTTP ${r.status}`);
  }

  return r.json();
}