# Core pkgs
import streamlit as st
st.set_page_config(layout="wide")
import altair as alt
## EDA Pkgs
import base64
import json
import jsonlines
import pandas as pd
import os
import numpy as np
import sys
import plotly.graph_objects as go
from datetime import datetime
import matplotlib.pyplot as plt
from wordcloud import WordCloud
# from container_ import main_proto

##############

# 
def select_useful_cols(corpus):
    """
    we just keep esssential cols that will be used for filtering and vizualising
    """
    columns = ['name','text','title',	'SNE',	'TNE',	'pertinence', 'thematic']
    new_corpus = pd.DataFrame(corpus, columns=columns)
    corpus_data  = pd.concat([new_corpus.drop(['SNE', 'TNE'], axis=1), new_corpus['SNE'].apply(pd.Series), new_corpus['TNE'].apply(pd.Series)], axis=1)
    return corpus_data

# 
def read_corpus(file):
    """
    fxn to pars the database : corpus of thematic documents
    """
    long_list = []
    with jsonlines.open(file) as f:
        for line in f.iter():
            long_list.append(line)
    my_corpus = pd.DataFrame(long_list,copy =True)
    corpus = select_useful_cols(my_corpus)
    return corpus



def look_for_thematic_data(file,thematic):
    '''
    Fxn to retrive data for a given thematic data from 3M Database. Three thematics are included :
    agriculture, hydrologie, and urbanisation
    file : input file, the database in jsonl, in this case
    '''
    my_corpus = read_corpus(file) 
    
    if thematic == 'risque':
        them_mask = my_corpus['thematic']==thematic
        query_data = my_corpus[them_mask]

    if thematic == 'urbanisme':
        them_mask = my_corpus['thematic']==thematic
        query_data = my_corpus[them_mask]
    return query_data

def get_table_download_link_csv(df):
    """
    fnx to dowload the query results in csv file format
    """
    #csv = df.to_csv(index=False)
    csv = df.to_csv(index=False, sep="\t", escapechar='\\').encode()
    #b64 = base64.b64encode(csv.encode()).decode() 
    b64 = base64.b64encode(csv).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="data.csv" target="_blank">Download csv file</a>'
    return href    

def process_date(corpus_data):
    """
    this fxn is used to categorize data during vizualisation.
    related to tne_color() fxn below
    """

    corpus_data['date'] = pd.to_datetime(corpus_data['date']) 
    corpus_data_tne = corpus_data[corpus_data['date'].notnull()]
    # corpus_data_tne.head(2)
    range_1 = corpus_data_tne[corpus_data_tne['date']>='2019-01-01']
    # range_1
    mask = (corpus_data_tne['date'] > '2015-01-01') & (corpus_data_tne['date'] <= '2019-01-01')
    range_2 = corpus_data_tne[mask]
    # range_2
    range_3 = corpus_data_tne[corpus_data_tne['date']<='2015-01-01']
    return corpus_data_tne, range_1, range_2, range_3    

def temporal_filter(filtered_data):
    """
    TO DO : take into account temporal filter (range for data query) as its doesn't works yet in UI.
    """
    
    return filtered_data
    
def sne_color(df):
    """
    fnx to differentiate pie diagram colors, for spatial named entities
    """
    colors = []
    for p in df["node_labels"]:
        if p in ["", 'Data Spatiality<br>']:
            colors.append("white")
        elif p in ['With_SNE']:
            colors.append("green")
        elif p in ["WithOut_SNE"]:
            colors.append("blue")
    return colors

###
def tne_color(df):
    """
    fnx to differentiate pie diagram colors, for temporal named entities
    """
    colors = []
    for p in df["node_labels"]:
        if p in ["", 'Data Temporality<br>']:
            colors.append("white")
        elif p in ["<1 an"]:
            colors.append("blue")
        elif p in ["1 à 5 ans"]:
            colors.append("brown")
        else:
            colors.append("red")
    return colors

###
def drw_pie(df, colors):
#     colors = tne_color(df)
    """
    fxn to draw pie diagram
    """
    fig=go.Figure(
    data=go.Sunburst(
        ids=df["node_names"],
        labels=df["node_labels"], 
        parents=df["node_parent"],
        marker=dict(colors=colors),
        values=df["node_counts"],
        branchvalues="total",
        texttemplate = ('%{label}',
                        '%{label}<br>%{percentParent:.1%}',
                        '%{label}<br>%{percentParent:.1%}',
                        '%{label}<br>%{percentParent:.1%}',
                        '%{label}<br>%{percentParent:.1%}',
                        '%{label}<br>%{percentParent:.1%}',
                        '%{label}<br>%{percentParent:.1%}',
                        '%{label}<br>%{percentParent:.1%}',
                        '%{label}<br>%{percentParent:.1%}'),),)
    fig.show()
    



# corpus_data = pd.read_csv('corpus.csv')
def run(corpus_data):
    """
    fxn that separate the corpus, according to the spatio-temporal coverage.
    
    """
    corpus_data_tne, range_1, range_2, range_3 = process_date(corpus_data)
    
    SNE_NODE = {'node_names': ['Corpus', 'With_SNE', 'WithOut_SNE'],
                   'node_parent': ["", "Corpus", "Corpus"],
                   'node_labels': ['Data Spatiality<br>','With_SNE', 'WithOut_SNE'],
                   #'node_counts': [len(corpus),  len(corpus_with_extend), len(corpus_without_extend)]
                   'node_counts': [len(corpus_data), corpus_data['ent0'].isna().sum(), len(corpus_data)- corpus_data['ent0'].isna().sum()]
                  }
    TNE_NODE = {'node_names': ['Corpus',"WithOut_TNE",'With_TNE', "<1 an", "1 à 5 ans","> 5 ans"],
                   'node_parent': ["", "Corpus", "Corpus", "With_TNE",'With_TNE','With_TNE'],
                   'node_labels': ['Data Temporality<br>',"WithOut_TNE",'With_TNE',"<1 an", "1 à 5 ans","> 5 ans"],
                   #'node_counts': [len(corpus),  len(corpus_with_extend), len(corpus_without_extend)]
                   'node_counts': [len(corpus_data),len(corpus_data)-len(corpus_data_tne),len(corpus_data_tne), len(range_1), len(range_2),len(range_3)]
                  }

    
    df1 = pd.DataFrame(TNE_NODE)
    df2 = pd.DataFrame(SNE_NODE)
    # colors = sne_color(df)
    colors1 = tne_color(df1)
    colors2 = sne_color(df2)
    return  df1, colors1, df2, colors2
#     drw_pie(df,colors)

def file_selector(folder_path='.'):
    """
    Fxn to select the database file localy
    """
    filenames = os.listdir(folder_path)
    selected_filename = st.selectbox('Select a file', filenames)
    return os.path.join(folder_path, selected_filename)


def main():
    """
    main Fxn, we build the UI with Streamlit (st) 
    """    
    # -- Create three columns
    col1, col2, col3 = st.columns([5, 5, 20])
    # -- Put the image in the middle column
    # - Commented out here so that the file will run without having the image downloaded
    with col1:
        st.image("tetis.png", width=200)
    # -- Put the title in the last column
    with col3:
        st.title('THECOB platform')
    # -- We use the first column here as a dummy to add a space to the left


#     df_main = pd.DataFrame()
    cols = ['name', 'title', 'text', 'pertinence', 'ent0',	'date', 'thematic']
    #st.title('3M Thematic Corpus Builder')
#     menu = ["Home", "Demo Data", "Data"] # menu to be selected
    menu = ["Demo Data"] 
    choice = st.sidebar.selectbox("Menu", menu)
    
    if choice == "Demo Data": # we are using Demo Data menu in this section
        st.subheader("Query parameters")
        txt,start_date, end_date = st.columns([2,1,1])
        Blk,Blk2,date_filter = st.columns([2,1,1])
        Use_Date = date_filter.checkbox("Use Date Filter")

        them_option = txt.selectbox('Select a Topic', ('urbanisme', 'risque'))
    #         start_date.success("start_date")
#         st.write('Thématique :',them_option)# themat)
        start_date = start_date.number_input("start_date",1995,2040)
#         st.write('Date Initale  :', start_date)
#         end_date.success("end_date")
        end_date = end_date.number_input("end_date",1996,2040)
        st.write('Thematic :',them_option)
        st.write('Date Initale  :', start_date)
        st.write('Date Finale :', end_date)

        
        st.subheader("Data base - Corpora")
#         thematique = st.text_area("Nom de thematique --> agriculture or hydrologie or urbanisation")
        filename = file_selector()
        st.write('You selected `%s`' % filename)
#         filename = st.file_uploader("Select an existing DataBase",type=['jsonl'])
        Scrap_button = st.button("Start Retriving") # st.form_submit_button(label = 'submit')
        df_main = ''
        if Scrap_button:
#             file_details = {"Filename":filename.name,"FileType":filename.type,"FileSize":filename.size}
#             st.write(file_details)
#             col1,col2 = st.columns(2)
            df = look_for_thematic_data(filename,them_option)#themat)#thematique)
            df = pd.DataFrame(df, columns=cols)
            df_main = df

            if them_option is not None:
                st.write('Selected parameters :', them_option ,start_date,end_date)


                #df['date'] = pd.to_datetime(df['date'])
                df["date"] = pd.to_datetime(df["date"]).dt.date
                start_date = datetime.strptime(str(start_date), '%Y').date()
                end_date = datetime.strptime(str(end_date), '%Y').date()
                mask = (df['date'] > start_date) & (df['date'] <= end_date)
                df = df[mask]

                st.success('TOP@10 of the Corpus DataFrame')
                st.dataframe(df.head(10))
                st.write(repr(len(df)) + '  documents in the corpus')
#                 st.write('Size of query corpus : ',df.memory_usage(index=True).sum() )
#                 st.write('Size of query corpus : ', df.info(memory_usage='deep'))
                st.write('Size of query corpus : ', repr(round(sys.getsizeof(df)/1000000,2))+ ' '+'Mb')
#                 st.int(len(df)) : >>> sys.getsizeof(df)

#                 st.dataframe(df)
#                 st.markdown(get_table_download_link(df), unsafe_allow_html=True)
                st.markdown(get_table_download_link_csv(df), unsafe_allow_html=True)
                
#             Distribution = st.button("Vizualise Data Distribution") # st.form_submit_button(label = 'submit')
                st.markdown("<h1 style='text-align: center; color: blue;'>Data Spatio-Temporal Distribution</h1>", unsafe_allow_html=True)
#                 col1= st.beta_container()
                
                #divided in two cols, in the first, we display Spatiality diagram et temporality in the second
                
                col1,col2 = st.columns(2) 


#                 col1,col2 = st.beta_ # st.beta_columns(2)
#             if Distribution:
#                 st.success('Quantitative Distribution')
                
                with col1:
                    st.success('Spatiality Coverage')
                    if Use_Date:
                        df1, colors1, df2, colors2 = run(df_main)
                    else:
                        df1, colors1, df2, colors2 = run(df)

                                    ###########
                    fig2=go.Figure( data=go.Sunburst( ids=df2["node_names"],labels=df2["node_labels"], 
                        parents=df2["node_parent"],
                        marker=dict(colors=colors2),
                        values=df2["node_counts"],
                        branchvalues="total",
                        texttemplate = ('%{label}',
                                        '%{label}<br>%{percentParent:.1%}',
                                        '%{label}<br>%{percentParent:.1%}'),),)
#                     fig2.update_layout(margin = dict(t=0, l=0, r=0, b=0))
                    fig2.update_layout(width=350,
                                      height=350,
                                      autosize=True,
                                      margin=dict(t=0, b=0, l=0, r=0),
                                      template="plotly_white",)
#                     fig2.update_layout(autosize=False, width=500,height=500,)
    #                 st.plotly_chart(fig2, use_container_width = True)
                    st.plotly_chart(fig2, use_container_width = True)
                    ########################
                with col2:
                    st.success("Temporality Coverage")

                    fig1=go.Figure( data=go.Sunburst( ids=df1["node_names"],labels=df1["node_labels"], 
                        parents=df1["node_parent"],
                        marker=dict(colors=colors1),
                        values=df1["node_counts"],
                        branchvalues="total",
                        texttemplate = ('%{label}',
                                        '%{label}<br>%{percentParent:.1%}',
                                        '%{label}<br>%{percentParent:.1%}',
                                        '%{label}<br>%{percentParent:.1%}',
                                        '%{label}<br>%{percentParent:.1%}',
                                        '%{label}<br>%{percentParent:.1%}'),),)
#                     fig1.update_layout(margin = dict(t=0, l=0, r=0, b=0))
                    fig1.update_layout(width=350,
                                      height=350,
                                      autosize=True,
                                      margin=dict(t=0, b=0, l=0, r=0),
                                      template="plotly_white",)
                    st.plotly_chart(fig1, use_container_width = True)
                
                #make two cols for wordcloud viz, spatial and temporal
                
                col11,col22 = st.columns(2)

                with col11:
                    st.success('Spatiality WordCloud')
                    #Final word cloud after all the cleaning and pre-processing
                    wordcloud = WordCloud(background_color='black').generate(' '.join(df['ent0'][df['ent0'].notnull()].astype(str) ))
                    plt.imshow(wordcloud)
                    plt.axis("off")
    #                 plt.show()
                    st.pyplot(plt)
            
                with col22:
                    st.success('Temporality WordCloud')
                    df['date'] = pd.to_datetime(df['date']) 
                    counts = df['date'].dt.year.value_counts()
                    counts.index = counts.index.map(str)
                    wordcloud = WordCloud().generate_from_frequencies(counts)
                    plt.figure()
                    plt.imshow(wordcloud, interpolation="bilinear")
                    plt.axis("off")
    #                 plt.show()
                    st.pyplot(plt)
                    
    
    
if __name__ == '__main__':
    main()
