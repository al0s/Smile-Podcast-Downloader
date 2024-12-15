import requests
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
import argparse
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_help()  # Kullanıcıya yardım mesajını göster
        print(f"\nHata: {message}")  # Hatanın nedenini belirt
        exit(2)  # Programı hata kodu ile sonlandır

# CustomArgumentParser ile argümanları işle
parser = CustomArgumentParser(description="Podcast RSS İşleyici")
parser.add_argument("--son", type=int, default=None, help="Son kaç ay içerisindeki bölümleri görüntülemek istediğinizi belirtin.")
parser.add_argument("-i", "--indir", action="store_true", help="Bölümleri indir.")
parser.add_argument("-g", "--goster", action="store_true", help="Bölüm başlıklarını göster.")
parser.add_argument("--klasor", type=str, default=None, help="İndirilecek dosyaların kaydedileceği klasör yolunu belirtin.")
parser.add_argument("-e", type=int, choices=[0, 1, 2], default=0, 
                    help="Başlık biçimi: 0 (sadece başlık), 1 (tarih ve başlık), 2 (tarih, saat ve başlık)")
args = parser.parse_args()


def dosya_adini_duzelt(dosya_adi):
    # Dosya adlarında geçersiz karakterleri temizler
    gecersiz_karakterler = '<>:"/\\|?*'
    return ''.join(c for c in dosya_adi if c not in gecersiz_karakterler).split("  ")[0]

# Saatleri değiştir (tersten sırala ve başlıklarda güncelle)
def saatleri_degistir_ve_guncelle(audios):
    if not audios:
        return audios

    # Yayınlanma saatlerini al ve ters sırada sırala
    saatler = [audio[2] for audio in audios]
    ters_saatler = saatler[::-1]

    # Saatleri ve başlıkları güncelle
    for idx, audio in enumerate(audios):
        audio[2] = ters_saatler[idx]  # Saat güncelle
        eski_baslik = audio[0].split(' ', 2)[2]  # Tarih ve eski saat dışında kalan başlık
        if args.e == 2:
            yeni_baslik = f"{audio[0].split(' ')[0]} {ters_saatler[idx].replace(':', '-')} {eski_baslik}"
        elif args.e == 1:
            yeni_baslik = f"{audio[0].split(' ')[0]} {eski_baslik}"
        else:
            yeni_baslik = eski_baslik
        audio[0] = yeni_baslik  # Başlığı güncelle
    return audios

def turkce_capitalize(kelime):
    if not kelime:
        return kelime
    # İlk harfi büyüt, geri kalanını küçük yap
    ilk_harf = kelime[0].translate(upper_map)
    geri_kalan = kelime[1:].translate(lower_map)
    return ilk_harf + geri_kalan

def format_baslik(baslik):
    return " ".join([turkce_capitalize(kelime) for kelime in baslik.split()])

def dosya_indir(dosya_url, dosya_yolu):
    try:
        r = requests.get(dosya_url, stream=True)
        r.raise_for_status()
        with open(dosya_yolu, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"İndirildi: {dosya_yolu}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"İndirme başarısız: {dosya_url}, Hata: {e}")
        return False

def saat_dilimi_donustur(tarih_str):
    saat_dilimleri = {
        "EST": "-0500",
        "EDT": "-0400",
        "CST": "-0600",
        "CDT": "-0500",
        "MST": "-0700",
        "MDT": "-0600",
        "PST": "-0800",
        "PDT": "-0700"
    }
    for dilim, offset in saat_dilimleri.items():
        if dilim in tarih_str:
            return tarih_str.replace(dilim, offset)
    return tarih_str


# Kullanıcıdan bir bağlantı al
link_dosyasi = "links.txt"

# links.txt dosyasını oku
try:
    with open(link_dosyasi, "r") as file:
        linkler = file.readlines()
except FileNotFoundError:
    print("links.txt dosyası bulunamadı.")
    exit()

# İlk bağlantıyı al
try:
    secilen_link = linkler[0].strip()
except IndexError:
    print("links.txt dosyasında bağlantı bulunamadı.")
    exit()

# Podcast RSS dosyasını çek
try:
    response = requests.get(secilen_link)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"Bağlantıya erişim sağlanamadı: {e}")
    exit()

# XML içeriğini işle
try:
    root = ET.fromstring(response.content)
except ET.ParseError:
    print("XML içeriği çözümlemede hata.")
    exit()


# Podcast program adını al
program_adi = root.find(".//channel/title").text.strip()
# Kullanıcı bir klasör belirtmişse onu kullan, yoksa varsayılan oluştur
temiz_program_adi = dosya_adini_duzelt(program_adi)
klasor_adi = args.klasor if args.klasor else f"PO - {temiz_program_adi}"
indirilenler_dosyasi = os.path.join(klasor_adi, "zaten_indirilenler.txt")

# Klasör oluştur
if args.indir and not os.path.exists(klasor_adi):
    klasor_adi=dosya_adini_duzelt(klasor_adi)
    os.makedirs(klasor_adi)

# Zaten indirilenleri yükle
indirilenler = set()
if os.path.exists(indirilenler_dosyasi):
    with open(indirilenler_dosyasi, "r") as f:
        indirilenler = set(f.read().splitlines())

# Türkçe harf dönüşüm tabloları
lcase_table = ''.join(u'abcçdefgğhıijklmnoöprsştuüvyzîûâ')
ucase_table = ''.join(u'ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZÎÛÂ')

# Büyük/küçük harf dönüşüm haritaları
lower_map = str.maketrans(ucase_table, lcase_table)
upper_map = str.maketrans(lcase_table, ucase_table)

# Podcast ses dosyalarının bağlantılarını, yayınlanma tarihlerini ve başlıklarını toplama
audio_links = []
publication_groups = defaultdict(list)

for item in root.findall(".//item"):
    enclosure = item.find("enclosure")
    pub_date = item.find("pubDate")
    title = item.find("title")

    if enclosure is None or not enclosure.get("url"):
        print("Ses dosyası bağlantısı bulunamadı.")
        continue
    if pub_date is None or not pub_date.text:
        print("Yayınlanma tarihi bulunamadı, atlanıyor.")
        continue
    if title is None:
        print("Başlık bulunamadı, atlanıyor.")
        continue

    pub_date_str = pub_date.text
    pub_date_str = saat_dilimi_donustur(pub_date_str)  # Saat dilimini dönüştür

    try:
        pub_date_parsed = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
    except ValueError:
        print(f"Tarih formatı çözümlemede hata: {pub_date_str}")
        continue

    # Tarih formatını 2019.01.16 gibi ayarla
    formatted_date = pub_date_parsed.strftime("%Y.%m.%d")
    formatted_time = pub_date_parsed.strftime("%H-%M-%S")
    episode_title = f"{formatted_date} {formatted_time} {format_baslik(title.text.strip())}"

    publication_groups[formatted_date].append([episode_title, enclosure.get("url"), pub_date_parsed.strftime("%H:%M:%S")])


# Tarih filtresi uygula
if args.son is not None:
    tarih_limiti = datetime.now() - timedelta(days=args.son * 30)
    publication_groups = {
        date: audios
        for date, audios in publication_groups.items()
        if datetime.strptime(date, "%Y.%m.%d") >= tarih_limiti
    }



if publication_groups:
    print("Yayınlanma tarihlerine göre gruplandırılmış ses dosyaları:")
    for date, audios in sorted(publication_groups.items()):
        publication_groups[date] = saatleri_degistir_ve_guncelle(audios)
        if args.goster:
            for title, _, _ in audios:
                print(title)  # Sadece başlığı yazdır
        if args.indir:
            with open(indirilenler_dosyasi, "a") as f:
                for title, audio, _ in audios:
                    if audio in indirilenler:
                        print(f"Zaten indirildi: {audio}")
                        continue
                    temizlenmis_baslik = dosya_adini_duzelt(title)
                    dosya_adi = os.path.join(klasor_adi, f"{temizlenmis_baslik}.mp3")
                    if dosya_indir(audio, dosya_adi):
                        f.write(audio + "\n")
                        f.flush()  # Veriyi hemen diske yaz
                        indirilenler.add(audio)
else:
    print("Belirtilen süre içerisinde herhangi bir ses dosyası bulunamadı.")