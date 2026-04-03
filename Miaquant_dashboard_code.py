import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import gspread
import json  # <- 클라우드 비밀금고를 열기 위한 도구 추가!

st.set_page_config(page_title="Miaquant Dashboard", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .section-title { color: #2C3E50; font-size: 18px; font-weight: bold; margin-bottom: 10px; }
    .history-header { color: #1E8449; font-size: 22px; font-weight: bold; margin-top: 40px; margin-bottom: 20px; border-bottom: 2px solid #1E8449; padding-bottom: 5px;}
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_quant_data():
    try:
        # 👇 [클라우드용 변경] 파일 대신 스트림릿 비밀금고(secrets)에서 열쇠를 꺼냅니다!
        key_dict = json.loads(st.secrets["gcp_json"])
        gc = gspread.service_account_from_dict(key_dict)
        
        sheet_url = "https://docs.google.com/spreadsheets/d/15W-2RGmry0sIZLPnVoPkwUsmueQOVrOED88o1SIFpLE/edit?gid=1048531866#gid=1048531866"
        sh = gc.open_by_url(sheet_url)
        
        ws_ticker = sh.worksheet("Ticker")
        data_t = ws_ticker.get_all_values()
        df_ticker = pd.DataFrame(data_t[1:], columns=data_t[0])
        df_ticker = df_ticker.loc[:, df_ticker.columns != '']
        
        ws_current = sh.worksheet("Current")
        data_c = ws_current.get_all_values()
        df_current = pd.DataFrame(data_c[2:], columns=data_c[1])
        df_current = df_current.loc[:, df_current.columns != '']
        
        cols_to_drop = [c for c in ['Theme', 'Core/Satellite', 'Portfolio', 'Stock name'] if c in df_current.columns]
        df_current = df_current.drop(columns=cols_to_drop)
        df_current = pd.merge(df_current, df_ticker[['Ticker', 'Stock name', 'Theme', 'Core/Satellite', 'Portfolio']], on='Ticker', how='left')

        cols_to_numeric_c = ['시가총액', '매출성장률 Annual YoY %', 'EPS성장률 Annual YoY %', 'FCF성장률 Annual YoY %', 
                             '영업 마진 (TTM %)', 'ROE (TTM %)', 'Net Debt/EBITDA', 'Beta', 
                             '1Y Price Momentum (%)', 'MQ_Value_Score', 'MQ_Momentum_Score', 'FCF Yield (%)']
        for col in cols_to_numeric_c:
            if col in df_current.columns:
                df_current[col] = pd.to_numeric(df_current[col].replace({'': np.nan}), errors='coerce')
                
        ws_history = sh.worksheet("History")
        data_h = ws_history.get_all_values()
        df_history = pd.DataFrame(data_h[2:], columns=data_h[1])
        df_history = df_history.loc[:, df_history.columns != '']
        
        cols_to_numeric_h = ['Year', '매출성장률 (Growth %)', 'EPS성장률 (Growth %)', 'FCF성장률 (Growth %)', '영업 마진 (Margin %)', 'ROE (Margin %)']
        for col in cols_to_numeric_h:
            if col in df_history.columns:
                df_history[col] = pd.to_numeric(df_history[col].replace({'': np.nan}), errors='coerce')

        return df_ticker, df_current, df_history
    except Exception as e:
        st.error(f"⚠️ 데이터 파이프라인 로딩 실패!\n에러 내용: {e}")
        st.stop()

df_tick, df_curr, df_hist = load_quant_data()

st.title("📈 Miaquant Dashboard - Fundamental Analysis")

f1, f2, f3, f4, f5 = st.columns(5)
with f1: selected_period = st.selectbox("기간 선택", ["2024 - 2026", "2020 - 2023"])

themes = ["All"] + list(df_tick['Theme'].dropna().unique())
with f2: selected_theme = st.selectbox("Theme", themes)

with f3: selected_core = st.selectbox("Core/Satellite", ["All", "Core", "Satellite"])

stocks = ["All"] + list(df_tick['Stock name'].dropna().unique())
with f4: selected_stock = st.selectbox("Stock name (Focus)", stocks)

ports = ["All"] + list(df_tick['Portfolio'].dropna().unique())
with f5: selected_portfolio = st.selectbox("Portfolio", ports)

df_filtered = df_curr.copy()
if selected_theme != "All": df_filtered = df_filtered[df_filtered['Theme'] == selected_theme]
if selected_core != "All": df_filtered = df_filtered[df_filtered['Core/Satellite'] == selected_core]
if selected_portfolio != "All": df_filtered = df_filtered[df_filtered['Portfolio'] == selected_portfolio]
if selected_stock != "All": df_filtered = df_filtered[df_filtered['Stock name'] == selected_stock]

st.markdown("---")

st.markdown('<p class="section-title">📋 Master Datasheet (Current)</p>', unsafe_allow_html=True)
tbl_cols = ['Stock name', 'Theme', 'MQ_Momentum_Score', 'MQ_Value_Score', 
            '매출성장률 Annual YoY %', '영업 마진 (TTM %)', 'FCF Yield (%)', 'Net Debt/EBITDA', '1Y Price Momentum (%)']
available_cols = [c for c in tbl_cols if c in df_filtered.columns]

if available_cols:
    df_disp = df_filtered[available_cols].sort_values(by="MQ_Momentum_Score", ascending=False)
    st.dataframe(
        df_disp.style.background_gradient(subset=['MQ_Momentum_Score', 'MQ_Value_Score'], cmap='Purples')
                     .format(precision=1),
        use_container_width=True, height=350 
    )

st.markdown("<br>", unsafe_allow_html=True)

st.markdown('<p class="section-title">[1] Integrated - 종목 발굴 (MQ Score 기준)</p>', unsafe_allow_html=True)
if set(['MQ_Value_Score', 'MQ_Momentum_Score']).issubset(df_filtered.columns):
    
    col_sct_left, col_sct_right = st.columns([7, 3])
    
    df_plot = df_filtered.copy()
    if "시가총액" in df_plot.columns:
        df_plot["시가총액"] = df_plot["시가총액"].fillna(0)
        
    with col_sct_left:
        fig_1 = px.scatter(
            df_plot, x="MQ_Value_Score", y="MQ_Momentum_Score", text="Ticker", 
            color="Theme", size="시가총액" if "시가총액" in df_plot.columns else None, 
            hover_data=['Stock name'],
            labels={'MQ_Value_Score': 'MQ Value Score', 'MQ_Momentum_Score': 'MQ Momentum Score'}
        )
        fig_1.update_traces(textposition='top center', marker=dict(opacity=0.7))
        fig_1.add_hline(y=50, line_dash="dot", line_color="gray")
        fig_1.add_vline(x=50, line_dash="dot", line_color="gray")
        
        box_style = dict(bgcolor="rgba(240,240,240,0.8)", bordercolor="lightgray", borderwidth=1)
        fig_1.add_annotation(x=0.98, y=0.98, text="<b>👑 챔피언</b>", xref="paper", yref="paper", xanchor="right", yanchor="top", showarrow=False, font=dict(color="#2C3E50", size=13), **box_style)
        fig_1.add_annotation(x=0.02, y=0.98, text="<b>🚀 인기주</b>", xref="paper", yref="paper", xanchor="left", yanchor="top", showarrow=False, font=dict(color="#2C3E50", size=13), **box_style)
        fig_1.add_annotation(x=0.02, y=0.02, text="<b>🗑️ JUNK!</b>", xref="paper", yref="paper", xanchor="left", yanchor="bottom", showarrow=False, font=dict(color="#7F8C8D", size=13), **box_style)
        fig_1.add_annotation(x=0.98, y=0.02, text="<b>💎 저평가주</b>", xref="paper", yref="paper", xanchor="right", yanchor="bottom", showarrow=False, font=dict(color="#2C3E50", size=13), **box_style)
        
        fig_1.update_layout(height=480, margin=dict(l=0, r=0, t=30, b=0)) 
        st.plotly_chart(fig_1, use_container_width=True)

    with col_sct_right:
        df_plot['Total_Score'] = df_plot['MQ_Value_Score'] + df_plot['MQ_Momentum_Score']
        
        q1 = df_plot[(df_plot['MQ_Value_Score'] >= 50) & (df_plot['MQ_Momentum_Score'] >= 50)].sort_values('Total_Score', ascending=False).head(3)
        q2 = df_plot[(df_plot['MQ_Value_Score'] < 50) & (df_plot['MQ_Momentum_Score'] >= 50)].sort_values('Total_Score', ascending=False).head(3)
        q4 = df_plot[(df_plot['MQ_Value_Score'] >= 50) & (df_plot['MQ_Momentum_Score'] < 50)].sort_values('Total_Score', ascending=False).head(3)
        q3 = df_plot[(df_plot['MQ_Value_Score'] < 50) & (df_plot['MQ_Momentum_Score'] < 50)].sort_values('Total_Score', ascending=False).head(3)

        with st.container(border=True):
            st.markdown("##### 🏆 사분면별 Top 3")
            st.caption("(Value + Momentum 합산 점수 기준)")
            
            def render_top3(title, df_q):
                st.markdown(f"<div style='margin-top: 15px;'>{title}</div>", unsafe_allow_html=True)
                if df_q.empty:
                    st.markdown("<div style='font-size:0.85em; color:gray;'>해당 종목 없음</div>", unsafe_allow_html=True)
                else:
                    items = [f"<b>{r['Ticker']}</b>" for _, r in df_q.iterrows()]
                    st.markdown(f"<div style='font-size:0.95em; color:#2C3E50;'>{' / '.join(items)}</div>", unsafe_allow_html=True)

            render_top3("👑 **챔피언 (가치↑ 모멘텀↑)**", q1)
            render_top3("🚀 **인기주 (가치↓ 모멘텀↑)**", q2)
            render_top3("💎 **저평가주 (가치↑ 모멘텀↓)**", q4)
            render_top3("🗑️ **JUNK! (가치↓ 모멘텀↓)**", q3)
            
            st.markdown("<br>", unsafe_allow_html=True)

st.markdown("---")

c1, c2, c3 = st.columns(3)

with c1:
    with st.container(border=True):
        st.markdown('<p class="section-title">[2] Benchmark (1Y Price Momentum)</p>', unsafe_allow_html=True)
        if '1Y Price Momentum (%)' in df_filtered.columns:
            df_bench = df_filtered.groupby('Theme')['1Y Price Momentum (%)'].mean().reset_index()
            fig_2 = px.bar(df_bench, x="Theme", y="1Y Price Momentum (%)", color="Theme")
            fig_2.add_hline(y=df_bench['1Y Price Momentum (%)'].mean(), line_dash="dot", line_color="red")
            st.plotly_chart(fig_2, use_container_width=True, height=350)

with c2:
    with st.container(border=True):
        st.markdown('<p class="section-title">[3] Character (성장 vs 수익)</p>', unsafe_allow_html=True)
        if set(['매출성장률 Annual YoY %', '영업 마진 (TTM %)']).issubset(df_filtered.columns):
            fig_3 = px.scatter(
                df_filtered, x="매출성장률 Annual YoY %", y="영업 마진 (TTM %)", text="Ticker", color="Theme"
            )
            fig_3.update_traces(textposition='top center')
            fig_3.add_hline(y=0, line_dash="solid", line_color="black", opacity=0.3)
            fig_3.add_vline(x=0, line_dash="solid", line_color="black", opacity=0.3)
            
            box_style = dict(bgcolor="rgba(240,240,240,0.8)", bordercolor="lightgray", borderwidth=1)
            fig_3.add_annotation(x=0.98, y=0.98, text="<b>👑 챔피언</b>", xref="paper", yref="paper", xanchor="right", yanchor="top", showarrow=False, font=dict(color="#2C3E50", size=12), **box_style)
            fig_3.add_annotation(x=0.02, y=0.98, text="<b>💰 캐시카우</b>", xref="paper", yref="paper", xanchor="left", yanchor="top", showarrow=False, font=dict(color="#2C3E50", size=12), **box_style)
            fig_3.add_annotation(x=0.02, y=0.02, text="<b>💤 정체기!</b>", xref="paper", yref="paper", xanchor="left", yanchor="bottom", showarrow=False, font=dict(color="#7F8C8D", size=12), **box_style)
            fig_3.add_annotation(x=0.98, y=0.02, text="<b>🔥 유망주</b>", xref="paper", yref="paper", xanchor="right", yanchor="bottom", showarrow=False, font=dict(color="#2C3E50", size=12), **box_style)
            
            st.plotly_chart(fig_3, use_container_width=True, height=350)

with c3:
    with st.container(border=True):
        st.markdown('<p class="section-title">[4] Risk 관리</p>', unsafe_allow_html=True)
        if set(['Net Debt/EBITDA', 'Beta']).issubset(df_filtered.columns):
            fig_4 = px.scatter(df_filtered, x="Net Debt/EBITDA", y="Beta", text="Ticker", color="Theme")
            fig_4.update_traces(textposition='top center')
            fig_4.add_hline(y=1, line_dash="dot", line_color="red", annotation_text="Beta=1")
            
            box_style = dict(bgcolor="rgba(240,240,240,0.8)", bordercolor="lightgray", borderwidth=1)
            fig_4.add_annotation(x=0.98, y=0.98, text="<b>💣 위험</b>", xref="paper", yref="paper", xanchor="right", yanchor="top", showarrow=False, font=dict(color="#2C3E50", size=12), **box_style)
            fig_4.add_annotation(x=0.02, y=0.02, text="<b>🛡️ 안전</b>", xref="paper", yref="paper", xanchor="left", yanchor="bottom", showarrow=False, font=dict(color="#2C3E50", size=12), **box_style)
            
            st.plotly_chart(fig_4, use_container_width=True, height=350)

st.markdown('<p class="history-header">🔍 [5~6] Deep Dive History Lab (선택 종목 시계열 분석)</p>', unsafe_allow_html=True)

focus_tickers = df_tick['Ticker'].dropna().unique()
selected_ticker = st.selectbox("분석할 Ticker를 선택하세요:", focus_tickers, index=0)

df_h_target = df_hist[df_hist['Ticker'] == selected_ticker].copy()

if df_h_target.empty:
    st.info(f"💡 {selected_ticker} 종목의 시계열(History) 데이터가 없습니다. 파이썬 스크립트를 통해 업데이트해 주세요.")
else:
    df_h_year = df_h_target[df_h_target['Quarter'] == 'FY'].sort_values('Year')
    df_h_qtr = df_h_target[df_h_target['Quarter'] != 'FY'].copy()
    if not df_h_qtr.empty:
        df_h_qtr['Period'] = df_h_qtr['Year'].astype(str) + "-" + df_h_qtr['Quarter']
    
    with st.container(border=True):
        h_col1, h_col2, h_col3, h_col4 = st.columns(4)
        
        with h_col1:
            st.markdown("**[5] 성장성 - Year**")
            fig_g_y = go.Figure()
            fig_g_y.add_trace(go.Bar(x=df_h_year['Year'], y=df_h_year['매출성장률 (Growth %)'], name='매출성장', marker_color='lightblue'))
            fig_g_y.add_trace(go.Scatter(x=df_h_year['Year'], y=df_h_year['EPS성장률 (Growth %)'], name='EPS성장', mode='lines+markers', line=dict(color='orange')))
            fig_g_y.add_trace(go.Scatter(x=df_h_year['Year'], y=df_h_year['FCF성장률 (Growth %)'], name='FCF성장', mode='lines+markers', line=dict(color='purple')))
            fig_g_y.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=300, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_g_y, use_container_width=True)

        with h_col2:
            st.markdown("**[5] 성장성 - Quarter**")
            if not df_h_qtr.empty:
                fig_g_q = go.Figure()
                fig_g_q.add_trace(go.Bar(x=df_h_qtr['Period'], y=df_h_qtr['매출성장률 (Growth %)'], name='매출성장', marker_color='lightblue'))
                fig_g_q.add_trace(go.Scatter(x=df_h_qtr['Period'], y=df_h_qtr['EPS성장률 (Growth %)'], name='EPS성장', mode='lines+markers', line=dict(color='orange')))
                fig_g_q.update_layout(showlegend=False, height=300, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_g_q, use_container_width=True)

        with h_col3:
            st.markdown("**[6] 수익성 - Year**")
            fig_p_y = go.Figure()
            fig_p_y.add_trace(go.Bar(x=df_h_year['Year'], y=df_h_year['영업 마진 (Margin %)'], name='영업마진', marker_color='royalblue'))
            fig_p_y.add_trace(go.Scatter(x=df_h_year['Year'], y=df_h_year['ROE (Margin %)'], name='ROE', mode='lines+markers', line=dict(color='goldenrod')))
            fig_p_y.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=300, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_p_y, use_container_width=True)

        with h_col4:
            st.markdown("**[6] 수익성 - Quarter**")
            if not df_h_qtr.empty:
                fig_p_q = go.Figure()
                fig_p_q.add_trace(go.Bar(x=df_h_qtr['Period'], y=df_h_qtr['영업 마진 (Margin %)'], name='영업마진', marker_color='royalblue'))
                fig_p_q.add_trace(go.Scatter(x=df_h_qtr['Period'], y=df_h_qtr['ROE (Margin %)'], name='ROE', mode='lines+markers', line=dict(color='goldenrod')))
                fig_p_q.update_layout(showlegend=False, height=300, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_p_q, use_container_width=True)