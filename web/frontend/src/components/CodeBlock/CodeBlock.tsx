// CodeBlock — syntax-highlighted <pre><code> via Prism.
//
// SPECA audits primarily target Solidity but the orchestrator is
// language-agnostic, so we ship a curated set of Prism grammars covering
// the languages SPECA can plausibly surface (Solidity, JS/TS, Python,
// Rust, Go, Java, C / C++). Adding a new one is a single `import` below.
//
// Why Prism (not highlight.js / shiki):
//   * Prism core is ~2 kB gzipped; each language grammar is 1-3 kB.
//   * No build step required — language modules attach to the global
//     Prism instance and we keep the bundle deterministic.
//   * Plays nicely with our CSS-tokenised theme system (Solarized included)
//     because we own the .token CSS rules instead of pulling a vendored
//     stylesheet that fights the rest of the app.
//
// Language detection: callers pass `language` explicitly if they know it,
// otherwise we sniff the file extension. Unknown languages fall through
// to plain text so we never throw.

import Prism from "prismjs";
import "prismjs/components/prism-clike";
import "prismjs/components/prism-c";
import "prismjs/components/prism-cpp";
import "prismjs/components/prism-go";
import "prismjs/components/prism-java";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-python";
import "prismjs/components/prism-rust";
import "prismjs/components/prism-solidity";
import "prismjs/components/prism-typescript";
import { useMemo } from "react";

import styles from "./CodeBlock.module.css";

export interface CodeBlockProps {
  /** Raw source text. Pre-formatted (no trailing-newline normalisation). */
  code: string;
  /** Optional explicit Prism language id. Wins over file-path sniffing. */
  language?: string;
  /** Source path used as a fallback for language detection. */
  filePath?: string;
  /** Starting line number for the gutter, 1-based. Pass `null` to hide it. */
  startLine?: number | null;
  /** Extra class for the outer container. */
  className?: string;
}

const EXT_TO_LANG: Record<string, string> = {
  sol: "solidity",
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  py: "python",
  pyi: "python",
  rs: "rust",
  go: "go",
  java: "java",
  c: "c",
  h: "c",
  cpp: "cpp",
  cc: "cpp",
  cxx: "cpp",
  hpp: "cpp",
  hh: "cpp",
};

function inferLanguage(language: string | undefined, filePath: string | undefined): string {
  if (language && Prism.languages[language]) return language;
  if (!filePath) return "";
  const lower = filePath.toLowerCase();
  const dot = lower.lastIndexOf(".");
  if (dot === -1) return "";
  const ext = lower.slice(dot + 1);
  return EXT_TO_LANG[ext] ?? "";
}

export function CodeBlock({
  code,
  language,
  filePath,
  startLine,
  className,
}: CodeBlockProps) {
  const lang = inferLanguage(language, filePath);

  const html = useMemo(() => {
    if (!code) return "";
    if (lang && Prism.languages[lang]) {
      try {
        return Prism.highlight(code, Prism.languages[lang], lang);
      } catch {
        // Fall through to plain text — never throw out of a render.
      }
    }
    // Escape so embedded HTML in evidence snippets doesn't render literally.
    return code
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }, [code, lang]);

  const lineNumbers = useMemo(() => {
    if (startLine === null || startLine === undefined) return null;
    const count = code ? code.split("\n").length : 0;
    if (count === 0) return null;
    const lines: number[] = [];
    for (let i = 0; i < count; i++) lines.push(startLine + i);
    return lines;
  }, [code, startLine]);

  return (
    <pre
      className={`${styles.pre} ${className ?? ""}`}
      data-language={lang || "plaintext"}
    >
      {lineNumbers && (
        <span className={styles.gutter} aria-hidden="true">
          {lineNumbers.map((n) => (
            <span key={n} className={styles.gutterLine}>
              {n}
            </span>
          ))}
        </span>
      )}
      <code
        className={`${styles.code} ${lang ? `language-${lang}` : ""}`}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </pre>
  );
}

export default CodeBlock;
