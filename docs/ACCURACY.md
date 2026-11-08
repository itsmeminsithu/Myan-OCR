# OCR evaluation

## Input

The OCR engine supports printed Myanmar and English text in PNG, JPEG and WebP images. Handwriting, complex layouts, low-resolution signs and Zawgyi-rendered text have not been broadly validated.

## Modes

- **Fast:** one Tesseract recognition pass.
- **Balanced:** original and contrast-enhanced passes.
- **Accurate:** multiple preprocessing/layout passes, ranked by heuristics; alternatives are retained.
- **Cloud:** Google Cloud Vision `DOCUMENT_TEXT_DETECTION`, if configured and explicitly selected.

An OCR confidence value is not the probability that every character is correct.

## Measuring quality

Create a dataset of images with manually verified reference text. Include printed pages, screenshots, receipts, camera photographs, mixed-language documents, rotated images and multiple Myanmar fonts.

Character Error Rate (CER) = edit distance between reference and recognized text ÷ reference character count. Record exact-match rate separately. Use a consistent Unicode normalization policy and document whether whitespace is included.

```bash
python scripts/benchmark.py samples/benchmark-synthetic.jsonl
```

The supplied synthetic example previously returned **5.71% CER** and **0/1 exact matches** with local Tesseract. This is not a representative camera benchmark and is not proof of improvement in v0.1.3.

## Capture guidelines

- Keep the camera steady and text in focus.
- Avoid shadows, glare and clipped characters.
- Keep enough image resolution for small Myanmar combining marks.
- Select the known text language when possible.
- Compare alternate recognition passes and correct the output before export.

Optional `tessdata_best` models can be installed with `./scripts/enable-best-models.sh`. Compare measured CER before and after switching models; higher model complexity does not guarantee higher accuracy.
