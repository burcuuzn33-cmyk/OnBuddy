"""Basit kayan pencere hız sınırı (IP başına).

Sayaçlar uygulama belleğindedir: gunicorn tek worker ile çalışırken yeterlidir.
Birden fazla worker/sunucuda ortak bir depo (ör. Redis) gerekir.
"""
from collections import deque
from math import ceil
from threading import Lock
from time import monotonic


class HizSiniri:
    def __init__(self, maks_istek, pencere_saniye):
        self.maks_istek = maks_istek
        self.pencere_saniye = pencere_saniye
        self._istekler = {}
        self._kilit = Lock()

    def izin_ver(self, anahtar):
        """İzin varsa isteği sayar ve 0 döner; yoksa kaç saniye sonra denenebileceğini döner."""
        simdi = monotonic()
        sinir = simdi - self.pencere_saniye
        with self._kilit:
            # Süresi dolan kayıtlar ve boşalan ziyaretçiler silinir; bellek büyümez
            for anahtar_ in list(self._istekler):
                zamanlar = self._istekler[anahtar_]
                while zamanlar and zamanlar[0] <= sinir:
                    zamanlar.popleft()
                if not zamanlar:
                    del self._istekler[anahtar_]

            zamanlar = self._istekler.setdefault(anahtar, deque())
            if len(zamanlar) >= self.maks_istek:
                return max(1, ceil(zamanlar[0] + self.pencere_saniye - simdi))
            zamanlar.append(simdi)
            return 0
