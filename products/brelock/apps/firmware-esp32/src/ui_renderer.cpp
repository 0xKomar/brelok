#include "ui_renderer.h"
#include <Fonts/FreeSans9pt7b.h>
#include <Fonts/FreeSansBold12pt7b.h>
#include <Fonts/FreeSansBold18pt7b.h>
#include <cmath>
#include <cstdio>
namespace brelock {
namespace {
constexpr uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3);
}
constexpr auto bg = rgb(9, 17, 31), panel = rgb(19, 33, 52);
constexpr auto white = rgb(230, 239, 250), muted = rgb(139, 161, 186);
constexpr auto blue = rgb(108, 177, 232), green = rgb(94, 206, 156);
constexpr auto red = rgb(231, 109, 113), amber = rgb(227, 178, 98);
void text(Adafruit_GFX &g, const char *value, int y, const GFXfont *font,
          uint16_t color) {
  g.setFont(font); g.setTextSize(1); g.setTextColor(color);
  int16_t x, top; uint16_t w, h;
  g.getTextBounds(value, 0, y, &x, &top, &w, &h);
  g.setCursor((240 - w) / 2 - x, y); g.print(value);
}
void small(Adafruit_GFX &g, const char *value, int y, uint16_t color = muted) {
  text(g, value, y, nullptr, color);
}
void ring(Adafruit_GFX &g, int radius, int percent, uint16_t color,
          int start = -90, int sweep = 360, int thickness = 3) {
  const int end = start + sweep * percent / 100;
  for (int degrees = start; degrees <= end; degrees += 2) {
    const float angle = degrees * 0.01745329252f;
    g.fillCircle(120 + std::lround(std::cos(angle) * radius),
                 115 + std::lround(std::sin(angle) * radius), thickness, color);
  }
}
void shield(Adafruit_GFX &g, uint16_t color, bool tick) {
  const int x[] = {120,148,145,137,120,103,95,92,120};
  const int y[] = {67,78,113,127,143,127,113,78,67};
  for (unsigned i = 0; i < 8; ++i)
    for (int o = 0; o < 3; ++o) g.drawLine(x[i]+o,y[i],x[i+1]+o,y[i+1],color);
  if (tick) {
    for (int o = -1; o <= 1; ++o) {
      g.drawLine(107,104+o,117,114+o,color);
      g.drawLine(117,114+o,135,93+o,color);
    }
  } else g.fillCircle(121,104,3,color);
}
void lockIcon(Adafruit_GFX &g, uint16_t color) {
  for (int i = 0; i < 3; ++i)
    g.drawRoundRect(104+i,72+i,33-2*i,39-2*i,16-i,color);
  g.fillRoundRect(94,98,53,43,9,panel);
  for (int i = 0; i < 2; ++i) g.drawRoundRect(94+i,98+i,53-2*i,43-2*i,9,color);
  g.fillCircle(120,115,4,color); g.fillRect(118,115,5,12,color);
}
void target(Adafruit_GFX &g, uint16_t color) {
  g.drawCircle(120,90,20,color); g.drawCircle(120,90,12,color);
  g.fillCircle(120,90,4,color);
  g.drawFastHLine(91,90,12,color); g.drawFastHLine(137,90,12,color);
  g.drawFastVLine(120,61,12,color); g.drawFastVLine(120,107,12,color);
}
}
void renderDeviceUi(Adafruit_GFX &g, const UiRenderState &s) {
  g.fillScreen(bg); g.setTextWrap(false);
  char label[40]{};
  const char *titles[] = {"OCHRONA","DYSTANS","KALIBRACJA","BLOKADA"};
  small(g,titles[static_cast<unsigned>(s.page)],17,white);
  const auto accent = !s.online ? muted : s.host.protection == 1 ? green
                         : s.host.protection == 2 ? amber : red;
  switch (s.page) {
    case UiPage::Protection:
      ring(g,88,100,panel,155,230);
      ring(g,88,100,accent,155,230,1);
      shield(g,accent,s.online && s.host.protection == 1);
      text(g,!s.online ? "BRAK PC" : s.host.protection == 1 ? "AKTYWNA"
             : s.host.protection == 2 ? "POWROT" : "WYLACZONA",
           177,&FreeSansBold12pt7b,accent);
      small(g,!s.online ? "Uruchom aplikacje" : s.host.protection == 1
            ? "Komputer chroniony" : s.host.protection == 2
            ? "Czekam na powrot" : "Ochrona nieaktywna",196);
      break;
    case UiPage::Distance: {
      ring(g,88,100,panel,135,270);
      const bool known = s.online && (s.host.flags & 1) && s.host.distanceCm != 0xFFFF;
      const int gauge = known ? s.host.distanceCm / 5 : 0;
      if (known) ring(g,88,gauge > 100 ? 100 : gauge,blue,135,270);
      if (known) std::snprintf(label,sizeof(label),"~%.1f",s.host.distanceCm/100.0f);
      else std::snprintf(label,sizeof(label),"--");
      text(g,label,124,&FreeSansBold18pt7b,white);
      text(g,"metra",149,&FreeSans9pt7b,muted);
      if (s.online && s.host.rssiDbm != -128)
        std::snprintf(label,sizeof(label),"%d dBm / %s",
                      s.host.rssiDbm,s.moving ? "ruch" : "spoczynek");
      else std::snprintf(label,sizeof(label),"Brak swiezych danych");
      small(g,label,182,blue); small(g,"Szacunek z sygnalu BLE",196);
      break;
    }
    case UiPage::Calibration: {
      const bool waiting = s.host.calibration == 1 || s.host.calibration == 3;
      const bool collecting = s.host.calibration == 4;
      const bool moving = s.host.calibration == 5;
      const auto color = s.online && s.host.calibration == 2 ? green : blue;
      if (s.online && s.host.calibrationStep) {
        std::snprintf(label,sizeof(label),"KROK %u/3 / %u M",s.host.calibrationStep,s.host.calibrationStep);
        small(g,label,38,blue);
      }
      g.fillCircle(120,110,61,panel); ring(g,66,100,panel);
      if (s.online && moving) {
        ring(g,66,(2-s.host.movementSeconds)*50,blue);
        std::snprintf(label,sizeof(label),"%u m",s.host.calibrationStep);
        text(g,label,122,&FreeSansBold18pt7b,white);
        std::snprintf(label,sizeof(label),"%u s",s.host.movementSeconds);
        text(g,label,158,&FreeSans9pt7b,blue);
        small(g,"COFNIJ SIE O 1 M",188,blue);
        small(g,"Od laptopa na stole",201);
        break;
      }
      if (s.online && s.holdPercent) ring(g,66,s.holdPercent,blue);
      else if (s.online && collecting) ring(g,66,s.host.calibrationPercent,color);
      else ring(g,66,100,s.online ? color : muted,-90,360,1);
      target(g,s.online ? color : muted);
      text(g,!s.online ? "BRAK PC" : s.host.calibration == 2 ? "ZAPISANO"
                  : collecting ? "POMIAR" : waiting ? "POMIAR" : "START",
           137,&FreeSansBold12pt7b,s.online ? color : muted);
      if (s.holdPercent > 0 && s.holdPercent < 100) {
        std::snprintf(label,sizeof(label),"%.1f s",3.0f-s.holdPercent*0.03f);
        text(g,label,165,&FreeSans9pt7b,blue);
      }
      small(g,!s.online ? "Uruchom aplikacje" : s.holdPercent == 100
                 ? "PUSC PALEC" : s.host.calibration == 3
                 ? "Przytrzymaj: ponow pomiar" : s.host.calibration == 2
                 ? "Przytrzymaj: nowy pomiar" : collecting ? "Nie ruszaj sie / 12-35 s"
                 : "PRZYTRZYMAJ 3 S",188);
      if (collecting) {
        std::snprintf(label,sizeof(label),"%u%% / zapis automatyczny",s.host.calibrationPercent);
        small(g,label,201);
      } else small(g,s.holdPercent == 100 ? "Zadanie wyslane"
                        : s.holdPercent ? "Puszczenie anuluje"
                        : waiting && s.host.calibrationStep ? "Potwierdz swoja pozycje"
                        : waiting ? "Odleglosc ustaw w PC" : "Seria 1 / 2 / 3 m",201);
      break;
    }
    case UiPage::Lock: {
      const bool enabled = s.online && s.host.lockAvailable();
      const auto color = enabled ? red : muted;
      ring(g,65,100,panel);
      if (s.holdPercent) ring(g,65,s.holdPercent,red);
      lockIcon(g,color);
      if (s.holdPercent > 0 && s.holdPercent < 100) {
        std::snprintf(label,sizeof(label),"%.1f s",3.0f-s.holdPercent*0.03f);
        text(g,label,165,&FreeSans9pt7b,red);
      } else {
        small(g,!s.online ? "BRAK POLACZENIA" : !enabled ? "BRAK UPRAWNIEN"
                  : s.host.feedback == 1 ? "ZADANIE WYSLANE"
                  : s.host.feedback == 2 ? "BLAD BLOKADY" : "PRZYTRZYMAJ 3 S",
              160,color);
      }
      small(g,"Puszczenie anuluje",183); small(g,"Zablokuj komputer",198);
      break;
    }
  }
  for (int i = 0; i < 4; ++i)
    g.fillCircle(102+i*12,215,i == static_cast<int>(s.page) ? 3 : 2,
                 i == static_cast<int>(s.page) ? blue : muted);
  if (s.batteryMv)
    std::snprintf(label,sizeof(label),"%s %.2f V",
                  s.online ? "PC" : s.bleHealthy ? "BLE" : "--",s.batteryMv/1000.0f);
  else std::snprintf(label,sizeof(label),"%s",s.online ? "PC POLACZONY" : "PC OFFLINE");
  small(g,label,229);
}
}  // namespace brelock
