# 音源置き場

曲調解析（`.claude/skills/music-analysis/`）に使う音源を置くフォルダです。

**このフォルダの音源ファイルは `.gitignore` で除外されています。**
リポジトリに入るのは解析して得た数値（`songs/analysis/`、`work/song_features.csv`）だけです。

## 音源の入手先

ストリーミング（Apple Music、Spotify、YouTube Music、LINE MUSIC、Amazon Music、AWA）の
「ダウンロード」はオフライン再生用の暗号化データで、解析には使えません。
**購入（ダウンロード販売）で買ったファイル**を使います。

| ストア | 形式 | 備考 |
| --- | --- | --- |
| [mora](https://mora.jp/) | FLAC（ハイレゾ配信がある場合）/ AAC | ロスレスがあれば最優先 |
| [amazon](https://www.amazon.co.jp/) デジタルミュージック | MP3 256kbps | ブラウザから素直に落ちる |
| iTunes Store | AAC 256kbps (.m4a) | Mac なら最速 |
| レコチョク | AAC | アプリ前提で PC に取り出しにくいことがある |

各作品の購入先は [`../link.md`](../link.md) の配信リンクから辿れます。

## ファイル名

`[曲名].拡張子` にします。曲名は公式表記のまま（`!` の数や `☆`/`★` を正規化しない）。
このファイル名がそのまま `songs/analysis/[曲名].md` になり、
`songs/lyrics/[曲名].md` と対応します。

```
audio/主人公.flac  ->  songs/analysis/主人公.md
```

## 扱いの注意

- ここに置くのは**購入した音源**か、グループ側から提供された音源だけにします。
- 客席録音のライブ音源は解析対象にしません。
- ステム分離した wav なども同じ扱いです。コミットしないでください。
