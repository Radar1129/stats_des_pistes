#!/usr/bin/env python3
import json
import ssl
import sys
import time
import requests
import websocket
from urllib.parse import quote

BASE_URL = "https://trajectoires.bordeaux.aeroport.fr"
# Chemin standard de négociation pour l'ancien SignalR
NEGOTIATE_URL = f"{BASE_URL}/signalr/negotiate"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/appmap",
}

def main():
    session = requests.Session()
    
    # 1. Négociation en GET avec les paramètres requis par SignalR 1.5
    params = {
        "clientProtocol": "1.5",
        "connectionData": json.dumps([{"name": "flight"}])
    }
    
    print(f"[*] Négociation classique → {NEGOTIATE_URL}")
    try:
        resp = session.get(NEGOTIATE_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        nego_data = resp.json()
        print(f"[+] Connexion Token obtenue.")
    except Exception as e:
        print(f"[!] Échec de la négociation : {e}")
        if 'resp' in locals():
            print(f"Contenu reçu : {resp.text[:200]}")
        sys.exit(1)

    token = nego_data.get("ConnectionToken")
    if not token:
        print("[!] Aucun ConnectionToken trouvé dans la réponse.")
        sys.exit(1)

    # 2. Construction de l'URL de connexion WebSocket SignalR 1.5
    ws_base = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = (
        f"{ws_base}/signalr/connect"
        f"?transport=webSockets"
        f"&clientProtocol=1.5"
        f"&connectionToken={quote(token)}"
        f"&connectionData={quote(json.dumps([{'name': 'flight'}]))}"
    )

    print(f"[*] Connexion WebSocket → {ws_url}")

    def on_open(ws):
        print("[+] Connecté au flux Aérovision ! Écoute des paquets...")

    def on_message(ws, message):
        try:
            payload = json.loads(message)
            # L'ancien SignalR encapsule les données dans l'attribut 'M' (Messages)
            if "M" in payload:
                for msg in payload["M"]:
                    if msg.get("M") in ["addPlot", "addOrUpdateFlight"]:
                        for arg in msg.get("A", []): # 'A' contient les arguments
                            print(f"  ✈  Vol détecté : {arg.get('flightId', '?')[:8]} | Alt: {arg.get('zToDisplay', '?')} | Vitesse: {arg.get('speedToDisplay', '?')}")
        except Exception:
            pass

    def on_error(ws, error):
        print(f"[!] Erreur : {error}")

    def on_close(ws, status_code, msg):
        print(f"[-] Flux arrêté ({status_code})")

    ws_headers = [f"{k}: {v}" for k, v in HEADERS.items()]
    cookie_header = "; ".join(f"{c.name}={c.value}" for c in session.cookies)
    if cookie_header:
        ws_headers.append(f"Cookie: {cookie_header}")

    ws = websocket.WebSocketApp(
        ws_url,
        header=ws_headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

if __name__ == "__main__":
    main()
