"""从视频中抽取关键帧，作为知识块的候选案例图。需要系统已安装 ffmpeg。

用法：python extract_frames.py 视频.mp4 输出目录 [--threshold 0.3] [--max 60]
文件名包含时间码（秒），方便在“出处”中引用。
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--threshold", type=float, default=0.3, help="场景变化阈值，越小抽得越多")
    ap.add_argument("--max", type=int, default=60)
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        print("未找到 ffmpeg，请先安装并加入 PATH", file=sys.stderr)
        return 1
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_f%05d.jpg"
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", a.video, "-vf", f"select='gt(scene,{a.threshold})',showinfo",
         "-vsync", "vfr", "-frames:v", str(a.max), "-q:v", "3", str(tmp)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    times = re.findall(r"pts_time:([\d.]+)", r.stderr)
    frames = sorted(out.glob("_f*.jpg"))
    for f, t in zip(frames, times):
        f.rename(out / f"frame_{int(float(t)):06d}s.jpg")
    print(f"抽取 {len(frames)} 帧 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
