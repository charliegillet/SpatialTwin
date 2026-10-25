/*
 * SET_DISPLAY `px` codec. Plain C, no Arduino headers, no dynamic allocation, so the same code
 * is compiled by the sketch and by the host test (firmware/tests/test_px_codec.c).
 *
 * Code table (keep in sync with backend/app/hardware/display.py PX_CODE_RGB):
 *   '0' off            'G' green (steady)   'g' green (flashing)
 *   'R' red (steady)   'r' red (flashing)
 *   'A' amber          'a' amber (flashing)
 *   'B' dim blue       'U' purple (unknown) 'u' purple (flashing)
 * Lowercase = flashing: shown while blinkPhase is true, dark otherwise.
 */
#ifndef SPATIALTWIN_PX_CODEC_H
#define SPATIALTWIN_PX_CODEC_H

#include <stdint.h>
#include <stddef.h>

#define PX_COUNT 24

#define PX_OK            0
#define PX_ERR_MISSING   1  /* no "px":" key */
#define PX_ERR_LENGTH    2  /* not exactly PX_COUNT characters before the closing quote */
#define PX_ERR_CODE      3  /* a character outside the code table */

/* Writes the 0xRRGGBB colour for one code into *rgb and the flashing flag into *flash.
 * Returns 1 for a known code, 0 otherwise. */
static inline int px_code_lookup(char c, uint32_t *rgb, int *flash) {
  *flash = 0;
  switch (c) {
    case '0': *rgb = 0x000000UL; return 1;
    case 'G': *rgb = 0x00A000UL; return 1;
    case 'R': *rgb = 0xB40000UL; return 1;
    case 'A': *rgb = 0xB45000UL; return 1;
    case 'B': *rgb = 0x000028UL; return 1;
    case 'U': *rgb = 0x5A005AUL; return 1;
    case 'g': *rgb = 0x00A000UL; *flash = 1; return 1;
    case 'r': *rgb = 0xB40000UL; *flash = 1; return 1;
    case 'a': *rgb = 0xB45000UL; *flash = 1; return 1;
    case 'u': *rgb = 0x5A005AUL; *flash = 1; return 1;
    default: return 0;
  }
}

/* Finds `"px":"` in a NUL-terminated command line, requires exactly PX_COUNT valid codes followed
 * by a closing quote, and fills rgb[] / flash[]. Outputs are untouched unless PX_OK is returned. */
static inline int px_parse(const char *line, uint32_t rgb_out[PX_COUNT], uint8_t flash_out[PX_COUNT]) {
  static const char key[] = "\"px\":\"";
  const char *p = line;
  const char *start = NULL;
  size_t i;
  uint32_t rgb[PX_COUNT];
  uint8_t flash[PX_COUNT];

  for (; *p; p++) {
    size_t k = 0;
    while (key[k] && p[k] == key[k]) k++;
    if (key[k] == '\0') { start = p + k; break; }
  }
  if (!start) return PX_ERR_MISSING;

  for (i = 0; i < PX_COUNT; i++) {
    int f;
    if (start[i] == '\0' || start[i] == '"') return PX_ERR_LENGTH;
    if (!px_code_lookup(start[i], &rgb[i], &f)) return PX_ERR_CODE;
    flash[i] = (uint8_t)f;
  }
  if (start[PX_COUNT] != '"') return PX_ERR_LENGTH;

  for (i = 0; i < PX_COUNT; i++) { rgb_out[i] = rgb[i]; flash_out[i] = flash[i]; }
  return PX_OK;
}

#endif
