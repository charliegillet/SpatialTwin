/* Host test for px_codec.h: cc -I../spatialtwin_board test_px_codec.c && ./a.out */
#include <stdio.h>
#include <string.h>
#include "px_codec.h"

static int failures = 0;
#define CHECK(cond) do { if (!(cond)) { printf("FAIL line %d: %s\n", __LINE__, #cond); failures++; } } while (0)

static int parse(const char *line, uint32_t *rgb, uint8_t *fl) { return px_parse(line, rgb, fl); }

int main(void) {
  uint32_t rgb[PX_COUNT]; uint8_t fl[PX_COUNT];
  uint32_t sentinel = 0xDEADBEEFUL;
  int i;

  /* Valid line: P1 green, P2 red, P3 flashing amber. */
  const char *ok = "{\"v\":1,\"type\":\"SET_DISPLAY\",\"session_id\":\"s\",\"command_id\":\"cmd-7\","
                   "\"px\":\"GGGGGGGGRRRRRRRRaaaaaaaa\"}";
  CHECK(parse(ok, rgb, fl) == PX_OK);
  CHECK(rgb[0] == 0x00A000UL && !fl[0] && rgb[7] == 0x00A000UL);
  CHECK(rgb[8] == 0xB40000UL && !fl[8]);
  CHECK(rgb[16] == 0xB45000UL && fl[16] == 1 && fl[23] == 1);

  /* Every code in the table is accepted with the right flash flag. */
  {
    const char *codes = "0GRABUgrau"; const int flashes[] = {0,0,0,0,0,0,1,1,1,1};
    for (i = 0; i < 10; i++) {
      uint32_t c; int f;
      CHECK(px_code_lookup(codes[i], &c, &f) == 1 && f == flashes[i]);
    }
  }
  CHECK(px_code_lookup('X', &sentinel, &i) == 0);
  CHECK(px_code_lookup('1', &sentinel, &i) == 0);

  /* Wrong length: 23, 25, empty, unterminated. */
  for (i = 0; i < PX_COUNT; i++) rgb[i] = 0x11111111UL;
  CHECK(parse("{\"px\":\"GGGGGGGGGGGGGGGGGGGGGGG\"}", rgb, fl) == PX_ERR_LENGTH);
  CHECK(parse("{\"px\":\"GGGGGGGGGGGGGGGGGGGGGGGGG\"}", rgb, fl) == PX_ERR_LENGTH);
  CHECK(parse("{\"px\":\"\"}", rgb, fl) == PX_ERR_LENGTH);
  CHECK(parse("{\"px\":\"GGGGGGGGGGGGGGGGGGGGGGGG", rgb, fl) == PX_ERR_LENGTH);
  CHECK(rgb[0] == 0x11111111UL); /* outputs untouched on error */

  /* Unknown code and lowercase look-alikes outside the table. */
  CHECK(parse("{\"px\":\"GGGGGGGGGGGGGGGGGGGGGGGX\"}", rgb, fl) == PX_ERR_CODE);
  CHECK(parse("{\"px\":\"bGGGGGGGGGGGGGGGGGGGGGGG\"}", rgb, fl) == PX_ERR_CODE);
  CHECK(parse("{\"px\":\"GGGGGGGGGGGGGGGGGGGGGGG \"}", rgb, fl) == PX_ERR_CODE);

  /* Missing key, empty line. */
  CHECK(parse("{\"type\":\"SET_DISPLAY\"}", rgb, fl) == PX_ERR_MISSING);
  CHECK(parse("", rgb, fl) == PX_ERR_MISSING);
  CHECK(parse("{\"px\":", rgb, fl) == PX_ERR_MISSING);
  CHECK(parse("{\"px\":\"GGGG", rgb, fl) == PX_ERR_LENGTH);

  /* All off. */
  CHECK(parse("{\"px\":\"000000000000000000000000\"}", rgb, fl) == PX_OK && rgb[23] == 0 && !fl[23]);

  if (failures) { printf("%d failure(s)\n", failures); return 1; }
  printf("px_codec: all checks passed\n");
  return 0;
}
