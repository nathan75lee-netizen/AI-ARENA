import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v3.2.0] 클라이언트 설정 (OpenRouter 무료 모델 위주)
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    or_key = st.secrets.get("OR_KEY")
    return g_key, gr_key, or_key

GEMINI_KEY, GROQ_KEY, OR_KEY = setup_clients()

# [핵심] Gemini 할당량 초과 시 사용할 OpenRouter 무료 모델 라인업
PRIORITY_MAP = {
    "Llama-Free-1": ["meta-llama/llama-3.2-3b-instruct:free"],
    "Llama-Free-2": ["meta-llama/llama-3.1-8b-instruct:free"],
    "Gemma-Free": ["google/gemma-2-9b-it:free"],
    "Mistral-Free": ["mistralai/mistral-7b-instruct:free"],
    "Phi-Free": ["microsoft/phi-3-medium-128k-instruct:free"],
    "Groq-Llama": ["llama-3.3-70b-versatile"],
    "Groq-Mixtral": ["mixtral-8x7b-32768"],
    "Backup-Flash": ["gemini-1.5-flash"] # Gemini가 살아나면 작동
}

def apply_style():
    st.markdown("""
        <style>
        .block-container { max-width: 100% !important; padding: 1rem 2% !important; background-color: #f8fafc; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 16px; margin-bottom: 5px; min-height: 120px; max-height: 400px; 
            overflow-y: auto; font-size: 14px; border-left: 6px solid #3b82f6;
        }
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        .stButton button { background-color: #3b82f6 !important; color: white !important; font-weight: bold !important; border-radius: 10px !important; height: 3.5rem; }
        </style>
    """, unsafe_allow_html=True)

def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    session = requests.Session()
    
    try:
        # 1. Groq 호출 (슬롯 6, 7)
        if "Groq" in family:
            r = session.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=20)
            if r.status_code == 200: return r.json()['choices'][0]['message']['content']
        
        # 2. OpenRouter 무료 모델 호출 (슬롯 1, 2, 3, 4, 5)
        elif ":free" in model_id:
            r = session.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "https://streamlit.io"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=40)
            if r.status_code == 200: return r.json()['choices'][0]['message']['content']
            else: return f"⚠️ OpenRouter 에러: {r.status_code} (인증 확인 필요)"

        # 3. Gemini 호출 (슬롯 8)
        else:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel(model_name=model_id)
            res = model.generate_content(prompt)
            return res.text
    except Exception as e:
        return f"⚠️ 호출 실패: {str(e)}"

async def async_worker(index, family, model_id, prompt, placeholders):
    await asyncio.sleep(index * 1.5) # 호출 간격 더 늘림 (안전성 최우선)
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family} • {model_id}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena", layout="wide")
    apply_style()
    f_names = list(PRIORITY_MAP.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert 8-Arena (v3.2.0)</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in PRIORITY_MAP.items()}

    main_q = st.text_area("Global Input", placeholder="Gemini 할당량 초과 시 OpenRouter 무료 모델로 대체 분석합니다...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 모든 AI 답변 동시 시작", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(*(async_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(num_models))))
        st.rerun()

    st.divider()
    cols = st.columns(2)
    for i in range(num_models):
        fam = f_names[i]
        with cols[i % 2]:
            st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {fam} • {selected[fam]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
