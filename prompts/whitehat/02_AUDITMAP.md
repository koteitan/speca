==================== WHITEHAT_02 コード注釈タスク ====================
🎯 **目的**
1. `security-agent/outputs/WHITEHAT_01b_AUDITMAP_ORDER.json` 内
   **function_chunks** をチャンク順／関数順に処理し、
   **必ずソースコードへ直接 `@audit` / `@audit-ok` コメント** を挿入する。
2. `security-agent/outputs/WHITEHAT_01_SPEC.json` と
   `security-agent/outputs/00_AST.json` を照合し、
   ホワイトハッカーのメンタルモデル（階層的防御・経済合理性・攻撃者視点）を
   適用してリスクを評価。
3. 3 周回 Tree-of-Thought (ToT) ＋ メタ反省で自己リライトを行い、
   (a) 注釈位置一覧 と
   (b) `security-agent/outputs/WHITEHAT_02_AUDITMAP.json`
   を生成・保存。
------------------------------------------------------------------------------
■ メンタルモデル & ノウハウ（常時適用）
  ● 疑念デフォルト — 「バグは必ず潜む」
  ● 防御層ピラミッド — Core-Logic → Guard → Permission → Economic-Checks
  ● 攻撃者 ROI 計算 — コスト < 利益 を想定し最短パスを探す
  ● 部分的安全性の罠 — 単独 OK でも組合せで危険
  ● トラスト境界明確化 — onlyOwner 等は “trusted” としスキップ
------------------------------------------------------------------------------
■ 途中再開ロジック
  WHITEHAT_01b_AUDITMAP_ORDER.json:
    {
      "function_chunks":[
        {"chunk_name":"UF-Deposit","functions":[...],"done_index":N}, ...
      ]
    }
  * done_index == len(functions) のチャンクはスキップ。
  * 各関数処理後に done_index++、ファイルを即保存。
------------------------------------------------------------------------------
■ コメントフォーマット（コード内に直接）
  // @audit  <仕様ID|N/A> | <UF-ID|N/A> | <変数/関数> | <攻撃一歩目要約>（80–120字日本語）
  // @audit-ok <根拠>（60–100字日本語）
  * 少なくとも **仕様/UF/状態変数/攻撃シナリオ** の 2 要素を含め、
    抽象語で終わらないこと。
------------------------------------------------------------------------------
■ スキップ & 信頼ルール
  * `onlyOwner` / `onlyRole` / `onlyGovernance` / `onlyTimelock` など
    **trusted modifiers** 付き関数は原則スキップ。
  * ただし **modifier 欠落・誤実装** は必ず検出対象。
------------------------------------------------------------------------------
■ 3 周回 ToT + メタ反省フロー
  FOR round IN 1..3:
    • INTERNAL_THINK（非出力）
        1) 仕様／インバリアント
        2) ガード列挙 → 迂回可否
        3) 攻撃最短手順・利益
        4) 経済合理性 (ROI)
    • コメント挿入 (@audit / @audit-ok)
    • audit_items[] へ記録
    • META_REFLECTION
        - コメント深度自己評価(1-5)→3 未満なら追記
------------------------------------------------------------------------------
■ JSON 出力 (`WHITEHAT_02_AUDITMAP.json`)
{
  "audit_items":[
    {
      "file":"src/Vault.sol",
      "line":152,
      "snippet":"call{value: amount}();",
      "risk_category":"Reentrancy",
      "description":"UF-Withdraw-1 で buffer を更新前に外部送金が発生し、totalBacking < talSupply となる恐れ",
      "status":"Vuln"|"ok"
    }
  ],
  "summary":{
    "rounds":3,
    "total_audit_flags":<int>,
    "high_risk_hotspots":["..."],
    "next_focus":"..."
  }
}
------------------------------------------------------------------------------
■ 出力 & チャット応答
  * ソースコードはコメント付きで保存。
  * **チャット返信には `WHITEHAT_02_AUDITMAP.json` の JSON オブジェクトのみ**。
  * 説明・ログは一切含めない。
------------------------------------------------------------------------------
💡 実行開始！
