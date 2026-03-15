import os
from typing import List
from PIL import Image
from camel.models import ModelFactory
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.types import ModelType, ModelPlatformType

class VLMTranscriber:
    def __init__(self, model_platform: ModelPlatformType = ModelPlatformType.GEMINI, 
                 model_type: ModelType = ModelType.GEMINI_3_PRO):
        self.model = ModelFactory.create(
            model_platform=model_platform,
            model_type=model_type,
        )
        self.system_message = "You are a technical document transcriber."

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
        
        agent = ChatAgent(system_message=self.system_message, model=self.model)
        response = agent.step(user_msg)
        if response.msg is None:
            return ""  
        return response.msg.content.strip()

    def detect_figures(self, image_path: str) -> str:
        """Prompts the VLM to identify visual-only figure blocks and return JSON coordinates."""
        prompt = """Analyze this image and identify all visual diagrams, illustrations, charts, or technical figures.

        CRITICAL: Identify only units that have ACTUAL visual content like drawings, diagrams, charts, plots, or table structures.
        - DO NOT box items that are PURELY TEXT, even if they are labeled "Figure X.Y" or "Table Z".
        - A figure must be a visually distinct 'ISLAND' containing non-textual elements (lines, boxes, arrows, shapes).
        - IGNORE body text paragraphs and simple section headers.
        - If a visual diagram exists, you MUST include its associated Master Caption in the box.
        - The box must be 'TIGHT' around the visual/caption unit.

        Return ONLY a JSON list of objects, each with "caption_hint" (the text of the label) and "bbox" in normalized [ymin, xmin, ymax, xmax] format (0-1000).
        If no figures are found, return '[]'."""
        
        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content=prompt,
            image_list=[Image.open(image_path)]
        )
        
        # Create a fresh agent for each call to prevent history contamination
        agent = ChatAgent(system_message=self.system_message, model=self.model)
        response = agent.step(user_msg)
        if response.msg is None:
            return "[]"
        return response.msg.content.strip()
