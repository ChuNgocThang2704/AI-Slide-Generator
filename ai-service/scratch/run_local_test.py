import sys
import os
import asyncio
import uuid
from pathlib import Path

# Configure console encoding to UTF-8 to prevent charmap/UnicodeEncodeError on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add backend to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent / 'backend'))


# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / 'backend' / '.env')

from services.file_processor import FileProcessor
from services.content_extractor import ContentExtractor
from services.slide_generator import SlideGenerator
from services.slide_text_quality import improve_slide_text_quality
from services.slide_charts import build_chart_specs_for_slides
from services.slide_tables import build_table_specs_for_slides
from services.images import build_image_paths_for_slides
from filename_utils import pptx_path_for_task
from config import LLM_MODEL, OUTPUT_DIR

async def run_pipeline():
    # Use a new task_id or specific task_id
    task_id = str(uuid.uuid4())
    print(f"Starting test pipeline with task_id: {task_id}")
    
    file_path = Path(__file__).resolve().parent.parent / 'uploads' / '14f85278-86b4-4648-82c6-6a4e9583d561.pdf'
    if not file_path.exists():
        print(f"Error: Source file {file_path} not found.")
        return
        
    print(f"Reading file: {file_path}")
    file_processor = FileProcessor()
    raw_content = await file_processor.process_file(file_path)
    print(f"Extracted raw text, length: {len(raw_content)}")
    
    print(f"Extracting and structuring content (model={LLM_MODEL})...")
    content_extractor = ContentExtractor(model_name=LLM_MODEL)
    structured_content = await content_extractor.extract_and_structure(
        raw_content,
        target_slides_override=10,
        force_exact_slide_count=True
    )
    
    # Force exact 10 slides
    structured_content = await content_extractor._force_slide_count_exact(structured_content, 10)
    
    print("Improving slide text quality...")
    structured_content = await improve_slide_text_quality(
        content_extractor,
        structured_content,
        task_id=task_id
    )
    
    print("Building table and chart specs...")
    table_specs = await build_table_specs_for_slides(
        content_extractor,
        structured_content,
        task_id=task_id
    )
    
    chart_specs = await build_chart_specs_for_slides(
        content_extractor,
        structured_content,
        task_id=task_id,
        table_indices=set(table_specs.keys())
    )
    
    print(f"Tables: {list(table_specs.keys())}, Charts: {list(chart_specs.keys())}")
    
    print("Generating image paths for slides...")
    image_paths = await build_image_paths_for_slides(
        content_extractor,
        structured_content,
        task_id,
        chart_specs=chart_specs,
        table_specs=table_specs
    )
    
    print(f"Generated images map: {image_paths}")
    
    output_path = pptx_path_for_task(OUTPUT_DIR, structured_content.get("title", ""), task_id)
    print(f"Creating PowerPoint file: {output_path}")
    slide_generator = SlideGenerator()
    await slide_generator.create_slide(
        structured_content,
        output_path,
        generate_images=bool(image_paths),
        image_paths=image_paths,
        chart_specs=chart_specs,
        table_specs=table_specs,
        preset="modern"
    )
    
    print(f"Pipeline finished successfully! PPTX: {output_path.name}")
    print(f"Review the new run debug output under outputs/debug/{task_id}_images.json")

if __name__ == '__main__':
    asyncio.run(run_pipeline())
