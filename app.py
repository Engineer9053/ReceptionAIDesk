import streamlit as st
from typing import Dict, Any, List
from utils.database import select_from_users
import pandas as pd

st.title("📋 Пользователи Telegram-бота")

# Фильтр по username
username_filter = st.text_input("🔍 Фильтр по username (оставь пустым для всех):")

filters: Dict[str, Any] = {}
if username_filter.strip():
    filters['username'] = username_filter.strip()

# Получаем пользователей из БД
users: List[Dict[str, Any]] = select_from_users(filters)

# Если есть пользователи — отображаем таблицу
if users:
    df = pd.DataFrame(users)
    df['created'] = pd.to_datetime(df['created']).dt.strftime("%Y-%m-%d %H:%M:%S")

    # Пагинация
    rows_per_page = 10
    total_rows = len(df)
    total_pages = (total_rows - 1) // rows_per_page + 1

    page = st.number_input("📄 Страница", min_value=1, max_value=total_pages, step=1)

    start_idx = (page - 1) * rows_per_page
    end_idx = start_idx + rows_per_page

    st.dataframe(df.iloc[start_idx:end_idx].reset_index(drop=True), use_container_width=True)
else:
    st.info("Пользователи не найдены.")