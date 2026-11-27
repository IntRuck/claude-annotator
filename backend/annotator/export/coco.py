"""COCO JSON, moved from today's app.export_coco: category id = class index, pixel boxes [x, y, w, h] rounded to
2 decimals. The image id is the image's position in the project's whole list (from 1), like today.
Outlines add `segmentation` (the dots in pixels) and make `area` the outline's area."""
from annotator.export.pick import Picked
from annotator.export.schemas import Shape
from annotator.label.rules import outline_area


def build(classes: list[tuple[int, str]], picked: list[Picked], shape: Shape = "boxes") -> dict:
    result = {"images": [], "annotations": [], "categories": [{"id": index, "name": name} for index, name in classes]}
    for p in picked:
        width, height = p.image.width, p.image.height
        result["images"].append({"id": p.number, "file_name": p.image.file_name, "width": width, "height": height})
        for b in p.boxes:
            x, y = b["x1"] * width, b["y1"] * height
            w, h = (b["x2"] - b["x1"]) * width, (b["y2"] - b["y1"]) * height
            annotation = {
                "id": len(result["annotations"]) + 1, "image_id": p.number, "category_id": b["cls"],
                "bbox": [round(x, 2), round(y, 2), round(w, 2), round(h, 2)], "area": round(w * h, 2), "iscrowd": 0,
            }
            if shape == "outlines":
                annotation["segmentation"] = [[round(v, 2) for px, py in b["points"] for v in (px * width, py * height)]]
                annotation["area"] = round(outline_area(b["points"]) * width * height, 2)
            result["annotations"].append(annotation)
    return result
