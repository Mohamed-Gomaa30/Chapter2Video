# V-Prof Slide Builder

The `slide_builder` module is responsible for transforming structured lesson data (JSON) into professional academic Beamer LaTeX presentations. It incorporates Paper2Video-style layout optimization to ensure figures are prominent and legible.

## Core Components

- **`builder.py`**: The orchestration layer. Manages the build pipeline, LaTeX compilation, and the **Binary MSTS Judge**.
- **`coder_agent.py`**: The LaTeX generation sub-agent. Uses a specialized system prompt to generate geometrically constrained Beamer code for different layouts.

## Layout Optimization Strategy

We use a **Binary Strategic Choice** approach for selecting the best layout for each slide:

1. **Variant Generation**: For every slide containing a figure, the system generates two candidate variants:
   - **Horizontal (A)**: Side-by-side with text on the left and a large figure on the right.
   - **Vertical (B)**: Top-down with text above and a maximum-width figure below.
2. **Binary MSTS Judge**: Both variants are rendered into 200 DPI images and presented to a Vision-Language Model (VLM).
3. **Selection Logic**: The VLM selects the layout that provides the **largest visible figure** without causing "Overfull" (overflow) errors or colliding with the slide footer.

## Artifact Generation

The builder produces a complete, modular set of artifacts for downstream video production in the `stage4/` directory:

| Artifact | Location | Description |
| :--- | :--- | :--- |
| **PNG Slides** | `figures/figureSlideN.png` | 300 DPI high-res extraction of every slide from the final PDF. |
| **Speaker TXTs** | `scripts/scriptN.txt` | Individual narration files (VLM for Slide 1-2, Original for 3+). |
| **Mapping JSON** | `ppt_mapping.json` | Master manifest linking each slide to its corresponding image and script. |

## Technical Constraints

- **Dynamic Figure Height**: Vertically stacked figures use variable max-heights (0.4–0.6 `\textheight`) based on bullet count to prevent footer collisions.
- **Font Hierarchy**: Automatically reduces font size from `\small` to `\footnotesize` for dense slides (3+ bullets) to maintain single-slide occupancy.
- **Balanced Horizontal Split**: Uses a `0.4/0.57 \textwidth` split for Horizontal layouts to prioritize figure prominence over text.
