import pandas as pd
import requests
from bs4 import BeautifulSoup
import csv

with open('currency_rate.csv', 'w', encoding='utf-8') as file: 
    writer = csv.writer(file) 
    writer.writerow(['date', 'dollar_rate'])

response = requests.get('https://cbr.ru/currency_base/dynamics/?UniDbQuery.Posted=True&UniDbQuery.so=1&UniDbQuery.mode=1&UniDbQuery.date_req1=&UniDbQuery.date_req2=&UniDbQuery.VAL_NM_RQ=R01235&UniDbQuery.From=01.01.2013&UniDbQuery.To=07.11.2025') 
response.encoding = 'utf-8'
soup = BeautifulSoup(response.text, "html.parser") 
table = soup.find('table')
rows = table.find_all('tr')

for row in rows[2:]:
    columns = row.find_all('td')
    date = columns[0].text
    dollar_rate = columns[2].text
    with open('currency_rate.csv', 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([date, dollar_rate])