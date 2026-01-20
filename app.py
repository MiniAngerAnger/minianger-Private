import streamlit as st
import json, requests, os, pandas as pd
from datetime import datetime
import plotly.express as px

# --- 0. 安全访问控制 ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if st.session_state.authenticated:
        return True
    
    st.title("🔐 访问受限")
    # 密码已设为 7777777
    pwd = st.text_input("请输入 7 位启动口令:", type="password")
    if st.button("验证进入"):
        if pwd == "7777777":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("口令错误，请重新输入")
    return False

if not check_password():
    st.stop()

# --- 1. 国际化字典 ---
LANG = {
    "CN": {
        "title": "🏝️ 巴厘岛数字资产指挥部", "total_assets": "当前总资产", 
        "tabs": ["📊 资产分布", "📝 记账助手", "📈 盈亏统计"],
        "table_cols": ["平台", "数量", "币种", "价值(USDT)"],
        "ledger_title": "录入流水", "history_title": "历史账本 (汇率已锁死)",
        "type": "类型", "cat": "分类", "acc": "账户", "amt": "金额", "note": "备注",
        "exp": "支出", "inc": "收入", "submit": "确认存入", "undo": "⏪ 撤销上笔",
        "sidebar": "⚙️ 控制台", "sync": "🔄 刷新实时汇率", "priv": "👁️ 隐私模式",
        "fix": "📝 修正持仓", "add": "➕ 新增资产", "del": "🗑️ 移除资产",
        "profit": "结余", "no_data": "无数据"
    },
    "EN": {
        "title": "🏝️ Bali Digital Assets Hub", "total_assets": "Current Balance",
        "tabs": ["📊 Portfolio", "📝 Ledger", "📈 Analytics"],
        "table_cols": ["Platform", "Amount", "Ccy", "Value(USDT)"],
        "ledger_title": "New Record", "history_title": "History (Fixed Rate)",
        "type": "Type", "cat": "Category", "acc": "Account", "amt": "Amount", "note": "Note",
        "exp": "Expense", "inc": "Income", "submit": "Submit", "undo": "⏪ Undo",
        "sidebar": "⚙️ Console", "sync": "🔄 Sync Rates", "priv": "👁️ Privacy Mode",
        "fix": "📝 Edit Assets", "add": "➕ Add New", "del": "🗑️ Remove",
        "profit": "Net", "no_data": "No Records"
    }
}

# --- 2. 核心引擎 ---
def get_time(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_db(f, d, fiat):
    if not os.path.exists(f):
        with open(f, 'w', encoding='utf-8') as fs: json.dump(d, fs, indent=4)
        return d
    with open(f, 'r', encoding='utf-8') as fs:
        try:
            data = json.load(fs)
            if f == 'transactions.json' and isinstance(data, list):
                cny_ref = 1 / fiat.get('CNY', 0.138)
                for e in data:
                    t = str(e.get('时间', ''))
                    if t and not t.startswith('20'): e['时间'] = f"2026-{t}"
                    if '等值USDT' not in e: e['等值USDT'] = round(float(e.get('金额', 0)) * fiat.get(e.get('币种', 'USD'), 1.0), 4)
                    if '等值CNY' not in e or e.get('等值CNY') is None or e.get('等值CNY') == "None":
                        e['等值CNY'] = round(e['等值USDT'] * cny_ref, 2)
            return data
        except: return d

def save_db(f, d):
    with open(f, 'w', encoding='utf-8') as fs: json.dump(d, fs, indent=4)
    st.cache_data.clear()

@st.cache_data(ttl=300)
def fetch_rates():
    r = {"CNY": 0.1385, "IDR": 0.0000624, "USD": 1.0, "USDT": 1.0, "IDR_PER_USDT": 16000.0}
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/CNY", timeout=3)
        if resp.status_code == 200:
            f = resp.json().get('rates', {})
            c_u = (1 / f['USD']) * 1.008
            r = {"CNY": 1/c_u, "IDR": 1/((f['IDR']/f['USD'])*1.008), "USD": 1.0, "USDT": 1.0, "IDR_PER_USDT": (f['IDR']/f['USD'])*1.008}
    except: pass
    return r

# --- 3. UI 初始化 ---
st.set_page_config(page_title="NomadVault 6.2", layout="wide")
st.markdown("<style>.stApp{background-color:#0b0e11;color:#eaecef;}.stMetric{background-color:#1e2329;border-radius:8px;padding:15px;border:1px solid #363a45;}div[data-testid='stExpander']{background-color:#1e2329;border:1px solid #363a45;}</style>", unsafe_allow_html=True)

if 'lang' not in st.session_state: st.session_state.lang = 'CN'
if 'privacy' not in st.session_state: st.session_state.privacy = False
T = LANG[st.session_state.lang]

rates = fetch_rates()
assets = load_db('assets.json', {"fiat_assets": [], "crypto_assets": []}, rates)
logs = load_db('transactions.json', [], rates)

all_a = assets.get('fiat_assets', []) + assets.get('crypto_assets', [])
total_now = sum([float(i['amount']) * rates.get(i['currency'], 1.0) for i in all_a])
opt_list = [f"{i['platform']}|{i['currency']}" for i in all_a]

# --- 4. 侧边栏 ---
with st.sidebar:
    st.header(T["sidebar"])
    c_l = st.radio("Lang", ["CN", "EN"], index=0 if st.session_state.lang == 'CN' else 1, horizontal=True, key="lc_62")
    if c_l != st.session_state.lang: st.session_state.lang = c_l; st.rerun()
    if st.button(T["sync"], key="sb_62"): st.cache_data.clear(); st.rerun()
    if st.button(T["priv"], key="pb_62"): st.session_state.privacy = not st.session_state.privacy; st.rerun()
    st.divider()
    with st.expander(T["del"]):
        if opt_list:
            with st.form("df_62"):
                sd = st.selectbox("Item", opt_list)
                if st.form_submit_button("REMOVE"):
                    p, c = sd.split('|')
                    for ck in assets: assets[ck] = [i for i in assets[ck] if not (i['platform'] == p and i['currency'] == c)]
                    save_db('assets.json', assets); st.rerun()
    with st.expander(T["fix"]):
        if opt_list:
            with st.form("ff_62"):
                sf = st.selectbox(T["acc"], opt_list); vf = st.number_input(T["amt"], format="%.2f")
                if st.form_submit_button("OK"):
                    for ck in assets:
                        for i in db[ck] if 'db' in locals() else assets[ck]:
                            if f"{i['platform']}|{i['currency']}" == sf: i['amount'] = vf
                    save_db('assets.json', assets); st.rerun()
    with st.expander(T["add"]):
        with st.form("af_62"):
            na = st.number_input("Amt", min_value=0.0); np = st.text_input("Plat")
            nc = st.selectbox("Ccy", ["USDT", "USD", "CNY", "IDR", "GBP"])
            if st.form_submit_button("ADD"):
                if np:
                    tg = 'crypto_assets' if nc in ["USDT", "USD"] else 'fiat_assets'
                    assets.setdefault(tg, []).append({"platform": np, "currency": nc, "amount": na})
                    save_db('assets.json', assets); st.rerun()

# --- 5. 主看板 ---
st.title(T["title"])
display_bal = f"${total_now:,.2f} USDT" if not st.session_state.privacy else "$ ********"
st.markdown(f"### {T['total_assets']}: <span style='color:#f0b90b; font-size:32px;'>{display_bal}</span>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
cur_u_c = 1/rates['CNY']
c1.success(f"💹 实时 USDT/CNY: {cur_u_c:.2f}"); c2.success(f"💹 实时 USDT/IDR: {rates['IDR_PER_USDT']:,.0f}"); c3.success(f"💹 实时 USDT/USD: 1.00")

t1, t2, t3 = st.tabs(T["tabs"])
with t1:
    rows = [{"p": i['platform'], "a": i['amount'], "c": i['currency'], "v": round(float(i['amount']) * rates.get(i['currency'], 1.0), 2)} for i in all_a]
    if rows:
        df_p = pd.DataFrame(rows); df_p.columns = T["table_cols"]
        st.dataframe(df_p.style.format({T["table_cols"][1]: "{:,.2f}", T["table_cols"][3]: "{:,.2f}"}), use_container_width=True, hide_index=True)

with t2:
    ci, cl = st.columns([1, 2])
    with ci:
        st.subheader(T["ledger_title"])
        ty = st.radio(T["type"], [T["exp"], T["inc"]], horizontal=True, key="ty_62")
        cats = ["🚬 烟酒", "🍚 外餐", "🎰 德州", "🏠 房租", "🛠️ 其他"] if ty == T["exp"] else ["💰 工资", "📈 投资", "🧧 其他"]
        with st.form("lf_62", clear_on_submit=True):
            tc = st.selectbox(T["cat"], cats); ta = st.selectbox(T["acc"], opt_list); tm = st.number_input(T["amt"], min_value=0.0); tn = st.text_input(T["note"])
            if st.form_submit_button(T["submit"]):
                pn, pc = ta.split('|'); snap_r = rates.get(pc, 1.0)
                uv = round(tm * snap_r, 6); cv = round(uv * cur_u_c, 2)
                logs.insert(0, {"时间": get_time(), "分类": tc, "账户": pn, "类型": "支出" if ty == T["exp"] else "收入", "金额": tm, "币种": pc, "等值USDT": uv, "等值CNY": cv, "备注": tn})
                save_db('transactions.json', logs)
                for ck in assets:
                    for i in assets[ck]:
                        if i['platform'] == pn and i['currency'] == pc: 
                            i['amount'] = round((i['amount'] - tm) if ty == T["exp"] else (i['amount'] + tm), 4)
                save_db('assets.json', assets); st.rerun()
    with cl:
        st.subheader(T["history_title"])
        if logs:
            df_l = pd.DataFrame(logs).sort_values(by='时间', ascending=False)
            st.dataframe(df_l, use_container_width=True, hide_index=True)
            if st.button(T["undo"], key="ub_62"):
                ls = logs.pop(0)
                for ck in assets:
                    for i in assets[ck]:
                        if i['platform'] == ls['账户'] and i['currency'] == ls['币种']: 
                            i['amount'] = round((i['amount'] + ls['金额']) if ls['类型'] == "支出" else (i['amount'] - ls['金额']), 4)
                save_db('transactions.json', logs); save_db('assets.json', assets); st.rerun()

with t3:
    if logs:
        df_all = pd.DataFrame(logs); df_all['dt'] = pd.to_datetime(df_all['时间'], format='mixed')
        df_all['Month'] = df_all['dt'].dt.strftime("%b %Y").str.upper()
        ms = sorted(df_all['Month'].unique(), reverse=True); sm = st.selectbox("Month", ms, key="ml_62")
        df_m = df_all[df_all['Month'] == sm]
        ve = df_m[df_m['类型']=='支出']['等值USDT'].sum(); vi = df_m[df_m['类型']=='收入']['等值USDT'].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric(T["exp"], f"${ve:,.2f}"); m2.metric(T["inc"], f"${vi:,.2f}"); m3.metric(T["profit"], f"${vi - ve:,.2f}", delta=float(vi - ve))
        st.markdown("---")
        lc, rc = st.columns(2)
        with lc:
            if not df_m[df_m['类型']=='支出'].empty: st.plotly_chart(px.pie(df_m[df_m['类型']=='支出'], values='等值USDT', names='分类', hole=.4, template="plotly_dark"), use_container_width=True)
        with rc:
            if not df_m[df_m['类型']=='收入'].empty: st.plotly_chart(px.pie(df_m[df_m['类型']=='收入'], values='等值USDT', names='分类', hole=.4, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
