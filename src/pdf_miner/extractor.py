import fitz  # PyMuPDF
import re
import os
from typing import List, Dict, Any
from models import Section, Figure

class PDFExtractor:
    def __init__(self, pdf_path: str, index_path: str, output_dir: str):
        self.pdf_path = pdf_path
        self.index_path = index_path
        self.output_dir = output_dir
        self.figures_dir = os.path.join(output_dir, "figures")
        os.makedirs(self.figures_dir, exist_ok=True)
        self.doc = fitz.open(pdf_path)

    def parse_index(self) -> List[Dict[str, Any]]:
        """Parses index.txt into a list of dictionaries with section_id and title."""
        sections = []
        with open(self.index_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                match = re.match(r'^([\d\.]+)\s+(.+)$', line)
                if match:
                    section_id = match.group(1)
                    title = match.group(2).strip()
                    level = section_id.count('.')
                    sections.append({
                        "section_id": section_id,
                        "title": title,
                        "page_hint": None,
                        "level": level
                    })
        return sections

    def find_header_coordinates(self, sections: List[Dict[str, Any]]) -> List[Section]:
        """Searches for section titles in the PDF and records their coordinates.
        Uses sequential search, strict ID matching, and discrete boundary logic.
        """
        enriched_sections = []
        last_page_found = 0
        
        for sec in sections:
            found = False
            section_id = sec['section_id']
            title = sec['title']
            
            id_pattern = re.escape(section_id) + r"\s+"
            
            for page_num in range(last_page_found, len(self.doc)):
                page = self.doc[page_num]
                blocks = page.get_text("blocks")
                for b in blocks:
                    if len(b) >= 7 and b[6] == 0:  
                        block_text = b[4].strip().replace('\n', ' ')
                        
                        if re.match(id_pattern, block_text):
                            if title.lower() in block_text.lower():
                                if re.search(r'\.{3,}\s*\d', block_text):
                                    continue
                                    
                                enriched_sections.append(Section(
                                    section_id=section_id,
                                    title=title,
                                    page_start=page_num,
                                    y_start=b[1], # y0
                                    level=sec['level']
                                ))
                                last_page_found = page_num
                                found = True
                                break
                    if found: break
                if found: break
                
            if not found:
                print(f"Warning: Could not find header for section {section_id} {title}")
        
        for i in range(len(enriched_sections)):
            curr_sec = enriched_sections[i]
            if i < len(enriched_sections) - 1:
                next_sec = enriched_sections[i+1]
                curr_sec.page_end = next_sec.page_start
                curr_sec.y_end = next_sec.y_start
            else:
                curr_sec.page_end = len(self.doc) - 1
                curr_sec.y_end = self.doc[curr_sec.page_end].rect.height
            
        return enriched_sections

    def extract_section_zones(self, section: Section) -> List[str]:
        """Clips the PDF pages into 'Zone' images for the section.
        Handles multi-page sections by taking full pages between start and end.
        """
        zone_images = []
        for page_num in range(section.page_start, section.page_end + 1):
            page = self.doc[page_num]
            
            y0 = 0
            y1 = page.rect.height
            
            if page_num == section.page_start:
                y0 = section.y_start
            
            if page_num == section.page_end:
                y1 = section.y_end
            
            if (y1 - y0) < 5:
                continue
                
            clip_rect = fitz.Rect(0, y0, page.rect.width, y1)
            pix = page.get_pixmap(clip=clip_rect, dpi=300)
            
            img_name = f"section_{section.section_id}_p{page_num}.png"
            img_path = os.path.join(self.output_dir, "zones", img_name)
            os.makedirs(os.path.dirname(img_path), exist_ok=True)
            pix.save(img_path)
            zone_images.append(img_path)
            
        return zone_images


    def extract_assets_in_zone(self, section: Section):
        """Extracts images found within the section's coordinate zone."""
        for page_num in range(section.page_start, section.page_end + 1):
            page = self.doc[page_num]
            images = page.get_images(full=True)

            img_info_list = page.get_image_info(xrefs=True)
            xref_to_bbox = {}
            for info in img_info_list:
                info_xref = info.get('xref')
                if info_xref is not None:
                    xref_to_bbox[info_xref] = info.get('bbox')
            
            for img_index, img in enumerate(images):
                xref = img[0]
                base_image = self.doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                bbox = xref_to_bbox.get(xref)
                if bbox is None:
                    continue 
                
                is_in_zone = True
                if page_num == section.page_start and bbox[1] < section.y_start:
                    is_in_zone = False
                if page_num == section.page_end and bbox[3] > section.y_end:
                    is_in_zone = False
                    
                if is_in_zone:
                    img_ext = base_image["ext"]
                    img_path = os.path.join(self.figures_dir, f"fig_{section.section_id}_{page_num}_{img_index}.{img_ext}")
                    with open(img_path, "wb") as f:
                        f.write(image_bytes)
                    
                    section.figures.append(Figure(
                        path=img_path,
                        page=page_num,
                        bbox=list(bbox)
                    ))

    def get_pages_with_images(self, section: Section) -> Dict[int, bool]:
        """Uses PyMuPDF to quickly check which pages in this section have images."""
        pages_with_images = {}
        for page_num in range(section.page_start, section.page_end + 1):
            page = self.doc[page_num]
            images = page.get_images(full=True)
            pages_with_images[page_num] = len(images) > 0
        return pages_with_images

    def extract_assets_with_vlm(self, section: Section, transcriber: Any, 
                                 zone_images: List[str],
                                 globally_extracted: set):
        """Uses VLM to visually identify figures via coordinates, then refines
        those coordinates with PyMuPDF object bounding boxes for pixel-perfect crops.
        """
        import json
        import time

        pages_with_images = self.get_pages_with_images(section)
        
        zones_to_scan = []
        for zone_path in zone_images:
            page_match = re.search(r'_p(\d+)', os.path.basename(zone_path))
            if page_match:
                page_num = int(page_match.group(1))
                if pages_with_images.get(page_num, False):
                    zones_to_scan.append((zone_path, page_num))
        
        if not zones_to_scan:
            print(f"    No visual objects detected (PyMuPDF pre-filter).")
            return

        for zone_path, page_num in zones_to_scan:
            print(f"  VLM visually scanning {os.path.basename(zone_path)}...")
            vlm_json = transcriber.detect_figures(zone_path)
            time.sleep(2)

            try:
                json_str = vlm_json.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()
                
                detected_figures = json.loads(json_str)
            except Exception as e:
                print(f"    Error parsing VLM JSON for {os.path.basename(zone_path)}: {e}")
                continue

            if not detected_figures:
                continue

            page = self.doc[page_num]
            pw, ph = page.rect.width, page.rect.height
            
            zone_y_start = section.y_start if page_num == section.page_start else 0
            zone_y_end = section.y_end if page_num == section.page_end else ph
            zone_height = zone_y_end - zone_y_start

            for fig_data in detected_figures:
                v_ymin, v_xmin, v_ymax, v_xmax = fig_data['bbox']
                caption_hint = fig_data.get('caption_hint', 'Unlabeled figure')

                if caption_hint in globally_extracted:
                    continue

                pdf_ymin = zone_y_start + (v_ymin / 1000.0) * zone_height
                pdf_ymax = zone_y_start + (v_ymax / 1000.0) * zone_height
                pdf_xmin = (v_xmin / 1000.0) * pw
                pdf_xmax = (v_xmax / 1000.0) * pw
                
                vlm_rect = fitz.Rect(pdf_xmin, pdf_ymin, pdf_xmax, pdf_ymax)

                img_info = page.get_image_info(xrefs=True)
                candidate_rects = []
                for info in img_info:
                    obj_rect = fitz.Rect(info['bbox'])
                    if obj_rect.intersects(vlm_rect):
                        candidate_rects.append(obj_rect)
                
                if candidate_rects:
                    final_rect = candidate_rects[0]
                    for r in candidate_rects[1:]:
                        final_rect |= r
                    final_rect.y0 = max(0, final_rect.y0 - 10)
                    final_rect.y1 = min(ph, final_rect.y1 + 10)
                else:
                    final_rect = vlm_rect

                final_rect.y0 = max(zone_y_start, final_rect.y0)
                final_rect.y1 = min(zone_y_end, final_rect.y1)
                blocks = page.get_text("blocks")
                caption_bottom = final_rect.y1  
                for b in blocks:
                    if len(b) >= 7 and b[6] == 0:  
                        b_top, b_bottom = b[1], b[3]
                        if final_rect.y1 <= b_top <= final_rect.y1 + 60:
                            block_text = b[4].strip()
                            if re.match(r'Figure\s+\d+', block_text, re.IGNORECASE):
                                caption_bottom = b_bottom + 5  
                                break
                final_rect.y1 = min(zone_y_end, caption_bottom)


                pix = page.get_pixmap(clip=final_rect, dpi=300)
                safe_caption = re.sub(r'[\\/*?:"<>|]', '', caption_hint).strip()[:100]
                if not safe_caption:
                    safe_caption = f"fig_{section.section_id}_p{page_num}"
                fig_name = f"{safe_caption}.png"

                fig_path = os.path.join(self.figures_dir, fig_name)
                pix.save(fig_path)

                section.figures.append(Figure(
                    path=fig_path,
                    caption=caption_hint,
                    page=page_num,
                    bbox=[final_rect.x0, final_rect.y0, final_rect.x1, final_rect.y1]
                ))
                globally_extracted.add(caption_hint)
                print(f"    ✓ Visually extracted: {fig_name}")




    def close(self):
        self.doc.close()

