import json
import sys
import re

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        data = json.load(open('outputs/debug/14f85278-86b4-4648-82c6-6a4e9583d561_images.json', encoding='utf-8'))
    except FileNotFoundError:
        print("Log file not found.")
        return

    severe_terms = (
        'unrelated', 'wrong subject', 'off topic', 'not related', 'does not match', 'irrelevant',
        'text dominates', 'large text', 'prominent text', 'watermark', 'logo', 'caption', 'diagram',
        'infographic', 'flowchart', 'screenshot', 'ui interface', 'severe', 'major artifact',
        'significant artifact', 'heavily distorted', 'unusable', 'unreadable', 'corrupt',
        'multiple faces distorted', 'extra limbs', 'missing limb'
    )

    print("=== DETAILED VLM JUDGMENTS AND REJECTION REASONS ===")
    
    for slide in data:
        s_idx = slide.get('slide_index')
        title = slide.get('title')
        status = slide.get('status')
        print(f"Slide #{s_idx}: {title} (Final Status: {status})")
        
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
                print(f"    VLM score: relevance={vlm.get('relevance_score')}, artifact={vlm.get('artifact_score')}, style={vlm.get('style_match_score')}")
                print(f"    Reasons: {reasons}")
                if matched_terms:
                    print(f"    Severe terms matched: {matched_terms}")
                    
        # Check AI Fallback VLM
        ai_vlm = slide.get('ai_fallback_vlm_judge')
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
            print(f"  * AI Fallback VLM:")
            print(f"    VLM score: relevance={ai_vlm.get('relevance_score')}, artifact={ai_vlm.get('artifact_score')}")
            print(f"    Reasons: {reasons}")
            if matched_terms:
                print(f"    Severe terms matched: {matched_terms}")

        print("=" * 60)

if __name__ == '__main__':
    main()
