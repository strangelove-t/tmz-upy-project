"""Entrada de la aplicación: autenticación, tema y navegación."""

import streamlit as st

from tamizaje.ui import NAVIGATION, apply_theme, require_authentication

st.set_page_config(page_title="Tamizaje UPY", page_icon="🎓", layout="wide")
require_authentication()
apply_theme()
st.navigation(
    [st.Page(page.path, title=page.title, icon=page.icon) for page in NAVIGATION]
).run()
