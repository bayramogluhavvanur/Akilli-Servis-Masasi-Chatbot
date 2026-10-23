from typer import prompt
from google import genai
import db_mssql
import pandas as pd
from rag_engine import generate_chat_title, generate_helpdesk_response
import streamlit as st
import time
import rag_engine

st.set_page_config(
    page_title="BT Servis Masası Asistanı", page_icon="🛠️", layout="wide"
)
kurumsal_css = """
<style>
/* 1. Asistan (Bot) Mesaj Balonu Arka Planı (Açık Gri/Mavi) */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background-color: #f8f9fa;
    border-left: 4px solid #0056b3; /* Kurumsal mavi sol şerit */
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 10px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
}

/* 2. Kullanıcı Mesaj Balonu Arka Planı (Çok Açık Turkuaz/Yeşil) */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background-color: #e9f5ec;
    border-left: 4px solid #198754; /* Kurumsal yeşil sol şerit */
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 10px;
}

/* 3. Avatar İkonlarının Çevresini Düzenleme */
.st-emotion-cache-p4micv {
    background-color: white;
    border-radius: 50%;
    box-shadow: 0px 2px 4px rgba(0,0,0,0.1);
}
</style>
"""

st.markdown(kurumsal_css, unsafe_allow_html=True)

# Session State Değişkenleri
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "retry_prompt" not in st.session_state:
    st.session_state.retry_prompt = None
if "last_error" not in st.session_state:
    st.session_state.last_error = None

# --- 1. GİRİŞ VE KAYIT EKRANI ---
if not st.session_state.authenticated:
    st.title("🔐 BT Servis Masası Portalı")
    st.caption("Kurumsal teknik destek ve çözüm merkezine hoş geldiniz.")

    col1, _ = st.columns([1.5, 2.5])
    with col1:
        tab_login, tab_register = st.tabs(["🔑 Giriş Yap", "📝 Kayıt Ol"])

        with tab_login:
            with st.form(key="login_form"):
                login_username = st.text_input("Kullanıcı Adı")
                login_password = st.text_input("Şifre", type="password")

                submit_button = st.form_submit_button(
                    "Giriş Yap", type="primary", use_container_width=True
                )

                if submit_button:
                    if login_username and login_password:
                        user = db_mssql.authenticate_user(login_username, login_password)
                        if user:
                            st.session_state.authenticated = True
                            st.session_state.user_info = user

                            sessions = db_mssql.get_user_chat_sessions(user["user_id"])
                            if sessions:
                                st.session_state.session_id = sessions[0]["session_id"]
                                st.session_state.messages = db_mssql.get_session_messages(
                                    st.session_state.session_id
                                )
                            else:
                                st.session_state.session_id = db_mssql.create_chat_session(
                                    user["user_id"], "Yeni Destek Talebi"
                                )
                                st.session_state.messages = []
                            st.rerun()
                        else:
                            st.toast("Kullanıcı adı veya şifre hatalı!", icon="🚨")
                    else:
                        st.warning("Lütfen kullanıcı adı ve şifre giriniz.")

        with tab_register:
            st.subheader("Yeni Hesap Oluştur")
            reg_fullname = st.text_input("Ad Soyad", key="reg_name")
            reg_username = st.text_input("Kullanıcı Adı Belirleyin", key="reg_user")
            reg_email = st.text_input(
                "E-posta Adresi", key="reg_email", placeholder="ornek@sirket.com"
            )
            reg_password = st.text_input(
                "Şifre Belirleyin (En az 8 karakter, 1 Büyük, 1 Küçük, 1 Rakam)",
                type="password",
                key="reg_pass",
            )

            if st.button("Hesap Oluştur", use_container_width=True):
                if reg_fullname and reg_username and reg_email and reg_password:
                    success, msg = db_mssql.register_user(
                        reg_username, reg_email, reg_password, reg_fullname, role="user"
                    )
                    if success:
                        st.toast(msg, icon="✅")
                    else:
                        st.toast(msg, icon="❌")
                else:
                    st.toast("Lütfen tüm alanları doldurun.", icon="⚠️")

        st.stop()

# --- 2. ANA SOHBET VE GEÇMİŞ SOHBETLER PANELİ ---
user = st.session_state.get("user_info") or {}
is_admin = str(user.get("role", "user")).lower() == "admin"

with st.sidebar:
    st.header(f"👤 {user.get('full_name', 'Kullanıcı')}")
    st.caption(f"Rol: **{str(user.get('role', 'user')).upper()}**")

    view_mode = "💬 Destek Sohbeti"

    if is_admin:
        view_mode = st.radio(
            "Panel Seçimi:", ["💬 Destek Sohbeti", "📊 Admin Denetim Paneli"]
        )
        st.markdown("---")

    if view_mode == "💬 Destek Sohbeti":
        if st.button("➕ Yeni Sohbet Başlat", use_container_width=True, type="primary"):
            user_id = st.session_state.user_info["user_id"]
            new_session_id = db_mssql.create_chat_session(user_id, "Yeni Destek Talebi")
            st.session_state.session_id = new_session_id
            st.session_state.messages = []
            st.rerun()

    st.markdown("---")
    st.subheader("📜 Geçmiş Sohbetlerim")

    user_sessions = db_mssql.get_user_chat_sessions(user["user_id"])

    for sess in user_sessions:
        sid = sess["session_id"]
        title = sess["title"]
        date_str = sess["date"].strftime("%d.%m.%Y %H:%M") if sess["date"] else ""

        is_active = sid == st.session_state.session_id
        button_label = f"{'💬' if is_active else '📄'} {title} ({date_str})"

        if st.button(
            button_label,
            key=f"sess_{sid}",
            use_container_width=True,
            type="secondary" if not is_active else "primary",
        ):
            st.session_state.session_id = sid
            st.session_state.messages = db_mssql.get_session_messages(sid)
            st.rerun()

    st.markdown("---")
    if st.button("🚪 Çıkış Yap", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_info = None
        st.session_state.session_id = None
        st.session_state.messages = []
        st.rerun()

# Admin Paneli Görünümü
if is_admin and view_mode == "📊 Admin Denetim Paneli":
    st.title("📊 IT Helpdesk - Admin Denetim Paneli")
    st.markdown(
        "Chatbot performansını, en çok sorulan soruları ve sistem başarı oranlarını buradan takip edebilirsiniz."
    )

    metrics = db_mssql.get_chatbot_metrics()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="💬 Toplam Yanıtlanan Soru", value=metrics["toplam_yanit"])
    with col2:
        st.metric(
            label="🎯 Ortalama Benzerlik Skoru",
            value=f"%{metrics['ortalama_skor']*100:.1f}",
        )
    with col3:
        st.metric(
            label="📈 Tahmini Başarı Oranı (Skor >= %75)",
            value=f"%{metrics['basari_orani']:.1f}",
        )

    st.divider()

    st.subheader("🔥 En Çok Sorulan Destek Soruları")
    top_questions = db_mssql.get_top_questions(limit=10)

    if top_questions:
        df_top = pd.DataFrame(top_questions, columns=["Soru İçeriği", "Sorulma Sayısı"])
        st.bar_chart(df_top.set_index("Soru İçeriği"))

    st.divider()

    st.subheader("📋 Detaylı Veritabanı Log Kayıtları")
    logs = db_mssql.get_all_logs_for_admin()

    if logs:
        df_logs = pd.DataFrame(
            [list(row) for row in logs],
            columns=[
                "Kullanıcı",
                "Ad Soyad",
                "Oturum ID",
                "Gönderen",
                "Mesaj Metni",
                "Benzerlik Skoru",
                "Tarih",
            ],
        )
        st.dataframe(df_logs, use_container_width=True)
    else:
        st.write("Henüz kayıtlı log bulunmuyor.")

else:
    # --- NORMAL SOHBET EKRANI ---
    st.title("🛠️ BT Servis Masası Akıllı Asistanı")
    st.caption(f"Mevcut Oturum ID: `#{st.session_state.session_id}` ")

    user_prompts = [
        m["content"] for m in st.session_state.messages if m["role"] == "user"
    ]

    # Mesajları Ekrana Bas
    for message in st.session_state.messages:
        avatar_icon = "🧑‍💻" if message["role"] == "user" else "🛠️"
        safe_role = message.get("role") or "assistant"
        with st.chat_message(safe_role, avatar=avatar_icon):
            st.markdown(message["content"])
            if "sources" in message and message["sources"]:
                with st.expander("📚 Kullanılan Bilgi Bankası Kaynakları"):
                    for idx, source_item in enumerate(message["sources"], 1):
                        if (
                            isinstance(source_item, (list, tuple))
                            and len(source_item) >= 5
                        ):
                            src, cat, subj, ans, sim = source_item[:5]
                            st.markdown(
                                f"**{idx}. Kaynak:** `{src}` | **Kategori:** `{cat}` | **Benzerlik:** `%{float(sim)*100:.1f}`"
                            )
                            if subj:
                                st.caption(f"**Konu:** {subj}")
                        else:
                            st.markdown(str(source_item))

    def soruyu_hafizaya_al():
        secilen = st.session_state.get("quick_resend_select")
        if secilen and secilen != "--- Soru Seçin ---":
            st.session_state.retry_prompt = secilen

    if user_prompts:
        with st.expander("🔍 Bu Sohbette Sorduğunuz Sorular (Hızlı Tekrar Sor)"):
            st.selectbox(
                "Daha önce sorduğunuz bir soruyu seçip tekrar çalıştırabilirsiniz:",
                options=["--- Soru Seçin ---"] + list(reversed(user_prompts)),
                key="quick_resend_select",
            )
            st.button(
                "Soruyu Tekrar Gönder", on_click=soruyu_hafizaya_al, type="primary"
            )

    if not st.session_state.messages:
        st.markdown(
            "<h3 style='text-align: center; color: #555;'>👋 Size Nasıl Yardımcı Olabilirim?</h3>",
            unsafe_allow_html=True,
        )
        st.write("")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔑 Şifremi Unuttum", use_container_width=True):
                st.session_state.retry_prompt = "Şifremi unuttum, nasıl sıfırlayabilirim?"
                st.rerun()
        with col2:
            if st.button("🌍 VPN'e Bağlanamıyorum", use_container_width=True):
                st.session_state.retry_prompt = (
                    "VPN bağlantı hatası alıyorum, ne yapmalıyım?"
                )
                st.rerun()
        with col3:
            if st.button("🖨️ Yazıcı Çalışmıyor", use_container_width=True):
                st.session_state.retry_prompt = "Ofisteki yazıcıya belge gönderemiyorum."
                st.rerun()

    # --- SOHBET GİRDİSİ VE MESAJ İŞLEME ---
    prompt_to_use = None
    chat_input_val = st.chat_input("Sorunuzu yazın...")

    if chat_input_val:
        prompt_to_use = chat_input_val
    elif st.session_state.get("retry_prompt"):
        prompt_to_use = st.session_state.retry_prompt
        st.session_state.retry_prompt = None

    if prompt_to_use:
        # 1. Kullanıcı mesajını arayüze ekle ve veritabanına kaydet
        st.session_state.messages.append({"role": "user", "content": prompt_to_use})
        db_mssql.log_message(
            session_id=st.session_state.session_id, role="user", content=prompt_to_use
        )

        if len(st.session_state.messages) == 1:
            new_title = generate_chat_title(prompt_to_use)
            db_mssql.update_session_title_if_default(st.session_state.session_id, new_title)

        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt_to_use)

        # 2. Asistan yanıtını üret
        with st.chat_message("assistant", avatar="🛠️"):
            st.info("Sistem logları taranıyor...")

            with st.spinner("Bilgi bankası taranıyor ve yanıt hazırlanıyor..."):
                try:
                    response_text, relevant_docs = generate_helpdesk_response(
                        user_query=prompt_to_use,
                        chat_history=st.session_state.get("messages", []),
                    )

                    sources = relevant_docs

                    def stream_data(text):
                        for word in text.split(" "):
                            yield word + " "
                            time.sleep(0.02)

                    st.write_stream(stream_data(response_text))

                    if sources:
                        with st.expander("📚 Kullanılan Referans Dokümanlar"):
                            for doc in sources:
                                st.write(
                                    f"- **Kaynak:** {doc[0]} | **Kategori:** {doc[1]} | **Skor:** {doc[4]:.4f}"
                                )

                        feedback = st.feedback("thumbs", key=f"fb_{len(st.session_state.messages)}")
                        if feedback == 1:
                            st.toast("Harika! Geri bildiriminiz için teşekkürler.", icon="👍")
                        elif feedback == 0:
                            st.toast("Bunu geliştirmek için çalışacağız.", icon="👎")

                    st.session_state.messages.append(
                        {"role": "assistant", "content": response_text}
                    )

                    top_score = float(sources[0][4]) if sources and len(sources[0]) >= 5 else None

                    db_mssql.log_message(
                        session_id=st.session_state.session_id,
                        role="assistant",
                        content=response_text,
                        sources=sources,
                        score=top_score,
                    )

                    st.session_state.last_error = None

                except Exception as e:
                    st.error(f"Bir hata oluştu: {e}")
                    st.session_state.last_error = str(e)
                    st.session_state.retry_prompt = prompt_to_use

        st.rerun()