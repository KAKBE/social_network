export function bellCount(placeUnread, requests, replies = []) {
  const places = Number.isFinite(placeUnread) && placeUnread > 0 ? Math.trunc(placeUnread) : 0;
  const people = Array.isArray(requests) ? requests.length : 0;
  const answers = Array.isArray(replies) ? replies.length : 0;
  return places + people + answers;
}

export function replyTitle(reply) {
  const name = [reply?.display_name, reply?.surname].filter(Boolean).join(" ").trim();
  return name ? `Ваша заявка принята: ${name}` : "Ваша заявка принята";
}

export function bellLabel(count) {
  return count > 0 ? `Уведомления, ${count}` : "Уведомления";
}
