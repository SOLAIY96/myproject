
export const API_URL = "http://localhost:8000";

export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});

  if (options.body instanceof FormData) {
    headers.delete("Content-Type");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";

  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail =
      typeof data === "string"
        ? data
        : data?.detail ||
          data?.message ||
          JSON.stringify(data);

    const error = new Error(
      detail || `Request failed: ${response.status}`
    );

    error.status = response.status;
    throw error;
  }

  return data;
}
