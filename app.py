import streamlit as st
import pandas as pd
import re
import plotly.express as px
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv() 
api_key = os.environ.get("GROQ_API_KEY")

# Page config
st.set_page_config(
    page_title="Punjab Agriculture Q&A",
    page_icon="🌾",
    layout="wide"
)

# Initialize Groq client

if not api_key:
    st.error("⚠️ GROQ_API_KEY not found. Add it to Render environment variables.")
else:
    client = Groq(api_key=api_key)

# Load dataset
@st.cache_data
def load_data():
    df = pd.read_csv("data/Punjab_Agri_Rainfall_Cleaned.csv")
    df.columns = df.columns.str.lower().str.strip()
    return df

df = load_data()

# Parse and query function
def parse_and_query(question):
    """Parse question and execute query using rules."""
    q = question.lower()
    
    # Extract year
    year_match = re.search(r'\b(19|20)\d{2}\b', question)
    year = int(year_match.group()) if year_match else None
    
    # Extract year range for trends
    year_range = re.search(r'(\d{4})\s*(?:to|-)\s*(\d{4})', question)
    last_n_years = re.search(r'last\s+(\d+)\s+years?', q)
    
    # Determine column
    if 'rainfall' in q or 'rain' in q:
        col = 'rainfall'
    elif 'rice' in q:
        col = 'rice_production'
    elif 'wheat' in q:
        col = 'wheat_production'
    else:
        return None, None, "Cannot identify which column (rainfall/rice/wheat)", None
    
    # Determine operation
    if 'lowest' in q or 'minimum' in q or 'least' in q:
        op = 'min'
    elif 'highest' in q or 'maximum' in q or 'most' in q:
        op = 'max'
    elif 'average' in q or 'mean' in q or 'avg' in q:
        op = 'avg'
    elif 'total' in q or 'sum' in q:
        op = 'sum'
    elif 'trend' in q or 'over time' in q or 'pattern' in q or 'show' in q and ('from' in q or 'between' in q):
        op = 'trend'
    elif 'compare' in q or 'vs' in q:
        op = 'compare'
    elif 'top' in q:
        num_match = re.search(r'top\s+(\d+)', q)
        op = 'top'
        top_n = int(num_match.group(1)) if num_match else 5
    else:
        op = 'list'
    
    # Execute query
    try:
        viz_data = None
        
        if year and op != 'trend':
            filtered = df[df['year'] == year]
            if filtered.empty:
                return None, None, f"No data for year {year}", None
        else:
            filtered = df
        
        if op == 'min':
            idx = filtered[col].idxmin()
            result = filtered.loc[idx]
            code = f"df[df['year'] == {year}].loc[df['{col}'].idxmin()]"
            
        elif op == 'max':
            idx = filtered[col].idxmax()
            result = filtered.loc[idx]
            code = f"df[df['year'] == {year}].loc[df['{col}'].idxmax()]"
            
        elif op == 'avg':
            result = filtered[col].mean()
            code = f"df[df['year'] == {year}]['{col}'].mean()"
            if year:
                viz_df = filtered.groupby('district')[col].mean().reset_index()
                viz_data = {
                    'data': viz_df,
                    'viz_type': 'bar',
                    'title': f'{col.replace("_", " ").title()} by District ({year})'
                }
            
        elif op == 'sum':
            result = filtered[col].sum()
            code = f"df[df['year'] == {year}]['{col}'].sum()"
            
        elif op == 'trend':
            if year_range:
                start_year = int(year_range.group(1))
                end_year = int(year_range.group(2))
                filtered = df[(df['year'] >= start_year) & (df['year'] <= end_year)]
                code = f"df[(df['year'] >= {start_year}) & (df['year'] <= {end_year})].groupby('year')['{col}'].mean()"
            elif last_n_years:
                n = int(last_n_years.group(1))
                max_year = df['year'].max()
                filtered = df[df['year'] >= (max_year - n)]
                code = f"df[df['year'] >= {max_year - n}].groupby('year')['{col}'].mean()"
            else:
                code = f"df.groupby('year')['{col}'].mean()"
            
            result = filtered.groupby('year')[col].mean().reset_index()
            viz_data = {
                'data': result,
                'viz_type': 'line',
                'title': f'{col.replace("_", " ").title()} Trend Over Time'
            }
            
        elif op == 'top':
            result = filtered.nlargest(top_n, col)[['district', 'year', col]]
            code = f"df[df['year'] == {year}].nlargest({top_n}, '{col}')"
            viz_data = {
                'data': result,
                'viz_type': 'bar',
                'title': f'Top {top_n} Districts by {col.replace("_", " ").title()}'
            }
            
        elif op == 'compare':
            available_districts = df['district'].unique()
            districts = [d for d in available_districts if d.lower() in q]
            
            if len(districts) >= 2:
                if year_range:
                    start_year = int(year_range.group(1))
                    end_year = int(year_range.group(2))
                    filtered = df[(df['year'] >= start_year) & (df['year'] <= end_year)]
                    code = f"df[(df['year'] >= {start_year}) & (df['year'] <= {end_year}) & (df['district'].isin({districts[:2]}))][['district', 'year', '{col}']]"
                elif year:
                    code = f"df[(df['year'] == {year}) & (df['district'].isin({districts[:2]}))][['district', 'year', '{col}']]"
                else:
                    code = f"df[df['district'].isin({districts[:2]})][['district', 'year', '{col}']]"
                
                result = filtered[filtered['district'].isin(districts[:2])][['district', 'year', col]]
                
                if len(result['year'].unique()) > 1:
                    viz_data = {
                        'data': result,
                        'viz_type': 'line_compare',
                        'title': f'{col.replace("_", " ").title()} Comparison: {districts[0]} vs {districts[1]}'
                    }
                else:
                    viz_data = {
                        'data': result,
                        'viz_type': 'compare',
                        'title': f'{col.replace("_", " ").title()} Comparison: {districts[0]} vs {districts[1]}'
                    }
            else:
                found_districts = ', '.join([d for d in available_districts if any(word in d.lower() for word in q.split())])
                if found_districts:
                    return None, None, f"Found only one district: {found_districts}. Available districts: {', '.join(available_districts[:5])}...", None
                else:
                    return None, None, f"Could not find those districts. Available districts include: {', '.join(available_districts[:5])}...", None
        else:
            result = filtered[['district', 'year', col]].head(10)
            code = f"df[df['year'] == {year}][['district', 'year', '{col}']].head(10)"
        
        return result, code, None, viz_data
        
    except Exception as e:
        return None, None, f"Query error: {e}", None

def create_visualization(result, viz_data, col):
    """Create visualization based on query type."""
    if viz_data is None:
        return None
    
    viz_type = viz_data.get('viz_type')
    title = viz_data.get('title', 'Data Visualization')
    data = viz_data.get('data')
    
    if data is None or viz_type is None:
        return None
    
    if viz_type == 'line':
        fig = px.line(
            data, 
            x='year', 
            y=col,
            title=title,
            markers=True,
            labels={'year': 'Year', col: col.replace('_', ' ').title()}
        )
        fig.update_traces(line_color='#2E86AB', marker=dict(size=8))
        
    elif viz_type == 'bar':
        if 'district' in data.columns:
            fig = px.bar(
                data,
                x='district',
                y=col,
                title=title,
                color=col,
                color_continuous_scale='Viridis',
                labels={'district': 'District', col: col.replace('_', ' ').title()}
            )
        else:
            fig = px.bar(
                data,
                x='district',
                y=col,
                title=title,
                labels={'district': 'District', col: col.replace('_', ' ').title()}
            )
        fig.update_layout(showlegend=False)
        
    elif viz_type == 'compare':
        fig = px.bar(
            data,
            x='district',
            y=col,
            color='district',
            title=title,
            barmode='group',
            labels={'district': 'District', col: col.replace('_', ' ').title()}
        )
        
    elif viz_type == 'line_compare':
        fig = px.line(
            data,
            x='year',
            y=col,
            color='district',
            title=title,
            markers=True,
            labels={'year': 'Year', col: col.replace('_', ' ').title(), 'district': 'District'}
        )
        fig.update_traces(marker=dict(size=8))
        
    else:
        return None
    
    fig.update_layout(
        template='plotly_white',
        height=400,
        hovermode='x unified'
    )
    
    return fig

def format_with_llm(question, result, code):
    """Use Groq to format the answer nicely."""
    
    if not client:
        return f"ANSWER: Based on the data analysis\n\nEVIDENCE:\n{result}\n\nSOURCE: Punjab_Agri_Rainfall_Cleaned.csv"
    
    if isinstance(result, pd.Series):
        result_str = f"District: {result['district']}, Year: {result['year']}, Value: {result.to_dict()}"
    elif isinstance(result, pd.DataFrame):
        result_str = result.to_string()
    else:
        result_str = f"{result:.2f}"
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": """You format data analysis results into clear answers.

Structure your response as:

ANSWER: [One clear sentence answering the question]

EVIDENCE:
[The specific data that supports this]

SOURCE: Punjab_Agri_Rainfall_Cleaned.csv from data.gov.in Ministry of Agriculture"""
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nData: {result_str}\n\nCode: {code}"
                }
            ],
            temperature=0.3,
            max_tokens=500
        )
        return completion.choices[0].message.content
    except:
        return f"ANSWER: Based on the data analysis\n\nEVIDENCE:\n{result_str}\n\nSOURCE: Punjab_Agri_Rainfall_Cleaned.csv"

# Streamlit UI
st.title("🌾 PB_CropTrack : Punjab Agriculture Q&A System")
st.markdown("### Intelligent Query System over data.gov.in Agricultural Data")

# Sidebar
with st.sidebar:
    st.header("📊 Dataset Information")
    st.metric("Total Records", len(df))
    st.metric("Districts", df['district'].nunique())
    st.metric("Year Range", f"{df['year'].min()} - {df['year'].max()}")
    
    st.markdown("---")
    st.markdown("**Available Columns:**")
    for col in df.columns:
        st.markdown(f"- `{col}`")
    
    st.markdown("---")
    st.markdown("**Original Data Sources:**")
    st.markdown("🔗 [Punjab Rainfall - data.gov.in](https://www.data.gov.in/resource/district-wise-annual-average-rainfall-punjab-1970-2021)")
    st.markdown("🔗 [Punjab Wheat Production - data.gov.in](https://www.data.gov.in/resource/district-wise-production-under-wheat-cultivation-punjab-1968-2018-april-march-0)")
    st.markdown("🔗 [Punjab Rice Production - data.gov.in](https://www.data.gov.in/resource/district-wise-production-under-rice-cultivation-punjab-1968-2018-april-march-0)")
    st.markdown("📅 Downloaded: 18th Oct 2025")

# Main area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Ask Your Question")
    
    sample_questions = [
        "Which district received the highest rainfall in 2007?",
        "What was the average rice production in 2000?",
        "Which district had the lowest wheat production in 1995?",
        "Show rice production trend from 2000 to 2010",
        "Show top 5 districts by rice production in 2010",
        "Compare rainfall between Amritsar and Ludhiana from 2001 to 2010"
    ]
    
    selected_sample = st.selectbox(
        "Select a sample question or type your own:",
        [""] + sample_questions
    )
    
    question = st.text_input(
        "Your Question:",
        value=selected_sample,
        placeholder="e.g., Which district had highest rainfall in 2007?"
    )
    
    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        ask_button = st.button("🔍 Ask", type="primary", use_container_width=True)
    with col_btn2:
        clear_button = st.button("Clear", use_container_width=True)

with col2:
    st.subheader("Quick Stats")
    
    latest_year = df['year'].max()
    latest_data = df[df['year'] == latest_year]
    
    if not latest_data.empty:
        st.metric(
            f"Avg Rainfall ({latest_year})",
            f"{latest_data['rainfall'].mean():.1f} mm"
        )
        st.metric(
            f"Total Rice ({latest_year})",
            f"{latest_data['rice_production'].sum():.0f}"
        )
        st.metric(
            f"Total Wheat ({latest_year})",
            f"{latest_data['wheat_production'].sum():.0f}"
        )

# Process question
if ask_button and question:
    with st.spinner("🔍 Analyzing your question..."):
        result, code, error, viz_data = parse_and_query(question)
        
        if error:
            st.error(f"❌ {error}")
        else:
            q = question.lower()
            if 'rainfall' in q:
                col = 'rainfall'
            elif 'rice' in q:
                col = 'rice_production'
            elif 'wheat' in q:
                col = 'wheat_production'
            else:
                col = None
            
            fig = create_visualization(result, viz_data, col) if col else None
            
            if fig:
                tab1, tab2, tab3, tab4 = st.tabs(["📝 Answer", "📊 Visualization", "📋 Data", "💻 Code"])
            else:
                tab1, tab2, tab3 = st.tabs(["📝 Answer", "📋 Data", "💻 Code"])
            
            with tab1:
                st.markdown("### Answer")
                formatted_answer = format_with_llm(question, result, code)
                st.markdown(formatted_answer)
            
            if fig:
                with tab2:
                    st.markdown("### Visual Analysis")
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption("📊 Interactive chart - hover for details, zoom in/out, pan, or download as PNG")
            
            data_tab = tab3 if fig else tab2
            with data_tab:
                st.markdown("### Raw Data")
                if isinstance(result, pd.Series):
                    st.dataframe(result.to_frame().T, use_container_width=True)
                elif isinstance(result, pd.DataFrame):
                    st.dataframe(result, use_container_width=True)
                else:
                    st.metric("Result", f"{result:.2f}")
            
            code_tab = tab4 if fig else tab3
            with code_tab:
                st.markdown("### Executed Code")
                st.code(code, language="python")
                st.caption("This pandas code was executed on the dataset to retrieve the answer")

if clear_button:
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>Built for Project Samarth | Data source: data.gov.in | Ministry of Agriculture & Farmers Welfare</p>
    <p>🔒 Powered by Groq (Llama 3.1) | Fast & Efficient</p>
</div>
""", unsafe_allow_html=True)