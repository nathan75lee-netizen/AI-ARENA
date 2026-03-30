import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v2.6.5] OpenRouter 실시간 무료 모델(:free) 자동 추출 패치
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    or_key = st.secrets.get("OR_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    
    # 1. Gemini 기본 모델 설정
    valid_gemini = ["gemini-1.5-flash", "gemini-1.5-pro"]
    if g_key:
        try:
            genai.configure(api_key=g_key)
            models = [m.name.replace("models/", "") for m in genai.list_models() 
                      if 'generateContent' in m.supported_generation_methods]
            if models: valid_gemini = models
        except: pass

    # 2. OpenRouter 실시간 무료 모델 자동 검색
    free_models = []
    if or_key:
        try:
            # OpenRouter 전체 모델 정보 가져오기
            response = requests.get("https://openrouter.ai/api/v1/models")
            if response.status_code == 200:
                all_models = response.json().get('data', [])
                # 가격이 0인 모델만 필터링
                free_models = [m['id'] for m in all_models 
                               if float(m.get('pricing', {}).get('prompt', 1)) == 0]
        except: pass
    
    # 만약 API 호출 실패 시 비상용 리스트
    if not free_models:
        free_models = ["google/gemini-flash-1.5-8b:free", "deepseek/deepseek-r1:free", 
                       "meta-llama/llama-3.3-70b-instruct:free", "mistralai/pixtral-12b:free"]
        
    return g_key, or_key, gr_key, valid_gemini, free_models

GEMINI_KEY, OR_KEY, GROQ_KEY, VALID_GEMINI, FREE_OR_MODELS = setup_clients()

# 화면에 보여줄 8개 그룹 구성 (자동으로 무료 모델 분배)
def get_dynamic_config():
    # 무료 모델들을 적절히 8개 영역에 나눠 담기
    # 부족하면 같은 모델을 넣거나 Gemini/Groq 활용
    config = {
        "Gemini (Google)": VALID_GEMINI,
        "Groq (Fast)": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
        "Free Group 1": [m for m in FREE_OR_MODELS if "llama" in m.lower()] or FREE_OR_MODELS[:3],
        "Free Group 2": [m for m in FREE_OR_MODELS if "deepseek" in m.lower()] or FREE_OR_MODELS[3:6],
        "Free Group 3": [m for m in FREE_OR_MODELS if "mistral" in m.lower() or "pixtral" in m.lower()] or FREE_OR_MODELS[6:9],
        "Free Group 4": [m for m in FREE_OR_MODELS if "gemma" in m.lower() or "google" in m.lower() and "free" in m.lower()] or FREE_OR_MODELS[9:12],
        "Free Group 5": FREE_OR_MODELS[12:15] if len(FREE_OR_MODELS) > 15 else FREE_OR_MODELS[:3],
        "Free Group 6": FREE_OR_MODELS[15:18] if len(FREE_OR_MODELS) > 18 else FREE_OR_MODELS[3:6]
    }
    return config

def apply_style():
    st.markdown("""
        <style>
        .block-container { max-width: 100% !important; padding: 1rem 2% !important; background-color: #f8fafc; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 16px; margin-bottom: 5px; min-height: 120px; max-height: 400px; 
            overflow-y: auto; font-size: 13px; border-left: 5px solid #3b82f6;
        }
        .model-info { font-size: 10px; font-weight: 800; color: #1e40af; margin-bottom: 3px; display: block; }
        .stButton button { background-color: #3b82f6 !important; color: white !important; font-weight: bold !important; height: 3.5rem; border-radius: 12px !important; }
        </style>
    """, unsafe_allow_html=True)

def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    session = requests.Session()
    try:
        if family == "Gemini (Google)":
            model = genai.GenerativeModel(model_name=model_id.split('/')[-1])
            return model.generate_content(prompt).text
        elif family == "Groq (Fast)":
            r = session.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=20)
            return r.json()['choices'][0]['message']['content']
        else:
            r = session.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "http://localhost:8501"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=45)
            return r.json()['choices'][0]['message']['content']
    except:
        return "⚠️ 현재 서버 응답이 없습니다. 다른 무료 모델을 선택해 보세요."

async def async_worker(index, family, model_id, prompt, placeholders):
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="Free AI Arena Auto", layout="wide")
    apply_style()
    
    current_config = get_dynamic_config()
    f_names = list(current_config.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * num_models

    st.markdown("<h2 style='text-align: center; margin-bottom: 20px;'>🚀 실시간 무료 AI 아레나</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.success(f"✅ 현재 {len(FREE_OR_MODELS)}개의 무료 모델 감지됨")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in current_config.items() if cfg}

    main_q = st.text_area("Input", placeholder="질문을 입력하세요...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 모든 무료 AI 답변 듣기", use_container_width=True) and main_q.strip():
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
        if fam in selected:
            with cols[i % 2]:
                st.markdown(f'<div class="res-card"><span class="model-info">{i+1}. {fam} ({selected[fam].split("/")[-1]})</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>', unsafe_allow_html=True)
                ind_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 개별 질문", label_visibility="collapsed")
                if ind_q.strip() and ind_q != st.session_state.last_in[i]:
                    st.session_state.last_in[i] = ind_q
                    st.session_state.res_list[i] = sync_api_call(fam, selected[fam], ind_q)
                    st.rerun()

if __name__ == "__main__":
    main()
