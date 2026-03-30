import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import json

# [v2.2.0] 통합 풀버전: 반응형 UI + 3종 API 엔진 + 개별/전체 검색 + 오류 진단
@st.cache_resource
def setup_clients():
    """API 키 로드 및 클라이언트 설정"""
    g_key = st.secrets.get("GEMINI_KEY")
    or_key = st.secrets.get("OR_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    
    # 키 누락 시 경고 표시 (디버깅용)
    missing = []
    if not g_key: missing.append("GEMINI_KEY")
    if not or_key: missing.append("OR_KEY")
    if not gr_key: missing.append("GROQ_KEY")
    
    if missing:
        st.sidebar.warning(f"⚠️ 미설정 키: {', '.join(missing)}")
    
    if g_key:
        try:
            genai.configure(api_key=g_key)
        except Exception as e:
            st.sidebar.error(f"Gemini 설정 실패: {e}")
            
    return g_key, or_key, gr_key

GEMINI_KEY, OR_KEY, GROQ_KEY = setup_clients()

# 모델 구성 (사용자 선호도 기준 최적화)
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

def apply_custom_style():
    """PC와 모바일을 동시에 잡는 반응형 CSS"""
    st.markdown("""
        <style>
        /* 기본 레이아웃 */
        .block-container { max-width: 100% !important; padding: 1.5rem 2% !important; background-color: #f8fafc; }
        
        /* 결과 카드 디자인 */
        .res-card {
            background: white; 
            border: 1px solid #e2e8f0; 
            border-radius: 12px; 
            padding: 16px; 
            margin-bottom: 12px; 
            height: 200px; 
            overflow-y: auto;
            font-size: 13px; 
            line-height: 1.6;
            border-left: 6px solid #3b82f6;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        
        /* 모델 라벨 */
        .model-info {
            font-size: 11px;
            font-weight: 800;
            color: #1e40af;
            text-transform: uppercase;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }

        /* 모바일 최적화 (Media Query) */
        @media (max-width: 768px) {
            .block-container { padding: 1rem 3% !important; }
            .res-card { 
                height: auto; 
                min-height: 150px; 
                font-size: 15px !important; 
                margin-bottom: 10px;
            }
            .stButton button { height: 3.5rem !important; border-radius: 12px; font-size: 16px !important; }
        }
        
        /* 공통 위젯 스타일 */
        .stTextArea textarea { border-radius: 10px !important; }
        .stTextInput input { border-radius: 8px !important; }
        </style>
    """, unsafe_allow_html=True)

async def fetch_api(family, model_id, prompt):
    """엔진별 API 호출 로직"""
    if not prompt.strip(): return "질문을 입력해주세요."
    
    try:
        if family == "Gemini":
            if not GEMINI_KEY: return "⚠️ Gemini 키 미설정"
            model = genai.GenerativeModel(model_name=model_id)
            res = await asyncio.to_thread(model.generate_content, prompt)
            return res.text
            
        elif family == "Groq":
            if not GROQ_KEY: return "⚠️ Groq 키 미설정"
            r = await asyncio.to_thread(requests.post, 
                url="https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={"model": model_id.split("/")[-1], "messages": [{"role": "user", "content": prompt}]},
                timeout=20)
            return r.json()['choices'][0]['message']['content']
            
        else:
            if not OR_KEY: return "⚠️ OpenRouter 키 미설정"
            r = await asyncio.to_thread(requests.post,
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]},
                timeout=45)
            return r.json()['choices'][0]['message']['content']
            
    except Exception as e:
        return f"⚠️ 연결 오류: {str(e)[:40]}..."

def main():
    st.set_page_config(page_title="AI Expert Arena", layout="wide", initial_sidebar_state="collapsed")
    apply_custom_style()
    
    # 세션 상태 초기화
    if 'res_8' not in st.session_state: st.session_state.res_8 = [""] * 8
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * 8

    # 헤더 섹션
    st.markdown("<h1 style='text-align: center; color: #0f172a;'>🚀 AI Expert 9-Arena</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; font-size: 14px;'>PC와 모바일에서 최적화된 8종 모델 동시 비교</p>", unsafe_allow_html=True)

    # 사이드바 설정 (모델 선택)
    with st.sidebar:
        st.header("⚙️ Model Selector")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}
        if st.button("초기화"): 
            st.session_state.res_8 = [""] * 8
            st.rerun()

    # 메인 입력창 (Global)
    main_q = st.text_area("Global Question", placeholder="모든 AI 모델에게 한 번에 질문하세요...", label_visibility="collapsed", key="g_input", height=110)
    
    if st.button("🔍 모든 모델 실행 (Run All)", use_container_width=True):
        if main_q.strip():
            async def run_all():
                tasks = [fetch_api(fam, selected[fam], main_q) for fam in MODEL_CONFIG.keys()]
                st.session_state.res_8 = list(await asyncio.gather(*tasks))
                st.rerun()
            with st.spinner("모든 모델이 답변을 생성 중입니다..."):
                asyncio.run(run_all())

    st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)

    # 결과 그리드 (반응형: PC 2열 / 모바일 1열)
    f_names = list(MODEL_CONFIG.keys())
    cols = st.columns(2)
    
    for i in range(8):
        with cols[i % 2]:
            fam = f_names[i]
            # 카드 인터페이스
            st.markdown(f'''
                <div class="res-card">
                    <div class="model-info">
                        <span>{i+1}. {fam}</span>
                        <span>{selected[fam].split("/")[-1]}</span>
                    </div>
                    {st.session_state.res_8[i] if st.session_state.res_8[i] else "<span style='color:#cbd5e1'>답변이 여기에 표시됩니다.</span>"}
                </div>
            ''', unsafe_allow_html=True)
            
            # 개별 질문 입력 (Enter 시 작동)
            indiv_q = st.text_input(f"Individual Query {i}", key=f"ind_{i}", placeholder=f"{fam} 전용 추가 질문...", label_visibility="collapsed")
            
            if indiv_q.strip() and indiv_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = indiv_q
                with st.spinner(f"{fam} 답변 중..."):
                    st.session_state.res_8[i] = asyncio.run(fetch_api(fam, selected[fam], indiv_q))
                st.rerun()

if __name__ == "__main__":
    main()
