/**
 * `noUncheckedIndexedAccess` types every index access as possibly undefined,
 * which is right for app code and noise in a test that is asserting the
 * element exists. `at()` makes the assertion explicit and fails loudly.
 */
export function at<T>(items: readonly T[] | undefined, index: number): T {
  const item = items?.[index];
  if (item === undefined) throw new Error(`Expected an element at index ${index}`);
  return item;
}
