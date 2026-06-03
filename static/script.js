// Состояние приложения
let chatHistory = [];
let currentPage = 1;
let currentQuery = 'fantasy';

// DOM элементы
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const exportCsvBtn = document.getElementById('exportCsvBtn');
const booksGrid = document.getElementById('booksGrid');
const prevPageBtn = document.getElementById('prevPage');
const nextPageBtn = document.getElementById('nextPage');
const pageIndicator = document.getElementById('pageIndicator');
const themeTitle = document.getElementById('themeTitle');

// Модальное окно
const modal = document.getElementById('bookModal');
const closeModal = document.querySelector('.close-modal');
const modalCover = document.getElementById('modalCover');
const modalTitle = document.getElementById('modalTitle');
const modalAuthor = document.getElementById('modalAuthor');
const modalYear = document.getElementById('modalYear');
const modalPitch = document.getElementById('modalPitch');

// === Инициализация ===
document.addEventListener('DOMContentLoaded', () => {
    loadBooks(currentPage);
});

// === Чат ===
sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    // Добавляем сообщение пользователя
    addMessageToUI('user', text);
    chatHistory.push({ role: 'user', content: text });
    chatInput.value = '';

    // Показываем индикатор загрузки
    const loadingId = addMessageToUI('ai', 'Печатает...');

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ history: chatHistory })
        });
        const data = await response.json();

        // Удаляем "Печатает..." и добавляем реальный ответ
        document.getElementById(loadingId).remove();
        addMessageToUI('ai', data.reply);
        chatHistory.push({ role: 'assistant', content: data.reply });
    } catch (error) {
        document.getElementById(loadingId).remove();
        addMessageToUI('ai', 'Извините, произошла ошибка соединения.');
    }
}

function addMessageToUI(role, text) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.id = 'msg-' + Date.now();
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div.id;
}

// Экспорт чата в CSV
exportCsvBtn.addEventListener('click', () => {
    if (chatHistory.length === 0) {
        alert('Чат пуст');
        return;
    }

    // Добавляем BOM (\ufeff) для корректного открытия в Excel
    let csvContent = "\uFEFFRole,Message,Timestamp\n";
    chatHistory.forEach(msg => {
        const escapedMessage = `"${msg.content.replace(/"/g, '""')}"`;
        const timestamp = new Date().toISOString();
        csvContent += `${msg.role},${escapedMessage},${timestamp}\n`;
    });

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'chat_history.csv';
    link.click();
});

// === Книги и Пагинация ===
async function loadBooks(page) {
    booksGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: #666;">Загрузка книг...</p>';

    try {
        const response = await fetch(`/api/books?query=${encodeURIComponent(currentQuery)}&page=${page}`);
        const data = await response.json();

        booksGrid.innerHTML = '';
        if (data.books.length === 0) {
            booksGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center;">Книги не найдены.</p>';
            return;
        }

        data.books.forEach(book => {
            const card = document.createElement('div');
            card.className = 'book-card';
            card.innerHTML = `
                <img src="${book.cover || 'https://via.placeholder.com/150x200?text=No+Cover'}" class="book-cover" alt="${book.title}">
                <div class="book-title">${book.title}</div>
                <div class="book-author">${book.author}</div>
                <div class="book-year">${book.year}</div>
            `;
            card.addEventListener('click', () => openBookModal(book));
            booksGrid.appendChild(card);
        });

        currentPage = data.current_page;
        pageIndicator.textContent = `Страница ${currentPage}`;
        prevPageBtn.disabled = currentPage <= 1;
        // Упрощенная логика: если книг меньше 12, значит это последняя страница
        nextPageBtn.disabled = data.books.length < 12;

    } catch (error) {
        booksGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: red;">Ошибка загрузки книг.</p>';
    }
}

prevPageBtn.addEventListener('click', () => {
    if (currentPage > 1) loadBooks(currentPage - 1);
});

nextPageBtn.addEventListener('click', () => {
    loadBooks(currentPage + 1);
});

// === Модальное окно и AI-питч ===
function openBookModal(book) {
    modalCover.src = book.cover || 'https://via.placeholder.com/250x350?text=No+Cover';
    modalTitle.textContent = book.title;
    modalAuthor.textContent = book.author;
    modalYear.textContent = `Год издания: ${book.year}`;
    modalPitch.textContent = 'Генерация персональной рекомендации...';
    modal.style.display = 'flex';

    // Запрос питча у AI
    fetch('/api/pitch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: book.title, author: book.author })
    })
    .then(res => res.json())
    .then(data => {
        modalPitch.textContent = data.pitch;
    })
    .catch(() => {
        modalPitch.textContent = 'Не удалось загрузить рекомендацию. Попробуйте позже.';
    });
}

closeModal.addEventListener('click', () => {
    modal.style.display = 'none';
});

window.addEventListener('click', (e) => {
    if (e.target === modal) {
        modal.style.display = 'none';
    }
});