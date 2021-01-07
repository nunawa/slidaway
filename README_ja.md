# Slidaway

Microsoft StreamとZoom Cloud Meetingのビデオからプレゼンテーションのスライドを抽出して保存するCLIツール

# 使い方

```bash
> slidaway-ja.exe -h
usage: slidaway-ja.exe [-h] [--version] [-i INTERVAL] [-t THRESHOLD]
                      (-u URL [URL ...] | -d URL [URL ...] | -x)

Slidaway: Microsoft StreamとZoom Cloud Meetingのビデオからプレゼンテーションのスライドを抽出して保存するCLIツール

optional arguments:
  -h, --help            show this help message and exit
  --version             バージョンを表示します。
  -i INTERVAL, --interval INTERVAL
                        スライドを抽出する際のサンプリング間隔を指定します。(単位: 秒, デフォルト: 3)
  -t THRESHOLD, --threshold THRESHOLD
                        前フレームとの差がこの値より大きい場合、現フレームが保存されます。
                        この値が負の場合、サンプリングされた全ての
                        フレームが保存されます。(デフォルト: 5)
  -u URL [URL ...], --url URL [URL ...]
                        デフォルトのモードです。動画をダウンロードし、プレゼンのスライドを抽出します。
                        URLは引用符で囲ってください。(例: "http://example.com/")
  -d URL [URL ...], --download URL [URL ...]
                        ダウンロードのみのモードです。
  -x, --extract         スライド抽出のみのモードです。
```

基本的な使い方：
```bash
slidaway-ja.exe -u "http://example.com/"
```

複数のURLを扱う：
```bash
slidaway-ja.exe -u "http://example.com/" "http://example.com/"
```

サンプリング間隔と閾値を設定する：
```bash
slidaway-ja.exe -i 10 -t 8 -u "http://example.com/"
```

ダウンロードのみ：
```bash
slidaway-ja.exe -d "http://example.com/"
```

スライド抽出のみ：
```bash
slidaway-ja.exe -x
```

# ライセンス

Slidawayは、MITライセンスのもとで公開されています。
