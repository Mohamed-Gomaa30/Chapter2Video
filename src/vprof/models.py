from pydantic import BaseModel
from typing import List, Optional, Union

class SlideVisuals(BaseModel):
    text: List[str]
    figure_path: Optional[str] = None
    layout_type: str = "Standard" # Mixed, SingleText, BulletPoints

class Slide(BaseModel):
    slide_idx: int
    concept: str
    format: str
    visuals: SlideVisuals
    script: str
    transition: Optional[str] = None

class Lecture(BaseModel):
    lecture_id: str
    title: str
    slides: List[Slide]
