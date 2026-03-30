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
    """서버에서 현재 권한이 있는 모델 리스트를 실시간으로 가져옴"""
    models = {"G": [], "Q": []}
    if G_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                models["G"] = [m['name'] for m in r.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', []) and "vision" not in m['name']]
        except: pass
    if Q_KEY:
        try:
            url = "https://api.groq.com/openai/v1/models"
            r = requests.get(url, headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=10)
            if r.status_code == 200:
                models["Q"] = [m['id'] for m in r.json().get('data', [])]
        except: pass
    return models

def call_with_retry(engine, m_id, prompt, role, max_retries=3):
    """429 에러 발생 시 자동으로 대기 후 재시도하는 핵심 로직"""
    headers = {"Content-Type": "application/json"}
    for i in range(max_retries):
        try:
            if engine == "G":
                # 스캔된 전체 경로(models/...)를 그대로 사용
                url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
                payload = {"contents": [{"parts": [{"text": f"당신은 {role}입니다. 질문: {prompt}"}]}]}
                r = requests.post(url, json=payload, timeout=30)
            else:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers["Authorization"] = f"Bearer {Q_KEY}"
                payload = {
                    "model": m_id,
                    "messages": [{"role": "user", "content": f"지시: {role}로서 답변하라.\n질문: {prompt}"}]
                }
                r = requests.post(url, json=payload, headers=headers, timeout=30)

            if r.status_code == 200:
                if engine == "G": return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
                return r.json()['choices'][0]['message']['content'], "Success"
            
            # 429(Rate Limit) 발생 시 지수 백오프 대기
            if r.status_code == 429:
                wait_time = (i + 1) * 10 # 10초, 20초, 30초 점진적 대기
                st.warning(f"⚠️ {role}({engine}) 한도 초과(429). {wait_time}초 후 재시도합니다... ({i+1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            return None, f"Status {r.status_code}: {r.text[:50]}"
        except Exception as e:
            time.sleep(2)
            if i == max_retries - 1: return None, str(e)
    return None, "재시도 횟수 초과"

# --- UI ---
st.set_page_config(page_title="Arena v24.5", layout="wide")
st.title("🏛️ 아레나 v24.5 (자동 모델 스캔 & 재시도)")

if 'models' not in st.session_state:
    st.session_state.models = {"G": [], "Q": []}

with st.sidebar:
    if st.button("🔍 가용 모델 실시간 스캔", type="primary"):
        st.session_state.models = scan_available_models()
        st.success("스캔 완료!")
    
    st.write(f"Gemini: {len(st.session_state.models['G'])}개 | Groq: {len(st.session_state.models['Q'])}개")

topic = st.text_input("토론 주제 입력")

if st.button("🚀 아레나 가동") and topic:
    m = st.session_state.models
    if not m["G"] and not m["Q"]:
        st.error("사이드바에서 [모델 스캔]을 먼저 실행하세요.")
        st.stop()

    # 유동적 모델 배정 (가장 앞순위 모델들 선택)
    experts = []
    if m["G"]: experts.append((m["G"][0], "G", "전략가"))
    if m["Q"]: experts.append((m["Q"][0], "Q", "기술자"))
    if len(m["Q"]) > 1: experts.append((m["Q"][1], "Q", "리스크"))
    elif len(m["G"]) > 1: experts.append((m["G"][1], "G", "리스크"))

    cols = st.columns(len(experts))
    logs = []

    for i, (mid, eng, role) in enumerate(experts):
        with cols[i]:
            with st.spinner(f"{role} 호출 중..."):
                time.sleep(2) # 기본 간격
                ans, status = call_with_retry(eng, mid, topic, role)
                if ans:
                    st.success(f"**{role}** 입정\n({mid})")
                    st.write(ans)
                    logs.append(ans)
                else:
                    st.error(f"**{role} 최종 실패**")
                    st.code(status)

    if logs:
        st.divider()
        st.subheader("📝 종합 결론")
        # 요약은 첫 번째 전문가가 수행
        final_mid, final_eng, _ = experts[0]
        final_ans, _ = call_with_retry(final_eng, final_mid, f"다음 요약: {' '.join(logs)}", "서기")
        st.write(final_ans if final_ans else "리포트 작성 실패")
