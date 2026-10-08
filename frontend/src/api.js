const API_BASE =
  import.meta.env.VITE_API_URL || "";

const CLIENT_ID = (() => {
  try {
    let id = localStorage.getItem("doorstep_client");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("doorstep_client", id);
    }
    return id;
  } catch {
    return "";
  }
})();

async function call(path, opts = {}) {
  const r = await fetch(`${API_BASE}${path}`, {
        headers: {
      "Content-Type": "application/json",
      "X-Client-Id": CLIENT_ID,
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

export const getInsights = () =>
  call("/api/insights");

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