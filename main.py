import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v2.6.7] 8개 계열(Fixed 8 Families) 고정 + 계열별 무료 모델 자동 필터링
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    or_key = st.secrets.get("OR_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    
    # OpenRouter에서 현재 실시간 무료($0) 모델 리스트 가져오기
    free_or_models = []
    if or_key:
        try:
            response = requests.get("https://openrouter.ai/api/v1/models")
            if response.status_code == 200:
                all_models = response.json().get('data', [])
                free_or_models = [m['id'] for m in all_models 
                                 if float(m.get('pricing', {}).get('prompt', 1)) == 0]
        except: pass

    # 비상용 무료 모델 (API 실패 시 대비)
    if not free_or_models:
        free_or_models = ["google/gemini-flash-1.5-8b:free", "deepseek/deepseek-r1:free", "meta-llama/llama-3.3-70b-instruct:free"]
    
    return g_key, or_key, gr_key, free_or_models

GEMINI_KEY, OR_KEY, GROQ_KEY, FREE_OR_MODELS = setup_clients()

# 8개 계열 고정 및 계열별 무료 모델 매칭 로직
def get_fixed_8_family_config():
    # 계열별 키워드에 맞는 무료 모델 필터링 함수
    def filter_free(keyword):
        matches = [m for m in FREE_OR_MODELS if keyword.lower() in m.lower()]
        return matches if matches else ["google/gemini-flash-1.5-8b:free"] # 없으면 범용 무료 모델 배치

    config = {
        "Gemini": ["gemini-1.5-flash", "gemini-1.5-pro"], # 구글 자체 무료 한도 이용
        "Groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"], # Groq 기본 제공
        "GPT": filter_free("gpt") or filter_free("gemini-flash"), # GPT 무료가 없으면 제미나이 프리로 대체
        "Claude": filter_free("claude") or filter_free("haiku"),
        "Llama": filter_free("llama"),
        "Mistral": filter_free("mistral") or filter_free("pixtral"),
        "DeepSeek": filter_free("deepseek"),
        "Gemma": filter_free("gemma")
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
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .model-info { font-size: 10px; font-weight: 800; color: #1e40af; margin-bottom: 3px; display: block; }
        .stButton button { background-color: #3b82f6 !important; color: white !important; font-weight: bold !important; height: 3.5rem; border-radius: 12px !important; }
        </style>
    """, unsafe_allow_html=True)

def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    session = requests.Session()
    try:
        if family == "Gemini":
            model = genai.GenerativeModel(model_name=model_id)
            return model.generate_content(prompt).text
        elif family == "Groq":
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
        return "⚠️ 해당 모델의 무료 서버가 응답하지 않습니다. 다른 무료 모델을 시도해 보세요."

async def async_worker(index, family, model_id, prompt, placeholders):
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family} • {model_id.split("/")[-1]}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="8-Arena Expert", layout="wide")
    apply_style()
    
    current_config = get_fixed_8_family_config()
    f_names = list(current_config.keys()) # 고정된 8개 계열 이름

    if 'res_list' not in st.session_state or len(st.session_state.res_list) != 8:
        st.session_state.res_list = [""] * 8
    if 'last_in' not in st.session_state or len(st.session_state.last_in) != 8:
        st.session_state.last_in = [""] * 8

    st.markdown("<h2 style='text-align: center; margin-bottom: 20px;'>🚀 AI Expert 8-Arena (무료 계열 고정판)</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 계열별 무료 모델 선택")
        selected = {}
        for fam in f_names:
            # 계열별로 검색된 무료 모델들을 드롭다운에 배치
            selected[fam] = st.selectbox(f"{fam}", current_config[fam], key=f"sel_{fam}")

    main_q = st.text_area("Input", placeholder="8개 계열에게 동시 질문...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 모든 무료 AI 답변 듣기", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(8)]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tasks = [async_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(8)]
        loop.run_until_complete(asyncio.gather(*tasks))
        st.rerun()

    st.divider()
    cols = st.columns(2)
    for i in range(8):
        fam = f_names[i]
        with cols[i % 2]:
            st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {fam} ({selected[fam].split("/")[-1]})</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)
            ind_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 계별 질문", label_visibility="collapsed")
            if ind_q.strip() and ind_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = ind_q
                st.session_state.res_list[i] = sync_api_call(fam, selected[fam], ind_q)
                st.rerun()

if __name__ == "__main__":
    main()
