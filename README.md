# Slidaway

CLI tool to extract and save presentation slides from Microsoft Stream and Zoom Cloud Meeting videos.

# Usage

```bash
> slidaway.exe -h
usage: slidaway.py [-h] [--version] [-i INTERVAL] [-t THRESHOLD] (-u URL [URL ...] | -d URL [URL ...] | -x)

Slidaway: Extract and save presentation slides from Microsoft Stream or Zoom Cloud Meeting videos

optional arguments:
  -h, --help            show this help message and exit
  --version             Show version.
  -i INTERVAL, --interval INTERVAL
                        Sampling interval when extracting an image. (in seconds, default: 3)
  -t THRESHOLD, --threshold THRESHOLD
                        If the difference compared to the previous frame is greater than 
                        this value, the current frame is saved. 
                        If this value is negative, all sampled frames will be saved. (default: 5)
  -u URL [URL ...], --url URL [URL ...]
                        Default mode. Download the video and extract the presentation slides. 
                        Enclose the URL in quotation marks. (like "http://example.com/")
  -d URL [URL ...], --download URL [URL ...]
                        Download only mode.
  -x, --extract         Extract only mode.
```

Basic usage:
```bash
slidaway.exe -u "http://example.com/"
```

Handle multiple URLs:
```bash
slidaway.exe -u "http://example.com/" "http://example.com/"
```

Set sampling interval and threshold:
```bash
slidaway.exe -i 10 -t 8 -u "http://example.com/"
```

Download only:
```bash
slidaway.exe -d "http://example.com/"
```

Extraction only:
```bash
slidaway.exe -x
```

# License

Slidaway is licensed under the MIT license.
