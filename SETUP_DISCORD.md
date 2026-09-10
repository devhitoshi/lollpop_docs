# Discord 経由でこのリポジトリの制作を回す（OpenACP セットアップ手順）

Discord のスレッドから Claude Code に指示を出し、記事・動画を作らせるための設定手順。
**認証情報（Bot トークン・チャンネル ID・ユーザー ID）を手に入れたあと、オーナーが上から順に実行する。**

構成は次のとおり。

```
利用者3名（スマホの Discord）
  ↓ スレッド 1本 = セッション 1本
OpenACP（このPCで常駐するブリッジ）
  ↓
Claude Code（認証済み）
  ↓
lollpop_docs / Google Drive
```

**済んでいること**（2026-09-10 時点。やり直し不要）

- Node.js v24.12.0（要件は 20 以上）
- `npm install -g @openacp/cli` → `2026.518.2`
- `gh` 認証済み・`gh browse` 動作確認済み
- タスクスケジューラに `OpenACP` を**無効の状態で**登録済み（手順5で有効化する）
- リポジトリ側の準備（`CLAUDE.md` の Discord 節、`video-production` スキル、`.gitignore`、force push / main 直接 push の防止）

**これからやること** = 手順1〜7。

---

## 0. 先に決めておくこと — workspace はリポジトリの外に置く

OpenACP の「workspace」は、**設定ファイルと Bot トークンの置き場**でもある。
`<workspace>/.openacp/` が作られ、その中の `config.json` と `plugins/data/` にトークンが**平文で**入る。

そのため **workspace には `C:\Users\kawad\work` を指定する。** リポジトリ（`work\projects\lollpop_docs`）を
指定すると、トークンがリポジトリの中に落ちる。`work` は git リポジトリではないので、この事故が起きない。

セッションを作るときに `projects/lollpop_docs` と相対名で指定できるので、使い勝手も落ちない。

> 保険として `.openacp/` はこのリポジトリの `.gitignore` と `guard_git.py` の禁止パターンの両方に入れてあるが、
> そもそも外に置くのが正しい。

---

## 1. Discord Bot を作る

### 1-1. アプリケーションと Bot

1. https://discord.com/developers/applications → **New Application**。名前は何でもよい（例: `lollpop-bridge`）
2. 左メニュー **Bot** → **Reset Token** → 表示されたトークンをコピーする
   - **Discord はトークンを一度しか表示しない。**この場では**チャットに貼らず**、パスワードマネージャか手元のメモに置く
3. 同じ **Bot** の画面で **Privileged Gateway Intents** の **MESSAGE CONTENT INTENT** を **ON** にして保存する
   - OpenACP の Discord アダプタは `Guilds` / `GuildMessages` / `MessageContent` の3つを要求する。
     前2つは既定で有効だが、**MessageContent だけは手動で ON にしないと本文が空で届く**

### 1-2. サーバーに招待する

**OAuth2 → URL Generator** で、

- **SCOPES**: `bot` と `applications.commands`
- **BOT PERMISSIONS**: Manage Channels / Send Messages / Create Public Threads / Manage Threads /
  Manage Messages / Embed Links / Attach Files / Read Message History / Use Slash Commands / Add Reactions

生成された URL を開き、サーバーを選んで承認する。
権限を手で組むなら、権限整数 **`328565073936`** を使って次の形でもよい。

```
https://discord.com/api/oauth2/authorize?client_id=<APPLICATION_ID>&permissions=328565073936&scope=bot%20applications.commands
```

`Manage Channels` が要るのは、OpenACP が起動時に `#openacp-sessions`（フォーラム）と
`#openacp-notifications`（テキスト）を**自分で作る**ため。

---

## 2. サーバー ID・チャンネル ID・ユーザー ID を取る

Discord の **ユーザー設定 → 詳細設定 → 開発者モード** を ON にする。以後、右クリック（スマホは長押し）のメニューに「ID をコピー」が出る。

| 何の ID | 取り方 | 使い道 |
| --- | --- | --- |
| **サーバー ID（guild ID）** | サーバー名を右クリック → **サーバー ID をコピー** | 手順3で入力。必須 |
| **ユーザー ID** | メンバー一覧で本人を右クリック → **ユーザー ID をコピー**（3名分） | 手順4の `allowedUserIds`。必須 |
| **チャンネル ID** | チャンネル名を右クリック → **チャンネル ID をコピー** | 既存チャンネルを使いたいときだけ。自動作成に任せるなら不要 |

いずれも 17〜20 桁の数字（snowflake）。3名には**自分のユーザー ID を送ってもらう**（開発者モードを ON にしてもらう必要がある）。

---

## 3. `openacp` ウィザードを走らせる

**PowerShell で workspace のディレクトリに移動してから**実行する。ウィザードは「実行した場所」を workspace にする。

```powershell
cd C:\Users\kawad\work
openacp
```

聞かれる項目と答え。

| 項目 | 答え |
| --- | --- |
| Choose your platform | **Discord** |
| Bot token | 手順1-1 でコピーしたトークンを**貼り付ける** |
| Guild ID | 手順2 のサーバー ID |
| Workspace directory | `C:\Users\kawad\work`（既定のまま／今いる場所） |
| Default AI agent | **Claude Code** |
| Run mode | **daemon** |
| Auto-start on boot | **No**（Windows では効かない。手順5のタスクスケジューラで代替する） |

終わると `C:\Users\kawad\work\.openacp\` ができる。チャンネル ID は `null` のままでよく、
初回起動時に OpenACP がフォーラムチャンネルを作って自分で書き戻す。

---

## 4. 設定を詰める

### 4-1. 利用者を3名に限定する（**必須**）

`allowedUserIds` が空配列だと、**サーバーにいる全員がこの PC 上で Claude Code を動かせる。**

```powershell
openacp plugin configure @openacp/security --dir C:\Users\kawad\work
```

メニューから **Edit allowed user IDs** を選び、手順2で集めた3名のユーザー ID を入れる。
同じメニューで **Session timeout minutes** も設定できる。

> **`openacp config` → Security のメニューには「allowed user IDs」の項目が無い**（表示はされるが編集できない）。
> 上の `plugin configure` を使うこと。パッケージ本体のコードで確認済み。

### 4-2. セッションのタイムアウトを延ばす

既定は 60 分。台本を投げてから数時間後にレビューが返る運用だと、その間にセッションが切れる。
**720 分（12時間）〜 1440 分（24時間）**を目安にする。手順4-1 と同じメニューの **Session timeout minutes** で設定する。

設定の実体は次のファイル。直接編集してもよい（その場合は `openacp restart`）。

```
C:\Users\kawad\work\.openacp\plugins\data\@openacp\security\settings.json
```

```json
{
  "allowedUserIds": ["<利用者1のID>", "<利用者2のID>", "<利用者3のID>"],
  "maxConcurrentSessions": 20,
  "sessionTimeoutMinutes": 1440
}
```

> **注意。**ドキュメントには `config.json` の `security` ブロックに書くとあるが、**このファイルが存在する場合はこちらが優先される**
> （プラグインの `install()` が起動時にこのファイルを作るので、実質常にこちらが勝つ）。
> `config.json` 側だけに書くと**黙って無視され、全員が使える状態のまま**になる。必ずこのファイルで確認すること。

### 4-3. 自動承認ルール — **OpenACP 側に粒度のある設定は無い**

調べた結果を正直に書く。**OpenACP が持つ自動承認の仕組みは、セッション単位の `/bypass_permissions` on/off だけ**で、
「読み取りは自動承認、書き込みは承認要求」のような区別はできない。`autoApprovedCommands` というグロブ設定は
存在するがプラグインのマニフェスト項目で、設定ファイルからは書けない。

**そして、何も設定しない既定の状態が、まさに求めている挙動になっている。**

| 操作 | 既定の挙動 |
| --- | --- |
| ファイルの読み取り・検索（Read / Grep / Glob） | 承認不要。無言で進む |
| シェルコマンド（Bash） | **Discord に承認ボタンが出る** |
| ファイルの書き込み・編集（Write / Edit） | **Discord に承認ボタンが出る** |

これは Claude Code 側の既定（manual モード）による区別で、OpenACP はその承認要求をボタンに変換しているだけ。
**したがって設定作業は「`/bypass_permissions` を ON にしないこと」だけ。**

> 承認待ちは **10 分で自動的に拒否**される。スマホを見ていない時間が長い運用なので、
> 「反応が無いまま止まっていた」ときはこれを疑う。

### 4-4. ボットが反応する範囲を絞る

**チャンネルを名指しで限定する設定キーは存在しない。**実装上こうなっている（アダプタのコードで確認済み）。

- **DM は無視する**
- **設定した guild 以外は無視する**
- **スレッドの中のメッセージしか処理しない**（通常のチャンネル投稿には反応しない）

セッションは `forumChannelId` に指定したフォーラムチャンネルにスレッドとして作られるので、
**「そのフォーラムチャンネル1つに閉じる」のが実質の限定手段**になる。
自動作成された `#openacp-sessions` をそのまま使い、そのチャンネルの閲覧権限を3名に絞れば、範囲は閉じる。

ユーザー単位の制限（4-1）は全チャンネル横断でかかるので、**実効的な防御はそちら**。

### 4-5. 設定一覧を見て、他に調整すべき項目がないか

```powershell
openacp config --dir C:\Users\kawad\work
```

対話エディタのセクションは **Channels / Agent / Workspace / Security / Logging / Run Mode / API / Tunnel**。
非対話で1つだけ変えるなら `openacp config set <key> <value>`（例: `openacp config set defaultAgent claude`）。

一覧を見たうえで、この運用で触る価値があるのは次の3つ。

| 項目 | 推奨 | 理由 |
| --- | --- | --- |
| `outputMode` | `medium`（既定）。うるさければ `low` | ツール実行のカードをどこまで出すか。スマホだと `high` は流れが速すぎる |
| `tunnel.enabled` | **`false` のまま** | 有効にすると差分を Monaco で見る URL が出るが、**ローカルのファイルを外部に公開する**ことになる。本文はチャットに貼る運用なので不要 |
| `logging.level` | `info`（既定） | 詰まったときだけ `debug` |

**セッション開始時に固定のプロンプトを注入する設定は存在しない。**
`initialPrompt` / `systemPrompt` / `customInstructions` に類するキーをパッケージ本体で検索したが、該当なし。
**リポジトリの `CLAUDE.md` が唯一の常時ルールの入口**になる（Discord 節を追記済み）。

### 4-6. Google ドライブのフォルダを3名と共有する

動画はリポジトリに入れず、`G:\マイドライブ\claude-work\<yyyymmdd>_<タスク名>\` に置いて
`https://drive.google.com/file/d/<fileId>/view` の URL を返す運用にしている（`.claude/skills/video-production`）。

**この URL は、そのファイルへのアクセス権がある人にしか開けない。**
`claude-work` フォルダを一度だけ3名の Google アカウントと共有しておく。

1. ブラウザで Google ドライブ → **マイドライブ → claude-work** を右クリック → **共有**
2. 3名の Google アカウント（Discord のアカウントとは別物。メールアドレスを聞く）を追加し、権限は **閲覧者**
3. 「リンクを知っている全員」には**しない**（動画は公開前の素材を含む）

以後、このフォルダの下に置いたファイルは自動的に3名から見える。共有し忘れると、
URL は返るのに利用者側で「アクセス権が必要です」になる。

---

## 5. 常駐させる（systemd の代わりにタスクスケジューラ）

**OpenACP は Windows での daemon 自動起動を公式にサポートしていない**（README の Known Limitations に明記）。
systemd の user service は macOS の LaunchAgent / Linux の systemd 用で、この PC では作れない。
代わりに**タスクスケジューラに登録済み**なので、有効化するだけでよい。

まず手動で起動して、設定が通っているか確かめる。

```powershell
cd C:\Users\kawad\work
openacp start
openacp status
openacp logs        # Ctrl+C で抜ける
```

Discord のサーバーに `#openacp-sessions` と `#openacp-notifications` ができていれば成功。

動いたらログオン時の自動起動を有効にする。

```powershell
Enable-ScheduledTask -TaskName "OpenACP"
Get-ScheduledTask -TaskName "OpenACP" | Select-Object TaskName, State
```

登録内容は「ログオンの30秒後に `node <openacp>/dist/cli.js start` を `C:\Users\kawad\work` で実行」。
止めるときは `Disable-ScheduledTask -TaskName "OpenACP"`、消すときは `Unregister-ScheduledTask -TaskName "OpenACP"`。

その他のコマンド。

```powershell
openacp stop         # 止める
openacp restart      # 設定を変えたあと
openacp doctor       # 診断
```

### 残ったワークツリーの掃除

スレッドごとに `.claude/worktrees/<種別>/<日付>-<スラッグ>/` が作られる（3人が同時に別の作業を
しても、互いの作業ディレクトリを奪わないようにするため）。完了時に Claude が畳むが、
**セッションが落ちた分は残る。**Discord 経由のセッションは終了時の後始末を促されない仕様なので、
ときどき見る。

```powershell
cd C:\Users\kawad\work\projects\lollpop_docs
git worktree list                       # 残っているものを確認
git worktree remove .claude/worktrees/<パス>
git worktree prune                      # ディレクトリだけ消えた登録を掃除
```

作業中のワークツリーには git のロックがかかっていて `remove` が拒否されることがある。
その場合は `git worktree unlock <パス>` を先に実行する。未コミットの変更が残っているときは
中身を確認してから `--force` を付ける（**中身ごと消える**）。

---

## 6. 動作確認チェックリスト

上から順に。**手順4-1（利用者の限定）が効いているかの確認を飛ばさない。**

- [ ] **指定チャンネルのスレッドで応答が返る**
      `#openacp-sessions` で `/new claude projects/lollpop_docs` → スレッドが立つ → 「このリポジトリの README を要約して」で返事が来る
- [ ] **許可していないユーザーが弾かれる**
      3名以外のアカウント（自分の別アカウントでよい）でスレッドに書き込む → **無反応**が正しい
      （拒否メッセージは出ず、黙って捨てられる仕様）。反応が返ってきたら手順4-2 の注意を読み直す
- [ ] **2つのスレッドが別のディレクトリで動く**
      2本スレッドを立て、それぞれで「いまどこで作業してる？」と聞く →
      `.claude/worktrees/` 配下の**別々のパス**が返るのが正しい。同じパスなら worktree が効いていない
- [ ] **2つのスレッドで文脈が混ざらない**
      スレッドAで「合言葉はカレー」、スレッドBで「合言葉は何？」→ **Bが答えられない**のが正しい
- [ ] **画像の添付が認識される**
      スレッドに画像を貼って「これは何が写ってる？」。アダプタに添付のダウンロード実装があるので動くはず。
      **動かなくても支障はない**（素材はパスか Drive 上の名前で指定する運用）
- [ ] **Drive の共有が効いている**
      手順4-6 で共有したアカウントで `https://drive.google.com/drive/my-drive` を開き、`claude-work` が見えるか
- [ ] **`gh browse` で URL が取れる**
      「CLAUDE.md の GitHub URL を教えて」→ `https://github.com/devhitoshi/lollpop_docs/tree/<branch>/CLAUDE.md` 形式が返る
- [ ] **ブランチが切られ、コミットに依頼者が入る**
      「テスト用のメモを作って」→ 最初の応答で `<video|article|review>/<YYYYMMDD>-<スラッグ>` が示され、
      `git log -1` の末尾に `requested-by: @<表示名>` が入っている
- [ ] **main が守られている**
      「main に直接 push して」→ フックが日本語の理由付きで止める（GitHub 側のルールセットでも弾かれる）
- [ ] **放置後に会話が再開できる**
      スレッドを1〜2時間放置してから続きを書く → 文脈を保ったまま返る。
      切れていたら `sessionTimeoutMinutes`（手順4-2）が反映されていない
- [ ] **PC 再起動後に自動で立ち上がる**
      再起動 → 1分ほど待って Discord から `/status`

**起動しないとき。**

```powershell
openacp status                          # 動いているか・PID
openacp logs                            # ライブでログを追う
openacp doctor                          # 設定と依存の診断
Get-Content C:\Users\kawad\work\.openacp\logs\openacp.log -Tail 50
Get-ScheduledTaskInfo -TaskName "OpenACP"   # LastRunTime と LastTaskResult（0 以外は失敗）
```

詳しく見たいときは `$env:OPENACP_DEBUG = "true"` を立ててから `openacp restart`。
セッションごとのログは `C:\Users\kawad\work\.openacp\logs\sessions\`。

---

## 7. Bot トークンをリポジトリに入れないための確認

トークンは次の2か所に**平文で**入る。どちらも `C:\Users\kawad\work\.openacp\` の下、
つまり**どの git リポジトリの中でもない**（手順0）。

```
C:\Users\kawad\work\.openacp\config.json
C:\Users\kawad\work\.openacp\plugins\data\@openacp\discord-adapter\settings.json
```

確認すること。

- [ ] `C:\Users\kawad\work` が git リポジトリでない
      → `git -C C:\Users\kawad\work rev-parse --show-toplevel` が `not a git repository` になる（確認済み）
- [ ] このリポジトリの中に `.openacp` が無い
      → `git ls-files | Select-String openacp` が空
- [ ] 保険が効いている
      → `.gitignore` に `.openacp/` があり、`guard_git.py` の禁止パターンにも入っている（設定済み）
- [ ] **トークンをチャットに貼らない。**Claude にも、Discord にも、Issue にも書かない。
      漏れたと思ったら Developer Portal で **Reset Token** し、手順4-1 と同じ `plugin configure` で入れ直す
- [ ] トークンを渡す先は Discord Developer Portal と、このPCの設定ファイルだけ

`.env`（twitterapi.io のキー）と同じ扱い。`guard_git.py` は `.env` を含むコミットも止める。

---

## 補足: もっと厳密に分けたい場合の移行先

Discord 経由のセッションだけに制限をかけたい（ターミナルからの直接利用には影響させたくない）場合、
**Discord 専用の git worktree を用意して、そこを OpenACP の workspace に指定する**方法がある。
`git worktree add C:\Users\kawad\work\lollpop_discord <ブランチ>` で作業ツリーを分け、その中の
`.claude/settings.local.json`（`.gitignore` 済みで git 管理外）に `permissions` の `allow` / `ask` / `deny` を書けば、
**その worktree で動くセッションにだけ**制限がかかり、`projects\lollpop_docs` で直接起動したときには一切効かない。
リポジトリにコミットされる `.claude/settings.json` を汚さずに、Discord 経由だけを絞れるのが利点。
いまの構成（制限を書かず、Claude Code の既定の承認要求をそのまま Discord のボタンに出す）で不足を感じたら、この形に移す。
