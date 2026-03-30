import streamlit as st
import requests
import os
import time

# [v21.0] 네트워크 지연(408/Timeout) 및 한도초과(429) 정밀 방어
def get_env_key(name):
    if name in st.secrets: return st.secrets[name]
    if os.path.exists("api_key.txt"):
        with open("api_key.txt", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    if k.strip().upper() == name: return v.strip()
    return None

G_KEY = get_env_key("GEMINI_KEY")
Q_KEY = get_env_key("GROQ_KEY")

def fetch_active_models():
    """아레나 방식: 실시간으로 살아있는 모델 3개 이상 확보"""
    models = {"G": [], "Q": []}
    if G_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                models["G"] = [m['name'] for m in r.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        except: pass
    if Q_KEY:
        try:
            url = "https://api.groq.com/openai/v1/models"
            r = requests.get(url, headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=10)
            if r.status_code == 200:
                models["Q"] = [m['id'] for m in r.json().get('data', [])]
        except: pass
    return models

def call_safe_api(engine, m_id, prompt, role):
    """타임아웃 연장 및 에러 핸들링 강화"""
    headers = {"Content-Type": "application/json"}
    # Timeout 에러 방지를 위해 30초로 연장
    T_OUT = 30 
    
    try:
        if engine == "G":
            url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
            payload = {"contents": [{"parts": [{"text": f"당신은 {role}입니다. 주제: {prompt}"}]}]}
            r = requests.post(url, json=payload, timeout=T_OUT)
        else:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {Q_KEY}"
            payload = {"model": m_id, "messages": [{"role": "user", "content": f"당신은 {role}입니다. {prompt}"}]}
            r = requests.post(url, json=payload, headers=headers, timeout=T_OUT)

        if r.status_code == 200:
            if engine == "G": return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
            return r.json()['choices'][0]['message']['content'], "Success"
        return None, f"Status {r.status_code}"
    except requests.exceptions.Timeout:
        return None, "지연 시간 초과 (서버 응답 없음)"
    except Exception as e:
        return None, str(e)

# --- UI ---
st.set_page_config(page_title="Arena v21.0", layout="wide")
st.title("🏛️ 아레나 v21.0 (안정성 최적화)")

with st.sidebar:
    if st.button("🔍 모델 리스트 새로고침", type="primary"):
        res = fetch_active_models()
        st.session_state.g_list = res["G"]
        st.session_state.q_list = res["Q"]
        st.success("스캔 완료")

topic = st.text_input("토론 주제 입력")

if st.button("🚀 전문가 소환") and topic:
    g_pool = st.session_state.get('g_list', [])
    q_pool = st.session_state.get('q_list', [])
    
    if not g_pool or not q_pool:
        st.error("사이드바의 [모델 리스트 새로고침]을 먼저 눌러주세요!")
        st.stop()

    # 상위 모델 3개 선정
    m1 = g_pool[0]
    m2 = q_pool[0]
    m3 = q_pool[1] if len(q_pool) > 1 else g_pool[1]

    experts = [(m1, "G", "전략가"), (m2, "Q", "기술자"), (m3, "Q" if m3 in q_pool else "G", "리스크")]
    cols = st.columns(3)
    
    for i, (mid, eng, role) in enumerate(experts):
        with cols[i]:
            with st.spinner(f"{role} 호출 중..."):
                # 429 에러 방지를 위해 호출 전 3초 대기 (강제 지연)
                if i > 0: time.sleep(3) 
                ans, err = call_safe_api(eng, mid, topic, role)
                if ans:
                    st.success(f"**{role}**\n({mid})")
                    st.write(ans)
                else:
                    st.error(f"**{role} 실패**\n\n{err}")
