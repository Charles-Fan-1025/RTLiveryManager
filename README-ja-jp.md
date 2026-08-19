# Running Train Livery Manager

**走ル列車 | Running Train** 向けの塗装管理ツールです。

![デモ](./image_assets/livery_management.png)

## 機能

- 塗装管理
  - 車両形式ごとに5つ以上の塗装を管理
  - 塗装のインポート、エクスポート、編集、削除
  - ライブラリからゲームスロットへ塗装を書き込み
- 塗装編集補助
  - ゲームが提供する空白の塗装テンプレートを正しいアスペクト比に変換（他のツールで編集する際に歪みを気にする必要がありません）
  - 編集した塗装ファイルを元のサイズに復元

## ユーザーマニュアル

[ユーザーマニュアル](https://github.com/Charles-Fan-1025/RTLiveryManager/blob/master/manual-ja-jp.md) をご参照ください。

## ディレクトリ構成

- `FrontEnd.py`：GUI エントリポイント
- `FileManage.py`：塗装ライブラリおよびゲームファイル管理のバックエンド
- `ImageProcess.py`：画像処理のバックエンド
- `SteamInteract.py`：Steam API 連携のバックエンド

## アプリケーションの実行

[Releases](https://github.com/Charles-Fan-1025/RTLiveryManager/releases) から実行可能ファイルを直接ダウンロードするか、Python（Pillow が必要）で実行します。

GUI を直接起動するには：

```powershell
python FrontEnd.py
```

画像処理モジュールはコマンドラインからの呼び出しにも対応しています。python ImageProcess.py -h でヘルプを表示できます。

## データパス
本ソフトウェアは C://Users/<ユーザー名>/Documents/RunningTrainLivery/ にデータを保存します。

## AI支援に関する宣言
本ソフトウェアはAIコーディングツールの支援を受けて開発されました。