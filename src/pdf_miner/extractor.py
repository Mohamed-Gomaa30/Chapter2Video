import fitz  # PyMuPDF
import re
import os
from typing import List, Dict, Any
from models import Section, Figure

class PDFExtractor:
    def __init__(self, pdf_path: str, index_path: str, output_dir: str, 
                 dpi: int = 300, 
                 vlm_dpi: int = 200,
                 bridge_margin_y: int = 20,
                 bridge_margin_x: int = 10,
                 padding: int = 5):
        self.pdf_path = pdf_path
        self.index_path = index_path
        self.output_dir = output_dir
        self.dpi = dpi
        self.vlm_dpi = vlm_dpi
        self.bridge_margin_y = bridge_margin_y
        self.bridge_margin_x = bridge_margin_x
        self.padding = padding
        
        self.figures_dir = os.path.join(output_dir, "figures")
        os.makedirs(self.figures_dir, exist_ok=True)
        self.doc = fitz.open(pdf_path)
        self._vlm_cache = {} 

    def parse_index(self) -> List[Dict[str, Any]]:
        """Parses index.txt into a list of dictionaries. 
        Supports various formats: '1.1 Title', 'Chapter 1 Title', 'Section 1.2 Title'.
        """
        sections = []
        with open(self.index_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                match = re.match(r'^((?:(?:Chapter|Section|Part)\s+)?[\d\w\.]+)\s*(.*)$', line, re.IGNORECASE)
                if match:
                    section_id = match.group(1).strip()
                    title = match.group(2).strip()
                    if not title:
                        title = section_id
                    
                    level = section_id.count('.') + (1 if ' ' in section_id else 0)
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
                            if b[1] < 50 or b[3] > self.doc[page_num].rect.height - 50:
                                continue

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
            pix = page.get_pixmap(clip=clip_rect, dpi=self.dpi)
            
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

    def get_pages_with_visual_content(self, section: Section) -> Dict[int, bool]:
        """Checks if pages have raster images, vector drawings, or 'Figure' hints."""
        pages_visual = {}
        for page_num in range(section.page_start, section.page_end + 1):
            page = self.doc[page_num]
            has_img = len(page.get_images()) > 0
            has_vec = len(page.get_drawings()) > 5 
            has_fig_text = "figure" in page.get_text().lower()
            
            pages_visual[page_num] = has_img or has_vec or has_fig_text
        return pages_visual

    def extract_assets_with_vlm(self, section: Section, transcriber: Any, 
                                 zone_images: List[str],
                                 globally_extracted: set):
        """Pivots to full-page VLM scanning for better context.
        Uses spatial filtering to attribute detected figures to the current section.
        """
        import json
        import time

        if not hasattr(self, '_vlm_cache'):
            self._vlm_cache = {} 

        pages_visual = self.get_pages_with_visual_content(section)
        
        pages_to_scan = [p for p in range(section.page_start, section.page_end + 1) if pages_visual.get(p, False)]
        
        if not pages_to_scan:
            print(f"    No visual objects detected (Smart pre-filter).")
            return

        for page_num in pages_to_scan:
            if page_num in self._vlm_cache:
                detected_figures = self._vlm_cache[page_num]
            else:
                print(f"  VLM scanning FULL PAGE {page_num} for context...")
                page = self.doc[page_num]
                pix = page.get_pixmap(dpi=self.vlm_dpi)
                temp_page_path = os.path.join(self.output_dir, "temp_full_page.png")
                pix.save(temp_page_path)
                
                vlm_json = transcriber.detect_figures(temp_page_path)
                time.sleep(2)

                try:
                    json_str = vlm_json.strip()
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0].strip()
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0].strip()
                    
                    detected_figures = json.loads(json_str)
                    self._vlm_cache[page_num] = detected_figures
                except Exception as e:
                    print(f"    Error parsing VLM JSON for page {page_num}: {e}")
                    continue

            if not detected_figures:
                continue

            page = self.doc[page_num]
            pw, ph = page.rect.width, page.rect.height
            
            zone_y_start = section.y_start if page_num == section.page_start else 0
            zone_y_end = section.y_end if page_num == section.page_end else ph

            for fig_data in detected_figures:
                bbox = fig_data.get('bbox')
                
                if isinstance(bbox, (list, tuple)) and len(bbox) == 1 and isinstance(bbox[0], (list, tuple)):
                    bbox = bbox[0]
                
                if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                    print(f"    ⚠ Skipping malformed figure data (bbox: {bbox})")
                    continue
                    
                v_ymin, v_xmin, v_ymax, v_xmax = bbox
                caption_hint = fig_data.get('caption_hint')
                if not caption_hint:
                    caption_hint = "Unlabeled figure"

                pdf_ymin = (v_ymin / 1000.0) * ph
                pdf_ymax = (v_ymax / 1000.0) * ph
                pdf_xmin = (v_xmin / 1000.0) * pw
                pdf_xmax = (v_xmax / 1000.0) * pw
                
                fig_center_y = (pdf_ymin + pdf_ymax) / 2
                if not (zone_y_start <= fig_center_y <= zone_y_end):
                    continue

                if caption_hint in globally_extracted and caption_hint != "Unlabeled figure":
                    continue

                vlm_rect = fitz.Rect(pdf_xmin, pdf_ymin, pdf_xmax, pdf_ymax)
                
                visual_objects = []
                img_info = page.get_image_info(xrefs=True)
                for info in img_info:
                    obj_rect = fitz.Rect(info['bbox'])
                    if obj_rect.intersects(vlm_rect): visual_objects.append(obj_rect)
                
                drawings = page.get_drawings()
                for d in drawings:
                    d_rect = fitz.Rect(d['rect'])
                    if d_rect.intersects(vlm_rect) and 5 < d_rect.width < pw * 0.95: 
                        visual_objects.append(d_rect)

                caption_blocks = []
                blocks = page.get_text("blocks")
                clean_hint = str(caption_hint).lower() if caption_hint else ""
                
                for b in blocks:
                    if len(b) >= 7 and b[6] == 0:
                        b_rect = fitz.Rect(b[:4])
                        text = b[4].strip()
                        
                        search_zone = fitz.Rect(vlm_rect.x0 - 10, vlm_rect.y0 - 10, 
                                                vlm_rect.x1 + 10, vlm_rect.y1 + 10)
                        if b_rect.intersects(search_zone):
                            is_hint_match = clean_hint != "unlabeled figure" and clean_hint in text.lower()
                            is_labeled = text.lower().startswith(('figure', 'fig.', 'table', 'tab.'))
                            is_short = text.count('\n') < 4
                            
                            is_noise = "www." in text.lower() or b_rect.y1 < 50 or b_rect.y0 > ph - 50
                            
                            if (is_hint_match or is_labeled) and is_short and not is_noise:
                                caption_blocks.append(b_rect)
         
                if visual_objects:
                    components = visual_objects + caption_blocks
                    final_rect = components[0]
                    for r in components[1:]: final_rect |= r
                else:
                    print(f"    ⚠ Skipping {caption_hint}: No visual anchor found (text-only).")
                    continue

                final_rect.y0 = max(0, final_rect.y0 - 5)
                final_rect.y1 = min(ph, final_rect.y1 + 5)
                final_rect.x0 = max(0, final_rect.x0 - 5)
                final_rect.x1 = min(pw, final_rect.x1 + 5)

                pix = page.get_pixmap(clip=final_rect, dpi=self.dpi)
                str_hint = str(caption_hint)
                safe_name = "".join([c for c in str_hint if c.isalnum() or c in (' ', '_', '-')]).strip()[:80]
                if not safe_name or safe_name.lower() == "unlabeled figure":
                    safe_name = f"fig_{section.section_id}_p{page_num}_{int(time.time()*1000)%1000}"
                fig_name = f"{safe_name.replace(' ', '_')}.png"

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
