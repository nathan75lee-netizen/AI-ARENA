import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import json

# [v1.4.0] 개별 검색 기능 복구 및 실시간 업데이트 최적화
@st.cache_resource
def setup_clients():
    try:
        g_key = st.secrets.get("GEMINI_KEY")
        or_key = st.secrets.get("OR_KEY")
        gr_key = st.secrets.get("GROQ_KEY")
        if g_key: genai.configure(api_key=g_key)
        return g_key, or_key, gr_key
    except:
        return None, None, None

GEMINI_KEY, OR_KEY, GROQ_KEY = setup_clients()

MODEL_CONFIG = {
    "Gemini": ("검색/멀티모달", ["gemini-1.5-flash", "gemini-2.0-flash"]),
    "Groq": ("초광속 응답", ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]),
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
        .block-container { max-width: 100% !important; padding: 1rem 1% !important; }
        .result-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px !important; height: 160px; overflow-y: auto; font-size: 11px !important; margin-bottom: 5px; }
        .node-label { font-size: 10px !important; font-weight: 800; color: #2563eb; }
        .stTextArea textarea { font-size: 11px !important; padding: 5px !important; }
        div[data-testid="stVerticalBlock"] > div { spacing: 0 !important; }
        </style>
    """, unsafe_allow_html=True)

async def fetch_api(family, model_id, prompt):
    if not prompt.strip(): return ""
    try:
        if family == "Gemini":
            def run_gemini(): return genai.GenerativeModel(model_name=model_id).generate_content(prompt).text
            return await asyncio.to_thread(run_gemini)
        elif family == "Groq":
            clean_id = model_id.split("/")[-1]
            r = await asyncio.to_thread(requests.post, 
                url="https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={"model": clean_id, "messages": [{"role": "user", "content": prompt}]})
            return r.json()['choices'][0]['message']['content']
        else:
            r = await asyncio.to_thread(requests.post,
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=40)
            return r.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ 오류: {str(e)[:30]}"

def main():
    st.set_page_config(layout="wide", page_title="AI Arena Pro")
    apply_style()
    
    if 'res_8' not in st.session_state: st.session_state.res_8 = [""] * 8
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * 8

    with st.sidebar:
        st.write("### 🛠️ MODEL SETUP")
        selected = {fam: st.selectbox(f"{fam}", cfg[1], key=f"s_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    st.markdown('<div style="font-size:1.5rem; font-weight:900; color:#1e293b; margin-bottom:10px;">AI Expert 9-Arena</div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns([0.9, 0.1])
    with c1:
        main_q = st.text_area("Global Input", placeholder="전체 모델에 질문...", label_visibility="collapsed", key="m_input", height=66)
    with c2:
        st.write("") # 간격 조절
        if st.button("🔍", use_container_width=True):
            if main_q.strip():
                async def run_all():
                    tasks = [fetch_api(fam, selected[fam], main_q) for fam in MODEL_CONFIG.keys()]
                    st.session_state.res_8 = list(await asyncio.gather(*tasks))
                    st.rerun()
                asyncio.run(run_all())

    f_names = list(MODEL_CONFIG.keys())
    # 2열 배치를 위해 컬럼 나누기 (모바일은 자동으로 1열로 변환됨)
    cols = st.columns(2)
    
    for i in range(8):
        with cols[i % 2]:
            fam = f_names[i]
            # 결과 박스
            st.markdown(f'''<div class="result-box"><span class="node-label">{i+1}. {fam} • {selected[fam].split("/")[-1]}</span><br>{st.session_state.res_8[i]}</div>''', unsafe_allow_html=True)
            
            # 개별 입력창
            indiv_q = st.text_area(f"q_{i}", key=f"indiv_{i}", label_visibility="collapsed", placeholder=f"{fam} 개별 질문 (Enter)", height=35)
            
            # 개별 검색 로직
            if indiv_q.strip() and indiv_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = indiv_q
                st.session_state.res_8[i] = asyncio.run(fetch_api(fam, selected[fam], indiv_q))
                st.rerun()

if __name__ == "__main__":
    main()
