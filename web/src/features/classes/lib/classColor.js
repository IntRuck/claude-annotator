/** Colour of a class: hues spread by the golden angle so neighbours look different (same as today's app). */
export function classColor(index) {
  return `hsl(${(index * 137.508) % 360} 80% 50%)`;
}
