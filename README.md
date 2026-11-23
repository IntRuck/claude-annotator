# Claude Annotator

A local dashboard that uses **Claude Code signed in with your Claude plan** to auto-annotate images for object detection. It also has a box editor for manual fixes. Labels are saved as YOLO `.txt`.

No API key is needed. Usage comes out of your Pro/Max plan limits.

## Setup

1. Install Claude Code and sign in with your Claude account (not a Console API key):
   ```
   npm install -g @anthropic-ai/claude-code
   claude          # follow the login, then type /exit
   ```
2. Install Python packages:
   ```
   pip install flask pillow
   ```
3. Make `classes.txt`, one class name per line. The line number is the YOLO class ID (first line = 0):
   ```
   cream_bottle
   spray_bottle
   canned_food
   ```

## Run

```
python app.py --images D:\data\shelf\images --classes classes.txt
```
Open http://127.0.0.1:5050

Labels go to `<images>/../labels/` by default (YOLO's standard layout). Change this with `--labels`.

## Using it

| Button | What it does |
|---|---|
| Annotate unlabeled | Claude labels every image with no labels yet (and retries errored ones) |
| Annotate this | Claude labels the current image from scratch (replaces its boxes) |
| Refine this | Claude sees the current boxes drawn on the image and fixes loose, split, duplicate or missing boxes |
| Refine all auto | Runs Refine on every Claude-labeled image you haven't reviewed |
| Stop | Stops after the current image |
| Health check | Dataset report: boxes per class, low-count and missing classes, imbalance, box sizes, where boxes sit in the frame, and issues (duplicates, tiny boxes, unknown class IDs, unlabeled, errors). Click a class or an issue to filter the image list to just those images |
| Export YOLO | Zip with `images/train`, `images/val`, `labels/...` and `data.yaml` (10% val) |
| Export COCO | One COCO JSON file |

Options in the top bar:
- **Model**: Sonnet is the best balance. Haiku uses the least of your limits. Opus is the most careful but burns limits fastest.
- **grid**: draws a faint 0-1000 grid on the image Claude sees. Can help box accuracy, so try it on a few images and compare.
- **Extra instructions**: e.g. `Products on the top shelf are out of scope` or `Label price tags too`.

### Editor shortcuts
| Key / mouse | Action |
|---|---|
| Drag on empty area | New box (uses the highlighted class) |
| Click box | Select |
| Drag box / corner | Move / resize |
| 1-9 | Set class (of selected box, and for new boxes) |
| Del | Delete selected box |
| H | Show only the selected box |
| L | Show / hide class names on boxes (also the "label names" checkbox, top right of the image) |
| Wheel / right-drag / F | Zoom / pan / fit |
| Ctrl+Z / Ctrl+Y (or Ctrl+Shift+Z) | Undo / redo (per image, up to 200 steps; also buttons in the right panel) |
| S | Save |
| R | Mark reviewed and go to next image |
| A / D | Previous / next image |

Double-click a class to rename it. The ID stays the same, so existing labels stay valid. New classes are always added at the end.

### Status colors
Gray = unlabeled · Blue = Claude labeled · Yellow = edited by you · Green = reviewed · Red = error (hover for the reason)

## Notes

- **Usage limits**: when Claude hits your 5-hour or weekly limit, the job pauses and logs it. Press Annotate again after the reset and it continues where it stopped.
- If `ANTHROPIC_API_KEY` is set in your environment, the app removes it for the Claude call, so you're never billed for API usage by accident.
- Claude's boxes can be a bit loose. Use Refine, then do a quick manual pass before training.
- Images are resized to max 1568 px before sending (Claude's native size). Your original files are never modified.
- Temp images sent to Claude are kept in `labels/_claude_tmp/`. Delete that folder anytime.
- Only images directly inside the images folder are listed (no subfolders).
- `CLAUDE_BIN` env var lets you point to a specific `claude` executable if it isn't on PATH.
