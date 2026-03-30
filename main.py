import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v2.7.1] v2.5.5 기반 + 네트워크 예외 처리 강화 + 답변 취합 기능
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

# v2.5.5 고정 계열 (사용자 지정 라인업)
MODEL_CONFIG = {
    "Gemini": VALID_GEMINI,
    "Groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    "GPT": ["openai/gpt-4o-mini", "openai/gpt-4o"],
    "Claude": ["anthropic/claude-3-haiku", "anthropic/claude-3.5-sonnet"],
    "Llama": ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.2-3b-instruct:free"],
    "Mistral": ["mistralai/mistral-nemo", "mistralai/pixtral-12b"],
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
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        .stButton button { 
            background-color: #3b82f6 !important; color: white !important; 
            font-weight: bold !important; border-radius: 10px !important;
            height: 3.5rem;
        }
        .summary-box {
            background: #f0fdf4; border: 2px solid #bbf7d0; border-radius: 15px;
            padding: 20px; margin-top: 20px; border-left: 10px solid #22c55e;
        }
        </style>
    """, unsafe_allow_html=True)

def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    session = requests.Session()
    # 네트워크 오류 시 최대 2회 재시도
    for attempt in range(2):
        try:
            if family == "Gemini":
                model = genai.GenerativeModel(model_name=model_id.split('/')[-1])
                return model.generate_content(prompt).text
            elif family == "Groq":
                r = session.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=15)
                return r.json()['choices'][0]['message']['content']
            else:
                r = session.post("https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "http://localhost:8501"},
                    json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=25)
                data = r.json()
                if 'choices' in data:
                    return data['choices'][0]['message']['content']
                return f"⚠️ API 메시지: {data.get('error', {}).get('message', '응답 없음')}"
        except requests.exceptions.RequestException:
            if attempt == 0:
                time.sleep(2) # 2초 대기 후 재시도
                continue
            return "⚠️ 네트워크 연결 오류 (OpenRouter 접속 불가). 인터넷 상태를 확인하세요."
        except Exception as e:
            return f"⚠️ 기타 오류: {str(e)[:50]}"

async def async_worker(index, family, model_id, prompt, placeholders):
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''
        <div class="res-card">
            <span class="model-info">{index+1}. {family} • {model_id.split('/')[-1]}</span>
            {res}
        </div>
    ''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena", layout="wide")
    apply_style()
    
    f_names = list(MODEL_CONFIG.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert 8-Arena</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    main_q = st.text_area("Global Input", placeholder="질문을 입력하세요...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 모든 AI 답변 듣기", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(*(async_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(num_models))))
        st.rerun()

    st.divider()

    # 8개 답변 카드
    cols = st.columns(2)
    for i in range(num_models):
        with cols[i % 2]:
            fam = f_names[i]
            st.markdown(f'''
                <div class="res-card">
                    <span class="model-info">{i+1}. {fam} • {selected[fam].split("/")[-1]}</span>
                    {st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}
                </div>
            ''', unsafe_allow_html=True)
            ind_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 개별 질문", label_visibility="collapsed")
            if ind_q.strip() and ind_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = ind_q
                st.session_state.res_list[i] = sync_api_call(fam, selected[fam], ind_q)
                st.rerun()

    # --- 취합 요약 섹션 ---
    st.divider()
    if st.button("📝 모든 답변 취합하여 결론 도출", use_container_width=True):
        all_text = ""
        for i, name in enumerate(f_names):
            if st.session_state.res_list[i]:
                all_text += f"[{name}의 답변]:\n{st.session_state.res_list[i]}\n\n"
        
        if all_text:
            with st.spinner("전문가 의견 종합 중..."):
                summary_prompt = f"다음은 8개 AI의 답변입니다. 핵심을 대조하여 최종 결론을 요약해 주세요:\n\n{all_text}"
                # Claude 계열 모델로 요약
                summary = sync_api_call("Claude", selected["Claude"], summary_prompt)
                st.session_state.summary_res = summary
        else:
            st.warning("먼저 답변을 생성해 주세요.")

    if 'summary_res' in st.session_state:
        st.markdown(f'''<div class="summary-box"><h4>💡 종합 분석 결과</h4>{st.session_state.summary_res}</div>''', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
