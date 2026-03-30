import streamlit as st
import requests
import os
import time

def get_key(name):
    if name in st.secrets: return st.secrets[name]
    if os.path.exists("api_key.txt"):
        try:
            with open("api_key.txt", "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        if k.strip().upper() == name: return v.strip()
        except: pass
    return None

G_KEY = get_key("GEMINI_KEY")
Q_KEY = get_key("GROQ_KEY")

def scan_models():
    models = {"G": [], "Q": []}
    if G_KEY:
        try:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}", timeout=10)
            if r.status_code == 200:
                models["G"] = [m['name'] for m in r.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', []) and "vision" not in m['name']]
        except: pass
    if Q_KEY:
        try:
            r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=10)
            if r.status_code == 200:
                models["Q"] = [m['id'] for m in r.json().get('data', [])]
        except: pass
    return models

def call_with_relay(engine, m_list, prompt, role):
    """지정된 엔진의 모델 리스트를 순회하며 성공할 때까지 릴레이 호출"""
    headers = {"Content-Type": "application/json"}
    
    # 모델 리스트가 비어있으면 종료
    if not m_list: return None, "No models available"

    for idx, m_id in enumerate(m_list[:5]): # 상위 5개 모델만 릴레이 시도
        try:
            if engine == "G":
                url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
                payload = {"contents": [{"parts": [{"text": f"당신은 {role}입니다. 질문: {prompt}"}]}]}
                r = requests.post(url, json=payload, timeout=25)
            else:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers["Authorization"] = f"Bearer {Q_KEY}"
                payload = {"model": m_id, "messages": [{"role": "user", "content": f"지시: {role}로서 답변하라. 질문: {prompt}"}]}
                r = requests.post(url, json=payload, headers=headers, timeout=25)

            if r.status_code == 200:
                if engine == "G": return r.json()['candidates'][0]['content']['parts'][0]['text'], f"Success ({m_id})"
                return r.json()['choices'][0]['message']['content'], f"Success ({m_id})"
            
            # 429 에러 발생 시 다음 모델로 즉시 바통 터치
            if r.status_code == 429:
                st.warning(f"⚠️ {role}({m_id}) 할당량 초과. 다음 가용 모델로 릴레이합니다...")
                time.sleep(3)
                continue
            
            return None, f"Status {r.status_code}"
        except:
            continue
            
    return None, "모든 릴레이 모델 호출 실패"

# --- UI ---
st.set_page_config(page_title="Arena v25.0", layout="wide")
st.title("🏛️ 아레나 v25.0 (모델 릴레이 시스템)")

if 'pool' not in st.session_state:
    st.session_state.pool = {"G": [], "Q": []}

with st.sidebar:
    if st.button("🔍 가용 모델 실시간 스캔", type="primary"):
        st.session_state.pool = scan_models()
        st.success(f"G:{len(st.session_state.pool['G'])} / Q:{len(st.session_state.pool['Q'])} 스캔됨")

topic = st.text_input("토론 주제 입력")

if st.button("🚀 아레나 가동") and topic:
    p = st.session_state.pool
    if not p["G"] and not p["Q"]:
        st.error("먼저 스캔 버튼을 눌러주세요.")
        st.stop()

    # 역할별 릴레이 그룹 설정
    # 전략가: Gemini 그룹 / 기술자: Groq 그룹 / 리스크: Groq 또는 Gemini 남은 그룹
    experts = [
        ("G", p["G"], "전략가"),
        ("Q", p["Q"], "기술자"),
        ("Q", p["Q"][1:] if len(p["Q"]) > 1 else p["G"][1:], "리스크")
    ]

    cols = st.columns(3)
    logs = []

    for i, (eng, m_list, role) in enumerate(experts):
        with cols[i]:
            with st.spinner(f"{role} 소환 중..."):
                time.sleep(2)
                ans, status = call_with_relay(eng, m_list, topic, role)
                if ans:
                    st.success(f"**{role}** 입정")
                    st.caption(status)
                    st.write(ans)
                    logs.append(ans)
                else:
                    st.error(f"**{role} 최종 실패**")
                    st.code(status)

    if logs:
        st.divider()
        st.subheader("📝 최종 리포트")
        # 요약은 가장 안정적인 첫번째 전문가 엔진 사용
        f_ans, _ = call_with_relay(experts[0][0], experts[0][1], f"요약하라: {' '.join(logs)}", "서기")
        st.markdown(f_ans if f_ans else "리포트 생성 실패")
