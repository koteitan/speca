// Term glossary for the <Tooltip term="..."/> component.
//
// Section 4.10.2 of `docs/UI_DESIGN.md` requires inline hover hints for
// SPECA-specific jargon. The dictionary is intentionally small (~12
// entries) — adding rare terms here costs nothing, but the v0 surface
// area covers the words actually rendered in the Runs / Findings tables.
//
// Keep entries SHORT (one sentence, Japanese). The full reference lives
// in the docs site; the tooltip is a "is this what I think it is?" prompt.

export type GlossaryKey =
  | "CWE"
  | "STRIDE"
  | "property"
  | "subgraph"
  | "verdict"
  | "severity"
  | "phase 03"
  | "phase 04"
  | "bug bounty scope"
  | "trust boundary"
  | "dead code"
  | "DISPUTED_FP"
  | "CONFIRMED_VULNERABILITY";

export const glossary: Record<GlossaryKey, string> = {
  CWE: "Common Weakness Enumeration。ソフトウェア脆弱性の共通分類 (例: CWE-22 Path Traversal)。",
  STRIDE:
    "脅威モデリングのフレームワーク。Spoofing / Tampering / Repudiation / Information disclosure / Denial of service / Elevation of privilege。",
  property:
    "形式的なセキュリティプロパティ。「常に X が成り立つ」という不変条件で、Phase 01e が生成する。",
  subgraph:
    "仕様から抽出した状態遷移グラフ。Mermaid 形式で、各ノードに不変条件を持つ。Phase 01b の出力。",
  verdict:
    "Phase 04 の最終判定。CONFIRMED_VULNERABILITY / CONFIRMED_POTENTIAL / DISPUTED_FP / DOWNGRADED / NEEDS_MANUAL_REVIEW / PASS_THROUGH の 6 値。",
  severity:
    "脆弱性の深刻度。Critical / High / Medium / Low / Informational の 5 段階。",
  "phase 03":
    "Audit Map。プロパティが target コードで成立するかを Proof ベースで検証する Phase。",
  "phase 04":
    "Review。Dead Code / Trust Boundary / Scope Check の 3 ゲートで誤検知をフィルタする recall-safe pipeline。",
  "bug bounty scope":
    "対象 bug bounty プログラムの in-scope / out-of-scope 定義。`BUG_BOUNTY_SCOPE.json` に保存される。",
  "trust boundary":
    "信頼境界。外部入力が内部処理に到達する境界線で、ここを越える finding は誤検知になりにくい。",
  "dead code":
    "Phase 04 の Gate 1。実際には到達不可能なコードパスで報告された finding を除外する。",
  DISPUTED_FP:
    "Phase 04 の 3 ゲートいずれかが「実は誤検知 (False Positive)」と判定した verdict。Recall-safe 設計のため、この 3 ゲートのみが FP 判定を出せる。",
  CONFIRMED_VULNERABILITY:
    "Phase 04 の最終判定で「真の脆弱性」と確認された finding。Report 化の主対象。",
};

/** Lookup with case-insensitive fallback so callers can pass casual spellings. */
export function lookupGlossary(term: string): string | undefined {
  if (term in glossary) {
    return glossary[term as GlossaryKey];
  }
  const lower = term.toLowerCase();
  for (const key of Object.keys(glossary) as GlossaryKey[]) {
    if (key.toLowerCase() === lower) {
      return glossary[key];
    }
  }
  return undefined;
}
