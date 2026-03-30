import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import json

# [v2.1.0] PC/모바일 자동 감지 및 반응형 레이아웃 통합
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
        /* 1. 기본 설정 (PC 기준) */
        .block-container { max-width: 100% !important; padding: 2rem 2% !important; }
        .res-box { 
            background: white; border: 1px solid #e2e8f0; border-radius: 10px; 
            padding: 15px; margin-bottom: 10px; height: 180px; overflow-y: auto;
            font-size: 13px; border-left: 5px solid #3b82f6;
        }
        .node-label { font-size: 11px; font-weight: 800; color: #2563eb; display: block; margin-bottom: 5px; }

        /* 2. 모바일 자동 감지 (화면 너비 768px 이하일 때 실행) */
        @media (max-width: 768px) {
            .block-container { padding: 1rem 3% !important; }
            .res-box { 
                height: auto; min-height: 120px; font-size: 15px !important; 
                padding: 12px; margin-bottom: 8px;
            }
            .node-label { font-size: 12px; }
            h1, h2 { font-size: 1.5rem !important; }
            .stButton button { height: 3.5rem !important; font-size: 16px !important; }
            
            /* 모바일에서 사이드바 위젯 폰트 조절 */
            [data-testid="stSidebar"] .stSelectbox label p { font-size: 13px !important; }
        }
        </style>
    """, unsafe_allow_html=True)

async def fetch_api(family, model_id, prompt):
    if not prompt.strip(): return ""
    try:
        if family == "Gemini":
            def run_gemini(): return genai.GenerativeModel(model_name=model_id).generate_content(prompt).text
            return await asyncio.to_thread(run_gemini)
        elif family == "Groq":
            r = await asyncio.to_thread(requests.post, 
                url="https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={"model": model_id.split("/")[-1], "messages": [{"role": "user", "content": prompt}]})
            return r.json()['choices'][0]['message']['content']
        else:
            r = await asyncio.to_thread(requests.post,
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=40)
            return r.json()['choices'][0]['message']['content']
    except: return "⚠️ 호출 실패 (Key/Quota 확인)"

def main():
    # PC는 넓게, 모바일은 중앙 집중형으로 자동 처리됨
    st.set_page_config(page_title="AI Expert Arena", layout="wide")
    apply_responsive_style()
    
    if 'res_8' not in st.session_state: st.session_state.res_8 = [""] * 8
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * 8

    # 헤더
    st.markdown("<h2 style='color: #1e293b;'>🚀 AI Expert 9-Arena</h2>", unsafe_allow_html=True)

    # 사이드바 설정 (PC에선 고정, 모바일에선 접힘)
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"s_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    # 메인 입력창
    main_q = st.text_area("Global Input", placeholder="전체 모델에게 질문 던지기...", label_visibility="collapsed", key="m_input", height=100)
    
    if st.button("🔍 Run All Models"):
        if main_q.strip():
            async def run_all():
                tasks = [fetch_api(fam, selected[fam], main_q) for fam in MODEL_CONFIG.keys()]
                st.session_state.res_8 = list(await asyncio.gather(*tasks))
                st.rerun()
            asyncio.run(run_all())

    st.divider()

    # 결과 그리드 (반응형: PC는 2열, 모바일은 1열 자동 전환)
    f_names = list(MODEL_CONFIG.keys())
    cols = st.columns(2) # 기본 2열
    
    for i in range(8):
        with cols[i % 2]: # PC에선 좌우로 나뉘고, 모바일에선 자동으로 한 줄씩 쌓임
            fam = f_names[i]
            st.markdown(f'''
                <div class="res-box">
                    <span class="node-label">{i+1}. {fam} • {selected[fam].split("/")[-1]}</span>
                    {st.session_state.res_8[i] if st.session_state.res_8[i] else "입력을 기다리는 중..."}
                </div>
            ''', unsafe_allow_html=True)
            
            # 개별 질문 창 (모바일 가독성을 위해 텍스트 인풋 사용)
            indiv_q = st.text_input(f"q_{i}", key=f"indiv_{i}", placeholder=f"{fam} 개별 질문 (Enter)", label_visibility="collapsed")
            
            if indiv_q.strip() and indiv_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = indiv_q
                st.session_state.res_8[i] = asyncio.run(fetch_api(fam, selected[fam], indiv_q))
                st.rerun()

if __name__ == "__main__":
    main()
