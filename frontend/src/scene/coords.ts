// Floor metres (x east, y north) to world space. Floor shapes use rotation.x = -PI/2 so that (x, y) -> (x, 0, -y).
export function toWorld(x: number, y: number, height = 0): [number, number, number] {
  return [x, height, -y];
}
