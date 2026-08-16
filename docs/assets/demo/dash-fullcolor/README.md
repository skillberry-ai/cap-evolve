# Full-colour dashboard captures — do NOT optimize these

24-bit RGB (`pix_fmt=rgb24`) captures of the `run_full` static dashboard, for video use.

`docs/assets/screenshots/` is palettized with `pngquant` (`pal8`, 256 colours) because
that is the right trade for docs. It is the wrong trade for film: the 256-colour table
dithers cap-evolve's dark gradients, and that dither reads as blue/purple speckle once a
frame is scaled into a 1080p timeline. **Never run `pngquant`/`oxipng` over this folder.**

Regenerate (never hand-edit — every pixel comes from the real UI):

```bash
/tmp/vidvenv/bin/python scripts/tools/shoot_dashboard.py \
  --out docs/assets/demo/dash-fullcolor --prefix "" --no-optimize \
  --only overview,candidates,gate,tasks,diffs,cost
```

Check after: `ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of csv=p=0 gate.png` → `rgb24`.
