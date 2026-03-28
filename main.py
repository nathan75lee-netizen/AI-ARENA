import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import os
import json

# [v1.2.1] 클라우드(Secrets) 전용 로더
@st.cache_resource
def setup_clients():
    try:
        # 클라우드 배포 시 Settings > Secrets에 입력한 값을 읽음
        g_key = st.secrets["GEMINI_KEY"]
        or_key = st.secrets["OR_KEY"]
        if g_key: genai.configure(api_key=g_key)
        return g_key, or_key
    except:
        # 로컬 테스트용 (메모장 경로 - 클라우드에선 작동 안함)
        return None, None

GEMINI_KEY, OR_KEY = setup_clients()

MODEL_CONFIG = {
    "Gemini": ("검색/멀티모달", ["gemini-1.5-flash", "gemini-2.0-flash"]),
    "GPT": ("범용/논리", ["openai/gpt-4o-mini", "openai/gpt-4o"]),
    "Claude": ("코딩/추론", ["anthropic/claude-3-haiku", "anthropic/claude-3.5-sonnet"]),
    "Llama": ("오픈소스/성능", ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.2-3b-instruct:free"]),
    "Mistral": ("논리/효율", ["mistralai/mistral-nemo", "mistralai/mistral-7b-instruct-v0.3"]),
    "Mixtral": ("다중작업", ["mistralai/mixtral-8x7b-instruct", "mistralai/mixtral-8x22b-instruct"]),
    "DeepSeek": ("수학/코딩", ["deepseek/deepseek-r1:free", "deepseek/deepseek-chat"]),
    "Gemma": ("한국어/섬세", ["google/gemma-2-9b-it", "google/gemma-2-27b-it"])
}

def apply_style():
    st.markdown("""
        <style>
        .block-container { max-width: 100% !important; padding: 1.5rem 1.5% !important; }
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { font-size: 11px !important; color: #007bff !important; font-weight: 800 !important; }
        [data-testid="stSidebar"] div[data-baseweb="select"] span { font-size: 11px !important; }
        .result-box { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px !important; height: 160px; overflow-y: auto; font-size: 11px !important; }
        .node-label { font-size: 10px !important; font-weight: 800; color: #2563eb; }
        </style>
    """, unsafe_allow_html=True)

async def fetch_api_worker(index, family, model_id, prompt, placeholders):
    if not GEMINI_KEY or not OR_KEY:
        placeholders[index].error("API 키 설정이 필요합니다.")
        return
    try:
        if family == "Gemini":
            def run_gemini(): return genai.GenerativeModel(model_name=model_id).generate_content(prompt).text
            res = await asyncio.to_thread(run_gemini)
        else:
            t_out = 50 if "mistral" in model_id.lower() else 30
            r = await asyncio.to_thread(requests.post,
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"},
                data=json.dumps({"model": model_id, "messages": [{"role": "user", "content": prompt}]}),
                timeout=t_out
            )
            res = r.json()['choices'][0]['message']['content'] if r.status_code == 200 else f"⚠️ {r.status_code}"
        st.session_state.res_8[index] = res
    except Exception as e:
        st.session_state.res_8[index] = f"⚠️ 오류: {str(e)[:25]}"
    placeholders[index].markdown(f'''<div class="result-box"><span class="node-label">{index+1}. {family} • {model_id.split("/")[-1]}</span><br>{st.session_state.res_8[index]}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(layout="wide", page_title="AI Arena Mobile")
    apply_style()
    if 'res_8' not in st.session_state: st.session_state.res_8 = [""] * 8
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * 8

    with st.sidebar:
        st.write("### 🛠️ TOOLBAR")
        selected = {fam: st.selectbox(f"{fam} • {cfg[0]}", cfg[1], key=f"s_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    st.markdown('<div style="font-size:1.5rem; font-weight:900; color:#1e293b;">AI Expert 8-Arena</div>', unsafe_allow_html=True)
    main_q = st.text_area("Global", placeholder="질문을 입력하고 🔍 버튼 클릭", label_visibility="collapsed", key="m_input", height=66)
    
    placeholders = []
    f_names = list(MODEL_CONFIG.keys())
    for i in range(8):
        ph = st.empty()
        placeholders.append(ph)
        ph.markdown(f'''<div class="result-box"><span class="node-label">{i+1}. {f_names[i]}</span><br>{st.session_state.res_8[i]}</div>''', unsafe_allow_html=True)

    if st.button("🔍") and main_q.strip():
        async def run_parallel():
            await asyncio.gather(*(fetch_api_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(8)))
        asyncio.run(run_parallel())

if __name__ == "__main__":
    main()