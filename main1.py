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

def call_gemini_v23(m_id, prompt, role):
    """404 에러 방지: 경로 및 모델명 3중 테스트"""
    # 2026년 최신 모델명 리스트
    test_models = ["gemini-1.5-flash", "gemini-pro", "gemini-1.0-pro"]
    
    for model in test_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={G_KEY}"
        try:
            payload = {"contents": [{"parts": [{"text": f"Role: {role}\n\n{prompt}"}]}]}
            r = requests.post(url, json=payload, timeout=20)
            if r.status_code == 200:
                return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
        except: continue
    return None, "404: 가용 모델 없음 (API 키 권한 확인 필요)"

def call_groq_v23(m_id, prompt, role):
    """400 에러 방지: 최신 Llama 3 계열로 강제 고정"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {Q_KEY}", "Content-Type": "application/json"}
    
    # 400 방지: 에러 유발 모델(Mixtral) 대신 가장 안정적인 Llama 3.3으로 대체 시도
    final_model = "llama-3.3-70b-versatile" if "mixtral" in m_id.lower() else m_id

    try:
        payload = {
            "model": final_model,
            "messages": [{"role": "user", "content": f"시스템: 당신은 {role}입니다. 질문: {prompt}"}],
            "temperature": 0.5
        }
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content'], "Success"
        return None, f"Status {r.status_code}: {r.text[:50]}"
    except Exception as e:
        return None, str(e)

# --- UI ---
st.set_page_config(page_title="Arena v23.8", layout="wide")
st.title("🏛️ 아레나 v23.8 (최종 안정화 배포)")

experts = [
    ("G", "gemini-1.5-flash", "전략가"),
    ("Q", "llama-3.3-70b-versatile", "기술자"),
    ("Q", "llama-3.1-8b-instant", "리스크") # Mixtral 대신 안정적인 Llama 8B로 변경
]

topic = st.text_input("토론 안건 입력")

if st.button("🚀 아레나 가동 (최종 수정본)") and topic:
    cols = st.columns(3)
    logs = []
    
    for i, (eng, mid, role) in enumerate(experts):
        with cols[i]:
            with st.spinner(f"{role} 호출 중..."):
                time.sleep(2) # 429 방지
                if eng == "G":
                    ans, err = call_gemini_v23(mid, topic, role)
                else:
                    ans, err = call_groq_v23(mid, topic, role)
                
                if ans:
                    st.success(f"**{role}** 입정")
                    st.write(ans)
                    logs.append(ans)
                else:
                    st.error(f"**{role} 최종 실패**")
                    st.code(err)

    if logs:
        st.divider()
        st.subheader("📝 종합 리포트")
        final, _ = call_groq_v23("llama-3.3-70b-versatile", f"종합하라: {' '.join(logs)}", "서기")
        st.markdown(final if final else "작성 실패")
