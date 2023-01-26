#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#def constant():
import os
from sentence_transformers import SentenceTransformer
import spacy

CHEMIN_LOG = "./log/"
CHEMIN_RESULTATS = os.getcwd()+"/documents/"# "./documents/"
NOT_SITES = "-site:youtube.com -site:pagesjaunes.fr"

# Download dependencies
nlp_model = spacy.load('fr_core_news_sm')# Text with nlp
embedder = SentenceTransformer('distilbert-base-nli-stsb-mean-tokens')
# print("downloading dependencies...")
# nltk.download('omw-1.4')
# nltk.download('wordnet')
