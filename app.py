"""
app.py — Tabibiyori Dashboard ホーム画面
URL: /
"""
import streamlit as st
from common import inject_css, setup_sidebar

st.set_page_config(
    page_title="Tabibiyori Dashboard",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_css()
setup_sidebar()

# ── 追加CSS（ホーム専用カード） ───────────────────────────────────────────────
st.markdown("""
<style>
.home-hero{text-align:center;padding:2rem 0 1.8rem;}
.home-hero h1{font-family:'Inter',sans-serif;font-weight:700;font-size:2.2rem;color:#1e3a5f;letter-spacing:-1px;margin:.3rem 0;}
.home-hero p{color:#6b7280;font-size:.82rem;letter-spacing:3px;text-transform:uppercase;}

.cat-label{
  font-family:'Space Mono',monospace;font-size:.62rem;font-weight:700;
  letter-spacing:3px;text-transform:uppercase;color:#9ca3af;
  border-bottom:1px solid #e5e7eb;padding-bottom:.4rem;
  margin:1.8rem 0 1rem;
}

.nav-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:.8rem;margin-bottom:.5rem;}

.nav-card{
  background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;
  padding:1.1rem 1.2rem;cursor:pointer;
  box-shadow:0 1px 3px rgba(0,0,0,.04);
  transition:border-color .15s,box-shadow .15s,transform .15s;
  text-decoration:none;display:block;
}
.nav-card:hover{
  border-color:#1e3a5f;
  box-shadow:0 4px 12px rgba(30,58,95,.12);
  transform:translateY(-1px);
}
.nav-card .icon{font-size:1.5rem;margin-bottom:.4rem;}
.nav-card .title{font-weight:600;font-size:.95rem;color:#1e3a5f;margin-bottom:.2rem;}
.nav-card .desc{font-size:.75rem;color:#9ca3af;line-height:1.5;}
.nav-card .url-tag{
  display:inline-block;margin-top:.5rem;
  font-family:'Space Mono',monospace;font-size:.6rem;
  color:#1e3a5f;background:#eff6ff;
  padding:1px 7px;border-radius:4px;border:1px solid #bfdbfe;
}

.cat-sns .nav-card:hover{border-color:#0ea5e9;box-shadow:0 4px 12px rgba(14,165,233,.12);}
.cat-sns .nav-card .url-tag{color:#0ea5e9;background:#f0f9ff;border-color:#bae6fd;}
.cat-crm .nav-card:hover{border-color:#8b5cf6;box-shadow:0 4px 12px rgba(139,92,246,.12);}
.cat-crm .nav-card .url-tag{color:#8b5cf6;background:#faf5ff;border-color:#e9d5ff;}
.cat-fin .nav-card:hover{border-color:#10b981;box-shadow:0 4px 12px rgba(16,185,129,.12);}
.cat-fin .nav-card .url-tag{color:#10b981;background:#f0fdf4;border-color:#a7f3d0;}
</style>
""", unsafe_allow_html=True)

# ── ヒーロー ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="home-hero">
  <div style="font-size:2.8rem;">🌸</div>
  <h1>Tabibiyori Dashboard</h1>
  <p>Japan Content Operations Dashboard</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SNS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="cat-label">📱 SNS</div>', unsafe_allow_html=True)

sns_cols = st.columns(4)

with sns_cols[0]:
    st.markdown("""
    <div class="nav-card cat-sns">
      <div class="icon">🔥</div>
      <div class="title">トレンド</div>
      <div class="desc">キーワード収集・スコアリング・履歴・再生数トラッキング</div>
      <span class="url-tag">/sns_trend</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/01_sns_trend.py", label="→ トレンドを開く")

with sns_cols[1]:
    st.markdown("""
    <div class="nav-card cat-sns">
      <div class="icon">💬</div>
      <div class="title">DM</div>
      <div class="desc">日次・時間帯別DM集計、ゴールデンタイム分析、月間目標進捗</div>
      <span class="url-tag">/sns_dm</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/02_sns_dm.py", label="→ DMを開く")

with sns_cols[2]:
    st.markdown("""
    <div class="nav-card cat-sns" style="opacity:.6;">
      <div class="icon">📣</div>
      <div class="title">集客</div>
      <div class="desc">集客施策の管理・分析（準備中）</div>
      <span class="url-tag">/sns_acquisition</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/03_sns_acquisition.py", label="→ 集客を開く")

with sns_cols[3]:
    st.markdown("""
    <div class="nav-card cat-sns" style="opacity:.6;">
      <div class="icon">📢</div>
      <div class="title">広告</div>
      <div class="desc">広告運用・効果測定（準備中）</div>
      <span class="url-tag">/sns_ads</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/04_sns_ads.py", label="→ 広告を開く")

# ─────────────────────────────────────────────────────────────────────────────
# 顧客管理
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="cat-label">👤 顧客管理</div>', unsafe_allow_html=True)

crm_cols = st.columns(4)

with crm_cols[0]:
    st.markdown("""
    <div class="nav-card cat-crm">
      <div class="icon">👥</div>
      <div class="title">顧客関係</div>
      <div class="desc">顧客登録・情報管理・備考メモ・購入履歴（Tour / Patreon / Guidebook）</div>
      <span class="url-tag">/crm_customers</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/05_crm_customers.py", label="→ 顧客関係を開く")

with crm_cols[1]:
    st.markdown("""
    <div class="nav-card cat-crm" style="opacity:.6;">
      <div class="icon">📦</div>
      <div class="title">商品関連</div>
      <div class="desc">商品・サービス管理（準備中）</div>
      <span class="url-tag">/crm_products</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/06_crm_products.py", label="→ 商品関連を開く")

# ─────────────────────────────────────────────────────────────────────────────
# 財務経理
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="cat-label">💴 財務経理</div>', unsafe_allow_html=True)

fin_cols = st.columns(5)

with fin_cols[0]:
    st.markdown("""
    <div class="nav-card cat-fin">
      <div class="icon">💴</div>
      <div class="title">売上</div>
      <div class="desc">事業別売上入力・経営ダッシュボード・月別推移グラフ</div>
      <span class="url-tag">/finance_sales</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/07_finance_sales.py", label="→ 売上を開く")

with fin_cols[1]:
    st.markdown("""
    <div class="nav-card cat-fin">
      <div class="icon">🧾</div>
      <div class="title">経費</div>
      <div class="desc">経費入力・領収書PDF管理・勘定科目別グラフ</div>
      <span class="url-tag">/finance_expense</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/08_finance_expense.py", label="→ 経費を開く")

with fin_cols[2]:
    st.markdown("""
    <div class="nav-card cat-fin" style="opacity:.6;">
      <div class="icon">📊</div>
      <div class="title">費用対効果</div>
      <div class="desc">ROI分析・UTMリンク管理（準備中）</div>
      <span class="url-tag">/finance_roi</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/09_finance_roi.py", label="→ 費用対効果を開く")

with fin_cols[3]:
    st.markdown("""
    <div class="nav-card cat-fin" style="opacity:.6;">
      <div class="icon">📋</div>
      <div class="title">BS</div>
      <div class="desc">貸借対照表（準備中）</div>
      <span class="url-tag">/finance_bs</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/10_finance_bs.py", label="→ BSを開く")

with fin_cols[4]:
    st.markdown("""
    <div class="nav-card cat-fin" style="opacity:.6;">
      <div class="icon">📈</div>
      <div class="title">PL</div>
      <div class="desc">損益計算書（準備中）</div>
      <span class="url-tag">/finance_pl</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/11_finance_pl.py", label="→ PLを開く")

# ── フッター ──────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;margin-top:2.5rem;padding-top:1.5rem;border-top:1px solid #e5e7eb;">
  <span style="font-size:.72rem;color:#d1d5db;letter-spacing:1px;">🌸 Tabibiyori Dashboard　— Japan Content Operations</span>
</div>
""", unsafe_allow_html=True)
