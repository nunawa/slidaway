import argparse
import glob
import os
import pathlib
import re
import subprocess
import sys

import cv2
import imagehash
import requests
from PIL import Image
from tqdm import tqdm


def switch():
    parser = argparse.ArgumentParser(description="Slidaway: Microsoft StreamとZoom Cloud Meetingのビデオからプレゼンテーションのスライドを抽出して保存するCLIツール")
    
    parser.add_argument("--version", action="version", version="version 0.1.0", help="バージョンを表示します。")
    parser.add_argument("-i", "--interval", type=int, help="スライドを抽出する際のサンプリング間隔を指定します。(単位: 秒, デフォルト: 3)")
    parser.add_argument("-t", "--threshold", type=int, help="前フレームとの差がこの値より大きい場合、現フレームが保存されます。この値が負の場合、サンプリングされた全てのフレームが保存されます。(デフォルト: 5)")
    #parser.add_argument("--noclean", action="store_true", help="保存先に既に画像がある場合、それらを削除しないようにします。")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-u", "--url", metavar="URL", nargs="+", help="デフォルトのモードです。動画をダウンロードし、プレゼンのスライドを抽出します。URLは引用符で囲ってください。(例: \"http://example.com/\")")
    group.add_argument("-d", "--download", metavar="URL", nargs="+", help="ダウンロードのみのモードです。")
    group.add_argument("-x", "--extract", action="store_true", help="スライド抽出のみのモードです。")
    
    args = parser.parse_args()

    if args.download:
        print("\nモード: ダウンロード")
        downloadVideo(args.download)
    elif args.extract:
        print("\nモード: スライド抽出")
        frameToImage(args.interval, args.threshold)
    else:
        print("\nモード: デフォルト")
        prev_list = findVideoFile()
        downloadVideo(args.url)
        list = findVideoFile()
        diff_list = set(list) - set(prev_list)
        frameToImage(args.interval, args.threshold, diff_list)

def downloadVideo(url_list):
    stream_url_list = []
    zoom_url_list = []

    for url in url_list:
        if "microsoftstream.com/" in url:
            stream_url_list.append(url)
        elif "zoom.us/" in url:
            zoom_url_list.append(url)

    # streamだけかzoomだけか両方か判定
    if not stream_url_list and not zoom_url_list:
        print("適切なURLが入力されませんでした")
        sys.exit(1)
    elif not stream_url_list:
        downloadFromZoom(zoom_url_list)
    elif not zoom_url_list:
        downloadFromStream(stream_url_list)
    else:
        downloadFromStream(stream_url_list)
        downloadFromZoom(zoom_url_list)

def downloadFromStream(url_list):
    print("\nStreamからのダウンロードを開始します\n")

    # urlのリストをtxtで保存
    url = "\n".join(["{}".format(n) for n in url_list])
    with open("url.txt", mode='w') as f:
        f.write(url)

    # txt経由でURL読み込み destreamer使ってダウンロード
    cmd = ["resources\\destreamer.exe", "-f", "url.txt", "-o", "..\\videos", "-t {title}", "-k"]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print("ダウンロードに失敗しました")
        sys.exit(1)

def downloadFromZoom(url_list):
    print("\nZoomからのダウンロードを開始します")

    for url in url_list:
        # 動画保存ディレクトリの作成
        os.makedirs("..\\videos", exist_ok=True)

        # HTTPリクエストしてmp4のURLとCookieを取得
        r = requests.get(url)
        cookie = r.cookies
        mp4_url = re.findall("source src=\"(.*)\" type=\"video/mp4\"", r.text)[0]
        # HTMLから題名・開始時間を取得し、ファイル名に
        meeting_topic = re.findall("class=\"meeting-topic\">\n(.*)\n</span>", r.text)[0]
        start_time = "".join(re.findall("id=\"r_meeting_start_time\" value=\"(.*)(AM|PM)", r.text)[0])
        filename = str(meeting_topic) + "_" + str(start_time).replace(" ", "_").replace(":", "").replace(",", "")

        # 同名ファイルがあったら改名
        path = "..\\videos\\{}.mp4".format(filename)
        uniq = 1
        while os.path.exists(path):
            path = "..\\videos\\{}_{}.mp4".format(filename, uniq)
            uniq += 1
        print("\nファイル名: " + path.replace("..\\videos\\", ""))

        # ファイルサイズ取得のためヘッダだけリクエスト
        mp4_size = int(requests.head(mp4_url, cookies=cookie, headers={"referer": url}).headers["Content-Length"])
        # プログレスバーの設定
        bar = tqdm(total=mp4_size, unit="B", unit_scale=True)

        # リファラとCookieを設定してmp4のURLにリクエスト
        r2 = requests.get(mp4_url, cookies=cookie, headers={"referer": url}, stream=True)
        # もらったデータを1024Byteずつバイナリで保存
        with open(path, mode='wb') as f:
            for chunk in r2.iter_content(chunk_size=1024):
                f.write(chunk)
                bar.update(len(chunk))
            bar.close()

        print("ダウンロード完了")

def findVideoFile():
    # videosフォルダにmp4かmkvファイルがあるか探す
    video_list = pathlib.Path("..\\videos")
    video_list = list([p for p in video_list.glob("**/*")
                            if re.search(".(mp4|mkv)", str(p))])
    return video_list

def frameToImage(interval, threshold, video_list = None):
    if not interval:
        interval = 3

    if not threshold:
        threshold = 5

    path_video_list = []
    filename_list = []

    if video_list:
        for p in video_list:
            # パスとファイル名をそれぞれリストに追加
            path_video_list.append(str(p))
            filename_list.append(str(p.name))
    else:
        # mp4またはmkvファイルを検索
        video_list = findVideoFile()

        # ファイルがない場合終了
        if not video_list:
            print("\nファイルがありません")
            sys.exit(1)

        print("\nファイルを選択\n（複数入力可、Enterキーを2回押して入力終了）")
        # ファイル一覧表示
        key = 0
        for p in video_list:
            print(str(key) + ": " + p.name)
            key += 1

        while True:
            try:
                select_raw = input(">>")
                if select_raw == "":
                    break
                select = int(select_raw)
                # 選択されたファイルのパス・ファイル名をリストに追加
                path_video_list.append(str(video_list[select]))
                filename_list.append(str(video_list[select].name))
            except ValueError:
                print("整数を入力してください")
            except IndexError:
                print("入力された数値が間違っています")

        if not path_video_list:
            print("ファイルが選択されませんでした")
            sys.exit()

    print("\nスライドの抽出を開始します")

    for (path_video, filename) in zip(path_video_list, filename_list):
        cap = cv2.VideoCapture(path_video)
        # ファイルが開けなかったら終了
        if cap.isOpened() == False:
            print("ファイルを開けません")
            sys.exit(1)

        # 画像保存ディレクトリの作成
        os.makedirs("..\\pictures\\" + filename, exist_ok=True)

        # フォルダ内に既に画像があった場合は消す
        png_list = glob.glob("..\\pictures\\" + filename + "\\*.png")
        if png_list:
            for png in png_list:
                os.remove(png)

        # 総フレーム数
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        # fps
        fps = cap.get(cv2.CAP_PROP_FPS)
        print("\nファイル名: {}\n総フレーム数: {}\nFPS: {}".format(filename, frame_count, fps))
        # 3秒間隔にする
        step = fps * interval

        # フレームの取得
        ret, prev_frame = cap.read()
        # OpenCVをPillowに
        prev_frame_pil = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2RGB)
        prev_frame_pil = Image.fromarray(prev_frame_pil)
        # ハッシュ値を計算
        prev_frame_hash = imagehash.phash(prev_frame_pil)
        # PNG画像として書き出し
        prev_frame_pil.save("..\\pictures\\{}\\{:0=7}.png".format(filename, 0))

        for i in tqdm(range(1, int(frame_count), int(step))):
            # 現在位置をi番目のフレームに移動
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            # 動画終了検知
            if cap is None:
                print("cap is \'NoneType\'")
                break
            ret, frame = cap.read()
            frame_pil = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_pil)
            frame_hash = imagehash.phash(frame_pil)
            # ハッシュ値の差をとる
            frame_distance = frame_hash - prev_frame_hash

            if frame_distance > threshold:
                # 現在のフレーム数を取得
                num = cap.get(cv2.CAP_PROP_POS_FRAMES)
                # cv2.imwriteでは日本語ファイルを保存できないので、numpyで保存
                frame_pil.save("..\\pictures\\{}\\{:0=7}.png".format(filename, int(num)))

            prev_frame_hash = frame_hash

        cap.release()
        print("抽出完了")


if __name__ == "__main__":
    switch()