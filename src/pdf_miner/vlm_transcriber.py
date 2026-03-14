import os
from typing import List
from PIL import Image
from camel.models import ModelFactory
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.types import ModelType, ModelPlatformType

class VLMTranscriber:
    def __init__(self, model_platform: ModelPlatformType = ModelPlatformType.GEMINI, 
                 model_type: ModelType = ModelType.GEMINI_2_0_FLASH):
        self.model = ModelFactory.create(
            model_platform=model_platform,
            model_type=model_type,
        )
        self.agent = ChatAgent(system_message="You are a technical document transcriber.", model=self.model)

    def transcribe_zone(self, image_path: str) -> str:
        """Sends a zone image to the VLM and returns transcribed LaTeX text."""
        prompt = """Transcribe the technical content of this image into a single string.

Formatting: Use $variable$ for inline math and $$equation$$ for standalone block equations.

Precision: Convert subscripts (dtrans), superscripts (1012), and fractions (L/R) accurately into LaTeX.

Exclusion: Ignore page numbers, headers, footers, and side-margin text.

Output: Return ONLY the transcribed text string."""
        
        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content=prompt,
            image_list=[Image.open(image_path)]
        )
        
        response = self.agent.step(user_msg)
        if response.msg is None:
            return ""  # Model returned empty response (e.g. figure-only page)
        return response.msg.content.strip()
    def detect_figures(self, image_path: str) -> str:
        """Prompts the VLM to identify visual-only figure blocks and return JSON coordinates."""
        prompt = """Analyze this image and identify all visual diagrams, illustrations, charts, or figures.
        
        CRITICAL: Your bounding box MUST encompass the ACTUAL visual diagram/drawing content. 
        - Do NOT return a box that only contains a text label or caption.
        - The box SHOULD include both the visual diagram and its associated caption text.
        
        For each figure, return its bounding box in normalized [ymin, xmin, ymax, xmax] format (0-1000).
        
        Return ONLY a JSON list:
        [
          {"caption_hint": "Actual caption text if visible", "bbox": [ymin, xmin, ymax, xmax]},
          ...
        ]
        If no figures are found, return '[]'."""

        
        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content=prompt,
            image_list=[Image.open(image_path)]
        )
        
        response = self.agent.step(user_msg)
        if response.msg is None:
            return "[]"
        return response.msg.content.strip()
