import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v2.6.2] OpenRouter 무제한 무료 모델(:free) 전용 구성 버전
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
    # Gemini는 기본적으로 일정 한도 내 무료(Flash 모델 등)
    if not valid_gemini: valid_gemini = ["gemini-1.5-flash", "gemini-1.5-pro"]
    return g_key, or_key, gr_key, valid_gemini

GEMINI_KEY, OR_KEY, GROQ_KEY, VALID_GEMINI = setup_clients()

# [중요] OpenRouter에서 '무료'로 제공되는 모델들로만 리스트업
MODEL_CONFIG = {
    "Gemini": VALID_GEMINI,
    "Groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"], # Groq은 현재 API 자체가 무료 수준
    "GPT": ["openai/gpt-4o-mini"], # OpenRouter 유료이므로 Gemini Flash 권장
    "Claude": ["anthropic/claude-3-haiku"], # 유료 모델이나 가장 저렴함 (에러 시 아래 무료 모델로 대체)
    "Llama": ["meta-llama/llama-3.3-70b-instruct:free", "meta-llama/llama-3.2-3b-instruct:free"],
    "Mistral": ["mistralai/mistral-7b-instruct:free", "mistralai/pixtral-12b:free"],
    "DeepSeek": ["deepseek/deepseek-r1:free", "deepseek/deepseek-chat:free"],
    "Gemma": ["google/gemma-2-9b-it:free", "google/learnlm-1.5-pro-experimental:free"]
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
            background: #f0fdf4; border: 2px solid #bbf7d0; border-radius: 15px;
            padding: 20px; margin-top: 20px; border-left: 10px solid #22c55e;
        }
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        .stButton button { 
            background-color: #3b82f6 !important; color: white !important; 
            font-weight: bold !important; border-radius: 10px !important;
            height: 3.5rem;
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
                # OpenRouter 무료 모델 호출
                r = session.post("https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "http://localhost:8501"},
                    json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=45)
                data = r.json()
                if 'choices' in data:
                    return data['choices'][0]['message']['content']
                else:
                    return f"⚠️ 무료 한도 초과 혹은 에러: {data.get('error', {}).get('message', '잠시 후 시도')}"
        except Exception as e:
            if attempt == 0: time.sleep(1); continue
            return f"⚠️ 연결 실패"
    return "⚠️ 응답 없음"

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
    st.set_page_config(page_title="AI Arena Free", layout="wide")
    apply_style()
    
    f_names = list(MODEL_CONFIG.items())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert Arena (무료 버전)</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.info("💡 ':free' 모델은 잔액 없이 무제한 이용 가능합니다.")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    main_q = st.text_area("Global Input", placeholder="질문을 입력하세요...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 모든 AI 답변 듣기", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asyncio.gather(*(async_worker(i, f_names[i][0], selected[f_names[i][0]], main_q, placeholders) for i in range(num_models))))
            loop.close()
        except:
            for i in range(num_models): 
                st.session_state.res_list[i] = sync_api_call(f_names[i][0], selected[f_names[i][0]], main_q)
        st.rerun()

    st.divider()

    cols = st.columns(2)
    for i in range(num_models):
        fam = f_names[i][0]
        with cols[i % 2]:
            st.markdown(f'''
                <div class="res-card">
                    <span class="model-info">{i+1}. {fam} • {selected[fam].split('/')[-1]}</span>
                    {st.session_state.res_list[i] if st.session_state.res_list[i] else "대기 중..."}
                </div>
            ''', unsafe_allow_html=True)
            ind_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 개별 질문", label_visibility="collapsed")
            if ind_q.strip() and ind_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = ind_q
                st.session_state.res_list[i] = sync_api_call(fam, selected[fam], ind_q)
                st.rerun()

    # 종합 요약 (DeepSeek 무료 모델 활용)
    st.divider()
    if st.button("📝 무료 AI 종합 요약 받기", use_container_width=True):
        all_text = ""
        for i, (fam, _) in enumerate(f_names):
            if st.session_state.res_list[i]:
                all_text += f"[{fam} 답변]: {st.session_state.res_list[i]}\n\n"
        
        if all_text:
            with st.spinner("무료 모델이 요약 중..."):
                # 요약도 무료인 DeepSeek-R1 혹은 Llama-3.3 사용
                summary = sync_api_call("DeepSeek", "deepseek/deepseek-r1:free", f"다음 답변들을 핵심 요약해줘:\n\n{all_text}")
                st.session_state.final_summary = summary
                st.rerun()

    if 'final_summary' in st.session_state:
        st.markdown(f'<div class="summary-card"><b>📌 종합 요약:</b><br><br>{st.session_state.final_summary}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
