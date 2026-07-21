import requests, json
from bs4 import BeautifulSoup
from datetime import datetime

def update_flights():
    date_aujourdhui = datetime.now().strftime("%d/%m/%Y")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }

    scraped_data = []

    # 1. Scraping Arrivées
    try:
        url_in = f"https://www.bordeaux.aeroport.fr/ajax/flights?w=in&date={date_aujourdhui}&time=00:00&_wrapper_format=drupal_ajax"
        res_in = requests.post(url_in, headers=headers, timeout=10)
        if res_in.status_code == 200:
            for cmd in res_in.json():
                if cmd.get("command") == "insert" and "data" in cmd:
                    soup = BeautifulSoup(cmd["data"], "html.parser")
                    for row in soup.find_all("tr"):
                        tds = row.find_all("td")
                        if len(tds) >= 4:
                            scraped_data.append({
                                "type": "Arrivée",
                                "heure": tds[0].get_text(strip=True),
                                "ville": tds[1].get_text(" / ", strip=True),
                                "vol": tds[2].get_text(" / ", strip=True),
                                "compagnie": tds[3].get_text(" / ", strip=True),
                                "statut": tds[5].get_text(strip=True) if len(tds) >= 6 else "Programmé"
                            })
                    break
    except Exception as e:
        print("Erreur Arrivées:", e)

    # 2. Scraping Départs
    try:
        url_out = f"https://www.bordeaux.aeroport.fr/ajax/flights?w=out&date={date_aujourdhui}&time=00:00&_wrapper_format=drupal_ajax"
        res_out = requests.post(url_out, headers=headers, timeout=10)
        if res_out.status_code == 200:
            for cmd in res_out.json():
                if cmd.get("command") == "insert" and "data" in cmd:
                    soup = BeautifulSoup(cmd["data"], "html.parser")
                    for row in soup.find_all("tr"):
                        tds = row.find_all("td")
                        if len(tds) >= 4:
                            scraped_data.append({
                                "type": "Départ",
                                "heure": tds[0].get_text(strip=True),
                                "ville": tds[1].get_text(" / ", strip=True),
                                "vol": tds[2].get_text(" / ", strip=True),
                                "compagnie": tds[3].get_text(" / ", strip=True),
                                "statut": tds[5].get_text(strip=True) if len(tds) >= 6 else "Programmé"
                            })
                    break
    except Exception as e:
        print("Erreur Départs:", e)

    scraped_data.sort(key=lambda x: x["heure"])

    if scraped_data:
        cache_file = "/home/ubuntu/stats_des_pistes/backend/scraped_cache.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(scraped_data, f, ensure_ascii=False, indent=2)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] OK: {len(scraped_data)} vols réactualisés.")

if __name__ == "__main__":
    update_flights()
