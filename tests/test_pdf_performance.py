import io
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PIL import Image

from tools.pdf_performance import (
    contiguous_page_runs,
    insert_pdf_pages,
    pixmap_to_png,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PDFPerformanceTests(unittest.TestCase):
    def test_pdf_to_png_defaults_zoom_to_one_in_python_and_yaml(self):
        python_source = (PROJECT_ROOT / "tools/pdf_to_png.py").read_text()
        yaml_source = (PROJECT_ROOT / "tools/pdf_to_png.yaml").read_text()

        self.assertIn(
            "zoom = 1 if zoom_param is None else int(zoom_param)", python_source
        )
        self.assertRegex(yaml_source, r"(?m)^  default: 1$")

    def test_pixmap_to_png_preserves_dimensions_and_format(self):
        document = pymupdf.open()
        page = document.new_page(width=40, height=30)
        page.draw_rect(page.rect, fill=(1, 0, 0))
        pixmap = page.get_pixmap(alpha=False)

        png_bytes = pixmap_to_png(pixmap)

        with Image.open(io.BytesIO(png_bytes)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (40, 30))

        document.close()

    def test_pixmap_to_png_uses_memoryview_and_compression_level_two(self):
        samples = memoryview(bytes([255, 0, 0]))

        class Pixmap:
            width = 1
            height = 1
            samples_mv = samples

        class EncodedImage:
            def save(self, output, *, format, compress_level):
                self.format = format
                self.compress_level = compress_level
                output.write(b"png")

        encoded_image = EncodedImage()
        with patch(
            "tools.pdf_performance.Image.frombuffer", return_value=encoded_image
        ) as frombuffer:
            self.assertEqual(pixmap_to_png(Pixmap()), b"png")

        self.assertIs(frombuffer.call_args.args[2], samples)
        self.assertEqual(encoded_image.format, "PNG")
        self.assertEqual(encoded_image.compress_level, 2)

    def test_contiguous_page_runs_preserve_gaps_reverse_order_and_duplicates(self):
        self.assertEqual(
            contiguous_page_runs([0, 1, 2, 4, 3, 3, 6, 7]),
            [(0, 2), (4, 4), (3, 3), (3, 3), (6, 7)],
        )

    def test_insert_pdf_pages_reuses_objects_until_last_run(self):
        class Output:
            def __init__(self):
                self.calls = []

            def insert_pdf(self, source, **kwargs):
                self.calls.append((source, kwargs))

        source = object()
        output = Output()

        insert_pdf_pages(output, source, [0, 1, 3, 2, 2])

        self.assertEqual(
            output.calls,
            [
                (source, {"from_page": 0, "to_page": 1, "final": 0}),
                (source, {"from_page": 3, "to_page": 3, "final": 0}),
                (source, {"from_page": 2, "to_page": 2, "final": 0}),
                (source, {"from_page": 2, "to_page": 2, "final": 1}),
            ],
        )

    def test_insert_pdf_pages_preserves_real_pdf_page_order_and_duplicates(self):
        source = pymupdf.open()
        for label in ("A", "B", "C"):
            page = source.new_page()
            page.insert_text((72, 72), label)
        output = pymupdf.open()

        insert_pdf_pages(output, source, [0, 1, 2, 1, 1, 0])

        self.assertEqual(
            [page.get_text().strip() for page in output],
            ["A", "B", "C", "B", "B", "A"],
        )

        output.close()
        source.close()


if __name__ == "__main__":
    unittest.main()
