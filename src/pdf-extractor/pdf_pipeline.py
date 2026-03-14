import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from extractor import PDFExtractor
from vlm_transcriber import VLMTranscriber
from models import Section

# Load .env from project root
project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(project_root / ".env")


def main():
    parser = argparse.ArgumentParser(description="Chapter2Video High-Precision Extraction Pipeline")
    parser.add_argument("--pdf", type=str, required=True, help="Path to the chapter PDF")
    parser.add_argument("--index", type=str, required=True, help="Path to the index.txt file")
    parser.add_argument("--output", type=str, default="./output", help="Directory for output files")
    parser.add_argument("--vlm", action="store_true", help="Run VLM transcription")
    parser.add_argument("--vlm-figures", action="store_true", help="Use VLM to detect and extract figures")
    
    args = parser.parse_args()
    
    extractor = PDFExtractor(args.pdf, args.index, args.output)
    
    print("Step 1: Parsing Index and Finding Header Coordinates...")
    raw_sections = extractor.parse_index()
    sections = extractor.find_header_coordinates(raw_sections)
    
    transcriber = None
    if args.vlm or args.vlm_figures:
        print("Step 2: Initializing VLM Transcriber...")
        transcriber = VLMTranscriber()
    
    print("Step 3: Extracting Zones and Assets...")
    final_data = []
    globally_extracted_figures = set()  # Track extracted figures across all sections
    for section in sections:
        print(f"Processing Section {section.section_id}: {section.title}...")
        
        # Extract zone images first (needed for both VLM figures and VLM text)
        zone_images = extractor.extract_section_zones(section)

        # Figure Extraction
        if args.vlm_figures and transcriber:
            extractor.extract_assets_with_vlm(section, transcriber, zone_images, globally_extracted_figures)
        else:
            # Fallback to standard PyMuPDF image extraction
            extractor.extract_assets_in_zone(section)

        
        # Transcribe zones if VLM is enabled
        if args.vlm and transcriber:
            import time
            transcribed_texts = []
            for zone_img in zone_images:
                print(f"  Transcribing {os.path.basename(zone_img)}...")
                text = transcriber.transcribe_zone(zone_img)
                transcribed_texts.append(text)
                # Sleep to avoid rate limits
                time.sleep(4) 
            section.text = "\n\n".join(transcribed_texts)
        else:
            section.text = "VLM transcription skipped."
            
        final_data.append(section.model_dump())

        
    print("Step 4: Saving Results to JSON...")
    output_json = os.path.join(args.output, "extraction_results.json")
    with open(output_json, "w") as f:
        json.dump(final_data, f, indent=4)
        
    print(f"Extraction complete! Results saved to {output_json}")
    extractor.close()

if __name__ == "__main__":
    main()
