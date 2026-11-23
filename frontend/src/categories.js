export const PLACE_CATEGORIES = [
  { id: "study", label: "Учёба" },
  { id: "food", label: "Еда" },
  { id: "walk", label: "Прогулка" },
  { id: "meet", label: "Встреча" },
];

export function categoryLabel(id) {
  return PLACE_CATEGORIES.find((item) => item.id === id)?.label ?? "";
}
