from camel.models import ModelFactory
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.types import ModelPlatformType, ModelType
from typing import Dict, Any
import json
import os


class CoderAgent:
    def __init__(self, model_platform: ModelPlatformType = ModelPlatformType.GEMINI,
                 model_type: ModelType = ModelType.GEMINI_2_5_PRO):
        self.model = ModelFactory.create(
            model_platform=model_platform,
            model_type=model_type,
        )
        self.system_message = (
            "You are a LaTeX Beamer Expert (The Coder Agent). "
            "Your task is to generate high-quality LaTeX Beamer code for a SINGLE slide based on the provided JSON data.\n\n"
            "**CORE DESIGN PRINCIPLES (Professional Aesthetics)**:\n"
            "1. **Modern Cleanliness**: Use standard beamer components (itemize, columns) but keep whitespace balanced.\n"
            "2. **Density & Readability**: NEVER split a slide into multiple frames. If a slide contains a FIGURE and 3 or MORE bullet points, you MUST use `\\footnotesize`. Otherwise, if there are 3 or more bullets (no figure), use `\\small`. If there are 6 or more bullets, ALWAYS use `\\footnotesize`. Everything MUST fit on exactly ONE page.\n"
            "3. **Mandatory Bottom Margin**: To avoid colliding with the beamer footer (the blue info bar), you MUST leave a clear gap (at least 0.5cm - 1.0cm) of empty space at the very bottom of the frame. Neither text nor figures should ever touch the footer.\n"
            "3. **Math Support**: The input data may contain `$` or `$$` symbols. These indicate LaTeX math. You MUST treat them as LaTeX math commands; DO NOT escape them with backslashes. For example, `$$E=mc^2$$` should remain exactly as is in the LaTeX code.\n"
            "4. **Visual Hierarchy**: Ensure a small vertical gap (e.g. `\\vspace{0.3em}`) between the slide title and the content to avoid collisions with the title bar.\n"
            "4. **Color Contrast**: Ensure text colors (including alerts) have high contrast against the background; avoid red-on-blue or dark-on-dark combinations.\n"
            "5. **Visual Excellence**: Ensure the figure is as large as possible without overflowing.\n\n"
            "**CRITICAL RULES (MUST NOT VIOLATE)**:\n"
            "1. **Single Frame Only**: You MUST generate exactly ONE `\\begin{frame}...\\end{frame}` block. "
            "FORBIDDEN frame options: `[allowframebreaks]`, `[t,allowframebreaks]`, or ANY option that causes content to spill across pages. "
            "ALL bullets provided in the JSON MUST appear together in one single frame. "
            "If content is too long, shrink font size to `\\footnotesize` — NEVER break the frame.\n"
            "2. **Text Preservation**: Copy the 'content' b ullet points from the JSON EXACTLY — no rephrasing or summarization.\n"
            "3. **Highlighting**: Use `\\alert{...}` to highlight 2-5 key technical terms per slide.\n"
            "4. **Output Only**: Return ONLY the LaTeX code. No markdown fences.\n\n"
            "**LAYOUT GUIDELINES** (Obey `variation_hint` if Scale/Layout is specified):\n\n"
            "Layout: Conclusion (Centered Text)\n"
            "- Structure: Use \\vfill, then \\centering, then large bold text, then \\vfill.\n"
            "- Content: Usually 'Thank You' and contact info. No bullets.\n\n"
            "Layout: Title (Title Page)\n"
            "- Structure: Simply \\titlepage within a frame.\n\n"
            "Layout: Mixed_Horizontal (Side-by-Side)\n"
            "- Structure: \\begin{columns}[onlytextwidth,T] with {0.4\\textwidth} for text and {0.57\\textwidth} for figure.\n"
            "- Figure: \\includegraphics[width=0.57\\textwidth,height=0.85\\textheight,keepaspectratio]{<path>}. (Prioritize figure prominence).\n\n"
            "Layout: Mixed_Vertical (Top-Text, Bottom-Figure)\n"
            "- Structure: \\vspace{-1.5em} (reclaim top space), then Text itemize block, then \\vfill, then \\centering, then Figure.\n"
            "- Figure: \\includegraphics[width=0.9\\textwidth,height=<H>\\textheight,keepaspectratio]{<path>}. \n"
            "  * If bullets == 1: use height=0.6\\textheight (Max clarity for sparse text).\n"
            "  * If bullets == 2: use height=0.45\\textheight.\n"
            "  * If bullets >= 3: use height=0.4\\textheight (MANDATORY for safety; works well with \\footnotesize).\n"
            "  (Absolute zero collision with footer!).\n\n"
            "**TECHNICAL REFINEMENTS**:\n"
            "- **ABSOLUTE ANIMATION BAN**: NEVER use `[<+->]`, `\\pause`, `\\only`, `\\uncover`, "
            "or ANY overlay/animation specification whatsoever. Sequential keywords in the script "
            "('First...', 'Next...', 'Then...', 'Finally...') are speaker cues ONLY — they do NOT "
            "trigger animations or separate slides. Everything MUST appear on ONE single PDF page "
            "with zero exceptions. There is no condition under which animations are acceptable.\n"
            "- **IGNORE TRANSITIONS**: The `transition` field in the JSON data is for the speaker; you MUST NOT include it in the LaTeX frame (no footline notes, no text boxes, no hidden commands for it).\n"
            "- **CHARACTER ESCAPING**: ALWAYS escape special LaTeX characters in the 'concept' (title) and 'visuals/text' bullets unless they are part of a deliberate LaTeX command. Specifically: `&` MUST be `\\&`, `%` MUST be `\\%`, `$` MUST be `\\$`, `#` MUST be `\\#`, `_` MUST be `\\_`. \n"
            "- **FILE PATH EXEMPTION**: NEVER escape ANY special characters in the `figure_path` (the argument to `\\includegraphics`). Filenames containing `_` MUST be left exactly as is (e.g., `Figure_1.png` — NOT `Figure\\_1.png`). Escaping underscores in filenames will cause the figure to fail to load.\n"
            "- **NO HALLUCINATED MACROS**: NEVER use commands that are not defined in standard Beamer or specifically provided in the prompt. For example, DO NOT use `\\insertslideidx`; if you need a title, use only the provided 'concept' field.\n"
            "- Ensure all environments (itemize, columns, center) are closed correctly."
        )

    def generate_frame(self, slide_data: Dict[str, Any], variation_hint: str = "") -> str:
        agent = ChatAgent(system_message=self.system_message, model=self.model)

        bullet_count = len(slide_data.get("visuals", {}).get("text", []))

        hint_block = f"VARIATION HINT (overrides layout_type from JSON if specified):\n{variation_hint}\n\n" if variation_hint else ""
        prompt = (
            f"{hint_block}"
            f"SLIDE DATA:\n{json.dumps(slide_data, indent=2)}\n\n"
            f"IMPORTANT: This slide has exactly {bullet_count} bullets. ALL {bullet_count} bullets MUST appear "
            f"in ONE single frame — no exceptions. Use \\footnotesize if needed to fit everything. "
            f"No animations, no \\pause, no overlays, no frame breaks.\n\n"
            "Generate the LaTeX Beamer code for this frame. Remember: output ONLY \\begin{frame}...\\end{frame}."
        )

        user_msg = BaseMessage.make_user_message(role_name="User", content=prompt)
        response = agent.step(user_msg)

        return self._clean_output(response.msgs[0].content)

    def correct_frame(self, original_code: str, error_log: str) -> str:
        """Self-Correction Loop: Fixes LaTeX code based on compilation error info."""
        agent = ChatAgent(system_message=self.system_message, model=self.model)

        prompt = (
            "The following LaTeX Beamer code failed to compile:\n\n"
            f"CODE:\n{original_code}\n\n"
            f"ERROR LOG:\n{error_log}\n\n"
            "Please fix the errors and return ONLY the corrected `\\begin{frame}...\\end{frame}` block. "
            "Do NOT change any text content, only fix the LaTeX syntax. "
            "Do NOT add animations, overlays, or split the frame — keep all content in ONE frame."
        )

        user_msg = BaseMessage.make_user_message(role_name="User", content=prompt)
        response = agent.step(user_msg)

        return self._clean_output(response.msgs[0].content)

    def _clean_output(self, content: str) -> str:
        if "```latex" in content:
            content = content.split("```latex")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        if "\\begin{frame}" in content:
            content = content[content.find("\\begin{frame}"):]
        if "\\end{frame}" in content:
            content = content[:content.rfind("\\end{frame}") + len("\\end{frame}")]
        
        import re
        content = content.replace("\\pause", "")
        content = re.sub(r"\[<[^>]+>\]", "", content)
        content = re.sub(r"\\item<[^>]+>", "\\\\item", content)
        content = re.sub(r"\\(only|uncover|visible|invisible|alt|temporal)<[^>]+>", "", content)
        
        return content.strip()