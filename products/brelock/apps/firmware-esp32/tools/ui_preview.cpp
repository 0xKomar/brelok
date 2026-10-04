#include "ui_renderer.h"
#include <cstdio>
#include <string>
int main(int argc,char **argv) {
  if (argc != 2) return 1;
  GFXcanvas16 canvas(240,240);
  brelock::UiRenderState state;
  state.online = true; state.bleHealthy = true; state.batteryMv = 4110;
  state.host.protection = 1; state.host.flags = 3; state.host.distanceCm = 230;
  state.host.rssiDbm = -65; state.host.calibrationPercent = 70;
  for (int i=0;i<12;++i) {
    state.page = static_cast<brelock::UiPage>(i < 4 ? i : i < 6 ? 3 : 2);
    state.host.calibration = i == 2 ? 0 : i == 7 ? 4 : i == 8 ? 2 : 1;
    state.host.calibrationStep = i >= 7 ? (i == 9 ? 2 : i == 10 ? 1 : 3) : 0;
    if (i == 9) state.host.calibration=5;
    state.host.movementSeconds = i == 9 ? 2 : 0;
    state.holdPercent = (i == 4 || i == 6) ? 55 : 0;
    state.online = i != 5;
    brelock::renderDeviceUi(canvas,state);
    const std::string path = std::string(argv[1])+"/"+std::to_string(i)+".ppm";
    FILE *file = std::fopen(path.c_str(),"wb");
    if (!file) return 2;
    std::fprintf(file,"P6\n240 240\n255\n");
    for (int p=0;p<240*240;++p) {
      const auto rgb = canvas.getBuffer()[p];
      const uint8_t pixel[] = {
        static_cast<uint8_t>(((rgb>>11)&31)*255/31),
        static_cast<uint8_t>(((rgb>>5)&63)*255/63),
        static_cast<uint8_t>((rgb&31)*255/31)
      };
      std::fwrite(pixel,1,3,file);
    }
    std::fclose(file);
  }
}
