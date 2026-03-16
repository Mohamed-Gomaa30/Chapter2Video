from typing import List, Dict
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelType, ModelPlatformType
import json

class AllocationAgent:
    def __init__(self, model_platform: ModelPlatformType = ModelPlatformType.GEMINI, 
                 model_type: ModelType = ModelType.GEMINI_3_PRO):
        self.model = ModelFactory.create(
            model_platform=model_platform,
            model_type=model_type,
        )
        self.system_message = (
            "You are a Strategic Lesson Planner (The Allocation Agent). "
            "Your task is to analyze a technical textbook section within the context of the FULL CHAPTER OUTLINE provided. \n\n"
            "Rules for Strategic Allocation:\n"
            "1. **Contextual Awareness**: Use the 'Chapter Outline' to see what comes before and after. If the current section is foundational, budget more slides. If it's a minor detail, budget fewer.\n"
            "2. **Concept Budgeting**: Decide a budget (1 to 4 slides) for the current section text. \n"
            "   - Intro/Summary sections: 1 slide.\n"
            "   - Standard technical sections: 2-3 slides.\n"
            "   - High-density/Complex sections: Max 4 slides.\n"
            "3. **Figure Anchoring**: Use figures and captions as anchors. A slide can contain BOTH a figure and text.\n"
            "4. **Vocabulary Spotting**: Identify and preserve technical terms in **bold** or *italics*. Ensure they are covered in the `text_content`.\n"
            "5. **Format**: Return strictly as a JSON list: "
            "[{\"concept_title\": \"...\", \"text_content\": \"...\", \"figure_references\": [\"path/to/fig1.png\"]}]"
        )

    def split_section(self, section_title: str, section_text: str, figures: List[Dict], 
                      chapter_outline: str = "", current_section_id: str = "") -> List[Dict]:
        agent = ChatAgent(system_message=self.system_message, model=self.model)
        
        prompt = (
            f"CHAPTER OUTLINE FOR CONTEXT:\n{chapter_outline}\n"
            f"CURRENT SECTION ID: {current_section_id}\n"
            f"CURRENT SECTION TITLE: {section_title}\n\n"
            f"SECTION TEXT TO BUDGET:\n{section_text}\n\n"
            f"FIGURES IN THIS SECTION:\n{json.dumps(figures, indent=2)}\n\n"
            "Analyze the section's position in the chapter and split it into an appropriate 'Concept Budget' (1-4 slides)."
        )
        
        user_msg = BaseMessage.make_user_message(role_name="User", content=prompt)
        response = agent.step(user_msg)
        
        if response.msg is None:
            return []
        
        # Extract JSON from response
        res_text = response.msg.content
        try:
            # Basic JSON extraction in case there is markdown formatting
            if "```json" in res_text:
                res_text = res_text.split("```json")[1].split("```")[0].strip()
            elif "```" in res_text:
                res_text = res_text.split("```")[1].split("```")[0].strip()
            return json.loads(res_text)
        except Exception as e:
            print(f"Error parsing AllocationAgent response: {e}")
            return []
