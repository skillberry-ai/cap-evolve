#!/usr/bin/env bash
# Assemble the cap-evolve demo video from the recorded terminal segments + cards.
# One re-encode at the end; every segment is normalised to the same size/fps/pix_fmt
# first, because concat demuxer stream-copies and silently corrupts on a mismatch.
set -euo pipefail
cd /tmp/video

W=2560; H=1340; FPS=25
V="-c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -r $FPS"
norm="scale=$W:$H:force_original_aspect_ratio=decrease,pad=$W:$H:(ow-iw)/2:(oh-ih)/2:color=0x0b0d17,fps=$FPS,format=yuv420p,setsar=1"

card () {  # card <png> <seconds> <out> — fade in/out so cuts don't jar
  local d="$2"
  ffmpeg -v error -loop 1 -i "$1" -t "$d" \
    -vf "$norm,fade=t=in:st=0:d=0.35,fade=t=out:st=$(echo "$d-0.35" | bc):d=0.35" \
    $V -an "$3" -y
}

clip () {  # clip <mp4> <trim_seconds> <out>
  ffmpeg -v error -i "$1" -t "$2" \
    -vf "$norm,fade=t=in:st=0:d=0.3,fade=t=out:st=$(echo "$2-0.4" | bc):d=0.4" \
    $V -an "$3" -y
}

echo "1/4  cards"
card cards/00_title.png    4.5 p0.mp4
card cards/01_replay.png   3.0 p1.mp4
card cards/02_parallel.png 3.2 p3.mp4
card cards/03_speedup.png  4.5 p5.mp4
card cards/04_honest.png   6.0 p6.mp4

echo "2/4  terminal segments"
clip replay.mp4   28.5 p2.mp4
clip parallel.mp4 12.5 p4.mp4

echo "3/4  concat"
: > list.txt
for f in p0 p1 p2 p3 p4 p5 p6; do echo "file '$PWD/$f.mp4'" >> list.txt; done
ffmpeg -v error -f concat -safe 0 -i list.txt -c copy cap-evolve-demo.mp4 -y

echo "4/4  done"
ffprobe -v error -show_entries stream=width,height,r_frame_rate,nb_frames \
        -show_entries format=duration,size -of default=nw=1 cap-evolve-demo.mp4
du -h cap-evolve-demo.mp4
