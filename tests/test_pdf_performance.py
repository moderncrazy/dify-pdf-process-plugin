import io
import importlib
import sys
import types
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


def load_pdf_to_png_module():
    class File:
        def __init__(self, blob, filename):
            self.blob = blob
            self.filename = filename

    class Tool:
        def create_blob_message(self, blob, meta):
            return {"type": "blob", "blob": blob, "meta": meta}

        def create_text_message(self, text):
            return {"type": "text", "text": text}

    class ToolParameter:
        class ToolParameterType:
            FILE = "file"
            NUMBER = "number"

        class ToolParameterForm:
            FORM = "form"

    dify_plugin = types.ModuleType("dify_plugin")
    dify_plugin.Tool = Tool
    entities = types.ModuleType("dify_plugin.entities")
    entities.I18nObject = object
    tool_entities = types.ModuleType("dify_plugin.entities.tool")
    tool_entities.ToolInvokeMessage = dict
    tool_entities.ToolParameter = ToolParameter
    file_package = types.ModuleType("dify_plugin.file")
    file_module = types.ModuleType("dify_plugin.file.file")
    file_module.File = File

    modules = {
        "dify_plugin": dify_plugin,
        "dify_plugin.entities": entities,
        "dify_plugin.entities.tool": tool_entities,
        "dify_plugin.file": file_package,
        "dify_plugin.file.file": file_module,
    }
    sys.modules.pop("tools.pdf_to_png", None)
    with patch.dict(sys.modules, modules):
        return importlib.import_module("tools.pdf_to_png")


class PDFPerformanceTests(unittest.TestCase):
    def test_manifest_declares_256_mib_of_memory(self):
        manifest = (PROJECT_ROOT / "manifest.yaml").read_text()
        self.assertRegex(manifest, r"(?m)^  memory: 268435456$")

    def test_multi_page_tool_uses_optimized_ordered_insertion(self):
        source = (PROJECT_ROOT / "tools/pdf_multi_pages_extractor.py").read_text()
        self.assertIn(
            "selected_page_indices = fixed_page_indices + dynamic_page_indices",
            source,
        )
        self.assertIn("insert_pdf_pages(output, doc, selected_page_indices)", source)
        self.assertNotIn("for index in fixed_page_indices", source)
        self.assertNotIn("for index in dynamic_page_indices", source)

    def test_extractors_open_the_original_blob_directly(self):
        for filename in (
            "pdf_multi_pages_extractor.py",
            "pdf_single_page_extractor.py",
        ):
            source = (PROJECT_ROOT / f"tools/{filename}").read_text()
            self.assertIn(
                'pymupdf.open(stream=pdf_content.blob, filetype="pdf")',
                source,
            )

    def test_pdf_to_png_defaults_zoom_to_one_in_python_and_yaml(self):
        python_source = (PROJECT_ROOT / "tools/pdf_to_png.py").read_text()
        yaml_source = (PROJECT_ROOT / "tools/pdf_to_png.yaml").read_text()
        readme = (PROJECT_ROOT / "README.md").read_text()

        self.assertIn(
            "zoom = 1 if zoom_param is None else int(zoom_param)", python_source
        )
        self.assertRegex(yaml_source, r"(?m)^  default: 1$")
        self.assertIn("defaults to 1", readme)

    def test_pdf_to_png_tool_preserves_messages_and_explicit_zoom(self):
        source = pymupdf.open()
        for color in ((1, 0, 0), (0, 0, 1)):
            page = source.new_page(width=40, height=30)
            page.draw_rect(page.rect, fill=color)
        pdf_blob = source.tobytes()
        source.close()

        module = load_pdf_to_png_module()
        tool = module.PDFToPNGTool()
        pdf_file = module.File(pdf_blob, "sample.pdf")

        with patch.object(module.pymupdf, "open", wraps=pymupdf.open) as open_pdf:
            default_messages = list(tool._invoke({"pdf_content": pdf_file}))

        self.assertIs(open_pdf.call_args.kwargs["stream"], pdf_blob)
        self.assertEqual(
            [message["type"] for message in default_messages],
            ["blob", "blob", "text"],
        )
        self.assertEqual(
            [message["meta"]["file_name"] for message in default_messages[:2]],
            ["sample_page1.png", "sample_page2.png"],
        )
        self.assertEqual(
            [
                Image.open(io.BytesIO(message["blob"])).size
                for message in default_messages[:2]
            ],
            [(40, 30), (40, 30)],
        )

        explicit_messages = list(tool._invoke({"pdf_content": pdf_file, "zoom": 2}))
        self.assertEqual(
            [
                Image.open(io.BytesIO(message["blob"])).size
                for message in explicit_messages[:2]
            ],
            [(80, 60), (80, 60)],
        )

    def test_pixmap_to_png_preserves_dimensions_and_format(self):
        document = pymupdf.open()
        page = document.new_page(width=40, height=30)
        page.draw_rect(page.rect, fill=(1, 0, 0))
        pixmap = page.get_pixmap(alpha=False)

        png_bytes = pixmap_to_png(pixmap)
        reference_pixels = bytes(pixmap.samples)

        with Image.open(io.BytesIO(png_bytes)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (40, 30))
            self.assertEqual(image.tobytes(), reference_pixels)

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
