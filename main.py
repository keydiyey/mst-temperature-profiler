import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sb
import re
import io

def load_excel(excel_file) -> pd.DataFrame:
    first_column = pd.read_excel(excel_file, usecols=[0], header=None)
    first_column_clean = first_column.iloc[:, 0].astype(str).str.strip()
    seconds_rows = first_column.index[first_column_clean == "Seconds"].tolist()

    if not seconds_rows:
        raise ValueError('Could not find "Seconds" in the first column.')

    header_row = seconds_rows[0]
    raw_data = pd.read_excel(excel_file, header=header_row)
    raw_data.columns = raw_data.columns.str.strip()
    
    data = raw_data[raw_data.columns[:-2]]
    data.insert(0, "Minutes", data["Seconds"] / 60)
    return data.drop(columns=["Seconds"])

def get_dwell_times(data, TCS, threshold=0.5, min_minutes=30) -> pd.DataFrame:
    df = data.copy()
    df['Average_Temp'] = df[TCS].mean(axis=1)
    df = df[['Minutes', 'Average_Temp']].copy()
    
    is_flat = df['Average_Temp'].diff().abs() < threshold
    df.loc[:, 'group'] = (is_flat != is_flat.shift()).cumsum()

    dwells = df[is_flat].groupby('group').agg(
        Start_Min=('Minutes', 'min'),
        End_Min=('Minutes', 'max'),
        Avg_Dwell_Temp=('Average_Temp', 'mean'),
        Duration=('Minutes', lambda x: x.max() - x.min())
    ).reset_index(drop=True)

    summary = dwells[dwells['Duration'] > min_minutes].round(2)
    return summary

# --- Sidebar ---
with st.sidebar:
    st.header("Temperature Profiler")
    uploaded_file = st.file_uploader("Upload KIC Profiler Data Excel File", type=["xlsx"])
    test = st.pills("Select Test Type", options=["Thermal Cycle (TC)", "Humidity Freeze (HF)", "Damp Heat (DH)", "Thermal Shock (TS)"])
    run_button = st.button(label="Run", use_container_width=True)

# --- Main App Logic ---
if run_button and uploaded_file and test:
    match = re.search(r'(CH\s*\d+|\bCH\d+\b)', uploaded_file.name, re.IGNORECASE)
    chamber_info = match.group(0).upper() if match else "Unknown Chamber"

    cleaned_data = load_excel(uploaded_file)
    TC_list = cleaned_data.columns[1:]
    
    if test == "Thermal Cycle (TC)":
        limits, min_dwell, threshold = [-40, 120], 10, 0.5
    elif test == "Humidity Freeze (HF)":
        limits, min_dwell, threshold = [-40, 85], 20, 1.2
    elif test == "Damp Heat (DH)":
        limits, min_dwell, threshold = [85, 85], 120, 0.3
    elif test == "Thermal Shock (TS)":
        limits, min_dwell, threshold = [-70, 140], 10, 0.5

    dwell_times = get_dwell_times(cleaned_data, TC_list, threshold, min_dwell)

    # ==========================================
    # 1. RENDER NATIVE STREAMLIT UI (NOT AN IMAGE)
    # ==========================================
    st.title("DEVELOPMENT ENGINEERING")
    st.caption(f"**Machine:** {chamber_info} | **Test:** {test}")
    
    # Create side-by-side columns on the dashboard

    st.subheader("Thermal Profile Plot")
    # Generate just the core graph cleanly for the UI
    fig_ui, ax_ui = plt.subplots(figsize=(7, 4.5))
    longform = cleaned_data.melt(id_vars="Minutes", var_name="TC", value_name="Temperature")
    sb.lineplot(data=longform, x="Minutes", y="Temperature", hue="TC", ax=ax_ui, linewidth=1.2)
    
    ax_ui.set_facecolor('white')
    ax_ui.yaxis.grid(True, linestyle='-', color='grey', alpha=0.15)
    ax_ui.xaxis.grid(True, linestyle='-', color='grey', alpha=0.15)
    ax_ui.set_xlabel("Time (Minutes)", fontsize=9)
    ax_ui.set_ylabel("Temperature (°C)", fontsize=9)
    
    y_min = min(limits) - 20 if limits[0] == limits[1] else min(limits) - 10
    y_max = max(limits) + 20 if limits[0] == limits[1] else max(limits) + 10
    ax_ui.set_ylim(y_min, y_max)
    
    for l in list(set(limits)):
        for t in (l-2, l, l+2):
            ax_ui.axhline(t, color='red', linestyle="--", alpha=0.12)
    
    ax_ui.legend(bbox_to_anchor=(1.02, 1), loc='upper left', frameon=False, fontsize=8)
    plt.tight_layout()
    
    # Display the standalone graph object natively
    st.pyplot(fig_ui)

    st.subheader("Table of Values (Dwell Times)")
    if not dwell_times.empty:
        # Native interactive Streamlit Dataframe
        st.dataframe(dwell_times, use_container_width=True, hide_index=True)
    else:
        st.info("No dwell times detected matching the criteria.")

    # ==========================================
    # 2. GENERATE UNIFIED EXPORTABLE REPORT (BACKGROUND ONLY)
    # ==========================================
    fig_report = plt.figure(figsize=(15, 8), dpi=150)
    gs = gridspec.GridSpec(3, 2, height_ratios=[0.7, 0.4, 6], width_ratios=[4.5, 5.5])

    # Title Banner Area
    ax_banner = fig_report.add_subplot(gs[0, :])
    ax_banner.set_facecolor('#003366')
    ax_banner.set_xticks([])
    ax_banner.set_yticks([])
    for spine in ax_banner.spines.values():
        spine.set_visible(False)
    ax_banner.text(0.5, 0.5, 'DEVELOPMENT ENGINEERING', color='white', weight='bold', fontsize=22, ha='center', va='center', transform=ax_banner.transAxes)

    # Metadata Row 
    ax_meta = fig_report.add_subplot(gs[1, :])
    ax_meta.set_facecolor('#F8F9FA')
    ax_meta.set_xticks([])
    ax_meta.set_yticks([])
    for spine in ax_meta.spines.values():
        spine.set_visible(False)
    meta_text = f"Machine: {chamber_info}   |   Test: {test}"
    ax_meta.text(0.5, 0.5, meta_text, color='#333333', weight='bold', fontsize=13, ha='center', va='center', transform=ax_meta.transAxes)

    # Table of Values Panel
    ax_table = fig_report.add_subplot(gs[2, 0])
    ax_table.axis('off')
    ax_table.set_title("Table of Values (Dwell Times)", fontsize=11, weight='bold', pad=10, loc='center')
    
    if not dwell_times.empty:
        table_vals = dwell_times.values.tolist()
        col_labels = ['Start (Min)', 'End (Min)', 'Avg Temp (°C)', 'Duration (Min)']
        tbl = ax_table.table(cellText=table_vals, colLabels=col_labels, loc='center', cellLoc='center')
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
        tbl.scale(1.0, 1.8)
        for (row, col), cell in tbl.get_celld().items():
            if row == 0:
                cell.set_text_props(weight='bold', color='white')
                cell.set_facecolor('#003366')
    else:
        ax_table.text(0.5, 0.5, "No dwell data detected.", ha='center', va='center', color='gray', fontsize=11)

    # Thermal Graph Panel
    ax_graph = fig_report.add_subplot(gs[2, 1])
    sb.lineplot(data=longform, x="Minutes", y="Temperature", hue="TC", ax=ax_graph, linewidth=1.2)
    ax_graph.set_facecolor('white')
    ax_graph.yaxis.grid(True, linestyle='-', color='grey', alpha=0.15)
    ax_graph.xaxis.grid(True, linestyle='-', color='grey', alpha=0.15)
    ax_graph.set_xlabel("Time (Minutes)", fontsize=9)
    ax_graph.set_ylabel("Temperature (°C)", fontsize=9)
    ax_graph.set_title("Thermal Profile Plot", fontsize=11, weight='bold', pad=10)
    ax_graph.set_ylim(y_min, y_max)

    for l in list(set(limits)):
        for t in (l-2, l, l+2):
            ax_graph.axhline(t, color='red', linestyle="--", alpha=0.12)
    ax_graph.legend(bbox_to_anchor=(1.02, 1), loc='upper left', frameon=False, fontsize=8)
    
    plt.subplots_adjust(wspace=0.25, hspace=0.1)
    
    # Prepare background download buffer without rendering fig_report to UI
    img_buf = io.BytesIO()
    fig_report.savefig(img_buf, format='png', bbox_inches='tight', facecolor=fig_report.get_facecolor())
    img_buf.seek(0)
    plt.close(fig_report) # Close to clear memory

    # --- Actions Area ---
    st.markdown("---")
    st.download_button(
        label="📥 Download Report Image",
        data=img_buf,
        file_name=f"Thermal_Profile_Report_{chamber_info}_{test.replace(' ', '_')}.png",
        mime="image/png",
        use_container_width=True
    )

    with st.expander("View Raw Cleaned Dataset"):
        st.dataframe(cleaned_data)