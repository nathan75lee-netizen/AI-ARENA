import streamlit as st
import requests
import os
import time
import re

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

def is_valid_korean_text(text):
    """답변이 숫자/특수문자만 있거나 한글이 없으면 무효 처리"""
    if not text: return False
    clean = text.strip()
    # 숫자, 점, 공백, %로만 구성된 경우 (429 에러나 점수만 올 때 대비)
    if re.match(r'^[0-9.\s%]+$', clean): return False
    # 한글이 포함되어 있지 않으면 무효
    if not re.search('[가-힣]', clean): return False
    return len(clean) > 30 # 최소 길이는 30자 이상

def call_ultimate_relay(role, prompt, primary_eng, pool, history=""):
    """엔진과 모델을 가리지 않고 '텍스트'가 나올 때까지 릴레이"""
    # 호출 순서: 기본 엔진 -> 다른 엔진 (실패 시 엔진 자체를 바꿈)
    engines = [primary_eng, "Q" if primary_eng == "G" else "G"]
    
    for eng in engines:
        targets = pool[eng][:3] # 엔진별 상위 3개 모델 시도
        for m_id in targets:
            try:
                # 텍스트 답변 강제 프롬프트
                instruction = f"지시: 당신은 {role}입니다. 반드시 한국어 문장으로 답변하세요. 숫자로만 대답하지 마세요."
                full_p = f"{instruction}\n\n[이전 토론 내용]\n{history}\n\n[질문]\n{prompt}"
                
                if eng == "G":
                    url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
                    r = requests.post(url, json={"contents": [{"parts": [{"text": full_p}]}]}, timeout=20)
                    ans = r.json()['candidates'][0]['content']['parts'][0]['text'] if r.status_code == 200 else None
                else:
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    r = requests.post(url, headers={"Authorization": f"Bearer {Q_KEY}"}, 
                                     json={"model": m_id, "messages": [{"role": "user", "content": full_p}]}, timeout=20)
                    ans = r.json()['choices'][0]['message']['content'] if r.status_code == 200 else None
                
                if is_valid_korean_text(ans):
                    return ans, f"{eng}({m_id})"
                else:
                    st.warning(f"⚠️ {role}({m_id}) 답변 부적절(숫자/단답). 다음 후보로 전환...")
                    time.sleep(2)
            except:
                continue
    return None, "모든 엔진의 모든 모델 호출 실패"

def scan_models():
    """가용 모델 스캔 (기본값 포함)"""
    models = {"G": ["models/gemini-1.5-flash", "models/gemini-2.0-flash"], "Q": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]}
    try:
        if G_KEY:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}", timeout=5)
            if r.status_code == 200:
                models["G"] = [m['name'] for m in r.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        if Q_KEY:
            r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=5)
            if r.status_code == 200:
                models["Q"] = [m['id'] for m in r.json().get('data', []) if "guard" not in m['id'].lower()]
    except: pass
    return models

# --- UI ---
st.set_page_config(page_title="Arena v30.0", layout="wide")
st.title("🏛️ 아레나 v30.0 (엔진 크로스 페일오버)")

if 'pool' not in st.session_state:
    st.session_state.pool = scan_models()

topic = st.text_input("토론 주제", "필리핀 내 유망 사업 및 투자 전략")

if st.button("🚀 전문가 소환 및 끝장 토론") and topic:
    pool = st.session_state.pool
    debate_history = ""
    
    # 1차 토론: 기조 연설
    st.subheader("📢 1차: 분야별 전략 제안")
    cols = st.columns(3)
    # 역할별 기본 배정 (G=Gemini, Q=Groq)
    experts = [("전략가", "G"), ("기술자", "Q"), ("리스크", "Q")]
    
    for i, (role, eng) in enumerate(experts):
        with cols[i]:
            with st.spinner(f"{role} 소환 중..."):
                time.sleep(i * 3) # API 충돌 방지
                ans, status = call_ultimate_relay(role, "해당 주제에 대해 전문적인 한국어 의견을 주십시오.", eng, pool, "")
                if ans:
                    st.success(f"**{role}**")
                    st.caption(status)
                    st.write(ans)
                    debate_history += f"[{role}]: {ans}\n"
                else:
                    st.error(f"**{role} 소환 최종 실패**")

    # 종합 리포트
    if debate_history:
        st.divider()
        st.subheader("📊 아레나 최종 종합 리포트")
        with st.spinner("리포트 작성 중..."):
            # 리포트는 실패 확률이 가장 낮은 Groq의 최상위 모델로 시도
            report, _ = call_ultimate_relay("수석 서기", "모든 토론을 요약하고 실행 로드맵을 작성하라.", "Q", pool, debate_history)
            if report:
                st.markdown(report)
