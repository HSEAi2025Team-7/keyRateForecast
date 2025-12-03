import re

def split_sentences_ru(text: str):
    return re.split(r'(?<=[\.\!\?])\s+|\n+', text) if isinstance(text, str) else []

INC_RE = re.compile(
    r'(?:(?<!не\s)(повыс\w+|повышени\w+|увелич\w+).{0,30}(ключев\w*\s+ставк\w*))|'
    r'(?:(ключев\w*\s+ставк\w*).{0,30}(?<!не\s)(повыс\w+|повышени\w+|увелич\w+))',
    re.IGNORECASE
)
DEC_RE = re.compile(
    r'(?:(?<!не\s)(сниз\w+|пониз\w+|снижени\w+|уменьш\w+).{0,30}(ключев\w*\s+ставк\w*))|'
    r'(?:(ключев\w*\s+ставк\w*).{0,30}(?<!не\s)(сниз\w+|пониз\w+|снижени\w+|уменьш\w+))',
    re.IGNORECASE
)
FLAT_RE = re.compile(
    r'(?:(без\s+измен\w+|не\s+измен\w+|на\s+уровне|сохран\w+|остав\w+\s+(?:без\s+измен\w+)?).{0,30}(ключев\w*\s+ставк\w*))|'
    r'(?:(ключев\w*\s+ставк\w*).{0,30}(без\s+измен\w+|не\s+измен\w+|на\s+уровне|сохран\w+|остав\w+\s+(?:без\s+измен\w+)?))',
    re.IGNORECASE
)

def decision_key_rate(text, as_string=False):
    """
    Возвращает:
      +1 / -1 / 0  (int) — если as_string=False (по умолчанию)
      '+1' / '-1' / '0' (str) — если as_string=True
      np.nan — если ничего не найдено
    """
    if not isinstance(text, str) or not text.strip():
        return np.nan

    t = text.lower()
    if INC_RE.search(t):
        return '+1' if as_string else 1
    elif DEC_RE.search(t):
        return '-1' if as_string else -1
    elif FLAT_RE.search(t):
        return '0' if as_string else 0
    else:
        return np.nan

# Ищем решение по размеру ключевой ставки
def key_rate(text):
    if not isinstance(text, str) or not text.strip():
        return None
    t = text.lower()
    pct = r'(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:%|процент\w*)'
    dash = r'[–—-]'

    candidates = []
    for s in split_sentences_ru(t):
        if 'ключев' not in s or 'ставк' not in s:
            continue
        for m in re.finditer(pct, s, flags=re.IGNORECASE):
            val = float(m.group(1).replace(',', '.'))
            # отфильтруем проценты, являющиеся частью диапазона (13,0–15,0%)
            left = s[max(0, m.start()-6):m.start()]
            right = s[m.end(): m.end()+6]
            if re.search(fr'\d\s*{dash}\s*$', left) or re.search(fr'^{dash}\s*\d', right):
                continue
            # усилим совпадения вокруг 'до / на уровне / составит / установлена'
            window = s[max(0, m.start()-30): m.end()+30]
            score = 0
            if re.search(r'\b(до|на\s+уровне|состав(ит|лял[аи]|ляет)|установ(лен[ао]?|ить))\b', window):
                score += 2
            candidates.append((score, val))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], - (10 <= x[1] <= 25)), reverse=True)
    return round(candidates[0][1], 2)

# Применяем ТОЛЬКО к тексту
df['decision'] = df['text'].map(decision_key_rate)
df['key_rate'] = df['text'].map(key_rate)