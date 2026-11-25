/**
 * The engines the bar offers, like today's top bar. Per engine:
 * `choices` a fixed model list ([value, text]); `models` suggestions you can type over (replaced by what the worker
 * found); `grid` can draw the 0-1000 grid; `threshold` a detector's default minimum confidence; `takesExtra` extra
 * instructions; `supportsRefine` can review its own boxes (VLMs only).
 */
export const ENGINES = [
  {
    value: 'gemini',
    label: 'Gemini (API key)',
    modelLabel: 'Gemini model',
    defaultModel: 'gemini-3.5-flash-lite',
    models: ['gemini-3.5-flash-lite', 'gemini-3.5-flash'],
    takesExtra: true,
    supportsRefine: true,
  },
  {
    value: 'claude',
    label: 'Claude (your plan)',
    modelLabel: 'Claude model',
    defaultModel: 'sonnet',
    choices: [['sonnet', 'Sonnet'], ['haiku', 'Haiku'], ['opus', 'Opus']],
    grid: true,
    takesExtra: true,
    supportsRefine: true,
  },
  {
    value: 'ollama',
    label: 'Local VLM (Ollama)',
    modelLabel: 'Ollama model',
    defaultModel: 'qwen3-vl:4b',
    models: ['qwen3-vl:4b'],
    grid: true,
    takesExtra: true,
    supportsRefine: true,
  },
  {
    value: 'grounding_dino',
    label: 'Grounding DINO',
    modelLabel: 'Grounding DINO size',
    defaultModel: 'IDEA-Research/grounding-dino-tiny',
    choices: [['IDEA-Research/grounding-dino-tiny', 'tiny'], ['IDEA-Research/grounding-dino-base', 'base (more VRAM)']],
    threshold: 0.35,
    supportsRefine: false,
  },
  {
    value: 'yolo_world',
    label: 'YOLO-World / YOLOE',
    modelLabel: 'YOLO weights',
    defaultModel: 'yolov8s-worldv2.pt',
    models: ['yolov8s-worldv2.pt', 'yoloe-11s-seg.pt'],
    threshold: 0.25,
    supportsRefine: false,
  },
];

export const engineInfo = (value) => ENGINES.find((e) => e.value === value) ?? ENGINES[0];

export const REFINE_NEEDS_VLM = 'Refine needs Gemini, Claude or a local VLM (Ollama); detectors only find boxes';

/** The options a job for the chosen engine is sent: only what that engine takes. */
export function engineOptions(settings) {
  const info = engineInfo(settings.engine);
  const options = { model: settings.model };
  if (info.takesExtra) options.extra = settings.extra ?? '';
  if (info.grid) options.grid = Boolean(settings.grid);
  if (info.threshold !== undefined) options.threshold = settings.threshold ?? info.threshold;
  return options;
}
