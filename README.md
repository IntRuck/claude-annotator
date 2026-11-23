# Auto Annotator

A local dashboard that auto-annotates images for object detection, with a box editor for manual fixes. Labels are saved as YOLO `.txt`.

You pick which model does the labeling:

| Backend | What it is | Cost | Needs | Can Refine? |
|---|---|---|---|---|
| **Claude (your plan)** | Claude Code CLI signed in with your Claude account | Your Pro/Max usage limits, no API key | Claude Code installed and logged in | ✅ |
| **Gemini (API key)** | Gemini through a Google AI Studio key | Free if no billing is linked (daily limits apply) | A free key in a `.env` file | ✅ |
| **Local VLM (Ollama)** | A vision-language model on your own PC, e.g. Qwen-VL | Free, offline | [Ollama](https://ollama.com) + a pulled vision model | ✅ |
| **Grounding DINO** | Open-source text-prompted detector | Free, offline | `torch` + `transformers` | ❌ |
| **YOLO-World / YOLOE** | Open-source text-prompted YOLO (fastest) | Free, offline | `ultralytics` + Ultralytics CLIP | ❌ |

VLMs (Claude, Gemini, Ollama) understand what they see and follow instructions, but their boxes can be loose. Detectors (Grounding DINO, YOLO-World) draw tight boxes but only know general things like "can" or "bottle", not your exact SKUs. A good combo: detector for boxes, then fix names by hand or with a VLM Refine.

## Setup

1. Python packages (always needed):
   ```
   pip install flask pillow
   ```
2. Then only what you'll use:

   **Claude** - install Claude Code and log in with your Claude account (not a Console API key):
   ```
   npm install -g @anthropic-ai/claude-code
   claude          # follow the login, then type /exit
   ```

   **Gemini** - get a free key and put it in a `.env` file:
   1. Go to https://aistudio.google.com → **Get API key** → **Create API key**
   2. **Don't click "Set up billing".** With no billing linked the key stays on the free tier and can't charge you; when the free limit runs out, requests just fail until it resets
   3. Copy `.env.example` to `.env` next to `app.py` and paste the key: `GEMINI_API_KEY=your_key_here`
   4. Restart the app. The terminal shows `gemini=key found`

   Your Gemini app subscription (Plus/Pro) is separate and doesn't add API quota. Never put the key in code or share `.env`.

   **Local VLM** - install Ollama from https://ollama.com, then pull a vision model:
   ```
   ollama pull qwen3-vl:4b      # try qwen3-vl:2b if your GPU runs out of memory
   ```
   Check exact model names in the Ollama library; anything with vision works (qwen2.5vl, gemma3, llava...).

   **Grounding DINO / YOLO-World** - install PyTorch with CUDA first (pick your CUDA version at https://pytorch.org), then:
   ```
   pip install transformers                                   # Grounding DINO
   pip install ultralytics git+https://github.com/ultralytics/CLIP.git   # YOLO-World / YOLOE
   ```
   Model weights download automatically the first time you run each one.

3. Make `classes.txt`, or start with an empty one and add SKUs in the app (**SKUs** button). One SKU per line, and the line number is the YOLO class ID (first line = 0):
   ```
   cream_bottle
   spray_bottle | blue spray bottle
   sardine_155g | red tin can | Short round red tin, yellow label with "SARDIN" in bold, white pull-tab lid
   ```
   Each line is `name | detector prompt | description`. Only the name is required.
   - **name** goes into your YOLO export
   - **detector prompt** is a short phrase Grounding DINO / YOLO-World search for ("red tin can" works much better than a SKU code)
   - **description** is for Claude / Ollama: shape, colors, brand text, size, lid, and how it differs from look-alikes. This helps cheaper models like Haiku the most

## Run

```
python app.py
```
Open http://127.0.0.1:5050. The terminal shows which backends are ready, for example:
`Backends: claude=yes  gemini=key found  ollama=running  grounding_dino=yes  yolo_world=not installed`

### Start page
1. **Images folder**: paste the path or click **Browse…** and click into folders, then **Use this folder**. A preview shows how many images it found, whether a `labels` folder with existing YOLO labels is there, and whether a class list exists.
   - Existing YOLO `.txt` labels are loaded and shown. The class list must be in the same order as the IDs in those labels (first line = 0).
   - If there's no `classes.txt` but a `data.yaml` sits next to the dataset, you can import its class names in one click.
   - **Advanced** lets you point at a different labels folder or class list file. Defaults: `labels/` and `classes.txt` next to the images folder (standard YOLO layout).
2. **SKUs**: if there's no class list yet, the SKU manager opens next. Add each SKU with a short description of how it looks, then **Start labeling**.

Recent datasets are listed on the start page. The 📁 button at the top left reopens it to switch datasets.
You can still skip the start page: `python app.py --images D:\data\shelf\images --classes classes.txt`.

| Flag | Default | Meaning |
|---|---|---|
| `--images` | none (pick on the start page) | Folder with images |
| `--labels` | `<images>/../labels` | Folder for the YOLO `.txt` labels |
| `--classes` | `classes.txt` next to the images folder | Class list, one SKU per line |
| `--port` | `5050` | Port. The server only listens on 127.0.0.1 |

On Windows run it with `python`, not `python3` (`python3` may be the Microsoft Store stub).

## Using it

Layout: **left** = this image (classes and boxes, AI buttons, log), **center** = canvas with tools, **right** = image counter, Approve / Flag, filter and thumbnails. **Top** = dataset, SKUs, health check, AI picker and batch runs, export.

Pick an AI in the top bar. Its options appear next to it:

| AI | Options |
|---|---|
| Claude | Model: Sonnet (balance), Haiku (uses least of your limits), Opus (most careful) |
| Gemini | Model name. Suggestions come from your key's model list. `gemini-3.5-flash-lite` has a bigger free daily limit |
| Local VLM | Ollama model name (suggestions come from the models you've pulled) |
| Grounding DINO | Size: tiny (fits 4 GB GPUs) or base. **conf**: minimum confidence to keep a box |
| YOLO-World | Weights file, e.g. `yolov8s-worldv2.pt` or `yoloe-11s-seg.pt`. **conf** as above |

**grid** (Claude / Ollama) draws a faint 0-1000 grid on the image the model sees. **Extra instructions**, e.g. `Products on the top shelf are out of scope`.

| Button | Where | What it does |
|---|---|---|
| Label all unlabeled | top | Labels every image with no labels yet (and retries errored ones) |
| Refine all | top | Runs Refine on every AI-labeled image you haven't approved |
| Stop | top | Stops after the current image |
| ✨ Find objects with AI | left | Labels the current image from scratch (replaces its boxes) |
| Refine boxes with AI | left | The AI sees the current boxes drawn on the image and fixes loose, split, duplicate or missing ones |
| ✓ Approve (R) | right | Marks the image as checked and moves to the next one |
| 🚩 Flag (G) | right | Marks the image to come back to later (see below) |
| SKUs | top | Add / rename SKUs and set each one's detector prompt and description. Saves automatically. Rows never move, so class IDs stay the same |
| Health check | top | Boxes per class, imbalance, box sizes, heat map, and issues. Click a class or issue to filter the thumbnails |
| Export | top | YOLO zip or COCO JSON (see below) |

Classes tab (left): click a class to draw with it (or press 1-9). If a box is selected, it changes that box too. Double-click a class to edit it. The number on the right is how many boxes of that class are on this image. Boxes tab: change a box's class, hide it or delete it.

Display (bottom left of the canvas): brightness, contrast, show / hide annotations and class names, fill boxes. These only change what you see, not the image.

### 🚩 Flag images to check later
For an image that looks wrong but you don't want to fix now. Click the red **🚩 Flag for later** button on the right or press **G**. A reason dropdown and note box appear; both save on their own. A red banner shows on the canvas while the image is flagged.
- Flag is separate from Approve, so an approved image can still be flagged. Re-running AI keeps the flag.
- Use the **🚩 Flagged** filter on the right to go through them later. Press G again to unflag once fixed.
- Previously the G key stopped working after you'd used any dropdown (the dropdown kept keyboard focus). Fixed: dropdowns now let go of focus once you pick something, and Esc leaves any text box.

### Export
| Option | Meaning |
|---|---|
| Approved images only | Only export images you approved with R. Use this for training so unchecked AI labels stay out |
| Leave out 🚩 flagged | Skip flagged images (on by default) |
| YOLO zip | `images/train`, `images/val`, `labels/...` and `data.yaml` (10% val). This is what YOLO training wants |
| COCO JSON | One JSON file for tools that use the COCO format (DETR, Detectron2, MMDetection). Not needed for YOLO |

### Editor shortcuts
| Key / mouse | Action |
|---|---|
| Drag on empty area | New box (uses the highlighted class) |
| Click box, drag box / corner | Select, move / resize |
| B / V, hold Space | Box tool / pan tool, pan while held |
| 1-9 | Set class (of selected box, and for new boxes) |
| Del | Delete selected box |
| H | Show only the selected box |
| G | 🚩 Flag / unflag |
| L | Show / hide class names |
| Wheel / right-drag / F | Zoom / pan / fit |
| Ctrl+Z / Ctrl+Y | Undo / redo (per image, up to 200 steps) |
| S | Save |
| R | Approve and go to next image |
| A / D | Previous / next image |

The ⌨ button on the canvas shows this list.

### Status colors
Gray = unlabeled · Blue = auto-labeled · Yellow = edited by you · Green = approved · Red = error (hover for the reason) · 🚩 = flagged by you

## Notes

- **Claude usage limits**: when Claude hits your 5-hour or weekly limit, the job pauses and logs it. Press Annotate again after the reset and it continues where it stopped.
- **Gemini free limits**: per-minute limits are waited out automatically. When the **daily** free quota is used up, the job pauses and says so; continue tomorrow or switch to another Gemini model (each model has its own quota).
- **Gemini boxes** come back as `[ymin, xmin, ymax, xmax]` (y first). The app converts them, so labels on disk are normal YOLO.
- **Free-tier data**: Google may use free-tier requests to improve its products. Decide whether that's OK for your images.
- **Claude terms**: running Claude in big unattended batches may conflict with the Consumer Terms' rule on automated access. Use it for reasonable batches, and use the open-source backends for bulk work.
- If `ANTHROPIC_API_KEY` is set, the app removes it for the Claude call, so you're never billed for API usage by accident.
- **GPU memory**: only one detector stays loaded at a time. On a 4 GB GPU use Grounding DINO tiny or a small YOLO-World; close other GPU apps. Ollama runs in its own process and also uses the GPU, so don't run both at once.
- Ollama gets the image padded to 1000×1000, so it reads coordinates correctly whether the model answers in pixels or on a 0-1000 scale.
- VLM images are resized to max 1568 px. Detectors run on your original image. Your original files are never modified.
- Temp images are kept in `labels/_claude_tmp/`. Delete that folder anytime.
- Only images directly inside the images folder are listed (no subfolders).
- `CLAUDE_BIN` env var lets you point to a specific `claude` executable if it isn't on PATH.
- Environment variables: `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) for Gemini, `CLAUDE_BIN` as above. `.env` is read at start-up but never overrides a variable already set in your shell.

## Files

| File | What's in it |
|---|---|
| `app.py` | Web server, project storage (labels, classes, status), background worker, health check, exports |
| `backends.py` | The labeling engines (Claude, Gemini, Ollama, Grounding DINO, YOLO-World) and the prompt/answer parsing for VLMs |
| `.env.example` | Template for your Gemini key. Copy to `.env` |
| `classes.example.txt` | Example class list (`name \| detector prompt \| description`). Copy to `classes.txt` |
| `requirements.txt` | Python packages: `flask`, `pillow`, optional detector packages commented out |
| `index.html` | The whole web page: start page, canvas editor, panels, thumbnails |
| `recent.json` | Created on first use: your recent datasets for the start page |
