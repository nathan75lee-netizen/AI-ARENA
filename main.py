import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v3.7.1] 클라이언트 설정
@st.cache_resource
def setup_clients():
    return st.secrets.get("GEMINI_KEY"), st.secrets.get("GROQ_KEY")

GEMINI_KEY, GROQ_KEY = setup_clients()

# [구성] 8개 슬롯 배치
PRIORITY_MAP = {
    "1. Gemini-2.0-F": ["gemini-2.0-flash", "llama-3.3-70b-versatile"],
    "2. Gemini-1.5-P": ["gemini-1.5-pro", "mixtral-8x7b-32768"],
    "3. Gemini-1.5-F": ["gemini-1.5-flash", "llama-3.1-8b-instant"],
    "4. Gemini-Exp": ["gemini-1.5-pro", "llama-3.3-70b-versatile"],
    "5. Groq-Llama-70B": ["llama-3.3-70b-versatile", "gemini-1.5-flash"],
    "6. Groq-Llama-8B": ["llama-3.1-8b-instant", "gemini-2.0-flash"],
    "7. Groq-Mixtral": ["mixtral-8x7b-32768", "gemini-1.5-flash"],
    "8. Groq-Expert": ["llama-3.3-70b-versatile", "gemini-1.5-pro"]
}

def apply_style():
    st.markdown("""
        <style>
        .block-container { max-width: 100% !important; padding: 1rem 2% !important; background-color: #f8fafc; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 16px; margin-bottom: 5px; min-height: 120px; max-height: 400px; 
            overflow-y: auto; font-size: 14px; border-left: 6px solid #3b82f6;
        }
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        .stButton button { background-color: #3b82f6 !important; color: white !important; font-weight: bold !important; border-radius: 10px !important; }
        .summary-box { background: #f0fdf4; border: 2px solid #bbf7d0; border-radius: 15px; padding: 20px; margin-top: 20px; border-left: 10px solid #22c55e; }
        .stTextArea textarea { font-size: 14px !important; }
        </style>
    """, unsafe_allow_html=True)

# [엔진] 호출 및 재시도 로직
def persistent_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    # 요약용 특별 우회 리스트 (Pro가 안되면 무조건 Llama나 Flash로)
    if family == "Summary-Expert":
        candidates = ["gemini-1.5-pro", "llama-3.3-70b-versatile", "gemini-1.5-flash"]
    else:
        candidates = PRIORITY_MAP.get(family, [model_id])
    
    for current_model in candidates:
        try:
            if "gemini" in current_model.lower():
                genai.configure(api_key=GEMINI_KEY)
                model = genai.GenerativeModel(model_name=current_model)
                res = model.generate_content(prompt)
                if res and res.text: return res.text
            else:
                r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": current_model, "messages": [{"role": "user", "content": prompt}]}, timeout=30)
                if r.status_code == 200: return r.json()['choices'][0]['message']['content']
        except: continue
    return "⚠️ 요약 엔진 호출 실패 (모든 API 할당량 소진)"

async def async_worker(index, family, model_id, prompt, placeholders):
    await asyncio.sleep(index * 1.5)
    res = await asyncio.to_thread(persistent_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena", layout="wide")
    apply_style()
    f_names = list(PRIORITY_MAP.keys())
    num_models = len(f_names)

    # 세션 초기화
    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models
    if 'summary_res' not in st.session_state: st.session_state.summary_res = None

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert 8-Arena (v3.7.1)</h2>", unsafe_allow_html=True)
    
    main_q = st.text_area("Global Input", placeholder="질문을 입력하세요...", key="g_input", height=100)
    
    if st.button("🔍 8개 모델 동시 분석 시작", use_container_width=True) and main_q.strip():
        st.session_state.summary_res = None # 새로운 질문 시 이전 요약 삭제
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(*(async_worker(i, f_names[i], PRIORITY_MAP[f_names[i]][0], main_q, placeholders) for i in range(num_models))))
        st.rerun()

    st.divider()
    cols = st.columns(2)
    for i in range(num_models):
        with cols[i % 2]:
            st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {f_names[i]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)

    # --- [강력 보강] 종합 취합 섹션 ---
    if any(st.session_state.res_list):
        st.write("---")
        if st.button("📝 모든 답변 교차 분석 및 종합 요약 (강제 실행)", use_container_width=True):
            with st.status("전문가 AI가 결론을 도출 중입니다...", expanded=True) as status:
                valid_ans = ""
                for i in range(num_models):
                    ans = st.session_state.res_list[i]
                    if ans and "⚠️" not in ans and ans != "...":
                        valid_ans += f"### {f_names[i]}의 답변:\n{ans}\n\n"
                
                if valid_ans:
                    summary_prompt = f"다음 8개 AI의 답변을 바탕으로 핵심 요약과 최종 결론을 한국어로 작성해줘:\n\n{valid_ans}"
                    # 요약 시도
                    result = persistent_call("Summary-Expert", "gemini-1.5-pro", summary_prompt)
                    st.session_state.summary_res = result
                    status.update(label="요약 완료!", state="complete", expanded=False)
                    st.rerun()
                else:
                    st.error("요약할 수 있는 정상적인 답변이 없습니다.")

    # 결과 출력
    if st.session_state.summary_res:
        st.markdown(f'<div class="summary-box"><h4>💡 전문가 종합 분석 리포트</h4>{st.session_state.summary_res}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
