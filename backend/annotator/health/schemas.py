from annotator.common.schemas import ApiModel


class HealthSummary(ApiModel):
    images: int
    labeled: int
    boxes: int
    avg_boxes_per_image: float
    classes: int
    classes_with_data: int
    imbalance_ratio: float  # most boxes / fewest boxes, over classes that have any (0 when none do)
    status: dict[str, int]  # only the statuses present


class ClassHealth(ApiModel):
    index: int
    name: str
    boxes: int
    images: int
    avg_area_pct: float
    warn: str
    image_ids: list[int]


class SizeBucket(ApiModel):
    key: str
    label: str
    count: int


class HealthIssue(ApiModel):
    key: str
    label: str
    count: int
    image_ids: list[int]


class HealthReport(ApiModel):
    summary: HealthSummary
    classes: list[ClassHealth]
    sizes: list[SizeBucket]
    heatmap: list[list[int]]  # rows top to bottom: how many box centres fall in each cell
    issues: list[HealthIssue]
    low_count: int
