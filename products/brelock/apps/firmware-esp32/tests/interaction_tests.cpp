#include "control.h"
#include "device_ui.h"
#include <cstdio>
#include <cstdlib>
using namespace brelock;
int checks = 0;
void expect(bool result) {
  ++checks;
  if (!result) { std::fprintf(stderr,"FAIL interaction check %d\n",checks); std::exit(1); }
}
HostStatus host(uint32_t now) {
  HostStatus h; h.session = 0x0102030405060708ULL; h.flags = 3; h.receivedAtMs = now;
  return h;
}
void lockPage(DeviceUi &ui) {
  ui.touch(10,false,120,110,4,host(10)); // wrap right: protection -> lock
}
void calibrationPage(DeviceUi &ui) {
  ui.touch(10,false,120,110,3,host(10));
  ui.touch(20,false,120,110,0,host(20));
  ui.touch(30,false,120,110,3,host(30));
}
int main() {
  const uint8_t status[] = {1,1,7,2,3,100,195,0,250,0,7,0,8,7,6,5,4,3,2,1};
  HostStatus decoded;
  expect(decodeHostStatus(status,sizeof(status),decoded));
  expect(decoded.distanceCm == 250 && decoded.rssiDbm == -61);
  expect(decoded.session == 0x0102030405060708ULL);
  expect(!decodeHostStatus(status,19,decoded));
  uint8_t measuring[20];
  for (unsigned i=0;i<20;++i) measuring[i] = status[i];
  measuring[3] = 4;
  expect(decodeHostStatus(measuring,20,decoded) && decoded.calibration == 4);
  measuring[3] = 5;
  expect(!decodeHostStatus(measuring,20,decoded));
  uint8_t invalid[20]{}; expect(!decodeHostStatus(invalid,20,decoded));
  uint8_t guided[20];
  for (unsigned i=0;i<20;++i) guided[i] = status[i];
  guided[0]=2; guided[3]=5; guided[7]=0x22;
  expect(decodeHostStatus(guided,20,decoded));
  expect(decoded.calibration == 5 && decoded.calibrationStep == 2 && decoded.movementSeconds == 2);
  guided[7]=0x24; expect(!decodeHostStatus(guided,20,decoded));
  guided[7]=0x32; expect(!decodeHostStatus(guided,20,decoded));
  guided[7]=0; expect(!decodeHostStatus(guided,20,decoded));
  guided[7]=0x22; guided[3]=4; expect(!decodeHostStatus(guided,20,decoded));
  guided[7]=2; expect(decodeHostStatus(guided,20,decoded));
  const auto command = encodeControl(DeviceAction::LockNow,7,decoded.session);
  expect(command[0] == 1 && command[1] == 3 && command[2] == 7);
  for (unsigned i=0;i<8;++i) expect(command[4+i] == status[12+i]);
  DeviceUi swipe;
  swipe.touch(100,true,190,110,0,host(100));
  swipe.touch(200,true,80,112,0,host(200));
  expect(swipe.page() == UiPage::Distance);
  swipe.touch(210,false,80,112,3,host(210));
  swipe.touch(215,false,80,112,3,host(215));
  expect(swipe.page() == UiPage::Distance); // final IRQ must not double-swipe
  expect(swipe.takeAction() == DeviceAction::None);
  swipe.touch(300,true,80,110,0,host(300));
  swipe.touch(400,false,180,111,4,host(400));
  expect(swipe.page() == UiPage::Protection);
  DeviceUi hold; lockPage(hold);
  expect(hold.page() == UiPage::Lock);
  hold.touch(100,true,120,110,0,host(100));
  hold.touch(3099,true,120,110,0,host(3099));
  expect(hold.takeAction() == DeviceAction::None);
  expect(hold.holdPercent(1600) == 50);
  hold.touch(3100,true,120,110,0,host(3100));
  expect(hold.takeAction() == DeviceAction::LockNow);
  hold.touch(5100,true,120,110,0,host(5100));
  expect(hold.takeAction() == DeviceAction::None);
  DeviceUi release; lockPage(release);
  release.touch(100,true,120,110,0,host(100));
  release.touch(2900,false,120,110,0,host(2900));
  release.tick(5000,host(5000)); expect(release.takeAction() == DeviceAction::None);
  expect(release.holdPercent(5000) == 0);
  DeviceUi lost; lockPage(lost);
  lost.touch(100,true,120,110,0,host(100));
  lost.touch(3100,true,120,110,0,host(100));
  expect(lost.takeAction() == DeviceAction::None);
  DeviceUi session; lockPage(session);
  session.touch(100,true,120,110,0,host(100));
  auto changed = host(3100); ++changed.session;
  session.touch(3100,true,120,110,0,changed);
  expect(session.takeAction() == DeviceAction::None);
  DeviceUi moved; lockPage(moved);
  moved.touch(100,true,120,110,0,host(100));
  moved.touch(900,true,148,110,0,host(900));
  moved.touch(3100,true,148,110,0,host(3100));
  expect(moved.takeAction() == DeviceAction::None);
  DeviceUi denied; lockPage(denied);
  auto noPermission = host(100); noPermission.flags = 1;
  denied.touch(100,true,120,110,0,noPermission);
  noPermission.receivedAtMs = 3100;
  denied.touch(3100,true,120,110,0,noPermission);
  expect(denied.takeAction() == DeviceAction::None);
  DeviceUi calibration;
  calibrationPage(calibration);
  expect(calibration.page() == UiPage::Calibration);
  calibration.touch(100,true,120,110,0,host(100));
  calibration.touch(200,false,120,110,0,host(200));
  expect(calibration.takeAction() == DeviceAction::None); // short taps cannot start
  calibration.touch(1000,true,120,110,0,host(1000));
  expect(calibration.holdPercent(2500) == 50);
  calibration.touch(3999,true,120,110,0,host(3999));
  expect(calibration.takeAction() == DeviceAction::None);
  calibration.touch(4000,true,120,110,0,host(4000));
  expect(calibration.takeAction() == DeviceAction::StartCalibration);
  calibration.touch(5000,true,120,110,0,host(5000));
  expect(calibration.takeAction() == DeviceAction::None); // exactly one action per hold
  calibration.touch(5100,false,120,110,0,host(5100));
  auto waiting = host(6000); waiting.calibration = 1;
  waiting.flags = 1; // calibration needs BLE, not permission to lock the computer
  calibration.touch(6000,true,120,110,0,waiting);
  waiting.receivedAtMs = 9000;
  calibration.touch(9000,true,120,110,0,waiting);
  expect(calibration.takeAction() == DeviceAction::SaveCalibration);
  calibration.touch(9100,false,120,110,0,waiting);
  auto collecting = host(10000); collecting.calibration = 4;
  calibration.touch(10000,true,120,110,0,collecting);
  collecting.receivedAtMs = 13000;
  calibration.touch(13000,true,120,110,0,collecting);
  expect(calibration.takeAction() == DeviceAction::None); // do not restart a running measurement
  calibration.touch(13100,false,120,110,0,collecting);
  auto retry = host(14000); retry.calibration = 3;
  calibration.touch(14000,true,120,110,0,retry);
  retry.receivedAtMs = 17000;
  calibration.touch(17000,true,120,110,0,retry);
  expect(calibration.takeAction() == DeviceAction::SaveCalibration);
  DeviceUi calRelease; calibrationPage(calRelease);
  calRelease.touch(100,true,120,110,0,host(100));
  calRelease.touch(2900,false,120,110,0,host(2900));
  calRelease.tick(5000,host(5000));
  expect(calRelease.takeAction() == DeviceAction::None && calRelease.holdPercent(5000) == 0);
  DeviceUi calState; calibrationPage(calState);
  calState.touch(100,true,120,110,0,host(100));
  auto measuringHost = host(3100); measuringHost.calibration = 4;
  calState.touch(3100,true,120,110,0,measuringHost);
  expect(calState.takeAction() == DeviceAction::None && calState.holdPercent(3100) == 0);
  DeviceUi calLost; calibrationPage(calLost);
  calLost.touch(100,true,120,110,0,host(100));
  calLost.touch(3100,true,120,110,0,host(100));
  expect(calLost.takeAction() == DeviceAction::None);
  DeviceUi calSession; calibrationPage(calSession);
  calSession.touch(100,true,120,110,0,host(100));
  calSession.touch(3100,true,120,110,0,changed);
  expect(calSession.takeAction() == DeviceAction::None);
  DeviceUi calSwipe; calibrationPage(calSwipe);
  calSwipe.touch(100,true,120,110,0,host(100));
  calSwipe.touch(600,true,45,112,0,host(600));
  calSwipe.tick(3100,host(3100));
  expect(calSwipe.page() == UiPage::Lock && calSwipe.takeAction() == DeviceAction::None);
  DeviceUi guidedUi;
  auto moveHost=host(100); moveHost.calibration=5; moveHost.calibrationStep=1;
  guidedUi.tick(100,moveHost);
  expect(guidedUi.page() == UiPage::Calibration);
  guidedUi.touch(100,true,120,110,0,moveHost);
  moveHost.receivedAtMs=3100;
  guidedUi.touch(3100,true,120,110,0,moveHost);
  expect(guidedUi.takeAction() == DeviceAction::None);
  guidedUi.touch(3110,false,120,110,0,moveHost);
  auto pointHost=host(4000); pointHost.calibration=1; pointHost.calibrationStep=1;
  guidedUi.touch(4000,true,120,110,0,pointHost);
  pointHost.receivedAtMs=7000;
  guidedUi.touch(7000,true,120,110,0,pointHost);
  expect(guidedUi.takeAction() == DeviceAction::SaveCalibration);
  guidedUi.touch(7100,false,120,110,0,pointHost);
  guidedUi.touch(8000,true,120,110,0,pointHost);
  pointHost.calibrationStep=2; pointHost.receivedAtMs=11000;
  guidedUi.touch(11000,true,120,110,0,pointHost);
  expect(guidedUi.takeAction() == DeviceAction::None);
  expect(guidedUi.holdPercent(11000) == 0);
  std::printf("PASS: %d gesture, hold and control protocol checks\n",checks);
}
