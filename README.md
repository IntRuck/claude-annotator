# Claude Annotator

A local dashboard that auto-annotates images for object detection, with a box editor for manual fixes. Exports YOLO (zip with `data.yaml`) or COCO.

Everything runs on your own computer:

| Part | What it does |
|---|---|
| **Web app** (`web/`) | The page you use: projects, SKUs, image strip, box editor, AI buttons, health check, export |
| **API** (`backend/`) | What the page talks to. Saves boxes, statuses and flags; sends live updates to every open tab |
| **Worker** (`backend/`) | Runs the AI in the background, one image at a time |
| **Local Supabase** | The database (projects, SKUs, boxes, statuses, AI jobs, activity log) and the photo storage |

You pick which AI does the labelling:

| AI | What it is | Cost | Needs | Can Refine? |
|---|---|---|---|---|
| **Gemini (API key)** | Gemini through a Google AI Studio key | Free if no billing is linked (daily limits apply) | A free key in `backend/.env` | ✅ |
| **Claude (your plan)** | Claude Code CLI signed in with your Claude account | Your Pro/Max usage limits, no API key | Claude Code installed and logged in | ✅ |
| **Local VLM (Ollama)** | A vision-language model on your own PC, e.g. Qwen-VL | Free, offline | [Ollama](https://ollama.com) + a pulled vision model | ✅ |
| **Grounding DINO** | Open-source text-prompted detector | Free, offline | PyTorch + `transformers` | ❌ |
| **YOLO-World / YOLOE** | Open-source text-prompted YOLO (fastest) | Free, offline | PyTorch + `ultralytics` | ❌ |

VLMs (Gemini, Claude, Ollama) understand what they see and follow instructions, but their boxes can be loose. Detectors (Grounding DINO, YOLO-World) draw tight boxes but only know general things like "can" or "bottle", not your exact SKUs. A good combo: a detector for the boxes, then fix the names by hand or with a VLM Refine.

## What you need

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (the database runs in it)
- [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started)
- Python 3.12 or newer
- Node.js 22 or newer

## First-time setup

Run these in PowerShell from the `claude-annotator` folder.

1. **Database.** Start Docker Desktop, then:
   ```
   supabase start
   docker compose run --rm flyway migrate
   supabase status
   ```
   `flyway migrate` creates the tables. From `supabase status`, copy the **service_role key** (newer versions call it **Secret key**).

2. **Backend.**
   ```
   cd backend
   python -m venv .venv
   .venv\Scripts\python -m pip install -e ".[dev]"
   copy .env.example .env
   ```
   Open `backend/.env` and paste the key into `SUPABASE_SERVICE_ROLE_KEY=`. The other lines are already right for this computer.

3. **Web app.**
   ```
   cd ..\web
   npm ci
   ```

4. **The AIs you'll use** (only these):

   **Gemini**: get a free key.
   1. Go to https://aistudio.google.com → **Get API key** → **Create API key**
   2. **Don't click "Set up billing".** With no billing linked the key stays on the free tier and can't charge you; when the free limit runs out, requests just fail until it resets
   3. Paste it into `backend/.env`: `GEMINI_API_KEY=your_key_here`, then restart the worker

   Your Gemini app subscription (Plus/Pro) is separate and doesn't add API quota. Never put the key in code or share `backend/.env`.

   **Claude**: install Claude Code and log in with your Claude account (not a Console API key):
   ```
   npm install -g @anthropic-ai/claude-code
   claude          # follow the login, then type /exit
   ```

   **Local VLM**: install Ollama from https://ollama.com, then pull a vision model:
   ```
   ollama pull qwen3-vl:4b      # try qwen3-vl:2b if your GPU runs out of memory
   ```
   Anything with vision works (qwen2.5vl, gemma3:4b, llava...). Text-only models such as llama3.2 or gemma3:270m can't see images.

   **Grounding DINO / YOLO-World**: install PyTorch with CUDA first (pick your CUDA version at https://pytorch.org), then in `backend`:
   ```
   .venv\Scripts\python -m pip install -e ".[detectors]"
   .venv\Scripts\python -m pip install git+https://github.com/ultralytics/CLIP.git    # YOLO-World / YOLOE
   ```
   Model weights download automatically the first time you run each one.

## Run (every day)

Docker Desktop must be running. Then use three terminals:

| # | Where | Command |
|---|---|---|
| 1 | `claude-annotator` | `supabase start` (finishes by itself, then you can reuse this terminal) |
| 2 | `claude-annotator\backend` | `.venv\Scripts\python -m uvicorn annotator.main:create_app --factory --host 127.0.0.1 --port 8000 --reload --timeout-graceful-shutdown 3` |
| 3 | `claude-annotator\backend` | `.venv\Scripts\python -m annotator.worker` |
| 4 | `claude-annotator\web` | `npm run dev` |

Open **http://localhost:5173**.

- The API and worker always read `backend/.env`, whichever folder you start them from. The commands above use `.venv\Scripts\python`, so run them inside `backend`.
- Without the worker everything works except the AI; the page says "Worker offline".
- To stop: Ctrl+C in each terminal, then `supabase stop`.
- After pulling new code, run `docker compose run --rm flyway migrate` once in case it added tables.

## Using it

1. **Projects page**: click **New project**, give it a name (and a short description if you like), then click its card to open it. Projects show as cards, three per row, each with its cover photo on top, how much is labelled (green = approved, orange = labelled but not approved yet), and what's waiting. Search and sort sit above the cards. The **⋯** on a card lets you edit the name and description, or delete the project. Deleting removes its photos, labels and SKUs for good, so you type the project's name to confirm. In a project, **← Projects** (top left) brings you back. Click the project's name to jump straight to another project. Both save unsaved box edits first.
2. **SKUs**: the SKU manager opens for a new project. Add each SKU:
   - **name** goes into your export
   - **detector prompt** is a short phrase Grounding DINO / YOLO-World search for ("red tin can" works much better than a SKU code)
   - **description** is for Gemini / Claude / Ollama: shape, colours, brand text, size, lid, and how it differs from look-alikes. This helps cheaper models the most

   Rows never move, so class IDs stay the same.
3. **Add images**: **Upload images**, or **Import dataset** to bring in an existing YOLO set. Import takes the images plus their `.txt` labels, and the class list from `classes.txt` (one SKU per line as `name | detector prompt | description`, see `classes.example.txt`) or `data.yaml`. A `_annot_state.json` from the old Claude Annotator brings its statuses and flags along.
4. **Label, check, fix**, then **Export**.

Layout: **left** = this image (classes and boxes, AI buttons, activity log), **centre** = the editor, **right** = upload, Approve / Flag, filter and thumbnails. **Top**, split along the same three columns: where you are (← Projects, project name with ● Live next to it; hover the name for its full text), the AI (picker, options, batch runs), and project tools (Health check, Export, and **⋯** for Import dataset, SKUs, Edit project details and Light / Dark / Auto). **Edit SKUs** also sits under the class list.

**Light or dark**: the switch at the top right of the projects page (or the workspace's **⋯** menu) picks Light, Dark or Auto. Auto follows your computer's setting; the browser remembers your choice. The font (Atkinson Hyperlegible Next, made to be easy to read) comes with the app, so it works offline.

Pick an AI in the top bar. Its options appear next to it:

| AI | Options |
|---|---|
| Gemini | Model name. Suggestions come from your key's model list. `gemini-3.5-flash-lite` has a bigger free daily limit |
| Claude | Model: Sonnet (balance), Haiku (uses least of your limits), Opus (most careful) |
| Local VLM | Ollama model name (suggestions come from the models you've pulled). If the chosen one isn't pulled, it switches to a pulled vision model, or warns if there is none |
| Grounding DINO | Size: tiny (fits 4 GB GPUs) or base. **conf**: minimum confidence to keep a box |
| YOLO-World | Weights file, e.g. `yolov8s-worldv2.pt` or `yoloe-11s-seg.pt`. **conf** as above |

**grid** (Claude / Ollama) draws a faint 0-1000 grid on the image the model sees. **Extra instructions**, e.g. `Products on the top shelf are out of scope`. The page remembers your choice, and each AI's last model.

| Button | Where | What it does |
|---|---|---|
| Label all unlabeled | top | Labels every image with no labels yet (and retries errored ones) |
| Refine all | top | Runs Refine on every AI-labelled image you haven't approved |
| ■ Stop | top | Cancels the waiting images; the one being labelled now finishes |
| Resume | top (yellow banner) | Shown when an AI hit a usage limit; continues the paused images |
| Health check | top | Boxes per class, imbalance, box sizes, where boxes sit, and issues. Click a class or issue to show just those images |
| Export | top | YOLO zip or COCO JSON (see below) |
| ✨ Find objects with AI | left | Labels the current image from scratch (replaces its boxes) |
| Refine boxes with AI | left | The AI sees the current boxes drawn on the image and fixes loose, split, duplicate or missing ones |
| ✓ Approve (R) | right | Marks the image as checked and moves to the next one |
| 🚩 Flag (G) | right | Marks the image to come back to later (see below) |

Classes tab (left): click a class to draw with it (or press 1-9). If a box is selected, it changes that box too. The number on the right is how many boxes of that class are on this image. Boxes tab: change a box's class, hide it or delete it.

Display (on the editor): brightness, contrast, show / hide annotations and class names, fill boxes. These only change what you see, not the image.

**Live updates**: open the project in two tabs, or let the AI run. Changes show up everywhere as they happen. Next to the project name it says **Live**, **Connecting…** or **Offline**.

### 🚩 Flag images to check later
For an image that looks wrong but you don't want to fix now. Click **🚩 Flag for later** on the right or press **G**, then pick a reason and add a note.
- Flag is separate from Approve, so an approved image can still be flagged. Re-running the AI keeps the flag.
- Use the **🚩 Flagged** filter on the right to go through them later. Press G again to unflag once fixed.

### Export
The dialog shows how many images and boxes will go in before you download.

| Option | Meaning |
|---|---|
| Approved images only | Only export images you approved with R. Use this for training so unchecked AI labels stay out |
| Leave out 🚩 flagged | Skip flagged images (on by default) |
| YOLO zip | `images/train`, `images/val`, `labels/...` and `data.yaml` (10% val). This is what YOLO training wants |
| COCO JSON | One JSON file for tools that use the COCO format (DETR, Detectron2, MMDetection). Not needed for YOLO |

Unsaved box edits are saved before the dialog opens, so they're in the download.

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
| Ctrl+Z / Ctrl+Y | Undo / redo (per image) |
| S | Save |
| R | Approve and go to next image |
| A / D | Previous / next image |
| Esc | Deselect, leave a text box |

Unsaved changes are saved as "edited" when you move to another image, open a dialog or run the AI.

### Status colours
Grey = unlabelled · Blue = labelled by AI · Yellow = edited by you · Green = approved · Red = error (hover for the reason) · 🚩 = flagged by you

## Notes

- **Usage limits**: when Claude hits your 5-hour or weekly limit, or Gemini's **daily** free quota runs out, that AI pauses and a yellow banner says so. Its waiting images stay in the queue; press **Resume** after the reset (or switch to another Gemini model: each has its own quota). Gemini's per-minute limits are waited out automatically.
- **Free-tier data**: Google may use free-tier requests to improve its products. Decide whether that's OK for your images.
- **Claude terms**: running Claude in big unattended batches may conflict with the Consumer Terms' rule on automated access. Use it for reasonable batches, and use the open-source AIs for bulk work.
- If `ANTHROPIC_API_KEY` is set, it's removed for the Claude call, so you're never billed for API usage by accident.
- **GPU memory**: only one detector stays loaded at a time. On a 4 GB GPU use Grounding DINO tiny or a small YOLO-World; close other GPU apps. Ollama runs in its own process and also uses the GPU, so don't run both at once.
- Ollama gets the image padded to 1000×1000, so it reads coordinates correctly whether the model answers in pixels or on a 0-1000 scale.
- VLM images are resized to max 1568 px. Detectors run on your original image. Your original photos are never changed.
- `CLAUDE_BIN` in `backend/.env` points to a specific `claude` executable if it isn't on PATH.
- Supabase Studio (http://127.0.0.1:55323) lets you look at the data directly.

## Before real use

This version is for one person on one computer: there's no login, the API only listens on 127.0.0.1, and only the web app may call it. Before other people use it, or it runs on a server:

- **Login**: Supabase JWT login, like backend_web
- **Roles**: who may label, approve, export and manage SKUs
- **Audit trail**: who changed which boxes, statuses and flags, and when
- **Upload limits**: maximum file size and number of images per upload

## For developers

```
cd backend
.venv\Scripts\python -m pytest            # unit + API tests
.venv\Scripts\python -m pytest -m db      # database tests (Docker: a throwaway Postgres migrated by Flyway)
cd ..\web
npm test
npm run lint
npm run build
docker compose run --rm flyway validate   # migrations match what's applied
```

How the code is organised, and its rules, are in [CLAUDE.md](CLAUDE.md), [backend/CLAUDE.md](backend/CLAUDE.md) and [web/CLAUDE.md](web/CLAUDE.md).

| Folder / file | What's in it |
|---|---|
| `backend/annotator/` | The API and worker, one folder per feature (projects, classes, images, labels, jobs, engines, health, export, ...) |
| `backend/db/migration/` | The database tables (Flyway SQL files) |
| `backend/.env.example` | Template for `backend/.env` (Supabase key, Gemini key, Claude and Ollama settings) |
| `web/src/` | The web app, one folder per feature |
| `supabase/config.toml` | The local Supabase stack (its own ports, 55320-55329) |
| `docker-compose.yml` | Flyway, which applies the migrations |
| `classes.example.txt` | Example class list for **Import dataset** |
