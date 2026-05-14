export type FormatOption = {
  format_id: string;
  ext: string;
  label: string;
  kind: string;
  height: number | null;
  abr: number | null;
  filesize_approx: number | null;
  vcodec: string | null;
  acodec: string | null;
  note: string | null;
};

export type VideoInfoResponse = {
  video_id: string;
  title: string;
  thumbnail: string | null;
  duration_seconds: number | null;
  view_count: number | null;
  uploader: string | null;
  video_formats: FormatOption[];
  audio_formats: FormatOption[];
};

export type JobStatus = "pending" | "processing" | "completed" | "failed";

export type DownloadJobRead = {
  id: string;
  url: string;
  title: string | null;
  format_id: string;
  status: JobStatus;
  file_path: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  download_url: string | null;
};

async function readError(res: Response): Promise<string> {
  let message = `${res.status} ${res.statusText}`;
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") {
        return detail;
      }
      if (Array.isArray(detail)) {
        return detail
          .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
          .join(", ");
      }
    }
  } catch {
    /* ignore */
  }
  return message;
}

export async function postVideoInfo(url: string): Promise<VideoInfoResponse> {
  const res = await fetch("/api/info", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    throw new Error(await readError(res));
  }
  return (await res.json()) as VideoInfoResponse;
}

export async function createDownload(payload: {
  url: string;
  format_id: string;
  title: string | null;
}): Promise<DownloadJobRead> {
  const res = await fetch("/api/downloads", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await readError(res));
  }
  return (await res.json()) as DownloadJobRead;
}

export async function getDownload(jobId: string): Promise<DownloadJobRead> {
  const res = await fetch(`/api/downloads/${encodeURIComponent(jobId)}`);
  if (!res.ok) {
    throw new Error(await readError(res));
  }
  return (await res.json()) as DownloadJobRead;
}
