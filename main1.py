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

def is_valid_korean(text):
    if not text: return False
    clean = text.strip()
    if re.match(r'^[0-9.\s%]+$', clean): return False
    if not re.search('[가-힣]', clean): return False
    return len(clean) > 30

def call_ultimate_relay(role, prompt, primary_eng, pool, history=""):
    engines = [primary_eng, "Q" if primary_eng == "G" else "G"]
    for eng in engines:
        targets = pool[eng][:3]
        for m_id in targets:
            try:
                instruction = f"당신은 {role}입니다. 반드시 한국어 문장으로 답변하세요. 숫자로만 답하지 마세요."
                full_p = f"{instruction}\n\n[진행 상황]\n{history}\n\n[지시]\n{prompt}"
                if eng == "G":
                    url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
                    r = requests.post(url, json={"contents": [{"parts": [{"text": full_p}]}]}, timeout=25)
                    ans = r.json()['candidates'][0]['content']['parts'][0]['text'] if r.status_code == 200 else None
                else:
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    r = requests.post(url, headers={"Authorization": f"Bearer {Q_KEY}"}, 
                                     json={"model": m_id, "messages": [{"role": "user", "content": full_p}]}, timeout=25)
                    ans = r.json()['choices'][0]['message']['content'] if r.status_code == 200 else None
                if is_valid_korean(ans): return ans, f"{eng}({m_id})"
                time.sleep(2)
            except: continue
    return None, "All Failed"

def scan_models():
    m = {"G": ["models/gemini-1.5-flash"], "Q": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]}
    try:
        if G_KEY:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}", timeout=5)
            if r.status_code == 200: m["G"] = [x['name'] for x in r.json().get('models', []) if 'generateContent' in x.get('supportedGenerationMethods', [])]
        if Q_KEY:
            r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=5)
            if r.status_code == 200: m["Q"] = [x['id'] for x in r.json().get('data', []) if "guard" not in x['id'].lower()]
    except: pass
    return m

st.set_page_config(page_title="Arena v31.0", layout="wide")
st.title("🏛️ 아레나 v31.0 (협의 사항 요약 및 최종 리포트)")

if 'pool' not in st.session_state: st.session_state.pool = scan_models()
topic = st.text_input("토론 주제", "필리핀 유망 사업 및 투자 전략")

if st.button("🚀 아레나 가동 (협의 포함)") and topic:
    pool = st.session_state.pool
    debate_log = ""
    
    # 1차 기조연설
    st.subheader("📢 1차: 각 분야별 핵심 제안")
    experts = [("전략가", "G"), ("기술자", "Q"), ("리스크", "Q")]
    cols1 = st.columns(3)
    for i, (role, eng) in enumerate(experts):
        with cols1[i]:
            ans, status = call_ultimate_relay(role, "이 주제에 대한 전문적 견해를 밝히십시오.", eng, pool, "")
            if ans:
                st.success(f"**{role}**")
                st.write(ans)
                debate_log += f"[{role} 1차]: {ans}\n\n"

    # 2차 상호 협의 (조율 단계)
    if debate_log:
        st.divider()
        st.subheader("🤝 2차: 전문가 상호 협의 및 이견 조율")
        cols2 = st.columns(3)
        consult_log = ""
        for i, (role, eng) in enumerate(experts):
            with cols2[i]:
                with st.spinner(f"{role} 협의 중..."):
                    time.sleep(4)
                    ans, _ = call_ultimate_relay(role, "다른 전문가들의 의견을 검토하고, 충돌하는 부분에 대한 절충안을 제시하십시오.", eng, pool, debate_log)
                    if ans:
                        st.info(f"**{role}의 조율안**")
                        st.write(ans)
                        consult_log += f"[{role} 협의]: {ans}\n\n"

        # 최종 리포트 (협의 요약 포함)
        st.divider()
        st.subheader("📊 최종 종합 전략 리포트")
        with st.spinner("최종 보고서 작성 중..."):
            summary_p = f"다음은 전문가들의 1차 제안과 2차 협의 내용입니다.\n\n{debate_log}\n{consult_log}\n\n위 내용을 바탕으로 '주요 협의 사항 요약'을 먼저 보여주고, 마지막으로 '최종 실행 로드맵'을 작성하라."
            report, _ = call_ultimate_relay("수석 서기", "전체 토론 요약 및 실행안 작성", "Q", pool, summary_p)
            if report:
                st.markdown(report)
