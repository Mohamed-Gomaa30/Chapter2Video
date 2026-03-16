# 🎓 Virtual Professor (V-Prof) Pipeline

The **Virtual Professor (V-Prof)** is an advanced multi-agent AI system designed to transform raw textbook content into structured, high-quality, and academically rigorous video lecture materials (PPT JSON).

## 🏗️ Architecture

V-Prof follows an **Instructional Design Pipeline**, treating video generation as a multi-step educational process rather than a simple summarization task.

### 1. Strategic Allocation Agent (The "Dean")
- **Role**: Strategic Lesson Planner.
- **Task**: Analyzes a section within the context of the **Full Chapter Outline**.
- **Logic**: 
    - Decides a **"Concept Budget"** (1 to 4 slides per input section) based on information density.
    - Performs **Vocabulary Spotting**: Explicitly identifies **bold** and *italic* technical terms to ensure they are preserved.
    - **Figure Anchoring**: Uses available figures and their captions as anchors for conceptual splitting.
    - **Input**: Section Raw Text + Figures Meta + Chapter Outline.
    - **Output**: A list of "Atomic Concepts" (Teaching Moments).

### 2. Orator Agent (The "Professor")
- **Role**: Technical Educator.
- **Task**: Generates the final slide text and the explanatory script.
- **Logic**:
    - **Strict Word-for-Word Extraction**: Slide bullets are 100% extractive (no paraphrasing) to maintain textbook fidelity.
    - **Informative Content**: Avoids filler phrases, prioritizing hard facts and key terminology.
    - **History Awareness**: Tracks previous slides to eliminate repetition and ensure a logical internal narrative.
    - **Tone**: Conversational, engaging, and professional (YouTube-style, like Computerphile).
    - **Output**: Technical script, extractive bullets, and smooth transitions.

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- CAMEL-AI framework
- Google Gemini API Key

### Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

## 🛠️ Usage

The main entry point is `src/vprof/generator.py`. It orchestrates the entire flow from PDF extraction results to the final PPT JSON.

```bash
# Ensure your PYTHONPATH includes the src directory
export PYTHONPATH=$PYTHONPATH:. 

# Run the generator
python -m src.vprof.generator
```

## 📄 Data Contract (PPT JSON)

The pipeline produces a structured JSON output (`ppt_results.json`) that can be directly consumed by a frontend renderer or a PPTX automation script.

```json
{
  "lecture_id": "networks_ch1",
  "title": "Computer Networks: Chapter 1",
  "slides": [
    {
      "slide_idx": 1,
      "concept": "Section Title (Intro)",
      "format": "SingleText",
      "visuals": {
        "text": ["Extractive sentence from source..."],
        "figure_path": null,
        "layout_type": "SingleText"
      },
      "script": "Professor's narration...",
      "transition": "Transition to next slide..."
    }
  ]
}
```

## 🎯 Design Principles
- **Fidelity**: 100% extractive slide text ensures no AI-hallucinated technical errors.
- **Engagement**: Scripts are written to feel like a real lecture, not a reading of the textbook.
- **Cohesion**: Using a global chapter index allows the system to understand the context and flow of the entire lesson.
