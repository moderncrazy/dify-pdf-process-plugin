import io
from collections.abc import Sequence
from typing import Any

from PIL import Image


def pixmap_to_png(pixmap: Any) -> bytes:
    image = Image.frombuffer(
        "RGB",
        (pixmap.width, pixmap.height),
        pixmap.samples_mv,
        "raw",
        "RGB",
        0,
        1,
    )
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=2)
    return output.getvalue()


def contiguous_page_runs(indices: Sequence[int]) -> list[tuple[int, int]]:
    if not indices:
        return []

    runs: list[tuple[int, int]] = []
    start = end = indices[0]
    for index in indices[1:]:
        if index == end + 1:
            end = index
        else:
            runs.append((start, end))
            start = end = index
    runs.append((start, end))
    return runs


def insert_pdf_pages(output: Any, source: Any, indices: Sequence[int]) -> None:
    runs = contiguous_page_runs(indices)
    for position, (start, end) in enumerate(runs):
        output.insert_pdf(
            source,
            from_page=start,
            to_page=end,
            final=int(position == len(runs) - 1),
        )
