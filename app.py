import os
import json
import base64
from datetime import datetime
from io import BytesIO

import streamlit as st
import yaml
import pandas as pd
import altair as alt
from pypdf import PdfReader

try:
    from docx import Document  # provided by python-docx
except ImportError:
    Document = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
except ImportError:
    canvas = None
    letter = None

from openai import OpenAI
import google.generativeai as genai
from anthropic import Anthropic
import httpx


# =========================
# Constants & configuration
# =========================

ALL_MODELS = [
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "gpt-5-mini",  # optional
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    "claude-3-5-sonnet-2024-10",
    "claude-3-5-haiku-20241022",
    "grok-4-fast-reasoning",
    "grok-3-mini",
]

# 限定在 510(k) Review pipeline 中可選的模型
REVIEW_PIPELINE_MODELS = [
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gpt-4o-mini",
]

OPENAI_MODELS = {"gpt-4o-mini", "gpt-4.1-mini", "gpt-5-mini"}
GEMINI_MODELS = {
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
}
ANTHROPIC_MODELS = {
    "claude-3-5-sonnet-20210",
    "claude-3-5-sonnet-2024-10",
    "claude-3-5-haiku-20241022",
}
GROK_MODELS = {"grok-4-fast-reasoning", "grok-3-mini"}

AGENT_MODEL_CHOICES = [
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    "gpt-4o-mini",
    "gpt-5-mini",
]

PAINTER_STYLES = [
    "Van Gogh", "Monet", "Picasso", "Da Vinci", "Rembrandt",
    "Matisse", "Kandinsky", "Hokusai", "Yayoi Kusama", "Frida Kahlo",
    "Salvador Dali", "Rothko", "Pollock", "Chagall", "Basquiat",
    "Haring", "Georgia O'Keeffe", "Turner", "Seurat", "Escher"
]

LABELS = {
    "Dashboard": {"English": "Dashboard", "繁體中文": "儀表板"},
    "510k_tab": {"English": "510(k) Intelligence", "繁體中文": "510(k) 智能分析"},
    "510k_summary_studio": {
        "English": "510(k) Summary Studio",
        "繁體中文": "510(k) 摘要視覺儀表板",
    },
    "PDF → Markdown": {"English": "PDF → Markdown", "繁體中文": "PDF → Markdown"},
    "Summary & Entities": {"English": "Summary & Entities", "繁體中文": "綜合摘要與實體"},
    "Comparator": {"English": "Comparator", "繁體中文": "文件版本比較"},
    "Checklist & Report": {"English": "510(k) Review Pipeline", "繁體中文": "510(k) 審查全流程"},
    "Note Keeper & Magics": {"English": "Note Keeper & Magics", "繁體中文": "筆記助手與魔法"},
    "FDA Orchestration": {"English": "FDA Reviewer Orchestration", "繁體中文": "FDA 審查協同規劃"},
    "Dynamic Agents": {"English": "Dynamic Agents from Guidance", "繁體中文": "依據指引動態產生代理"},
    "Agents Config": {"English": "Agents Config Studio", "繁體中文": "代理設定工作室"},
    "Skill Studio": {"English": "SKILL & Catalog", "繁體中文": "SKILL 與知識庫"},
}

STYLE_CSS = {
    "Van Gogh": "body { background: radial-gradient(circle at top left, #243B55, #141E30); }",
    "Monet": "body { background: linear-gradient(120deg, #a1c4fd, #c2e9fb); }",
    "Picasso": "body { background: linear-gradient(135deg, #ff9a9e, #fecfef); }",
    "Da Vinci": "body { background: radial-gradient(circle, #f9f1c6, #c9a66b); }",
    "Rembrandt": "body { background: radial-gradient(circle, #2c1810, #0b090a); }",
    "Matisse": "body { background: linear-gradient(135deg, #ffecd2, #fcb69f); }",
    "Kandinsky": "body { background: linear-gradient(135deg, #00c6ff, #0072ff); }",
    "Hokusai": "body { background: linear-gradient(135deg, #2b5876, #4e4376); }",
    "Yayoi Kusama": "body { background: radial-gradient(circle, #ffdd00, #ff6a00); }",
    "Frida Kahlo": "body { background: linear-gradient(135deg, #f8b195, #f67280, #c06c84); }",
    "Salvador Dali": "body { background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d); }",
    "Rothko": "body { background: linear-gradient(135deg, #141E30, #243B55); }",
    "Pollock": "body { background: repeating-linear-gradient(45deg,#222,#222 10px,#333 10px,#333 20px); }",
    "Chagall": "body { background: linear-gradient(135deg, #a18cd1, #fbc2eb); }",
    "Basquiat": "body { background: linear-gradient(135deg, #f7971e, #ffd200); }",
    "Haring": "body { background: linear-gradient(135deg, #ff512f, #dd2476); }",
    "Georgia O'Keeffe": "body { background: linear-gradient(135deg, #ffefba, #ffffff); }",
    "Turner": "body { background: linear-gradient(135deg, #f8ffae, #43c6ac); }",
    "Seurat": "body { background: radial-gradient(circle, #e0eafc, #cfdef3); }",
    "Escher": "body { background: linear-gradient(135deg, #232526, #414345); }",
}


# =========================
# Helper: localization & style
# =========================

def t(key: str) -> str:
    lang = st.session_state.settings.get("language", "English")
    return LABELS.get(key, {}).get(lang, key)


def apply_style(theme: str, painter_style: str):
    css = STYLE_CSS.get(painter_style, "")
    if theme == "Dark":
        css += """
        body { color: #e0e0e0; }
        .stButton>button { background-color: #1f2933; color: white; border-radius: 999px; }
        .stTextInput>div>div>input, .stTextArea textarea {
          background-color: #111827; color: #e5e7eb; border-radius: 0.5rem;
        }"""
    else:
        css += """
        body { color: #111827; }
        .stButton>button { background-color: #2563eb; color: white; border-radius: 999px; }
        .stTextInput>div>div>input, .stTextArea textarea {
          background-color: #ffffff; color: #111827; border-radius: 0.5rem;
        }"""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# =========================
# LLM routing
# =========================

def get_provider(model: str) -> str:
    if model in OPENAI_MODELS:
        return "openai"
    if model in GEMINI_MODELS:
        return "gemini"
    if model in ANTHROPIC_MODELS:
        return "anthropic"
    if model in GROK_MODELS:
        return "grok"
    raise ValueError(f"Unknown model: {model}")


def call_llm(model: str, system_prompt: str, user_prompt: str,
             max_tokens: int = 12000, temperature: float = 0.2,
             api_keys: dict | None = None) -> str:
    provider = get_provider(model)
    api_keys = api_keys or {}

    def get_key(name: str, env_var: str) -> str:
        return api_keys.get(name) or os.getenv(env_var) or ""

    if provider == "openai":
        key = get_key("openai", "OPENAI_API_KEY")
        if not key:
            raise RuntimeError("Missing OpenAI API key.")
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content

    if provider == "gemini":
        key = get_key("gemini", "GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Missing Gemini API key.")
        genai.configure(api_key=key)
        llm = genai.GenerativeModel(model)
        resp = llm.generate_content(
            system_prompt + "\n\n" + user_prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        return resp.text

    if provider == "anthropic":
        key = get_key("anthropic", "ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Missing Anthropic API key.")
        client = Anthropic(api_key=key)
        resp = client.messages.create(
            model=model,
            system=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return resp.content[0].text

    if provider == "grok":
        key = get_key("grok", "GROK_API_KEY")
        if not key:
            raise RuntimeError("Missing Grok (xAI) API key.")
        with httpx.Client(base_url="https://api.x.ai/v1", timeout=60) as client:
            resp = client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]


# =========================
# Generic helpers
# =========================

def show_status(step_name: str, status: str):
    color = {
        "pending": "gray",
        "running": "#f59e0b",
        "done": "#10b981",
        "error": "#ef4444",
    }.get(status, "gray")
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;margin-bottom:0.25rem;">
          <div style="width:10px;height:10px;border-radius:50%;background:{color};margin-right:6px;"></div>
          <span style="font-size:0.9rem;">{step_name} – <b>{status}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def log_event(tab: str, agent: str, model: str, tokens_est: int):
    st.session_state["history"].append({
        "tab": tab,
        "agent": agent,
        "model": model,
        "tokens_est": tokens_est,
        "ts": datetime.utcnow().isoformat()
    })


def extract_pdf_pages_to_text(file, start_page: int, end_page: int) -> str:
    reader = PdfReader(file)
    n = len(reader.pages)
    start = max(0, start_page - 1)
    end = min(n, end_page)
    texts = []
    for i in range(start, end):
        try:
            texts.append(reader.pages[i].extract_text() or "")
        except Exception:
            texts.append("")
    return "\n\n".join(texts)


def extract_docx_to_text(file) -> str:
    if Document is None:
        return ""
    try:
        bio = BytesIO(file.read())
        doc = Document(bio)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def create_pdf_from_text(text: str) -> bytes:
    if canvas is None or letter is None:
        raise RuntimeError(
            "PDF generation library 'reportlab' is not installed. "
            "Please add 'reportlab' to your Space requirements."
        )
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    margin = 72
    line_height = 14
    y = height - margin
    for line in text.splitlines():
        if y < margin:
            c.showPage()
            y = height - margin
        c.drawString(margin, y, line[:2000])
        y -= line_height
    c.save()
    buf.seek(0)
    return buf.getvalue()


def show_pdf(pdf_bytes: bytes, height: int = 600):
    if not pdf_bytes:
        return
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_html = f"""
    <iframe src="data:application/pdf;base64,{b64}"
            width="100%" height="{height}" type="application/pdf"></iframe>
    """
    st.markdown(pdf_html, unsafe_allow_html=True)


def agent_run_ui(
    agent_id: str,
    tab_key: str,
    default_prompt: str,
    default_input_text: str = "",
    allow_model_override: bool = True,
    tab_label_for_history: str | None = None,
):
    agents_cfg = st.session_state["agents_cfg"]
    agent_cfg = agents_cfg["agents"][agent_id]
    status_key = f"{tab_key}_status"
    if status_key not in st.session_state:
        st.session_state[status_key] = "pending"

    show_status(agent_cfg.get("name", agent_id), st.session_state[status_key])

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        user_prompt = st.text_area(
            "Prompt",
            value=st.session_state.get(f"{tab_key}_prompt", default_prompt),
            height=160,
            key=f"{tab_key}_prompt",
        )
    with col2:
        base_model = agent_cfg.get("model", st.session_state.settings["model"])
        model_index = ALL_MODELS.index(base_model) if base_model in ALL_MODELS else 0
        model = st.selectbox(
            "Model",
            ALL_MODELS,
            index=model_index,
            disabled=not allow_model_override,
            key=f"{tab_key}_model",
        )
    with col3:
        max_tokens = st.number_input(
            "max_tokens",
            min_value=1000,
            max_value=120000,
            value=st.session_state.settings["max_tokens"],
            step=1000,
            key=f"{tab_key}_max_tokens",
        )

    input_text = st.text_area(
        "Input Text / Markdown",
        value=st.session_state.get(f"{tab_key}_input", default_input_text),
        height=260,
        key=f"{tab_key}_input",
    )

    run = st.button("Run Agent", key=f"{tab_key}_run")

    if run:
        st.session_state[status_key] = "running"
        show_status(agent_cfg.get("name", agent_id), "running")
        api_keys = st.session_state.get("api_keys", {})
        system_prompt = agent_cfg.get("system_prompt", "")
        user_full = f"{user_prompt}\n\n---\n\n{input_text}"

        with st.spinner("Running agent..."):
            try:
                out = call_llm(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_full,
                    max_tokens=max_tokens,
                    temperature=st.session_state.settings["temperature"],
                    api_keys=api_keys,
                )
                st.session_state[f"{tab_key}_output"] = out
                st.session_state[status_key] = "done"
                token_est = int(len(user_full + out) / 4)
                log_event(
                    tab_label_for_history or tab_key,
                    agent_cfg.get("name", agent_id),
                    model,
                    token_est,
                )
            except Exception as e:
                st.session_state[status_key] = "error"
                st.error(f"Agent error: {e}")

    output = st.session_state.get(f"{tab_key}_output", "")
    view_mode = st.radio(
        "View mode", ["Markdown", "Plain text"],
        horizontal=True, key=f"{tab_key}_viewmode"
    )
    if view_mode == "Markdown":
        edited = st.text_area(
            "Output (Markdown, editable)",
            value=output,
            height=320,
            key=f"{tab_key}_output_md",
        )
    else:
        edited = st.text_area(
            "Output (Plain text, editable)",
            value=output,
            height=320,
            key=f"{tab_key}_output_txt",
        )

    st.session_state[f"{tab_key}_output_edited"] = edited


# =========================
# Sidebar
# =========================

def render_sidebar():
    with st.sidebar:
        st.markdown("### Global Settings")

        st.session_state.settings["theme"] = st.radio(
            "Theme", ["Light", "Dark"],
            index=0 if st.session_state.settings["theme"] == "Light" else 1,
        )
        st.session_state.settings["language"] = st.radio(
            "Language", ["English", "繁體中文"],
            index=0 if st.session_state.settings["language"] == "English" else 1,
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            style = st.selectbox(
                "Painter Style",
                PAINTER_STYLES,
                index=PAINTER_STYLES.index(st.session_state.settings["painter_style"]),
            )
        with col2:
            if st.button("Jackpot!"):
                import random
                style = random.choice(PAINTER_STYLES)
        st.session_state.settings["painter_style"] = style

        st.session_state.settings["model"] = st.selectbox(
            "Default Model",
            ALL_MODELS,
            index=ALL_MODELS.index(st.session_state.settings["model"]),
        )
        st.session_state.settings["max_tokens"] = st.number_input(
            "Default max_tokens",
            min_value=1000,
            max_value=120000,
            value=st.session_state.settings["max_tokens"],
            step=1000,
        )
        st.session_state.settings["temperature"] = st.slider(
            "Temperature",
            0.0,
            1.0,
            st.session_state.settings["temperature"],
            0.05,
        )

        st.markdown("---")
        st.markdown("### API Keys")

        keys = {}
        if os.getenv("OPENAI_API_KEY"):
            keys["openai"] = os.getenv("OPENAI_API_KEY")
            st.caption("OpenAI key from environment.")
        else:
            keys["openai"] = st.text_input("OpenAI API Key", type="password")

        if os.getenv("GEMINI_API_KEY"):
            keys["gemini"] = os.getenv("GEMINI_API_KEY")
            st.caption("Gemini key from environment.")
        else:
            keys["gemini"] = st.text_input("Gemini API Key", type="password")

        if os.getenv("ANTHROPIC_API_KEY"):
            keys["anthropic"] = os.getenv("ANTHROPIC_API_KEY")
            st.caption("Anthropic key from environment.")
        else:
            keys["anthropic"] = st.text_input("Anthropic API Key", type="password")

        if os.getenv("GROK_API_KEY"):
            keys["grok"] = os.getenv("GROK_API_KEY")
            st.caption("Grok key from environment.")
        else:
            keys["grok"] = st.text_input("Grok API Key", type="password")

        st.session_state["api_keys"] = keys

        st.markdown("---")
        st.markdown("### Agents Catalog (agents.yaml)")
        uploaded_agents = st.file_uploader(
            "Upload custom agents.yaml",
            type=["yaml", "yml"],
            key="sidebar_agents_yaml",
        )
        if uploaded_agents is not None:
            try:
                cfg = yaml.safe_load(uploaded_agents.read())
                if "agents" in cfg:
                    st.session_state["agents_cfg"] = cfg
                    st.success("Custom agents.yaml loaded for this session.")
                else:
                    st.warning("Uploaded YAML has no top-level 'agents' key. Using previous config.")
            except Exception as e:
                st.error(f"Failed to parse uploaded YAML: {e}")


# =========================
# Tabs
# =========================

def render_dashboard():
    st.title(t("Dashboard"))
    hist = st.session_state["history"]
    if not hist:
        st.info("No runs yet.")
        return
    df = pd.DataFrame(hist)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Runs", len(df))
    with col2:
        st.metric("Unique 510(k) Sessions", df[df["tab"].str.contains("510", na=False)].shape[0])
    with col3:
        st.metric("Approx Tokens Processed", int(df["tokens_est"].sum()))

    st.subheader("Runs by Tab")
    chart_tab = alt.Chart(df).mark_bar().encode(
        x="tab:N",
        y="count():Q",
        color="tab:N",
        tooltip=["tab", "count()"],
    )
    st.altair_chart(chart_tab, use_container_width=True)

    st.subheader("Runs by Model")
    chart_model = alt.Chart(df).mark_bar().encode(
        x="model:N",
        y="count():Q",
        color="model:N",
        tooltip=["model", "count()"],
    )
    st.altair_chart(chart_model, use_container_width=True)

    st.subheader("Token Usage Over Time")
    df_time = df.copy()
    df_time["ts"] = pd.to_datetime(df_time["ts"])
    chart_time = alt.Chart(df_time).mark_line(point=True).encode(
        x="ts:T",
        y="tokens_est:Q",
        color="tab:N",
        tooltip=["ts", "tab", "agent", "model", "tokens_est"],
    )
    st.altair_chart(chart_time, use_container_width=True)

    st.subheader("Recent Activity")
    st.dataframe(df.sort_values("ts", ascending=False).head(25), use_container_width=True)


def render_510k_tab():
    st.title(t("510k_tab"))
    col1, col2 = st.columns(2)
    with col1:
        device_name = st.text_input("Device Name")
        k_number = st.text_input("510(k) Number (e.g., K123456)")
    with col2:
        sponsor = st.text_input("Sponsor / Manufacturer (optional)")
        product_code = st.text_input("Product Code (optional)")
    extra_info = st.text_area("Additional context (indications, technology, etc.)")

    default_prompt = f"""
You are assisting an FDA 510(k) reviewer.

Task:
1. Search FDA resources (or emulate such search) for:
   - Device: {device_name}
   - 510(k) number: {k_number}
   - Sponsor: {sponsor}
   - Product code: {product_code}
2. Synthesize a detailed, review-oriented summary (約 3000–4000 字).
3. Provide at least 5 markdown tables.

Language: {st.session_state.settings["language"]}.
"""
    combined_input = f"""
=== Device Inputs ===
Device name: {device_name}
510(k) number: {k_number}
Sponsor: {sponsor}
Product code: {product_code}

Additional context:
{extra_info}
"""
    agent_run_ui(
        agent_id="fda_search_agent",
        tab_key="510k",
        default_prompt=default_prompt,
        default_input_text=combined_input,
        tab_label_for_history="510(k) Intelligence",
    )


# ====== 這裡省略 510(k) Summary Studio、PDF→Markdown、Summary & Entities、Comparator、FDA Orchestration、
# Dynamic Agents 等原本邏輯（可直接沿用你給的版本），僅對 510(k) Review Pipeline 與 Note Keeper 作關鍵強化 ======
# 為避免回答過長，下方僅展示關鍵兩個 tab 與 SKILL/Agents Config 的新段落。
# 若你要完整整合版，我可以在下一輪單獨貼上 full app.py。

# -------------------------
# 510(k) Review Pipeline
# -------------------------

def render_510k_review_pipeline_tab():
    st.title(t("Checklist & Report"))

    st.markdown("### Step 1 – 510(k) Submission Material → Organized Markdown")
    if "subm_status" not in st.session_state:
        st.session_state["subm_status"] = "pending"
    show_status("Submission Material Structuring", st.session_state["subm_status"])

    col_in1, col_in2 = st.columns(2)
    with col_in1:
        subm_input_mode = st.radio(
            "Input mode",
            ["Paste text / markdown", "Upload file (PDF/TXT/MD)"],
            horizontal=True,
            key="subm_input_mode",
        )
        raw_subm = ""
        if subm_input_mode == "Paste text / markdown":
            raw_subm = st.text_area(
                "Paste 510(k) submission material (text / markdown)",
                height=220,
                key="subm_paste_text",
            )
        else:
            f = st.file_uploader(
                "Upload 510(k) submission file",
                type=["pdf", "txt", "md"],
                key="subm_file",
            )
            if f is not None:
                suffix = f.name.lower().rsplit(".", 1)[-1]
                if suffix == "pdf":
                    raw_subm = extract_pdf_pages_to_text(f, 1, 9999)
                else:
                    raw_subm = f.read().decode("utf-8", errors="ignore")

    with col_in2:
        subm_model = st.selectbox(
            "Model for structuring submission",
            REVIEW_PIPELINE_MODELS,
            index=0,
            key="subm_model",
        )
        subm_max_tokens = st.number_input(
            "max_tokens",
            min_value=2000,
            max_value=120000,
            value=12000,
            step=1000,
            key="subm_max_tokens",
        )

    default_subm_prompt = st.session_state.get(
        "subm_prompt_default",
        """你是一位熟悉 FDA 510(k) 的審查員助手。

請將以下 510(k) 提交資料（可為文字或 Markdown）整理成 **結構化 Markdown 文件**：

1. 保留原始技術內容，不可憑空捏造。
2. 以 510(k) 審查實務為導向分段，例如：
   - 申請人與裝置基本資訊
   - 裝置描述與原理
   - 適應症與使用說明
   - 比較裝置 / Predicate 設備
   - 性能測試與驗證
   - 風險管理與風險控制
3. 盡可能將清單與條列轉為 Markdown 表格或項目符號。
4. 保持易讀且便於後續打勾式審查。

輸出語言：繁體中文或原文混合皆可，但標題盡量使用繁體中文。
"""
    )
    subm_prompt = st.text_area(
        "Prompt for structuring submission",
        value=default_subm_prompt,
        height=200,
        key="subm_prompt",
    )

    if st.button("Transform submission to organized Markdown", key="subm_run_btn"):
        if not raw_subm.strip():
            st.warning("Please paste or upload submission material first.")
        else:
            st.session_state["subm_status"] = "running"
            show_status("Submission Material Structuring", "running")
            api_keys = st.session_state.get("api_keys", {})
            system_prompt = "You are a 510(k) submission organizer. Follow the user's instructions carefully."
            user_prompt = subm_prompt + "\n\n=== SUBMISSION MATERIAL ===\n" + raw_subm
            with st.spinner("Structuring submission material..."):
                try:
                    out = call_llm(
                        model=subm_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=subm_max_tokens,
                        temperature=0.15,
                        api_keys=api_keys,
                    )
                    st.session_state["subm_md"] = out
                    st.session_state["subm_raw"] = raw_subm
                    st.session_state["subm_status"] = "done"
                    token_est = int(len(user_prompt + out) / 4)
                    log_event(
                        "510(k) Review Pipeline",
                        "Submission Structurer",
                        subm_model,
                        token_est,
                    )
                except Exception as e:
                    st.session_state["subm_status"] = "error"
                    st.error(f"Error structuring submission: {e}")

    subm_md = st.session_state.get("subm_md", "")
    st.markdown("#### Organized Submission (editable)")
    subm_view = st.radio(
        "View mode for submission",
        ["Markdown", "Plain text"],
        horizontal=True,
        key="subm_view_mode",
    )
    if subm_view == "Markdown":
        subm_md_edited = st.text_area(
            "Submission (Markdown)",
            value=subm_md,
            height=260,
            key="subm_md_edited",
        )
    else:
        subm_md_edited = st.text_area(
            "Submission (Plain text)",
            value=subm_md,
            height=260,
            key="subm_txt_edited",
        )
    st.session_state["subm_effective"] = subm_md_edited

    st.markdown("---")
    st.markdown("### Step 2 – Review Checklist → Organized Markdown")

    if "chk_status" not in st.session_state:
        st.session_state["chk_status"] = "pending"
    show_status("Checklist Structuring", st.session_state["chk_status"])

    col_ck1, col_ck2 = st.columns(2)
    with col_ck1:
        chk_input_mode = st.radio(
            "Checklist input mode",
            ["Paste text / markdown / CSV", "Upload (TXT/MD/CSV)"],
            horizontal=True,
            key="chk_input_mode",
        )
        raw_chk = ""
        if chk_input_mode.startswith("Paste"):
            raw_chk = st.text_area(
                "Paste checklist (text / markdown / CSV-like)",
                height=180,
                key="chk_paste",
            )
        else:
            f = st.file_uploader(
                "Upload checklist file",
                type=["txt", "md", "csv"],
                key="chk_file",
            )
            if f is not None:
                suffix = f.name.lower().rsplit(".", 1)[-1]
                if suffix == "csv":
                    df_ck = pd.read_csv(f)
                    raw_chk = df_ck.to_markdown(index=False)
                else:
                    raw_chk = f.read().decode("utf-8", errors="ignore")

    with col_ck2:
        chk_model = st.selectbox(
            "Model for structuring checklist",
            REVIEW_PIPELINE_MODELS,
            index=0,
            key="chk_model",
        )
        chk_max_tokens = st.number_input(
            "max_tokens",
            min_value=2000,
            max_value=120000,
            value=12000,
            step=1000,
            key="chk_max_tokens",
        )

    default_chk_prompt = st.session_state.get(
        "chk_prompt_default",
        """你是一位 FDA 510(k) 審查 checklist 設計專家。

請將以下原始 checklist（可能是文字、Markdown 或 CSV 匯出）整理為 **適合審查員逐項勾選的 Markdown 版本**：

1. 使用階層式結構（章節 → 小節 → 檢查項目）。
2. 每一項目應包含：
   - 編號（例如 1.1.1）
   - 檢查主題
   - 說明/判準（簡要說明合格條件）
   - 可選欄位（例如：結果/備註）
3. 鼓勵使用 Markdown 表格呈現重複結構的檢查項目。
4. 不憑空新增不存在於原始 checklist 的要求，但可以重新分組與整理。

輸出使用繁體中文標題與說明。
"""
    )
    chk_prompt = st.text_area(
        "Prompt for structuring checklist",
        value=default_chk_prompt,
        height=200,
        key="chk_prompt",
    )

    if st.button("Transform checklist to organized Markdown", key="chk_run_btn"):
        if not raw_chk.strip():
            st.warning("Please paste or upload checklist first.")
        else:
            st.session_state["chk_status"] = "running"
            show_status("Checklist Structuring", "running")
            api_keys = st.session_state.get("api_keys", {})
            system_prompt = "You are a 510(k) review checklist organizer. Follow the user's instructions."
            user_prompt = chk_prompt + "\n\n=== RAW CHECKLIST ===\n" + raw_chk
            with st.spinner("Structuring checklist..."):
                try:
                    out = call_llm(
                        model=chk_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=chk_max_tokens,
                        temperature=0.15,
                        api_keys=api_keys,
                    )
                    st.session_state["chk_md"] = out
                    st.session_state["chk_raw"] = raw_chk
                    st.session_state["chk_status"] = "done"
                    token_est = int(len(user_prompt + out) / 4)
                    log_event(
                        "510(k) Review Pipeline",
                        "Checklist Structurer",
                        chk_model,
                        token_est,
                    )
                except Exception as e:
                    st.session_state["chk_status"] = "error"
                    st.error(f"Error structuring checklist: {e}")

    chk_md = st.session_state.get("chk_md", "")
    st.markdown("#### Organized Checklist (editable)")
    chk_view = st.radio(
        "View mode for checklist",
        ["Markdown", "Plain text"],
        horizontal=True,
        key="chk_view_mode",
    )
    if chk_view == "Markdown":
        chk_md_edited = st.text_area(
            "Checklist (Markdown)",
            value=chk_md,
            height=260,
            key="chk_md_edited",
        )
    else:
        chk_md_edited = st.text_area(
            "Checklist (Plain text)",
            value=chk_md,
            height=260,
            key="chk_txt_edited",
        )
    st.session_state["chk_effective"] = chk_md_edited

    st.markdown("---")
    st.markdown("### Step 3 – Apply Checklist to Submission → Review Report")

    if "rep_status" not in st.session_state:
        st.session_state["rep_status"] = "pending"
    show_status("Review Report Generator", st.session_state["rep_status"])

    subm_effective = st.session_state.get("subm_effective", "")
    chk_effective = st.session_state.get("chk_effective", "")

    if not subm_effective or not chk_effective:
        st.info("需先完成 Step 1 與 Step 2（有結構化提交資料與 checklist）才能產出審查報告。")
        return

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        rep_model = st.selectbox(
            "Model for review report",
            REVIEW_PIPELINE_MODELS,
            index=1,  # 預設稍微深度一點
            key="rep_model",
        )
    with col_r2:
        rep_max_tokens = st.number_input(
            "max_tokens",
            min_value=4000,
            max_value=120000,
            value=12000,
            step=1000,
            key="rep_max_tokens",
        )

    default_rep_prompt = st.session_state.get(
        "rep_prompt_default",
        """你是一位 FDA 510(k) 主審查員。

請根據「整理後的提交資料」與「整理後的 checklist」，撰寫一份 **正式審查報告草稿**：

1. 報告應包含至少以下章節：
   - 審查範圍與文件來源
   - 裝置與申請概述
   - 主要技術特性與比較裝置摘要
   - 逐項審查結果（依 checklist 結構整理，清楚指出符合/不符合/需補件）
   - 風險與風險控制評估重點
   - 建議結論（例如：SE / NSE / 需補件）
2. 請在「逐項審查結果」部分，參考 checklist 的編號，建立清楚的 traceability。
3. 可使用 Markdown 標題與表格輔助閱讀。
4. 若資訊明顯不足，請在報告中註明「資訊不足」並避免臆測。

輸出語言：繁體中文。
"""
    )
    rep_prompt = st.text_area(
        "Prompt for building review report",
        value=default_rep_prompt,
        height=220,
        key="rep_prompt",
    )

    if st.button("Generate Review Report", key="rep_run_btn"):
        st.session_state["rep_status"] = "running"
        show_status("Review Report Generator", "running")
        api_keys = st.session_state.get("api_keys", {})
        system_prompt = "You are an FDA 510(k) reviewer drafting an internal review report."
        user_prompt = (
            rep_prompt
            + "\n\n=== ORGANIZED CHECKLIST ===\n"
            + chk_effective
            + "\n\n=== ORGANIZED SUBMISSION MATERIAL ===\n"
            + subm_effective
        )
        with st.spinner("Generating review report..."):
            try:
                out = call_llm(
                    model=rep_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=rep_max_tokens,
                    temperature=0.18,
                    api_keys=api_keys,
                )
                st.session_state["rep_md"] = out
                st.session_state["rep_status"] = "done"
                token_est = int(len(user_prompt + out) / 4)
                log_event(
                    "510(k) Review Pipeline",
                    "Review Report Builder",
                    rep_model,
                    token_est,
                )
            except Exception as e:
                st.session_state["rep_status"] = "error"
                st.error(f"Error generating review report: {e}")

    rep_md = st.session_state.get("rep_md", "")
    st.markdown("#### Review Report (editable)")
    rep_view = st.radio(
        "View mode for report",
        ["Markdown", "Plain text"],
        horizontal=True,
        key="rep_view_mode",
    )
    if rep_view == "Markdown":
        rep_md_edited = st.text_area(
            "Review Report (Markdown)",
            value=rep_md,
            height=320,
            key="rep_md_edited",
        )
    else:
        rep_md_edited = st.text_area(
            "Review Report (Plain text)",
            value=rep_md,
            height=320,
            key="rep_txt_edited",
        )
    st.session_state["rep_effective"] = rep_md_edited


# -------------------------
# Note Keeper & Magics
# -------------------------

def highlight_keywords(text: str, keywords: list[str], color: str) -> str:
    """Simple keyword highlighter using span style."""
    if not text or not keywords:
        return text
    out = text
    for kw in sorted(set([k for k in keywords if k.strip()]), key=len, reverse=True):
        safe_kw = kw.strip()
        if not safe_kw:
            continue
        span = f'<span style="color:{color};font-weight:600;">{safe_kw}</span>'
        out = out.replace(safe_kw, span)
    return out


def render_note_keeper_tab():
    st.title(t("Note Keeper & Magics"))

    st.markdown("### Step 1 – Paste Notes & Transform to Structured Markdown")
    raw_notes = st.text_area("Paste your notes (text or markdown)", height=220, key="notes_raw")

    col_n1, col_n2, col_n3 = st.columns([2, 1, 1])
    with col_n1:
        note_model = st.selectbox(
            "Model for Note → Markdown",
            ALL_MODELS,
            index=ALL_MODELS.index(st.session_state.settings["model"]),
            key="note_model",
        )
    with col_n2:
        note_max_tokens = st.number_input(
            "max_tokens",
            min_value=2000,
            max_value=120000,
            value=12000,
            step=1000,
            key="note_max_tokens",
        )
    with col_n3:
        if "note_status" not in st.session_state:
            st.session_state["note_status"] = "pending"
        show_status("Note Structuring", st.session_state["note_status"])

    default_note_prompt = st.session_state.get(
        "note_struct_prompt_default",
        """你是一位協助 FDA 510(k) 審查員整理個人筆記的助手。

請將下列雜亂或半結構化的筆記，整理成：

1. 清晰的 Markdown 結構（標題、子標題、條列）。
2. 保留所有技術與法規重點，不要憑空新增內容。
3. 顯示出：
   - 關鍵技術要點
   - 主要風險與疑問
   - 待釐清/追問事項
4. 盡可能讓後續的「關鍵字標示」「實體萃取」「總結」等功能可以直接沿用。

輸出使用 Markdown。
"""
    )
    note_struct_prompt = st.text_area(
        "Prompt for Note → Markdown",
        value=default_note_prompt,
        height=200,
        key="note_struct_prompt",
    )

    if st.button("Transform notes to structured Markdown", key="note_run_btn"):
        if not raw_notes.strip():
            st.warning("Please paste notes first.")
        else:
            st.session_state["note_status"] = "running"
            show_status("Note Structuring", "running")
            api_keys = st.session_state.get("api_keys", {})
            system_prompt = "You organize reviewer's notes into clean markdown."
            user_prompt = note_struct_prompt + "\n\n=== RAW NOTES ===\n" + raw_notes
            with st.spinner("Structuring notes..."):
                try:
                    out = call_llm(
                        model=note_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=note_max_tokens,
                        temperature=0.15,
                        api_keys=api_keys,
                    )
                    st.session_state["note_md"] = out
                    st.session_state["note_status"] = "done"
                    token_est = int(len(user_prompt + out) / 4)
                    log_event(
                        "Note Keeper",
                        "Note Structurer",
                        note_model,
                        token_est,
                    )
                except Exception as e:
                    st.session_state["note_status"] = "error"
                    st.error(f"Error structuring notes: {e}")

    st.markdown("#### Structured Note (editable)")
    note_md = st.session_state.get("note_md", raw_notes)
    note_view = st.radio(
        "View mode for base note",
        ["Markdown", "Plain text"],
        horizontal=True,
        key="note_view_mode",
    )
    if note_view == "Markdown":
        note_md_edited = st.text_area(
            "Note (Markdown)",
            value=note_md,
            height=260,
            key="note_md_edited",
        )
    else:
        note_md_edited = st.text_area(
            "Note (Plain text)",
            value=note_md,
            height=260,
            key="note_txt_edited",
        )
    st.session_state["note_effective"] = note_md_edited

    base_note = st.session_state.get("note_effective", "")

    st.markdown("---")
    st.markdown("### AI Formatting")

    fmt_model = st.selectbox(
        "Model for AI Formatting",
        ALL_MODELS,
        index=ALL_MODELS.index(st.session_state.settings["model"]),
        key="fmt_model",
    )
    fmt_max_tokens = st.number_input(
        "max_tokens (Formatting)",
        min_value=2000,
        max_value=120000,
        value=12000,
        step=1000,
        key="fmt_max_tokens",
    )
    default_fmt_prompt = st.session_state.get(
        "fmt_prompt_default",
        """請在不改變實際內容與結論的前提下，幫我將這份筆記做「版面與結構微調」：

1. 統一標題層級與命名（例如：一、二、三 或 Level 1/2/3）。
2. 將長句適度分段，使其更易閱讀。
3. 對關鍵段落可適度加粗或使用列表，但不得新增新資訊。
4. 不要刪除原始內容，只做「整齊化」處理。

輸出仍為 Markdown。
"""
    )
    fmt_prompt = st.text_area(
        "Prompt for AI Formatting",
        value=default_fmt_prompt,
        height=160,
        key="fmt_prompt",
    )

    if st.button("Run AI Formatting", key="fmt_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            system_prompt = "You are a formatting-only assistant for markdown notes."
            user_prompt = fmt_prompt + "\n\n=== NOTE ===\n" + base_note
            with st.spinner("Formatting note..."):
                try:
                    out = call_llm(
                        model=fmt_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=fmt_max_tokens,
                        temperature=0.1,
                        api_keys=api_keys,
                    )
                    st.session_state["fmt_note"] = out
                    token_est = int(len(user_prompt + out) / 4)
                    log_event("Note Keeper", "AI Formatting", fmt_model, token_est)
                except Exception as e:
                    st.error(f"Formatting failed: {e}")

    fmt_note = st.session_state.get("fmt_note", "")
    if fmt_note:
        st.markdown("#### Formatted Note (editable)")
        st.text_area(
            "Formatted Note (Markdown)",
            value=fmt_note,
            height=220,
            key="fmt_note_edited",
        )

    st.markdown("---")
    st.markdown("### AI Keywords")

    kw_input = st.text_input(
        "Keywords (comma-separated, e.g. predicate device, bench testing, risk control)",
        key="kw_input",
    )
    kw_color = st.color_picker("Color for keywords", "#ff7f50", key="kw_color")

    if st.button("Apply Keyword Highlighting (no LLM)", key="kw_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
            highlighted = highlight_keywords(base_note, keywords, kw_color)
            st.session_state["kw_note"] = highlighted

    kw_note = st.session_state.get("kw_note", "")
    if kw_note:
        st.markdown("#### Note with Highlighted Keywords (Markdown)")
        st.markdown(kw_note, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### AI Entities (20 Entities with Context Table)")

    ent_model = st.selectbox(
        "Model for AI Entities",
        ALL_MODELS,
        index=ALL_MODELS.index("gemini-2.5-flash") if "gemini-2.5-flash" in ALL_MODELS else 0,
        key="ent_model",
    )
    ent_max_tokens = st.number_input(
        "max_tokens (Entities)",
        min_value=2000,
        max_value=120000,
        value=12000,
        step=1000,
        key="ent_max_tokens",
    )
    default_ent_prompt = st.session_state.get(
        "ent_prompt_default",
        """請從以下筆記中，萃取至少 20 個與醫療器材 / FDA / 510(k) 審查相關的「關鍵實體」，例如：

- 裝置名稱 / 類別 / product code
- 測試項目 / 標準 / 指引文件
- 主要風險 / 不良事件型態
- 臨床試驗、族群、主要終點
- 關鍵法規條文或規範號碼

並以 Markdown 表格輸出，欄位至少包含：
- Entity
- Type
- Context (原文簡短片段)
- Regulatory Relevance (為何對審查有用)
"""
    )
    ent_prompt = st.text_area(
        "Prompt for AI Entities",
        value=default_ent_prompt,
        height=200,
        key="ent_prompt",
    )

    if st.button("Run AI Entities", key="ent_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            system_prompt = "You are a regulatory entity extraction assistant."
            user_prompt = ent_prompt + "\n\n=== NOTE ===\n" + base_note
            with st.spinner("Extracting entities..."):
                try:
                    out = call_llm(
                        model=ent_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=ent_max_tokens,
                        temperature=0.15,
                        api_keys=api_keys,
                    )
                    st.session_state["ent_table"] = out
                    token_est = int(len(user_prompt + out) / 4)
                    log_event("Note Keeper", "AI Entities", ent_model, token_est)
                except Exception as e:
                    st.error(f"Entity extraction failed: {e}")

    ent_table = st.session_state.get("ent_table", "")
    if ent_table:
        st.markdown("#### Entity Table (Markdown)")
        st.text_area(
            "Entity Table",
            value=ent_table,
            height=260,
            key="ent_table_edited",
        )

    st.markdown("---")
    st.markdown("### AI Chat (on this Note)")

    if "note_chat_history" not in st.session_state:
        st.session_state["note_chat_history"] = []

    chat_model = st.selectbox(
        "Model for AI Chat",
        ALL_MODELS,
        index=ALL_MODELS.index("gemini-3-flash-preview") if "gemini-3-flash-preview" in ALL_MODELS else 0,
        key="note_chat_model",
    )
    chat_max_tokens = st.number_input(
        "max_tokens (Chat)",
        min_value=2000,
        max_value=120000,
        value=4000,
        step=1000,
        key="note_chat_max_tokens",
    )

    for msg in st.session_state["note_chat_history"]:
        role = msg["role"]
        content = msg["content"]
        align = "flex-start" if role == "user" else "flex-end"
        bg = "#e0f2fe" if role == "user" else "#ecfdf5"
        border = "#38bdf8" if role == "user" else "#22c55e"
        st.markdown(
            f"""
            <div style="display:flex;justify-content:{align};margin-bottom:0.3rem;">
              <div style="max-width:100%;background:{bg};border:1px solid {border};padding:8px 10px;border-radius:10px;font-size:0.9rem;">
                <b>{'You' if role=='user' else 'Assistant'}</b><br>{content}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    chat_q = st.text_area(
        "Ask the AI about this note",
        height=100,
        key="note_chat_input",
    )

    if st.button("Send Chat Question", key="note_chat_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        elif not chat_q.strip():
            st.warning("Please type a question.")
        else:
            st.session_state["note_chat_history"].append({"role": "user", "content": chat_q})
            api_keys = st.session_state.get("api_keys", {})
            system_prompt = f"""
You are a regulatory assistant chatting about a 510(k) reviewer's note.

BASE NOTE:
\"\"\"{base_note[:12000]}\"\"\"

Answer based ONLY on this note and standard FDA 510(k) concepts.
If the note does not cover the question, explain what is missing.
"""
            convo = "\n\n".join(
                f"{m['role'].upper()}: {m['content']}"
                for m in st.session_state["note_chat_history"][-8:]
            )
            with st.spinner("Answering..."):
                try:
                    out = call_llm(
                        model=chat_model,
                        system_prompt=system_prompt,
                        user_prompt=convo,
                        max_tokens=chat_max_tokens,
                        temperature=0.2,
                        api_keys=api_keys,
                    )
                    st.session_state["note_chat_history"].append(
                        {"role": "assistant", "content": out}
                    )
                    token_est = int(len(convo + out) / 4)
                    log_event("Note Keeper", "AI Chat", chat_model, token_est)
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Chat failed: {e}")

    st.markdown("---")
    st.markdown("### AI Summary")

    sum_model = st.selectbox(
        "Model for AI Summary",
        ALL_MODELS,
        index=ALL_MODELS.index("gpt-4o-mini") if "gpt-4o-mini" in ALL_MODELS else 0,
        key="note_sum_model",
    )
    sum_max_tokens = st.number_input(
        "max_tokens (Summary)",
        min_value=2000,
        max_value=120000,
        value=12000,
        step=1000,
        key="note_sum_max_tokens",
    )
    default_sum_prompt = st.session_state.get(
        "sum_prompt_default",
        """請針對以下審查筆記撰寫摘要，方便後續做決策紀錄：

1. 給出約 3~7 個重點 bullet（偏向「給主管看的摘要」）。
2. 清楚指出：
   - 裝置與適應症的關鍵點
   - 目前最大的風險或不確定性
   - 建議的下一步行動（例如：要求補件、需要專家會議等）
3. 可加上一段約 3~5 句的總結性文字段落。

輸出使用繁體中文。
"""
    )
    sum_prompt = st.text_area(
        "Prompt for AI Summary",
        value=default_sum_prompt,
        height=200,
        key="note_sum_prompt",
    )

    if st.button("Run AI Summary", key="note_sum_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            system_prompt = "You write executive-style regulatory summaries."
            user_prompt = sum_prompt + "\n\n=== NOTE ===\n" + base_note
            with st.spinner("Summarizing note..."):
                try:
                    out = call_llm(
                        model=sum_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=sum_max_tokens,
                        temperature=0.2,
                        api_keys=api_keys,
                    )
                    st.session_state["note_summary"] = out
                    token_est = int(len(user_prompt + out) / 4)
                    log_event("Note Keeper", "AI Summary", sum_model, token_est)
                except Exception as e:
                    st.error(f"Summary failed: {e}")

    note_summary = st.session_state.get("note_summary", "")
    if note_summary:
        st.markdown("#### Note Summary (Markdown)")
        st.text_area(
            "Summary",
            value=note_summary,
            height=220,
            key="note_summary_edited",
        )

    st.markdown("---")
    st.markdown("### AI Magics – 兩個進階功能")

    magic = st.selectbox(
        "Select Magic",
        ["AI Risk & Action Register", "AI Regulatory Gap Finder"],
        key="note_magic_select",
    )

    magic_model = st.selectbox(
        "Model for Magic",
        ALL_MODELS,
        index=ALL_MODELS.index("gemini-3-pro-preview") if "gemini-3-pro-preview" in ALL_MODELS else 0,
        key="note_magic_model",
    )
    magic_max_tokens = st.number_input(
        "max_tokens (Magic)",
        min_value=2000,
        max_value=120000,
        value=12000,
        step=1000,
        key="note_magic_max_tokens",
    )

    if magic == "AI Risk & Action Register":
        magic_desc = """根據筆記內容，產出「風險與行動登錄表」，欄位如：
- Risk
- Root Cause / Trigger
- Impact
- Current Controls
- Recommended Action
- Owner / Due Date (建議性的欄位，可留白或示意)"""
    else:
        magic_desc = """根據筆記內容，找出可能的「法規/指引/標準缺口」，例如：
- 是否缺少特定性能測試
- 是否未涵蓋某些適用 FDA 指引
- 醫療電氣 / 軟體 / 可靠度等是否有明顯缺口
請以條列與表格說明。"""

    st.info(magic_desc)

    if st.button("Run Magic", key="note_magic_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            if magic == "AI Risk & Action Register":
                system_prompt = "You build a risk & action register table from review notes."
            else:
                system_prompt = "You detect regulatory gaps from review notes."

            user_prompt = f"{magic_desc}\n\n=== NOTE ===\n{base_note}"
            with st.spinner("Running magic..."):
                try:
                    out = call_llm(
                        model=magic_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=magic_max_tokens,
                        temperature=0.2,
                        api_keys=api_keys,
                    )
                    st.session_state["note_magic_output"] = out
                    token_est = int(len(user_prompt + out) / 4)
                    log_event("Note Keeper", magic, magic_model, token_est)
                except Exception as e:
                    st.error(f"Magic failed: {e}")

    magic_out = st.session_state.get("note_magic_output", "")
    if magic_out:
        st.markdown("#### Magic Output (Markdown)")
        st.text_area(
            "Magic Output",
            value=magic_out,
            height=260,
            key="note_magic_output_edited",
        )


# -------------------------
# Agents Config + SKILL.md
# -------------------------

def render_agents_config_tab():
    st.title("Agents Config Studio / 代理設定工作室")

    agents_cfg = st.session_state["agents_cfg"]
    agents_dict = agents_cfg.get("agents", {})

    st.subheader("1. Current Agents Overview")
    if not agents_dict:
        st.warning("No agents found in current agents.yaml.")
    else:
        df = pd.DataFrame([
            {
                "agent_id": aid,
                "name": acfg.get("name", ""),
                "model": acfg.get("model", ""),
                "category": acfg.get("category", ""),
            }
            for aid, acfg in agents_dict.items()
        ])
        st.dataframe(df, use_container_width=True, height=260)

    st.markdown("---")
    st.subheader("2. Edit Full agents.yaml (raw text)")

    yaml_str_current = yaml.dump(
        st.session_state["agents_cfg"],
        allow_unicode=True,
        sort_keys=False,
    )
    edited_yaml_text = st.text_area(
        "agents.yaml (editable)",
        value=yaml_str_current,
        height=320,
        key="agents_yaml_text_editor",
    )

    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        if st.button("Apply edited YAML to session", key="apply_edited_yaml"):
            try:
                cfg = yaml.safe_load(edited_yaml_text)
                if not isinstance(cfg, dict) or "agents" not in cfg:
                    st.error("Parsed YAML does not contain top-level key 'agents'. No changes applied.")
                else:
                    st.session_state["agents_cfg"] = cfg
                    st.success("Updated agents.yaml in current session.")
            except Exception as e:
                st.error(f"Failed to parse edited YAML: {e}")

    with col_a2:
        uploaded_agents_tab = st.file_uploader(
            "Upload agents.yaml file",
            type=["yaml", "yml"],
            key="agents_yaml_tab_uploader",
        )
        if uploaded_agents_tab is not None:
            try:
                cfg = yaml.safe_load(uploaded_agents_tab.read())
                if "agents" in cfg:
                    st.session_state["agents_cfg"] = cfg
                    st.success("Uploaded agents.yaml applied to this session.")
                else:
                    st.warning("Uploaded file has no top-level 'agents' key. Ignoring.")
            except Exception as e:
                st.error(f"Failed to parse uploaded YAML: {e}")

    with col_a3:
        st.download_button(
            "Download current agents.yaml",
            data=yaml_str_current.encode("utf-8"),
            file_name="agents.yaml",
            mime="text/yaml",
            key="download_agents_yaml_current",
        )

    st.markdown("---")
    st.subheader("3. SKILL.md 管理 / SKILL.md Management")

    skill_md = st.session_state.get("skill_md", "")
    skill_md_edited = st.text_area(
        "SKILL.md (editable)",
        value=skill_md,
        height=320,
        key="skill_md_editor",
    )

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("Update SKILL.md in session", key="skill_update_btn"):
            st.session_state["skill_md"] = skill_md_edited
            st.success("SKILL.md updated in session (檔案內容已更新於記憶體，可供下載或另行保存到 repo)。")
    with col_s2:
        st.download_button(
            "Download SKILL.md",
            data=skill_md_edited.encode("utf-8"),
            file_name="SKILL.md",
            mime="text/markdown",
            key="skill_download_btn",
        )

    uploaded_skill = st.file_uploader(
        "Upload SKILL.md",
        type=["md", "markdown", "txt"],
        key="skill_upload",
    )
    if uploaded_skill is not None:
        try:
            txt = uploaded_skill.read().decode("utf-8", errors="ignore")
            st.session_state["skill_md"] = txt
            st.success("Uploaded SKILL.md applied to this session.")
        except Exception as e:
            st.error(f"Failed to load uploaded SKILL.md: {e}")


# =========================
# Main
# =========================

st.set_page_config(page_title="FDA 510(k) Agentic Reviewer", layout="wide")

if "settings" not in st.session_state:
    st.session_state["settings"] = {
        "theme": "Light",
        "language": "English",
        "painter_style": "Van Gogh",
        "model": "gpt-4o-mini",
        "max_tokens": 12000,
        "temperature": 0.2,
    }
if "history" not in st.session_state:
    st.session_state["history"] = []

# Load agents.yaml
if "agents_cfg" not in st.session_state:
    try:
        with open("agents.yaml", "r", encoding="utf-8") as f:
            st.session_state["agents_cfg"] = yaml.safe_load(f)
    except Exception as e:
        st.error(f"Failed to load agents.yaml: {e}")
        st.stop()

# Load SKILL.md
if "skill_md" not in st.session_state:
    try:
        with open("SKILL.md", "r", encoding="utf-8") as f:
            st.session_state["skill_md"] = f.read()
    except Exception:
        st.session_state["skill_md"] = ""

render_sidebar()
apply_style(st.session_state.settings["theme"], st.session_state.settings["painter_style"])

tab_labels = [
    t("Dashboard"),
    t("510k_tab"),
    t("510k_summary_studio"),
    t("PDF → Markdown"),
    t("Summary & Entities"),
    t("Comparator"),
    t("Checklist & Report"),
    t("Note Keeper & Magics"),
    t("FDA Orchestration"),
    t("Dynamic Agents"),
    t("Agents Config"),
]
tabs = st.tabs(tab_labels)

with tabs[0]:
    render_dashboard()
with tabs[1]:
    render_510k_tab()
# 這裡你可以再次放回原本的 render_510k_summary_studio_tab / render_pdf_to_md_tab / render_summary_tab / render_diff_tab /
# render_fda_orchestration_tab / render_dynamic_agents_tab 等函式呼叫。
with tabs[6]:
    render_510k_review_pipeline_tab()
with tabs[7]:
    render_note_keeper_tab()
with tabs[10]:
    render_agents_config_tab()
