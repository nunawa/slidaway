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
    parser = argparse.ArgumentParser(description="Slidaway: Extract and save presentation slides from Microsoft Stream or Zoom Cloud Meeting videos")
    
    parser.add_argument("--version", action="version", version="version 0.1.0", help="Show version.")
    parser.add_argument("-i", "--interval", type=int, help="Sampling interval when extracting an image. (in seconds, default: 3)")
    parser.add_argument("-t", "--threshold", type=int, help="If the difference compared to the previous frame is greater than this value, the current frame is saved. If this value is negative, all sampled frames will be saved. (default: 5)")
    #parser.add_argument("--noclean", action="store_true", help="If there are already images in the destination, they will not be deleted.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-u", "--url", metavar="URL", nargs="+", help="Default mode. Download the video and extract the presentation slides. Enclose the URL in quotation marks. (like \"http://example.com/\")")
    group.add_argument("-d", "--download", metavar="URL", nargs="+", help="Download only mode.")
    group.add_argument("-x", "--extract", action="store_true", help="Extract only mode.")
    
    args = parser.parse_args()

    if args.download:
        print("\nMode: Download")
        downloadVideo(args.download)
    elif args.extract:
        print("\nMode: Extract")
        frameToImage(args.interval, args.threshold)
    else:
        print("\nMode: Default")
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
        print("The proper URL was not entered")
        sys.exit(1)
    elif not stream_url_list:
        downloadFromZoom(zoom_url_list)
    elif not zoom_url_list:
        downloadFromStream(stream_url_list)
    else:
        downloadFromStream(stream_url_list)
        downloadFromZoom(zoom_url_list)

def downloadFromStream(url_list):
    print("\nStart downloading from Stream")

    # urlのリストをtxtで保存
    url = "\n".join(["{}".format(n) for n in url_list])
    with open("url.txt", mode='w') as f:
        f.write(url)

    # txt経由でURL読み込み destreamer使ってダウンロード
    cmd = ["resources\\destreamer.exe", "-f", "url.txt", "-o", "..\\videos", "-t {title}", "-k"]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print("Download failed")
        sys.exit(1)

def downloadFromZoom(url_list):
    print("\nStart downloading from Zoom")

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

        print("Download finished")

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
            print("\nFile not found")
            sys.exit(1)

        print("\nSelect files\n（Multiple entries allowed, Press Enter twice to finish typing）")
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
                print("Please enter an integer")
            except IndexError:
                print("The value you entered is incorrect")

        if not path_video_list:
            print("No file selected")
            sys.exit()

    print("\nStart extracting the slides")

    for (path_video, filename) in zip(path_video_list, filename_list):
        cap = cv2.VideoCapture(path_video)
        # ファイルが開けなかったら終了
        if cap.isOpened() == False:
            print("Can't open file")
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
        print("\nFile name: {}\nTotal number of frames: {}\nFPS: {}".format(filename, frame_count, fps))
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
        print("Extraction finished")


if __name__ == "__main__":
    switch()