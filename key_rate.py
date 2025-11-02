import requests
from bs4 import BeautifulSoup
import spacy
import re

# Загрузка предварительно обученной модели для русского языка
nlp = spacy.load("ru_core_news_sm")

# Функция для получения содержимого веб-страницы
def get_web_content(url):

    text = requests.get(url).text

    return BeautifulSoup(text, 'html.parser').get_text()

# Функция для очистки лишних пробелов в тексте
def clean_spaces(text):
    # Удаление HTML-тегов, ссылок и специальных символов:
    text = re.sub(r'<[^>]+>|http\S+|[^\w\s\.\,\!]', '', text)
    # Замена чисел на специальный токен <NUM>:
    text = re.sub(r'\b\d+[\.,]?\d*\b', '<NUM>', text)    
    # Разделение текста по пробелам и объединение обратно через один пробел
    return ' '.join(text.split())

# Функция для фильтрации и лемматизации слов
def filter_words(text):
    # Обработка текста моделью spaCy
    doc = nlp(text.lower())
    # Извлечение базовых форм слов
    words = [token.lemma_ for token in doc if not token.is_punct and not token.is_space]
    # Множество стоп-слов
    stop_words = {'и','в','на','с','по','о'}
    # Объединение отфильтрованных слов
    return ' '.join(w for w in words if len(w) >= 3 and w not in stop_words)

# Функция для отображения результата
def show_result(text):

    print(f"Результат ({len(text)} символов):")

    print(text[:1500] + "..." if len(text) > 1500 else text)

# Основной блок выполнения программы

url = 'https://www.cbr.ru/'

original = get_web_content(url)

cleaned = clean_spaces(original)

filtered = filter_words(cleaned)

show_result(filtered)