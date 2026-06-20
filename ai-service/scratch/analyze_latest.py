import json
import sys
import re
from pathlib import Path

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    debug_dir = Path(__file__).resolve().parent.parent / 'backend' / 'outputs' / 'debug'
    
    # Find all _images.json files
    files = list(debug_dir.glob("*_images.json"))
    if not files:
        print("No debug json files found under outputs/debug.")
        return
        
    # Sort by modification time to get the latest
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    latest_file = files[0]
    
    print(f"Analyzing latest debug log file: {latest_file.name}")
    try:
        data = json.load(open(latest_file, encoding='utf-8'))
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    severe_terms = (
        'unrelated', 'wrong subject', 'off topic', 'not related', 'does not match', 'irrelevant',
        'text dominates', 'large text', 'prominent text', 'watermark', 'logo', 'caption', 'diagram',
        'infographic', 'flowchart', 'screenshot', 'ui interface', 'severe', 'major artifact',
        'significant artifact', 'heavily distorted', 'unusable', 'unreadable', 'corrupt',
        'multiple faces distorted', 'extra limbs', 'missing limb'
    )

    print("=" * 60)
    print(f"Run ID: {data[0].get('task_id') if data else 'N/A'}")
    print(f"Total Slides: {len(data)}")
    print("=" * 60)
    
    for slide in data:
        s_idx = slide.get('slide_index')
        title = slide.get('title')
        status = slide.get('status')
        risk = slide.get('risk')
        print(f"Slide #{s_idx}: {title} (Risk: {risk}) -> Final Status: {status}")
        
        # Check attempts
        for attempt in slide.get('attempts', []):
            label = attempt.get('label')
            status_att = attempt.get('status')
            vlm = attempt.get('vlm_judge') or {}
            reasons = vlm.get('reasons') or []
            combined = ' '.join(str(r) for r in reasons).lower()
            combined = re.sub(
                r"\b(?:no|without|does not show|doesn't show|avoids?)\s+"
                r"(?:text|diagram|diagrams|infographic|infographics|logo|watermark|screenshot)s?\b",
                " ",
                combined,
            )
            matched_terms = [t for t in severe_terms if t in combined]
            print(f"  * Attempt [{label}] -> status: {status_att}")
            if vlm:
                print(f"    VLM: relevance={vlm.get('relevance_score')}, artifact={vlm.get('artifact_score')}, style={vlm.get('style_match_score')}")
                print(f"    Reasons: {reasons}")
                if matched_terms:
                    print(f"    Severe terms matched: {matched_terms}")
                    
        # Check AI Fallback VLM
        ai_vlm = slide.get('ai_fallback_vlm_judge')
        ai_reject = slide.get('ai_fallback_rejection')
        if ai_vlm or ai_reject:
            print(f"  * AI Fallback VLM:")
            if ai_reject:
                print(f"    Rejection info: {ai_reject}")
            if ai_vlm:
                reasons = ai_vlm.get('reasons') or []
                combined = ' '.join(str(r) for r in reasons).lower()
                combined = re.sub(
                    r"\b(?:no|without|does not show|doesn't show|avoids?)\s+"
                    r"(?:text|diagram|diagrams|infographic|infographics|logo|watermark|screenshot)s?\b",
                    " ",
                    combined,
                )
                matched_terms = [t for t in severe_terms if t in combined]
                print(f"    Scores: relevance={ai_vlm.get('relevance_score')}, artifact={ai_vlm.get('artifact_score')}")
                print(f"    Reasons: {reasons}")
                if matched_terms:
                    print(f"    Severe terms matched: {matched_terms}")

        # Check External details
        ext_source = slide.get('external_source')
        if ext_source:
            print(f"  * External Image:")
            print(f"    Source={ext_source}, Query='{slide.get('external_query')}'")
            print(f"    URL: {slide.get('external_page_url')}")
            ext_vlm = slide.get('external_vlm_judge')
            if ext_vlm:
                print(f"    VLM score: relevance={ext_vlm.get('relevance_score')}, artifact={ext_vlm.get('artifact_score')}")
                print(f"    Reasons: {ext_vlm.get('reasons')}")
                
        img_path = slide.get('image_path')
        if img_path:
            print(f"  * Image Saved: {img_path}")
        print("-" * 60)

if __name__ == '__main__':
    main()
