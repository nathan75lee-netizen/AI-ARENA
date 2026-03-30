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
    return len(clean) > 20

def call_ultimate_relay(role, prompt, primary_eng, pool, history=""):
    """리포트 누락 방지를 위해 타임아웃 및 재시도 강화"""
    # 컨텍스트가 너무 길면 하단 2000자만 유지 (압축)
    if len(history) > 3000:
        history = "--- 이전 내용 생략 ---\n" + history[-2500:]
        
    engines = [primary_eng, "Q" if primary_eng == "G" else "G"]
    for eng in engines:
        targets = pool[eng][:4] # 후보군 확대
        for m_id in targets:
            try:
                instruction = f"지시: 당신은 {role}입니다. 반드시 한국어로 상세히 답변하세요."
                full_p = f"{instruction}\n\n[참고 데이터]\n{history}\n\n[요구 사항]\n{prompt}"
                
                if eng == "G":
                    url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
                    r = requests.post(url, json={"contents": [{"parts": [{"text": full_p}]}]}, timeout=35)
                    ans = r.json()['candidates'][0]['content']['parts'][0]['text'] if r.status_code == 200 else None
                else:
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    r = requests.post(url, headers={"Authorization": f"Bearer {Q_KEY}"}, 
                                     json={"model": m_id, "messages": [{"role": "user", "content": full_p}]}, timeout=35)
                    ans = r.json()['choices'][0]['message']['content'] if r.status_code == 200 else None
                
                if is_valid_korean(ans): return ans, f"{eng}({m_id})"
                time.sleep(3)
            except: continue
    return None, "All Failed"

def scan_models():
    m = {"G": ["models/gemini-1.5-flash", "models/gemini-1.5-pro"], "Q": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]}
    try:
        if G_KEY:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}", timeout=5)
            if r.status_code == 200: m["G"] = [x['name'] for x in r.json().get('models', []) if 'generateContent' in x.get('supportedGenerationMethods', [])]
        if Q_KEY:
            r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=5)
            if r.status_code == 200: m["Q"] = [x['id'] for x in r.json().get('data', []) if "guard" not in x['id'].lower()]
    except: pass
    return m

st.set_page_config(page_title="Arena v32.0", layout="wide")
st.title("🏛️ 아레나 v32.0 (리포트 생성 보장판)")

if 'pool' not in st.session_state: st.session_state.pool = scan_models()
topic = st.text_input("토론 주제", "필리핀 유망 사업 및 투자 전략")

if st.button("🚀 전체 프로세스 가동") and topic:
    pool = st.session_state.pool
    debate_history = ""
    
    # 1. 기조 연설
    st.subheader("📢 1차: 전문가별 핵심 제언")
    experts = [("전략가", "G"), ("기술자", "Q"), ("리스크", "Q")]
    cols1 = st.columns(3)
    for i, (role, eng) in enumerate(experts):
        with cols1[i]:
            ans, _ = call_ultimate_relay(role, "주제에 대한 전문적 견해를 5줄 이상 한국어로 쓰세요.", eng, pool, "")
            if ans:
                st.success(f"**{role}**")
                st.write(ans)
                debate_history += f"<{role} 의견>\n{ans}\n\n"

    # 2. 상호 협의 및 조율 (압축 전달)
    if debate_history:
        st.divider()
        st.subheader("🤝 2차: 상호 협의 및 이견 조율")
        cols2 = st.columns(3)
        consult_log = ""
        for i, (role, eng) in enumerate(experts):
            with cols2[i]:
                with st.spinner(f"{role} 조율 중..."):
                    time.sleep(5)
                    ans, _ = call_ultimate_relay(role, "다른 전문가들의 의견을 검토하고 구체적인 합의안이나 절충안을 제시하세요.", eng, pool, debate_history)
                    if ans:
                        st.info(f"**{role}의 조율안**")
                        st.write(ans)
                        consult_log += f"<{role} 협의 사항>\n{ans}\n\n"

        # 3. 최종 리포트 (데이터 보존 최우선)
        st.divider()
        st.subheader("📊 아레나 최종 종합 리포트")
        with st.spinner("모든 데이터를 종합하여 리포트를 작성 중..."):
            time.sleep(5)
            # 리포트 작성을 위한 최종 프롬프트 (요약 + 협의내용 포함 요청)
            final_p = "1차 제안과 2차 협의 내용을 모두 분석하여, 상호 협의된 핵심 사항을 먼저 요약하고, 최종 실행 로드맵을 한국어로 상세히 작성하라."
            full_context = debate_history + consult_log
            
            # 서기는 가장 안정적인 Groq Llama 70B를 1순위로 사용
            report, status = call_ultimate_relay("수석 서기", final_p, "Q", pool, full_context)
            
            if report:
                st.markdown("### 📋 최종 보고서")
                st.markdown(report)
                st.caption(f"작성 모델: {status}")
            else:
                st.error("리포트 생성에 최종 실패했습니다. 개별 답변들을 확인해 주세요.")
