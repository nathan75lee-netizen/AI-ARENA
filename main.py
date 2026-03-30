import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import json

# [v2.3.1] 버튼 위치 상단 이동 및 모바일 UI 강화
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
        
        /* 카드 디자인 */
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 16px; margin-bottom: 10px; min-height: 120px; max-height: 300px; 
            overflow-y: auto; font-size: 13px; border-left: 6px solid #3b82f6;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        
        /* 버튼 강조 */
        .stButton button {
            background-color: #3b82f6 !important;
            color: white !important;
            font-weight: bold !important;
            border-radius: 10px !important;
            height: 3rem;
            margin-top: 5px;
        }

        @media (max-width: 768px) {
            .res-card { font-size: 15px !important; min-height: 100px; max-height: none; }
            .stButton button { height: 4rem !important; font-size: 18px !important; }
        }
        </style>
    """, unsafe_allow_html=True)

async def fetch_api_worker(index, family, model_id, prompt, placeholders):
    try:
        if family == "Gemini":
            if not GEMINI_KEY: res = "⚠️ Gemini Key 확인 필요"
            else:
                model = genai.GenerativeModel(model_name=model_id)
                response = await asyncio.to_thread(model.generate_content, prompt)
                res = response.text
        elif family == "Groq":
            if not GROQ_KEY: res = "⚠️ Groq Key 확인 필요"
            else:
                r = await asyncio.to_thread(requests.post, 
                    url="https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": model_id.split("/")[-1], "messages": [{"role": "user", "content": prompt}]})
                res = r.json()['choices'][0]['message']['content']
        else:
            if not OR_KEY: res = "⚠️ OpenRouter Key 확인 필요"
            else:
                r = await asyncio.to_thread(requests.post,
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OR_KEY}"},
                    json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=40)
                res = r.json()['choices'][0]['message']['content']
        st.session_state.res_8[index] = res
    except Exception as e:
        st.session_state.res_8[index] = f"⚠️ 오류: {str(e)[:30]}"
    
    placeholders[index].markdown(f'''
        <div class="res-card">
            <span class="model-info">{index+1}. {family} • {model_id.split("/")[-1]}</span>
            {st.session_state.res_8[index]}
        </div>
    ''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Arena Fast", layout="wide")
    apply_responsive_style()
    
    if 'res_8' not in st.session_state: st.session_state.res_8 = [""] * 8

    # 1. 헤더 및 입력창 (최상단)
    st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>⚡ AI Expert Arena</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    # 질문창
    main_q = st.text_area("Global Input", placeholder="전체 모델에게 질문...", label_visibility="collapsed", key="g_input", height=100)
    
    # 2. 실행 버튼 (질문창 바로 아래로 이동)
    btn_label = "🔍 모든 AI 답변 듣기"
    if st.button(btn_label, use_container_width=True) and main_q.strip():
        # 실행 시 결과 위치를 확보하기 위해 placeholders 정의
        f_names = list(MODEL_CONFIG.keys())
        async def run_parallel():
            await asyncio.gather(*(fetch_api_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(8)))
        
        # 버튼 아래에 결과 박스들을 미리 배치
        cols = st.columns(2)
        placeholders = []
        for i in range(8):
            with cols[i % 2]:
                ph = st.empty()
                placeholders.append(ph)
        
        asyncio.run(run_parallel())
    
    # 3. 결과 영역 (버튼이 눌리지 않았을 때도 기본 틀 유지)
    else:
        st.divider()
        f_names = list(MODEL_CONFIG.keys())
        cols = st.columns(2)
        for i in range(8):
            with cols[i % 2]:
                st.markdown(f'''
                    <div class="res-card">
                        <span class="model-info">{i+1}. {f_names[i]} • {selected[f_names[i]].split("/")[-1]}</span>
                        {st.session_state.res_8[i] if st.session_state.res_8[i] else "대기 중..."}
                    </div>
                ''', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
