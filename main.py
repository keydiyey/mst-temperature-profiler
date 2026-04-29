import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sb
import numpy as np

def load_excel(excel_file, profiler:str = "KIC")-> pd.DataFrame:
    """
    Loads the excel_file and cleans data
    """

    if profiler == "KIC":
        # skip the first 101 rows since it is jus bs 
        data = pd.read_excel(excel_file, skiprows=101)
        # remove the two unnamed columns? how is it reading nan obj  bro ([:-2]) negative indexing means to remove the last two columns
        cleaned = data.columns[:-2]
        # this part tells to only keep the columns that are in the cleaned columns list
        data = data[cleaned]
        # adds minutes column in the first column
        data.insert(0, "Minutes", data["Seconds"] / 60)
        # Removes the Seconds Columns 
        cleaned = data.drop(data.columns[[1]], axis=1)

    elif profiler == "SEFRAM":
        # i dont know what sefram output looks like bro
        data = pd.read_excel(excel_file, skiprows=0)
        cleaned = data
    
    return cleaned


def get_dwell_times(data, TCS, threshold=0.5, min_minutes=30)-> pd.DataFrame:

    # get mean temp across all thermocouple per minute and add a row average temp
    data['Average_Temp'] = data[TCS].mean(axis=1)
    data = data[['Minutes', 'Average_Temp']]
    
    is_flat = data['Average_Temp'].diff().abs() < threshold
    
    data['group'] = (is_flat != is_flat.shift()).cumsum()

    dwells = data[is_flat].groupby('group').agg(
        Start_Min=('Minutes', 'min'),
        End_Min=('Minutes', 'max'),
        Avg_Dwell_Temp=('Average_Temp', 'mean'),
        Duration=('Minutes', lambda x: x.max() - x.min())
    )

    summary_table = dwells[dwells['Duration'] > min_minutes]

    return summary_table

def style_plot(graph, title):
    # Background color
    graph.set_facecolor('white')
    
    # Use a soft grid only on the Y-axis (temp levels)
    graph.yaxis.grid(True, linestyle='-', which='major', color='grey', alpha=0.2)
    graph.xaxis.grid(True, linestyle='-', which='major', color='grey', alpha=0.2)
    
    # Set labels
    graph.set_xlabel("Time (Minutes)", fontsize=10, color = "black")
    graph.set_ylabel("Temperature (°C)", fontsize=10, color="black")

    return graph

# ------------------ Interface ------------------
with st.sidebar:
    st.header("Temperature Profiler")
    uploaded_file = st.file_uploader("Upload Profiler Data Excel File here :3", type=["xlsx"])
    profiler = st.pills("Select Profiler Type", options=["KIC", "SEFRAM"])
    test = st.pills("Select Test Type", options=["Thermal Cycle (TC)", "Humidity Freeze (HF)", "Damp Heat (DH)", "Bake", "Thermal Shock (TS)"])


    run_button = st.button(label = "Run", use_container_width=True)


# On click
if run_button:
    if uploaded_file:
        cleaned_data = load_excel(uploaded_file)
        
        longform = cleaned_data.melt(id_vars="Minutes", var_name="TC", value_name="Temperature")

        # Plotting
        figure, graph = plt.subplots(figsize=(12, 6), dpi=100)
        sb.lineplot(data=longform, x="Minutes", y="Temperature", hue="TC", ax=graph, linewidth=2)

        style_plot(graph, f"{test} Profile Analysis")
            


        # set temp limits here
        if test == "Thermal Cycle (TC)":
            # i know tc is from -40 to 120
            limits = [-40, 120]
        elif test == "Humidity Freeze (HF)":
            # hmmm hf i just know that it is 85 C
            limits = [-40, 85]
        elif test == "Damp Heat (DH)":
            # ?? i forgor
            limits = []
        elif test == "Bake":
            limits = [0, 120]

        elif test == "Thermal Shock (TS)":
            # thermal shock -70? to 140?
            limits = [-70, 140]
        

        # y axis +- 10 para di sagad onti
        graph.set_ylim(min(limits) - 10, max(limits) + 10)

        tolerances = [t for l in limits for t in (l-2, l, l+2)]

        # tolerance lines
        for tolerance in tolerances:
            graph.axhline(tolerance, color='red', linestyle = "--", alpha=0.2)

        #legend outside of plot
        graph.legend(bbox_to_anchor=(1.05, 1), loc='upper left', frameon=False, fontsize=9)

        # Display the plot
        st.header("Thermal Profile Plot")
        st.pyplot(figure)

        # Display Data Table
        with st.expander("View Cleaned Data"):
            st.dataframe(cleaned_data)
        st.text("Dwell times for the test:")
        
        # lists all the available columns ...
        # the [1:] means from after the first item (minutes) to the end
        TC_list = cleaned_data.columns[1:]
        dwell_times = get_dwell_times(data = cleaned_data, TCS=TC_list, threshold=0.9, min_minutes=30)
        
        st.dataframe(dwell_times)

