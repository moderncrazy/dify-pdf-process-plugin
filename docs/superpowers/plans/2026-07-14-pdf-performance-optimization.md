# PDF Performance Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PDF-to-PNG and selected-page extraction faster and less memory-intensive while preserving the approved compatibility contract.

**Architecture:** Add a small `tools/pdf_performance.py` module for independently testable encoding and page-copy primitives. Existing Dify tool classes keep their public interfaces and delegate only the performance-sensitive operations to those helpers.

**Tech Stack:** Python 3.12, `unittest`, PyMuPDF 1.26.x, Pillow 12.x, Dify Plugin SDK 0.3-0.5.

## Global Constraints

- Default PDF-to-PNG `zoom` changes from `2` to `1`; explicit zoom values keep the existing integer conversion behavior.
- PNG format, filenames, page order, and page count remain unchanged; compressed bytes may differ.
- Extracted PDF page order and duplicate pages remain exactly as requested.
- Do not add page-count, pixel-count, file-size, timeout, concurrency, or other processing limits.
- Do not add user-facing parameters or production dependencies.
- Keep Pillow as the PNG encoder and use lossless PNG compression level `2`.

---

### Task 1: Add Tested Performance Primitives

**Files:**
- Create: `tools/pdf_performance.py`
- Create: `tests/__init__.py`
- Create: `tests/test_pdf_performance.py`

**Interfaces:**
- Produces: `pixmap_to_png(pixmap: Any) -> bytes`
- Produces: `contiguous_page_runs(indices: list[int]) -> list[tuple[int, int]]`
- Produces: `insert_pdf_pages(output: Any, source: Any, indices: list[int]) -> None`

- [ ] **Step 1: Write failing tests for PNG encoding**

```python
import io
import unittest
from unittest.mock import patch

import pymupdf
from PIL import Image

from tools.pdf_performance import pixmap_to_png


class PDFPerformanceTests(unittest.TestCase):
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
        with patch("tools.pdf_performance.Image.frombuffer", return_value=encoded_image) as frombuffer:
            self.assertEqual(pixmap_to_png(Pixmap()), b"png")

        self.assertIs(frombuffer.call_args.args[2], samples)
        self.assertEqual(encoded_image.format, "PNG")
        self.assertEqual(encoded_image.compress_level, 2)
```

- [ ] **Step 2: Run the PNG tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_pdf_performance.PDFPerformanceTests -v`

Expected: `ERROR` with `ModuleNotFoundError: No module named 'tools.pdf_performance'`.

- [ ] **Step 3: Write failing tests for ordered page runs and final flags**

```python
from tools.pdf_performance import contiguous_page_runs, insert_pdf_pages


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
```

- [ ] **Step 4: Run the page-copy tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_pdf_performance.PDFPerformanceTests -v`

Expected: import failure for the missing page-run functions.

- [ ] **Step 5: Implement the minimal performance primitives**

```python
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
    runs = []
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
```

- [ ] **Step 6: Run the helper tests and verify GREEN**

Run: `.venv/bin/python -m unittest tests.test_pdf_performance -v`

Expected: all helper tests pass.

- [ ] **Step 7: Commit the primitives**

```bash
git add tools/pdf_performance.py tests/__init__.py tests/test_pdf_performance.py
git commit -m "perf: add efficient PDF processing primitives"
```

### Task 2: Optimize PDF-to-PNG and Change the Default Zoom

**Files:**
- Modify: `tools/pdf_to_png.py:1-105`
- Modify: `tools/pdf_to_png.yaml:35-46`
- Modify: `tests/test_pdf_performance.py`

**Interfaces:**
- Consumes: `pixmap_to_png(pixmap: Any) -> bytes`
- Produces: unchanged `PDFToPNGTool._invoke(...)` message stream

- [ ] **Step 1: Add failing configuration tests**

```python
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pdf_to_png_defaults_zoom_to_one_in_python_and_yaml(self):
    python_source = (PROJECT_ROOT / "tools/pdf_to_png.py").read_text()
    yaml_source = (PROJECT_ROOT / "tools/pdf_to_png.yaml").read_text()

    self.assertIn("zoom = 1 if zoom_param is None else int(zoom_param)", python_source)
    self.assertRegex(yaml_source, r"(?m)^  default: 1$")
```

- [ ] **Step 2: Run the configuration test and verify RED**

Run: `.venv/bin/python -m unittest tests.test_pdf_performance.PDFPerformanceTests.test_pdf_to_png_defaults_zoom_to_one_in_python_and_yaml -v`

Expected: failure because both defaults are still `2`.

- [ ] **Step 3: Delegate PNG encoding and remove the source-buffer copy**

Update `tools/pdf_to_png.py` to import `pixmap_to_png`, use the default below,
open from the original blob, and pass the encoded bytes directly to Dify:

```python
from tools.pdf_performance import pixmap_to_png

zoom = 1 if zoom_param is None else int(zoom_param)
doc = pymupdf.open(stream=pdf_content.blob, filetype="pdf")

pix = page.get_pixmap(matrix=mat, alpha=False)
png_bytes = pixmap_to_png(pix)
yield self.create_blob_message(
    blob=png_bytes,
    meta={"mime_type": "image/png", "file_name": output_filename},
)
```

Remove the no-longer-used `io` and `PIL.Image` imports from this tool file.
Change both runtime and YAML parameter defaults and descriptions from `2` to
`1`.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `.venv/bin/python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 5: Commit PDF-to-PNG optimization**

```bash
git add tools/pdf_to_png.py tools/pdf_to_png.yaml tests/test_pdf_performance.py
git commit -m "perf: reduce PDF-to-PNG rendering overhead"
```

### Task 3: Optimize Selected-Page PDF Extraction

**Files:**
- Modify: `tools/pdf_multi_pages_extractor.py:1-201`
- Modify: `tools/pdf_single_page_extractor.py:1-114`
- Test: `tests/test_pdf_performance.py`

**Interfaces:**
- Consumes: `insert_pdf_pages(output: Any, source: Any, indices: Sequence[int]) -> None`
- Produces: unchanged PDF blob message content and naming behavior

- [ ] **Step 1: Add a failing production-integration test**

```python
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
```

- [ ] **Step 2: Run the integration tests and verify RED**

Run: `.venv/bin/python -m unittest tests.test_pdf_performance.PDFPerformanceTests.test_multi_page_tool_uses_optimized_ordered_insertion tests.test_pdf_performance.PDFPerformanceTests.test_extractors_open_the_original_blob_directly -v`

Expected: failures because the tools still contain per-page loops and `BytesIO`
source wrappers.

- [ ] **Step 3: Integrate optimized insertions and direct blob opening**

Update the multi-page tool:

```python
from tools.pdf_performance import insert_pdf_pages

doc = pymupdf.open(stream=pdf_content.blob, filetype="pdf")
selected_page_indices = fixed_page_indices + dynamic_page_indices
insert_pdf_pages(output, doc, selected_page_indices)
```

Remove the two old per-page insertion loops and unused source `BytesIO`. Update
the single-page tool to open `pdf_content.blob` directly while retaining its
single `insert_pdf` call and output buffer.

- [ ] **Step 4: Run extraction tests and verify GREEN**

Run: `.venv/bin/python -m unittest discover -s tests -v`

Expected: all tests pass, including order and duplicate preservation.

- [ ] **Step 5: Commit extraction optimization**

```bash
git add tools/pdf_multi_pages_extractor.py tools/pdf_single_page_extractor.py tests/test_pdf_performance.py
git commit -m "perf: reuse resources when extracting PDF pages"
```

### Task 4: Correct Resource Declaration and Verify the Whole Change

**Files:**
- Modify: `manifest.yaml:24-31`
- Modify: `tests/test_pdf_performance.py`

**Interfaces:**
- Produces: plugin manifest requesting exactly `268435456` bytes of memory

- [ ] **Step 1: Add a failing manifest test**

```python
def test_manifest_declares_256_mib_of_memory(self):
    manifest = (PROJECT_ROOT / "manifest.yaml").read_text()
    self.assertRegex(manifest, r"(?m)^  memory: 268435456$")
```

- [ ] **Step 2: Run the manifest test and verify RED**

Run: `.venv/bin/python -m unittest tests.test_pdf_performance.PDFPerformanceTests.test_manifest_declares_256_mib_of_memory -v`

Expected: failure because the manifest still declares `1048576`.

- [ ] **Step 3: Raise the declared memory**

```yaml
resource:
  memory: 268435456
```

- [ ] **Step 4: Run complete automated verification**

Run: `.venv/bin/python -m unittest discover -s tests -v`

Expected: all tests pass with no warnings or errors.

Run: `.venv/bin/python -m compileall -q main.py provider tools tests`

Expected: exit code `0` with no output.

Run: `git diff --check`

Expected: exit code `0` with no output.

- [ ] **Step 5: Run the approved benchmark scenarios**

Run an in-memory PyMuPDF/Pillow benchmark for text-like and scan-like A4 pages
at `zoom=1` and `zoom=2`, plus repeated extraction of pages sharing image
resources. Record dimensions, median execution time, output size, and the
current-versus-optimized extraction comparison in the final handoff.

- [ ] **Step 6: Commit resource correction**

```bash
git add manifest.yaml tests/test_pdf_performance.py
git commit -m "perf: request sufficient memory for PDF processing"
```

- [ ] **Step 7: Review final repository state**

Run: `git status --short --branch && git log --oneline -5`

Expected: clean worktree on `main`, ahead of `origin/main` only by the approved
design, plan, and implementation commits.
