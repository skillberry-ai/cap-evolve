---
name: video-processor
description: Process videos by removing silence/pauses/openings and concatenating the remaining parts. Use for end-to-end "silence remover" tasks that turn an input video into a compressed_video.mp4 plus a compression_report.json, or to remove a known list of segments. Bundles a one-command pipeline (audio → energy → opening → pauses → trim → report) as well as direct filter_complex segment removal.
---

# Video Segment Processor

Processes videos by removing specified segments and concatenating the remaining parts. Handles multiple removal segments efficiently using ffmpeg's filter_complex.

## End-to-end silence/pause removal (recommended — run this first)

For a "remove the silence / pauses / opening from a video" task whose required
output is a `compressed_video.mp4` plus a `compression_report.json`, do NOT
hand-tune parameters or chain the detector scripts yourself. Run the bundled
orchestrator, which performs the entire pipeline deterministically with tuned,
general parameters and the correct coordination between steps:

```bash
python3 /root/.claude/skills/video-processor/scripts/remove_silence.py \
    --input data/input_video.mp4 \
    --output compressed_video.mp4 \
    --report compression_report.json
```

It runs: extract audio → per-second RMS energy → detect the opening (initial
silence) → detect mid-video pauses **starting after the opening** → combine
segments → trim/concat the kept parts → write the JSON report. Because it always
starts pause detection at the detected opening end, it never fragments the
opening's silent tail into spurious short "pause" segments — a common cause of
low detection precision. Execute this script; do not reimplement it. Only fall
back to the manual step-by-step scripts below (or the individual detector
skills) when the task needs behaviour this orchestrator does not cover.

### Scope of removal — trust the detector output; do NOT hand-edit it

"Silence removal" is defined purely by **audio energy**: the *opening* is the
initial low-audio region (title / standby / countdown / pre-roll slide) and the
*pauses* are the mid-video low-audio gaps. That is the entire scope — even when
the task wording mentions "non-teaching content", it means these silent regions,
not an editorial judgement about the footage.

After the orchestrator writes `compressed_video.mp4` and
`compression_report.json`, those files are the **final answer — submit them as
is.** Do NOT:

- shorten or split the opening because it "looks long": a static title/standby
  screen can legitimately run for **several minutes** and still be one correct
  opening segment. The audio energy, not the moment the visuals change, defines
  where it ends.
- inspect video frames and add extra removal segments based on visual content,
  scene changes, speaker identity, an inserted clip, or a belief that some
  passage "isn't teaching / is off-topic". Removing content the audio detector
  did not flag **over-cuts the video and fails the removed-duration and
  compressed-duration checks.**

Only re-run the pipeline (e.g. adjust `--silence-multiplier` / `--pause-ratio`)
if the detector clearly missed *audio silence*; never overwrite its report by
hand to cut content it intentionally kept.

## Use Cases

- Removing detected pauses and openings from videos
- Creating highlight reels by keeping only specific segments
- Batch processing multiple segment removals

## Usage

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /path/to/input.mp4 \
    --output /path/to/output.mp4 \
    --remove-segments /path/to/segments.json
```

### Parameters

- `--input`: Path to input video file
- `--output`: Path to output video file
- `--remove-segments`: JSON file containing segments to remove

### Input Segment Format

```json
{
  "segments": [
    {"start": 0, "end": 600, "duration": 600},
    {"start": 610, "end": 613, "duration": 3}
  ]
}
```

Or multiple segment files:

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input video.mp4 \
    --output output.mp4 \
    --remove-segments opening.json pauses.json
```

### Output

Creates the processed video and a report JSON:

```json
{
  "original_duration": 3908.61,
  "output_duration": 3078.61,
  "removed_duration": 830.0,
  "compression_percentage": 21.24,
  "segments_removed": 91,
  "segments_kept": 91
}
```

## How It Works

1. **Load removal segments** from JSON file(s)
2. **Calculate keep segments** (inverse of removal segments)
3. **Build ffmpeg filter** to trim and concatenate
4. **Process video** using hardware-accelerated encoding
5. **Generate report** with statistics

### FFmpeg Filter Example

For 3 segments to keep:
```
[0:v]trim=start=600:end=610,setpts=PTS-STARTPTS[v0];
[0:a]atrim=start=600:end=610,asetpts=PTS-STARTPTS[a0];
[0:v]trim=start=613:end=1000,setpts=PTS-STARTPTS[v1];
[0:a]atrim=start=613:end=1000,asetpts=PTS-STARTPTS[a1];
[v0][v1]concat=n=2:v=1:a=0[outv];
[a0][a1]concat=n=2:v=0:a=1[outa]
```

## Dependencies

- ffmpeg with libx264 and aac support
- Python 3.11+

## Limitations

- Processing time: ~0.3× video duration (e.g., 20 min for 65 min video)
- Requires sufficient disk space (output ≈ 70-80% of input size)
- May have frame-accurate cuts (not sample-accurate)

## Example

```bash
# Process video with opening and pause removal
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /root/lecture.mp4 \
    --output /root/compressed.mp4 \
    --remove-segments /root/opening.json /root/pauses.json

# Result: 65 min → 51 min (21.2% compression)
```

## Performance Tips

- Use `-preset medium` for balanced speed/quality
- Use `-crf 23` for good quality at reasonable size
- Process on machines with 2+ CPU cores for faster encoding

## Notes

- Preserves video quality using CRF encoding
- Maintains audio sync throughout
- Handles edge cases (segments at start/end of video)
- Generates detailed statistics for verification
