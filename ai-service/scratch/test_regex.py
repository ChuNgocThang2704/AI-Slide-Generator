import re

reasons = [
    'The image is clean and free of artifacts, text, or watermarks.',
    'There are no severe artifacts, text, watermarks, or distorted anatomy.',
    'There are no severe artifacts or distortions.',
    'There are minor distortions in the hands and faces, but they are not severe enough to be considered creepy or distracting.',
    'The image contains a watermark.',
    'A watermark is visible in the corner.',
    'There is a logo.',
    'Text dominates the image.',
    'There are no watermarks.'
]

severe_terms = (
    "unrelated",
    "wrong subject",
    "off topic",
    "not related",
    "does not match",
    "irrelevant",
    "text dominates",
    "large text",
    "prominent text",
    "watermark",
    "logo",
    "caption",
    "diagram",
    "infographic",
    "flowchart",
    "screenshot",
    "ui interface",
    "severe",
    "major artifact",
    "significant artifact",
    "heavily distorted",
    "unusable",
    "unreadable",
    "corrupt",
    "multiple faces distorted",
    "extra limbs",
    "missing limb",
)

for r in reasons:
    cleaned = r.lower()
    for term in severe_terms:
        # Build regex for this specific term
        pattern = r"\b(?:no|not|without|free of|clear of|clean of|doesn't|does not|avoid|avoids)\b[a-zA-Z0-9\s,]*?\b" + re.escape(term) + r"s?\b"
        cleaned = re.sub(pattern, " [CLEANED_" + term.upper() + "] ", cleaned, flags=re.IGNORECASE)
        
    matched = [t for t in severe_terms if t in cleaned]
    print('Original:', r)
    print('Cleaned :', cleaned)
    print('Matched  :', matched)
    print("-" * 50)
