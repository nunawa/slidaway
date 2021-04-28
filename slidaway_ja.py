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
    parser = argparse.ArgumentParser(description="Slidaway: Microsoft StreamとZoomのビデオからプレゼンテーションのスライドを抽出して保存するCLIツール")
    
    parser.add_argument("--version", action="version", version="version 0.1.0", help="バージョンを表示します。")
    parser.add_argument("-i", "--interval", default=3, type=int, help="スライドを抽出する際のサンプリング間隔を指定します。(単位: 秒, デフォルト: 3)")
    parser.add_argument("-t", "--threshold", default=5, type=int, help="前フレームとの差がこの値より大きい場合、現フレームが保存されます。この値が負の場合、サンプリングされた全てのフレームが保存されます。(デフォルト: 5)")
    parser.add_argument("-s", "--savedir", default="..", metavar="PATH", help="ファイルを保存するためのディレクトリを設定します。 (デフォルト: ..)")
    #parser.add_argument("--noclean", action="store_true", help="保存先に既に画像がある場合、それらを削除しないようにします。")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-u", "--url", metavar="URL", nargs="+", help="デフォルトのモードです。動画をダウンロードし、プレゼンのスライドを抽出します。対象となるURLを指定してください。")
    group.add_argument("-d", "--download", metavar="URL", nargs="+", help="ダウンロードのみのモードです。")
    group.add_argument("-x", "--extract", metavar="PATH", nargs="+", help="スライド抽出のみのモードです。対象となる動画ファイルのパスを指定してください。")
    
    args = parser.parse_args()

    if args.download:
        print("\nモード: ダウンロード")
        download_video(args.download, args.savedir)
    elif args.extract:
        print("\nモード: スライド抽出")
        frame_to_image(args.extract, args.savedir, args.interval, args.threshold)
    else:
        print("\nモード: デフォルト")
        prev_list = find_video_file(args.savedir)
        download_video(args.url, args.savedir)
        list = find_video_file(args.savedir)
        diff_list = set(list) - set(prev_list)
        frame_to_image(diff_list, args.savedir, args.interval, args.threshold)

def download_video(url_list, save_dir):
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
        download_from_zoom(zoom_url_list, save_dir)
    elif not zoom_url_list:
        download_from_stream(stream_url_list, save_dir)
    else:
        download_from_stream(stream_url_list, save_dir)
        download_from_zoom(zoom_url_list, save_dir)

def download_from_stream(url_list, save_dir):
    print("\nStreamからのダウンロードを開始します\n")

    # urlのリストをtxtで保存
    url = "\n".join(["{}".format(n) for n in url_list])
    with open("url.txt", mode='w') as f:
        f.write(url)

    # txt経由でURL読み込み destreamer使ってダウンロード
    cmd = ["resources\\destreamer.exe", "-f", "url.txt", "-o", save_dir, "-t {title}", "-k"]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print("ダウンロードに失敗しました")
        sys.exit(1)

def download_from_zoom(url_list, save_dir):
    print("\nZoomからのダウンロードを開始します")

    for url in url_list:
        # 動画保存ディレクトリの作成
        #os.makedirs("..\\videos", exist_ok=True)

        # HTTPリクエストしてmp4のURLとCookieを取得
        r = requests.get(url)
        cookie = r.cookies
        mp4_url = re.findall("source src=\"(.*)\" type=\"video/mp4\"", r.text)[0]
        # HTMLから題名・開始時間を取得し、ファイル名に
        meeting_topic = re.findall("class=\"meeting-topic\">\n(.*)\n</span>", r.text)[0]
        start_time = "".join(re.findall("id=\"r_meeting_start_time\" value=\"(.*)(AM|PM)", r.text)[0])
        filename = str(meeting_topic) + "_" + str(start_time).replace(" ", "_").replace(":", "").replace(",", "")

        # 同名ファイルがあったら改名
        path = save_dir + "\\{}.mp4".format(filename)
        uniq = 1
        while os.path.exists(path):
            path = save_dir + "\\{}_{}.mp4".format(filename, uniq)
            uniq += 1
        print("\nファイル名: " + path.replace(save_dir + "\\", ""))

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

def find_video_file(save_dir):
    # 保存先フォルダにmp4かmkvファイルがあるか探す
    video_list = pathlib.Path(save_dir)
    video_list = list([p for p in video_list.glob("**/*")
                            if re.search(".(mp4|mkv)", str(p))])
    return video_list

def frame_to_image(video_list, save_dir, interval, threshold):
    path_video_list = []
    filename_list = []

    for p in video_list:
        # パスとファイル名をそれぞれリストに追加
        path_video_list.append(str(p))
        filename_list.append(os.path.basename(p))

    print("\nスライドの抽出を開始します")

    for (path_video, filename) in zip(path_video_list, filename_list):
        cap = cv2.VideoCapture(path_video)
        # ファイルが開けなかったら終了
        if cap.isOpened() == False:
            print("ファイルを開けません")
            sys.exit(1)

        # 画像保存ディレクトリの作成
        save_dir_modified = save_dir + "\\" + os.path.splitext(filename)[0]
        os.makedirs(save_dir_modified, exist_ok=True)

        # フォルダ内に既に画像があった場合は消す
        png_list = glob.glob(save_dir_modified + "\\*.png")
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
        prev_frame_pil.save(save_dir_modified + "\\{:0=7}.png".format(0))

        for i in tqdm(range(1, int(frame_count), int(step))):
            # 現在位置をi番目のフレームに移動
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            # 動画終了検知
            if cap is None:
                print("cap is \'NoneType\'")
                break
            ret, frame = cap.read()
            # フレームが読み込めなかった時は飛ばす
            if ret == False:
                continue
            frame_pil = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_pil)
            frame_hash = imagehash.phash(frame_pil)
            # ハッシュ値の差をとる
            frame_distance = frame_hash - prev_frame_hash

            if frame_distance > threshold:
                # 現在のフレーム数を取得
                num = cap.get(cv2.CAP_PROP_POS_FRAMES)
                # cv2.imwriteでは日本語ファイルを保存できないので、NumPyで保存
                frame_pil.save(save_dir_modified + "\\{:0=7}.png".format(int(num)))

            prev_frame_hash = frame_hash

        cap.release()
        #フルパス表示にする
        print("抽出完了")


if __name__ == "__main__":
    switch()