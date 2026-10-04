#pragma once
#include <cstdint>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <string>
#define PROGMEM
using String = std::string;
class __FlashStringHelper;
inline void yield() {}
inline float radians(float degrees) { return degrees * 0.01745329252f; }
