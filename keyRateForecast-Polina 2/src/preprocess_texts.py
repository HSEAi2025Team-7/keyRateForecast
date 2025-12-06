import nltk
nltk.download('punkt_tab')

import pandas as pd
import numpy as np
import re
import string
from typing import List, Dict

from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

import pymorphy3
from gensim.models.phrases import Phrases, Phraser

from itertools import chain
from collections import Counter


ru_stop = set(stopwords.words('russian'))
morph = pymorphy3.MorphAnalyzer()
punct = set(string.punctuation)
punct_add = ['«', '»', '“', '„', '—']

data = pd.read_csv('/Users/polinakokova/Desktop/HSE/keyRateForecastNew/data/raw/cbr_press/press_releases.csv')


def clean(text): # spaces, переносы и регистр

    if not isinstance(text, str):
        return ""
    text = text.replace('\n', ' ').replace('\xa0', ' ').strip().lower()
    return text


def sentence(text):
    #список стр по предложениям
    sentences = sent_tokenize(text, language='russian')
    return sentences


def stopword(sentences):
    # слова в тексте, знаки препинания, числа токенизация по словам

    filtered_text = []
    stop_words = set(stopwords.words('russian'))
    for i in sentences:
        for w in word_tokenize(i, language='russian'):
            w = w.replace('–', '-').replace('—', '-')
            w = w.strip()
            if not w:
                continue
            if w in punct or w in punct_add:  # delete знаки пунктуации
                continue
            if re.fullmatch(r'\d+([.,]\d+)?', w):  # del числовые токены
                continue
            if re.fullmatch(r'\d{1,2}:\d{2}(:\d{2})?', w):  #  delete время
                continue
            if re.fullmatch(r'\d{1,2}\.\d{1,2}\.\d{2,4}', w):  # delete даты
                continue
            if re.fullmatch(r'\d{4}-\d{4}', w):  #   del год-год
                continue
            if re.fullmatch(r'\d+(?:[.\-\/]\d+)+', w):  #  del число с разделителями
                continue
            if re.fullmatch(r'\d+(?:[.,]\d+)?\s*-\s*\d+(?:[.,]\d+)?', w):  # delete числовые значения с тире
                continue
            if w in ru_stop:  # del стоп-слова
                continue
            filtered_text.append(w)
    return filtered_text


def abb(tokens):
    #abriviations/ short
    abbreviation = {
        'б.п.': 'базисный пункт',
        'б.п': 'базисный пункт',
        'рф': 'российская федерация',
        'млн': 'миллион',
        'млрд': 'миллиард',
        'г': 'год',
        'г.': 'год',
        'офз': 'облигации федерального займа'
    }
    result = []
    for w in tokens:
        key = w
        if key in abbreviation:
            result.extend(abbreviation[key].split())
        else:
            key2 = w.replace('.', '')
            if key2 in abbreviation:
                result.extend(abbreviation[key2].split())
            else:
                result.append(w)
    return result


def lemma(tokens):
    # initial form of the word / lemma listing
    lemma_list = [morph.parse(word)[0].normal_form for word in tokens]

    return lemma_list


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
    # Функция выделяем решени по ключевой ставке: +1 / -1 / 0 / nan

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


def key_rate(text):
    # Функция возвращает размер ключевой ставки key rate size number.,nember%

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
            left = s[max(0, m.start() - 6):m.start()]
            right = s[m.end(): m.end() + 6]
            if re.search(fr'\d\s*{dash}\s*$', left) or re.search(fr'^{dash}\s*\d', right):
                continue
            window = s[max(0, m.start() - 30): m.end() + 30]
            score = 0
            if re.search(r'\b(до|на\s+уровне|состав(ит|лял[аи]|ляет)|установ(лен[ао]?|ить))\b', window):
                score += 2
            candidates.append((score, val))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], - (10 <= x[1] <= 25)), reverse=True)
    return round(candidates[0][1], 2)


def get_ngrams(tokens, n=2):
    if not isinstance(tokens, list) or len(tokens) < n:
        return []
    if n == 2:
        return list(zip(tokens, tokens[1:]))
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def process_series(text_sr: pd.Series, title_sr: pd.Series = None):
    # dict
    if title_sr is not None:
        raw = (title_sr.fillna('') + ' ' + text_sr.fillna('')).str.strip()
    else:
        raw = text_sr.fillna('')

    cleaned = text_sr.fillna("").map(clean)  # убираем NaN значения и применяем функция очиски текста
    sents = cleaned.map(sentence)  # применяем функцию разделения по предложениям к очищенному тексту
    tokens = sents.map(stopword).map(
        abb)  # применяем функцию очистки от стоп слов к разделенному по предложениям тексту, расшифровки аббревитарур
    lemmas = tokens.map(lemma)  # применяем функцию лемматизации к токенам с расшифроваными аббревиатурами
    bigrams = lemmas.map(lambda lst: get_ngrams(lst, 2))
    decisions = raw.map(decision_key_rate)
    rates = raw.map(key_rate)

    return {
        "clean": cleaned,
        "sentences": sents,
        "tokens": tokens,
        "lemmas": lemmas,
        "bigrams": bigrams,
        "decision": decisions,
        "key_rate": rates
    }


# прогоняем столбец "текст" через функцию process_series и возвращаем
# в новые колонки в таблице
text_add = process_series(data.text, data.title)
data['text_clean'] = text_add['clean']
data['text_sentences'] = text_add['sentences']
data['text_tokens'] = text_add['tokens']
data['text_lemmas'] = text_add['lemmas']
data['text_bigrams'] = text_add['bigrams']

# прогоняем столбец "заголовок" через функцию process_series и возвращаем
# в новые колонки в таблице
title_add = process_series(data.title)
data['title_clean'] = title_add['clean']
data['title_sentences'] = title_add['sentences']
data['title_tokens'] = title_add['tokens']
data['title_lemmas'] = title_add['lemmas']
data['title_bigrams'] = title_add['bigrams']

data['decision'] = text_add['decision']
data['key_rate'] = text_add['key_rate']

data.to_json('cbr_key-rate_press_releases_processed.json', orient='records', force_ascii=False, indent=2)