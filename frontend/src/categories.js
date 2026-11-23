export const PLACE_CATEGORIES = [
  { id: "study", label: "Учёба" },
  { id: "food", label: "Еда" },
  { id: "walk", label: "Прогулка" },
  { id: "meet", label: "Встреча" },
];

export function categoryLabel(id) {
  if (!id) return "";
  return PLACE_CATEGORIES.find((item) => item.id === id)?.label ?? id;
}

export function categoryChoices(custom = []) {
  const extra = custom
    .map((item) => (typeof item === "string" ? item : item.title))
    .filter((title) => title && !PLACE_CATEGORIES.some((item) => item.id === title))
    .map((title) => ({ id: title, label: title }));
  return [...PLACE_CATEGORIES, ...extra];
}
