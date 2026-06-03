import os
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPEN_LIBRARY_URL = "https://openlibrary.org/search.json"

# Системный промпт для агента
SYSTEM_PROMPT = """Ты — дружелюбный и эрудированный продавец-консультант независимого книжного магазина "Умная Полка". 
Твоя цель — помогать посетителям находить книги, давать краткие рекомендации и поддерживать уютную атмосферу. 
Отвечай кратко (2-4 предложения), по делу, на русском языке."""


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + data.get("history", [])

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "AI Bookstore",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/llama-3-8b-instruct",  # Бесплатная/дешевая быстрая модель
        "messages": messages
    }

    try:
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"]
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/books', methods=['GET'])
def get_books():
    query = request.args.get('query', 'fantasy')
    page = request.args.get('page', 1)

    params = {
        'q': query,
        'page': page,
        'limit': 12,
        'fields': 'title,author_name,cover_i,first_publish_year'
    }

    try:
        response = requests.get(OPEN_LIBRARY_URL, params=params)
        response.raise_for_status()
        data = response.json()

        books = []
        for doc in data.get('docs', []):
            books.append({
                'title': doc.get('title', 'Без названия'),
                'author': ', '.join(doc.get('author_name', ['Неизвестный автор'])),
                'year': doc.get('first_publish_year', 'Год неизвестен'),
                'cover': f"https://covers.openlibrary.org/b/id/{doc.get('cover_i')}-M.jpg" if doc.get(
                    'cover_i') else None
            })

        return jsonify({
            'books': books,
            'total_pages': (data.get('num_found', 0) // 12) + 1,
            'current_page': int(page)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/pitch', methods=['POST'])
def generate_pitch():
    data = request.json
    title = data.get('title', 'Книга')
    author = data.get('author', 'Автор')

    prompt = f"Напиши короткое (2-3 предложения), продающее и интригующее описание для книги '{title}' автора {author}. Тон: дружелюбный книжный продавец, создающий уютную атмосферу."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "AI Bookstore",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/llama-3-8b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()
        pitch = response.json()["choices"][0]["message"]["content"]
        return jsonify({"pitch": pitch})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)