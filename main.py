import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import json

# [v2.3.2] 전체 실행(상단) + 개별 실행(카드별) 완벽 통합 버전
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    or_key = st.secrets.get("OR_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    if g_key:
        try: genai.configure(api_key=g_key)
        except: pass
    return g_key, or_key, gr_key

GEMINI_KEY, OR_KEY, GROQ_KEY = setup_clients()

MODEL_CONFIG = {
    "Gemini": ["gemini-1.5-flash", "gemini-2.0-flash"],
    "Groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    "GPT": ["openai/gpt-4o-mini", "openai/gpt-4o"],
    "Claude": ["anthropic/claude-3-haiku", "anthropic/claude-3.5-sonnet"],
    "Llama": ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.2-3b-instruct:free"],
    "Mistral": ["mistralai/mistral-nemo", "mistralai/mistral-7b-instruct-v0.3"],
    "DeepSeek": ["deepseek/deepseek-r1:free", "deepseek/deepseek-chat"],
    "Gemma": ["google/gemma-2-9b-it", "google/gemma-2-27b-it"]
}

def apply_responsive_style():
    st.markdown("""
        <style>
        .block-container { max-width: 100% !important; padding: 1rem 2% !important; background-color: #f8fafc; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 16px; margin-bottom: 5px; min-height: 120px; max-height: 350px; 
            overflow-y: auto; font-size: 13px; border-left: 6px solid #3b82f6;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        .stButton button {
            background-color: #3b82f6 !important; color: white !important;
            font-weight: bold !important; border-radius: 10px !important;
            height: 3.5rem; margin-top: 5px;
        }
        @media (max-width: 768px) {
            .res-card { font-size: 15px !important; min-height: 100px; max-height: none; }
            .stButton button { height: 4rem !important; font-size: 18px !important; }
            .stTextInput input { font-size: 14px !important; height: 3rem !important; }
        }
        </style>
    """, unsafe_allow_html=True)

async def fetch_api(family, model_id, prompt):
    """단일 호출용 (개별 질문용)"""
    try:
        if family == "Gemini":
            model = genai.GenerativeModel(model_name=model_id)
            res = await asyncio.to_thread(model.generate_content, prompt)
            return res.text
        elif family == "Groq":
            r = await asyncio.to_thread(requests.post, 
                url="https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                json={"model": model_id.split("/")[-1], "messages": [{"role": "user", "content": prompt}]})
            return r.json()['choices'][0]['message']['content']
        else:
            r = await asyncio.to_thread(requests.post,
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=40)
            return r.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ 오류: {str(e)[:30]}"

async def fetch_api_worker(index, family, model_id, prompt, placeholders):
    """병렬 호출용 (전체 질문용)"""
    res = await fetch_api(family, model_id, prompt)
    st.session_state.res_8[index] = res
    placeholders[index].markdown(f'''
        <div class="res-card">
            <span class="model-info">{index+1}. {family} • {model_id.split("/")[-1]}</span>
            {res}
        </div>
    ''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Arena Pro", layout="wide")
    apply_responsive_style()
    
    if 'res_8' not in st.session_state: st.session_state.res_8 = [""] * 8
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * 8

    st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>⚡ AI Expert Arena</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    # 1. 상단 질문창 & 전체 실행 버튼
    main_q = st.text_area("Global Input", placeholder="모든 AI 모델에게 질문...", label_visibility="collapsed", key="g_input", height=100)
    
    f_names = list(MODEL_CONFIG.keys())
    
    if st.button("🔍 모든 AI 답변 듣기", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = []
        for i in range(8):
            with cols[i % 2]:
                ph = st.empty()
                placeholders.append(ph)
        asyncio.run(asyncio.gather(*(fetch_api_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(8))))
    
    # 2. 결과 카드 및 개별 질문창 영역
    st.divider()
    cols = st.columns(2)
    for i in range(8):
        with cols[i % 2]:
            fam = f_names[i]
            # 결과 카드 표시
            st.markdown(f'''
                <div class="res-card">
                    <span class="model-info">{i+1}. {fam} • {selected[fam].split("/")[-1]}</span>
                    {st.session_state.res_8[i] if st.session_state.res_8[i] else "대기 중..."}
                </div>
            ''', unsafe_allow_html=True)
            
            # [추가] 개별 질문 입력창
            indiv_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 전용 개별 질문 (Enter)", label_visibility="collapsed")
            
            # 개별 질문 로직
            if indiv_q.strip() and indiv_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = indiv_q
                with st.spinner(f"{fam} 답변 중..."):
                    st.session_state.res_8[i] = asyncio.run(fetch_api(fam, selected[fam], indiv_q))
                st.rerun()

if __name__ == "__main__":
    main()
