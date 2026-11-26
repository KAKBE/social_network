export function friendRecommendations(items, { city = "", author = "" } = {}) {
  const placeCity = city.trim();
  return items.filter((item) => {
    if (item.is_own) return false;
    if (placeCity && (item.place?.city ?? "") !== placeCity) return false;
    if (author && item.author?.username !== author) return false;
    return true;
  });
}
