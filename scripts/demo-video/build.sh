#!/usr/bin/env bash
# Assemble the cap-evolve demo video: cards + terminal + dashboard + VO + captions.
#
#   bash scripts/demo-video/build.sh            # full build, fails on any missing input
#   ANIMATIC=1 bash scripts/demo-video/build.sh # allow stand-in footage, stamp it as such
#
# Every segment is normalised to the same size/fps/pix_fmt BEFORE concat, because
# the concat demuxer stream-copies and silently corrupts on a mismatch.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
V=/tmp/video
PY=${PY:-/tmp/vidvenv/bin/python}
ANIMATIC=${ANIMATIC:-0}
OUTNAME=${OUTNAME:-cap-evolve-demo.mp4}
# Where in the long terminal/dashboard recordings the useful window starts.
TERM_SEEK=${TERM_SEEK:-7.7}   # lands the 13.7s window on the finished lineage
DASH_SEEK=${DASH_SEEK:-1.6}   # past first paint, into the headline tiles
PAR_SEEK=${PAR_SEEK:-13.5}  # where workers=8 lands and the identical-SplitResult line prints

die () { echo "FATAL: $*" >&2; exit 1; }
have () { [ -s "$1" ]; }

[ -x "$PY" ] || die "$PY missing. python3 -m venv /tmp/vidvenv && /tmp/vidvenv/bin/pip install Pillow playwright"
command -v ffmpeg >/dev/null || die "ffmpeg not on PATH"
mkdir -p "$V"

# ── 1. the speedup card must come from the run the camera filmed ──────────
# parallel.tape runs par_demo.py, which writes par_results.json; vhs then writes
# parallel.mp4. So for one-and-the-same run the json is always OLDER than the
# mp4. A json that is NEWER means someone ran par_demo.py standalone afterwards,
# and the card would quote numbers the footage never showed. Refuse that.
echo "1/6  checking the measurement matches its footage"
have "$V/par_results.json" || die "no $V/par_results.json — record it:
  vhs scripts/demo-video/parallel.tape   (this both films and measures)"
have "$V/parallel.mp4" || die "no $V/parallel.mp4 — vhs scripts/demo-video/parallel.tape"
if [ "$V/par_results.json" -nt "$V/parallel.mp4" ]; then
  die "par_results.json is newer than parallel.mp4 — the speedup card would
quote a different run than the footage shows. Re-record both together:
  vhs scripts/demo-video/parallel.tape"
fi
"$PY" -c "
import json; r = json.load(open('$V/par_results.json'))
assert r['identical'], 'par_demo reported a DIVERGED SplitResult — do not ship'
print('     ', {k: v['wallclock'] for k, v in r['runs'].items()}, 'identical=True')
" || die "par_results.json is unusable"

# ── 2. cards + voiceover + manifest ───────────────────────────────────────
echo "2/6  cards + voiceover"
"$PY" "$HERE/assets.py" || die "assets.py failed"
have "$V/shots.json" || die "assets.py did not write shots.json"

W=$($PY -c "import json;print(json.load(open('$V/shots.json'))['w'])")
H=$($PY -c "import json;print(json.load(open('$V/shots.json'))['h'])")
FPS=$($PY -c "import json;print(json.load(open('$V/shots.json'))['fps'])")
TOTAL=$($PY -c "import json;print(json.load(open('$V/shots.json'))['total'])")

VENC="-c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p -r $FPS"
NORM="scale=$W:$H:force_original_aspect_ratio=decrease,pad=$W:$H:(ow-iw)/2:(oh-ih)/2:color=0x0b0d17,fps=$FPS,format=yuv420p,setsar=1"

# ── 3. footage inputs must exist ──────────────────────────────────────────
echo "3/6  checking footage"
missing=0
for f in replay dashboard parallel; do
  if have "$V/$f.mp4"; then
    printf '     %-10s %s\n' "$f" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V/$f.mp4")s"
  else
    printf '     %-10s MISSING\n' "$f"; missing=1
  fi
done
if [ "$missing" = 1 ]; then
  cat >&2 <<'EOF'
FATAL: a footage segment is missing. Record it, then re-run:
  vhs scripts/demo-video/replay.tape                # -> /tmp/video/replay.mp4
  vhs scripts/demo-video/parallel.tape              # -> /tmp/video/parallel.mp4
  /tmp/vidvenv/bin/python scripts/demo-video/dash.py  # -> /tmp/video/dashboard.mp4
Refusing to ship a short video with a segment silently dropped.
EOF
  exit 1
fi

# ── 4. one clip per shot ──────────────────────────────────────────────────
echo "4/6  rendering shots"
rm -f "$V"/seg_*.mp4 "$V"/list.txt "$V"/alist.txt
n=0
while IFS=$'\t' read -r id kind dur src; do
  seg="$V/seg_$(printf '%02d' $n)_$id.mp4"
  fin=$(echo "$dur - 0.35" | bc)
  case "$kind" in
    card)
      if [ "$id" = logo ]; then
        # the opener is a real frame sequence, not a still
        ffmpeg -nostdin -v error -framerate "$FPS" -i "$V/logo/%04d.jpg" -t "$dur" \
          -vf "$NORM,fade=t=out:st=$fin:d=0.35" $VENC -an "$seg" -y
      else
        # Held still, deliberately: a push-in on a text card forces a full
        # re-encode of every frame and cost ~2 MB per shot. The fade at each
        # cut is the motion; the animated opener and the live footage are where
        # movement earns its bitrate.
        ffmpeg -nostdin -v error -loop 1 -i "$V/cards/$id.png" -t "$dur" \
          -vf "$NORM,fade=t=in:st=0:d=0.3,fade=t=out:st=$fin:d=0.3" \
          $VENC -an "$seg" -y
      fi
      ;;
    footage)
      case "$src" in
        terminal)  in_mp4="$V/replay.mp4";    seek=$TERM_SEEK ;;
        dashboard) in_mp4="$V/dashboard.mp4"; seek=$DASH_SEEK ;;
        *)         in_mp4="$V/parallel.mp4";  seek=$PAR_SEEK ;;
      esac
      ffmpeg -nostdin -v error -ss "$seek" -i "$in_mp4" -i "$V/lower/$id.png" -t "$dur" \
        -filter_complex "[0:v]$NORM[b];[b][1:v]overlay=0:H-h:format=auto[o];[o]fade=t=in:st=0:d=0.3,fade=t=out:st=$fin:d=0.35[v]" \
        -map "[v]" $VENC -an "$seg" -y \
        || die "could not render footage shot '$id' from $in_mp4 (is it shorter than ${seek}s+${dur}s?)"
      ;;
    *) die "unknown shot kind '$kind'" ;;
  esac
  have "$seg" || die "shot '$id' produced no output"
  echo "file '$seg'" >> "$V/list.txt"
  printf '     %-10s %-8s %5.2fs\n' "$id" "$kind" "$dur"
  n=$((n + 1))
done < <("$PY" - <<'PYEOF'
import json
for s in json.load(open('/tmp/video/shots.json'))['shots']:
    print(f"{s['id']}\t{s['kind']}\t{s['dur']}\t{s['src'] or ''}")
PYEOF
)

# ── 5. video concat, then the voiceover laid on the same timeline ──────────
echo "5/6  concat + audio"
ffmpeg -nostdin -v error -f concat -safe 0 -i "$V/list.txt" -c copy "$V/video_only.mp4" -y
have "$V/video_only.mp4" || die "concat produced nothing"

# One aac track: each line delayed to its shot's start, then mixed.
"$PY" - > "$V/afilter.txt" <<'PYEOF'
import json
m = json.load(open('/tmp/video/shots.json'))
vo = [s for s in m['shots'] if s['vo']]
ins = " ".join(f"-i {s['vo']}" for s in vo)
parts = [f"[{i+1}:a]adelay={int((s['start']+0.25)*1000)}|{int((s['start']+0.25)*1000)}[a{i}]"
         for i, s in enumerate(vo)]
mix = "".join(f"[a{i}]" for i in range(len(vo)))
print(ins)
# apad, so `-shortest` trims the (now endless) audio to the video rather than
# trimming the video down to the last syllable of the last VO line.
print(f"{';'.join(parts)};{mix}amix=inputs={len(vo)}:normalize=0:dropout_transition=0,apad[out]")
PYEOF
AIN=$(sed -n 1p "$V/afilter.txt")
AFC=$(sed -n 2p "$V/afilter.txt")
# shellcheck disable=SC2086
ffmpeg -nostdin -v error -i "$V/video_only.mp4" $AIN \
  -filter_complex "$AFC" -map 0:v -map "[out]" \
  -c:v copy -c:a aac -ac 1 -b:a 72k -shortest "$V/$OUTNAME" -y \
  || die "audio mux failed"

# ── 6. verify: A/V lengths must agree, and the budget must hold ───────────
echo "6/6  verify"
cp "$V/captions.srt" "$V/${OUTNAME%.mp4}.srt"
VD=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 "$V/$OUTNAME")
AD=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of csv=p=0 "$V/$OUTNAME")
SZ=$(du -h "$V/$OUTNAME" | cut -f1)
printf '     video %ss  audio %ss  planned %ss  size %s\n' "$VD" "$AD" "$TOTAL" "$SZ"
"$PY" - "$VD" "$AD" "$TOTAL" <<'PYEOF'
import sys
v, a, t = (float(x) for x in sys.argv[1:4])
bad = []
if abs(v - t) > 0.5:   bad.append(f"video {v:.2f}s != planned {t:.2f}s")
if a - v > 0.30:       bad.append(f"audio {a:.2f}s overruns video {v:.2f}s")
if v > 90.5:           bad.append(f"{v:.1f}s exceeds the 90s budget")
if bad:
    print("FATAL: " + "; ".join(bad)); raise SystemExit(1)
print("     ok — A/V aligned, within budget")
PYEOF

echo
echo "wrote $V/$OUTNAME  (+ $V/${OUTNAME%.mp4}.srt)"
[ "$ANIMATIC" = 1 ] && echo "NOTE: ANIMATIC=1 — footage may be a stand-in. Do not ship." || true
echo "publish:  cp $V/$OUTNAME $HERE/../../docs/assets/demo/"
