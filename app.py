import streamlit as st
import json, requests, os, pandas as pd
from datetime import datetime
import plotly.express as px

# --- 0. 权限与验证 (13571357) ---
def check_auth():
    if "auth_role" not in st.session_state: st.session_state.auth_role = None
    if st.session_state.auth_role: return True
    st.title("🔐 NomadVault 权限验证")
    pwd = st.text_input("请输入访问口令:", type="password", key="auth_v669")
    if st.button("进入系统"):
        if pwd == "13571357": st.session_state.auth_role = "admin"; st.rerun()
        elif pwd == "1111111": st.session_state.auth_role = "staff"; st.rerun()
        else: st.error("口令错误")
    return False

if not check_auth(): st.stop()

# --- 1. 数据引擎 ---
def get_time(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@st.cache_data(ttl=300)
def fetch_rates():
    r = {"CNY": 0.1385, "IDR": 0.0000624, "USD": 1.0, "USDT": 1.0, "IDR_PER_USDT": 16000.0}
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/CNY", timeout=5)
        if resp.status_code == 200:
            f = resp.json().get('rates', {})
            c_u = (1 / f['USD']) * 1.008
            r = {"CNY": 1/c_u, "IDR": 1/((f['IDR']/f['USD'])*1.008), "USD": 1.0, "USDT": 1.0, "IDR_PER_USDT": (f['IDR']/f['USD'])*1.008}
    except: pass
    return r

def load_db(f, d, fiat):
    if not os.path.exists(f): return d
    with open(f, 'r', encoding='utf-8') as fs:
        try:
            data = json.load(fs)
            if f == 'transactions.json':
                cny_ref = 1 / fiat.get('CNY', 0.138)
                for e in data:
                    t_str = str(e.get('时间', ''))
                    if t_str and not t_str.startswith('20'): e['时间'] = f"2026-{t_str}"
                    if '等值USDT' not in e: e['等值USDT'] = round(float(e.get('金额', 0)) * fiat.get(e.get('币种', 'USD'), 1.0), 4)
                    if '等值CNY' not in e: e['等值CNY'] = round(e['等值USDT'] * cny_ref, 2)
            return data
        except: return d

def save_db(f, d):
    with open(f, 'w', encoding='utf-8') as fs: json.dump(d, fs, indent=4)
    st.cache_data.clear()

if 'privacy' not in st.session_state: st.session_state.privacy = False
rates = fetch_rates()
assets = load_db('assets.json', {"fiat_assets": [], "crypto_assets": []}, rates)
logs = load_db('transactions.json', [], rates)
all_a = assets.get('fiat_assets', []) + assets.get('crypto_assets', [])
total_now = sum([float(i['amount']) * rates.get(i['currency'], 1.0) for i in all_a])
opt_list = [f"{i['platform']}|{i['currency']}" for i in all_a]

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 控制中心")
    if st.button("🔄 刷新汇率"): st.cache_data.clear(); st.rerun()
    if st.session_state.auth_role == "admin":
        if st.button("👁️ 隐私模式切换"): st.session_state.privacy = not st.session_state.privacy; st.rerun()
        st.divider()
        with st.expander("📝 修正持仓"):
            with st.form("fix"):
                sf = st.selectbox("账户", opt_list); vf = st.number_input("金额", format="%.2f")
                if st.form_submit_button("确认"):
                    for ck in assets:
                        for i in assets[ck]:
                            if f"{i['platform']}|{i['currency']}" == sf: i['amount'] = vf
                    save_db('assets.json', assets); st.rerun()
        with st.expander("➕ 新增资产"):
            with st.form("add"):
                na = st.number_input("金额", min_value=0.0); np = st.text_input("平台")
                nc = st.selectbox("币种", ["USDT", "USD", "CNY", "IDR", "GBP"])
                if st.form_submit_button("确认"):
                    if np:
                        tg = 'crypto_assets' if nc in ["USDT", "USD"] else 'fiat_assets'
                        assets.setdefault(tg, []).append({"platform": np, "currency": nc, "amount": na})
                        save_db('assets.json', assets); st.rerun()
        with st.expander("🗑️ 移除资产"):
            with st.form("del"):
                sd = st.selectbox("账户", opt_list, key="d")
                if st.form_submit_button("确认"):
                    p, c = sd.split('|')
                    for ck in assets: assets[ck] = [i for i in assets[ck] if not (i['platform'] == p and i['currency'] == c)]
                    save_db('assets.json', assets); st.rerun()
    st.divider()
    if st.button("🚪 退出登录"): st.session_state.auth_role = None; st.rerun()

# --- 3. 记账组件 ---
def render_ledger(target):
    ci, cl = target.columns([1, 2])
    with ci:
        st.subheader("📝 录入流水")
        with st.form("l", clear_on_submit=True):
            ty = st.radio("类型", ["支出", "收入"], horizontal=True)
            tc = st.selectbox("分类", ["🚬 烟酒", "🍚 外餐", "🎰 德州", "🏠 房租", "💰 工资", "📈 投资", "🛠️ 其他"])
            ta = st.selectbox("账户", opt_list)
            tm = st.number_input("金额", min_value=0.0); tn = st.text_input("备注")
            if st.form_submit_button("确认"):
                pn, pc = ta.split('|'); uv = round(tm * rates.get(pc, 1.0), 6); cv = round(uv * (1/rates['CNY']), 2)
                logs.insert(0, {"时间": get_time(), "分类": tc, "账户": pn, "类型": ty, "金额": tm, "币种": pc, "等值USDT": uv, "等值CNY": cv, "备注": tn})
                save_db('transactions.json', logs)
                for ck in assets:
                    for i in assets[ck]:
                        if i['platform'] == pn and i['currency'] == pc: i['amount'] = round((i['amount'] - tm) if ty == "支出" else (i['amount'] + tm), 4)
                save_db('assets.json', assets); st.rerun()
    with cl:
        st.subheader("📜 历史流水 (全展示)")
        if logs:
            df_l = pd.DataFrame(logs).head(50)
            st.dataframe(df_l, use_container_width=True, hide_index=True, height=(len(df_l) + 1) * 35 + 3)
            if st.session_state.auth_role == "admin" and st.button("⏪ 撤销上笔"):
                ls = logs.pop(0)
                for ck in assets:
                    for i in assets[ck]:
                        if i['platform'] == ls['账户'] and i['currency'] == ls['币种']: i['amount'] = round((i['amount'] + ls['金额']) if ls['类型'] == "支出" else (i['amount'] - ls['金额']), 4)
                save_db('transactions.json', logs); save_db('assets.json', assets); st.rerun()

# --- 4. 渲染 ---
if st.session_state.auth_role == "admin":
    st.title("🏝️ 资产指挥部")
    dt = f"${total_now:,.2f}" if not st.session_state.privacy else "🔒 ******"
    st.markdown(f"### 当前总资产 (USDT): <span style='color:#f0b90b; font-size:32px;'>{dt}</span>", unsafe_allow_html=True)
    r1, r2, r3 = st.columns(3)
    r1.success(f"💹 USDT/CNY: {1/rates['CNY']:.2f}"); r2.success(f"💹 USDT/IDR: {rates['IDR_PER_USDT']:,.0f}"); r3.success(f"💹 USDT/USD: 1.00")
    t1, t2, t3 = st.tabs(["📊 资产看板", "📝 记账助手", "📈 盈亏统计"])
    with t1:
        st.subheader("资产分布明细")
        rows = [{"平台": i['platform'], "数量": i['amount'] if not st.session_state.privacy else "🔒", "币种": i['currency'], "现值(USDT)": round(float(i['amount']) * rates.get(i['currency'], 1.0), 2) if not st.session_state.privacy else "🔒"} for i in all_a]
        if rows: st.table(pd.DataFrame(rows))
    with t2: render_ledger(st)
    with t3:
        if logs:
            df = pd.DataFrame(logs)
            df['dt'] = pd.to_datetime(df['时间'], errors='coerce', format='mixed')
            df = df.dropna(subset=['dt'])
            df['Month'] = df['dt'].dt.strftime('%Y-%m')
            curr_m = st.selectbox("选择月份", sorted(df['Month'].unique(), reverse=True))
            df_m = df[df['Month'] == curr_m]
            exp_m = df_m[df_m['类型'] == '支出']['等值USDT'].sum(); inc_m = df_m[df_m['类型'] == '收入']['等值USDT'].sum()
            m1, m2, m3 = st.columns(3)
            m1.metric("🔴 本月支出", f"${exp_m:,.2f}"); m2.metric("🟢 本月收入", f"${inc_m:,.2f}"); m3.metric("⚖️ 净盈亏", f"${inc_m - exp_m:,.2f}", delta=float(inc_m - exp_m))
            st.divider()
            cl, cr = st.columns(2)
            with cl:
                st.write("### 支出构成")
                de = df_m[df_m['类型'] == '支出']
                if not de.empty: st.plotly_chart(px.pie(de, values='等值USDT', names='分类', hole=.4, template="plotly_dark"), use_container_width=True)
            with cr:
                st.write("### 收入构成")
                di = df_m[df_m['类型'] == '收入']
                if not di.empty: st.plotly_chart(px.pie(di, values='等值USDT', names='分类', hole=.4, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
else:
    st.title("📝 记账助手 (协作版)")
    render_ledger(st)