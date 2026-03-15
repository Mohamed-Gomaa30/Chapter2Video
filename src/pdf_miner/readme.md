# PDF Miner: High-Precision Technical Document Extractor

PDF Miner is a multi-modal extraction pipeline designed to convert technical PDFs into structured JSON data. It perfectly combines traditional PDF parsing (PyMuPDF) with the reasoning power of Vision-Language Models (Gemini 3 Pro "highly recommended") to handle complex layouts, diagrams, and math-heavy text.

## Key Features

- **Context-Aware Sectioning**: Automatically splits PDFs based on a provided `index.txt` while intelligently ignoring page margins, folios, and headers to prevent boundary errors.
- **Visual-Centric Figure Extraction**: Uses a **"Visual Anchor"** requirement. Figures are only extracted if real PDF visual objects (vector drawings or raster images) are detected, eliminating text-only hallucinations.
- **Sanitized Union Cropping**: Sophisticated cropping that perfectly captures figures and their associated captions while "cleaning" surrounding body text.
- **LaTeX Transcription**: Transcribes technical text into high-quality LaTeX, supporting complex math, subscripts, and superscripts.
- **Stateless VLM Execution**: Every section is processed by a fresh VLM agent instance, preventing "history bleed" and ensuring zero cross-contamination between sections.
- **Robust Multi-Modal Parsing**: Resilient to various VLM output formats (nested lists, markdown, etc.).

## Usage

Run the main pipeline orchestrator:

```bash
python src/pdf_miner/pdf_pipeline.py \
    --pdf path/to/your_document.pdf \
    --index path/to/index.txt \
    --output ./output_directory \
    --vlm-figures \
    --vlm
```

### Command Line Arguments:
- `--pdf`: Path to the input PDF file.
- `--index`: Path to a text file containing the hierarchical structure of the document.
- `--output`: Directory where results (JSON and Figures) will be saved.
- `--vlm`: Enable VLM text transcription.
- `--vlm-figures`: Enable high-precision VLM figure extraction.

## Project Structure

- `src/pdf_miner/pdf_pipeline.py`: Main execution orchestrator.
- `src/pdf_miner/extractor.py`: Core logic for spatial PDF manipulation and figure "Sanitization."
- `src/pdf_miner/vlm_transcriber.py`: The VLM interface for stateless detection and transcription.
- `src/pdf_miner/models.py`: Pydantic data models for structured output.

## Output

The pipeline generates a JSON file containing:
- Section titles and IDs.
- Transcribed LaTeX text.
- List of extracted figures with their captions, paths, and source bounding boxes.

---
*Developed for high-precision technical communication and presentation automation.*
