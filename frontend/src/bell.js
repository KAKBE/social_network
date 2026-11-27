export function bellCount(placeUnread, requests) {
  const places = Number.isFinite(placeUnread) && placeUnread > 0 ? Math.trunc(placeUnread) : 0;
  const people = Array.isArray(requests) ? requests.length : 0;
  return places + people;
}

export function bellLabel(count) {
  return count > 0 ? `Уведомления, ${count}` : "Уведомления";
}
