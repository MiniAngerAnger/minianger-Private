import streamlit as st
import json, requests, os, pandas as pd
from datetime import datetime
import plotly.express as px

# --- 0. 基础配置 ---
st.set_page_config(page_title="NomadVault", layout="wide")

def get_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

# --- 1. 权限验证 ---
if "auth_role" not in st.session_state:
    st.session_state.auth_role = None

if not st.session_state.auth_role:
    st.title("🔐 NomadVault 权限验证")
    pwd = st.text_input("请输入访问口令:", type="password")
    if st.button("进入系统"):
        if pwd == "13571357":
            st.session_state.auth_role = "admin"
            st.rerun()
        elif pwd == "1111111":
            st.session_state.auth_role = "staff"
            st.rerun()
        else:
            st.error("口令错误")
    st.stop()

# --- 2. 汇率引擎 ---
@st.cache_data(ttl=300)
def fetch_rates():
    r = {"CNY": 0.138, "IDR": 0.000062, "USD": 1.0, "USDT": 1.0, "CNY_TO_IDR": 2180, "USD_TO_IDR": 15800, "USD_TO_CNY": 7.23}
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/CNY", timeout=5)
        if resp.status_code == 200:
            f = resp.json().get('rates', {})
            c_u = (1 / f['USD']) * 1.008
            r = {
                "CNY": 1/c_u, "IDR": 1/((f['IDR']/f['USD'])*1.008), "USD": 1.0, "USDT": 1.0,
                "CNY_TO_IDR": f.get('IDR', 2180), "USD_TO_IDR": f.get('IDR', 15800)/f.get('USD', 0.138), "USD_TO_CNY": 1/f.get('USD', 0.138)
            }
    except:
        pass
    return r

rates = fetch_rates()

# --- 3. 数据读写 ---
def load_db(f, d):
    if not os.path.exists(f): return d
    with open(f, 'r', encoding='utf-8') as fs:
        try:
            data = json.load(fs)
            if f == 'transactions.json':
                u_c = rates.get('USD_TO_CNY', 7.23)
                for e in data:
                    t = str(e.get('时间', ''))
                    if len(t) > 16: e['时间'] = t[:16] # 强制去秒
                    if t and not t.startswith('20'): e['时间'] = f"2026-{e['时间']}"
                    if '等值USD' not in e:
                        e['等值USD'] = e.get('等值USDT', round(float(e.get('金额', 0)) * rates.get(e.get('币种', 'USD'), 1.0), 4))
                    if '等值CNY' not in e:
                        e['等值CNY'] = round(e.get('等值USD', 0) * u_c, 2)
            return data
        except: return d

def save_db(f, d):
    if f == 'transactions.json':
        d = sorted(d, key=lambda x: x['时间'], reverse=True)
    with open(f, 'w', encoding='utf-8') as fs:
        json.dump(d, fs, indent=4)
    st.cache_data.clear()

assets = load_db('assets.json', {"fiat_assets": [], "crypto_assets": []})
logs = load_db('transactions.json', [])
all_a = assets.get('fiat_assets', []) + assets.get('crypto_assets', [])
total_usd = sum([float(i['amount']) * rates.get(i['currency'], 1.0) for i in all_a])
opt_list = [f"{i['platform']}|{i['currency']}" for i in all_a]

# --- 4. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 控制中心")
    if st.button("🔄 刷新汇率"):
        st.cache_data.clear()
        st.rerun()
    if st.session_state.auth_role == "admin":
        if "privacy" not in st.session_state: st.session_state.privacy = False
        if st.button("👁️ 隐私模式切换"):
            st.session_state.privacy = not st.session_state.privacy
            st.rerun()
        st.divider()
        with st.expander("📝 修正持仓"):
            sf = st.selectbox("账户", opt_list)
            vf_raw = st.text_input("金额", key="fix_val")
            if st.button("确认修正"):
                try:
                    vf = float(vf_raw.strip())
                    for ck in assets:
                        for x in assets[ck]:
                            if f"{x['platform']}|{x['currency']}" == sf: x['amount'] = vf
                    save_db('assets.json', assets)
                    st.rerun()
                except: st.error("输入非法")
    st.divider()
    if st.button("🚪 退出登录"):
        st.session_state.auth_role = None
        st.rerun()

# --- 5. 记账组件 (物理去错版) ---
def render_ledger():
    ci, cl = st.columns([0.9, 2.1])
    with ci:
        st.subheader("📝 录入流水")
        ty = st.radio("类型", ["支出", "收入"], horizontal=True, label_visibility="collapsed")
        
        # 建立独立容器，防止报错残留在页面
        info_box = st.empty()
        
        with st.form(key=f"led_form_{ty}", clear_on_submit=True):
            tc = st.selectbox("分类", ["🚬 烟酒", "🍚 外餐", "🎰 德州", "🏠 房租", "🛒 购物", "🛠️ 其他"] if ty=="支出" else ["💰 工资", "📈 投资", "🃏 德州盈利", "🎁 报销", "🔄 收入"])
            ta = st.selectbox("账户", opt_list)
            tm_raw = st.text_input("金额", placeholder="输入数字...")
            tn = st.text_input("备注")
            submit = st.form_submit_button("确认存入")
            
            if submit:
                try:
                    tm_str = tm_raw.strip().replace(',', '')
                    if not tm_str:
                        info_box.warning("金额不能为空")
                    else:
                        tm = round(float(tm_str), 4)
                        pn, pc = ta.split('|')
                        uv = round(tm * rates.get(pc, 1.0), 4)
                        cv = round(uv * rates.get('USD_TO_CNY', 7.23), 2)
                        
                        # 执行写入
                        logs.insert(0, {"时间": get_time(), "分类": tc, "账户": pn, "类型": ty, "金额": tm, "币种": pc, "等值USD": uv, "等值CNY": cv, "备注": tn})
                        save_db('transactions.json', logs)
                        
                        # 更新余额
                        for ck in assets:
                            for i in assets[ck]:
                                if i['platform'] == pn and i['currency'] == pc:
                                    i['amount'] = round((i['amount']-tm) if ty=="支出" else (i['amount']+tm), 4)
                        save_db('assets.json', assets)
                        
                        # 核心补丁：入库即闪现，不给报错弹窗留时间
                        st.rerun()
                except:
                    info_box.error("⚠️ 请输入纯数字")

    with cl:
        st.subheader("📜 历史流水")
        if logs:
            df_l = pd.DataFrame(logs).head(50)
            # 严格锁定 8 列展示
            disp = ["时间", "分类", "账户", "类型", "金额", "币种", "等值USD", "备注"]
            st.dataframe(df_l[disp], use_container_width=True, hide_index=True)
            if st.session_state.auth_role == "admin" and st.button("⏪ 撤销上笔"):
                ls = logs.pop(0)
                for ck in assets:
                    for i in assets[ck]:
                        if i['platform'] == ls['账户'] and i['currency'] == ls['币种']:
                            i['amount'] = round((i['amount']+ls['金额']) if ls['类型']=="支出" else (i['amount']-ls['金额']), 4)
                save_db('transactions.json', logs); save_db('assets.json', assets); st.rerun()

# --- 6. 主看板 ---
if st.session_state.auth_role == "admin":
    st.title("🏝️ 资产指挥部")
    val_disp = f"${total_usd:,.2f}" if not st.session_state.privacy else "🔒 ******"
    st.markdown(f"### 总资产 (USD): <span style='color:#f0b90b; font-size:32px;'>{val_disp}</span>", unsafe_allow_html=True)
    
    r1, r2, r3 = st.columns(3)
    r1.success(f"💹 CNY/IDR: {rates.get('CNY_TO_IDR', 0):,.0f}")
    r2.success(f"💹 USD/IDR: {rates.get('USD_TO_IDR', 0):,.0f}")
    r3.success(f"💹 USD/CNY: {rates.get('USD_TO_CNY', 0):.2f}")
    
    t1, t2, t3 = st.tabs(["📊 看板", "📝 记账", "📈 统计"])
    with t1:
        st.subheader("资产占比 (现值)")
        rows = [{"平台": f"{i['platform']} ({i['currency']})", "现值(USD)": round(float(i['amount']) * rates.get(i['currency'], 1.0), 2)} for i in all_a if float(i['amount']) > 0]
        if rows:
            dfp = pd.DataFrame(rows)
            if not st.session_state.privacy:
                fig = px.pie(dfp, values='现值(USD)', names='平台', hole=.4, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(showlegend=True, margin=dict(t=0, b=0, l=0, r=0), height=350)
                st.plotly_chart(fig, use_container_width=True)
        st.table(pd.DataFrame([{"平台": i['platform'], "数量": i['amount'] if not st.session_state.privacy else "🔒", "币种": i['currency'], "现值(USD)": round(float(i['amount']) * rates.get(i['currency'], 1.0), 2) if not st.session_state.privacy else "🔒"} for i in all_a]))
    with t2:
        render_ledger()
    with t3:
        if logs:
            df = pd.DataFrame(logs)
            df['dt'] = pd.to_datetime(df['时间'], errors='coerce')
            df = df.dropna(subset=['dt'])
            df['Month'] = df['dt'].dt.strftime('%Y-%m')
            m = st.selectbox("月份", sorted(df['Month'].unique(), reverse=True))
            dfm = df[df['Month'] == m]
            ex = dfm[dfm['类型'] == '支出']['等值USD'].sum()
            im = dfm[dfm['类型'] == '收入']['等值USD'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("🔴 支出", f"${ex:,.2f}")
            c2.metric("🟢 收入", f"${im:,.2f}")
            c3.metric("⚖️ 盈亏", f"${im - ex:,.2f}", delta=float(im - ex))
            st.divider()
            cl, cr = st.columns(2)
            with cl:
                st.write("### 支出构成")
                de = dfm[dfm['类型'] == '支出']
                if not de.empty: st.plotly_chart(px.pie(de, values='等值USD', names='分类', hole=.4, template="plotly_dark"), use_container_width=True)
            with cr:
                st.write("### 收入构成")
                di = dfm[dfm['类型'] == '收入']
                if not di.empty: st.plotly_chart(px.pie(di, values='等值USD', names='分类', hole=.4, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
else:
    st.title("📝 记账助手 (协作版)")
    render_ledger()
