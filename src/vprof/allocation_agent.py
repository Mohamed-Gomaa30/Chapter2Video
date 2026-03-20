from typing import List, Dict
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelType, ModelPlatformType
import json

class AllocationAgent:
    def __init__(self, model_platform: ModelPlatformType = ModelPlatformType.GEMINI, 
                 model_type: ModelType = ModelType.GEMINI_2_5_PRO):
        self.model = ModelFactory.create(
            model_platform=model_platform,
            model_type=model_type,
        )
        self.system_message = (
            "You are a Strategic Lesson Planner (The Allocation Agent). "
            "Your task is to analyze a technical textbook section within the context of the FULL CHAPTER OUTLINE "
            "and split it into a precise number of concept slides for an academic video lecture.\n\n"

            "RULES FOR STRATEGIC ALLOCATION:\n\n"

            "1. CONTEXTUAL AWARENESS:\n"
            "   - Study the Chapter Outline to understand what comes before and after the current section.\n"
            "   - Foundational sections that introduce core concepts → budget MORE slides.\n"
            "   - Transitional, summary, or minor detail sections → budget FEWER slides.\n\n"

            "2. CONCEPT BUDGETING:\n"
            "   - Intro / overview / transition sections              → 1 slide\n"
            "   - Standard technical sections (1–2 concepts)         → 2–3 slides\n"
            "   - Dense sections (3+ distinct concepts or figures)   → 3-5 slides\n"
            "   - Complex sections (many subsections + figures)      → Budget as many as needed to cover all content and ALL figures.\n\n"

            "3. NO FIGURE LEFT BEHIND (CRITICAL):\n"
            "   - Every figure path provided in the 'FIGURES IN THIS SECTION' list MUST be assigned to at least one slide.\n"
            "   - Do NOT drop any figure. If a section has 9 figures, you must budget enough slides (or multi-figure slides) to show them all.\n"
            "   - Assign each figure to the slide whose text_content it best illustrates.\n"
            "   - A slide can have multiple figure references if they are tightly related, but usually one per slide is cleaner.\n\n"

            "4. VOCABULARY SPOTTING:\n"
            "   - Identify all bold (**term**) and italic (*term*) technical terms in the section text.\n"
            "   - Ensure every such term appears in at least one slide's text_content — do NOT drop them.\n"
            "   - Copy them verbatim with their original formatting markers intact.\n\n"

            "5. TEXT SPLITTING:\n"
            "   - text_content must be a VERBATIM excerpt from the section text — no paraphrasing, no summarizing.\n"
            "   - Distribute the section text logically: each slide should cover one coherent concept.\n"
            "   - concept_title must be short and specific (not the section title — describe THIS slide's concept).\n\n"

            "OUTPUT FORMAT (STRICT):\n"
            "Return ONLY a valid JSON array. No markdown fences. No explanation. No preamble.\n"
            "Output starts with [ and ends with ]. Nothing before or after.\n"
            "[\n"
            "  {\"concept_title\": \"...\", \"text_content\": \"...\", \"figure_references\": [\"path/to/fig.png\"]},\n"
            "  ...\n"
            "]\n"
            "Always return a list — even for a 1-slide budget, wrap it in []."
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
