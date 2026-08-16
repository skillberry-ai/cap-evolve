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
TERM_SEEK=${TERM_SEEK:-0.6}   # the reshot tape starts on the home screen: play it from the top
DASH_SEEK=${DASH_SEEK:-1.6}   # past first paint, into the headline tiles

die () { echo "FATAL: $*" >&2; exit 1; }
have () { [ -s "$1" ]; }

[ -x "$PY" ] || die "$PY missing. python3 -m venv /tmp/vidvenv && /tmp/vidvenv/bin/pip install Pillow playwright"
command -v ffmpeg >/dev/null || die "ffmpeg not on PATH"
mkdir -p "$V"

# The parallel/speedup pair is gone from the cut, and with it the build-time
# freshness check that tied the speedup card to par_results.json. par_demo.py
# itself stays — README still documents it as a standalone parallelism check —
# but nothing in this build reads it, so nothing here can go stale.

# ── 1. cards + voiceover + music + manifest ───────────────────────────────
echo "1/5  cards + voiceover + music"
"$PY" "$HERE/assets.py" || die "assets.py failed"
have "$V/shots.json" || die "assets.py did not write shots.json"

W=$($PY -c "import json;print(json.load(open('$V/shots.json'))['w'])")
H=$($PY -c "import json;print(json.load(open('$V/shots.json'))['h'])")
FPS=$($PY -c "import json;print(json.load(open('$V/shots.json'))['fps'])")
TOTAL=$($PY -c "import json;print(json.load(open('$V/shots.json'))['total'])")

VENC="-c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p -r $FPS"
NORM="scale=$W:$H:force_original_aspect_ratio=decrease,pad=$W:$H:(ow-iw)/2:(oh-ih)/2:color=0x0b0d17,fps=$FPS,format=yuv420p,setsar=1"

MUSIC=$($PY -c "import sys;sys.path.insert(0,'$HERE');import script;print(script.MUSIC_WAV)")
MUSIC_DB=$($PY -c "import sys;sys.path.insert(0,'$HERE');import script;print(script.MUSIC_DB)")
MFI=$($PY -c "import sys;sys.path.insert(0,'$HERE');import script;print(script.MUSIC_FADE_IN)")
MFO=$($PY -c "import sys;sys.path.insert(0,'$HERE');import script;print(script.MUSIC_FADE_OUT)")
have "$MUSIC" || die "assets.py did not write the music bed at $MUSIC"

# ── 2. footage inputs must exist ──────────────────────────────────────────
echo "2/5  checking footage"
missing=0
for f in replay dashboard; do
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
  /tmp/vidvenv/bin/python scripts/demo-video/dash.py  # -> /tmp/video/dashboard.mp4
Refusing to ship a short video with a segment silently dropped.
EOF
  exit 1
fi

# ── 3. one clip per shot ──────────────────────────────────────────────────
echo "3/5  rendering shots"
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
        *)         die "footage shot '$id' has unknown src '$src'" ;;
      esac
      # Footage is shown CLEAN. assets.py only writes lower/<id>.png under
      # ANIMATIC=1, as a corner stand-in badge; when it is absent there is no
      # overlay pass at all.
      if have "$V/lower/$id.png"; then
        ffmpeg -nostdin -v error -ss "$seek" -i "$in_mp4" -i "$V/lower/$id.png" -t "$dur" \
          -filter_complex "[0:v]$NORM[b];[b][1:v]overlay=0:H-h:format=auto[o];[o]fade=t=in:st=0:d=0.3,fade=t=out:st=$fin:d=0.35[v]" \
          -map "[v]" $VENC -an "$seg" -y \
          || die "could not render footage shot '$id' from $in_mp4 (is it shorter than ${seek}s+${dur}s?)"
      else
        ffmpeg -nostdin -v error -ss "$seek" -i "$in_mp4" -t "$dur" \
          -vf "$NORM,fade=t=in:st=0:d=0.3,fade=t=out:st=$fin:d=0.35" \
          $VENC -an "$seg" -y \
          || die "could not render footage shot '$id' from $in_mp4 (is it shorter than ${seek}s+${dur}s?)"
      fi
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

# ── 4. video concat, then voiceover + music laid on the same timeline ──────
echo "4/5  concat + audio"
ffmpeg -nostdin -v error -f concat -safe 0 -i "$V/list.txt" -c copy "$V/video_only.mp4" -y
have "$V/video_only.mp4" || die "concat produced nothing"

# One aac track: every VO line delayed to its shot's start and summed at unity,
# then the generated music bed mixed UNDER it at script.MUSIC_DB.
"$PY" - "$MUSIC" "$MUSIC_DB" "$MFI" "$MFO" > "$V/afilter.txt" <<'PYEOF'
import json, sys
music, db, fi, fo = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
m = json.load(open('/tmp/video/shots.json'))
vo = [s for s in m['shots'] if s['vo']]
total = m['total']
# The music is input 1 so the VO inputs keep their existing 1..n ordering logic.
print(" ".join([f"-i {music}"] + [f"-i {s['vo']}" for s in vo]))
parts = [f"[{i+2}:a]adelay={int((s['start']+0.25)*1000)}|{int((s['start']+0.25)*1000)}[a{i}]"
         for i, s in enumerate(vo)]
mix = "".join(f"[a{i}]" for i in range(len(vo)))
# Narration first, at unity — normalize=0 so amix never scales the voice down.
parts.append(f"{mix}amix=inputs={len(vo)}:normalize=0:dropout_transition=0[voice]")
# The bed: ducked to MUSIC_DB, faded in at the head and out on the last frames.
parts.append(f"[1:a]volume={db}dB,afade=t=in:st=0:d={fi},"
             f"afade=t=out:st={max(0.0, total - fo):.2f}:d={fo}[bed]")
# apad, so `-shortest` trims the (now endless) audio to the video rather than
# trimming the video down to the last syllable of the last VO line.
parts.append("[voice][bed]amix=inputs=2:normalize=0:dropout_transition=0,apad[out]")
print(";".join(parts))
PYEOF
AIN=$(sed -n 1p "$V/afilter.txt")
AFC=$(sed -n 2p "$V/afilter.txt")
# shellcheck disable=SC2086
ffmpeg -nostdin -v error -i "$V/video_only.mp4" $AIN \
  -filter_complex "$AFC" -map 0:v -map "[out]" \
  -c:v copy -c:a aac -ac 1 -b:a 96k -shortest "$V/$OUTNAME" -y \
  || die "audio mux failed"

# ── 5. verify: A/V lengths must agree, and the budget must hold ───────────
echo "5/5  verify"
cp "$V/captions.srt" "$V/${OUTNAME%.mp4}.srt"
VD=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 "$V/$OUTNAME")
AD=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of csv=p=0 "$V/$OUTNAME")
MD=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$MUSIC")
SZ=$(du -h "$V/$OUTNAME" | cut -f1)
printf '     video %ss  audio %ss  music %ss  planned %ss  size %s\n' \
  "$VD" "$AD" "$MD" "$TOTAL" "$SZ"
"$PY" - "$VD" "$AD" "$TOTAL" "$MD" <<'PYEOF'
import json, sys
v, a, t, m = (float(x) for x in sys.argv[1:5])
bad = []
if abs(v - t) > 0.5:   bad.append(f"video {v:.2f}s != planned {t:.2f}s")
if a - v > 0.30:       bad.append(f"audio {a:.2f}s overruns video {v:.2f}s")
if v > 90.5:           bad.append(f"{v:.1f}s exceeds the 90s budget")
if m + 0.10 < t:       bad.append(f"music bed {m:.2f}s is shorter than the cut {t:.2f}s")
# No VO line may be cut off by the end of its own shot, or by the end of the cut.
for s in json.load(open('/tmp/video/shots.json'))['shots']:
    if not s['vo']:
        continue
    end = s['start'] + 0.25 + s['vo_dur']
    if end > s['start'] + s['dur'] + 0.01:
        bad.append(f"vo '{s['id']}' overruns its shot by {end - s['start'] - s['dur']:.2f}s")
    if end > v + 0.01:
        bad.append(f"vo '{s['id']}' is clipped by the end of the video")
if bad:
    print("FATAL: " + "; ".join(bad)); raise SystemExit(1)
print("     ok — A/V aligned, no VO clipped, music covers the cut, within budget")
PYEOF

echo
echo "wrote $V/$OUTNAME  (+ $V/${OUTNAME%.mp4}.srt)"
[ "$ANIMATIC" = 1 ] && echo "NOTE: ANIMATIC=1 — footage may be a stand-in. Do not ship." || true
echo "publish:  cp $V/$OUTNAME $HERE/../../docs/assets/demo/"
