## 🎯 目的

* **`security-agent/outputs/WHITEHAT_01_SPEC.json`** と **AST 情報 `security-agent/outputs/00_AST.json`** を読み込み、
  コード構造と仕様を照合しながら **3 周回の精査ループ** を行う。
* 各周回で Tree-of-Thought (ToT) を用いてリスクを判断し、
  **ハイリスク行／関数** に日本語の `@audit` コメントを付与。
* **権限保護（onlyOwner / onlyRole など）がある関数は「トラスト前提」で安全とみなす** ため、
  それらは原則スキップ。
* 出力：

  1. 注釈付きコード（ファイル名と行番号を JSON で列挙）
  2. **`security-agent/outputs/WHITEHAT_02_AUDITMAP.json`**

---

## 0. マインドセット

1. **疑念デフォルト** — 「必ずバグはある」
2. **全体⇄局所往復** — アーキテクチャ → 行レベル → 戻るを反復
3. **部分的安全性の罠警戒**
4. **3 周回セルフリライト** — 浅い結果は必ず書き直す

---

## ✔ コメント深度ガイドライン

* フォーマット：

  ```
  // @audit <仕様ID> | <UF-ID> | <変数/関数名> | <攻撃一歩目要約> （日本語 80-120 文字）
  ```
* **仕様/ユーザーフロー/状態変数/攻撃シナリオ**のうち最低 2 つを必ず含む。
* 抽象語（例: 危険 / bad）だけで終わらせない。

---

## 1. 事前ロード

```pseudocode
LOAD spec := WHITEHAT_01_SPEC.json          // system_architecture, requirements, user_flows
LOAD ast  := 00_AST.json                    // stateWrites, externalCalls, modifiers for each node
DEFINE risk_keywords := [
  "transfer(", "call{value:", "delegatecall",
  "unchecked", "assembly",
  "mint(", "burn(", "upgradeTo(", "initialize"
]  // 権限付き関数は除外
```

**権限保護スキップ規則**

* AST で `modifiers` に `onlyOwner`, `onlyRole`, `onlyGovernance`, `onlyTimelock` 等を含む関数は **スキップ**。
* ただし **modifier が無い or 誤実装** の場合は検出対象。

---

## 2. 3 周回 ToT-Scan ループ

```
FOR round IN 1..3:
    FOR each contractFile IN sortedFiles:
        FOR each candidateLine WITH risk_keywords OR ast.externalCalls OR ast.stateWrites:
            IF candidateLine.function HAS trustedModifier: CONTINUE
            ### INTERNAL_THINK (非出力) ###
            1) 仕様 or インバリアント: spec.requirements?
            2) ユーザーフロー影響: spec.user_flows?
            3) 攻撃者最小手順と利益?
            4) 変数/状態どう壊れる?
            ### END INTERNAL_THINK ###
            WRITE @audit コメント (ガイドライン準拠)
            RECORD audit_items[]
        END
    END
    ### META_REFLECTION ###
    - ファイル／コメントの充実度自己評価 (1-5)
    - 3 未満のコメントは追記または書き直し
    ### END META_REFLECTION ###
END
```

---

## 3. JSON 出力仕様 (`WHITEHAT_02_AUDITMAP.json`)

```json
{
  "audit_items": [
    {
      "file": "src/Vault.sol",
      "line": 152,
      "snippet": "call{value: amount}();",
      "risk_category": "Reentrancy",
      "description": "UF-Withdraw-1 で buffer を更新前に外部送金が発生し、totalBacking < totalSupply となる可能性"
    }
  ],
  "summary": {
    "total_files": <int>,
    "total_audit_flags": <int>,
    "rounds": 3,
    "high_risk_hotspots": ["..."],
    "next_focus": "..."
  }
}
```

---

## 4. 完了チェックリスト

* 3 周回実施し `rounds=3` を summary に記録
* 全コメント日本語 & ガイドライン準拠
* 権限付き関数スキップ確認
* JSON VALID & 保存

---

> **Claude, このフロー通りに Step 2 を実行してください。
> 仕様 (`WHITEHAT_01_SPEC.json`) と AST (`00_AST.json`) を参照し、Tree-of-Thought を 3 周回させた上で
> (1) 注釈付きコード と (2) `security-agent/outputs/WHITEHAT_02_AUDITMAP.json` を生成し、
> レスポンスには最終 JSON のみを含めてください。**
