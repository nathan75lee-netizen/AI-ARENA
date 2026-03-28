import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import json

# [v1.3.0] Groq 추가 및 실시간 개별 렌더링 버전
@st.cache_resource
def setup_clients():
    try:
        g_key = st.secrets["GEMINI_KEY"]
        or_key = st.secrets["OR_KEY"]
        gr_key = st.secrets["GROQ_KEY"] # Groq 키 추가
        if g_key: genai.configure(api_key=g_key)
        return g_key, or_key, gr_key
    except:
        return None, None, None

GEMINI_KEY, OR_KEY, GROQ_KEY = setup_clients()

# Groq 모델 정보 추가
MODEL_CONFIG = {
    "Gemini": ("검색/멀티모달", ["gemini-1.5-flash", "gemini-2.0-flash"]),
    "Groq": ("초광속 응답", ["groq/llama-3.3-70b-versatile", "groq/mixtral-8x7b-32768"]),
    "GPT": ("범용/논리", ["openai/gpt-4o-mini", "openai/gpt-4o"]),
    "Claude": ("코딩/추론", ["anthropic/claude-3-haiku", "anthropic/claude-3.5-sonnet"]),
    "Llama": ("오픈소스/성능", ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.2-3b-instruct:free"]),
    "Mistral": ("논리/효율", ["mistralai/mistral-nemo", "mistralai/mistral-7b-instruct-v0.3"]),
    "DeepSeek": ("수학/코딩", ["deepseek/deepseek-r1:free", "deepseek/deepseek-chat"]),
    "Gemma": ("한국어/섬세", ["google/gemma-2-9b-it", "google/gemma-2-27b-it"])
}

def apply_style():
    st.markdown("""
        <style>
        .block-container { max-width: 100% !important; padding: 1.5rem 1.5% !important; }
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { font-size: 11px !important; color: #007bff !important; font-weight: 800 !important; }
        .result-box { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px !important; height: 160px; overflow-y: auto; font-size: 11px !important; }
        .node-label { font-size: 10px !important; font-weight: 800; color: #2563eb; }
        </style>
    """, unsafe_allow_html=True)

async def fetch_api_worker(index, family, model_id, prompt, placeholders):
    try:
        if family == "Gemini":
            def run_gemini(): return genai.GenerativeModel(model_name=model_id).generate_content(prompt).text
            res = await asyncio.to_thread(run_gemini)
        elif family == "Groq":
            # Groq 직접 호출 (OpenRouter보다 훨씬 빠름)
            clean_id = model_id.split("/")[-1]
            r = await asyncio.to_thread(requests.post,
                url="https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={"model": clean_id, "messages": [{"role": "user", "content": prompt}]}
            )
            res = r.json()['choices'][0]['message']['content']
        else:
            r = await asyncio.to_thread(requests.post,
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]},
                timeout=40
            )
            res = r.json()['choices'][0]['message']['content']
        st.session_state.res_8[index] = res
    except Exception as e:
        st.session_state.res_8[index] = f"⚠️ 오류 발생 (키 확인 필요)"
    
    placeholders[index].markdown(f'''<div class="result-box"><span class="node-label">{index+1}. {family} • {model_id.split("/")[-1]}</span><br>{st.session_state.res_8[index]}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(layout="wide", page_title="AI Arena Mobile")
    apply_style()
    if 'res_8' not in st.session_state: st.session_state.res_8 = [""] * 8

    with st.sidebar:
        st.write("### 🛠️ TOOLBAR (11px)")
        selected = {fam: st.selectbox(f"{fam}", cfg[1], key=f"s_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    st.markdown('<div style="font-size:1.5rem; font-weight:900; color:#1e293b;">AI Expert 9-Arena</div>', unsafe_allow_html=True)
    main_q = st.text_area("Global Input", placeholder="질문 입력...", label_visibility="collapsed", key="m_input", height=66)
    
    placeholders = [st.empty() for _ in range(8)]
    f_names = list(MODEL_CONFIG.keys())
    
    for i in range(8):
        placeholders[i].markdown(f'''<div class="result-box"><span class="node-label">{i+1}. {f_names[i]}</span><br>{st.session_state.res_8[i]}</div>''', unsafe_allow_html=True)

    if st.button("🔍 Run All Models") and main_q.strip():
        async def run_parallel():
            await asyncio.gather(*(fetch_api_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(8)))
        asyncio.run(run_parallel())

if __name__ == "__main__":
    main()
