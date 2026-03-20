from typing import List, Dict
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelType, ModelPlatformType
import json

class OratorAgent:
    def __init__(self, model_platform: ModelPlatformType = ModelPlatformType.GEMINI, 
                 model_type: ModelType = ModelType.GEMINI_2_5_PRO):
        self.model = ModelFactory.create(
            model_platform=model_platform,
            model_type=model_type,
        )
        self.system_message = (
            "You are a Technical Professor (The Orator Agent). "
            "Your task is to write the script and slide text for an academic video lecture. \n\n"
            "Style Guidelines:\n"
            "1. Academic Rigor: Maintain technical precision. Use LaTeX for math (e.g., `$x^2$` or `$$E=mc^2$$`). These symbols will be preserved by the builder.\n"
            "2. Conversational Flow: Write like a professional YouTube educator (e.g., Computerphile). "
            "Use phrases like 'Let's dive into...', 'Notice on the diagram...', 'This brings us to...'\n"
            "3. Slide Logic (STRICT WORD-FOR-WORD EXTRACTION):\n"
            "   - Slide Format: Choose 'BulletPoints' or 'SingleText'.\n"
            "   - Content Quality: Slide text MUST be **Word-for-Word sentences or phrases** taken directly from the source text. NO Paraphrasing. NO adding words.\n"
            "   - **Vocabulary Priority**: You MUST include bold/italic technical terms from the source on the slide.\n"
            "   - Limit (BulletPoints): Min 3, Max 5 bullets. **Conciseness is CRITICAL**: For slides with figures (Mixed layout), keep each bullet to 1-2 lines maximum to avoid vertical overflow in the Beamer frame.\n"
            "   - Limit (SingleText): Write an informative summary (at most 3 or 4 sentences OR equivalent content).\n"
            "   - DO NOT repeat content from previous slides.\n"
            "4. Script vs. Visuals: The visuals show the exact raw text; the script EXPLAINS them in a friendly, conversational tone.\n"
            "5. Visual Cues: Refer to figures consistently.\n\n"
            "Return JSON: {\"text\": [\"...\"], \"layout_type\": \"...\", \"script\": \"...\", \"transition\": \"...\"}"
        )

    def generate_content(self, concept_title: str, content: str, figures: List[str], 
                         previous_content: str = "", preferred_format: str = None) -> Dict:
        agent = ChatAgent(system_message=self.system_message, model=self.model)
        
        fmt_hint = f"Prefer format: {preferred_format}" if preferred_format else "Choose best format."
        
        prompt = (
            f"Current Slide Heading: {concept_title}\n"
            f"Source Text Content:\n{content}\n"
            f"Figures: {', '.join(figures)}\n"
            f"Previous Slide Context: {previous_content}\n"
            f"Format Hint: {fmt_hint}\n\n"
            "Generate extractive slide text and explanatory script."
        )
        
        user_msg = BaseMessage.make_user_message(role_name="User", content=prompt)
        response = agent.step(user_msg)
        
        if response.msg is None:
            return {}
            
        res_text = response.msg.content
        try:
            if "```json" in res_text:
                res_text = res_text.split("```json")[1].split("```")[0].strip()
            elif "```" in res_text:
                res_text = res_text.split("```")[1].split("```")[0].strip()
            data = json.loads(res_text)
            if isinstance(data, list):
                return {"text": data, "script": res_text, "transition": "", "layout_type": "BulletPoints"}
            return data
        except:
            return {"text": [], "script": res_text, "transition": "", "layout_type": "BulletPoints"}
