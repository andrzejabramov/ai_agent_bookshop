import os
import json
import time
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# 1. Загружаем переменные окружения
load_dotenv()

app = Flask(__name__)

# 2. Все константы в одном месте
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPEN_LIBRARY_URL = "https://openlibrary.org/search.json"

# Проверка ключа при старте
if OPENROUTER_API_KEY:
    print(f"🔑 КЛЮЧ ЗАГРУЖЕН: {OPENROUTER_API_KEY[:15]}...")
else:
    print("❌ ВНИМАНИЕ: OPENROUTER_API_KEY не найден в .env файле!")

# 3. Загрузка базы знаний
KNOWLEDGE_BASE = {
    "shop_info": {"name": "Умная Полка", "description": "Книжный магазин", "hours": "10:00-22:00",
                  "delivery": "По всей РФ", "payment": "Карты, СБП"},
    "genres": {},
    "faq": {}
}

try:
    with open('knowledge_base.json', 'r', encoding='utf-8') as f:
        KNOWLEDGE_BASE = json.load(f)
    print("✅ База знаний (knowledge_base.json) загружена!")
except FileNotFoundError:
    print("⚠️ Файл knowledge_base.json не найден.")
except Exception as e:
    print(f"⚠️ Ошибка чтения knowledge_base.json: {e}")

# 4. Системный промпт
shop = KNOWLEDGE_BASE.get("shop_info", {})
genres_list = ", ".join([f"{v.get('name', k)}" for k, v in KNOWLEDGE_BASE.get("genres", {}).items()])

SYSTEM_PROMPT = f"""Ты — дружелюбный консультант книжного магазина "{shop.get('name', 'Умная Полка')}". 
{shop.get('description', '')}.
Часы работы: {shop.get('hours', '10:00-22:00')}. Доставка: {shop.get('delivery', 'По РФ')}.
Жанры в наличии: {genres_list or 'Различные'}.
Отвечай КРАТКО (2-4 предложения), по делу, на русском языке. Давай конкретные рекомендации."""

# 5. === ДИНАМИЧЕСКИЙ КЭШ БЕСПЛАТНЫХ МОДЕЛЕЙ ===
FREE_MODELS_CACHE = []
LAST_MODEL_FETCH = 0


def get_available_free_models():
    """Получает актуальный список бесплатных моделей с OpenRouter API"""
    global FREE_MODELS_CACHE, LAST_MODEL_FETCH

    # Обновляем не чаще раза в час
    if time.time() - LAST_MODEL_FETCH < 3600 and FREE_MODELS_CACHE:
        return FREE_MODELS_CACHE

    try:
        print("🔄 Загрузка актуального списка моделей с OpenRouter...")
        headers = {}
        if OPENROUTER_API_KEY:
            headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"

        response = requests.get(OPENROUTER_MODELS_URL, headers=headers, timeout=15)
        response.raise_for_status()
        models_data = response.json().get("data", [])

        print(f"📊 Всего моделей в каталоге OpenRouter: {len(models_data)}")

        # Фильтруем бесплатные модели
        # ВАЖНО: цены в API приходят СТРОКАМИ ("0"), а не числами!
        free_models = []
        for m in models_data:
            model_id = m.get("id", "")
            pricing = m.get("pricing", {})

            # Бесплатная модель, если:
            # 1) ID заканчивается на :free ИЛИ
            # 2) Все цены равны строке "0"
            is_free = model_id.endswith(":free") or (
                    pricing.get("prompt") == "0" and
                    pricing.get("completion") == "0"
            )

            # Дополнительно проверяем, что модель активна (имеет контекст)
            has_context = m.get("context_length", 0) > 0

            if is_free and has_context:
                free_models.append(model_id)

        # Берем первые 10 моделей (этого более чем достаточно)
        FREE_MODELS_CACHE = free_models[:10]
        LAST_MODEL_FETCH = time.time()

        if FREE_MODELS_CACHE:
            print(f"✅ Найдено {len(FREE_MODELS_CACHE)} бесплатных моделей:")
            for i, model in enumerate(FREE_MODELS_CACHE, 1):
                print(f"   {i}. {model}")
        else:
            print("⚠️ Бесплатные модели не найдены! Используем запасные...")
            FREE_MODELS_CACHE = [
                "meta-llama/llama-3.3-70b-instruct:free",
                "qwen/qwen-2.5-7b-instruct:free",
                "google/gemma-3-1b-it:free",
                "mistralai/mistral-small-3.1-24b-instruct:free",
                "deepseek/deepseek-chat-v3-0324:free"
            ]

        return FREE_MODELS_CACHE

    except Exception as e:
        print(f"⚠️ Ошибка загрузки списка моделей: {e}")
        # Запасной список на случай недоступности API
        return [
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen-2.5-7b-instruct:free",
            "google/gemma-3-1b-it:free",
            "mistralai/mistral-small-3.1-24b-instruct:free"
        ]


# 6. === ПОИСК ПО БАЗЕ ЗНАНИЙ ===
def search_in_knowledge_base(query):
    """Простая и надежная база знаний"""
    query_lower = query.lower()

    # Приветствие
    if query_lower.strip() in ["привет", "здравствуйте", "добрый день", "хай"]:
        return "⚡ Здравствуйте! Рад видеть вас в нашем магазине. Могу рассказать о жанрах, доставке или помочь выбрать книгу. Что вас интересует?"

    # Доставка
    if any(word in query_lower for word in ["доставк", "привез", "срок", "курьер"]):
        return "⚡ Доставляем по всей России. Москва и СПб — 1-2 дня, регионы — 3-7 дней. Бесплатная доставка от 2000₽."

    # Оплата
    if any(word in query_lower for word in ["оплат", "деньг", "карт", "наличн", "сбп"]):
        return "⚡ Принимаем банковские карты, СБП, электронные кошельки. При получении можно оплатить наличными или картой."

    # Возврат
    if any(word in query_lower for word in ["возврат", "вернуть", "обмен"]):
        return "⚡ Возврат в течение 14 дней, если книга не подошла. Главное — сохранить товарный вид."

    # Скидки
    if any(word in query_lower for word in ["скидк", "промокод", "бонус", "акци"]):
        return "⚡ Скидка 10% на первый заказ по промокоду WELCOME. Постоянным клиентам — накопительная система."

    # Жанры (общий вопрос)
    if any(word in query_lower for word in ["жанр", "тематик", "категор"]):
        return "⚡ У нас есть отличные книги в жанрах: Фэнтези, Детективы, Научная фантастика, Классика. Уточните, что вам ближе, и я подберу конкретные книги!"

    # Фэнтези
    if "фэнтези" in query_lower:
        return "⚡ В жанре Фэнтези рекомендую:\n• Властелин колец (Дж.Р.Р. Толкин) — Классика эпического фэнтези\n• Имя ветра (Патрик Ротфусс) — Потрясающая история становления мага\n• Ученик убийцы (Робин Хобб) — Глубокий психологический фэнтези-роман"

    # Детективы
    if "детектив" in query_lower:
        return "⚡ В жанре Детективы рекомендую:\n• Девушка с татуировкой дракона (Стиг Ларссон) — Захватывающий скандинавский нуар\n• Убийство в Восточном экспрессе (Агата Кристи) — Классика жанра\n• Шерлок Холмс (Артур Конан Дойл) — Бессмертная классика"

    # Научная фантастика
    if "научн" in query_lower or "нф " in query_lower or " фантастик" in query_lower:
        return "⚡ В жанре Научная фантастика рекомендую:\n• Дюна (Фрэнк Герберт) — Эпическая сага о политике и экологии\n• Основание (Айзек Азимов) — Масштабная история галактической империи\n• Марсианин (Энди Вейер) — Наука и выживание с юмором"

    # Классика
    if "классик" in query_lower:
        return "⚡ В жанре Классика рекомендую:\n• Преступление и наказание (Ф.М. Достоевский) — Глубокое исследование души\n• Мастер и Маргарита (М.А. Булгаков) — Философский роман с мистикой\n• 1984 (Джордж Оруэлл) — Пугающе актуальная антиутопия"

    # Подарок ребенку
    if "подар" in query_lower and "ребен" in query_lower:
        return "⚡ Для детей рекомендую:\n• Маленький принц (Сент-Экзюпери) — Философская сказка для всех возрастов\n• Гарри Поттер (Дж.К. Роулинг) — Волшебный мир магии и дружбы\n• Хроники Нарнии (К.С. Льюис) — Приключения в волшебной стране"

    # Общие рекомендации
    if any(word in query_lower for word in ["посоветуй", "порекоменд", "что почитать", "выбрать"]):
        return "⚡ С удовольствием помогу! Уточните, пожалуйста:\n• Какой жанр вас интересует? (Фэнтези, Детективы, Научная фантастика, Классика)\n• Для кого книга? (Для себя, в подарок, для ребенка)\n• Какое настроение хотите? (Легкое, глубокое, захватывающее)"

    return None


# === МАРШРУТЫ ===

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    history = data.get("history", [])
    user_message = history[-1]["content"] if history else ""

    print(f"\n📩 ЗАПРОС: {user_message}")

    # Уровень 1: Локальная база (мгновенно)
    local_answer = search_in_knowledge_base(user_message)
    if local_answer:
        print("✅ ОТВЕТ ИЗ ЛОКАЛЬНОЙ БАЗЫ")
        return jsonify({"reply": local_answer, "source": "local"})

    print("🤖 ИДЕМ В AI...")

    # Уровень 2: AI с динамическим списком моделей
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://127.0.0.1:8088",
        "X-Title": "AI Bookstore",
        "Content-Type": "application/json"
    }

    # Получаем актуальный список бесплатных моделей
    models_to_try = get_available_free_models()

    for model in models_to_try:
        print(f"🔄 Пробуем: {model}")
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 150
        }

        try:
            response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=20)

            if response.status_code == 429:
                print(f"   ⏱️ 429 — перегружена, следующая...")
                continue
            elif response.status_code == 404:
                print(f"   ❌ 404 — модель не найдена, следующая...")
                continue
            elif response.status_code != 200:
                print(f"   ❌ Ошибка {response.status_code}: {response.text[:100]}")
                continue

            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            print(f"   ✅ УСПЕХ! Ответ от {model}")
            return jsonify({"reply": reply, "source": "ai"})

        except requests.exceptions.Timeout:
            print(f"   ⏱️ Таймаут для {model}")
            continue
        except Exception as e:
            print(f"   💥 Ошибка: {e}")
            continue

    print("❌ ВСЕ МОДЕЛИ ОТКАЗАЛИ")
    return jsonify({
        "reply": "Извините, все бесплатные AI-модели сейчас перегружены. Но я могу ответить на вопросы о доставке, оплате или жанрах!",
        "source": "error"
    }), 200


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
        response = requests.get(OPEN_LIBRARY_URL, params=params, timeout=10)
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

    prompt = f"Коротко (1-2 предложения) и интригующе порекомендуй книгу '{title}' ({author}). Тон: уютный книжный продавец."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://127.0.0.1:8088",
        "X-Title": "AI Bookstore",
        "Content-Type": "application/json"
    }

    models_to_try = get_available_free_models()

    for model in models_to_try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100
        }

        try:
            response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=15)
            if response.status_code != 200:
                continue
            pitch = response.json()["choices"][0]["message"]["content"]
            return jsonify({"pitch": pitch})
        except Exception:
            continue

    return jsonify({"pitch": "Эта книга — настоящий подарок для любителя хорошей литературы!"})


# === ТОЧКА ВХОДА ===
if __name__ == '__main__':
    print("=" * 60)
    print("✅ СЕРВЕР ЗАПУЩЕН!")
    print("🌐 ОТКРОЙ: http://127.0.0.1:8088")
    print("=" * 60)
    app.run(debug=True, host='127.0.0.1', port=8088, use_reloader=False)