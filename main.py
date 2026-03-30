import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import json

# [v2.3.0] 실시간 개별 렌더링 통합 버전 (응답 오는 순서대로 출력)
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
        .block-container { max-width: 100% !important; padding: 1.5rem 2% !important; background-color: #f8fafc; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 16px; margin-bottom: 10px; min-height: 120px; max-height: 250px; 
            overflow-y: auto; font-size: 13px; border-left: 6px solid #3b82f6;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        @media (max-width: 768px) {
            .res-card { font-size: 15px !important; min-height: 100px; max-height: none; }
            .stButton button { height: 3.5rem !important; }
        }
        </style>
    """, unsafe_allow_html=True)

async def fetch_api_worker(index, family, model_id, prompt, placeholders):
    """개별 모델의 답변을 가져와서 즉시 해당 위치에 렌더링"""
    try:
        if family == "Gemini":
            if not GEMINI_KEY: res = "⚠️ Gemini Key 미설정"
            else:
                model = genai.GenerativeModel(model_name=model_id)
                response = await asyncio.to_thread(model.generate_content, prompt)
                res = response.text
        elif family == "Groq":
            if not GROQ_KEY: res = "⚠️ Groq Key 미설정"
            else:
                r = await asyncio.to_thread(requests.post, 
                    url="https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": model_id.split("/")[-1], "messages": [{"role": "user", "content": prompt}]})
                res = r.json()['choices'][0]['message']['content']
        else:
            if not OR_KEY: res = "⚠️ OpenRouter Key 미설정"
            else:
                r = await asyncio.to_thread(requests.post,
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OR_KEY}"},
                    json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=40)
                res = r.json()['choices'][0]['message']['content']
        
        st.session_state.res_8[index] = res
    except Exception as e:
        st.session_state.res_8[index] = f"⚠️ 오류: {str(e)[:30]}"
    
    # 해당 모델의 칸(placeholder)만 즉시 업데이트
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
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * 8

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert Fast-Arena</h2>", unsafe_allow_html=True)

    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}

    main_q = st.text_area("Global Input", placeholder="전체 모델에게 질문...", label_visibility="collapsed", key="g_input", height=90)
    
    # 8개의 결과창 위치(Placeholder)를 미리 생성
    f_names = list(MODEL_CONFIG.keys())
    placeholders = []
    cols = st.columns(2)
    for i in range(8):
        with cols[i % 2]:
            ph = st.empty() # 답변이 들어갈 빈 칸 확보
            placeholders.append(ph)
            # 초기 상태 출력
            ph.markdown(f'''
                <div class="res-card">
                    <span class="model-info">{i+1}. {f_names[i]} • {selected[f_names[i]].split("/")[-1]}</span>
                    {st.session_state.res_8[i] if st.session_state.res_8[i] else "대기 중..."}
                </div>
            ''', unsafe_allow_html=True)

    if st.button("🔍 즉시 실행 (전체)", use_container_width=True) and main_q.strip():
        async def run_parallel():
            # 8개 작업을 동시에 던지고, 먼저 끝나는 순서대로 fetch_api_worker가 화면을 그림
            await asyncio.gather(*(fetch_api_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(8)))
        asyncio.run(run_parallel())

    # 개별 질문 처리 (하단에 따로 배치하거나 각 카드 아래 배치 가능)
    # 공간 효율을 위해 개별 질문은 모바일에서 필요할 때만 사용하도록 구성
    st.caption("※ 개별 모델 업데이트는 상단 Global Input 이용 후 결과창을 확인하세요.")

if __name__ == "__main__":
    main()
