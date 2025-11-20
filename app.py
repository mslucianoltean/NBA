import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

# --- Configurare Inițială Streamlit ---
st.set_page_config(layout="wide", page_title="PRO BETTING ANALYTICS")

# --- Constante și Helpers ---
COLOR_MAP = {
    'SCAZUT': '#00ff41',    # Verde Neon
    'MEDIU': '#ffff00',     # Galben
    'RIDICAT': '#ff0000'    # Roșu
}

@st.cache_data
def load_data(input_file):
    """ Încarcă și pre-procesează datele din CSV. """
    df = pd.read_csv(input_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['decimal_odds'] = df['odds'].apply(lambda odds: 1 + odds / 100 if odds >= 0 else 1 - 100 / odds)
    df = df.sort_values('timestamp')
    return df

class AnalyticsEngine:
    """ Logică de Analiză bazată pe codul existent, adaptată pentru Streamlit. """
    def __init__(self, df, spread_buffer=3.5, total_buffer=6.0):
        self.df = df
        self.spread_buffer = spread_buffer
        self.total_buffer = total_buffer
        self.teams = self._detect_match_info()

    def _detect_match_info(self):
        try:
            home = self.df[self.df['side'] == 'home']['team'].dropna().iloc[0]
            away = self.df[self.df['side'] == 'away']['team'].dropna().iloc[0]
            return {'home': home, 'away': away}
        except:
            teams = self.df['team'].unique()
            return {'home': teams[0], 'away': teams[1] if len(teams) > 1 else "Unknown"}
    
    def _get_metrics(self, market_type, selection):
        # ... [Păstrează funcția get_metrics din codul anterior aici] ...
        if market_type == 'Total':
            subset = self.df[(self.df['market_type'] == 'Total') & (self.df['side'] == selection)]
        else:
            subset = self.df[(self.df['market_type'] == market_type) & (self.df['team'] == selection)]

        if len(subset) < 5: return None

        n = max(3, int(len(subset) * 0.15))
        open_slice = subset.iloc[:n]
        close_slice = subset.iloc[-n:]
        
        avg_open_odds = open_slice['decimal_odds'].mean()
        avg_close_odds = close_slice['decimal_odds'].mean()
        
        if market_type == 'Moneyline':
            avg_open_line = 0; avg_close_line = 0
        else:
            avg_open_line = open_slice['line'].mean()
            avg_close_line = close_slice['line'].mean()

        prob_open = 1 / avg_open_odds if avg_open_odds > 0 else 0
        prob_close = 1 / avg_close_odds if avg_close_odds > 0 else 0
        
        return {
            'open_line': avg_open_line,
            'close_line': avg_close_line,
            'money_flow': (prob_close - prob_open) * 100,
            'current_odds': avg_close_odds
        }

    def _calculate_score(self, market_type, m, selection):
        # ... [Păstrează funcția calculate_score din codul anterior aici] ...
        score = 5 
        
        if m['money_flow'] > 0.5: score += 2
        elif m['money_flow'] < -0.5: score -= 2
        
        if market_type == 'Spread':
            line_tightened = m['close_line'] < m['open_line'] 
            if line_tightened: score += 2
            else: score -= 1
            
        elif market_type == 'Total':
            if selection == 'over' and m['close_line'] < m['open_line'] and m['money_flow'] > 0: score += 3
            elif selection == 'under' and m['close_line'] > m['open_line'] and m['money_flow'] > 0: score += 3
                
        elif market_type == 'Moneyline':
             if m['money_flow'] > 1.5: score += 3

        return max(1, min(10, score))


    def analyze_all(self):
        signals = []
        # Logica pentru Spread, Total, Moneyline (Păstrează structura din codul anterior)
        
        # SPREAD
        for side, team in self.teams.items():
            m = self._get_metrics('Spread', team)
            if m:
                score = self._calculate_score('Spread', m, team)
                risk = self._get_risk_label(score)
                signals.append({
                    'Market': 'SPREAD', 'Selection': team, 'Score': score, 'Risk': risk,
                    'Safe Bet Line': f"{team} {m['close_line'] + self.spread_buffer:.1f}", 'Metrics': m
                })

        # TOTAL
        for side in ['over', 'under']:
            m = self._get_metrics('Total', side)
            if m:
                score = self._calculate_score('Total', m, side)
                risk = self._get_risk_label(score)
                val = m['close_line'] - self.total_buffer if side == 'over' else m['close_line'] + self.total_buffer
                signals.append({
                    'Market': f'TOTAL {side.upper()}', 'Selection': 'Puncte', 'Score': score, 'Risk': risk,
                    'Safe Bet Line': f"{side.title()} {val:.1f}", 'Metrics': m
                })

        # MONEYLINE
        for side, team in self.teams.items():
            m = self._get_metrics('Moneyline', team)
            if m:
                score = self._calculate_score('Moneyline', m, team)
                risk = self._get_risk_label(score)
                rec = "Victorie (ML)" if m['current_odds'] < 2.0 else "Evită / H+ Alternativ"
                signals.append({
                    'Market': 'MONEYLINE', 'Selection': team, 'Score': score, 'Risk': risk,
                    'Safe Bet Line': rec, 'Metrics': m
                })

        return pd.DataFrame(signals).sort_values('Score', ascending=False)
    
    def _get_risk_label(self, score):
        if score >= 7: return "SCĂZUT"
        elif score >= 5: return "MEDIU"
        else: return "RIDICAT"

# --- Funcție de Generare Grafic (Smart Money Visualization) ---
@st.cache_data
def create_analysis_chart(df, market_type, team=None):
    """
    Generează graficul interactiv Plotly.
    Vizualizează mișcarea liniei vs. money flow în timp.
    """
    # 1. Filtrare date pentru piața specifică
    if market_type in ['Spread', 'Moneyline']:
        filtered_df = df[(df['market_type'] == market_type) & (df['team'] == team)].copy()
        y_axis_label = f"Linie {market_type} (puncte)" if market_type == 'Spread' else "Cota Decimală"
        
        # Pentru Moneyline, folosim odds-urile ca valoare Y (linia e 0)
        if market_type == 'Moneyline':
            filtered_df['plot_value'] = filtered_df['decimal_odds']
        else:
            filtered_df['plot_value'] = filtered_df['line']
            
        filtered_df['side_label'] = filtered_df['team']
        
    elif market_type == 'Total':
        filtered_df = df[df['market_type'] == 'Total'].copy()
        filtered_df['plot_value'] = filtered_df['line']
        filtered_df['side_label'] = filtered_df['side']
        y_axis_label = "Total Puncte"

    if filtered_df.empty:
        return None

    # 2. Calcul Money Flow (folosim diferența procentuală de probabilitate față de opener)
    opener_odds = filtered_df.iloc[0]['decimal_odds']
    opener_prob = 1 / opener_odds if opener_odds else 0
    filtered_df['probability'] = 1 / filtered_df['decimal_odds']
    filtered_df['flow_delta'] = (filtered_df['probability'] - opener_prob) * 100
    
    # 3. Creare Grafic Plotly
    fig = px.scatter(
        filtered_df,
        x='timestamp',
        y='plot_value',
        size='flow_delta', # Mărimea punctului indică intensitatea Money Flow-ului
        color='flow_delta', # Culoarea punctului indică direcția Flow-ului
        hover_data=['odds', 'line', 'flow_delta'],
        title=f"Evoluția Liniei vs. Money Flow (Intensitatea Smart Money) - {market_type}",
        labels={'timestamp': 'Timp', 'plot_value': y_axis_label, 'flow_delta': 'Money Flow (%)'}
    )

    fig.update_traces(mode='lines+markers', line_shape='spline')
    fig.update_layout(xaxis_title="Timp (Evoluție)", yaxis_title=y_axis_label)

    # Adăugăm o linie orizontală pentru linia de deschidere (Open Line)
    open_line = filtered_df.iloc[0]['plot_value']
    fig.add_hline(y=open_line, line_dash="dot", annotation_text="Linie Deschidere (Open)", annotation_position="bottom right")

    return fig

# --- Funcția Principală de Afișare UI ---
def main():
    FILE_NAME = "Clippers_vs_Magic_COMPLETE_20251120_1820.csv"
    
    st.markdown(f"## 📊 PRO BETTING ANALYTICS {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.markdown("---")

    try:
        data = load_data(FILE_NAME)
        engine = AnalyticsEngine(data)
        results_df = engine.analyze_all()
        teams = engine.teams
        
        st.markdown(f"### Meci: {teams['away']} @ {teams['home']}")
        
        # --- 1. Tablou de Bord (Tabelul de Recomandări) ---
        st.header("✨ Tabloul de Bord Decizional")
        
        # Stilizarea tabelului cu culori bazate pe Risc (Scor)
        def color_risk(val):
            color = COLOR_MAP.get(val, 'black')
            return f'background-color: {color}; color: black; font-weight: bold' if val != 'SCĂZUT' else f'color: {COLOR_MAP["SCAZUT"]}; font-weight: bold'

        styled_df = results_df.style.applymap(color_risk, subset=['Risk']).format({'Score': '{:.0f}'})
        st.dataframe(styled_df, use_container_width=True)
        
        st.markdown(f"""
            <div style='background-color: #333; padding: 10px; border-radius: 5px; font-size: 14px;'>
                ℹ️ <b>Legenda Riscului:</b> 
                <span style='color: {COLOR_MAP["SCAZUT"]};'>Verde Neon (7-10)</span> | 
                <span style='color: {COLOR_MAP["MEDIU"]};'>Galben (5-6)</span> | 
                <span style='color: {COLOR_MAP["RIDICAT"]};'>Roșu (1-4)</span>.
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")

        # --- 2. Grafice de Analiză (Mecanismul din Spate) ---
        st.header("📈 Analiză Tehnică: Mișcarea Liniei vs. Smart Money")
        st.write("Vizualizează cum s-au mișcat liniile pe parcursul zilei și unde a intrat *volumul masiv de bani* (Smart Money) în raport cu linia de deschidere.")
        
        market_options = ['Spread', 'Total', 'Moneyline']
        selected_market = st.selectbox("Selectează Piața pentru Grafic:", market_options)

        if selected_market == 'Spread' or selected_market == 'Moneyline':
            # Dacă e Spread/ML, trebuie să știm pe cine
            team_options = [teams['home'], teams['away']]
            selected_team = st.selectbox(f"Selectează Echipa pentru {selected_market}:", team_options)
            fig = create_analysis_chart(data, selected_market, selected_team)
        elif selected_market == 'Total':
            # Totalul e comun
            fig = create_analysis_chart(data, 'Total')
        
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            
            # Explicația Mecanismului
            if selected_market != 'Moneyline':
                st.subheader("Cum Citim Graficul (RLM & Smart Money)")
                st.markdown("""
                    * **Mărimea & Culoarea Punctului:** Reprezintă intensitatea **Money Flow**-ului. Punctele mai mari arată unde s-au pariat cei mai mulți bani (probabilistic).
                    * **Linia Rosie (Open):** Linia de start stabilită de bookmaker.
                    * **Semnalul RLM (Reverse Line Movement):** Apare când linia se mișcă **împotriva** a ceea ce pariază publicul (care este de obicei pe linia de deschidere), dar banii (punctele mari) susțin cealaltă parte. Aceasta indică **Smart Money**.
                    * **Steam Movement:** Linia și Punctele (Banii) se mișcă în aceeași direcție (parere populară + suport profesional).
                """)

    except Exception as e:
        st.error(f"A apărut o eroare la procesarea datelor: {e}")
        st.stop()


if __name__ == '__main__':
    main()
