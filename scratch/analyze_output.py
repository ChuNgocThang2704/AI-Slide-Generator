import json
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        data = json.load(open('outputs/debug/14f85278-86b4-4648-82c6-6a4e9583d561_images.json', encoding='utf-8'))
    except FileNotFoundError:
        print("Log file not found.")
        return

    print("=== LATEST RUN IMAGE SELECTION SUMMARY ===")
    print(f"Run ID: 14f85278-86b4-4648-82c6-6a4e9583d561")
    print(f"Total Slides: {len(data)}")
    print("=" * 60)

    for slide in data:
        s_idx = slide.get('slide_index')
        title = slide.get('title', '')
        status = slide.get('status', '')
        risk = slide.get('risk', '')
        
        print(f"Slide #{s_idx}: {title} (Risk: {risk})")
        print(f"  Status: {status}")
        
        # Checking AI fallback details
        ai_vlm = slide.get('ai_fallback_vlm_judge')
        if ai_vlm:
            print(f"  AI VLM Score: relevance={ai_vlm.get('relevance_score')}, artifact={ai_vlm.get('artifact_score')}")
        ai_reject = slide.get('ai_fallback_rejection')
        if ai_reject:
            print(f"  AI Fallback Rejected because: {ai_reject}")

        # Checking External details
        ext_source = slide.get('external_source')
        if ext_source:
            print(f"  External Image: Source={ext_source}")
            print(f"    Query used: '{slide.get('external_query')}'")
            print(f"    URL: {slide.get('external_page_url')}")
            ext_vlm = slide.get('external_vlm_judge')
            if ext_vlm:
                print(f"    External VLM Score: relevance={ext_vlm.get('relevance_score')}, artifact={ext_vlm.get('artifact_score')}")
        
        img_path = slide.get('image_path', '')
        print(f"  Final Image: {img_path}")
        print("-" * 60)

if __name__ == '__main__':
    main()
