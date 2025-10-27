import os
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import json

# CONFIGURAZIONE
# Prende il BOT_TOKEN dalle variabili d'ambiente (per Replit) o dal codice
BOT_TOKEN = os.environ.get('BOT_TOKEN')  # Set in Replit Secrets!
AUTHORIZED_GROUP_IDS = [-1003146204155, -1002492402815]  # Lista di chat autorizzati
TEMP_DIR = "temp_files"
COOKIES_FILE = "terabox_cookies.json"

# TERABOX LOGIN (solo per test!)
TERABOX_EMAIL = "jinnegru2@protonmail.com"
TERABOX_PASSWORD = "Limone189!"

# Keep-alive per UptimeRobot
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=5000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Funzioni bot
def is_authorized_chat(chat_id):
    """Verifica se il chat è autorizzato"""
    return chat_id in AUTHORIZED_GROUP_IDS

def load_cookies():
    """Carica i cookie salvati"""
    try:
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_cookies(cookies):
    """Salva i cookie"""
    try:
        with open(COOKIES_FILE, 'w') as f:
            json.dump(cookies, f, indent=2)
    except:
        pass

def get_session_with_cookies():
    """Crea una sessione con i cookie salvati"""
    session = requests.Session()
    cookies = load_cookies()
    
    print(f"[DEBUG] Caricamento cookie: {len(cookies)} cookie totali")
    
    # Imposta i cookie nella sessione con dominio corretto
    for cookie_name, cookie_value in cookies.items():
        # Usa .terabox.com come dominio principale
        session.cookies.set(cookie_name, cookie_value, domain='.terabox.com')
        session.cookies.set(cookie_name, cookie_value, domain='.1024tera.com')
        session.cookies.set(cookie_name, cookie_value, domain='1024tera.com')
        print(f"[DEBUG] Cookie impostato: {cookie_name}")
    
    # Headers per sembrare un browser reale autenticato
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.terabox.com/',
        'Origin': 'https://www.terabox.com',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'X-Requested-With': 'XMLHttpRequest',
    })
    
    return session

def do_terabox_login(email, password):
    """
    Fa login su Terabox e ottiene i cookie aggiornati
    WARNING: Richiede Chrome/Selenium - NON funziona su Replit base!
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        import time
        
        print(f"[DEBUG] 🔐 Tentativo login Terabox con {email}")
        
        options = Options()
        options.add_argument('--headless')  # Esegui in background
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        
        # Vai su Terabox
        driver.get("https://www.terabox.com")
        time.sleep(2)
        
        # Click login
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Log in"))
        )
        login_btn.click()
        time.sleep(2)
        
        # Email
        email_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        email_input.send_keys(email)
        time.sleep(1)
        
        # Password
        password_input = driver.find_element(By.NAME, "password")
        password_input.send_keys(password)
        time.sleep(1)
        
        # Submit
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()
        time.sleep(5)
        
        # Prendi i cookie
        cookies = driver.get_cookies()
        cookie_dict = {}
        for cookie in cookies:
            cookie_dict[cookie['name']] = cookie['value']
        
        # Salva
        save_cookies(cookie_dict)
        
        driver.quit()
        
        print(f"[DEBUG] ✅ Login riuscito! {len(cookie_dict)} cookie salvati")
        return cookie_dict
        
    except Exception as e:
        print(f"[DEBUG] ❌ Login fallito: {str(e)}")
        return None

def get_terabox_files():
    try:
        with open("terabox_links.txt", "r") as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def get_local_files():
    """Ottieni file dalla cartella locale per il fallback"""
    try:
        if os.path.exists("local_files"):
            files = []
            for filename in os.listdir("local_files"):
                if os.path.isfile(os.path.join("local_files", filename)):
                    files.append(os.path.join("local_files", filename))
            return files
    except:
        pass
    return []

def download_from_pixeldrain(pixeldrain_url):
    """
    Scarica file da Pixeldrain (API diretta)
    """
    try:
        print(f"[DEBUG] Download da Pixeldrain: {pixeldrain_url}")
        
        # Estrai ID dal link
        import re
        import time
        # Link formato: https://pixeldrain.com/u/FILE_ID
        id_match = re.search(r'pixeldrain\.com/u/([A-Za-z0-9_-]+)', pixeldrain_url)
        if not id_match:
            print(f"[DEBUG] Non riesco a estrarre ID da URL Pixeldrain")
            return None, None
        
        file_id = id_match.group(1)
        
        # Aggiungi delay per evitare rate limit
        time.sleep(1)
        
        # API diretta di Pixeldrain con headers per evitare 403
        api_url = f"https://pixeldrain.com/api/file/{file_id}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://pixeldrain.com/',
            'Origin': 'https://pixeldrain.com',
        }
        
        print(f"[DEBUG] Download via API: {api_url}")
        
        response = requests.get(api_url, timeout=30, allow_redirects=True, headers=headers)
        
        if response.status_code == 200:
            # Estrai filename
            content_disposition = response.headers.get('content-disposition', '')
            filename = f"pixeldrain_{file_id}.txt"
            
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"')
            
            print(f"[DEBUG] ✅ Download Pixeldrain riuscito: {filename}")
            return response.content, filename
        else:
            print(f"[DEBUG] Errore download: {response.status_code}")
        
        return None, None
        
    except Exception as e:
        print(f"[DEBUG] Errore download Pixeldrain: {str(e)}")
        return None, None

def download_from_gofile(gofile_url):
    """
    Scarica file da GoFile (API)
    """
    try:
        print(f"[DEBUG] Download da GoFile: {gofile_url}")
        
        # GoFile richiede un token
        import re
        
        # Estrai content ID dall'URL
        # https://gofile.io/d/CONTENT_ID
        id_match = re.search(r'gofile\.io/d/([A-Za-z0-9_-]+)', gofile_url)
        if not id_match:
            print(f"[DEBUG] Non riesco a estrarre ID da URL GoFile")
            return None, None
        
        content_id = id_match.group(1)
        
        # Prima ottieni un token
        token_response = requests.get('https://api.gofile.io/createAccount', timeout=15)
        if token_response.status_code == 200:
            data = token_response.json()
            if data.get('status') == 'ok':
                token = data['data']['token']
                
                # Ottieni info file
                info_url = f"https://api.gofile.io/getContent?contentId={content_id}&token={token}"
                info_response = requests.get(info_url, timeout=15)
                
                if info_response.status_code == 200:
                    info_data = info_response.json()
                    if info_data.get('status') == 'ok':
                        # Estrai link di download
                        contents = info_data['data']['contents']
                        
                        # Prendi il primo file
                        for file_id, file_info in contents.items():
                            download_link = file_info.get('directLink') or file_info.get('link')
                            filename = file_info.get('name', 'gofile_download.txt')
                            
                            if download_link:
                                print(f"[DEBUG] Link download: {download_link}")
                                
                                # Scarica
                                file_response = requests.get(download_link, timeout=30)
                                if file_response.status_code == 200:
                                    print(f"[DEBUG] ✅ Download GoFile riuscito: {filename}")
                                    return file_response.content, filename
        
        return None, None
        
    except Exception as e:
        print(f"[DEBUG] Errore download GoFile: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

def download_from_anonfiles(anonfiles_url):
    """
    Scarica file da Anonfiles (link diretti)
    """
    try:
        print(f"[DEBUG] Download da Anonfiles: {anonfiles_url}")
        
        # Anonfiles: dalla pagina ottieni il link di download vero
        response = requests.get(anonfiles_url, timeout=30)
        
        if response.status_code == 200:
            html = response.text
            
            # Salva HTML per debug
            try:
                with open("debug_anonfiles.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"[DEBUG] HTML Anonfiles salvato in debug_anonfiles.html")
            except:
                pass
            
            # Cerca il link di download nella pagina con pattern multipli
            import re
            
            # Pattern 1: cerca button/link con "download"
            patterns = [
                r'href=["\']([^"\']*cdn[^"\']*)["\']',  # CDN links
                r'href=["\']([^"\']*download[^"\']*)["\']',  # Download links
                r'<a[^>]*class="[^"]*download[^"]*"[^>]*href="([^"]+)"',  # Download button
                r'window\.location\s*=\s*["\']([^"\']+)["\']',  # JavaScript redirect
            ]
            
            download_url = None
            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    download_url = match.group(1)
                    print(f"[DEBUG] Link trovato con pattern: {pattern[:30]}...")
                    break
            
            if download_url:
                if not download_url.startswith('http'):
                    # URL relativo
                    base_url = 'https://anonfile.co' if 'anonfile.co' in anonfiles_url else 'https://anonfiles.com'
                    download_url = base_url + download_url
                
                print(f"[DEBUG] Link download trovato: {download_url}")
                
                # Scarica il file
                file_response = requests.get(download_url, timeout=30, allow_redirects=True)
                
                if file_response.status_code == 200:
                    content_disposition = file_response.headers.get('content-disposition', '')
                    filename = "anonfiles_download.txt"
                    
                    if 'filename=' in content_disposition:
                        filename = content_disposition.split('filename=')[1].strip('"')
                    else:
                        # Estrai da URL
                        filename = anonfiles_url.split('/')[-1] or "anonfiles_download.txt"
                    
                    print(f"[DEBUG] ✅ Download Anonfiles riuscito: {filename}")
                    return file_response.content, filename
            else:
                print(f"[DEBUG] ❌ Nessun link di download trovato con nessun pattern")
                print(f"[DEBUG] Controlla debug_anonfiles.html per vedere il contenuto")
        
        return None, None
        
    except Exception as e:
        print(f"[DEBUG] Errore download Anonfiles: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

def get_terabox_files_from_folder(terabox_url):
    """Estrae tutti i link ai file da una cartella Terabox usando l'API"""
    import re
    import json
    from urllib.parse import urlparse, parse_qs
    
    print(f"[DEBUG] Tentativo di estrazione file da Terabox...")
    
    session = get_session_with_cookies()
    
    try:
        # Prima ottieni la pagina per estrarre parametri necessari
        response = session.get(terabox_url, timeout=15, allow_redirects=True)
        html_content = response.text
        
        print(f"[DEBUG] Ricevuto HTML ({len(html_content)} caratteri)")
        
        # Estrai shorturl e surl dalla URL
        # Formato tipico: https://1024terabox.com/s/1AOnZVft-P1OPC6RU5cBMoQ
        shorturl_match = re.search(r'/s/([A-Za-z0-9_-]+)', terabox_url)
        if not shorturl_match:
            print("[DEBUG] Non riesco a estrarre shorturl dall'URL")
            return None
        
        shorturl = shorturl_match.group(1)
        print(f"[DEBUG] Shorturl estratto: {shorturl}")
        
        # Prova diversi endpoint e metodi
        # Metodo 1: API standard con più parametri
        api_urls_to_try = [
            "https://www.terabox.com/share/list",
            "https://www.1024tera.com/share/list",
            "https://1024terabox.com/share/list"
        ]
        
        params = {
            'shorturl': shorturl,
            'root': '1',
            'page': '1',
            'num': '100',
            'order': 'name',
            'desc': '0',
            'web': '1',
            'channel': 'dubox',
            'app_id': '250528',
            'clienttype': '0',
            'jsToken': '',  # Può essere necessario
            'dp-logid': '',
        }
        
        # Aggiungi CSRF token se disponibile
        cookies = load_cookies()
        if 'csrfToken' in cookies:
            params['csrfToken'] = cookies['csrfToken']
        
        headers = session.headers.copy()
        headers.update({
            'Referer': terabox_url,
            'Origin': terabox_url.split('/s/')[0] if '/s/' in terabox_url else 'https://www.terabox.com',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })
        
        # Prova tutti gli endpoint disponibili
        data = None
        for api_url in api_urls_to_try:
            try:
                print(f"[DEBUG] Tentativo con: {api_url}")
                api_response = session.get(api_url, params=params, headers=headers, timeout=15)
                
                print(f"[DEBUG] Status Code: {api_response.status_code}")
                
                if api_response.status_code != 200:
                    continue
                    
                data = api_response.json()
                print(f"[DEBUG] Response errno: {data.get('errno')}")
                
                # Se otteniamo una risposta valida (errno 0 o anche con errore ma con dati)
                if data.get('errno') == 0:
                    print(f"[DEBUG] ✅ Endpoint funzionante: {api_url}")
                    break
                elif data.get('errno') == -9:
                    # Link scaduto o non valido
                    print(f"[DEBUG] Link non valido o scaduto")
                    continue
                else:
                    print(f"[DEBUG] Errore {data.get('errno')}: {data.get('errmsg')}")
                    # Continua a provare altri endpoint
                    continue
            except Exception as e:
                print(f"[DEBUG] Errore con {api_url}: {str(e)}")
                continue
        
        # Salva risposta API per debug se abbiamo ottenuto qualcosa
        if data:
            try:
                with open("debug_api_response.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"[DEBUG] Risposta API salvata in debug_api_response.json")
            except:
                pass
        
        # Processa i dati se errno == 0
        if data and data.get('errno') == 0 and 'list' in data:
            try:
                print(f"[DEBUG] API Response keys: {data.keys()}")
                
                if True:  # Blocco sempre eseguito se arriviamo qui
                    file_list = data['list']
                    print(f"[DEBUG] Trovati {len(file_list)} file dall'API")
                    
                    file_links = []
                    for file_item in file_list:
                        if file_item.get('isdir') == 0:  # Solo file, non cartelle
                            # Usa dlink se disponibile, altrimenti costruisci URL
                            dlink = file_item.get('dlink', '')
                            filename = file_item.get('server_filename', 'unknown')
                            fs_id = file_item.get('fs_id', '')
                            
                            print(f"[DEBUG] File: {filename}, fs_id: {fs_id}")
                            
                            if dlink:
                                file_links.append({
                                    'filename': filename,
                                    'dlink': dlink,
                                    'fs_id': fs_id
                                })
                    
                    print(f"[DEBUG] File con download link: {len(file_links)}")
                    
                    if file_links:
                        # Ritorna i dlink
                        return [f['dlink'] for f in file_links if f.get('dlink')]
                else:
                    print(f"[DEBUG] API Error: errno={data.get('errno')}, errmsg={data.get('errmsg', 'N/A')}")
                    
                    # Se serve verifica, prova a fare login
                    if data.get('errno') == 400141:  # need verify
                        print(f"[DEBUG] 🔐 Richiesta verifica, provo login automatico...")
                        new_cookies = do_terabox_login(TERABOX_EMAIL, TERABOX_PASSWORD)
                        if new_cookies:
                            print(f"[DEBUG] ✅ Nuovi cookie salvati, riprovo...")
                            # Ricarica sessione con nuovi cookie
                            session = get_session_with_cookies()
                            # Riprova la chiamata
                            api_response = session.get(api_url, params=params, headers=headers, timeout=15)
                            if api_response.status_code == 200:
                                data = api_response.json()
                                if data.get('errno') == 0 and 'list' in data:
                                    file_list = data['list']
                                    file_links = []
                                    for file_item in file_list:
                                        if file_item.get('isdir') == 0:
                                            dlink = file_item.get('dlink', '')
                                            if dlink:
                                                file_links.append({'dlink': dlink})
                                    if file_links:
                                        return [f['dlink'] for f in file_links if f.get('dlink')]
            except Exception as e:
                print(f"[DEBUG] Errore parsing JSON API: {str(e)}")
        
        # Fallback: parsing HTML - ESTRAZIONE FORZATA
        print(f"[DEBUG] Fallback: parsing HTML forzato...")
        file_info = []
        
        # Salva HTML
        try:
            with open("debug_terabox.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"[DEBUG] HTML salvato in debug_terabox.html")
        except:
            pass
        
        # Cerca TUTTI i pattern possibili per fs_id e filename
        fsid_matches = re.findall(r'"fs_id"\s*:\s*["\']?(\d+)', html_content)
        filename_matches = re.findall(r'"server_filename"\s*:\s*"([^"]+)"', html_content)
        
        print(f"[DEBUG] Pattern 1 - fs_id trovati: {len(fsid_matches)}, filename: {len(filename_matches)}")
        
        # Pattern alternativo
        fsid_pattern2 = re.findall(r'fs_id["\']?\s*:\s*["\']?(\d+)', html_content)
        filename_pattern2 = re.findall(r'server_filename["\']?\s*:\s*["\']?([^"\'\s]+)', html_content)
        
        print(f"[DEBUG] Pattern 2 - fs_id trovati: {len(fsid_pattern2)}, filename: {len(filename_pattern2)}")
        
        # Combina tutti
        all_fsids = list(set(fsid_matches + fsid_pattern2))
        all_filenames = list(set(filename_matches + filename_pattern2))
        
        print(f"[DEBUG] TOTALE fs_id: {len(all_fsids)}, TOTALE filename: {len(all_filenames)}")
        
        # Se abbiamo solo fs_id senza filename, usa numeri progressivi
        if all_fsids:
            for i, fsid in enumerate(all_fsids):
                filename = all_filenames[i] if i < len(all_filenames) else f"file_{i+1}.txt"
                file_info.append({
                    'filename': filename,
                    'fs_id': fsid
                })
        
        print(f"[DEBUG] Trovati {len(file_info)} file (fallback)")
        
        # Se abbiamo trovato file, genera un report di debug
        if file_info:
            print(f"[DEBUG] === REPORT DEBUG FILE ===")
            for i, f in enumerate(file_info[:10], 1):
                print(f"[DEBUG] File {i}: {f['filename']} (fs_id: {f['fs_id']})")
            if len(file_info) > 10:
                print(f"[DEBUG] ... e altri {len(file_info) - 10} file")
            print(f"[DEBUG] ============================")
            
            # Ritorna una lista di link per download
            # Usa un approccio alternativo: vedi debug_api_response.json
            return None
        else:
            print(f"[DEBUG] ❌ NESSUN FILE TROVATO - HTML salvato per analisi")
        
        # Ritorna None se non troviamo file - il bot tratterà il link come singolo file
        return None
        
    except Exception as e:
        print(f"[DEBUG] Errore nell'estrazione link: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_terabox_download_link(terabox_url):
    """Prova a scaricare un singolo file usando i cookie salvati"""
    
    # Controlla se è Pixeldrain
    if 'pixeldrain.com' in terabox_url:
        print(f"[DEBUG] Rilevato link Pixeldrain")
        return download_from_pixeldrain(terabox_url)
    
    # Controlla se è GoFile
    if 'gofile.io' in terabox_url:
        print(f"[DEBUG] Rilevato link GoFile")
        return download_from_gofile(terabox_url)
    
    # Controlla se è Anonfiles (anonfile.co o anonfiles.com)
    if 'anonfile' in terabox_url:
        print(f"[DEBUG] Rilevato link Anonfiles")
        return download_from_anonfiles(terabox_url)
    
    session = get_session_with_cookies()
    
    try:
        print(f"[DEBUG] get_terabox_download_link: {terabox_url}")
        
        # Se l'URL contiene /s/ è probabilmente una cartella condivisa
        if '/s/' in terabox_url:
            print(f"[DEBUG] URL rilevato come cartella condivisa")
            all_files = get_terabox_files_from_folder(terabox_url)
            if all_files and len(all_files) > 0:
                print(f"[DEBUG] Ritorno {len(all_files)} file dalla cartella")
                return all_files, "folder"
            else:
                print(f"[DEBUG] Nessun file estratto dalla cartella, provo come file singolo")
        
        # Prova a scaricare come file singolo
        response = session.get(terabox_url, timeout=15, allow_redirects=True)
        
        print(f"[DEBUG] Response status: {response.status_code}, content-type: {response.headers.get('content-type', 'N/A')}")
        
        # Se richiede ancora verifica, prova senza cookie
        if "need verify" in response.text or "errno" in response.text:
            print(f"[DEBUG] Richiesta verifica, riprovo senza cookie")
            response = requests.get(terabox_url, timeout=10, allow_redirects=True)
            
            if "need verify" in response.text or "errno" in response.text:
                print(f"[DEBUG] Ancora richiesta verifica, fallito")
                return None, None
        
        # Se il contenuto sembra essere un file (non HTML)
        if response.status_code == 200 and len(response.content) > 100:
            # Controlla se è HTML o un file reale
            content_type = response.headers.get('content-type', '').lower()
            
        # Controlla content-type per capire se è HTML o file
        if 'text/html' in content_type or 'application/json' in content_type:
            # Potrebbe essere una cartella o una pagina HTML
            print(f"[DEBUG] Ricevuto HTML/JSON, provo a estrarre file dalla cartella")
            
            # Prova prima a vedere se è una cartella
            all_files = get_terabox_files_from_folder(terabox_url)
            if all_files and len(all_files) > 0:
                print(f"[DEBUG] ✅ Cartella con {len(all_files)} file")
                return all_files, "folder"
            else:
                # Se non è una cartella, potrebbe essere la pagina di un file singolo
                # Prova a trovare il link di download nella pagina
                html_content = response.text
                import re
                
                # Cerca direct download link
                dlink_match = re.search(r'"dlink"\s*:\s*"([^"]+)"', html_content)
                if dlink_match:
                    dlink = dlink_match.group(1)
                    print(f"[DEBUG] Trovato download link diretto")
                    # Scarica dal dlink
                    file_response = session.get(dlink, timeout=30)
                    if file_response.status_code == 200:
                        filename = terabox_url.split('/')[-1] + '.txt'
                        return file_response.content, filename
                
                # Se non trova dlink, ritorna None
                print(f"[DEBUG] Nessun file trovato nella pagina")
                return None, None
        else:
            # È un file diretto (non HTML)
            filename = terabox_url.split('/')[-1] or "file.txt"
            
            # Estrai filename dal content-disposition o dall'URL
            content_disposition = response.headers.get('content-disposition', '')
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"')
            
            print(f"[DEBUG] ✅ File singolo scaricato: {filename}")
            return response.content, filename
            
    except Exception as e:
        print(f"[DEBUG] Errore in get_terabox_download_link: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_chat(update.message.chat_id):
        return
    await update.message.reply_text("👋 Usa /search <parola>")

async def files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_chat(update.message.chat_id):
        return
    
    local_files = get_local_files()
    terabox_links = get_terabox_files()
    cookies = load_cookies()
    
    # Conta i file in cache Terabox
    terabox_cache_count = 0
    terabox_cache_dir = "terabox_cache"
    if os.path.exists(terabox_cache_dir):
        terabox_cache_count = len([f for f in os.listdir(terabox_cache_dir) if os.path.isfile(os.path.join(terabox_cache_dir, f))])
    
    msg = f"📁 **File disponibili per la ricerca:**\n\n"
    msg += f"📄 **File locali:** {len(local_files)}\n"
    
    terabox_cached_files = []
    if os.path.exists(terabox_cache_dir):
        for filename in os.listdir(terabox_cache_dir)[:5]:  # Mostra solo i primi 5
            terabox_cached_files.append(filename)
    
    msg += f"💾 **Cache Terabox:** {terabox_cache_count} file scaricati\n"
    if terabox_cached_files:
        for filename in terabox_cached_files[:5]:
            msg += f"  • {filename}\n"
        if terabox_cache_count > 5:
            msg += f"  • ... e altri {terabox_cache_count - 5} file\n"
    
    msg += f"\n🔗 **Link Terabox configurati:** {len(terabox_links)}\n"
    for link in terabox_links[:3]:  # Mostra solo i primi 3
        msg += f"  • {link}\n"
    if len(terabox_links) > 3:
        msg += f"  • ... e altri {len(terabox_links) - 3} link\n"
    
    msg += f"\n🍪 **Cookie salvati:** {len(cookies)} cookie\n"
    if cookies:
        msg += f"  • {', '.join(list(cookies.keys())[:3])}{'...' if len(cookies) > 3 else ''}\n"
    
    msg += f"\n💡 **Comandi:**\n"
    msg += f"  • `/search <parola>` - Cerca nei file\n"
    msg += f"  • `/cookies` - Gestisci cookie Terabox\n"
    msg += f"  • `/clearcache` - Pulisci cache Terabox"
    
    await update.message.reply_text(msg)

async def cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_chat(update.message.chat_id):
        return
    
    cookies = load_cookies()
    
    # Cookie critici necessari per Terabox
    critical_cookies = ['browserid', 'ndus', 'ndut_fmt', 'csrfToken', 'TSID']
    
    if not cookies:
        msg = "🍪 **Nessun cookie salvato**\n\n"
        msg += "**Cookie CRITICI per Terabox:**\n"
        for c in critical_cookies:
            msg += f"  ❌ {c}\n"
        msg += "\n**Usa `/setallcookies` per impostarli rapidamente**\n"
        msg += "oppure `/setcookie nome=valore` uno per uno"
    else:
        msg = f"🍪 **Cookie salvati ({len(cookies)}):**\n\n"
        
        # Mostra stato cookie critici
        msg += "**Cookie CRITICI:**\n"
        for c in critical_cookies:
            if c in cookies:
                msg += f"  ✅ {c}: `{cookies[c][:15]}...`\n"
            else:
                msg += f"  ❌ {c}: MANCANTE\n"
        
        # Mostra altri cookie
        other_cookies = {k: v for k, v in cookies.items() if k not in critical_cookies}
        if other_cookies:
            msg += f"\n**Altri cookie ({len(other_cookies)}):**\n"
            for name, value in list(other_cookies.items())[:3]:
                msg += f"  • {name}: `{value[:15]}...`\n"
            if len(other_cookies) > 3:
                msg += f"  ... e altri {len(other_cookies) - 3}\n"
        
        msg += f"\n**Comandi:**\n"
        msg += f"  • `/setcookie nome=valore` - Aggiungi cookie\n"
        msg += f"  • `/setallcookies` - Imposta cookie predefiniti\n"
        msg += f"  • `/clearcookies` - Cancella tutti"
    
    await update.message.reply_text(msg)

async def setcookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_chat(update.message.chat_id):
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usa: /setcookie nome=valore")
        return
    
    cookie_str = " ".join(context.args)
    if "=" not in cookie_str:
        await update.message.reply_text("❌ Formato: /setcookie nome=valore")
        return
    
    name, value = cookie_str.split("=", 1)
    cookies = load_cookies()
    cookies[name.strip()] = value.strip()
    save_cookies(cookies)
    
    await update.message.reply_text(f"✅ Cookie '{name}' salvato!")

async def setallcookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Imposta tutti i cookie Terabox necessari in un colpo solo"""
    if not is_authorized_chat(update.message.chat_id):
        return
    
    # Cookie completi estratti da Terabox - ULTIMI AGGIORNATI
    default_cookies = {
        # Cookie CRITICI (aggiornati)
        "browserid": "BercL1o9teav2tv89GY31rjJxyuibPAl_C_FCZiWnYq3S3XD31GVqSAtIJwrC9BYHGaoHbj1ITnt4mGf",
        "ndus": "YzTsFiYteHuiL78_XvM5MPNdSDFIrRenRArPxLZj",
        "ndut_fmt": "C8C83D52F7C2D9925D9E795175F3D9E1DF52FFFFF4CF05AFB93C1543CA8A8746",
        "csrfToken": "GjVXwWujKLEqXnCjySbeC2kG",
        "TSID": "oN0osQxY8D5kCiELq5mszwIvXQtGTsax",
        # Stripe cookies
        "__stripe_mid": "3c81dae7-1d76-475b-82c8-d2996f02b0a922c8bd",
        "__stripe_sid": "91fab44c-2fcd-4559-8c83-2ffb596248651aa536",
        # Altri
        "lang": "en",
        "g_state": '{"i_l":0,"i_ll":1761546810191,"i_b":"rkyOXorl6hFZFuI5iIt7Q/46NIPhci4nenQlizV69/I"}',
        "NID": "526=rCtTdiZV27LOAappUttRE56J5cbV8cWXUlzd8rIfpuOxI86_q-lSYJ_0-NrkGXLzNk63SZFREY-N94fnX9VpFmoOs4SUtlTj3rASYzTduYT3Q-nU6-fBSGRKhMRnMWPoj7nTyeAWAPK8gV9IDBhpF7-VrhgTCbwO6Un8_6O7JDAiyRooWObBOE5mU-SMloE"
    }
    
    save_cookies(default_cookies)
    
    msg = f"✅ Cookie Terabox impostati! ({len(default_cookies)} cookie)\n\n"
    msg += "**IMPORTANTE per evitare ban:**\n"
    msg += "• Usa account Terabox dedicati (non il tuo principale)\n"
    msg += "• Non fare troppe richieste consecutive\n"
    msg += "• Aggiorna i cookie ogni 1-2 settimane\n\n"
    msg += "**Come ottenere cookie aggiornati:**\n"
    msg += "1. Vai su www.terabox.com\n"
    msg += "2. Fai login con l'account\n"
    msg += "3. Premi F12 > Application > Cookies\n"
    msg += "4. Copia i cookie con /setcookie\n\n"
    msg += "Cookie importanti: ndus, browserid, csrfToken"
    
    await update.message.reply_text(msg)

async def clearcookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_chat(update.message.chat_id):
        return
    
    save_cookies({})
    await update.message.reply_text("✅ Tutti i cookie cancellati!")

async def clearcache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_chat(update.message.chat_id):
        return
    
    terabox_cache_dir = "terabox_cache"
    count = 0
    if os.path.exists(terabox_cache_dir):
        for filename in os.listdir(terabox_cache_dir):
            try:
                os.remove(os.path.join(terabox_cache_dir, filename))
                count += 1
            except:
                pass
    
    await update.message.reply_text(f"✅ Cache Terabox pulita! ({count} file rimossi)")

async def redownload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forza il re-download di tutti i file da Terabox"""
    if not is_authorized_chat(update.message.chat_id):
        return
    
    await update.message.reply_text("🔄 Re-download in corso... (usa /search per avviare)")
    
    # Pulisci la cache
    terabox_cache_dir = "terabox_cache"
    if os.path.exists(terabox_cache_dir):
        for filename in os.listdir(terabox_cache_dir):
            try:
                os.remove(os.path.join(terabox_cache_dir, filename))
            except:
                pass
    
    await update.message.reply_text("✅ Cache pulita! Ora usa /search per scaricare di nuovo")

async def testapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test diretto dell'API Terabox"""
    if not is_authorized_chat(update.message.chat_id):
        return
    
    await update.message.reply_text("🔍 Testando API Terabox...")
    
    terabox_links = get_terabox_files()
    if not terabox_links:
        await update.message.reply_text("❌ Nessun link Terabox configurato")
        return
    
    link = terabox_links[0]
    await update.message.reply_text(f"📡 Chiamata API per: {link}")
    
    # Chiama la funzione e cattura i log
    files = get_terabox_files_from_folder(link)
    
    if files:
        msg = f"✅ Trovati {len(files)} file:\n\n"
        for i, file_url in enumerate(files[:10], 1):
            msg += f"{i}. {file_url[:50]}...\n"
        if len(files) > 10:
            msg += f"\n... e altri {len(files) - 10} file"
    else:
        msg = "❌ **PROBLEMA: Terabox richiede verifica**\n\n"
        msg += "**Errore:** errno=400141 (need verify)\n\n"
        msg += "**Causa:** I cookie non sono sufficienti.\n"
        msg += "Terabox richiede una sessione di login attiva.\n\n"
        msg += "**SOLUZIONI:**\n\n"
        msg += "1️⃣ **Metodo consigliato:**\n"
        msg += "   • Fai login su www.terabox.com nel browser\n"
        msg += "   • Dopo il login, copia TUTTI i cookie\n"
        msg += "   • Cookie critici: SBOX_USER_ID, ndus, ndut_fmt\n"
        msg += "   • Usa /setcookie per ognuno\n\n"
        msg += "2️⃣ **Alternativa:**\n"
        msg += "   • Carica i file nella cartella local_files/\n"
        msg += "   • Evita problemi di autenticazione\n\n"
        msg += "3️⃣ **Link singoli:**\n"
        msg += "   • Invece di link cartella\n"
        msg += "   • Un link per ogni file"
    
    await update.message.reply_text(msg)

async def chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_chat(update.message.chat_id):
        return
    
    msg = f"💬 **Chat autorizzati ({len(AUTHORIZED_GROUP_IDS)}):**\n\n"
    for i, chat_id in enumerate(AUTHORIZED_GROUP_IDS, 1):
        msg += f"  {i}. `{chat_id}`\n"
    
    msg += f"\n**Chat corrente:** `{update.message.chat_id}`\n"
    msg += f"**Autorizzato:** {'✅ Sì' if is_authorized_chat(update.message.chat_id) else '❌ No'}"
    
    await update.message.reply_text(msg)

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_chat(update.message.chat_id):
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usa: /search <parola>")
        return

    parola = " ".join(context.args).lower()
    
    # Pulisci la parola per usarla come nome file (rimuovi caratteri non validi)
    safe_parola = "".join(c for c in parola if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_parola = safe_parola.replace(' ', '_')
    
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    file_links = get_terabox_files()
    local_files = get_local_files()
    
    if not file_links and not local_files:
        await update.message.reply_text("❌ Nessun file trovato")
        return

    risultati = []
    all_results_content = []
    
    # FASE 1: Scarica e salva tutti i file da Terabox nella cartella locale se non già presenti
    terabox_cache_dir = "terabox_cache"
    if not os.path.exists(terabox_cache_dir):
        os.makedirs(terabox_cache_dir)
    
    print(f"[DEBUG] Scaricando file da servizi cloud...")
    
    # Messaggio di progresso
    progress_msg = await update.message.reply_text(f"⏳ Download: 0/{len(file_links)} (0%)")
    
    # Download parallelo per velocità
    import concurrent.futures
    
    def download_single_file(link):
        """Scarica un singolo file (usato per parallelizzazione)"""
        try:
            cache_filename = link.split('/')[-1]
            cache_file_path = os.path.join(terabox_cache_dir, f"{cache_filename}.txt")
            
            # Se già in cache, salta
            if os.path.exists(cache_file_path):
                print(f"[DEBUG] ✓ Cache: {cache_filename}")
                return True
            
            # Scarica
            print(f"[DEBUG] ⬇ Scarico: {cache_filename}")
            file_content, file_name = get_terabox_download_link(link)
            
            if file_content and file_name != "folder":
                with open(cache_file_path, "wb") as f:
                    f.write(file_content)
                print(f"[DEBUG] ✅ Salvato: {cache_filename}")
                return True
            
            return False
        except Exception as e:
            print(f"[DEBUG] ❌ Errore: {str(e)}")
            return False
    
    # Download parallelo (max 3 alla volta per evitare rate limit)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(download_single_file, link) for link in file_links]
        
        # Attendi completamento con aggiornamenti progresso
        downloaded = 0
        total = len(file_links)
        
        for future in concurrent.futures.as_completed(futures):
            if future.result():
                downloaded += 1
            
            # Calcola percentuale
            percentage = int((downloaded / total) * 100)
            
            # Aggiorna messaggio ogni 5 file o ogni 10%
            if downloaded % 5 == 0 or percentage % 10 == 0:
                progress_bar = "█" * (percentage // 10) + "░" * (10 - percentage // 10)
                try:
                    await progress_msg.edit_text(
                        f"⏳ Download: {downloaded}/{total} ({percentage}%)\n"
                        f"[{progress_bar}]"
                    )
                except:
                    pass  # Ignora errori se messaggio non modificabile
    
    # Messaggio finale
    final_percentage = int((downloaded / total) * 100)
    await progress_msg.edit_text(
        f"✅ Download completato: {downloaded}/{total} ({final_percentage}%)\n"
        f"🔍 Ora cerco nei file..."
    )
    
    print(f"[DEBUG] Download completato. File in cache: {len(os.listdir(terabox_cache_dir))}")
    
    # FASE 2: Ora controlla TUTTI i file (locali + cache Terabox)
    # Aggiungi i file della cache alla lista dei file locali
    if os.path.exists(terabox_cache_dir):
        for filename in os.listdir(terabox_cache_dir):
            cached_file_path = os.path.join(terabox_cache_dir, filename)
            if os.path.isfile(cached_file_path) and cached_file_path not in local_files:
                local_files.append(cached_file_path)
    
    print(f"[DEBUG] Totale file da controllare: {len(local_files)}")
    
    # Prima controlla i file locali (inclusi quelli in cache Terabox)
    for file_path in local_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                contenuto = f.read().lower()
                
                if parola in contenuto:
                    risultati.append(os.path.basename(file_path))
                    
                    # Trova tutte le righe che contengono la parola
                    f.seek(0)
                    lines = f.read().split('\n')
                    matching_lines = []
                    for i, line in enumerate(lines, 1):
                        if parola in line.lower():
                            matching_lines.append(f"Riga {i}: {line.strip()}")
                    
                    # Salva i risultati - SOLO il contenuto trovato
                    file_result_content = f"=== {os.path.basename(file_path)} ===\n\n"
                    if matching_lines:
                        # Estrai solo il testo delle righe senza "Riga X:"
                        for line in matching_lines:
                            # Rimuovi "Riga X: " e lascia solo il contenuto
                            if ": " in line:
                                content = line.split(": ", 1)[1]
                                file_result_content += content + "\n"
                            else:
                                file_result_content += line + "\n"
                    else:
                        f.seek(0)
                        full_content = f.read()
                        file_result_content += full_content
                    
                    all_results_content.append(file_result_content)
        except Exception as e:
            continue

    # Risposta finale
    if not risultati:
        await update.message.reply_text(f"🔍 Nessun risultato per '{parola}'")
        return

    # Crea un SINGOLO file con TUTTI i risultati combinati
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
        
    result_filename = f"risultati_{safe_parola}_completo.txt"
    result_file_path = os.path.join(TEMP_DIR, result_filename)
    
    with open(result_file_path, "w", encoding="utf-8") as f:
        f.write(f"Ricerca: '{parola}'\n")
        f.write(f"File trovati: {len(risultati)}\n")
        f.write(f"=" * 80 + "\n\n")
        
        # Scrivi tutti i contenuti trovati - PULITI
        for i, result_content in enumerate(all_results_content, 1):
            f.write(result_content)
            f.write("\n" + "-" * 80 + "\n\n")
    
    # Invia il SINGOLO file con TUTTI i risultati
    await update.message.reply_document(
        document=open(result_file_path, "rb"),
        filename=result_filename,
        caption=f"📄 **Tutti i risultati per '{parola}' ({len(risultati)} file trovati)**"
    )
    
    # Cancella il file temporaneo
    try:
        os.remove(result_file_path)
    except:
        pass

def main():
    keep_alive()  # Avvia web server per UptimeRobot
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("search", search))
    app_bot.add_handler(CommandHandler("files", files))
    app_bot.add_handler(CommandHandler("cookies", cookies))
    app_bot.add_handler(CommandHandler("setcookie", setcookie))
    app_bot.add_handler(CommandHandler("setallcookies", setallcookies))
    app_bot.add_handler(CommandHandler("clearcookies", clearcookies))
    app_bot.add_handler(CommandHandler("clearcache", clearcache))
    app_bot.add_handler(CommandHandler("redownload", redownload))
    app_bot.add_handler(CommandHandler("testapi", testapi))
    app_bot.add_handler(CommandHandler("chats", chats))
    app_bot.run_polling()

if __name__ == "__main__":
    main()
