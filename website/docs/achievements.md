---
sidebar_position: 9
title: 実績
---

# 実績 (コミュニティ追記 OK)

SPECA を使って見つけたバグ、提出した報告、当てた賞金、書いたツール拡張など、コミュニティの実績をここに集めるページです。**誰でも自由に追記できます**。

> 自分の SPECA 利用結果をここに載せたい方は、このファイル (`website/docs/achievements.md`) を直接編集する pull request を [NyxFoundation/speca](https://github.com/NyxFoundation/speca) に出してください。匿名希望の場合はハンドル名のみで OK です。

## 追記テンプレート

```markdown
### YYYY-MM-DD — <短いタイトル>

- 報告者: <ハンドル名 or 組織名>
- ターゲット: <監査対象。リポジトリ URL や hash 等。非公開なら「private」と記載>
- 種別: <CONFIRMED_VULNERABILITY / CONFIRMED_POTENTIAL / DOWNGRADED / 等>
- 重大度: <Critical / High / Medium / Low / Informational>
- 概要: <2-3 行で。バグの内容や、どのように SPECA が役立ったか>
- 公開状態: <bug bounty 報告済 / patch 公開済 / disclosure 期限内 / 等>
- 参考リンク: <PR / commit / advisory / writeup の URL があれば>
```

## 載せるときのガイドライン

- **disclosure timeline を守る**: 修正前のバグや非公開のバグ詳細は記載しない
- **再現コードは原則貼らない**: writeup や advisory の URL を載せるに留める
- **個人情報の扱い**: 自分のハンドル名のみ、第三者の個人情報は書かない
- **誇張しない**: 数字や severity は実報告通りに、誇張・過小評価とも避ける
- **コミット規約**: 追記の commit メッセージは英語、PR タイトル / 本文は日本語可

---

## 実績

### 2026-05-08 — speca-cli homepage の初期版

- 報告者: hirorogo
- ターゲット: NyxFoundation/speca リポジトリ
- 種別: コントリビューション (バグではなくドキュメント整備)
- 概要: Docusaurus ベースのホームページを `website/` 以下に新規構築。日本語ドキュメント・論文 2 本のリファレンス・やさしいガイド・実戦チュートリアル・設計の裏側ノート・ブログ枠まで一通り作成。
- 参考リンク: [PR #36](https://github.com/NyxFoundation/speca/pull/36)

---

> 続きの実績は pull request でこのページに足していってください。
