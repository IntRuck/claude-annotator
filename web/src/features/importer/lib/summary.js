/** Turns the server's import result into the plain-language lines the dialog shows. */
export function summaryLines(r) {
  const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
  const lines = [`Added ${plural(r.added, 'image')} · ${r.labelled} labelled with ${plural(r.boxes, 'box', 'boxes')}`];
  if (r.classesCreated.length) lines.push(`Classes from the folder: ${r.classesCreated.join(', ')}`);
  if (r.keptExistingClasses) lines.push("Kept this project's classes; the class list in the folder wasn't used.");
  if (r.placeholderClasses.length) {
    lines.push(`Some label IDs had no class name, so they got placeholder classes: ${r.placeholderClasses.join(', ')}. Rename them in SKUs.`);
  }
  if (r.statesApplied) lines.push(`Statuses and flags brought over for ${plural(r.statesApplied, 'image')}.`);
  if (r.labelsWithoutImage.length) lines.push(`No image for these label files: ${r.labelsWithoutImage.join(', ')}`);
  if (r.badLabelLines) lines.push(`${plural(r.badLabelLines, 'label line')} could not be read and were skipped.`);
  if (r.ignoredFiles.length) lines.push(`${r.ignoredFiles.length} other ${r.ignoredFiles.length === 1 ? 'file' : 'files'} ignored.`);
  return [...lines, ...r.warnings];
}
