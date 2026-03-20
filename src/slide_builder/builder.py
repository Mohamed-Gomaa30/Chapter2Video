import json
import os
import subprocess
import fitz
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Any, Optional
from .coder_agent import CoderAgent
from camel.models import ModelFactory
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.types import ModelPlatformType, ModelType
from dotenv import load_dotenv

load_dotenv()


class VProfSliderBuilder:
    def __init__(self, output_dir: str, project_root: str = ""):
        self.output_dir = output_dir
        self.project_root = project_root
        self.coder = CoderAgent()
        
        self.vlm_model = ModelFactory.create(
            model_platform=ModelPlatformType.GEMINI,
            model_type=ModelType.GEMINI_3_PRO,
        )
        os.makedirs(output_dir, exist_ok=True)
        self.temp_dir = os.path.join(output_dir, "temp_variants")
        os.makedirs(self.temp_dir, exist_ok=True)

    def generate_preamble(self, title: str, author: str, date: str, affiliation: str) -> str:
        return f"""\\documentclass{{beamer}}
\\usetheme{{Madrid}}
\\usecolortheme{{default}}

% Packages for robust layout and math
\\usepackage{{graphicx}}
\\usepackage{{booktabs}}
\\usepackage{{amsmath}}
\\usepackage{{amsfonts}}
\\usepackage{{amssymb}}
\\usepackage{{listings}}

\\lstset{{
  basicstyle=\\ttfamily\\small,
  breaklines=true,
  frame=single
}}

% Definition for potential hallucinated slide counter macro
\\newcommand{{\\insertslideidx}}{{%
  % This is a fallback definition for the slide index.
}}

\\title{{{title}}}
\\author{{{author}}}
\\institute{{{affiliation}}}
\\date{{{date}}}

\\begin{{document}}

\\begin{{frame}}
  \\titlepage
\\end{{frame}}
"""

    def generate_toc(self, index_path: str) -> str:
        toc_frames = ""
        if os.path.exists(index_path):
            with open(index_path, 'r') as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]

            chunk_size = 10
            for i in range(0, len(lines), chunk_size):
                chunk = lines[i:i + chunk_size]
                toc_frames += "\\begin{frame}\n  \\frametitle{Chapter Outline}\n  \\begin{itemize}\n"
                for line in chunk:
                    item = line.replace("_", "\\_").replace("&", "\\&").replace("%", "\\%")
                    toc_frames += f"    \\item {item}\n"
                toc_frames += "  \\end{itemize}\n\\end{frame}\n"
        else:
            print(f"Index file not found for TOC: {index_path}")
        return toc_frames

    def _strip_animations(self, code: str) -> str:
        """Force-removes all Beamer animation/overlay commands (e.g., \\pause, [<+->], <1->)."""
        import re
        code = code.replace("\\pause", "")
        code = re.sub(r"\[<[^>]+>\]", "", code)
        code = re.sub(r"\\item<[^>]+>", "\\\\item", code)
        code = re.sub(r"\\(only|uncover|visible|invisible|alt|temporal)<[^>]+>", "", code)
        return code

    def _sanitize_latex_data(self, data: Any) -> Any:
        """Recursively escapes special LaTeX characters in all string values."""
        if isinstance(data, str):
            s = data
            if "&" in s and "\\&" not in s: s = s.replace("&", "\\&")
            if "%" in s and "\\%" not in s: s = s.replace("%", "\\%")
            if "_" in s and "\\_" not in s: s = s.replace("_", "\\_")
            return s
        elif isinstance(data, list):
            return [self._sanitize_latex_data(x) for x in data]
        elif isinstance(data, dict):
            return {k: (v if k == "figure_path" else self._sanitize_latex_data(v)) for k, v in data.items()}
        return data

    def build_presentation(self, ppt_json_path: str, index_path: str,
                           professor_name: str = "Virtual Professor",
                           affiliation: str = "V-Prof AI Lab",
                           date: str = "\\today") -> str:
        with open(ppt_json_path, 'r') as f:
            data = json.load(f)

        lecture_title = data.get("title", "Lecture")
        lecture_title = self._sanitize_latex_data(lecture_title)
        self.preamble = self.generate_preamble(lecture_title, professor_name, date, affiliation)
        self.toc = self.generate_toc(index_path)

        slides = data.get("slides", [])
        self.frames = []

        for slide_orig in slides:
            slide = self._sanitize_latex_data(slide_orig)
            print(f"Processing Slide {slide['slide_idx']}: {slide['concept']}")

            visuals = slide.get("visuals", {})
            fig_path_raw = visuals.get("figure_path", "")
            
            fig_path = fig_path_raw
            if self.project_root and fig_path and not os.path.isabs(fig_path):
                fig_path = os.path.join(self.project_root, fig_path)

            if fig_path and os.path.exists(fig_path):
                slide["visuals"]["figure_path"] = os.path.abspath(fig_path)
                print(f"  Figure detected: {slide['visuals']['figure_path']}. Running MSTS-8 VLM layout selection...")
                best_code = self.select_best_layout_with_vlm(slide)
                best_code = self._strip_animations(best_code)
                self.frames.append({"data": slide, "code": best_code})
            else:
                if fig_path_raw:
                    print(f"  WARNING: Figure path not found: {fig_path}")
                frame_code = self.coder.generate_frame(slide)
                frame_code = self._strip_animations(frame_code)
                self.frames.append({"data": slide, "code": frame_code})

        return self._save_and_compile(ppt_json_path)

    # ─────────────────────────────────────────────────────────────────────────
    # Binary MSTS Judge
    # ─────────────────────────────────────────────────────────────────────────
    def select_best_layout_with_vlm(self, slide_data: Dict[str, Any]) -> str:
        """
        Binary selection between Horizontal (A) and Vertical (B).
        Strict geometric and font rules applied via CoderAgent.
        """
        visuals = slide_data.get("visuals", {})
        fig_path = visuals.get("figure_path", "")
        
        if not fig_path or not os.path.exists(fig_path):
            return self.coder.generate_frame(slide_data)

        # 1. Generate 2 variants: A (Horizontal) and B (Vertical)
        labels = ["A", "B", "C", "D"] # Standard labels, but we only use A and B
        variants_code = []
        image_paths = []
        
        bullet_count = len(visuals.get("text", []))
        print(f"    [Binary Choice] Generating 2 variants (A:Horizontal, B:Vertical)...")
        
        # Variant A: Mixed_Horizontal
        hint_a = "layout=Mixed_Horizontal"
        code_a = self.coder.generate_frame(slide_data, variation_hint=hint_a)
        img_a = self._render_variant_to_image(code_a, "A")
        variants_code.append(code_a)
        image_paths.append(img_a)
        print(f"      A (Horizontal): {'OK' if img_a else 'FAILED/OVERFLOW'}")

        # Variant B: Mixed_Vertical
        hint_b = "layout=Mixed_Vertical"
        code_b = self.coder.generate_frame(slide_data, variation_hint=hint_b)
        img_b = self._render_variant_to_image(code_b, "B")
        variants_code.append(code_b)
        image_paths.append(img_b)
        print(f"      B (Vertical): {'OK' if img_b else 'FAILED/OVERFLOW'}")

        slide_idx = slide_data.get('slide_idx', 0)
        grid_path = os.path.join(self.temp_dir, f"binary_grid_{slide_idx}.png")
        self._concat_images_2x1(image_paths[:2], grid_path, labels=["Horizontal (A)", "Vertical (B)"])

        system_prompt = (
            "You are a slide layout judge. You are shown two items:\n"
            "1. Raw Original Figure: The ground truth diagram.\n"
            "2. Candidates: 2x1 Grid showing Slide A (Horizontal/Left) and Slide B (Vertical/Right).\n\n"
            "CRITICAL JUDGING RULES (Strict):\n"
            "1. DISQUALIFY OVERFULL: If any part of the figure or its caption is pushed into the footer (blue bar) or clipped/missing, DISQUALIFY THAT SLIDE.\n"
            "2. DISQUALIFY INFIDELITY: The figure must be complete compared to the Raw Original Figure.\n"
            "3. READABILITY & SIZE: Among survivors, pick the one where the FIGURE IS LARGER AND CLEARER.\n"
            "   - For 1-2 bullets: Slide B (Vertical) is usually much better because the figure can be massive.\n"
            "   - For 3+ bullets: Slide A (Horizontal) is usually safer to avoid cropping.\n"
            "4. SELECTION: Pick the variant with the most 'impactful' and 'visible' figure. Large and centered is best.\n\n"
            "Return ONLY valid JSON: {\"reason\": \"...\", \"choice\": \"A\"|\"B\"}"
        )

        user_prompt = f"Slide has {bullet_count} bullets. Figure fidelity is top priority. Which variant (A or B) is the LARGEST that is 100% visible and NOT cropped?"

        try:
            grid_img = Image.open(grid_path)
            raw_fig_img = Image.open(fig_path)
            user_msg = BaseMessage.make_user_message(role_name="User", content=user_prompt, image_list=[grid_img, raw_fig_img])
            agent = ChatAgent(system_message=system_prompt, model=self.vlm_model)
            response = agent.step(user_msg)
            content = response.msgs[0].content.strip()
            if "{" in content: content = content[content.find("{"):content.rfind("}") + 1]
            result = json.loads(content)
            choice = result.get("choice", "A").upper()
            choice_idx = 0 if choice == "A" else 1
            print(f"    [Binary Choice] Judge chose: {choice} (Reason: {result.get('reason','')})")
            return variants_code[choice_idx]
        except Exception as e:
            print(f"    [Binary Choice] Judge failed: {e}. Defaulting to Horizontal (A).")
            return variants_code[0]

    def _save_and_compile(self, ppt_json_path: str) -> str:
        full_latex = (
            self.preamble + "\n"
            + self.toc + "\n"
            + "\n".join([f['code'] for f in self.frames])
            + "\n\\end{document}"
        )

        tex_filename = os.path.basename(ppt_json_path).replace(".json", ".tex")
        tex_path = os.path.join(self.output_dir, tex_filename)
        with open(tex_path, 'w') as f:
            f.write(full_latex)

        print(f"LaTeX file generated: {tex_path}")
        return tex_path

    def compile_tex(self, tex_path: str, max_retries: int = 3):
        """Attempts to compile the .tex file with a self-correction loop."""
        if not os.path.exists(tex_path):
            print(f"[!] ERROR: .tex file not found: {tex_path}")
            return False

        for attempt in range(max_retries):
            print(f"Compilation Attempt {attempt + 1}...")
            try:
                cmd = [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-output-directory", self.output_dir,
                    tex_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    pdf_path = tex_path.replace(".tex", ".pdf")
                    print(f"Successfully compiled: {pdf_path}")
                    return True

                print(f"Compilation failed on attempt {attempt + 1}. Starting Self-Correction...")
                error_info = self._extract_error_context(result.stdout)
                if not error_info:
                    print("Could not isolate specific error frame. Full log saved.")
                    break

                self._fix_failing_frames(error_info)
                # Rewrite the .tex with corrected frames
                full_latex = (
                    self.preamble + "\n"
                    + self.toc + "\n"
                    + "\n".join([f['code'] for f in self.frames])
                    + "\n\\end{document}"
                )
                with open(tex_path, 'w') as f:
                    f.write(full_latex)

            except FileNotFoundError:
                print("\n[!] ERROR: 'pdflatex' is not installed in this environment.")
                print(f"[!] The LaTeX file has been generated at: {tex_path}")
                print("[!] Download and compile via Overleaf or a local TeX distribution.")
                return False
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                break

        print("Max retries reached. Manual inspection required.")
        return False

    def _extract_error_context(self, log: str) -> List[Dict[str, Any]]:
        """Parses pdflatex log to find which frame/line failed."""
        errors = []
        lines = log.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("!"):
                # Scan ahead up to 5 lines to find the 'l.[line]' indicator
                for j in range(1, 6):
                    if i + j < len(lines) and lines[i + j].strip().startswith("l."):
                        try:
                            # Extract line number from "l.67 \end{frame}"
                            parts = lines[i + j].strip().split()
                            if parts:
                                line_num_str = parts[0][2:] # Strip 'l.'
                                line_num = int(line_num_str)
                                errors.append({"line": line_num, "msg": line})
                                break
                        except Exception:
                            continue
        return errors

    def _fix_failing_frames(self, errors: List[Dict[str, Any]]):
        if errors:
            err = errors[0]
            print(f"Attempting to fix error at line {err['line']}: {err['msg']}")
            for frame in self.frames:
                new_code = self.coder.correct_frame(frame['code'], err['msg'])
                frame['code'] = new_code


if __name__ == "__main__":
    project_root = "/teamspace/studios/this_studio/.lightning_studio/Chapter2Video"
    output_dir = os.path.join(project_root, "assets/os/")
    json_path = os.path.join(project_root, "data/processed/os/ppt_results.json")
    index_path = os.path.join(project_root, "data/raw/os/chapter1_index.txt")

    print(f"Checking index path: {index_path} -> {'Exists' if os.path.exists(index_path) else 'NOT FOUND'}")

    builder = VProfSliderBuilder(output_dir, project_root=project_root)

    if os.path.exists(json_path):
        tex = builder.build_presentation(json_path, index_path)
        print(f"LaTeX generation complete: {tex}")
        builder.compile_tex(tex)
    else:
        print(f"JSON not found: {json_path}")
