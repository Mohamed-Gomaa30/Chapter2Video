from pydantic import BaseModel
from typing import List, Optional

class Figure(BaseModel):
    path: str
    caption: Optional[str] = None
    page: int
    bbox: List[float] # [x0, y0, x1, y1]

class Section(BaseModel):
    section_id: str
    title: str
    text: Optional[str] = None
    figures: List[Figure] = []
    page_start: int
    y_start: float
    page_end: Optional[int] = None
    y_end: Optional[float] = None
    level: int
