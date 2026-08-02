# Waukeen Crafting Assistant

Waukeen Crafting Assistant (WCA), Path of Exile icin cluster, map, socket/color
ve base jewel craft akislari sunan Windows masaustu uygulamasidir.

Map Craft ekraninda Normal Map ve Memory/Nightmare icin ayri istenmeyen mod
listeleri bulunur. Quant, Rarity ve Pack esikleri birlikte kontrol edilir.
`Alchemy + Vaal` modu, Chain ile envanterdeki T16 mapleri sirayla isler. Normal
rarity maplere once Alchemy, Rare maplere dogrudan Vaal uygular; kabul edilmeyen
sonuclari acik stashe Ctrl+sol tikla gonderir. Bu moddan once Orb Locations
ekraninda Vaal Orb konumu ayarlanmalidir.

## Kurulum

1. En son GitHub Release icindeki `Waukeen-Crafting-Assistant-Setup-vX.Y.Z.exe`
   dosyasini indirin.
2. Setup'i calistirin ve kurulum adimlarini tamamlayin.
3. Masaustu veya Baslat menusu kisayolundan WCA'yi acin.

ZIP paketi tasinabilir kurulum gerektiren durumlar icin ayrica sunulur.

## Guncellemeler

WCA her baslangicta GitHub Releases kanalini zorunlu olarak kontrol eder. Kontrol
tamamlanmadan ana ekran kullanilamaz. Yeni paket SHA-256 ile dogrulanir; ayarlar,
loglar ve kullanici tarafindan duzenlenen template'ler korunarak harici updater
tarafindan uygulanir.

## Gelistirme

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller==6.17.0
.\tools\build_setup.ps1 -Version 1.0.42
```

Olusan uygulama `build\main-dist\Waukeen Crafting Assistant` altinda, yayin
dosyalari ve Windows setup ise `release` altinda bulunur. Setup derlemek icin
Inno Setup 6 gerekir. Dagitim paketine WCA'nin `.py`/`.pyw` kaynak dosyalari
eklenmez.
