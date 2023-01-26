from src.collector import scrapper

vcUrb = "./terms/urbanisme.txt"
vcRisq = "./terms/risque.txt"
spatial_extent = 'Montpellier'


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print("scrapping...")
    scrapper(spatial_extent, vcRisq)

