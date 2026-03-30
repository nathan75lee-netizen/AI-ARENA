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

def is_valid_text(text):
    """답변이 숫자로만 되어있거나 너무 짧으면 무효로 판정"""
    if not text: return False
    clean_text = text.strip()
    # 숫자로만 이루어져 있거나, 특수문자/숫자 조합인 경우 (예: 0.00823)
    if re.match(r'^[0-9.\s%]+$', clean_text): return False
    # 한글이 한 글자도 없으면 무효 (한국어 서비스 기준)
    if not re.search('[가-힣]', clean_text): return False
    return len(clean_text) > 20 # 최소 20자 이상은 되어야 함

def scan_real_llms():
    """진짜 답변을 할 줄 아는 모델만 선별"""
    models = {"G": [], "Q": []}
    try:
        if G_KEY:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}", timeout=5)
            if r.status_code == 200:
                models["G"] = [m['name'] for m in r.json().get('models', []) 
                             if ("flash" in m['name'].lower() or "pro" in m['name'].lower()) and "vision" not in m['name']]
        if Q_KEY:
            r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=5)
            if r.status_code == 200:
                models["Q"] = [m['id'] for m in r.json().get('data', []) 
                             if not any(x in m['id'].lower() for x in ['guard', 'speculative', 'whisper', 'preview'])
                             and ("llama" in m['id'].lower() or "mixtral" in m['id'].lower())]
    except: pass
    return models

def call_with_validation(eng, m_list, prompt, role, history=""):
    """답변이 무효할 경우 리스트 내의 다음 모델로 즉시 릴레이"""
    headers = {"Content-Type": "application/json"}
    
    # 릴레이할 모델 후보 (최대 3개)
    candidates = m_list[:3] if m_list else []
    
    for m_id in candidates:
        try:
            # 한국어 응답을 강력히 요구하는 프롬프트 엔지니어링
            instruction = f"지시: 당신은 {role}입니다. 반드시 한국어로 문장형 답변을 하세요. 숫자로만 대답하지 마세요."
            full_p = f"{instruction}\n\n[이전 맥락]\n{history}\n\n[질문]\n{prompt}"
            
            if eng == "G":
                url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
                payload = {"contents": [{"parts": [{"text": full_p}]}]}
                r = requests.post(url, json=payload, timeout=25)
                ans = r.json()['candidates'][0]['content']['parts'][0]['text'] if r.status_code == 200 else None
            else:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers["Authorization"] = f"Bearer {Q_KEY}"
                r = requests.post(url, headers=headers, json={"model": m_id, "messages": [{"role": "user", "content": full_p}]}, timeout=25)
                ans = r.json()['choices'][0]['message']['content'] if r.status_code == 200 else None
            
            # 검역 실시: 유효한 텍스트인가?
            if is_valid_text(ans):
                return ans, f"Success ({m_id})"
            else:
                st.warning(f"⚠️ {role}({m_id})의 답변이 부적절하여(숫자/단답) 다음 모델로 교체합니다.")
                time.sleep(2)
                continue
        except:
            continue
            
    # 정 안되면 엔진 스위칭 (G 실패 시 Q로, Q 실패 시 G로)
    return None, "모든 모델이 무효한 답변을 생성했습니다."

# --- UI ---
st.set_page_config(page_title="Arena v29.0", layout="wide")
st.title("🏛️ 아레나 v29.0 (무효 답변 검역 시스템)")

if 'pool' not in st.session_state:
    st.session_state.pool = scan_real_llms()

topic = st.text_input("토론 주제", "필리핀 내 유망한 사업 아이템과 진출 전략")

if st.button("🚀 전문가 긴급 소환") and topic:
    p = st.session_state.pool
    # 백업용 수동 할당 (스캔 실패 대비)
    if not p["G"]: p["G"] = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]
    if not p["Q"]: p["Q"] = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]

    experts = [("전략가", "G", p["G"]), ("기술자", "Q", p["Q"]), ("리스크", "Q", p["Q"])]
    cols = st.columns(3)
    history = ""

    for i, (role, eng, m_list) in enumerate(experts):
        with cols[i]:
            with st.spinner(f"{role} 답변 검역 중..."):
                time.sleep(i * 2) # API 충돌 방지
                ans, status = call_with_validation(eng, m_list, "해당 주제에 대해 3줄 이상의 한국어 문장으로 전문적인 의견을 주십시오.", role, "")
                if ans:
                    st.success(f"**{role}**")
                    st.caption(status)
                    st.write(ans)
                    history += f"[{role}]: {ans}\n"
                else:
                    st.error(f"**{role} 소환 실패**")

    if history:
        st.divider()
        st.subheader("📊 아레나 최종 요약 리포트")
        # 리포트는 무조건 성공률 높은 Groq Llama 70B로 시도
        report, _ = call_with_validation("Q", p["Q"], "위 토론을 요약하여 필리핀 진출을 위한 최종 로드맵을 작성하라.", "수석 서기", history)
        st.markdown(report if report else "리포트 작성 실패")
