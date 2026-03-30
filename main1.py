import streamlit as st
import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor

# [v18.0] 배포(Secrets) & 로컬(File) 통합 및 동적 모델 스캔 시스템
def get_env_key(name):
    if name in st.secrets:
        return st.secrets[name]
    for f in os.listdir("."):
        if f.lower() == "api_key.txt":
            try:
                with open(f, "r", encoding="utf-8") as file:
                    for line in file:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            if k.strip().upper() == name:
                                return v.strip()
            except: pass
    return None

G_KEY = get_env_key("GEMINI_KEY")
Q_KEY = get_env_key("GROQ_KEY")

def get_active_models():
    """서버에서 현재 사용 가능한 모델 리스트를 실시간으로 가져옴"""
    models = {"G": [], "Q": []}
    if G_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                models["G"] = [m['name'].split('/')[-1] for m in r.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        except: pass
    if Q_KEY:
        try:
            url = "https://api.groq.com/openai/v1/models"
            r = requests.get(url, headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=5)
            if r.status_code == 200:
                models["Q"] = [m['id'] for m in r.json().get('data', [])]
        except: pass
    return models

def call_arena_api(engine, prompt, role, model_id):
    """표준 호출 프로토콜 (Header 위장 포함)"""
    headers = {"Content-Type": "application/json", "User-Agent": "Arena-Client/18.0"}
    try:
        if engine == "G" and G_KEY:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={G_KEY}"
            payload = {"contents": [{"parts": [{"text": f"당신은 {role}입니다. 다음 안건에 대해 전문가적 견해를 밝히세요: {prompt}"}]}]}
            r = requests.post(url, json=payload, headers=headers, timeout=20)
        elif engine == "Q" and Q_KEY:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {Q_KEY}"
            payload = {"model": model_id, "messages": [{"role": "system", "content": f"당신은 {role}입니다."}, {"role": "user", "content": prompt}]}
            r = requests.post(url, json=payload, headers=headers, timeout=20)
        else: return None, "Key Missing"

        if r.status_code == 200:
            return (r.json()['candidates'][0]['content']['parts'][0]['text'] if engine == "G" 
                    else r.json()['choices'][0]['message']['content']), "Success"
        return None, f"Status {r.status_code}"
    except Exception as e: return None, str(e)

# --- UI 설정 ---
st.set_page_config(page_title="Arena v18.0", layout="wide")
st.title("🏛️ 아레나 v18.0 (얼티밋 배포 버전)")

# 사이드바: 모델 스캔 및 상태 확인
with st.sidebar:
    st.header("⚙️ 시스템 설정")
    if st.button("🔍 가용 모델 실시간 스캔"):
        m_list = get_active_models()
        st.session_state.g_list = m_list["G"]
        st.session_state.q_list = m_list["Q"]
        st.success(f"스캔 완료! (G:{len(m_list['G'])}, Q:{len(m_list['Q'])})")
    
    st.write(f"Gemini: {'✅' if G_KEY else '❌'} | Groq: {'✅' if Q_KEY else '❌'}")
    st.info("💡 **배포 팁**: Streamlit Cloud의 Settings > Main file path를 **main1.py**로 변경하세요.")

topic = st.text_input("토론 주제를 입력하세요")

if st.button("🚀 아레나 가동 (5회 중첩 토론)") and topic:
    # 1. 모델 동적 배정 (v2.9.2 로직)
    g_list = st.session_state.get('g_list', ['gemini-1.5-flash'])
    q_list = st.session_state.get('q_list', ['llama-3.3-70b-versatile', 'mixtral-8x7b-32768'])
    
    # 상위 3개 모델 선택
    m1 = g_list[0]
    m2 = q_list[0] if q_list else g_list[0]
    m3 = q_list[1] if len(q_list) > 1 else (g_list[1] if len(g_list) > 1 else m2)

    # 1단계: 전문가 초안
    st.subheader("🟢 1단계: 전문가 초안 도출")
    cols = st.columns(3)
    experts = [(m1, "G" if m1 in g_list else "Q", "전략가"), (m2, "Q", "기술자"), (m3, "Q" if m3 in q_list else "G", "리스크")]
    
    debate_history = []
    for i, (mid, eng, role) in enumerate(experts):
        with cols[i]:
            ans, err = call_arena_api(eng, topic, role, mid)
            if ans:
                st.success(f"**{role}** ({mid})")
                st.write(ans[:600] + "...")
                debate_history.append(f"{role}: {ans}")
            else: st.error(f"**{role} 실패**: {err}")

    # 2~3단계: 5회 중첩 토론
    if debate_history:
        st.divider()
        st.subheader("🔄 2~3단계: 5회 중첩 심화 토론")
        context = "\n".join(debate_history)
        for i in range(5):
            step = "비판" if i < 2 else "대안"
            res, _ = call_arena_api("Q", f"현재까지 논의 요약: {context[-4000:]}\n\n위 내용에 대해 {step}하라.", f"{step}가", m2)
            if res:
                st.write(f"✅ {i+1}회차 {step} 완료")
                context += f"\n\n[{step}]: {res}"
            time.sleep(1)

        # 4단계: 리포트
        st.divider()
        st.subheader("📝 4단계: 최종 리포트")
        final, _ = call_arena_api("Q", f"종합 리포트 작성: {context[-6000:]}", "서기", m2)
        if final:
            st.markdown(final)
            st.download_button("💾 리포트 다운로드", data=final, file_name="arena_report.md")