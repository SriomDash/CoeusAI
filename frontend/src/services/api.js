const BASE_URL = "http://127.0.0.1:8000";
const API_V1 = `${BASE_URL}/api/v1`;

export const registerUser = async (userName) => {
  const response = await fetch(`${API_V1}/users/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_name: userName, user_pdf_name: null }),
  });

  if (!response.ok) {
    const msg = await safeErrorMessage(response);
    throw new Error(msg || "Registration failed");
  }
  return await response.json();
};

// If you still have old upload endpoint, adjust accordingly.
// If you moved to ingest/upload, use: `${API_V1}/ingest/upload`
export const uploadPdf = async (file, userId, userName) => {
  const formData = new FormData();
  formData.append("file", file);

  const url = new URL(`${API_V1}/ingest/upload`);
  url.searchParams.set("user_id", userId);
  url.searchParams.set("user_name", userName);

  const response = await fetch(url.toString(), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const msg = await safeErrorMessage(response);
    throw new Error(msg || "Upload failed");
  }
  return await response.json();
};

export const runIngestion = async (jobId, userId, userName) => {
  const url = new URL(`${API_V1}/ingest/${jobId}/run`);
  url.searchParams.set("user_id", userId);
  url.searchParams.set("user_name", userName);

  const response = await fetch(url.toString(), { method: "POST" });

  if (!response.ok) {
    const msg = await safeErrorMessage(response);
    throw new Error(msg || "Ingestion failed");
  }
  return await response.json();
};

async function safeErrorMessage(response) {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
    return data?.message || null;
  } catch {
    try {
      return await response.text();
    } catch {
      return null;
    }
  }
}