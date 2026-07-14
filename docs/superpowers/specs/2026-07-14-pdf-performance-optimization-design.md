# PDF Performance Optimization Design

## Goal

Reduce PDF page extraction and PDF-to-PNG execution time, peak memory use, and
unnecessary output growth without adding operational limits or new production
dependencies.

## Compatibility Contract

- Change the PDF-to-PNG default `zoom` from `2` to `1` in both the Python
  runtime parameter and the tool YAML definition.
- Continue accepting an explicitly supplied `zoom`, including `2`, with the
  existing integer conversion behavior.
- Preserve PNG format, filenames, page order, page count, and rendered visual
  content for a given zoom. PNG binary bytes and compression metadata may
  differ.
- Preserve extracted PDF page order and duplicate pages exactly as requested.
- Do not add page-count, pixel-count, file-size, timeout, concurrency, or other
  processing limits.
- Do not add new user-facing parameters or production dependencies.

## Implementation Design

### PDF-to-PNG

Keep Pillow as the PNG encoder because local benchmarks show that PyMuPDF's
direct PNG encoder is slower at `zoom=2` for both text and scan-like pages.
Pass `Pixmap.samples_mv` into Pillow instead of materializing `Pixmap.samples`
as an intermediate `bytes` object. Encode losslessly with PNG compression level
`2`, which keeps image pixels unchanged while reducing CPU time in the measured
samples. Keep the pixmap alive until encoding completes.

Open the source PDF directly from the Dify file blob rather than wrapping the
blob in another `BytesIO`. Continue yielding one blob message per page so output
ordering and streaming behavior remain unchanged.

### PDF Extraction

Open source PDFs directly from the input blob. For multi-page extraction,
convert the ordered page-index sequence into maximal contiguous ascending runs.
Insert each run with one `Document.insert_pdf` call. Set `final=0` on every call
except the last call, which uses `final=1`, so PyMuPDF reuses already-copied
fonts, images, and other shared PDF objects. This must preserve arbitrary order
and duplicates: for example, `1,2,3,5,4,4` becomes runs `1-3`, `5`, `4`, `4`.

For single-page extraction there is only one insertion, so `final=1` remains
the correct behavior.

### Resource Declaration

Raise `resource.memory` from `1048576` bytes (1 MiB) to `268435456` bytes
(256 MiB). This changes the declared execution resource requirement only; it
does not impose a new application-level processing limit.

## Error Handling

Preserve the existing validation and exception messages. Resource cleanup will
use context managers where practical, without changing user-visible errors.
Optimization helpers must not silently reorder, deduplicate, or discard pages.

## Testing

Add unit tests that prove:

- the default zoom is `1` in Python and YAML;
- explicit zoom values still control output dimensions;
- PNG output remains valid RGB PNG data with the expected dimensions, filename,
  count, and page order;
- the encoder consumes the pixmap memory view and uses compression level `2`;
- contiguous pages are grouped while gaps, reverse order, and duplicates are
  preserved;
- all multi-page insertion calls except the last use `final=0`;
- the last insertion uses `final=1`;
- the manifest declares 256 MiB of memory.

Performance timing will be checked with a repeatable local benchmark and
reported separately. Wall-clock thresholds will not be added to unit tests
because they are environment-dependent.

## Expected Impact

With the new default `zoom=1`, A4 output dimensions change from approximately
`1190 x 1684` to `595 x 842`. Pixel count and raw RGB memory fall by 75%; local
text and scan-like samples rendered and encoded about four times faster.

For callers that explicitly retain `zoom=2`, lossless compression and memory
copy optimizations measured roughly 10-20% faster per-page encoding and remove
one full raw RGB intermediate buffer. Multi-page extraction gains depend on PDF
resource sharing; documents with shared images or fonts benefit the most.
