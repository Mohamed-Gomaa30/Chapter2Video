import json
import os
from typing import List, Dict, Union
from dotenv import load_dotenv
from pathlib import Path
from src.vprof.models import Lecture, Slide, SlideVisuals
from src.vprof.allocation_agent import AllocationAgent
from src.vprof.orator_agent import OratorAgent

project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(project_root / ".env")

class VProfGenerator:
    def __init__(self, lecture_id: str, title: str):
        self.lecture_id = lecture_id
        self.title = title
        self.allocator = AllocationAgent()
        self.orator = OratorAgent()
        self.slides: List[Slide] = []
        self.slide_counter = 1

    def process_extraction(self, extraction_path: str, index_path: str = None, limit: int = None):
        with open(extraction_path, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            sections = data
        else:
            sections = data.get("sections", [])
            
        chapter_outline = ""
        if index_path and os.path.exists(index_path):
            with open(index_path, 'r') as f:
                chapter_outline = f.read()
        
        if limit:
            sections = sections[:limit]
            
        for section in sections:
            print(f"Processing Section: {section['section_id']} - {section['title']}")
            
            concepts = self.allocator.split_section(
                section['title'], 
                section['text'], 
                section['figures'],
                chapter_outline=chapter_outline,
                current_section_id=section.get("section_id")
            )
            
            is_first_slide = True
            section_bullets_history = []
            
            for concept in concepts:
                previous_context = "\n".join(section_bullets_history)
                
                preferred_format = "SingleText" if is_first_slide else "BulletPoints"
                
                content_result = self.orator.generate_content(
                    concept['concept_title'],
                    concept['text_content'],
                    concept['figure_references'],
                    previous_content=previous_context,
                    preferred_format=preferred_format
                )
                
                if not isinstance(content_result, dict):
                    content_result = {"text": [], "script": str(content_result), "transition": "", "layout_type": "BulletPoints"}
                
                slide_text_list = content_result.get("text", [])
                slide_text_list = self._flatten_text(slide_text_list)
                section_bullets_history.extend(slide_text_list)
                
                figs = concept.get('figure_references', [])
                if not figs:
                    visuals = SlideVisuals(
                        text=slide_text_list if slide_text_list else ["(No text)"],
                        figure_path=None,
                        layout_type=content_result.get("layout_type", "BulletPoints")
                    )
                    self._add_slide(section['title'] if is_first_slide else concept['concept_title'], 
                                   visuals, content_result, is_first_slide)
                    is_first_slide = False
                else:
                    for i, fig in enumerate(figs):
                        fig_path = fig['path'] if isinstance(fig, dict) else fig
                        
                        title = section['title'] if (is_first_slide and i == 0) else concept['concept_title']
                        if i > 0:
                            title = f"{title} (cont.)"
                        
                        visuals = SlideVisuals(
                            text=slide_text_list if i == 0 else [f"Referencing: {os.path.basename(fig_path)}"],
                            figure_path=fig_path,
                            layout_type="Mixed_Horizontal"
                        )
                        self._add_slide(title, visuals, content_result, is_first_slide and i == 0)
                        if i == 0: is_first_slide = False

    def _add_slide(self, title: str, visuals: SlideVisuals, content_result: Dict, is_first: bool):
        slide = Slide(
            slide_idx=self.slide_counter,
            concept=title,
            format=visuals.layout_type,
            visuals=visuals,
            script=content_result.get("script", ""),
            transition=content_result.get("transition", "")
        )
        self.slides.append(slide)
        self.slide_counter += 1

    def _flatten_text(self, text_items: List[Union[str, Dict]]) -> List[str]:
        """Flattens structured content (headings/bullets) from LLM into a string list."""
        flat = []
        for item in text_items:
            if isinstance(item, str):
                flat.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "heading":
                    flat.append(f"**{item.get('text', '')}**")
                elif item.get("type") == "bullet_points":
                    flat.extend(item.get("items", []))
                elif "text" in item:
                    flat.append(str(item["text"]))
                else:
                    flat.append(str(item))
        return flat

    def save(self, output_path: str):
        if self.slides and self.slides[-1].concept != "Conclusion":
            conclusion_visuals = SlideVisuals(
                text=[
                    "Thank you for your attention!",
                    "**Questions?** Feel free to reach out."
                ],
                figure_path=None,
                layout_type="Text_Only"
            )
            conclusion_slide = Slide(
                slide_idx=self.slide_counter,
                concept="Conclusion",
                format="Text_Only",
                visuals=conclusion_visuals,
                script="That concludes our lesson for today. Thank you for your time and attention. I'm happy to answer any questions you may have.",
                transition="End of Lesson"
            )
            self.slides.append(conclusion_slide)
            self.slide_counter += 1

        lecture = Lecture(
            lecture_id=self.lecture_id,
            title=self.title,
            slides=self.slides
        )
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(lecture.model_dump_json(indent=2))
        
        print(f"Lecture saved to {output_path}")

if __name__ == "__main__":
    gen = VProfGenerator("OS_Ch1.1", "Operating System: Chapter 1")
    gen.process_extraction(
        "./data/processed/os/extraction_results.json", 
        index_path="./data/raw/os/chapter1_index.txt",
        limit=3
    )
    gen.save("./data/processed/os/ppt_results.json")
    gen.save("./data/processed/os/ppt_results.json")
