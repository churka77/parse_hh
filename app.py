from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import sqlite3

app = Flask(__name__, template_folder="templates")

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/vacancies')
def view_vacancies():
    company = request.args.get('company', '')
    salary = request.args.get('salary', '')
    location = request.args.get('location', '')

    print(f'Фильтр: компания={company}, зарплата={salary}, местоположение={location}')

    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    
    query = "SELECT title, salary, company, location FROM vacancies WHERE 1=1"
    params = []

    if company:
        query += " AND company LIKE ?"
        params.append(f'%{company}%')
    
    if salary:
        query += " AND salary LIKE ?"
        params.append(f'%{salary}%')
    
    if location:
        query += " AND location LIKE ?"
        params.append(f'%{location}%')

    cursor.execute(query, params)
    vacancies = cursor.fetchall()
    conn.close()

    print(f'Найдено вакансий: {len(vacancies)}')

    if request.headers.get('Accept') == 'application/json':
        return jsonify({'vacancies': vacancies})
    else:
        return render_template('vacancies.html', vacancies=vacancies)

def get_html(url, params=None):
    user_agent = UserAgent()
    headers = {'User-Agent': user_agent.random}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.text

def get_vacancies_list(html):
    soup = BeautifulSoup(html, features="html.parser")
    vacancies = soup.find_all(class_='vacancy-search-item__card')
    vacancies_list = []
    for i in vacancies:
        if i:
            soupchik = BeautifulSoup(str(i), features="html.parser")
            vacancy_name = soupchik.select_one('span[class*="vacancy-name"]').get_text()
            vacancy_salary = soupchik.select_one('span[class*="compensation-text"]').get_text() if soupchik.select_one('span[class*="compensation-text"]') is not None else 'Не указана'
            vacancy_company = soupchik.select_one('span[class*="company-info-text"]').get_text() if soupchik.select_one('span[class*="company-info-text"]') is not None else 'Не указана'
            vacancy_region = soupchik.select_one('span[data-qa*="vacancy-serp__vacancy-address"]').get_text()
            vacancies_list.append(([vacancy_name, vacancy_salary, vacancy_company, vacancy_region]))
    return vacancies_list

def fetch_all_vacancies(base_url, params):
    all_vacancies = []
    page_number = 0
    while True:
        params['page'] = page_number
        try:
            html = get_html(base_url, params=params)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                break
            else:
                raise
        vacancies = get_vacancies_list(html)
        if not vacancies:
            break
        all_vacancies.extend(vacancies)
        page_number += 1
    return all_vacancies

@app.route('/fetch_vacancies', methods=['GET'])
def fetch_vacancies():
    query = request.args.get('query')
    experience_id = request.args.get('experience_id', default=0, type=int)
    education_options = request.args.getlist('education_options', type=int)
    employment_options = request.args.getlist('employment_options', type=int)

    if not query:
        return jsonify({'error': 'Запрос не указан'}), 400

    base_url = 'https://hh.ru/search/vacancy'
    experience = ['', 'noExperience', 'between1And3', 'between3And6', 'moreThan6']
    education = ['', 'not_required_or_not_specified', 'higher', 'special_secondary']
    employment = ['', 'full', 'part', 'probation', 'project', 'volunteer']

    params = {'text': query, 'area': 1}
    
    if experience_id != 0:
        params['experience'] = experience[experience_id]

    if education_options != [0]:
        params['education'] = '&'.join([education[option] for option in education_options if option != 0])

    if employment_options != [0]:
        params['employment'] = '&'.join([employment[option] for option in employment_options if option != 0])

    all_vacancies = fetch_all_vacancies(base_url, params)
    save_vacancies_to_db(all_vacancies)
    return jsonify({'count': len(all_vacancies)})

def save_vacancies_to_db(vacancies):
    conn = sqlite3.connect('vacancies.db')
    cursor = conn.cursor()
    
    cursor.execute('''DROP TABLE IF EXISTS vacancies''')
    cursor.execute('''CREATE TABLE vacancies
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       title TEXT,
                       salary TEXT,
                       company TEXT,
                       location TEXT)''')
    
    cursor.executemany('INSERT INTO vacancies (title, salary, company, location) VALUES (?, ?, ?, ?)', vacancies)
    conn.commit()
    conn.close()

if __name__ == '__main__':
    app.run(debug=True)
