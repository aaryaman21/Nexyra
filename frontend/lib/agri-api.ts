export async function agriRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    const timeout = AbortSignal.timeout(30000);
    response = await fetch(`/api/agri/${path}`, { ...options, signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new Error("Cannot reach the backend. Start the Python API on port 8000, then click Retry connection.");
  }
  if (!response.ok) {
    let detail = "";
    try { const body = await response.json(); detail = typeof body.detail === "string" ? body.detail : ""; } catch { /* Proxy can return HTML when backend is down. */ }
    throw new Error(detail || (response.status >= 500
      ? "The backend is unavailable. Start the Python API on port 8000, then click Retry connection."
      : "The request could not be completed. Check your inputs and try again."));
  }
  return response.json();
}

export function downloadText(name: string, text: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
