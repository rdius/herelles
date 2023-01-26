import json
import os
import re
import signal
import unicodedata
import urllib
from contextlib import contextmanager
import subprocess
from datetime import datetime, timedelta
from time import mktime, strptime
import time
import html2text as html2text
from bs4 import BeautifulSoup, UnicodeDammit
from dateutil import parser
import PyPDF2 as PyPDF2
import magic
from googlesearch import search
import logging, logging.handlers
import src.params as params
from src.evaluate_similarity import compute_best_doc


class Log(object):
    def __init__(self, dossier, nomFichier, niveau=logging.DEBUG):
        super(Log, self).__init__()

        self.__logger__ = logging.getLogger(nomFichier)
        self.__logger__.setLevel(niveau)

        format = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s', datefmt='%d-%m-%Y %H:%M:%S')
        fichierLog = logging.handlers.RotatingFileHandler("{0}{1}.log".format(dossier, nomFichier), 'a', 1000000, 1)

        fichierLog.setLevel(niveau)
        fichierLog.setFormatter(format)
        self.__logger__.addHandler(fichierLog)

        console = logging.StreamHandler()
        console.setLevel(niveau)
        self.__logger__.addHandler(console)

    def info(self, message):
        self.__logger__.info(message)

    def debug(self, message):
        self.__logger__.debug(message)

    def warning(self, message):
        self.__logger__.warning(message)

    def error(self, message):
        self.__logger__.error(message)

    def critical(self, message):
        self.__logger__.critical(message)

    def exception(self, message):
        self.__logger__.exception(message)

    def close(self):
        for handler in  self.__logger__.handlers[:] :
            handler.close()
            self.__logger__.removeHandler(handler)


class TextCleaner():
    """docstring for TextCleaner."""
    def __init__(self):
        """ Expressions régulières """
        self.match_alpha = re.compile(r'\w{3,}') # Existence d'un mot d'au moins 3 lettres
        self.match_formfeed = re.compile(r'\f') # Saut de page
        self.match_useless_line = re.compile(r'^[^\w•]+$|^[\d\. ]+$', re.MULTILINE) # Ligne ne contenant aucun caractère alphanumérique

        self.match_bad_nl = re.compile(r'([^\.?!\n:])\n+(?![IVX\d]+[\.\)]|ANNEXE)([\w\(«\"=<>])') # Mauvais saut de ligne
        self.match_bad_nl2 = re.compile(r'(\.{4,} ?\d+) (\w)') # Mauvais saut de ligne
        self.make_paragraph = re.compile(r'\.\n(?=\w)') # On sépare mieux les paragraphes
        self.match_toomuch_nl = re.compile(r'\n{3,}') # Nouvelles lignes surnuméraires
        self.match_begin_end_nl = re.compile(r'^\n+|\n+$') # Nouvelles lignes au début et à la fin

        self.match_begin_end_space = re.compile(r'^[ \t]+|[ \t]+$', re.MULTILINE) # Espace ou tabulation en début et fin de ligne
        self.match_toomuch_spaces = re.compile(r' {2,}|\t+') # Espaces surnuméraires et tabulations

        self.match_link = re.compile(r'!?\[.*?\]\(.*?\)|https?://[^ ]+', re.DOTALL) # Lien issu de la conversion depuis HTML
        self.match_cesure = re.compile(r'(\w)-(\w)') # Césure
        self.match_stuckwords = re.compile(r'(/\d{2,4}|[a-z])([A-ZÉÈÀÔ])') # Dates et mots collés

        self.match_odd = re.compile(r'[�●§\\\|]+|\(cid:\d+\)|(?<=- )W ') # caractère bizarre
        self.match_accent1 = re.compile(r'Ã©') # é
        self.match_accent2 = re.compile(r'Ã¨') # è
        self.match_accent3 = re.compile(r'Ã') # à
        self.match_puce1 = re.compile(r'')
        self.match_puce2 = re.compile(r'[]')
        self.match_diam = re.compile(r'diam\.')
        self.match_apostrophe = re.compile(r'’')

    def clean(self, text):
        # Remplacement des espaces insécables
        text = text.replace(u'\xa0', ' ')

        text = self.match_link.sub('', text)
        text = self.match_formfeed.sub('\n\n', text)
        text = self.match_useless_line.sub('\n', text)

        text = self.match_diam.sub('diamètre', text)
        text = self.match_accent1.sub('é', text)
        text = self.match_accent2.sub('è', text)
        text = self.match_accent3.sub('à', text)
        text = self.match_puce1.sub('*', text)
        text = self.match_puce2.sub('-', text)
        text = self.match_odd.sub('', text)
        text = self.match_apostrophe.sub('\'', text)

        text = self.match_begin_end_space.sub('', text)
        text = self.match_bad_nl.sub(r'\g<1> \g<2>', text)
        # On double la réparation des lignes, meilleurs résultats
        text = self.match_bad_nl.sub(r'\g<1> \g<2>', text)
        text = self.match_bad_nl2.sub(r'\g<1>\n\g<2>', text)
        text = self.make_paragraph.sub('.\n\n', text)
        text = self.match_stuckwords.sub(r'\g<1> \g<2>', text)
        text = self.match_toomuch_spaces.sub(' ', text)
        text = self.match_toomuch_nl.sub('\n\n', text)
        text = self.match_begin_end_nl.sub('', text)

        return text

    def exists_alpha(self, text):
        """ Contrôle l'existence de caractères alphanumériques """
        return self.match_alpha.search(text) is not None


def query_generator(city, motscles, logger, site):
    logger.info("Génération des requêtes")

    requetes_effectuees = []

    with open("{0}{1}/.sauvegarde.txt".format(params.CHEMIN_RESULTATS, city)) as file:
        to_be_queried = file.readlines()

    for i in range(0, len(motscles), 1):
        # motscles_couple = motscles[i].split("+")
        # Si aucun site n'est spécifié alors on n'exclut
        # seulement ceux définis dans les constants
        if site == "":
            site_or_not_sites = params.NOT_SITES
        # Sinon on cherche uniquement sur le site spécifié
        else:
            site_or_not_sites = "site:" + site
        query = "\"{0}\" AND {1}".format(city, motscles[i])
        if not any(query in s for s in to_be_queried):
            yield query


def format_word(mot):
    """
        Supprime les retour charriot et remplace les espace par un ?.

        @type  mot: String.
        @param mot: Mot à formaté.

        @rtype: String.
        @return: Mot formaté.
    """
    liste_caracteres = dict()

    liste_caracteres["\n"] = ""
    liste_caracteres[" "] = "?"

    for i in liste_caracteres :
        mot = mot.replace(i, liste_caracteres[i])

    return mot


class TimeoutException(Exception): pass

@contextmanager
def sleep_time(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

def convert_pdf_to_txt(src_file_path):
    """
        Appel externe à pdftotext.

        -q : pas de message d'erreur dans la sortie.
         - : envoie la sortie dans la console au lieu d'un fichier texte.

        Capture de la sortie texte.

        @type  src_file_path: String.
        @param src_file_path: Chemin du fichier source.

        @rtype: String.
        @return: Texte brut.
    """
    completed_process = subprocess.run(["pdftotext", "-q", src_file_path, "-"], stdout=subprocess.PIPE)
    return completed_process.stdout.decode('utf-8')


def norm_string(string):
    """ On supprime les accents et on remplace les caractères spéciaux par un tiret bas """
    new_string = unicodedata.normalize('NFKD', string).encode('ascii', 'ignore').decode('utf-8')
    return re.sub(r'[^\w\[\]\./]+', '_', new_string)


def format_to_iso_date(pdfdate):
    datestring = ''
    if pdfdate !='':
        if len(pdfdate)==23:
            datestring = pdfdate[2:-7]
        elif len(pdfdate)==17:
            datestring = pdfdate[2:-1]
        elif len(pdfdate)==21:
            datestring = pdfdate[:-7]
        ts = strptime(datestring, "%Y%m%d%H%M%S")# "%Y-%m-%dT%H:%M:%S.%fZ" )#
        dt = datetime.fromtimestamp(mktime(ts))
        new_format = dt.isoformat()
    else:
        new_format = "no_date"
    return new_format


def get_pdf_info(f, logger):
    fd = PyPDF2.PdfReader(f, 'rb')
    doc_info = fd.metadata
    #print("doc_info :", doc_info)
    if '/ModDate' in doc_info:
        val_ = doc_info['/ModDate']
        try:
            val_ = format_to_iso_date(val_)
        except:
            logger.exception("cannot format the extracted date.\n")
    elif '/CreationDate' in doc_info:
        val_ = doc_info['/CreationDate']
        try:
            val_ = format_to_iso_date(val_)
        except:
            logger.exception("cannot format the extracted date.\n")
    else:
        val_ = None # 'no_date'

    if '/Title' in doc_info:
        title = doc_info['/Title']
    else:
        title = None # 'no_title'
    #print("title :", str(title))
    #print("date :", str(parser.parse(val_).date()))
    return str(title), str(parser.parse(val_).date())


def extract_date(text):
    # Motif : JJ/MM/AAAA
    match_date = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
    # Motif : JJ mois AAAA
    match_date2 = re.search(r'(\d{1,2}) (\w+) (\d{4})', text)

    if match_date:
        date = datetime(
            int(match_date[3]), # Année
            int(match_date[2]), # Mois
            int(match_date[1])  # Jour
        )

        return date

    elif match_date2:
        mapping_month = {
            'janvier': 1,
            'février': 2,
            'mars': 3,
            'avril': 4,
            'mai': 5,
            'juin': 6,
            'juillet': 7,
            'août': 8,
            'septembre': 9,
            'octobre': 10,
            'novembre': 11,
            'décembre': 12,
        }

        month = match_date2[2].lower()

        if month in mapping_month:
            date = datetime(
                int(match_date2[3]), # Année
                mapping_month[month], # Mois
                int(match_date2[1])  # Jour
            )

            return date


def less_html(html_doc):
    """ Prend du code HTML en entrée et retourne un code épuré de certaines balises """
    soup = BeautifulSoup(html_doc, 'html.parser')
    # Regex pour matcher les attributs contenant ces termes
    bad_classes = re.compile(r'menu|head|publici|share|social|button|alert|prev|next|foot|tags|label|sidebar|author|topics|contact|modal|nav|snippet|register|aside|logo|bandeau|immobilier', re.IGNORECASE)
    # Suppression des espaces ou des sauts de ligne au début et à la fin du titre
    title = re.sub(r'^\s|\s$', '', soup.find('title').text)

    # Dictionnaire des métadonnées
    metadata = {}
    metadata['title'] = title
    # Recherche d'une éventuelle balise dont la classe contient "date"
    # En principe la première date est la date de publication
    bloc_date = soup.find(class_=re.compile(r'date', re.IGNORECASE))

    if bloc_date:
        # Recherche du premier motif JJ/MM/AAAA,
        # en principe la date de publication
        metadata['post_date'] = ''
        date = extract_date(bloc_date.text)
        print(">>>> html_date :", str(date))
        if date: metadata['post_date'] = str(parser.parse(str(date)).date())# str(date)# html_date_to_isoformat(repr(date))
#         if date: metadata['post_date'] = html_date_to_isoformat(repr(date))


    for balise in soup.find_all():
        conditions = (
            balise.name == 'head',
            balise.name == 'nav',
            balise.name == 'footer',
            balise.name == 'aside',
            balise.name == 'script',
            balise.name == 'style',
            balise.name == 'a',
            balise.name == 'figure',
            balise.name == 'img',
            balise.name == 'svg',
            balise.name == 'noscript',
            balise.name == 'form',
            balise.name == 'button'
        )

        if any(conditions):
            balise.extract()
        # On ajoute un espace devant chaque span, pour éviter
        # parfois d'avoir des mots collés
        elif balise.name == 'span' and balise.string:
            balise.string = ' ' + balise.string

    for balise in soup.find_all(attrs={'class': bad_classes}):
        balise.decompose()

    for balise in soup.find_all(attrs={'id': bad_classes}):
        balise.decompose()

    for balise in soup.find_all():
        if balise.text == '': balise.extract()

    return metadata, str(soup)


def convert_html_to_txt(src_file_path):
    """
        Conversion à l'aide de html2text.
        Détection automatique de l'encodage (UnicodeDammit).
        On capture la sortie texte.
        @type  src_file_path: String.
        @param src_file_path: Chemin du fichier source.
        @rtype: String.
        @return: Texte brut.
    """
    html_file = open(src_file_path, 'rb').read()
    dammit = UnicodeDammit(html_file) # src_file_path
#     metadata, html_mini = less_html(html_file.decode(dammit.original_encoding))
    metadata, html_mini = less_html(html_file.decode(dammit.original_encoding))
    handler = html2text.HTML2Text()
    handler.ignore_links = True
    handler.ignore_emphasis = True
    text = handler.handle(html_mini)

    return metadata, text


# extract spatial named entities
def SNE_Extract(title_mtd):
    SNE = {}
    dc = params.nlp_model(title_mtd)
    i = 0
    for ent in dc.ents:
        if ent.label_ in ['LOC']:
            SNE['ent'+repr(i)] = repr(ent)
            i+=1
    return SNE


# ajout de meta données suplementaires pour l'intdexation spatiale et temporelle
def enrich_mtd(mtd):
    if 'title' in mtd:
        title_mtd = mtd['title']
        SNE = SNE_Extract(title_mtd)
        mtd['SNE'] = SNE #liste d'ENS

    mtd['TNE'] = {}
    #if 'post_date' in mtd and '$date' in mtd['post_date']:
    #    mtd['TNE']['date'] = mtd['post_date']['$date']
    if "post_date" in mtd:
        mtd['TNE']['date'] = []
        mtd['TNE']['date'] = mtd['post_date']
    #mtd = TNE_extract(mtd)
    return mtd


def sauvegarde_fichier_advanced(ville, url, logger, tc):
    """
		Enregistre un fichier quelqu'il soit.

		@type  ville: String.
		@param ville: Nom de la ville.

		@type  url: String.
		@param url: URL vers le fichier pdf.

		@type  log: Logger.
		@param log: Fichier de log.

		@type  tc: TextCleaner.
		@param tc: Nettoyeur de texte.
	"""
    # On prend l'URL de base pour désigner l'origine du fichier à laquelle on enlève le "www."
    origine = re.sub(r'^www\.', '', urllib.request.urlparse(url).netloc)

    url_split = url.split('/')

    # Extraction du nom du document
    if url_split[-1] == '':
        my_doc = norm_string(url_split[-2])
    else:
        my_doc = norm_string(url_split[-1])

    src_file_path = "{0}{1}/Documents_SRC/[{2}]{3}".format(params.CHEMIN_RESULTATS, ville, origine, my_doc)

#     print(">>>>>>>", url)
#     print("#####", src_file_path)

    if not os.path.isfile(src_file_path):
        req = urllib.request.Request(url, headers={'User-Agent': "Magic Browser"})
        response = urllib.request.urlopen(req)
        read_buffer = response.read()
        mime_type = magic.from_buffer(read_buffer, mime=True)

        source = {
            'file_link': src_file_path,
            'complete_url': url,
            'base_url': origine,
            'open_access': False,
        }

        document = {
            'name': my_doc,
            'mime_type': mime_type,
            'source': source,
            'manually_validated': False,
        }

        # Écriture du fichier téléchargé
        with open(src_file_path, "wb") as fichier:
            fichier.write(read_buffer)
            logger.info("Document sauvegardé.")

        # On détecte le type du document source pour utiliser la conversion adaptée
        # Si le document est un PDF
        if mime_type == 'application/pdf':
            try:
                # Conversion en texte brut
                raw_text = convert_pdf_to_txt(src_file_path)
                logger.info("Document PDF converti en texte brut.")
                title, p_d = get_pdf_info(src_file_path,logger)
                document['text'] = tc.clean(raw_text)
                document['title'] = title
                document['post_date'] = p_d
                logger.info("Texte nettoyé.\n")
                #print("title, p_d :", title, p_d)
            except:
                logger.exception("Erreur lors de la conversion en texte du pdf.\n")

        # Si le document est un HTML (ou autre fichier web)
        elif mime_type == 'text/html':
            try:
                # Conversion en texte brut
                metadata, raw_text = convert_html_to_txt(src_file_path)
                logger.info("Document web converti en texte brut.")
                document['text'] = tc.clean(raw_text)
                document.update(metadata)
                logger.info("Texte nettoyé.\n")

            except:
                logger.exception("Erreur lors de la conversion en texte de la page web.\n")

        else:
            logger.info("Autre type de document téléchargé.\n")

        document = enrich_mtd(document)

        return document

    else:
        logger.info("Le document existe déjà.\n")
        return None


### save database
def save_to_jsonl(mtd,spatial_extent):
#     with open('3m_db.jsonl', 'a+', encoding='utf8') as outfile:
    with open("{0}{1}/urbanisation_herelle.jsonl".format(params.CHEMIN_RESULTATS, spatial_extent), 'a+', encoding='utf8') as outfile:
        #for entry in JSON_file:
        json.dump(mtd, outfile, ensure_ascii=False)
        outfile.write('\n')


def pause(logger, minutes=0.5):
    """
		Effectue une pause.
		@type  log: Logger.
		@param log: Fichier de log.
		@type  minutes: Entier.
		@param minutes: Temps en minute à attendre.
	"""
    date = datetime.now().strftime('%d-%m-%Y:%Hh%M')
    current_time = datetime.now() + timedelta(minutes=minutes)

    logger.info("{0} : Nombre limite de requete atteint. Reprise du programme : {1}".format(date, current_time.strftime(
        '%d-%m-%Y:%Hh%M')))

    while datetime.now() < current_time:
        time.sleep(0.5)


### save database
def db_to_jsonl(mtd, thematic):
    head, tail = os.path.split(thematic)
    #print("tail :", tail)
    #     head,tail.split('.')[0]
    thematic = tail.split('.')[0]# keyword_file
    with open("./documents/" + str(thematic)+"_db.jsonl", 'a+', encoding='utf8') as outfile:
    #with open("{0}{1}/"+thematic+".jsonl".format(params.CHEMIN_RESULTATS, spatial_extent), 'a', encoding='utf8') as outfile:
        #for entry in JSON_file:
        json.dump(mtd, outfile, ensure_ascii=False)
        outfile.write('\n')


def get_doc(spatial_extent,voc_concept,motscles,thematic, logger, site):
    print("starting doc collector...")
    """
		Effecue la recherche.

		@type  ville: String.
		@param ville: Nom de la ville.

		@type  motscles: Liste de string.
		@param motscles: Liste des mots clés à rechercher.

		@type  logger: Logger.
		@param logger: Fichier de log.
	"""

    # Initialisation du nettoyeur de texte
    tc = TextCleaner()

    # Génération de la liste des requêtes
    queries_list = query_generator(format_word(spatial_extent), motscles, logger, site)
    #print('>>#', liste_requetes)
    for requete in queries_list:
        #print('###', requete)
        response = search(requete, lang='fr', stop=10) # stop=10
        # response = bing_search.search(requete)  # stop=10
        try:
            #liste_url = list(response)
            liste_url = set(response)
        except:
            liste_url = []
#         resume = 'resume'
        with (open("{0}{1}/resume.txt".format(params.CHEMIN_RESULTATS, spatial_extent), "a")) as res:
            logger.info("Nouvelle requête : {0}\n".format(requete))
            res.write("Requête : {0}\n".format(requete))
            res.write("Nombre de résultats affichés : {0}\n".format(len(liste_url)))
            res.write("\nListe des résultats\n")
            res.write("\n")
            for url in liste_url:
                if not url.endswith('xml.gz'):
                    logger.info("URL : {0}\n".format(url))
                    res.write("{0}\n".format(url))
                    try:
                        # On temporise chaque requête Google pour ne pas être bloqué
                        with sleep_time(30):
                            document = sauvegarde_fichier_advanced(spatial_extent, url, logger, tc)

                            # On s'assure que le document existe et qu'un texte y est associé
                            if document and 'text' in document:
                                #print("ok")
                                document = compute_best_doc(voc_concept, document)
                                document['source']['type'] = 'web_request'
                                document['source']['raw_request'] = requete
                                document['spatial_extent'] = spatial_extent
                                document['thematic'] = thematic
                                #print("thematic :", thematic)
                                # insert the doc into the Jsonl file
                                db_to_jsonl(document, thematic)
                                logger.info("Document inséré dans l'inventaire.\n")
                    except Exception as e:
                        print(e)
                        logger.info("Erreur pour l'URL : {0}\n".format(url))
                        res.write("Erreur pour l'URL : {0}\n".format(url))
            logger.info("***********************************************************************\n")
            res.write("***********************************************************************\n\n")
        with open("{0}{1}/.sauvegarde.txt".format(params.CHEMIN_RESULTATS, spatial_extent), "a") as f:
            f.write("{0}\n".format(requete))

        pause(logger)

def creation_dossier_resultat(chemin_resultats, ville, log, keyword_file) :
    """
        Création des dossiers de stockage et renvoi des mots clés.

        @type  ville: String.
        @param ville: Nom de la ville.

        @rtype: Liste de string.
        @return: Liste des mots clés à rechercher.
    """
    head, tail = os.path.split(keyword_file)
#     head,tail.split('.')[0]
    thematic = tail.split('.')[0]# keyword_file
    if not os.path.exists(chemin_resultats + ville):
        os.makedirs(chemin_resultats + ville)
        log.info("Création des dossier pour {0}".format(ville))
    if not os.path.exists("{0}{1}/Documents_SRC".format(chemin_resultats, ville)):
        os.makedirs("{0}{1}/Documents_SRC".format(chemin_resultats, ville))
        log.info("Création du dossier Documents_SRC\n")

    with open(keyword_file) as keywords_file:
        words = keywords_file.readlines()
        log.info("Lecture de keywords.txt ... \n")
    open("{0}{1}/.sauvegarde.txt".format(chemin_resultats, ville),"a").close()
    for i in range(0, len(words)):
        words[i] = format_word(words[i])
    return words, thematic


def scrapper(spatial_extent,voc_concept, site=''):
    logger = Log(params.CHEMIN_LOG, 'collecteDeDonnees_{0}'.format(datetime.today().strftime("%d-%m-%y")))
    spatial_extent = spatial_extent.title()
    motscles, thematic = creation_dossier_resultat(params.CHEMIN_RESULTATS, spatial_extent, logger, voc_concept)
    logger.info("Début de la recherche de document concernant la ville de {0}".format(spatial_extent))
    get_doc(spatial_extent,voc_concept, motscles,thematic, logger, site)
