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

def scan_available_models():
    """서버에 직접 물어봐서 현재 내 키로 쓸 수 있는 모델 리스트 확보"""
    models = {"G": [], "Q": []}
    
    # 1. Gemini 모델 스캔 (v1beta 기준)
    if G_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                # generateContent가 가능한 모델만 추출 (vision 제외 권장)
                data = r.json().get('models', [])
                models["G"] = [m['name'] for m in data if 'generateContent' in m.get('supportedGenerationMethods', []) and "vision" not in m['name']]
        except: pass

    # 2. Groq 모델 스캔
    if Q_KEY:
        try:
            url = "https://api.groq.com/openai/v1/models"
            headers = {"Authorization": f"Bearer {Q_KEY}"}
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                # 활성화된 모델 ID만 추출
                models["Q"] = [m['id'] for m in r.json().get('data', []) if m.get('active', True)]
        except: pass
        
    return models

def call_dynamic_api(engine, m_id, prompt, role):
    """유동적으로 선택된 모델 ID로 호출"""
    headers = {"Content-Type": "application/json"}
    try:
        if engine == "G":
            # Gemini는 스캔된 모델 경로(models/...)를 그대로 사용
            url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
            payload = {"contents": [{"parts": [{"text": f"당신은 {role}입니다. 질문: {prompt}"}]}]}
            r = requests.post(url, json=payload, timeout=30)
        else:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {Q_KEY}"
            payload = {
                "model": m_id,
                "messages": [{"role": "user", "content": f"지시: {role}로서 답변하라.\n질문: {prompt}"}],
                "temperature": 0.5
            }
            r = requests.post(url, json=payload, headers=headers, timeout=30)

        if r.status_code == 200:
            if engine == "G": return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
            return r.json()['choices'][0]['message']['content'], "Success"
        return None, f"Status {r.status_code}: {r.text[:50]}"
    except Exception as e:
        return None, str(e)

# --- UI ---
st.set_page_config(page_title="Arena v24.0", layout="wide")
st.title("🏛️ 아레나 v24.0 (실시간 유동 모델 시스템)")

# 세션 상태에 모델 리스트 저장
if 'scanned_models' not in st.session_state:
    st.session_state.scanned_models = {"G": [], "Q": []}

with st.sidebar:
    st.header("⚙️ 시스템 엔진")
    if st.button("🔍 가용 모델 실시간 스캔", type="primary"):
        with st.spinner("서버에서 모델 리스트를 가져오는 중..."):
            st.session_state.scanned_models = scan_available_models()
            st.success(f"스캔 완료! (G:{len(st.session_state.scanned_models['G'])}개, Q:{len(st.session_state.scanned_models['Q'])}개)")
    
    if st.session_state.scanned_models["G"] or st.session_state.scanned_models["Q"]:
        st.write("**현재 사용 가능한 모델 예시:**")
        st.caption(f"G: {st.session_state.scanned_models['G'][:2]}")
        st.caption(f"Q: {st.session_state.scanned_models['Q'][:2]}")

topic = st.text_input("토론 주제 입력")

if st.button("🚀 아레나 가동 (유동 배정)") and topic:
    m_list = st.session_state.scanned_models
    if not m_list["G"] and not m_list["Q"]:
        st.error("사이드바에서 먼저 [모델 실시간 스캔]을 눌러주세요.")
        st.stop()

    # 🔴 모델 유동 배정 로직 (순서대로 3개 추출)
    # 전략가: Gemini 첫번째 / 기술자: Groq 첫번째 / 리스크: Groq 두번째(없으면 Gemini 두번째)
    pool_g = m_list["G"]
    pool_q = m_list["Q"]

    # 안전하게 모델 3개 확보
    try:
        m1 = (pool_g[0], "G", "전략가")
        m2 = (pool_q[0] if pool_q else pool_g[1], "Q" if pool_q else "G", "기술자")
        m3 = (pool_q[1] if len(pool_q) > 1 else (pool_g[-1]), "Q" if len(pool_q) > 1 else "G", "리스크")
    except IndexError:
        st.error("사용 가능한 모델이 부족합니다. API 키 권한을 확인하세요.")
        st.stop()

    experts = [m1, m2, m3]
    cols = st.columns(3)
    logs = []

    for i, (mid, eng, role) in enumerate(experts):
        with cols[i]:
            with st.spinner(f"{role} 호출 중..."):
                # 429 방지를 위해 호출 전 5초 대기
                if i > 0: time.sleep(5)
                ans, status = call_dynamic_api(eng, mid, topic, role)
                if ans:
                    st.success(f"**{role}** 입정")
                    st.caption(f"모델: {mid}")
                    st.write(ans)
                    logs.append(ans)
                else:
                    st.error(f"**{role} 호출 실패**")
                    st.code(status)

    if logs:
        st.divider()
        st.subheader("📝 종합 결론")
        # 요약은 가장 성능 좋은 Groq 모델로 진행
        final_mid = pool_q[0] if pool_q else pool_g[0]
        final_eng = "Q" if pool_q else "G"
        final_ans, _ = call_dynamic_api(final_eng, final_mid, f"다음 내용을 요약하라: {' '.join(logs)}", "서기")
        st.write(final_ans if final_ans else "리포트 작성 실패")
