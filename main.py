import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v2.6.0] 8개 계열 복구 + 클로드 종합 요약(Summarizer) 기능 통합
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
    "Claude": ["anthropic/claude-3.5-sonnet", "anthropic/claude-3-haiku"],
    "Llama": ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.2-3b-instruct:free"],
    "Mistral": ["mistralai/mistral-nemo", "mistralai/mistral-7b-instruct-v0.3"],
    "DeepSeek": ["deepseek/deepseek-r1:free", "deepseek/deepseek-chat"],
    "Gemma": ["google/gemma-2-9b-it", "google/gemma-2-27b-it"]
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
        .summary-card {
            background: #fffef0; border: 2px solid #fcd34d; border-radius: 15px;
            padding: 20px; margin-top: 20px; border-left: 10px solid #f59e0b;
        }
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        .stButton button { 
            background-color: #3b82f6 !important; color: white !important; 
            font-weight: bold !important; border-radius: 10px !important;
            height: 3.5rem; margin-top: 5px;
        }
        .summary-btn button {
            background-color: #8b5cf6 !important; /* 보라색 강조 */
            border: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    session = requests.Session()
    for attempt in range(2):
        try:
            if family == "Gemini":
                model = genai.GenerativeModel(model_name=model_id.split('/')[-1])
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
                data = r.json()
                return data['choices'][0]['message']['content'] if 'choices' in data else f"⚠️ 에러: {data.get('error', {}).get('message', '지연')}"
        except Exception as e:
            if attempt == 0: time.sleep(1.5); continue
            return f"⚠️ 실패: {str(e)[:40]}"
    return "⚠️ 호출 불가"

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
    st.set_page_config(page_title="AI Arena 8 Pro", layout="wide")
    apply_style()
    
    f_names = list(MODEL_CONFIG.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state or len(st.session_state.res_list) != num_models:
        st.session_state.res_list = [""] * num_models
    if 'last_in' not in st.session_state or len(st.session_state.last_in) != num_models:
        st.session_state.last_in = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert Arena (v2.6.0)</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    main_q = st.text_area("Global Input", placeholder="질문을 입력하면 8개 AI가 동시에 응답합니다...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 모든 AI 답변 듣기", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asyncio.gather(*(async_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(num_models))))
            loop.close()
        except:
            for i in range(num_models): st.session_state.res_list[i] = sync_api_call(f_names[i], selected[f_names[i]], main_q)
        st.rerun()

    st.divider()

    # 결과 카드 영역
    cols = st.columns(2)
    for i in range(num_models):
        with cols[i % 2]:
            fam = f_names[i]
            st.markdown(f'''
                <div class="res-card">
                    <span class="model-info">{i+1}. {fam} • {selected[fam]}</span>
                    {st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}
                </div>
            ''', unsafe_allow_html=True)
            ind_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 개별 질문", label_visibility="collapsed")
            if ind_q.strip() and ind_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = ind_q
                st.session_state.res_list[i] = sync_api_call(fam, selected[fam], ind_q)
                st.rerun()

    # --- [NEW] 클로드 종합 요약 섹션 ---
    st.divider()
    st.markdown("### ✨ 전문가 의견 종합 (Claude AI)")
    
    st.markdown('<div class="summary-btn">', unsafe_allow_html=True)
    if st.button("📝 8개 답변 취합하여 결론 도출하기", use_container_width=True):
        # 현재 생성된 답변들 모으기
        all_text = ""
        for i, name in enumerate(f_names):
            if st.session_state.res_list[i]:
                all_text += f"[{name}의 답변]:\n{st.session_state.res_list[i]}\n\n"
        
        if all_text:
            with st.spinner("클로드가 모든 답변을 읽고 최적의 결론을 작성 중입니다..."):
                final_prompt = f"다음은 동일한 질문에 대한 8개 AI 모델의 답변입니다. 내용의 정확성을 교차 검증하고, 가장 뛰어난 해결책을 종합하여 한눈에 보기 쉽게 요약해 주세요:\n\n{all_text}"
                # Claude 3.5 Sonnet으로 요약 수행
                summary = sync_api_call("Claude", "anthropic/claude-3.5-sonnet", final_prompt)
                st.session_state.final_summary = summary
        else:
            st.warning("먼저 질문을 입력하여 AI들의 답변을 생성해 주세요.")
    st.markdown('</div>', unsafe_allow_html=True)

    if 'final_summary' in st.session_state:
        st.markdown(f'''
            <div class="summary-card">
                <h4 style="margin-top:0; color:#b45309;">💡 클로드의 종합 비평 및 최종 결론</h4>
                <div style="line-height:1.6; color:#4b5563;">{st.session_state.final_summary}</div>
            </div>
        ''', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
