from django import template
import json

register = template.Library()

@register.filter
def render_with_annotations(text, annotations_json):
    if not text or not annotations_json:
        return text

    try:
        annotations = json.loads(annotations_json)
    except (json.JSONDecodeError, TypeError):
        return text

    # Comprehensive Unicode space separators (covers Bangla/common cases)
    SPACE_CHARS = (
        ' \t\n\r\x0b\x0c'  # ASCII whitespace
        '\u00A0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A'  # NBSP, en/em spaces
        '\u202F\u205F\u3000'  # Narrow NBSP, medium math space, ideographic space
    )
    
    annotations.sort(key=lambda x: x['start_index'])
    result = []
    last_end = 0

    for ann in annotations:
        start_idx = ann.get('start_index', 0)
        end_idx = ann.get('end_index', 0)
        label = ann.get('label', 'Unknown')
        label_color = ann.get('label_color', '#000000')
        suggestions = ann.get('suggestions', [])
        ann_id = ann.get('id', 0)

        if start_idx < 0 or end_idx > len(text) or start_idx >= end_idx:
            continue

        if start_idx > last_end:
            result.append(text[last_end:start_idx])

        annotated_text = text[start_idx:end_idx]
        
        # STRIP ALL TRAILING SPACE CHARACTERS (aggressive)
        annotated_text_trimmed = annotated_text.rstrip(SPACE_CHARS)
        trailing_part = annotated_text[len(annotated_text_trimmed):]  # Preserve EXACT chars
        
        # Skip empty annotations (only spaces)
        if not annotated_text_trimmed:
            result.append(trailing_part)
            last_end = end_idx
            continue

        # Build suggestions HTML
        suggestions_html = (
            '<br><strong>Suggestions:</strong><br>' + '<br>'.join(f'• {s}' for s in suggestions)
            if suggestions else ''
        )
        
        # CRITICAL: Use trimmed text INSIDE span, trailing chars OUTSIDE
        annotation_span = (
            f'<span class="annotation-span" style="border-bottom-color: {label_color}; background-color: {label_color};" '
            f'data-ann-id="{ann_id}">{annotated_text_trimmed}'
            f'<div class="annotation-info"><strong>{label}</strong>{suggestions_html}</div></span>'
        )
        
        result.append(annotation_span)
        if trailing_part:  # Append EXACT trailing chars (spaces/NBSP) outside span
            result.append(trailing_part)
        
        last_end = end_idx

    if last_end < len(text):
        result.append(text[last_end:])
        
    return ''.join(result)