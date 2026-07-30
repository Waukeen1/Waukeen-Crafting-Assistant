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

1. En son GitHub Release icindeki `Waukeen-Crafting-Assistant-Windows.zip`
   dosyasini indirin.
2. ZIP dosyasini kalici bir klasore cikartin.
3. `Waukeen Crafting Assistant.exe` dosyasini calistirin.

Uygulama klasorunun tamaminin korunmasi gerekir; yalnizca EXE dosyasini tasimayin.

## Guncellemeler

`Settings > Auto Update` acikken WCA baslangicta GitHub Releases kanalini arka
planda kontrol eder. `Check for Updates` dugmesi ayni kontrolu elle baslatir.
Yeni paket SHA-256 ile dogrulanir ve ayarlar ile loglar korunarak harici updater
tarafindan uygulanir. Craft aktifse otomatik guncelleme uygulamayi kapatmaz.

## Gelistirme

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller==6.17.0
.\tools\build_release.ps1 -Version 1.0.0
```

Olusan uygulama `build\main-dist\Waukeen Crafting Assistant` altinda, yayin
dosyalari ise `release` altinda bulunur.
