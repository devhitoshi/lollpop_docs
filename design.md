---
version: "1.0"
name: lollpop-docs-design
description: 「ろりぽっぷ!!!!!!! Docs」(GitHub Pages で公開するファンドキュメント)のデザインシステム。純白のキャンバスに、角丸のない「フルブリード水平バンド」を積んで構成する。白・ブラッシュ(桜)・プラム黒・ピンクの4面が交互に切り替わり、バンド内のグルーピングは枠線ではなく余白と整列が担う。見出し・本文とも Noto Sans JP。ブランド電圧は白×ろりぽっぷピンク(#d6006e)の対で作り、押せるものの色はこのピンクただ一色。

colors:
  primary: "#d6006e"
  primary-active: "#b0005b"
  primary-disabled: "#f5cce1"
  primary-on-dark: "#ff9ecb"
  ink: "#1d1216"
  body: "#45383e"
  body-strong: "#2a2026"
  muted: "#71646b"
  muted-soft: "#998a92"
  hairline: "#f2e2ea"
  hairline-soft: "#faeef4"
  canvas: "#ffffff"
  surface-soft: "#fff5f9"
  surface-blush: "#fbe7f0"
  surface-blush-strong: "#f6d3e3"
  surface-dark: "#1a1113"
  surface-dark-elevated: "#2a1a24"
  surface-dark-soft: "#241a20"
  on-primary: "#ffffff"
  on-dark: "#fff5f9"
  on-dark-soft: "#d9c4ce"
  success: "#2e9e5b"
  warning: "#b45309"
  error: "#cf3a3a"
  chart-orig: "#d6006e"
  chart-stk: "#2a6fd6"
  chart-hpst: "#eda100"
  chart-open: "#2a6fd6"
  chart-close: "#eb6834"
  chart-seq-1: "#fcdfee"
  chart-seq-2: "#f6b7d7"
  chart-seq-3: "#ee8abc"
  chart-seq-4: "#e0539b"
  chart-seq-5: "#c21b74"
  chart-seq-6: "#8f0050"
  chart-grid: "#f0e2e9"
  chart-axis: "#dcc8d2"
  mc-kurumi: "#cc0000"
  mc-mayu: "#f5c400"
  mc-mau: "#7fd4e8"
  mc-ami: "#2e9e5b"
  mc-mana: "#ffffff"
  mc-asaka: "#f172a3"
  mc-natsumi: "#2a6fd6"

typography:
  display-xl:
    fontFamily: "Noto Sans JP, Hiragino Kaku Gothic ProN, Yu Gothic Medium, Meiryo, sans-serif"
    fontSize: 48px
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: -0.02em
  display-lg:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 36px
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: -0.02em
  display-md:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: -0.015em
  display-sm:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 22px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: -0.01em
  title-lg:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 20px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: 0
  title-md:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 17px
    fontWeight: 700
    lineHeight: 1.5
    letterSpacing: 0
  title-sm:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 15px
    fontWeight: 700
    lineHeight: 1.5
    letterSpacing: 0
  body-lg:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 20px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0.01em
  body-md:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.85
    letterSpacing: 0.01em
  body-sm:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.8
    letterSpacing: 0.01em
  caption:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: 0.01em
  caption-uppercase:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 12px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: 0.12em
  code:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0
  button:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 15px
    fontWeight: 500
    lineHeight: 1
    letterSpacing: 0
  nav-link:
    fontFamily: "Noto Sans JP, sans-serif"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0

rounded:
  none: 0
  xs: 4px
  sm: 6px
  md: 8px
  pill: 9999px
  full: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  gutter: 24px
  band: 64px
  section: 96px

components:
  top-nav:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.nav-link}"
    height: 56px
    borderBottom: "1px {colors.hairline}"
  sub-nav:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.title-md}"
    borderBottom: "1px {colors.hairline}"
    height: 52px
  band-white:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    rounded: "{rounded.none}"
    padding: 96px 24px
  band-blush:
    backgroundColor: "{colors.surface-blush}"
    textColor: "{colors.body}"
    rounded: "{rounded.none}"
    padding: 96px 24px
  band-dark:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    rounded: "{rounded.none}"
    padding: 96px 24px
  band-pink:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.none}"
    padding: 64px 24px
  hero-band:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.display-xl}"
    rounded: "{rounded.none}"
    padding: 96px 24px
  band-eyebrow:
    backgroundColor: transparent
    textColor: "{colors.muted-soft}"
    typography: "{typography.caption-uppercase}"
  feature-band:
    backgroundColor: "{colors.surface-blush}"
    textColor: "{colors.ink}"
    typography: "{typography.title-md}"
    rounded: "{rounded.none}"
    padding: 96px 24px
    columnGap: 32px
  feature-item:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.title-sm}"
  stat-band:
    backgroundColor: "{colors.surface-blush}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: 64px 24px
    columnGap: 32px
  stat-item:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.display-md}"
  chart-figure:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: 24px
  chart-tooltip:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.md}"
    border: "1px {colors.hairline}"
  method-band:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.none}"
    padding: 64px 24px
  doc-prose:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    typography: "{typography.body-md}"
    maxWidth: 720px
  toc-list:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
  callout:
    backgroundColor: "{colors.surface-blush-strong}"
    textColor: "{colors.body-strong}"
    typography: "{typography.body-md}"
    rounded: "{rounded.none}"
    padding: 24px 32px
  pull-quote:
    backgroundColor: transparent
    textColor: "{colors.body-strong}"
    typography: "{typography.display-sm}"
  list-row:
    backgroundColor: transparent
    textColor: "{colors.body}"
    typography: "{typography.body-md}"
    borderBottom: "1px {colors.hairline}"
    padding: 16px 0
  member-dots:
    backgroundColor: transparent
    size: 12px
    rounded: "{rounded.full}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 44px
  button-primary-active:
    backgroundColor: "{colors.primary-active}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
  button-primary-disabled:
    backgroundColor: "{colors.primary-disabled}"
    textColor: "{colors.muted}"
    rounded: "{rounded.md}"
  button-secondary:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    border: "1px {colors.hairline}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 44px
  button-secondary-on-dark:
    backgroundColor: "{colors.surface-dark-elevated}"
    textColor: "{colors.on-dark}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
  button-inverse-on-primary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 44px
  button-text-link:
    backgroundColor: transparent
    textColor: "{colors.primary}"
    typography: "{typography.button}"
  text-link:
    backgroundColor: transparent
    textColor: "{colors.primary}"
    typography: "{typography.body-md}"
  badge-pill:
    backgroundColor: "{colors.surface-blush-strong}"
    textColor: "{colors.ink}"
    typography: "{typography.caption}"
    rounded: "{rounded.pill}"
    padding: 4px 12px
  badge-pink:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.caption-uppercase}"
    rounded: "{rounded.pill}"
    padding: 4px 12px
  cta-band-pink:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.display-sm}"
    rounded: "{rounded.none}"
    padding: 64px 24px
  footer:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark-soft}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.none}"
    padding: 64px 24px
---

## Overview

「ろりぽっぷ!!!!!!! Docs」は、アイドルグループ「ろりぽっぷ!!!!!!!」のファンドキュメントを
GitHub Pages で公開するサイト群のデザインシステム。実装の正は本ファイルで、
`resources/css/style.css` がこのトークンの実装、`resources/` の各HTMLがその適用先になる。

床は**純白のキャンバス**(`{colors.canvas}`)。グレーがかったオフホワイトには逃げない。
その上に**フルブリードの水平バンド**を積んで1ページを構成する。バンドは端から端まで走る
色面で、1バンドに1つの話題だけを載せる。バンドの中では、枠線や箱ではなく
**余白と整列**がグルーピングを担う。

ブランド電圧は**白×ろりぽっぷピンク**(`{colors.primary}` — #d6006e)の対で作る。
ピンクは「押せるもの」(ボタン・リンク・アクティブ表示)と、1ページに1回だけ許される
フルブリードのピンク帯に使う。要素単位では希少に、ピンク帯では惜しみなく。

タイポグラフィは**全部 Noto Sans JP**。ウェイト(700の見出し/400の本文)とサイズが
階層のすべてを担う。コンテンツは日本語なので、行間は欧文の常識より緩く取る(本文1.85)。

サイトの4つのバンド面:
1. **白**(`{colors.canvas}`) — 既定の床。本文が住む場所
2. **ブラッシュ**(`{colors.surface-blush}`) — 話題の切り替わり。特徴紹介・グループ化されたリスト
3. **プラム黒**(`{colors.surface-dark}`) — データ・集計方法・フッター。ニュートラルな炭色ではなく、ピンクと同族のプラムに寄せた黒
4. **ピンク**(`{colors.primary}`) — 1ページに最大1回のCTAの瞬間

**要点:**
- 純白キャンバス+プラム寄りの黒文字(`{colors.ink}`)。白い床があるから、他の面が「決定」として読める
- バンド構成。コンテンツを包むカードなし、角丸の面なし、影なし、グループを囲う枠線なし
- 角丸は操作要素だけ: ボタン・入力・チップに `{rounded.md}`(8px)まで、バッジに pill。それ以外はすべて `{rounded.none}`
- ヘアライン(`{colors.hairline}`)は情報を刻む場所にだけ引く(後述の3箇所+Docs例外1箇所)
- バンドのリズムは縦 `{spacing.section}`(96px)。バンド内のアイテム間は `{spacing.xl}`(32px)以上
- メンバーカラー7色は**装飾専用**。リンクやボタンには決して使わない
- 🍭 絵文字+「ろりぽっぷ!!!!!!! Docs」がワードマーク。絵文字はアイコン・被写体としても使う

## Bands

バンドはこのシステム唯一のレイアウトコンテナ。他所ならカードになるものは、
ここではバンドそのもの・バンド内のアイテム・素の流し込みコンテンツのどれかになる。

### 解剖
- **面** — 上記4色のどれか。端から端までフルブリード。radius なし、枠なし、影なし
- **ガター** — 横 `{spacing.gutter}`(24px)以上。ワイド画面ではコンテンツ列が上限幅
  (ポータル等は 1200px、読み物は 720px)に達し、余りはガターが吸収する
- **縦パディング** — 主要バンドは `{spacing.section}`(96px)、詰めるバンド
  (CTA・集計方法・フッター)は `{spacing.band}`(64px)
- **アイブロウ**(任意) — `{component.band-eyebrow}`。`{typography.caption-uppercase}` を
  `{colors.muted-soft}` で。バンドの中身に名前が要るときだけ(RANKING、TIMELINE など)。全バンドには付けない

### バンド内のグルーピング
枠線がやるはずだった仕事を余白がやる:
- 横並びのアイテム間は最低 `{spacing.xl}`(32px)。テキストが重いなら `{spacing.xxl}`(48px)
- アイテム同士の間隔は、タイトルとその説明の間隔(`{spacing.xxs}`〜`{spacing.xs}`)より
  **常に目に見えて広く**。この比率が「これは一組」と枠なしで読ませる
- アイテムは上端と左端を揃える。整列が乱れると箱が欲しくなる。箱を足すのではなく整列を直す

### 線を引いてよい場所
線は情報を刻むためのもので、飾りではない。1px の `{colors.hairline}` は次の場所に限る:
- `{component.top-nav}` の下。クロームとページの境
- 密なリストや表の行間(`{component.list-row}`)。各行が独立したレコードである場合
- チャートのグリッド線・軸線(`{colors.chart-grid}` / `{colors.chart-axis}`)
- **Docs 例外**: viewer の `{component.sub-nav}` の下(ナビクロームの一部として扱う)

それ以外の場所では、バンドを切り替えるか余白を増やす。

### バンドの並び
同じ面を2連続で使わない。典型的なページはこう流れる:

`白(ヒーロー) → ブラッシュ(特徴/KPI) → 黒(データ) → 白(本文) → ピンク(CTA) → 黒(フッター)`

この交互が、ページのペースそのもの。ブラッシュが2連続すると継ぎ目のある1本の帯に見えてしまう。

## Colors

### ブランド&アクセント
- **ろりぽっぷピンク / Primary**(`{colors.primary}` — #d6006e): 署名色。
  プライマリCTAの背景、フルブリードのピンク帯、本文中のリンク、フォーカスリング。
  白地の上で 5.1:1 のコントラストがあり、白文字を小さいサイズで載せてもAAを通る
- **Pink Active**(`{colors.primary-active}` — #b0005b): 押下状態。色相を変えずに沈める
- **Pink Disabled**(`{colors.primary-disabled}` — #f5cce1)
- **Pink on Dark**(`{colors.primary-on-dark}` — #ff9ecb): 暗帯上の唯一のアクセント。
  濃いピンクは暗い面に沈むため、暗帯ではこの明ピンクに反転する

### 面
- **Canvas**(`{colors.canvas}` — #ffffff): 既定の床。純白
- **Surface Soft**(`{colors.surface-soft}` — #fff5f9): 白との差が最小のほんのり桜。
  白と区別したいがブラッシュ帯にはしたくない場面用
- **Surface Blush**(`{colors.surface-blush}` — #fbe7f0): 標準のグルーピング帯。primary の脱飽和
- **Surface Blush Strong**(`{colors.surface-blush-strong}` — #f6d3e3): バッジの地、強調カットイン
- **Surface Dark**(`{colors.surface-dark}` — #1a1113): データ帯・フッター。プラムの気配を持つ黒
- **Surface Dark Elevated**(`{colors.surface-dark-elevated}` — #2a1a24): 暗帯内の操作要素・クローム
- **Surface Dark Soft**(`{colors.surface-dark-soft}` — #241a20): 暗帯の中にもう一段必要なときの黒
- **Hairline**(`{colors.hairline}` — #f2e2ea) / **Hairline Soft**(`{colors.hairline-soft}` — #faeef4):
  1px の線の色。ブランドのごく薄い桜で、墨線には見せない

### 文字
- **Ink**(`{colors.ink}` — #1d1216): 見出し・第一級の文字。プラム寄りの黒
- **Body Strong**(`{colors.body-strong}` — #2a2026): リード段落・引用
- **Body**(`{colors.body}` — #45383e): 本文の既定色。純白の上に純黒は硬すぎる
- **Muted**(`{colors.muted}` — #71646b): アイテムの説明・小見出し
- **Muted Soft**(`{colors.muted-soft}` — #998a92): アイブロウ・キャプション・奥付
- **On Primary**(`{colors.on-primary}` — #ffffff)
- **On Dark**(`{colors.on-dark}` — #fff5f9): 暗帯上の文字。桜がかった白
- **On Dark Soft**(`{colors.on-dark-soft}` — #d9c4ce): 暗帯上の二次テキスト・フッター本文

### セマンティック
- **Success**(`{colors.success}` — #2e9e5b) / **Warning**(`{colors.warning}` — #b45309) /
  **Error**(`{colors.error}` — #cf3a3a)。Error はピンクと見分けがつくよう純赤方向に振ってある

### チャートパレット(データビジュアライゼーション)
セトリ白書・成長戦略ノートのグラフはこのトークンで塗る。**図版の床は必ず白**
(ブラッシュ帯の中では図版領域を白のカットインにする。淡色セルと枠だけのセルは
白以外の床では読めない)。

- カテゴリカル(楽曲ルーツ別): オリジナル=`{colors.chart-orig}`(=primary)、
  ストクレ=`{colors.chart-stk}`(#2a6fd6)、ハピスト=`{colors.chart-hpst}`(#eda100)
- ダイバージング(曲順ポジション): 1曲目=`{colors.chart-open}`(青)、ラスト=`{colors.chart-close}`(橙)
- シーケンシャル(ヒートマップ・ピンク単色 淡→濃):
  `{colors.chart-seq-1}` → `{colors.chart-seq-6}`(#fcdfee → #8f0050)
- 補助: グリッド=`{colors.chart-grid}`、軸=`{colors.chart-axis}`
- 比較対象・文脈系列はグレー(`{colors.muted-soft}`)、主役系列だけに色を使う

### メンバーカラー(装飾専用)
くるみ=`{colors.mc-kurumi}`(赤)、茉夢=`{colors.mc-mayu}`(黄)、まう=`{colors.mc-mau}`(水色)、
愛美=`{colors.mc-ami}`(緑)、まな=`{colors.mc-mana}`(白・輪郭線付きで描く)。
卒業した2人の色(朝香=`{colors.mc-asaka}`、なつみ=`{colors.mc-natsumi}`)も記録として保持する。
**リンク・ボタン・状態表示には決して使わない。** ドット・凡例・チャートの曲識別だけ。

## Typography

### フォント
**Noto Sans JP** 一本(Google Fonts、wght 400 / 500 / 700)。
フォールバックは `Hiragino Kaku Gothic ProN → Yu Gothic Medium → Meiryo → sans-serif`。
コードとテーブル数値は `ui-monospace` 系。数値には `font-variant-numeric: tabular-nums` を指定する。

セリフ体は使わない。カードのないレイアウトでは型が階層の大半を担うため、
**ウェイトのコントラスト**(700の見出し vs 400の本文)をはっきり付ける。
Noto Sans JP の 400 をただ大きくした見出しは階層が立たないので作らない。

### 階層

| トークン | サイズ | ウェイト | 行間 | 字間 | 用途 |
|---|---|---|---|---|---|
| `{typography.display-xl}` | 48px | 700 | 1.25 | -0.02em | ヒーロー h1 |
| `{typography.display-lg}` | 36px | 700 | 1.3 | -0.02em | バンド見出し |
| `{typography.display-md}` | 28px | 700 | 1.35 | -0.015em | セクション見出し・KPI数値 |
| `{typography.display-sm}` | 22px | 700 | 1.4 | -0.01em | CTA帯見出し・引用 |
| `{typography.title-lg}` | 20px | 700 | 1.4 | 0 | 大きめのアイテム見出し |
| `{typography.title-md}` | 17px | 700 | 1.5 | 0 | バンド内アイテムの見出し |
| `{typography.title-sm}` | 15px | 700 | 1.5 | 0 | 小さなアイテム見出し・図版タイトル |
| `{typography.body-lg}` | 20px | 400 | 1.6 | 0.01em | リード文 |
| `{typography.body-md}` | 16px | 400 | 1.85 | 0.01em | 本文 |
| `{typography.body-sm}` | 14px | 400 | 1.8 | 0.01em | 説明文・フッター本文 |
| `{typography.caption}` | 13px | 500 | 1.5 | 0.01em | バッジ・キャプション・凡例 |
| `{typography.caption-uppercase}` | 12px | 700 | 1.4 | 0.12em | アイブロウ(英字)。和文なら 0.06em |
| `{typography.code}` | 14px | 400 | 1.6 | 0 | コード・パス表記 |
| `{typography.button}` | 15px | 500 | 1.0 | 0 | ボタンラベル |
| `{typography.nav-link}` | 13px | 500 | 1.4 | 0 | ナビのリンク |

### 原則
- 和文の負の字間は控えめに(-0.01〜-0.02em)。欧文流の -1.5px は和文を潰す
- 本文は `{colors.body}` で組む。純白の上の `{colors.ink}` 長文は硬い
- 本文の行長は全角 38〜42 字(≒720px カラム)。バンドにはカードの縁がないので、
  行を止めるものは明示した measure しかない
- 見出しは `text-wrap: balance` を指定してよい

## Layout

### スペーシング
- 基本単位 4px。`{spacing.xxs}` 4 / `{spacing.xs}` 8 / `{spacing.sm}` 12 / `{spacing.md}` 16 /
  `{spacing.lg}` 24 / `{spacing.xl}` 32 / `{spacing.xxl}` 48 / `{spacing.band}` 64 / `{spacing.section}` 96
- バンド縦: 主要 96px、詰め 64px。モバイルでは 96→56px
- バンド横ガター: 24px(モバイル)〜。コンテンツ列が上限に達したらガターが余白を吸収
- アイテム間: 32px以上。タイトルと自分の説明の間: 4〜8px。この差がグルーピングそのもの

### グリッドとコンテナ
- **コンテンツ上限幅**: ポータル・図版の多いページは 1200px、読み物(doc)は 720px。
  面は常にフルブリードで、列だけが応答する
- **特徴アイテム**: デスクトップ 3-up、タブレット 2-up、モバイル 1-up。カードの列ではなくグリッドの列
- **KPI(stat)**: 4-up → 2-up → 2-up

### 余白の思想
白は余白を増幅する。96px のバンドリズムは白い床の上でこそ「開けた」ページに読める。詰めたくなっても詰めない。

## Elevation & Depth

**エレベーションは存在しない。** 影なし、浮くパネルなし、持ち上がるカードなし。

奥行きはフルブリード面の連なりが作る: 白 → ブラッシュ → プラム黒 の進行を、
目は影なしで後退として読む。機能上の例外はフォーカスリング
(2px `{colors.primary}`、状態表示であって深度ではない)のみ。

暗帯の中では `{colors.surface-dark-elevated}` が操作要素・クロームの印。色の変化であって、持ち上げではない。

### 装飾
- 🍭 絵文字がワードマークの先頭と、バンドの「被写体」(旧タイル絵文字)を務める。
  絵文字グリフは 48〜64px で文字ではなく被写体として扱う
- メンバーカラードット(`{component.member-dots}`)は装飾の帯。ナビゲーションではない
- チャートはHTML/SVGで直接描く。画像化した図をカード枠に入れない

## Shapes

### 角丸スケール

| トークン | 値 | 用途 |
|---|---|---|
| `{rounded.none}` | 0 | すべてのバンド、すべてのコンテンツ面、図版、画像、カットイン。**既定** |
| `{rounded.xs}` | 4px | ヒートマップのセル、小さなチップ |
| `{rounded.sm}` | 6px | 小さなインラインボタン |
| `{rounded.md}` | 8px | ボタン、ツールチップ、インラインコードの地 |
| `{rounded.pill}` | 9999px | バッジ、パイプラインチップ |
| `{rounded.full}` | 9999px / 50% | メンバーカラードット、アイコンボタン |

スケールは 8px で止まる。それ以上の radius はカードを意味し、カードは存在しない。
旧システムの 18px 角丸(タイル・カード・画像)はすべて 0 に置き換える。

### 画像
`.doc` 内の画像(記事のグラフ画像など)は radius 0・影なしで、コンテンツ列に揃えて置く。

## Components

### ナビゲーション

**`top-nav`** — 白いバー、56px、下に 1px `{colors.hairline}`。左に「🍭 ろりぽっぷ!!!!!!! Docs」
ワードマーク、右に主要リンク。旧システムの黒いグローバルナビを置き換える。sticky でよい。

**`sub-nav`** — viewer 専用の第二バー。白地+ヘアライン下線(Docs 例外)。文書タイトルと「← 戻る」。
すりガラス(backdrop-filter)は使わない。

### バンド

**`band-white`** / **`band-blush`** / **`band-dark`** / **`band-pink`** — 4つの基本面。
フルブリード、`{rounded.none}`。以降はすべてこの特殊化。

**`hero-band`** — ページ先頭の白バンド。アイブロウ+h1(`{typography.display-xl}`)+リード+
ボタン行(+装飾のメンバーカラードット)。

**`feature-band`** / **`feature-item`** — ブラッシュ帯に 3 カラム。アイテムは絵文字グリフ+
`{typography.title-sm}` 見出し+`{colors.muted}` の説明文。アイテム自身は背景・枠・パディングを持たない。

**`stat-band`** / **`stat-item`** — KPI の行。数値は `{typography.display-md}`、ラベルは
`{typography.caption}` を `{colors.muted}` で。箱に入れず、整列だけで並べる。

**`chart-figure`** — チャートの図版領域。**床は常に白**。白バンド内では素のまま、
ブラッシュ帯内では白いカットイン(radius 0)として面ごと切り替える。図版タイトルは
`{typography.title-sm}`、補足は `{typography.caption}`。ツールチップは `{component.chart-tooltip}`
(白地・ヘアライン枠・8px・影なし)。

**`method-band`** — 集計方法・出典を載せる暗帯。`{colors.on-dark}` の見出しと
`{colors.on-dark-soft}` の本文。記事ページではフッターを兼ねてよい。

**`cta-band-pink`** — ページ唯一のピンクの瞬間。見出し `{typography.display-sm}`、
サブは `{colors.surface-blush}`、ボタンは `{component.button-inverse-on-primary}`。

**`callout`** — 結論・要点のカットイン。`{colors.surface-blush-strong}` の色面(radius 0)。
左罫線や枠線は付けない。面の色だけが強調。

**`doc-prose`** — marked が生成する記事本文。720px、`{typography.body-md}`。
h2 は罫線でなく余白(上 80px)+`{typography.display-md}` で切る。blockquote は
`{colors.surface-blush}` の色面(radius 0)。表は `{component.list-row}` のヘアライン行。

**`toc-list`** — 目次。「目次」アイブロウ+素のリンクリスト。箱・枠・角丸なし。

**`list-row`** — 密なレコードの行。16px 縦パディング+1px `{colors.hairline}` 下線。
線が正しいのはここ(各行が別レコード)だけ。

**`pull-quote`** — 白バンド内の独立した引用。`{typography.display-sm}` を
`{colors.body-strong}` で。引用符の装飾・左罫線・色地なし。サイズと行長が処理のすべて。

**`member-dots`** — メンバーカラーの 12px ドット列。白(`{colors.mc-mana}`)のドットだけ
1px の輪郭(inset)を描く。装飾専用。

**`footer`** — プラム黒の帯でページを閉じる。リンクは `{colors.primary-on-dark}`、
本文は `{colors.on-dark-soft}`。非公式サイトである旨の注記を必ず含める。

### ボタン

**`button-primary`** — ピンクのCTA。`{rounded.md}`(8px)、高さ44px。押下で
`{colors.primary-active}` に沈む。scale アニメーションは使わない。
暗帯の上では背景 `{colors.primary-on-dark}`・文字 `{colors.surface-dark}` に反転する。

**`button-secondary`** — 透明地+`{colors.ink}` 文字+1px `{colors.hairline}` 枠。
操作要素には輪郭が要る——これはカードの枠ではなく、ライト面で唯一の枠線。

**`button-secondary-on-dark`** — 暗帯内。地 `{colors.surface-dark-elevated}`、文字 `{colors.on-dark}`。

**`button-inverse-on-primary`** — 白地+`{colors.ink}` 文字。ピンク帯・暗帯の上で使う。

**`text-link`** — 本文中のリンクは `{colors.primary}`。暗帯上は `{colors.primary-on-dark}`。

### バッジ

**`badge-pill`** — 地 `{colors.surface-blush-strong}`、`{rounded.pill}`。工程チップ・タグ。
**`badge-pink`** — NEW / BETA 専用。

## Do's and Don'ts

### Do
- ページはフルブリードのバンドで組む。1バンド1話題
- バンド内は余白と整列でグルーピング。アイテム間 > タイトル&説明の間、を常に保つ
- 床は純白に固定する。白があるからピンクが「決定」として読める
- 見出しは Noto Sans JP 700。本文 400。ウェイト差をはっきり付ける
- ピンクはCTA・リンク・フォーカス・1枚のピンク帯に限定。1ページのピンクの瞬間は3〜4回が上限
- 本文の measure(720px / 全角40字前後)を明示する
- チャートの床は白。ブラッシュ帯では白カットインにする
- 面を交互に切り替える: 白 → ブラッシュ → 黒 → 白 → ピンク → 黒
- 数値は tabular-nums で揃える

### Don't
- コンテンツをカード・パネル・枠付きの箱で包まない。分けたければ面を替えるか余白を増やす
- 8px を超える radius を使わない(旧 18px 角丸は全廃)
- 影を使わない。エレベーションは存在しない(旧 .doc img の影も廃止)
- 線は情報を刻む場所以外に引かない。飾り罫・縦罫は禁止
- 床にグレー系オフホワイトを使わない
- メンバーカラーをリンク・ボタン・状態表示に使わない
- ピンクを至る所に塗らない。要素単位では希少に、ピンク帯では惜しみなく
- ブラッシュをラベンダーや桃色の方向にずらさない。`{colors.surface-blush}` は primary の脱飽和のみ
- 同じ面のバンドを2連続させない
- ホバーに独自の演出を足さない。press(active)の暗転だけが状態変化

## Responsive Behavior

### ブレークポイント

| 名前 | 幅 | 主な変化 |
|---|---|---|
| モバイル | < 640px | h1 48→30px、バンド縦 96→56px、アイテム 1-up、ボタン行は縦積み・全幅 |
| タブレット | 640–1024px | アイテム 2-up、ガター 24px |
| デスクトップ | > 1024px | アイテム 3-up、コンテンツ列 1200px(読み物 720px)上限、ガターが余白を吸収 |

どのブレークポイントでも面はフルブリード。応答するのは中の列だけ。
バンドがワイド画面で「額縁の中の箱」になってはいけない。

### タッチターゲット
- ボタンは最小 44×44px。リスト行・アイテムはセル全体をタップ領域にする

### 折りたたみ
- アイテムが 1-up に積まれたら、アイテム間を `{spacing.xxl}`(48px)に広げる。
  縦積みでは列の整列が失われるぶん、余白がグルーピングを引き受ける
- チャートは横スクロール(ヒートマップ等)。折り返さない
- 詳細テーブルは `details` で畳んでよい

## Iteration Guide

1. 新しい要素はまず「バンドか、バンド内のアイテムか、素の流し込みか」を決める。第四の答えはない
2. 1回の変更で触るのは1コンポーネント。YAML キー(`{component.feature-band}` 等)で参照する
3. 変種は `components:` の別エントリ(`-active`、`-disabled`、`-on-dark`)
4. hex を直書きせず、必ず `{token.refs}` を使う。値を変えるときは本ファイルが正で、
   `resources/css/style.css` に反映する。単一ファイル完結のHTML(セトリ白書・成長戦略)には
   同じ値を転記し、冒頭コメントで本ファイルを指す
5. hover は設計しない。Default と Active/Pressed だけ
6. 白+ブラッシュ+プラム黒+ピンクで面は完結。5つ目の面を発明しない
7. 枠・radius・影を足したくなったら、先に「余白を増やす/整列を直す/面を替える」を試す。
   それでほぼ全部解決する
8. 強調に迷ったら、太くするのではなく大きくする(700 のままサイズを上げる)

## Known Gaps

- チャートパレットのダークモード変種は旧セトリ白書に実績があるが、本システムは
  「純白が床」を原則とするためスコープ外(ページは `color-scheme: light` で固定)。
  将来ダーク対応するならパレットごと再検証が要る
- `{colors.mc-mana}`(白)はドット表現時に輪郭線が必須という例外を持つ
- note 入稿用のグラフ画像(articles/ 配下の PNG)は入稿済みスナップショットであり、
  本システムの適用対象外。再生成する場合はチャートパレット節に従う
- 印刷スタイルは未定義
