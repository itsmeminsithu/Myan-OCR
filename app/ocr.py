"""Tesseract recognition, ranked variants and optional explicit Google Cloud Vision."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import base64
import os
import re
from statistics import mean
import unicodedata

from PIL import Image
import pytesseract
from pytesseract import Output
import httpx

from .preprocess import variants, image_to_png_bytes
from .budget import check_budget, remaining_seconds

LANGS = {'my': 'mya', 'en': 'eng', 'both': 'mya+eng'}
MYANMAR_PATTERN = re.compile(r'[\u1000-\u109f\uaa60-\uaa7f\ua9e0-\ua9ff]')
ASCII_PATTERN = re.compile(r'[A-Za-z]')


class OCRUnavailable(RuntimeError):
    pass


def supported_languages() -> list[str]:
    try:
        return sorted(pytesseract.get_languages(config=''))
    except (FileNotFoundError, pytesseract.TesseractNotFoundError):
        return []


def _combine_line_tokens(words: list[dict]) -> str:
    """Keep visual spaces only where geometry suggests them; avoid one per Burmese token.

    Tesseract does not return original word separators from image_to_data.
    This is a conservative layout heuristic, not lossless text reconstruction.
    """
    pieces = []
    previous = None
    for word in words:
        token = unicodedata.normalize('NFC', word['text'])
        if previous is not None:
            gap = max(0, word['_abs'][0] - previous['_abs'][2])
            baseline = max(1, min(word['_abs'][3]-word['_abs'][1], previous['_abs'][3]-previous['_abs'][1]))
            prev_last = previous['text'][-1:]
            curr_first = token[:1]
            is_myanmar = bool(MYANMAR_PATTERN.search(prev_last+curr_first))
            # OCR words can be split within Myanmar orthographic syllables.
            # Use only large visual gaps for Burmese; use normal gaps for Latin words.
            gap_threshold = 0.20 if is_myanmar else 0.08
            if gap / baseline > gap_threshold:
                pieces.append(' ')
        pieces.append(token)
        previous = word
    return ''.join(pieces)


def _line_boxes(data: dict, width: int, height: int):
    groups: dict[tuple, list[dict]] = defaultdict(list)
    word_conf: list[float] = []
    for i, token in enumerate(data.get('text', [])):
        token = str(token).strip()
        if not token:
            continue
        try:
            value = float(data['conf'][i])
        except (ValueError, TypeError, IndexError):
            value = -1
        if value >= 0:
            word_conf.append(value)
        x = int(data['left'][i]); y = int(data['top'][i])
        w = int(data['width'][i]); h = int(data['height'][i])
        key = tuple(data[k][i] for k in ('page_num', 'block_num', 'par_num', 'line_num'))
        groups[key].append({'text': token, 'confidence': round(value, 1) if value >= 0 else None,
                            '_abs': (x, y, x+w, y+h), '_order': i})
    lines = []
    for key, words in sorted(groups.items(), key=lambda item: (item[0], min(w['_abs'][1] for w in item[1]))):
        words.sort(key=lambda w: (w['_abs'][0], w['_order']))
        xs = [v['_abs'][0] for v in words]; ys = [v['_abs'][1] for v in words]
        rights = [v['_abs'][2] for v in words]; bottoms = [v['_abs'][3] for v in words]
        line_conf = [v['confidence'] for v in words if v['confidence'] is not None]
        lines.append({'text': _combine_line_tokens(words),
                      'confidence': round(mean(line_conf), 1) if line_conf else None,
                      'box': {'x': min(xs)/width, 'y': min(ys)/height,
                              'width': (max(rights)-min(xs))/width,
                              'height': (max(bottoms)-min(ys))/height}})
    # Tesseract line identifiers may not follow visual reading order on scans.
    lines.sort(key=lambda line: (round(line['box']['y'] * height / 18), line['box']['x']))
    return lines, round(mean(word_conf), 1) if word_conf else 0.0


def _text_from_lines(lines: list[dict]) -> str:
    return '\n'.join(row['text'] for row in lines).strip()


def _rank(conf: float, text: str, language: str) -> float:
    """Conservative candidate ordering. NOT an accuracy percentage."""
    meaningful = [c for c in text if not c.isspace()]
    if not meaningful:
        return -999
    mya = len(MYANMAR_PATTERN.findall(text))
    eng = len(ASCII_PATTERN.findall(text))
    total = len(meaningful)
    score = conf
    # Do not reward a longer candidate: hallucinated characters inflate length.
    # A small penalty is appropriate when output clearly contradicts selected language.
    if language == 'my':
        score -= 12 * (eng / total)
    elif language == 'en':
        score -= 12 * (mya / total)
        score += 2 * (eng / total)
    return score


def recognize_local(image: Image.Image, language: str, mode: str) -> dict:
    if language not in LANGS:
        raise ValueError('Unknown language.')
    needed = LANGS[language].split('+')
    available = supported_languages()
    if any(lang not in available for lang in needed):
        raise OCRUnavailable(f'Missing Tesseract model(s): {", ".join(l for l in needed if l not in available)}. Install traineddata and restart.')
    candidates = []
    for label, candidate_image, psm in variants(image, mode):
        check_budget()
        try:
            data = pytesseract.image_to_data(candidate_image, lang=LANGS[language],
                                             config=f'--oem 1 --psm {psm}',
                                             output_type=Output.DICT, timeout=max(1, min(17, int(remaining_seconds()))))
        except RuntimeError:
            continue
        except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError) as exc:
            raise OCRUnavailable(str(exc)) from exc
        lines, conf = _line_boxes(data, image.width, image.height)
        raw = _text_from_lines(lines)
        candidates.append({'variant': label, 'psm': psm, 'text': raw, 'lines': lines,
                           'confidence': conf, 'rank': _rank(conf, raw, language) - (8 if label == 'sparse' else 0)})
    if not candidates:
        raise OCRUnavailable('Recognition timed out. Try a smaller, clearer image or Fast mode.')
    candidates.sort(key=lambda c: c['rank'], reverse=True)
    best = candidates[0]
    return {'engine': 'local', 'text': best['text'], 'lines': best['lines'],
            'confidence': best['confidence'], 'variant': best['variant'],
            'alternatives': [
                {'variant': c['variant'], 'text': c['text'], 'confidence': c['confidence']}
                for c in candidates[1:] if c['text'] and c['text'] != best['text']
            ][:3],
            'note': 'Recognition confidence is NOT measured accuracy; review the text against the image.'}


def _bbox(vertices: list[dict], w: int, h: int):
    if not vertices:
        return None
    xvalues = [v.get('x', 0) for v in vertices]
    yvalues = [v.get('y', 0) for v in vertices]
    x0, y0 = min(xvalues), min(yvalues)
    return {'x': x0/w, 'y': y0/h, 'width': (max(xvalues)-x0)/w, 'height': (max(yvalues)-y0)/h}


async def recognize_cloud(image: Image.Image, language: str) -> dict:
    key = os.getenv('GOOGLE_CLOUD_API_KEY', '').strip()
    if not key:
        raise OCRUnavailable('Cloud OCR is not configured. Add GOOGLE_CLOUD_API_KEY to the server environment.')
    blob = image_to_png_bytes(image)
    payload = {'requests': [{'image': {'content': base64.b64encode(blob).decode('ascii')},
                             'features': [{'type': 'DOCUMENT_TEXT_DETECTION'}],
                             'imageContext': {'languageHints': ['my', 'en'] if language == 'both' else [language]}}]}
    try:
        check_budget()
        async with httpx.AsyncClient(timeout=min(35.0, max(1.0, remaining_seconds()))) as client:
            response = await client.post('https://vision.googleapis.com/v1/images:annotate',
                                         params={'key': key}, json=payload)
            response.raise_for_status()
            parsed = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OCRUnavailable(f'Cloud OCR request failed: {type(exc).__name__}. Check API setup and network.') from exc
    if not isinstance(parsed, dict):
        raise OCRUnavailable('Cloud Vision returned an invalid response envelope.')
    responses = parsed.get('responses')
    if not isinstance(responses, list) or len(responses) != 1 or not isinstance(responses[0], dict):
        raise OCRUnavailable('Cloud Vision returned an invalid responses list.')
    result = responses[0]
    if 'error' in result:
        err = result['error'] if isinstance(result['error'], dict) else {}
        code = err.get('code', 'unknown')
        # Never relay raw cloud errors: provider messages can contain document metadata.
        raise OCRUnavailable(f'Cloud Vision rejected the request (code {str(code)[:12]}). Check credentials, billing, quota and API restrictions.')
    annotation = result.get('fullTextAnnotation') or {}
    if not isinstance(annotation, dict):
        raise OCRUnavailable('Cloud Vision returned malformed OCR annotation.')
    if not isinstance(annotation.get('text',''), str) or not isinstance(annotation.get('pages',[]), list):
        raise OCRUnavailable('Cloud Vision OCR fields are invalid.')
    text = annotation.get('text', '').strip()
    lines = []
    conf = []
    for page in annotation.get('pages', []):
        if not isinstance(page, dict) or not isinstance(page.get('blocks', []), list):
            raise OCRUnavailable('Cloud Vision returned invalid page structure.')
        width = page.get('width', image.width); height = page.get('height', image.height)
        if not isinstance(width, (int,float)) or not isinstance(height, (int,float)) or width <= 0 or height <= 0:
            raise OCRUnavailable('Cloud Vision returned invalid page dimensions.')
        for block in page.get('blocks', []):
            if not isinstance(block, dict) or not isinstance(block.get('paragraphs', []), list):
                raise OCRUnavailable('Cloud Vision returned invalid block structure.')
            for paragraph in block.get('paragraphs', []):
                if not isinstance(paragraph, dict) or not isinstance(paragraph.get('words', []), list):
                    raise OCRUnavailable('Cloud Vision returned invalid paragraph structure.')
                pieces = []
                for word in paragraph.get('words', []):
                    if not isinstance(word, dict) or not isinstance(word.get('symbols', []), list):
                        raise OCRUnavailable('Cloud Vision returned invalid word structure.')
                    symbols = word.get('symbols', [])
                    if any(not isinstance(symbol, dict) or not isinstance(symbol.get('text', ''), str) or not isinstance(symbol.get('property') or {}, dict) for symbol in symbols):
                        raise OCRUnavailable('Cloud Vision returned invalid symbol structure.')
                    val = ''.join(symbol.get('text', '') + (' ' if (symbol.get('property') or {}).get('detectedBreak', {}).get('type') in ('SPACE', 'SURE_SPACE') else '') for symbol in symbols)
                    if val:
                        pieces.append(val)
                if pieces:
                    box = _bbox((paragraph.get('boundingBox') or {}).get('vertices', []), width, height)
                    line = {'text': ''.join(pieces), 'confidence': None, 'box': box}
                    lines.append(line)
                    if isinstance(paragraph.get('confidence'), (float, int)):
                        conf.append(paragraph['confidence'] * 100)
    return {'engine': 'cloud', 'text': text, 'lines': lines,
            'confidence': round(mean(conf), 1) if conf else None,
            'variant': 'Google Cloud Vision', 'alternatives': [],
            'note': 'Cloud confidence is provider-specific and is not a measured accuracy score.'}
