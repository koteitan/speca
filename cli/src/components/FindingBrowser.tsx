/**
 * FindingBrowser — top-level Ink component for `speca browse`.
 *
 * Composition:
 *   ┌─ FilterBar
 *   ├─ FindingTable    (windowed; selection driven by useInput here)
 *   ├─ FindingDetail   (always shown for the highlighted row)
 *   └─ CodePeek        (only after the user presses `c`)
 *
 * Keybindings (also documented at the bottom of the screen):
 *   ↑/↓ or k/j    move selection
 *   Enter         toggle expanded detail
 *   c             open / refresh code peek for the selection
 *   f             enter filter-edit mode
 *   /             enter text-search edit mode (translates to `text:<query>`)
 *   s             cycle sort mode
 *   r             reload from disk
 *   q or Esc      exit
 *
 * The component is render-only when `nonInteractive=true` (used by tests)
 * to skip the `useInput` hook, which would crash without a real TTY.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Box, Text, useApp, useInput } from "ink";

import { CodePeek } from "./CodePeek.js";
import { FilterBar } from "./FilterBar.js";
import { FindingDetail } from "./FindingDetail.js";
import { FindingTable } from "./FindingTable.js";
import {
  type CodePeekResult,
  loadCodePeek,
} from "../lib/findings/codePeek.js";
import { applyFilter } from "../lib/findings/filter.js";
import {
  type LoadResult,
  type LoaderWarning,
  loadFindings,
} from "../lib/findings/loader.js";
import { type SortMode, nextSortMode, sortFindings } from "../lib/findings/sort.js";
import { useKeybind } from "../lib/keybinds/index.js";

export interface FindingBrowserProps {
  /** Initial dataset (typically pre-loaded by the command). */
  initial: LoadResult;
  /** Glob the loader was called with — kept for the `r` (reload) action. */
  globs: string[];
  /** Initial filter source (from `--filter`/`--severity`/`--verdict`). */
  initialFilter?: string;
  /** When true, do not register input handlers (useful for ink-testing). */
  nonInteractive?: boolean;
  /** Override base dir for code peek lookups. Defaults to process cwd. */
  cwd?: string;
}

export function FindingBrowser({
  initial,
  globs,
  initialFilter = "",
  nonInteractive = false,
  cwd,
}: FindingBrowserProps) {
  const { exit } = useApp();
  const [data, setData] = useState<LoadResult>(initial);
  const [filterApplied, setFilterApplied] = useState<string>(initialFilter);
  const [filterBuffer, setFilterBuffer] = useState<string>("");
  const [editing, setEditing] = useState<"none" | "filter" | "text">("none");
  const [sortMode, setSortMode] = useState<SortMode>("severity");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [peek, setPeek] = useState<CodePeekResult | null>(null);
  const [peekLoading, setPeekLoading] = useState(false);
  const [reloadMsg, setReloadMsg] = useState<string | null>(null);

  // Apply filter + sort to the in-memory dataset.
  const { matched, parsed } = useMemo(() => {
    const r = applyFilter(data.findings, filterApplied);
    if (!r.result.ok) {
      return { matched: data.findings, parsed: r.result };
    }
    return { matched: sortFindings(r.matched, sortMode), parsed: r.result };
  }, [data, filterApplied, sortMode]);

  const filterError = parsed.ok ? null : parsed.message;

  // Clamp selection to the new matched length.
  useEffect(() => {
    if (matched.length === 0) {
      setSelectedIndex(0);
      return;
    }
    if (selectedIndex >= matched.length) setSelectedIndex(matched.length - 1);
    if (selectedIndex < 0) setSelectedIndex(0);
  }, [matched, selectedIndex]);

  // Selection -> drop the previous code peek so it doesn't go stale.
  useEffect(() => {
    setPeek(null);
    setExpanded(false);
  }, [selectedIndex, filterApplied, sortMode]);

  const selected = matched[selectedIndex];

  // ─── Edit mode: useInput collects characters into the filter buffer. ───
  // The action layer (useKeybind) handles read-mode shortcuts below.
  // Both hooks are always called; `isActive` toggles which one fires.
  useInput(
    (input, key) => {
      if (key.escape) {
        setEditing("none");
        setFilterBuffer("");
        return;
      }
      if (key.return) {
        let raw = filterBuffer;
        if (editing === "text") raw = `text:${quoteIfNeeded(filterBuffer)}`;
        setFilterApplied(raw);
        setEditing("none");
        setFilterBuffer("");
        return;
      }
      if (key.backspace || key.delete) {
        setFilterBuffer((b) => b.slice(0, -1));
        return;
      }
      if (input && !key.ctrl && !key.meta) {
        setFilterBuffer((b) => b + input);
      }
    },
    { isActive: !nonInteractive && editing !== "none" },
  );

  // ─── Read-mode actions via the M6 keybind layer. Each call is gated
  // on `editing === "none"` so user characters typed into the filter
  // buffer don't double-trigger actions like `exit` or `sort-mode`.
  const readModeActive = !nonInteractive && editing === "none";

  useKeybind("exit", () => exit(), { isActive: readModeActive });
  useKeybind("up", () => setSelectedIndex((i) => Math.max(0, i - 1)), { isActive: readModeActive });
  useKeybind(
    "down",
    () => setSelectedIndex((i) => Math.min(Math.max(0, matched.length - 1), i + 1)),
    { isActive: readModeActive },
  );
  useKeybind("pageUp", () => setSelectedIndex((i) => Math.max(0, i - 10)), { isActive: readModeActive });
  useKeybind(
    "pageDown",
    () => setSelectedIndex((i) => Math.min(Math.max(0, matched.length - 1), i + 10)),
    { isActive: readModeActive },
  );
  useKeybind("confirm", () => setExpanded((v) => !v), { isActive: readModeActive });
  useKeybind(
    "filter-mode",
    () => {
      setEditing("filter");
      setFilterBuffer(filterApplied);
    },
    { isActive: readModeActive },
  );
  useKeybind(
    "search-mode",
    () => {
      setEditing("text");
      setFilterBuffer("");
    },
    { isActive: readModeActive },
  );
  useKeybind("sort-mode", () => setSortMode((m) => nextSortMode(m)), { isActive: readModeActive });

  const triggerCodePeek = useCallback(() => {
    if (!selected) return;
    setPeekLoading(true);
    loadCodePeek(selected.primaryLocation, { cwd }).then((res) => {
      setPeek(res);
      setPeekLoading(false);
    });
  }, [selected, cwd]);
  useKeybind("code-peek", triggerCodePeek, { isActive: readModeActive });

  const triggerReload = useCallback(() => {
    setReloadMsg("reloading…");
    loadFindings(globs, { cwd })
      .then((res) => {
        setData(res);
        setReloadMsg(`reloaded ${res.findings.length} finding(s) from ${res.files.length} file(s)`);
      })
      .catch((err: Error) => setReloadMsg(`reload failed: ${err.message}`));
  }, [globs, cwd]);
  useKeybind("reload", triggerReload, { isActive: readModeActive });

  return (
    <Box flexDirection="column">
      <Header globs={globs} matched={matched.length} total={data.findings.length} reloadMsg={reloadMsg} warnings={data.warnings} />
      <Box marginTop={1} flexDirection="column">
        <FilterBar
          applied={filterApplied}
          editing={editing !== "none"}
          buffer={filterBuffer}
          error={filterError}
          sortMode={sortMode}
          total={data.findings.length}
          matched={matched.length}
          modeLabel={editing === "text" ? "search" : "filter"}
        />
      </Box>
      <Box marginTop={1} borderStyle="single" borderColor="gray" flexDirection="column" paddingX={1}>
        <FindingTable findings={matched} selectedIndex={selectedIndex} viewportHeight={10} />
      </Box>
      <Box marginTop={1} borderStyle="single" borderColor="gray" flexDirection="column" paddingX={1}>
        <FindingDetail finding={selected} expanded={expanded} />
      </Box>
      <Box marginTop={1} borderStyle="single" borderColor="gray" flexDirection="column" paddingX={1}>
        <Text bold>Code peek</Text>
        <CodePeek peek={peek} loading={peekLoading} />
      </Box>
      <Box marginTop={1}>
        <Text dimColor>
          [↑/↓ j/k] move  [Enter] expand  [c] code peek  [f] filter  [/] text  [s] sort  [r] reload  [q] quit
        </Text>
      </Box>
    </Box>
  );
}

interface HeaderProps {
  globs: string[];
  matched: number;
  total: number;
  reloadMsg: string | null;
  warnings: LoaderWarning[];
}

function Header({ globs, matched, total, reloadMsg, warnings }: HeaderProps) {
  return (
    <Box borderStyle="round" paddingX={1} flexDirection="column">
      <Box>
        <Text bold>speca browse </Text>
        <Text dimColor>{`  ${matched}/${total} findings`}</Text>
      </Box>
      <Box>
        <Text dimColor>{`source: ${globs.join("  ")}`}</Text>
      </Box>
      {warnings.length > 0 ? (
        <Box>
          <Text color="yellow">{`! ${warnings.length} loader warning(s) — use --verbose to inspect`}</Text>
        </Box>
      ) : null}
      {reloadMsg ? (
        <Box>
          <Text color="cyan">{reloadMsg}</Text>
        </Box>
      ) : null}
    </Box>
  );
}

function quoteIfNeeded(s: string): string {
  if (/\s/.test(s)) return `"${s}"`;
  return s;
}
