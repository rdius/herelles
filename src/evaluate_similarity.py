import os
from sentence_transformers import util
from nltk.corpus import wordnet

import src.params as params


# read kwds list
def read_kwd(txtfile):
    f = open(txtfile)
    content = f.read()
    kw_list = (content.lower()).split('\n')
    return kw_list


def get_synonym(voc_concept):
    #Creating a list
    synonyms = []
    for syn in wordnet.synsets(voc_concept, lang='fra'):#, lang='fra'
        for lm in syn.lemmas('fra'):
            synonyms.append(lm.name())#adding into synonyms
    synonyms = set(synonyms)
    return synonyms


# recoder pour prendre en compte un fichier csv, la sortie du vocabulaire de concepts final
def generate_new_terms(voc_concept):
    data = read_kwd(voc_concept)
    #print(len(data))
    root, filname = os.path.split(voc_concept)
    filname = filname.split('.txt')[0]
    L = []
    for t in data:
        t = t.split(' ')
        if t.__len__() == 1:
            syn = [get_synonym(a) for a in t]
            for v in syn[0]:
                L.append(v)
        if t.__len__() > 1:
            syn = [get_synonym(a) for a in t]
            #print(syn)
            for s in syn[0]:
                test = " ".join(t[1:])
                w = s.lower() + ' ' + test
                #print('zzz', w)
                L.append(w)
    L = set(L)
    return list(L)


# termes similarity scoring with DistilBert
# corpus ==> list of extracted terms from the corpus with BioTex
# return a dictionary, keys =>  extracted terms, and values => mean of the whole similarity score!
# top_k => k
def measure_(corpus,query) :
    #embedder = SentenceTransformer('distilbert-base-nli-stsb-mean-tokens')
    # Corpus with example sentences
    corpus_embeddings = params.embedder.encode(query, convert_to_tensor=True)
    query_embedding = params.embedder.encode(corpus, convert_to_tensor=True)
    cos_scores = util.pytorch_cos_sim(query_embedding, corpus_embeddings)[0]
    cos_scores = cos_scores.cpu()
    return cos_scores


#
def score_doc_sim(extend_voc_concept, doc):
    kwd_cp = " ".join(k for k in extend_voc_concept[:1000])
    score = measure_(doc["text"],kwd_cp)
    doc["pertinence"] = round(score.tolist()[0], 2)
    return doc


def compute_best_doc(voc_concept, doc):
    extent_voc_concept = generate_new_terms(voc_concept)
    doc = score_doc_sim(extent_voc_concept, doc)
    return doc
