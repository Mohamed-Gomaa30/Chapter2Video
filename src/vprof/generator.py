import json
import os
from typing import List, Dict
from dotenv import load_dotenv
from pathlib import Path
from src.vprof.models import Lecture, Slide, SlideVisuals
from src.vprof.allocation_agent import AllocationAgent
from src.vprof.orator_agent import OratorAgent

# Load .env from project root
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
            
        # Read Chapter Outline from index file if provided
        chapter_outline = ""
        if index_path and os.path.exists(index_path):
            with open(index_path, 'r') as f:
                chapter_outline = f.read()
        
        if limit:
            sections = sections[:limit]
            
        for section in sections:
            print(f"Processing Section: {section['section_id']} - {section['title']}")
            
            # 1. Split section into Atomic Concepts with Chapter Context
            concepts = self.allocator.split_section(
                section['title'], 
                section['text'], 
                section['figures'],
                chapter_outline=chapter_outline,
                current_section_id=section.get("section_id")
            )
            
            # 2. Generate content for each concept
            is_first_slide = True
            section_bullets_history = []
            
            for concept in concepts:
                # Pass history of text to avoid repetition
                previous_context = "\n".join(section_bullets_history)
                
                # First slide of section prefers High-Impact SingleText
                preferred_format = "SingleText" if is_first_slide else "BulletPoints"
                
                content_result = self.orator.generate_content(
                    concept['concept_title'],
                    concept['text_content'],
                    concept['figure_references'],
                    previous_content=previous_context,
                    preferred_format=preferred_format
                )
                
                # Update history using the correct 'text' key
                slide_text_list = content_result.get("text", [])
                section_bullets_history.extend(slide_text_list)
                
                # 3. Handle Visuals/Layout
                figure_path = None
                # Trust the agent's choice, but override if figures exist
                suggested_layout = content_result.get("layout_type", "BulletPoints")
                
                if concept['figure_references']:
                    figure_path = concept['figure_references'][0]
                    layout_type = "Mixed_Horizontal"
                else:
                    layout_type = suggested_layout

                visuals = SlideVisuals(
                    text=slide_text_list if slide_text_list else ["(No text)"],
                    figure_path=figure_path,
                    layout_type=layout_type
                )
                
                # First slide of the section gets the Section Title, others get Concept Title
                slide_title = section['title'] if is_first_slide else concept['concept_title']
                is_first_slide = False
                
                slide = Slide(
                    slide_idx=self.slide_counter,
                    concept=slide_title,
                    format=layout_type,
                    visuals=visuals,
                    script=content_result.get("script", ""),
                    transition=content_result.get("transition", "")
                )
                
                self.slides.append(slide)
                self.slide_counter += 1

    def save(self, output_path: str):
        lecture = Lecture(
            lecture_id=self.lecture_id,
            title=self.title,
            slides=self.slides
        )
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(lecture.model_dump_json(indent=2))
        
        print(f"Lecture saved to {output_path}")

if __name__ == "__main__":
    gen = VProfGenerator("networks_ch1", "Computer Networks: Chapter 1")
    gen.process_extraction(
        "./data/processed/os/extraction_results.json", 
        index_path="./data/raw/os/os_chapter1_index.txt",
        limit=3
    )
    gen.save("./data/processed/os/ppt_results.json")
