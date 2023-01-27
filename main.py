from src.collector import scrapper

vcUrb = "./terms/urbanisme.txt"
vcRisq = "./terms/risque.txt"
spatial_extent = 'Montpellier'


# start scrapping
if __name__ == '__main__':
    print("scrapping...")
    scrapper(spatial_extent, vcRisq)

