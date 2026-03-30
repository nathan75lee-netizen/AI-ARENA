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

def scan_and_filter_models():
    """단순 스캔이 아니라, 실제 대화가 가능한 '품질 좋은' 모델만 선별"""
    models = {"G": [], "Q": []}
    
    # 1. Gemini 스캔 (Flash 1.5 이상 권장)
    if G_KEY:
        try:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}", timeout=10)
            if r.status_code == 200:
                raw = r.json().get('models', [])
                # 'flash'나 'pro'가 들어간 모델 위주로 선별
                models["G"] = [m['name'] for m in raw if ('flash' in m['name'].lower() or 'pro' in m['name'].lower()) and "vision" not in m['name']]
        except: pass

    # 2. Groq 스캔 (Prompt-guard 같은 필터 모델 제외)
    if Q_KEY:
        try:
            r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=10)
            if r.status_code == 200:
                raw = r.json().get('data', [])
                # 보안용(guard), 소형(8b 미만) 모델 제외하고 고성능(llama-3, mixtral) 위주로 필터링
                models["Q"] = [m['id'] for m in raw if "guard" not in m['id'].lower() and ("llama-3" in m['id'].lower() or "mixtral" in m['id'].lower() or "70b" in m['id'].lower())]
        except: pass
    return models

def call_elite_relay(engine, m_list, prompt, role):
    """엄선된 모델 리스트를 순회하며 400/429 방어 호출"""
    headers = {"Content-Type": "application/json"}
    if not m_list: return None, "No High-Quality Models Found"

    for m_id in m_list[:3]: # 최상위 3개 고성능 모델만 시도
        try:
            if engine == "G":
                url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
                payload = {"contents": [{"parts": [{"text": f"당신은 {role} 전문가입니다. 다음 질문에 상세히 답하세요: {prompt}"}]}]}
            else:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers["Authorization"] = f"Bearer {Q_KEY}"
                # 400 방지: 가장 표준적인 채팅 구조 사용
                payload = {
                    "model": m_id,
                    "messages": [{"role": "user", "content": f"지시: 당신은 {role}입니다. 질문: {prompt}"}],
                    "temperature": 0.5
                }
            
            r = requests.post(url, json=payload, headers=headers, timeout=25)
            
            if r.status_code == 200:
                if engine == "G": return r.json()['candidates'][0]['content']['parts'][0]['text'], f"Success ({m_id})"
                return r.json()['choices'][0]['message']['content'], f"Success ({m_id})"
            
            # 실패 시 로그 출력 후 다음 모델로
            st.warning(f"⚠️ {role}({m_id}) 실패: {r.status_code}. 다음 모델 시도 중...")
            time.sleep(2)
            continue
        except:
            continue
    return None, "모든 고성능 모델 호출 실패"

# --- UI ---
st.set_page_config(page_title="Arena v25.5", layout="wide")
st.title("🏛️ 아레나 v25.5 (고성능 모델 정밀 필터링)")

if 'elite_pool' not in st.session_state:
    st.session_state.elite_pool = {"G": [], "Q": []}

with st.sidebar:
    if st.button("🔍 고성능 모델 스캔", type="primary"):
        st.session_state.elite_pool = scan_and_filter_models()
        st.success(f"엄선 완료! G:{len(st.session_state.elite_pool['G'])} / Q:{len(st.session_state.elite_pool['Q'])}")

topic = st.text_input("토론 주제 입력")

if st.button("🚀 아레나 가동") and topic:
    p = st.session_state.elite_pool
    if not p["G"] and not p["Q"]:
        st.error("사이드바에서 먼저 [모델 스캔]을 실행하세요.")
        st.stop()

    # 역할 배정 로직 (품질 순)
    experts = [
        ("G", p["G"], "전략가"), # Gemini 최우선
        ("Q", p["Q"], "기술자"), # Groq 고성능(70B 등) 최우선
        ("Q", p["Q"][1:] if len(p["Q"]) > 1 else p["G"][1:], "리스크")
    ]

    cols = st.columns(3)
    logs = []

    for i, (eng, m_list, role) in enumerate(experts):
        with cols[i]:
            with st.spinner(f"{role} 엄선 모델 소환 중..."):
                time.sleep(3) # 429 방어용 간격
                ans, status = call_elite_relay(eng, m_list, topic, role)
                if ans:
                    st.success(f"**{role}** 입정")
                    st.caption(status)
                    st.write(ans)
                    logs.append(ans)
                else:
                    st.error(f"**{role} 최종 실패**")
                    st.code(status)
