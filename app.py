"""Entrada de la aplicación: autenticación, tema y navegación."""

import streamlit as st

from tamizaje.ui import NAVIGATION, apply_theme, require_authentication

st.set_page_config(page_title="Tamizaje UPY", page_icon="🎓", layout="wide")
# La navegación se registra siempre (así Streamlit no muestra la lista
# automática de pages/), pero queda oculta hasta validar la contraseña.
navigation = st.navigation(
    [st.Page(page.path, title=page.title, icon=page.icon) for page in NAVIGATION],
    position="sidebar" if st.session_state.get("authenticated") else "hidden",
)
require_authentication()
apply_theme()
navigation.run()
