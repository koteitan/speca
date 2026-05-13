// useDownloadMarkdown — tiny hook that turns a string + filename into a
// browser-side download.
//
// The hook is feature-agnostic on purpose: findings, run logs, chat
// transcripts, and any other Markdown/text payload can reuse it. The
// returned function:
//
//   1. Bails out on SSR (typeof window === "undefined") — future
//      Docusaurus integration may import this file during prerender.
//   2. Builds a Blob with `text/markdown;charset=utf-8` so the file
//      opens cleanly in editors that sniff the MIME, while still
//      reading as plain text everywhere else.
//   3. Creates an off-DOM <a download> anchor, clicks it, and revokes
//      the object URL on the next tick. We schedule revocation with
//      `setTimeout(0)` (and a `requestAnimationFrame` fallback) instead
//      of revoking synchronously because Safari aborts the download if
//      the URL is revoked before the click handler has fired.
//
// The hook is memoised with `useCallback` so consumers can pass it
// straight to `onClick` props without retriggering renders.

import { useCallback } from "react";

export type DownloadMarkdown = (text: string, filename: string) => void;

function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof document !== "undefined";
}

function scheduleRevoke(url: string): void {
  // Two-stage cleanup: a microtask is too early on Safari, and a long
  // timeout would leak if the page navigates first. 1s after the click
  // is the de-facto convention used by file-saver et al.
  const revoke = () => {
    try {
      URL.revokeObjectURL(url);
    } catch {
      // Swallow — revocation failures are not actionable for the caller.
    }
  };
  if (typeof window !== "undefined" && typeof window.setTimeout === "function") {
    window.setTimeout(revoke, 1000);
  } else {
    revoke();
  }
}

/**
 * Returns a `(text, filename) => void` function that triggers a
 * browser-side download. The returned function is stable across
 * renders.
 */
export function useDownloadMarkdown(): DownloadMarkdown {
  return useCallback((text: string, filename: string) => {
    if (!isBrowser()) {
      // SSR / test / worker context — no-op. Caller can branch on
      // `typeof window === "undefined"` if it needs a fallback (e.g.
      // copy-to-clipboard); the hook itself stays silent.
      return;
    }

    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    // Keep it off-screen and out of the tab order. Firefox requires the
    // anchor to be attached to the document for the click to fire.
    anchor.rel = "noopener";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);

    scheduleRevoke(url);
  }, []);
}
