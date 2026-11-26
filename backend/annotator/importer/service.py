"""Import an existing dataset folder (today's claude-annotator layout or any YOLO dataset) into a project.

Uses the other features only through their services: classes, images and labels.
"""
from pathlib import PurePosixPath

from annotator.classes.service import ClassService
from annotator.image.service import ImageService, UploadedFile
from annotator.importer.parsers import (
    classify,
    parse_annot_state,
    parse_classes_txt,
    parse_data_yaml_names,
    parse_yolo_label,
)
from annotator.importer.schemas import ImportResult
from annotator.label.service import LabelService

STATE_UNREADABLE = "Couldn't read _annot_state.json, so statuses and flags weren't imported."


def _text(f: UploadedFile) -> str:
    return f.content.decode("utf-8-sig", errors="replace")


def _stem(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).stem


class ImportService:
    def __init__(self, images: ImageService, classes: ClassService, labels: LabelService):
        self.images = images
        self.classes = classes
        self.labels = labels

    def import_dataset(self, project_id: int, files: list[UploadedFile]) -> ImportResult:
        existing_classes = self.classes.list_classes(project_id)  # also checks the project exists
        kinds = classify([f.file_name for f in files])
        by_kind: dict[str, list[UploadedFile]] = {}
        for f in files:
            by_kind.setdefault(kinds[f.file_name], []).append(f)
        warnings: list[str] = []

        # 1. Class list: classes.txt first, else data.yaml, and only into a project with no classes yet.
        entries = None
        if by_kind.get("classes"):
            entries = parse_classes_txt(_text(by_kind["classes"][0]))
        elif by_kind.get("yaml"):
            entries = [(name, "", "") for name in parse_data_yaml_names(_text(by_kind["yaml"][0]))]
        kept_existing = bool(entries is not None and existing_classes)
        created = [] if entries is None or kept_existing else self.classes.import_classes(project_id, entries)

        # 2. Images (same rules as a normal upload).
        upload = self.images.upload(project_id, by_kind.get("image", []))

        # 3. Labels, matched to the images just added by file stem.
        labels_by_stem: dict[str, tuple[str, list[dict]]] = {}
        bad_lines = 0
        for f in by_kind.get("label", []):
            boxes, bad = parse_yolo_label(_text(f))
            bad_lines += bad
            labels_by_stem.setdefault(_stem(f.file_name), (f.file_name, boxes))
        matched = [(image, labels_by_stem[_stem(image.file_name)][1])
                   for image in upload.added if _stem(image.file_name) in labels_by_stem]
        used_stems = {_stem(image.file_name) for image, _ in matched}
        without_image = [path for stem, (path, _) in labels_by_stem.items() if stem not in used_stems]

        highest = max((b["cls"] for _, boxes in matched for b in boxes), default=-1)
        placeholders = self.classes.ensure_indexes(project_id, highest) if highest >= 0 else []
        box_total = 0
        for image, boxes in matched:
            box_total += self.labels.replace_boxes(project_id, image.id, boxes, source="import")
            self.images.update_state(image.id, status="auto", note="imported")

        # 4. Today's statuses and flags, when the state file came along.
        states_applied = 0
        if by_kind.get("state"):
            try:
                state = parse_annot_state(_text(by_kind["state"][0]))
            except ValueError:
                state = {}
                warnings.append(STATE_UNREADABLE)
            for image in upload.added:
                entry = state.get(image.file_name)
                if entry is None:
                    continue
                kwargs = {"flagged": entry.flagged, "flag_reason": entry.flag_reason, "flag_note": entry.flag_note}
                if entry.status:
                    kwargs.update(status=entry.status, note=entry.note)
                self.images.update_state(image.id, **kwargs)
                states_applied += 1

        return ImportResult(
            added=len(upload.added), skipped=upload.skipped, labelled=len(matched), boxes=box_total,
            classes_created=created, placeholder_classes=placeholders, kept_existing_classes=kept_existing,
            labels_without_image=without_image, bad_label_lines=bad_lines, states_applied=states_applied,
            ignored_files=[f.file_name for f in by_kind.get("ignored", [])], warnings=warnings,
        )
