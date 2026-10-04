#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
class Print {
 public:
  virtual ~Print() {}
  virtual size_t write(uint8_t) = 0;
  virtual size_t write(const uint8_t *data, size_t size) {
    for (size_t i=0;i<size;++i) write(data[i]);
    return size;
  }
  size_t print(const char *text) {
    return write(reinterpret_cast<const uint8_t *>(text), std::strlen(text));
  }
};
