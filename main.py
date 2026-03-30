import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v2.5.4] OpenRouter 타임아웃 확장(45s) 및 레이아웃 영구 고정 버전
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    or_key = st.secrets.get("OR_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    valid_gemini = []
    if g_key:
        try:
            genai.configure(api_key=g_key)
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    valid_gemini.append(m.name.replace("models/", ""))
        except: pass
    if not valid_gemini: valid_gemini = ["gemini-1.5-flash", "gemini-1.5-pro"]
    return g_key, or_key, gr_key, valid_gemini

GEMINI_KEY, OR_KEY, GROQ_KEY, VALID_GEMINI = setup_clients()

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
        .block-container { max-width: 100% !important; padding: 1rem 2% !important; background-color: #f8fafc; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 16px; margin-bottom: 5px; min-height: 120px; max-height: 400px; 
            overflow-y: auto; font-size: 14px; border-left: 6px solid #3b82f6;
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
        }
        </style>
    """, unsafe_allow_html=True)

def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    # 세션 재사용으로 연결 안정성 향상
    session = requests.Session()
    
    for attempt in range(2): # 2회 재시도
        try:
            if family == "Gemini":
                model = genai.GenerativeModel(model_name=model_id.split('/')[-1])
                return model.generate_content(prompt).text
            
            elif family == "Groq":
                r = session.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=20)
                return r.json()['choices'][0]['message']['content']
            
            else: # OpenRouter (GPT, Claude, DeepSeek 등)
                r = session.post("https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OR_KEY}",
                        "HTTP-Referer": "http://localhost:8501",
                        "X-Title": "AI Expert Arena"
                    },
                    json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, 
                    timeout=45) # 타임아웃 45초로 연장
                
                data = r.json()
                if 'choices' in data:
                    return data['choices'][0]['message']['content']
                else:
                    return f"⚠️ API 메시지: {data.get('error', {}).get('message', '응답 지연')}"
                    
        except Exception as e:
            if attempt == 0:
                time.sleep(1.5)
                continue
            return f"⚠️ 연결 실패: {str(e)[:45]}"
    return "⚠️ 호출 실패"

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
    st.set_page_config(page_title="AI Expert Arena Pro", layout="wide")
    apply_style()
    
    f_names = list(MODEL_CONFIG.keys())
    num_models = len(f_names)

    # 데이터 저장소 초기화
    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * num_models

    st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>⚡ AI Expert Arena</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    # [1] 질문창 및 전체 버튼 (항상 유지)
    main_q = st.text_area("Global Input", placeholder="전체 모델에게 질문...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 모든 AI 답변 듣기", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        for i, ph in enumerate(placeholders):
            ph.info(f"{f_names[i]} 대답 준비 중...")
            
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

    # [2] 결과 및 개별 입력창 (항상 표시되는 영역)
    cols = st.columns(2)
    for i in range(num_models):
        with cols[i % 2]:
            fam = f_names[i]
            st.markdown(f'''
                <div class="res-card">
                    <span class="model-info">{i+1}. {fam} • {selected[fam]}</span>
                    {st.session_state.res_list[i] if st.session_state.res_list[i] else "질문을 입력하세요."}
                </div>
            ''', unsafe_allow_html=True)
            
            ind_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 개별 질문 (Enter)", label_visibility="collapsed")
            
            if ind_q.strip() and ind_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = ind_q
                with st.spinner(f"{fam} 생각 중..."):
                    st.session_state.res_list[i] = sync_api_call(fam, selected[fam], ind_q)
                st.rerun()

if __name__ == "__main__":
    main()
