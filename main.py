import streamlit as st
import google.generativeai as genai
import requests
import asyncio

# [v2.5.1] IndexError 방지 및 가변 모델 개수 완벽 대응 버전
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    or_key = st.secrets.get("OR_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    valid_gemini_models = []
    
    if g_key:
        try:
            genai.configure(api_key=g_key)
            # 가용 모델 스캔
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    name = m.name.replace("models/", "")
                    # 최신 모델 위주로 필터링 (선택 사항)
                    if "flash" in name or "pro" in name:
                        valid_gemini_models.append(name)
        except: pass
    
    # 스캔 실패 시 기본값
    if not valid_gemini_models:
        valid_gemini_models = ["gemini-1.5-flash", "gemini-1.5-pro"]
            
    return g_key, or_key, gr_key, valid_gemini_models

GEMINI_KEY, OR_KEY, GROQ_KEY, VALID_GEMINI = setup_clients()

# 모델 설정 (현재 6개 계열)
MODEL_CONFIG = {
    "Gemini": VALID_GEMINI,
    "Groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    "GPT": ["openai/gpt-4o-mini", "openai/gpt-4o"],
    "Claude": ["anthropic/claude-3-haiku", "anthropic/claude-3.5-sonnet"],
    "Llama": ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.2-3b-instruct:free"],
    "DeepSeek": ["deepseek/deepseek-r1:free", "deepseek/deepseek-chat"]
}

def apply_style():
    st.markdown("""
        <style>
        .block-container { max-width: 100% !important; padding: 1rem 2% !important; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 16px; margin-bottom: 8px; min-height: 120px; max-height: 400px; 
            overflow-y: auto; font-size: 14px; border-left: 6px solid #3b82f6;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        .stButton button { background-color: #3b82f6 !important; color: white !important; font-weight: bold !important; height: 3.5rem; }
        @media (max-width: 768px) { .res-card { font-size: 15px !important; } }
        </style>
    """, unsafe_allow_html=True)

def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    try:
        if family == "Gemini":
            m_name = model_id.split('/')[-1]
            model = genai.GenerativeModel(model_name=m_name)
            return model.generate_content(prompt).text
        elif family == "Groq":
            r = requests.post(
                url="https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=15)
            return r.json()['choices'][0]['message']['content']
        else:
            r = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=30)
            return r.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ 오류: {str(e)[:50]}"

async def async_worker(index, family, model_id, prompt, placeholders):
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''
        <div class="res-card">
            <span class="model-info">{index+1}. {family} • {model_id}</span>
            {res}
        </div>
    ''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Arena", layout="wide")
    apply_style()
    
    f_names = list(MODEL_CONFIG.keys())
    num_models = len(f_names) # 모델 개수 자동 파악 (현재 6개)

    # 세션 상태 초기화 (고정된 8 대신 실제 개수 사용)
    if 'res_list' not in st.session_state or len(st.session_state.res_list) != num_models:
        st.session_state.res_list = [""] * num_models
    if 'last_in' not in st.session_state or len(st.session_state.last_in) != num_models:
        st.session_state.last_in = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert Arena</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    main_q = st.text_area("Global Input", placeholder="전체 모델에게 질문...", label_visibility="collapsed", key="g_input", height=100)
    
    # 버튼 및 실행 로직
    if st.button("🔍 모든 AI 답변 듣기", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asyncio.gather(*(async_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(num_models))))
            loop.close()
        except:
            for i in range(num_models): 
                st.session_state.res_list[i] = sync_api_call(f_names[i], selected[f_names[i]], main_q)
            st.rerun()

    st.divider()

    # 결과 카드 출력 영역
    cols = st.columns(2)
    for i in range(num_models):
        with cols[i % 2]:
            fam = f_names[i]
            st.markdown(f'''
                <div class="res-card">
                    <span class="model-info">{i+1}. {fam} • {selected[fam]}</span>
                    {st.session_state.res_list[i] if st.session_state.res_list[i] else "대기 중..."}
                </div>
            ''', unsafe_allow_html=True)
            
            ind_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 개별 질문", label_visibility="collapsed")
            if ind_q.strip() and ind_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = ind_q
                st.session_state.res_list[i] = sync_api_call(fam, selected[fam], ind_q)
                st.rerun()

if __name__ == "__main__":
    main()
