---
sidebar_position: 1
---

# 運用ガイド概要

データセットのリフレッシュ・ベンチマークの実行・成果物の配布など、SPECA を「動かす側」のための作業手順をまとめたカテゴリです。

## 想定読者

- SPECA の評価結果を再現したい研究者・実装者
- HuggingFace の audit-finding コーパス([NyxFoundation/vulnerability-reports](https://huggingface.co/datasets/NyxFoundation/vulnerability-reports))を更新したい運用担当者
- 新しいベンチマーク実行結果を共有したい貢献者

## 共通前提

- speca リポジトリのチェックアウト + [インストール](../getting-started/installation.md)
- self-hosted GitHub Actions runner(`grandchildrice` / `hirorogo` の allowlist)
- ターゲット作業に応じた追加 secret:
  - `HF_TOKEN` — HuggingFace org `NyxFoundation` への write 権限
  - `GITHUB_TOKEN` — Release への書き込み(GitHub Actions が自動発行)

## このカテゴリのページ

| ページ | 目的 |
|---|---|
| [データセットを更新する](./dataset-refresh.md) | scrape → CSV → HF dataset の loop |
| [ベンチマーク成果物の配布](./release-artifacts.md) | `benchmarks/results/` を GitHub Release に bundle / restore |
| [RQ1 を再現する](./benchmark-rq1.md) | Sherlock Ethereum Fusaka audit contest |
| [RQ2 を再現する](./benchmark-rq2a.md) | RepoAudit C/C++ benchmark |
| [RQ2b を再現する](./benchmark-rq2b.md) | ProFuzzBench(探索的) |

## 全体像

```
  scrape_*.py (手元で実行)
        ↓
  benchmarks/data/defi_audit_reports/*.csv
        ↓
  Publish dataset to HuggingFace (workflow_dispatch)
        ↓
  https://huggingface.co/datasets/NyxFoundation/vulnerability-reports
```

```
  benchmarks/results/<rq>/<run>/  (eval pipeline 出力)
        ↓
  Publish benchmark artifacts (workflow_dispatch)
        ↓
  GitHub Release `bench-<rq>-<date>-<suffix>`
        ↓
  restore-results.sh で再展開
```
