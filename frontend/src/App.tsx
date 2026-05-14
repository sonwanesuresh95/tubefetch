import { useCallback, useEffect, useRef, useState } from "react";
import { createDownload, getDownload, postVideoInfo, type FormatOption, type VideoInfoResponse } from "./api";

function formatDuration(seconds: number | null): string {
  if (seconds == null || seconds < 0) {
    return "—";
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatViewCount(count: number | null | undefined): string {
  if (count == null || count < 0 || !Number.isFinite(count)) {
    return "—";
  }
  if (count >= 1_000_000) {
    return new Intl.NumberFormat(undefined, {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(count);
  }
  return new Intl.NumberFormat(undefined).format(count);
}

function formatRowKey(f: FormatOption): string {
  return `${f.format_id}|${f.ext}|${f.label}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Starts the browser file save using the completed job file URL (same origin as the API). */
function triggerBrowserDownload(href: string): void {
  const a = document.createElement("a");
  a.href = href;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" />
    </svg>
  );
}

type TabKey = "video" | "audio";

export default function App() {
  const [url, setUrl] = useState("");
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<VideoInfoResponse | null>(null);
  const [tab, setTab] = useState<TabKey>("video");
  const [downloadingByKey, setDownloadingByKey] = useState<Record<string, boolean>>({});
  const downloadGuardRef = useRef(new Set<string>());

  const formats = info ? (tab === "video" ? info.video_formats : info.audio_formats) : [];

  useEffect(() => {
    return () => {
      downloadGuardRef.current.clear();
    };
  }, []);

  const analyze = useCallback(async () => {
    setError(null);
    setInfo(null);
    setDownloadingByKey({});
    downloadGuardRef.current.clear();
    const trimmed = url.trim();
    if (!trimmed) {
      setError("Paste a YouTube link to continue.");
      return;
    }
    setAnalyzeLoading(true);
    try {
      const data = await postVideoInfo(trimmed);
      setInfo(data);
      setTab(data.video_formats.length ? "video" : "audio");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setAnalyzeLoading(false);
    }
  }, [url]);

  const downloadFormat = useCallback(
    async (f: FormatOption) => {
      if (!info) {
        return;
      }
      const key = formatRowKey(f);
      if (downloadGuardRef.current.has(key)) {
        return;
      }
      downloadGuardRef.current.add(key);
      setDownloadingByKey((prev) => ({ ...prev, [key]: true }));
      setError(null);
      try {
        const job = await createDownload({
          url: url.trim(),
          format_id: f.format_id,
          title: info.title,
        });
        let status = job.status;
        let latest = job;
        while (status !== "completed" && status !== "failed") {
          await sleep(1200);
          latest = await getDownload(job.id);
          status = latest.status;
        }
        if (status === "failed") {
          throw new Error(latest.error_message || "Download failed.");
        }
        if (!latest.download_url) {
          throw new Error("File URL missing.");
        }
        triggerBrowserDownload(latest.download_url);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Download failed.");
      } finally {
        downloadGuardRef.current.delete(key);
        setDownloadingByKey((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      }
    },
    [info, url],
  );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void analyze();
  };

  return (
    <div className="min-h-full bg-gradient-to-b from-slate-50 to-white text-slate-900">
      <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-900 text-sm font-semibold text-white shadow-soft">
              TF
            </div>
            <div>
              <p className="text-sm font-semibold tracking-tight">TubeFetch</p>
              <p className="text-xs text-slate-500">YouTube video & audio</p>
            </div>
          </div>
          <span className="hidden rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 sm:inline">
            Lite · no sign-in
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-balance text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Download YouTube media in the quality you need
          </h1>
          <p className="mt-3 text-pretty text-sm leading-relaxed text-slate-600 sm:text-base">
            Paste a link, review available streams, and save video or audio. Built for clarity and speed—no accounts,
            no clutter.
          </p>
        </div>

        <div className="mx-auto mt-10 max-w-3xl">
          <form
            onSubmit={onSubmit}
            className="rounded-2xl border border-slate-200 bg-white p-4 shadow-soft sm:p-6"
          >
            <label htmlFor="url" className="block text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              YouTube URL
            </label>
            <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-stretch">
              <input
                id="url"
                name="url"
                type="url"
                inputMode="url"
                autoComplete="off"
                spellCheck={false}
                placeholder="https://www.youtube.com/watch?v=…"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="w-full flex-1 rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3 text-sm text-slate-900 outline-none ring-slate-900/10 placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:ring-4"
              />
              <button
                type="submit"
                disabled={analyzeLoading}
                className="inline-flex shrink-0 items-center justify-center rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {analyzeLoading ? "Analyzing…" : "Analyze"}
              </button>
            </div>
            {error ? (
              <p className="mt-3 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-left text-sm text-rose-800">
                {error}
              </p>
            ) : null}
          </form>
        </div>

        {info ? (
          <div className="mx-auto mt-8 max-w-5xl space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white shadow-soft">
              <div className="grid gap-0 lg:grid-cols-[1fr_minmax(260px,340px)] lg:items-start">
                <div className="min-w-0 self-start p-4 sm:p-5 lg:sticky lg:top-6 lg:z-10 lg:p-6 lg:pr-4">
                  {info.video_id ? (
                    <div className="relative aspect-video w-full overflow-hidden rounded-xl border border-slate-200/90 bg-slate-950 shadow-sm ring-1 ring-slate-900/5">
                      <iframe
                        className="absolute inset-0 h-full w-full"
                        src={`https://www.youtube.com/embed/${encodeURIComponent(info.video_id)}?rel=0&modestbranding=1`}
                        title={info.title}
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                        allowFullScreen
                      />
                    </div>
                  ) : (
                    <div className="flex aspect-video w-full items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
                      Preview unavailable
                    </div>
                  )}
                </div>

                <aside className="flex min-w-0 flex-col border-t border-slate-100 bg-gradient-to-b from-slate-50/90 to-slate-50 p-4 sm:p-5 lg:border-l lg:border-t-0 lg:px-5 lg:py-5">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">Video details</p>
                    <h2 className="mt-1.5 text-balance text-base font-semibold leading-snug tracking-tight text-slate-900 sm:text-lg">
                      {info.title}
                    </h2>
                  </div>

                  <div className="mt-4 flex flex-col gap-3">
                    <div className="flex gap-2.5 rounded-lg border border-slate-200/90 bg-white/80 p-3 shadow-sm ring-1 ring-slate-900/[0.03]">
                      <div
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-slate-100 to-slate-200/90 text-xs font-bold text-slate-600"
                        aria-hidden
                      >
                        {(info.uploader ?? "?").trim().charAt(0).toUpperCase() || "?"}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Channel</p>
                        <p className="mt-0.5 truncate text-sm font-semibold leading-snug text-slate-900">
                          {info.uploader ?? "—"}
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded-lg border border-slate-200/90 bg-white/80 px-3 py-2.5 shadow-sm ring-1 ring-slate-900/[0.03]">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Duration</p>
                        <p className="mt-1 tabular-nums text-base font-semibold tracking-tight text-slate-900">
                          {formatDuration(info.duration_seconds)}
                        </p>
                      </div>
                      <div className="rounded-lg border border-slate-200/90 bg-white/80 px-3 py-2.5 shadow-sm ring-1 ring-slate-900/[0.03]">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Views</p>
                        <p className="mt-1 tabular-nums text-base font-semibold tracking-tight text-slate-900">
                          {formatViewCount(info.view_count)}
                        </p>
                      </div>
                    </div>

                    {info.video_id ? (
                      <a
                        href={`https://www.youtube.com/watch?v=${encodeURIComponent(info.video_id)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-slate-900/[0.03] transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900"
                      >
                        <span>Open on YouTube</span>
                        <svg
                          className="h-4 w-4 shrink-0 text-slate-500 transition group-hover:text-blue-600"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden
                        >
                          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                          <path d="M15 3h6v6" />
                          <path d="M10 14L21 3" />
                        </svg>
                      </a>
                    ) : null}
                  </div>

                  <p className="mt-4 border-t border-slate-200/70 pt-3 text-[11px] leading-relaxed text-slate-500">
                    Pick a format below when you are ready.
                  </p>
                </aside>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white shadow-soft">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3 sm:px-6">
                <div className="inline-flex rounded-full border border-slate-200 bg-slate-50 p-1 text-xs font-medium">
                  <button
                    type="button"
                    onClick={() => setTab("video")}
                    className={`rounded-full px-4 py-1.5 transition ${
                      tab === "video" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    Video ({info.video_formats.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setTab("audio")}
                    className={`rounded-full px-4 py-1.5 transition ${
                      tab === "audio" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    Audio ({info.audio_formats.length})
                  </button>
                </div>
                <p className="text-xs text-slate-500">Use the download icon to save that format to your device.</p>
              </div>

              <div className="max-h-[420px] overflow-auto">
                {formats.length === 0 ? (
                  <p className="px-6 py-10 text-center text-sm text-slate-600">No formats in this category.</p>
                ) : (
                  <table className="min-w-full border-collapse text-left text-sm">
                    <thead className="sticky top-0 z-10 bg-slate-50/95 text-xs font-semibold uppercase tracking-wide text-slate-500 backdrop-blur">
                      <tr>
                        <th className="px-4 py-3 sm:px-6">Quality</th>
                        <th className="hidden px-4 py-3 sm:table-cell sm:px-6">Container</th>
                        <th className="hidden px-4 py-3 md:table-cell md:px-6">Codecs</th>
                        <th className="w-14 px-2 py-3 text-right sm:w-16 sm:px-3">
                          <span className="sr-only">Download</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {formats.map((f) => {
                        const rowKey = formatRowKey(f);
                        const isBusy = Boolean(downloadingByKey[rowKey]);
                        return (
                          <tr key={rowKey} className="transition hover:bg-slate-50/70">
                            <td className="px-4 py-3 sm:px-6">
                              <div className="font-medium text-slate-900">{f.label}</div>
                              {f.note ? <p className="mt-1 text-xs text-slate-500">{f.note}</p> : null}
                            </td>
                            <td className="hidden px-4 py-3 text-slate-600 sm:table-cell sm:px-6">{f.ext.toUpperCase()}</td>
                            <td className="hidden px-4 py-3 text-xs text-slate-600 md:table-cell md:px-6">
                              {[f.vcodec, f.acodec].filter(Boolean).join(" · ") || "—"}
                            </td>
                            <td className="px-2 py-2 text-right sm:px-3">
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => void downloadFormat(f)}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-xl text-slate-600 transition hover:bg-slate-100 hover:text-blue-600 focus-visible:outline focus-visible:ring-2 focus-visible:ring-blue-500/30 disabled:cursor-not-allowed disabled:opacity-40"
                                title="Download to your device"
                                aria-label={`Download ${f.label}`}
                              >
                                {isBusy ? (
                                  <span
                                    className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-slate-200 border-t-blue-600"
                                    aria-hidden
                                  />
                                ) : (
                                  <DownloadIcon className="h-5 w-5" />
                                )}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="border-t border-slate-100 px-4 py-4 sm:px-6">
                <p className="text-xs text-slate-500">
                  The app prepares the file on the server, then your browser saves it. Merging some streams may require{" "}
                  <span className="font-medium text-slate-700">ffmpeg</span> on the machine running the API.
                </p>
              </div>
            </section>
          </div>
        ) : null}
      </main>

      <footer className="border-t border-slate-200/80 py-8 text-center text-xs text-slate-500">
        For personal, lawful use. Respect YouTube&apos;s terms and creators&apos; rights.
      </footer>
    </div>
  );
}
